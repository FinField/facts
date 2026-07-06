"""Smart-layer property tests on a synthetic factset."""
from decimal import Decimal

from finfacts.model import Entity, FactSet, FinFact, Period, Source
from finfacts.derive import (
    BOOK_EQUITY,
    CAPEX,
    NET_INCOME,
    OPEX,
    PUBLIC_FLOAT,
    REVENUE,
    _latest_instant,
    derive_all,
    instant_ratio,
    ttm,
    yoy_growth,
)

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


def _instant(concept, value, end, ref="acc", unit="USD"):
    return FinFact(
        entity_id="ticker:TEST US", concept=concept, value=value, unit=unit,
        period=Period(end=end), source=Source(kind="sec-companyfacts", ref=ref, fetched="2026-07-06"),
    )


def _full_fs(float_end="2025-04-15", float_val=700, float_unit="USD",
             book_end="2025-03-31", book_val=350):
    fs = _fs([100, 200, 300, 400, 500], [10, 20, 30, 40, 50])
    for concept, values in ((CAPEX[0], [5, 6, 7, 8, 9]), (OPEX[0], [50, 60, 70, 80, 90])):
        for (start, end, fy, fp), val in zip(QUARTERS, values):
            fs.add(
                FinFact(
                    entity_id="ticker:TEST US", concept=concept, value=val, unit="USD",
                    period=Period(end=end, start=start, fiscal_year=fy, fiscal_period=fp), source=SRC,
                )
            )
    fs.add(_instant(PUBLIC_FLOAT[0], float_val, float_end, unit=float_unit))
    fs.add(_instant(BOOK_EQUITY[0], book_val, book_end))
    return fs


# 7 — latest instant: restatement wins per period.end, then max end wins
def test_latest_instant_restatement():
    fs = FactSet(entity=Entity(ticker="TEST US"))
    fs.add(_instant(PUBLIC_FLOAT[0], 600, "2024-06-30", ref="acc-9"))
    fs.add(_instant(PUBLIC_FLOAT[0], 700, "2025-03-31", ref="acc-1"))
    fs.add(_instant(PUBLIC_FLOAT[0], 710, "2025-03-31", ref="acc-2"))  # restated
    f = _latest_instant(fs, PUBLIC_FLOAT)
    assert f.value == 710 and f.period.end == "2025-03-31"
    assert _latest_instant(fs, BOOK_EQUITY) is None


# 8 — capex/opex reuse the TTM machinery, guards included
def test_capex_opex_ttm():
    out = {f.concept: f for f in derive_all(_full_fs())}
    capex, opex = out["finfield:capex_ttm"], out["finfield:opex_ttm"]
    assert capex.value == 6 + 7 + 8 + 9 and opex.value == 60 + 70 + 80 + 90
    assert capex.period.start == "2024-04-01" and capex.period.end == "2025-03-31"
    assert len(capex.derived_from) == 4 and len(opex.derived_from) == 4


# 9 — F&F ratios on free-float mcap: exact values, provenance, later period.end
def test_derive_all_float_ratios():
    out = {f.concept: f for f in derive_all(_full_fs())}
    flt = _latest_instant(_full_fs(), PUBLIC_FLOAT)
    book = _latest_instant(_full_fs(), BOOK_EQUITY)
    b2m = out["finfield:book_to_float_mcap"]
    e2m = out["finfield:earnings_to_float_mcap"]
    c2m = out["finfield:capex_to_float_mcap"]
    assert b2m.decimal == Decimal("0.5")  # 350 / 700
    assert e2m.decimal == Decimal("0.2")  # ni_ttm 140 / 700
    assert c2m.value == 42857  # capex_ttm 30 / 700 = 0.042857142... at scale 6
    assert b2m.derived_from == (book.cid, flt.cid)
    assert e2m.derived_from == (out["finfield:net_income_ttm"].cid, flt.cid)
    assert c2m.derived_from == (out["finfield:capex_ttm"].cid, flt.cid)
    for f in (b2m, e2m, c2m):  # period = the LATER end (the float's), instant
        assert f.period.end == "2025-04-15" and f.period.start is None
        assert f.unit == "pure" and f.scale == 6


# 10 — staleness guard: 3-year-old equity vs fresh float yields no B/M
def test_ratio_staleness_guard():
    out = {f.concept: f for f in derive_all(_full_fs(book_end="2023-06-30"))}
    assert "finfield:book_to_float_mcap" not in out
    assert "finfield:earnings_to_float_mcap" in out  # ttm end is still fresh


# 11 — non-positive float is not a denominator
def test_ratio_nonpositive_float():
    for bad in (0, -700):
        out = {f.concept for f in derive_all(_full_fs(float_val=bad))}
        assert not any(c.endswith("_to_float_mcap") for c in out)


# 12 — unit mismatch: both sides must be USD
def test_ratio_unit_mismatch():
    out = {f.concept for f in derive_all(_full_fs(float_unit="EUR"))}
    assert not any(c.endswith("_to_float_mcap") for c in out)
    numer_mismatch = instant_ratio(
        _instant(BOOK_EQUITY[0], 350, "2025-03-31", unit="pure"),
        _instant(PUBLIC_FLOAT[0], 700, "2025-03-31"), "x",
    )
    assert numer_mismatch is None


# 13 — determinism: two independent runs mint byte-identical CIDs
def test_derive_determinism():
    a = sorted(f.cid for f in derive_all(_full_fs()))
    b = sorted(f.cid for f in derive_all(_full_fs()))
    assert a == b and len(a) == 10
