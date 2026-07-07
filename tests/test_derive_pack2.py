"""Derived pack 2: momentum, investment, profitability, IFRS aliases (issue #1)."""
from datetime import date, timedelta
from decimal import Decimal

from finfacts.model import Entity, FactSet, FinFact, Period, Source
from finfacts.derive import (
    BOOK_EQUITY,
    NET_INCOME,
    OPERATING_INCOME,
    TOTAL_ASSETS,
    derive_all,
    instant_ratio,
    instant_yoy,
    momentum_12_1,
    ttm,
)

SRC = Source(kind="stooq-eod", ref="test", fetched="2026-07-06")
E = Entity(ticker="TEST US")


def _close(day: str, value: int, scale: int = 2, unit: str = "USD") -> FinFact:
    return FinFact(entity_id=E.entity_id, concept="finfield:close", value=value,
                   scale=scale, unit=unit, period=Period(end=day), source=SRC)


def _instant(concept: str, day: str, value: int, unit: str = "USD") -> FinFact:
    return FinFact(entity_id=E.entity_id, concept=concept, value=value, unit=unit,
                   period=Period(end=day), source=SRC)


def _close_series(anchor: str, days: int = 400, step: int = 7, base: int = 10000):
    """Weekly closes: value rises 1 cent per day, so returns are predictable."""
    fs = FactSet(entity=E)
    end = date.fromisoformat(anchor)
    d = end - timedelta(days=days)
    while d <= end:
        offset = (d - (end - timedelta(days=days))).days
        fs.add(_close(d.isoformat(), base + offset))
        d += timedelta(days=step)
    return fs


def test_momentum_12_1_skips_last_month():
    fs = _close_series("2026-07-06")
    mom = momentum_12_1(fs)
    assert mom is not None and mom.unit == "pure" and mom.scale == 6
    # p1 ≈ anchor-30d, p0 ≈ anchor-365d; both inputs cited
    p1_end, p0_end = mom.period.end, mom.period.start
    assert abs((date.fromisoformat("2026-07-06") - date.fromisoformat(p1_end)).days - 30) <= 10
    assert abs((date.fromisoformat("2026-07-06") - date.fromisoformat(p0_end)).days - 365) <= 15
    assert len(mom.derived_from) == 2
    by_end = {f.period.end: f for f in fs.facts}
    expect = by_end[p1_end].decimal / by_end[p0_end].decimal - Decimal(1)
    assert mom.decimal == expect.quantize(Decimal("0.000001"))


def test_momentum_needs_a_year_of_closes():
    assert momentum_12_1(_close_series("2026-07-06", days=120)) is None


def test_momentum_crypto_unit():
    fs = _close_series("2026-07-06")
    # crypto closes are USD too (coingecko) — but a mixed-unit series must not blend
    fs.add(_close("2026-07-05", 999999, unit="EUR"))
    mom = momentum_12_1(fs)
    assert mom is not None  # EUR outlier excluded, USD series intact


def test_instant_yoy_asset_growth():
    fs = FactSet(entity=E)
    fs.add(_instant(TOTAL_ASSETS[0], "2024-12-31", 100_000))
    fs.add(_instant(TOTAL_ASSETS[0], "2025-12-31", 112_000))
    g = instant_yoy(fs, TOTAL_ASSETS, "finfield:asset_growth_yoy")
    assert g is not None and g.decimal == Decimal("0.12")
    assert g.period.start == "2024-12-31" and g.period.end == "2025-12-31"


def test_instant_yoy_rejects_nonpositive_base_and_unit_mix():
    fs = FactSet(entity=E)
    fs.add(_instant(TOTAL_ASSETS[0], "2024-12-31", 0))
    fs.add(_instant(TOTAL_ASSETS[0], "2025-12-31", 112_000))
    assert instant_yoy(fs, TOTAL_ASSETS, "x") is None
    fs2 = FactSet(entity=E)
    fs2.add(_instant(TOTAL_ASSETS[0], "2024-12-31", 100_000, unit="EUR"))
    fs2.add(_instant(TOTAL_ASSETS[0], "2025-12-31", 112_000))
    assert instant_yoy(fs2, TOTAL_ASSETS, "x") is None


QUARTERS = [
    ("2024-04-01", "2024-06-30", 2024, "Q2"),
    ("2024-07-01", "2024-09-30", 2024, "Q3"),
    ("2024-10-01", "2024-12-31", 2024, "Q4"),
    ("2025-01-01", "2025-03-31", 2025, "Q1"),
]


def _quarterly_fs(concept: str, vals, unit: str = "USD") -> FactSet:
    fs = FactSet(entity=E)
    for (start, end, fy, fp), v in zip(QUARTERS, vals):
        fs.add(FinFact(entity_id=E.entity_id, concept=concept, value=v, unit=unit,
                       period=Period(end=end, start=start, fiscal_year=fy, fiscal_period=fp),
                       source=SRC))
    return fs


def test_operating_profitability_eur_pair():
    fs = _quarterly_fs(OPERATING_INCOME[1], [25, 25, 25, 25], unit="EUR")  # IFRS alias
    fs.add(_instant(BOOK_EQUITY[2], "2025-03-31", 1000, unit="EUR"))       # ifrs-full:Equity
    op = ttm(fs, OPERATING_INCOME, "finfield:operating_income_ttm")
    book = [f for f in fs.facts if f.concept == BOOK_EQUITY[2]][0]
    r = instant_ratio(op, book, "finfield:operating_profitability")
    assert r is not None and r.decimal == Decimal("0.1")
    # mixed currency refuses
    assert instant_ratio(op, _instant(BOOK_EQUITY[0], "2025-03-31", 1000), "x") is None


def test_ifrs_net_income_alias_derives_ttm():
    fs = _quarterly_fs(NET_INCOME[1], [10, 20, 30, 40], unit="EUR")  # ifrs-full:ProfitLoss
    f = ttm(fs, NET_INCOME, "finfield:net_income_ttm")
    assert f is not None and f.value == 100 and f.unit == "EUR"


def test_derive_all_includes_new_factors():
    fs = _close_series("2026-07-06")
    fs.add(_instant(TOTAL_ASSETS[0], "2024-12-31", 100_000))
    fs.add(_instant(TOTAL_ASSETS[0], "2025-12-31", 112_000))
    concepts = {f.concept for f in derive_all(fs)}
    assert "finfield:momentum_12_1" in concepts
    assert "finfield:asset_growth_yoy" in concepts
