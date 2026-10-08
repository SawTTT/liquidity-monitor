"""Regulatory parameters for the simplified LCR / NSFR engine.

Factors follow the Basel III framework (BCBS 238 for LCR, BCBS 295 for NSFR)
and the EU Delegated Regulation 2015/61 in spirit, but are deliberately
simplified for a portfolio project. They are illustrative, not a substitute
for a production regulatory rulebook.

Every balance-sheet line in the dataset carries an ``lcr_category`` and an
``nsfr_category``. The tables below map those categories to factors.
"""

# --------------------------------------------------------------------------
# LCR - High Quality Liquid Assets (stock side)
# --------------------------------------------------------------------------
# category -> (HQLA level, haircut)
HQLA = {
    "cash_central_bank": ("L1", 0.00),
    "govt_bonds_l1": ("L1", 0.00),
    "covered_bonds_l2a": ("L2A", 0.15),
    "corporate_bonds_l2b": ("L2B", 0.50),
}

# Composition caps (as a share of total post-haircut HQLA)
CAP_L2_TOTAL = 0.40
CAP_L2B = 0.15

# --------------------------------------------------------------------------
# LCR - 30-day stressed outflows (liability side)
# --------------------------------------------------------------------------
OUTFLOW_RATES = {
    "retail_deposit_stable": 0.05,
    "retail_deposit_less_stable": 0.10,
    "corporate_deposit_operational": 0.25,
    "corporate_deposit_non_operational": 0.40,
    "fi_unsecured_funding": 1.00,
    "repo_l1_collateral": 0.00,
    "repo_l2a_collateral": 0.15,
    "repo_non_hqla_collateral": 1.00,
    "committed_facility_corporate": 0.10,  # undrawn, off-balance sheet
    "committed_facility_fi": 0.40,  # undrawn, off-balance sheet
}

# --------------------------------------------------------------------------
# LCR - 30-day stressed inflows (asset side, contractual maturity < 30d)
# --------------------------------------------------------------------------
INFLOW_RATES = {
    "loan_maturing_corporate": 0.50,
    "loan_maturing_fi": 1.00,
    "reverse_repo_l1_collateral": 0.00,
    "reverse_repo_non_hqla_collateral": 1.00,
}

# Inflows can offset at most 75% of outflows
INFLOW_CAP = 0.75

# --------------------------------------------------------------------------
# NSFR - Available Stable Funding / Required Stable Funding
# --------------------------------------------------------------------------
ASF_FACTORS = {
    "capital": 1.00,
    "long_term_funding_gt_1y": 1.00,
    "retail_deposit_stable": 0.95,
    "retail_deposit_less_stable": 0.90,
    "corporate_deposit_lt_1y": 0.50,
    "fi_funding_lt_6m": 0.00,
    "other_liabilities": 0.00,
}

RSF_FACTORS = {
    "cash_central_bank": 0.00,
    "hqla_l1_securities": 0.05,
    "hqla_l2a": 0.15,
    "hqla_l2b": 0.50,
    "fi_lending_lt_6m": 0.15,
    "corporate_loan_lt_1y": 0.50,
    "mortgage_gt_1y": 0.65,
    "other_loan_gt_1y": 0.85,
    "other_assets": 1.00,
    "off_balance_commitments": 0.05,
}

# --------------------------------------------------------------------------
# Internal risk appetite
# --------------------------------------------------------------------------
REG_MINIMUM = 1.00  # 100% regulatory floor for both ratios
LCR_INTERNAL_LIMIT = 1.10  # management buffer: early warning at 110%
NSFR_INTERNAL_LIMIT = 1.05
