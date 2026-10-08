import pandas as pd
import pytest

from liquidity_monitor import attribution, data, forecast, lcr, nsfr

D1, D2 = pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")


def _pos(rows, date=D1):
    """rows: (line_id, business, side, lcr_category, nsfr_category, balance)"""
    return pd.DataFrame([
        dict(date=date, entity="T", line_id=i, business=b, product=i,
             counterparty="third_party", side=s, lcr_category=lc,
             nsfr_category=nc, balance_eur_mn=bal)
        for i, b, s, lc, nc, bal in rows
    ])


def test_lcr_hand_calculation():
    pos = _pos([
        ("a", "T", "asset", "cash_central_bank", "cash_central_bank", 1000),
        ("b", "T", "asset", "covered_bonds_l2a", "hqla_l2a", 200),   # 170 after haircut
        ("c", "D", "liability", "corporate_deposit_non_operational",
         "corporate_deposit_lt_1y", 2000),                            # 800 outflow
        ("d", "L", "asset", "loan_maturing_corporate", "corporate_loan_lt_1y", 400),  # 200 inflow
    ])
    r = lcr.compute(pos).iloc[0]
    assert r["hqla"] == pytest.approx(1170)
    assert r["net_outflow"] == pytest.approx(600)
    assert r["lcr"] == pytest.approx(1170 / 600)


def test_inflow_cap_at_75_percent():
    pos = _pos([
        ("a", "T", "asset", "cash_central_bank", "cash_central_bank", 100),
        ("c", "M", "liability", "fi_unsecured_funding", "fi_funding_lt_6m", 400),
        ("d", "M", "asset", "loan_maturing_fi", "fi_lending_lt_6m", 1000),
    ])
    r = lcr.compute(pos).iloc[0]
    assert r["inflow_capped"] == pytest.approx(300)  # 75% of 400
    assert r["net_outflow"] == pytest.approx(100)


def test_level2b_cap():
    caps = lcr.apply_hqla_caps(l1=100, l2a=0, l2b=100)
    # L2B can be at most 15% of the total -> 100 / 0.85 = 117.6
    assert caps["hqla"] == pytest.approx(100 / 0.85)


def test_level2_total_cap():
    caps = lcr.apply_hqla_caps(l1=60, l2a=100, l2b=0)
    # L2 at most 40% of total -> L1 / 0.6 = 100
    assert caps["hqla"] == pytest.approx(100)


def test_nsfr_hand_calculation():
    pos = _pos([
        ("k", "T", "liability", None, "capital", 100),
        ("r", "D", "liability", None, "retail_deposit_stable", 200),   # 190
        ("m", "L", "asset", None, "mortgage_gt_1y", 300),              # 195
    ])
    r = nsfr.compute(pos).iloc[0]
    assert r["asf"] == pytest.approx(290)
    assert r["rsf"] == pytest.approx(195)


def test_attribution_reconciles_to_reported_surplus():
    positions = data.generate_positions(n_days=40)
    dates = sorted(positions["date"].unique())
    for start, end in [(dates[-2], dates[-1]), (dates[0], dates[-1])]:
        drv = attribution.explain_move(positions, start, end, by=["business", "counterparty"])
        assert drv["delta"].sum() == pytest.approx(drv.attrs["reported_change"])


def test_attribution_captures_inflow_cap_effect():
    rows = [
        ("a", "T", "asset", "cash_central_bank", "cash_central_bank", 100),
        ("c", "M", "liability", "fi_unsecured_funding", "fi_funding_lt_6m", 400),
        ("d", "M", "asset", "loan_maturing_fi", "fi_lending_lt_6m", 200),
    ]
    day2 = [r if r[0] != "d" else (*r[:5], 1000) for r in rows]  # inflows jump past the cap
    positions = pd.concat([_pos(rows, D1), _pos(day2, D2)])
    drv = attribution.explain_move(positions, D1, D2)
    cap = drv.loc[drv["business"] == attribution.CAP_EFFECT, "delta"].iloc[0]
    assert cap == pytest.approx(-(800 - 100))  # 800 raw inflow gain, only 100 usable


def test_forecast_applies_pipeline():
    positions = data.generate_positions(n_days=30)
    last = positions["date"].max()
    pipe = pd.DataFrame({
        "date": [last + pd.offsets.BDay(2)], "line_id": ["A01"],
        "delta_eur_mn": [-500.0], "business": ["Treasury"], "description": ["test"],
    })
    proj = forecast.project_positions(positions, pipe, horizon=3)
    cash = proj[proj["line_id"] == "A01"].set_index("date")["balance_eur_mn"]
    base = positions[(positions["date"] == last) & (positions["line_id"] == "A01")][
        "balance_eur_mn"].iloc[0]
    assert cash.iloc[0] == pytest.approx(base)
    assert cash.iloc[1] == pytest.approx(base - 500)
    assert cash.iloc[2] == pytest.approx(base - 500)  # event persists
