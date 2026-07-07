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
    synthesize_q4,
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


def _dur(value, start, end, fy, fp, ref="acc", unit="USD", scale=0, concept=REVENUE[1]):
    return FinFact(
        entity_id="ticker:TEST US", concept=concept, value=value, unit=unit, scale=scale,
        period=Period(end=end, start=start, fiscal_year=fy, fiscal_period=fp),
        source=Source(kind="sec-companyfacts", ref=ref, fetched="2026-07-06"),
    )


def _fs_of(*facts):
    fs = FactSet(entity=Entity(ticker="TEST US"))
    for f in facts:
        fs.add(f)
    return fs


# 14 — CLOW US regression: Q3-2016 + two restated Q1-2017 rows (starts one day
# apart, same fy/fp) + Q2-2017 must NOT mint a TTM that double-counts Q1
def test_ttm_clow_restated_q1_not_double_counted():
    fs = _fs_of(
        _dur(100, "2016-07-01", "2016-09-30", 2016, "Q3", ref="acc-1"),
        _dur(200, "2017-01-01", "2017-03-31", 2017, "Q1", ref="acc-2"),
        _dur(210, "2017-01-02", "2017-03-31", 2017, "Q1", ref="acc-3"),  # restated
        _dur(300, "2017-04-01", "2017-06-30", 2017, "Q2", ref="acc-4"),
    )
    assert ttm(fs, REVENUE, "x") is None  # dedupes to 3 quarters, Q4-2016 missing


# 15 — restatement happy path: the refiled row (same fy/fp, start +1 day)
# replaces the original; TTM sums the restated value and links its CID
def test_ttm_restatement_latest_accession_wins():
    restated = _dur(220, "2024-04-02", "2024-06-30", 2024, "Q2", ref="acc-3")
    fs = _fs_of(
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1", ref="acc-1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2", ref="acc-2"),
        restated,
        _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3", ref="acc-4"),
        _dur(400, "2024-10-01", "2024-12-31", 2024, "Q4", ref="acc-5"),
    )
    f = ttm(fs, REVENUE, "x")
    assert f.value == 100 + 220 + 300 + 400
    assert restated.cid in f.derived_from and len(f.derived_from) == 4


# 16 — adjacency: four quarters whose total span passes the gate but with a
# hole between Q2 and Q3 are rejected, not summed
def test_ttm_adjacency_hole_rejected():
    fs = _fs_of(
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2"),
        _dur(300, "2024-08-01", "2024-10-31", 2024, "Q3"),  # 32-day hole
        _dur(400, "2024-11-01", "2024-12-31", 2024, "Q4"),
    )
    assert ttm(fs, REVENUE, "x") is None


# 17 — Q4 synthesis: FY - Q1 - Q2 - Q3, exact across mixed scales
def test_synthesize_q4_exact_mixed_scales():
    fy = _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY", ref="acc-9")
    q1 = _dur(200000, "2024-01-01", "2024-03-31", 2024, "Q1", scale=3)  # 200 USD
    q2 = _dur(250, "2024-04-01", "2024-06-30", 2024, "Q2")
    q3 = _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3")
    out = synthesize_q4(_fs_of(fy, q1, q2, q3), REVENUE)
    assert len(out) == 1
    f = out[0]
    assert f.value == 250000 and f.scale == 3  # 1000 - 200 - 250 - 300 = 250 USD
    assert f.decimal == Decimal("250")
    assert f.concept == REVENUE[1] and f.unit == "USD"
    assert f.period.start == "2024-10-01" and f.period.end == "2024-12-31"
    assert f.period.fiscal_year == 2024 and f.period.fiscal_period == "Q4"
    assert f.source.kind == "finfield-derived"
    assert f.source.ref == "finfacts.derive.synthesize_q4"
    assert f.derived_from == (fy.cid, q1.cid, q2.cid, q3.cid)


# 18 — never synthesize when a real Q4 already exists for that fiscal year
def test_synthesize_q4_real_q4_wins():
    out = synthesize_q4(_fs_of(
        _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY"),
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2"),
        _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3"),
        _dur(400, "2024-10-01", "2024-12-31", 2024, "Q4"),
    ), REVENUE)
    assert out == []


# 19 — no synthesis when any of Q1-Q3 is missing
def test_synthesize_q4_missing_quarter():
    out = synthesize_q4(_fs_of(
        _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY"),
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3"),
    ), REVENUE)
    assert out == []


# 20 — unit mismatch across the four inputs skips synthesis
def test_synthesize_q4_unit_mismatch():
    out = synthesize_q4(_fs_of(
        _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY"),
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2", unit="EUR"),
        _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3"),
    ), REVENUE)
    assert out == []


# 21 — a negative synthesized Q4 (loss quarter) is real and kept
def test_synthesize_q4_negative_allowed():
    out = synthesize_q4(_fs_of(
        _dur(500, "2024-01-01", "2024-12-31", 2024, "FY"),
        _dur(200, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2"),
        _dur(200, "2024-07-01", "2024-09-30", 2024, "Q3"),
    ), REVENUE)
    assert len(out) == 1 and out[0].value == -100


# 22 — TTM over Q1-Q3 + synthesized Q4 equals the FY total exactly,
# with the synthesized fact's CID in the provenance chain
def test_ttm_with_synthesized_q4_equals_fy():
    fy = _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY")
    q1 = _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1")
    q2 = _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2")
    q3 = _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3")
    fs = _fs_of(fy, q1, q2, q3)
    synth = synthesize_q4(fs, REVENUE)[0]
    f = ttm(fs, REVENUE, "finfield:revenue_ttm")
    assert f.value == 1000 and f.decimal == fy.decimal
    assert f.period.start == "2024-01-01" and f.period.end == "2024-12-31"
    assert f.derived_from == (q1.cid, q2.cid, q3.cid, synth.cid)
    assert synth.derived_from == (fy.cid, q1.cid, q2.cid, q3.cid)


# 23 — yoy_growth sees synthesized quarters uniformly with real ones
def test_yoy_with_synthesized_q4():
    fs = _fs_of(
        _dur(100, "2023-10-01", "2023-12-31", 2023, "Q4"),  # real prior-year Q4
        _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
        _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2"),
        _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3"),
        _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY"),  # synth Q4 = 400
    )
    f = yoy_growth(fs, REVENUE, "x")
    assert f.decimal == Decimal("3")  # Q4: 400 vs 100


# 24 — synthesis is deterministic: independent runs mint identical CIDs
def test_synthesize_q4_determinism():
    def build():
        return _fs_of(
            _dur(1000, "2024-01-01", "2024-12-31", 2024, "FY"),
            _dur(100, "2024-01-01", "2024-03-31", 2024, "Q1"),
            _dur(200, "2024-04-01", "2024-06-30", 2024, "Q2"),
            _dur(300, "2024-07-01", "2024-09-30", 2024, "Q3"),
        )
    a = [f.cid for f in synthesize_q4(build(), REVENUE)]
    b = [f.cid for f in synthesize_q4(build(), REVENUE)]
    assert a == b and len(a) == 1
    assert ttm(build(), REVENUE, "x").cid == ttm(build(), REVENUE, "x").cid
