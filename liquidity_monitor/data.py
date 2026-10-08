"""Synthetic balance-sheet generator for a single EU legal entity.

Produces a daily position file (one row per balance-sheet line per business
day) and a pipeline of known future events used by the forecast.

All figures are EUR millions and entirely made up. The structure mirrors what
a Treasury analyst would pull from a finance/risk data warehouse: business
line, product, counterparty type (third party vs affiliate), side of the
balance sheet and the regulatory buckets each line maps to.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ENTITY = "EU_BANK_AG"  # fictional legal entity


@dataclass(frozen=True)
class Line:
    line_id: str
    business: str
    product: str
    counterparty: str  # "third_party" | "affiliate"
    side: str  # "asset" | "liability" | "off_balance"
    lcr_category: str | None
    nsfr_category: str | None
    base: float  # starting balance, EUR mn
    daily_vol: float  # daily noise as a share of balance


LINES: list[Line] = [
    # ---- Assets -----------------------------------------------------------
    Line("A01", "Treasury", "Cash at central bank", "third_party", "asset",
         "cash_central_bank", "cash_central_bank", 4000, 0.020),
    Line("A02", "Treasury", "Government bonds (L1)", "third_party", "asset",
         "govt_bonds_l1", "hqla_l1_securities", 4000, 0.004),
    Line("A03", "Treasury", "Covered bonds (L2A)", "third_party", "asset",
         "covered_bonds_l2a", "hqla_l2a", 2000, 0.004),
    Line("A04", "Markets", "Corporate bonds (L2B)", "third_party", "asset",
         "corporate_bonds_l2b", "hqla_l2b", 900, 0.010),
    Line("A05", "Lending", "Corporate loans maturing <30d", "third_party", "asset",
         "loan_maturing_corporate", "corporate_loan_lt_1y", 3000, 0.008),
    Line("A06", "Markets", "FI loans maturing <30d", "third_party", "asset",
         "loan_maturing_fi", "fi_lending_lt_6m", 1200, 0.015),
    Line("A07", "Markets", "Reverse repo (L1 collateral)", "third_party", "asset",
         "reverse_repo_l1_collateral", "fi_lending_lt_6m", 4000, 0.015),
    Line("A08", "Markets", "Reverse repo (non-HQLA collateral)", "affiliate", "asset",
         "reverse_repo_non_hqla_collateral", "fi_lending_lt_6m", 1500, 0.015),
    Line("A09", "Lending", "Mortgages >1y", "third_party", "asset",
         None, "mortgage_gt_1y", 7000, 0.001),
    Line("A10", "Lending", "Corporate term loans >1y", "third_party", "asset",
         None, "other_loan_gt_1y", 12000, 0.002),
    Line("A11", "Treasury", "Other assets", "third_party", "asset",
         None, "other_assets", 2500, 0.002),
    # ---- Liabilities ------------------------------------------------------
    Line("L01", "Deposits", "Retail deposits - stable", "third_party", "liability",
         "retail_deposit_stable", "retail_deposit_stable", 8000, 0.002),
    Line("L02", "Deposits", "Retail deposits - less stable", "third_party", "liability",
         "retail_deposit_less_stable", "retail_deposit_less_stable", 4000, 0.004),
    Line("L03", "Payments", "Corporate operational deposits", "third_party", "liability",
         "corporate_deposit_operational", "corporate_deposit_lt_1y", 9000, 0.010),
    Line("L04", "Deposits", "Corporate non-operational deposits", "third_party", "liability",
         "corporate_deposit_non_operational", "corporate_deposit_lt_1y", 6000, 0.012),
    Line("L05", "Markets", "FI unsecured funding", "third_party", "liability",
         "fi_unsecured_funding", "fi_funding_lt_6m", 2500, 0.015),
    Line("L06", "Markets", "Intragroup unsecured funding", "affiliate", "liability",
         "fi_unsecured_funding", "fi_funding_lt_6m", 1500, 0.010),
    Line("L07", "Markets", "Repo (L1 collateral)", "third_party", "liability",
         "repo_l1_collateral", "fi_funding_lt_6m", 3500, 0.015),
    Line("L08", "Markets", "Repo (non-HQLA collateral)", "affiliate", "liability",
         "repo_non_hqla_collateral", "fi_funding_lt_6m", 1200, 0.015),
    Line("L09", "Treasury", "Long-term funding >1y", "third_party", "liability",
         None, "long_term_funding_gt_1y", 5000, 0.000),
    Line("L10", "Treasury", "Capital", "third_party", "liability",
         None, "capital", 5500, 0.000),
    # ---- Off-balance sheet -------------------------------------------------
    Line("O01", "Lending", "Undrawn committed facilities - corporate", "third_party",
         "off_balance", "committed_facility_corporate", "off_balance_commitments",
         10000, 0.004),
    Line("O02", "Markets", "Undrawn liquidity facilities - FI", "third_party",
         "off_balance", "committed_facility_fi", "off_balance_commitments",
         1500, 0.010),
]

LINE_INDEX = {line.line_id: line for line in LINES}

# Historical business events injected into the series:
# (business-day index, {line_id: delta EUR mn}, description)
HISTORICAL_EVENTS = [
    (60, {"L04": -1500, "A01": -1500},
     "Large corporate client withdraws non-operational deposits"),
    (95, {"L08": 900, "A08": 900},
     "Markets grows affiliate-facing repo book (non-HQLA collateral)"),
    (110, {"L05": -800, "A01": -800},
     "FI unsecured funding not rolled at maturity"),
]


def generate_positions(
    end_date: str = "2026-09-30", n_days: int = 130, seed: int = 7
) -> pd.DataFrame:
    """Return a long-format daily position table."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=end_date, periods=n_days)

    balances = {line.line_id: np.empty(n_days) for line in LINES}
    current = {line.line_id: line.base for line in LINES}
    anchor = dict(current)  # level each line mean-reverts towards
    events = {day: deltas for day, deltas, _ in HISTORICAL_EVENTS}

    for t in range(n_days):
        for line in LINES:
            if t > 0 and line.daily_vol > 0:
                shock = rng.normal(0, line.daily_vol) * line.base
                # mild mean reversion keeps the series stationary
                pull = 0.05 * (anchor[line.line_id] - current[line.line_id])
                current[line.line_id] += shock + pull
        for line_id, delta in events.get(t, {}).items():
            current[line_id] += delta
            anchor[line_id] += delta  # event is permanent, not reverted
        for line in LINES:
            balances[line.line_id][t] = max(current[line.line_id], 0.0)

    frames = []
    for line in LINES:
        frames.append(pd.DataFrame({
            "date": dates,
            "entity": ENTITY,
            "line_id": line.line_id,
            "business": line.business,
            "product": line.product,
            "counterparty": line.counterparty,
            "side": line.side,
            "lcr_category": line.lcr_category,
            "nsfr_category": line.nsfr_category,
            "balance_eur_mn": balances[line.line_id].round(1),
        }))
    return pd.concat(frames, ignore_index=True).sort_values(["date", "line_id"])


def generate_pipeline(last_date: pd.Timestamp) -> pd.DataFrame:
    """Known upcoming business events, as a Front Office / IB pipeline feed."""
    d = pd.bdate_range(start=last_date + pd.offsets.BDay(1), periods=15)
    rows = [
        (d[2], "A10", 600, "Lending", "Drawdown of new syndicated term loan"),
        (d[2], "A01", -600, "Lending", "Cash leg of syndicated loan drawdown"),
        (d[4], "L03", -900, "Payments", "Quarter-end corporate payment outflows"),
        (d[4], "A01", -900, "Payments", "Cash leg of corporate payment outflows"),
        (d[6], "L09", 1000, "Treasury", "New 3y senior unsecured issuance settles"),
        (d[6], "A01", 1000, "Treasury", "Cash leg of 3y issuance"),
        (d[9], "L08", 700, "Markets", "Affiliate repo book increase (non-HQLA)"),
        (d[9], "A08", 700, "Markets", "Matching affiliate reverse repo"),
    ]
    return pd.DataFrame(
        rows, columns=["date", "line_id", "delta_eur_mn", "business", "description"]
    )
