"""Short-horizon LCR forecast.

Method (intentionally simple and explainable):

1. Carry every balance forward from the latest actual (no BAU drift - the
   synthetic history is mean-reverting, so a fitted trend would be noise).
2. Overlay the known business pipeline (loan drawdowns, issuance, payment
   flows) on the dates it settles.
3. Recompute HQLA, outflows, inflows and the LCR for each forecast day.
4. Put an uncertainty band around the surplus from the historical
   volatility of daily surplus moves, scaled by sqrt(horizon).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, lcr


def project_positions(
    positions: pd.DataFrame, pipeline: pd.DataFrame, horizon: int = 10
) -> pd.DataFrame:
    last_date = positions["date"].max()
    latest = positions[positions["date"] == last_date]
    future_dates = pd.bdate_range(start=last_date + pd.offsets.BDay(1), periods=horizon)

    frames = []
    cumulative = pd.Series(0.0, index=latest["line_id"].values)
    for d in future_dates:
        todays = pipeline[pipeline["date"] == d].groupby("line_id")["delta_eur_mn"].sum()
        cumulative = cumulative.add(todays, fill_value=0.0)
        day = latest.copy()
        day["date"] = d
        day["balance_eur_mn"] = (
            day["balance_eur_mn"].values + cumulative.reindex(day["line_id"]).fillna(0).values
        ).clip(min=0)
        frames.append(day)
    return pd.concat(frames, ignore_index=True)


def forecast_lcr(
    positions: pd.DataFrame,
    pipeline: pd.DataFrame,
    horizon: int = 10,
    z: float = 1.65,
    vol_window: int = 60,
) -> pd.DataFrame:
    history = lcr.compute(positions)
    projected = lcr.compute(project_positions(positions, pipeline, horizon))

    daily_std = history["surplus"].diff().tail(vol_window).std()
    h = np.arange(1, len(projected) + 1)
    band = z * daily_std * np.sqrt(h)

    projected["surplus_low"] = projected["surplus"] - band
    projected["surplus_high"] = projected["surplus"] + band
    # translate the surplus band into an LCR band at constant net outflows
    projected["lcr_low"] = 1 + projected["surplus_low"] / projected["net_outflow"]
    projected["lcr_high"] = 1 + projected["surplus_high"] / projected["net_outflow"]
    projected["below_internal_limit"] = projected["lcr"] < config.LCR_INTERNAL_LIMIT
    projected["low_case_below_limit"] = projected["lcr_low"] < config.LCR_INTERNAL_LIMIT
    return projected
