"""Generate senior-management (ALCO-style) commentary in Markdown.

The goal is the short narrative a Treasury analyst writes on top of the
numbers: where we are, what moved and why, what is coming, what to watch.
"""

from __future__ import annotations

import pandas as pd

from . import attribution, config


def _eur(x: float, signed: bool = True) -> str:
    sign = "-" if x < 0 else ("+" if signed and x > 0 else "")
    return f"{sign}EUR {abs(x) / 1000:,.2f}bn"


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _driver_lines(drivers: pd.DataFrame, label_cols: list[str], top: int = 3) -> list[str]:
    lines = []
    for _, row in drivers.head(top).iterrows():
        label = " / ".join(str(row[c]) for c in label_cols if row[c])
        lines.append(f"- {label}: {_eur(row['delta'])}")
    return lines


def build(
    positions: pd.DataFrame,
    lcr_daily: pd.DataFrame,
    nsfr_daily: pd.DataFrame,
    fcst: pd.DataFrame,
    pipeline: pd.DataFrame,
    lookback: int = 20,
) -> str:
    dates = lcr_daily.index
    today, prev, past = dates[-1], dates[-2], dates[-1 - lookback]
    t = lcr_daily.loc[today]
    entity = positions["entity"].iloc[0]

    dod = attribution.explain_move(positions, prev, today, by="business")
    period = attribution.explain_move(
        positions, past, today, by=["business", "product", "counterparty"]
    )
    vol = attribution.volatility_by_business(positions, window=lookback)

    status = "within" if t["lcr"] >= config.LCR_INTERNAL_LIMIT else "BELOW"
    nsfr_today = nsfr_daily.loc[today, "nsfr"]
    fmin_idx = fcst["lcr"].idxmin()
    fmin = fcst.loc[fmin_idx]

    md = [
        f"# Liquidity update - {entity} - {today:%d %b %Y}",
        "",
        "## Headline",
        f"- **LCR {_pct(t['lcr'])}** ({status} the {_pct(config.LCR_INTERNAL_LIMIT)} "
        f"internal limit; regulatory minimum {_pct(config.REG_MINIMUM)}).",
        f"- Surplus over 100%: {_eur(t['surplus'], False)}; headroom to internal "
        f"limit: {_eur(t['surplus_vs_internal_limit'], False)}.",
        f"- HQLA {_eur(t['hqla'], False)} vs net stressed outflows "
        f"{_eur(t['net_outflow'], False)}.",
        f"- **NSFR {_pct(nsfr_today)}** (internal limit "
        f"{_pct(config.NSFR_INTERNAL_LIMIT)}).",
        "",
        "## Day-on-day",
        f"Surplus moved {_eur(dod.attrs['reported_change'])} vs {prev:%d %b}. Main drivers:",
        *_driver_lines(dod, ["business"]),
        "",
        f"## Last {lookback} business days",
        f"LCR {_pct(lcr_daily.loc[past, 'lcr'])} -> {_pct(t['lcr'])}; surplus "
        f"{_eur(period.attrs['reported_change'])}. Largest drivers by business / "
        "product / counterparty:",
        *_driver_lines(period, ["business", "product", "counterparty"], top=4),
        "",
        f"Most volatile contributor: **{vol.index[0]}** "
        f"(daily std {_eur(vol.iloc[0, 0], False)}).",
        "",
        f"## Outlook - next {len(fcst)} business days",
        f"- Projected low point: **LCR {_pct(fmin['lcr'])} on {fmin_idx:%d %b}** "
        f"(low case {_pct(fmin['lcr_low'])}).",
    ]
    if fcst["below_internal_limit"].any():
        first = fcst.index[fcst["below_internal_limit"]][0]
        md.append(f"- **Warning:** base case breaches the internal limit from {first:%d %b}.")
    elif fcst["low_case_below_limit"].any():
        first = fcst.index[fcst["low_case_below_limit"]][0]
        md.append(f"- Watch: low case falls below the internal limit from {first:%d %b}.")
    else:
        md.append("- Base and low case stay above the internal limit.")

    md += ["", "Pipeline events included:"]
    for _, ev in pipeline[pipeline["delta_eur_mn"].ne(0)].iterrows():
        if ev["line_id"] == "A01":  # cash legs are implied by the business event
            continue
        md.append(f"- {ev['date']:%d %b} - {ev['business']}: {ev['description']} "
                  f"({_eur(ev['delta_eur_mn'])})")

    md += [
        "",
        "_Synthetic data. Simplified Basel III factors - illustrative only._",
    ]
    return "\n".join(md)
