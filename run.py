"""Run the full liquidity pack: data -> LCR/NSFR -> attribution -> forecast -> outputs.

Usage:
    python run.py                 # use data/ if present, otherwise generate it
    python run.py --regenerate    # rebuild the synthetic dataset first
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from liquidity_monitor import attribution, commentary, data, forecast, lcr, nsfr, plots

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "output"


def load_inputs(regenerate: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    pos_path, pipe_path = DATA / "positions.csv", DATA / "pipeline.csv"
    if regenerate or not pos_path.exists():
        DATA.mkdir(exist_ok=True)
        positions = data.generate_positions()
        positions.to_csv(pos_path, index=False)
        data.generate_pipeline(positions["date"].max()).to_csv(pipe_path, index=False)
    positions = pd.read_csv(pos_path, parse_dates=["date"])
    pipeline = pd.read_csv(pipe_path, parse_dates=["date"])
    return positions, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=10)
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    positions, pipeline = load_inputs(args.regenerate)

    lcr_daily = lcr.compute(positions)
    nsfr_daily = nsfr.compute(positions)
    fcst = forecast.forecast_lcr(positions, pipeline, horizon=args.horizon)

    dates = lcr_daily.index
    drivers = attribution.explain_move(
        positions, dates[-1 - args.lookback], dates[-1], by="business"
    )

    lcr_daily.join(nsfr_daily, rsuffix="_nsfr").round(4).to_csv(OUT / "lcr_nsfr_daily.csv")
    fcst.round(4).to_csv(OUT / "lcr_forecast.csv")
    drivers.round(1).to_csv(OUT / "surplus_attribution.csv", index=False)

    plots.lcr_history(lcr_daily, OUT / "lcr_history.png")
    plots.attribution_bars(
        drivers, "business",
        f"What moved the LCR surplus - last {args.lookback} business days",
        OUT / "surplus_attribution.png",
    )
    plots.lcr_forecast(lcr_daily, fcst, OUT / "lcr_forecast.png")

    text = commentary.build(positions, lcr_daily, nsfr_daily, fcst, pipeline,
                            lookback=args.lookback)
    (OUT / "alco_commentary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
