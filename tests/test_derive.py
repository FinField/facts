"""Smart-layer property tests on a synthetic factset."""
from decimal import Decimal

from finfacts.model import Entity, FactSet, FinFact, Period, Source
from finfacts.derive import NET_INCOME, REVENUE, derive_all, ttm, yoy_growth

SRC = Source(kind="sec-companyfacts", ref="acc", fetched="2026-07-06")

QUARTERS = [
    ("2024-01-01", "2024-03-31", 2024, "Q1"),
    ("2024-04-01", "2024-06-30", 2024, "Q2"),
    ("2024-07-01", "2024-09-30", 2024, "Q3"),
    ("2024-10-01", "2024-12-31", 2024, "Q4"),
    ("2025-01-01", "2025-03-31", 2025, "Q1"),
]


def _fs(revenues, incomes=None):
    fs = FactSet(entity=Entity(ticker="TEST US"))
    for (start, end, fy, fp), val in zip(QUARTERS, revenues):
        fs.add(
            FinFact(
                entity_id="ticker:TEST US", concept=REVENUE[1], value=val, unit="USD",
                period=Period(end=end, start=start, fiscal_year=fy, fiscal_period=fp), source=SRC,
            )
        )
    for (start, end, fy, fp), val in zip(QUARTERS, incomes or []):
        fs.add(
            FinFact(
                entity_id="ticker:TEST US", concept=NET_INCOME[0], value=val, unit="USD",
                period=Period(end=end, start=start, fiscal_year=fy, fiscal_period=fp), source=SRC,
            )
        )
    return fs


# 1 — TTM sums the last four quarters
def test_ttm_sum():
    f = ttm(_fs([100, 200, 300, 400, 500]), REVENUE, "finfield:revenue_ttm")
    assert f.value == 200 + 300 + 400 + 500
    assert f.period.start == "2024-04-01" and f.period.end == "2025-03-31"


# 2 — TTM needs four quarters
def test_ttm_insufficient():
    assert ttm(_fs([100, 200, 300]), REVENUE, "x") is None


# 3 — TTM provenance links all four inputs
def test_ttm_provenance():
    fs = _fs([100, 200, 300, 400, 500])
    f = ttm(fs, REVENUE, "x")
    cids = {x.cid for x in fs.facts}
    assert len(f.derived_from) == 4 and set(f.derived_from) <= cids


# 4 — YoY compares same fiscal quarter across years, exactly
def test_yoy():
    f = yoy_growth(_fs([100, 200, 300, 400, 150]), REVENUE, "x")
    assert f.decimal == Decimal("0.5")  # Q1: 150 vs 100
    assert f.unit == "pure" and len(f.derived_from) == 2


# 5 — full smart pack: margin = ni_ttm / rev_ttm
def test_derive_all_margin():
    out = {f.concept: f for f in derive_all(_fs([100, 200, 300, 400, 500], [10, 20, 30, 40, 50]))}
    rev, ni = out["finfield:revenue_ttm"], out["finfield:net_income_ttm"]
    margin = out["finfield:net_margin_ttm"]
    assert margin.decimal == ni.decimal / rev.decimal
    assert set(margin.derived_from) == {rev.cid, ni.cid}


# 6 — derived facts are integer-valued (knittable)
def test_derived_integer_only():
    for f in derive_all(_fs([100, 200, 300, 400, 500], [10, 20, 30, 40, 50])):
        assert isinstance(f.value, int) and isinstance(f.scale, int)
