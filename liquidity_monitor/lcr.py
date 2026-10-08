"""Liquidity Coverage Ratio engine.

LCR = Stock of HQLA / Total net cash outflows over a 30-day stress period

The calculation is split in two steps so that results can be attributed:

1. ``enrich`` - row-level weighting. Each position gets its HQLA value,
   stressed outflow and stressed inflow. These are linear in the balance.
2. ``aggregate`` - per-date totals, then the non-linear rules
   (HQLA composition caps, 75% inflow cap) are applied.
"""

from __future__ import annotations

import pandas as pd

from . import config


def enrich(positions: pd.DataFrame) -> pd.DataFrame:
    """Add row-level LCR weightings to a position table."""
    df = positions.copy()
    cat = df["lcr_category"]

    hqla_level = cat.map(lambda c: config.HQLA.get(c, (None, None))[0])
    haircut = cat.map(lambda c: config.HQLA.get(c, (None, 0.0))[1])
    out_rate = cat.map(config.OUTFLOW_RATES).fillna(0.0)
    in_rate = cat.map(config.INFLOW_RATES).fillna(0.0)

    bal = df["balance_eur_mn"]
    df["hqla_level"] = hqla_level
    df["hqla_value"] = (bal * (1 - haircut.fillna(0.0))).where(hqla_level.notna(), 0.0)
    df["outflow"] = bal * out_rate
    df["inflow"] = bal * in_rate
    return df


def apply_hqla_caps(l1: float, l2a: float, l2b: float) -> dict:
    """Basel III HQLA composition caps (simplified, no unwind adjustment).

    Level 2B may be at most 15% of HQLA and Level 2 (2A + 2B) at most 40%.
    """
    adj_l2b = max(l2b - 15 / 85 * (l1 + l2a), l2b - 15 / 60 * l1, 0.0)
    adj_l2 = max(l2a + l2b - adj_l2b - 2 / 3 * l1, 0.0)
    total = l1 + l2a + l2b - adj_l2b - adj_l2
    return {"hqla_cap_adjustment": -(adj_l2b + adj_l2), "hqla": total}


def aggregate(enriched: pd.DataFrame) -> pd.DataFrame:
    """Daily LCR from an enriched position table."""
    by_level = (
        enriched.pivot_table(index="date", columns="hqla_level",
                             values="hqla_value", aggfunc="sum")
        .reindex(columns=["L1", "L2A", "L2B"])
        .fillna(0.0)
    )
    flows = enriched.groupby("date")[["outflow", "inflow"]].sum()

    out = by_level.join(flows)
    caps = out.apply(lambda r: apply_hqla_caps(r["L1"], r["L2A"], r["L2B"]),
                     axis=1, result_type="expand")
    out = out.join(caps)

    out["inflow_capped"] = out[["inflow"]].join(
        (out["outflow"] * config.INFLOW_CAP).rename("cap")
    ).min(axis=1)
    out["net_outflow"] = out["outflow"] - out["inflow_capped"]
    out["lcr"] = out["hqla"] / out["net_outflow"]
    out["surplus"] = out["hqla"] - out["net_outflow"]  # EUR mn above 100%
    out["surplus_vs_internal_limit"] = (
        out["hqla"] - config.LCR_INTERNAL_LIMIT * out["net_outflow"]
    )
    return out


def compute(positions: pd.DataFrame) -> pd.DataFrame:
    return aggregate(enrich(positions))
