"""Driver attribution: why did the LCR surplus move?

The daily surplus number alone says *that* liquidity changed. Attribution
says *why*: which business, product and counterparty type drove it.

Each position contributes linearly to the uncapped surplus:

    contribution = HQLA value - stressed outflow + stressed inflow

Summing the change in contribution by any dimension explains the move in
the uncapped surplus. The difference to the reported (capped) surplus is
shown on its own line as the cap effect (75% inflow cap, HQLA caps), so the
attribution always reconciles to the reported number.
"""

from __future__ import annotations

import pandas as pd

from . import lcr

CAP_EFFECT = "Cap effects (inflow / HQLA)"


def contributions(positions: pd.DataFrame) -> pd.DataFrame:
    df = lcr.enrich(positions)
    df["contribution"] = df["hqla_value"] - df["outflow"] + df["inflow"]
    return df


def explain_move(
    positions: pd.DataFrame,
    date_from: pd.Timestamp,
    date_to: pd.Timestamp,
    by: str | list[str] = "business",
) -> pd.DataFrame:
    """Attribute the change in LCR surplus between two dates.

    Returns one row per driver plus a cap-effect row, sorted by absolute
    impact. ``delta`` sums exactly to the reported change in surplus.
    """
    by = [by] if isinstance(by, str) else list(by)
    df = contributions(positions[positions["date"].isin([date_from, date_to])])

    pivot = df.pivot_table(index=by, columns="date", values="contribution",
                           aggfunc="sum").fillna(0.0)
    drivers = (pivot[date_to] - pivot[date_from]).rename("delta").reset_index()

    daily = lcr.compute(positions[positions["date"].isin([date_from, date_to])])
    reported = daily.loc[date_to, "surplus"] - daily.loc[date_from, "surplus"]
    cap_effect = reported - drivers["delta"].sum()

    cap_row = {col: CAP_EFFECT if i == 0 else "" for i, col in enumerate(by)}
    cap_row["delta"] = cap_effect
    drivers = pd.concat([drivers, pd.DataFrame([cap_row])], ignore_index=True)

    drivers = drivers.reindex(
        drivers["delta"].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)
    drivers.attrs["reported_change"] = reported
    return drivers


def volatility_by_business(positions: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Standard deviation of daily surplus contribution per business line.

    Answers "which business makes our liquidity usage volatile?" over the
    most recent ``window`` business days.
    """
    df = contributions(positions)
    daily = df.groupby(["date", "business"])["contribution"].sum().unstack()
    recent = daily.diff().tail(window)
    return (
        recent.std()
        .rename("daily_std_eur_mn")
        .sort_values(ascending=False)
        .to_frame()
    )
