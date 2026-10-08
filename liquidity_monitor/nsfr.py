"""Net Stable Funding Ratio engine.

NSFR = Available Stable Funding (ASF) / Required Stable Funding (RSF)

Liabilities and capital provide ASF; assets and off-balance-sheet
commitments consume RSF.
"""

from __future__ import annotations

import pandas as pd

from . import config


def enrich(positions: pd.DataFrame) -> pd.DataFrame:
    df = positions.copy()
    cat = df["nsfr_category"]
    bal = df["balance_eur_mn"]
    is_liab = df["side"].eq("liability")

    df["asf"] = (bal * cat.map(config.ASF_FACTORS).fillna(0.0)).where(is_liab, 0.0)
    df["rsf"] = (bal * cat.map(config.RSF_FACTORS).fillna(0.0)).where(~is_liab, 0.0)
    return df


def compute(positions: pd.DataFrame) -> pd.DataFrame:
    totals = enrich(positions).groupby("date")[["asf", "rsf"]].sum()
    totals["nsfr"] = totals["asf"] / totals["rsf"]
    totals["surplus"] = totals["asf"] - totals["rsf"]
    return totals
