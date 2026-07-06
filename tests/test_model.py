"""Core model property tests."""
from decimal import Decimal

from finfacts.model import Entity, FactSet, FinFact, Period, Source, cid, from_scaled, to_scaled


def _fact(value=1000, scale=0, concept="us-gaap:Revenues", end="2025-12-31", ref="acc-1"):
    return FinFact(
        entity_id="ticker:TEST US",
        concept=concept,
        value=value,
        scale=scale,
        unit="USD",
        period=Period(end=end, start="2025-10-01", fiscal_year=2025, fiscal_period="Q4"),
        source=Source(kind="sec-companyfacts", ref=ref, fetched="2026-07-06"),
    )


# 1 — CID is deterministic: same fact, same hash
def test_cid_deterministic():
    assert _fact().cid == _fact().cid
    assert _fact().cid.startswith("ff1:")


# 2 — any field change changes the CID
def test_cid_sensitive():
    base = _fact().cid
    assert _fact(value=1001).cid != base
    assert _fact(scale=2).cid != base
    assert _fact(end="2026-01-01").cid != base
    assert _fact(ref="acc-2").cid != base


# 3 — canonical JSON is key-order independent
def test_canonical_order_independent():
    assert cid({"a": 1, "b": 2}) == cid({"b": 2, "a": 1})


# 4 — scaled conversion roundtrips exact decimals
def test_to_scaled_roundtrip():
    for raw in ("1.23", "1000", "0.000001", "-45.6", 7, 0.5):
        v, s = to_scaled(raw)
        assert from_scaled(v, s) == Decimal(str(raw)).normalize()


# 5 — scaled values never lose precision to floats
def test_to_scaled_exact():
    assert to_scaled("1.1") == (11, 1)
    assert to_scaled(100) == (100, 0)


# 6 — dedupe collapses identical facts only
def test_factset_dedupe():
    fs = FactSet(entity=Entity(ticker="TEST US"))
    fs.add(_fact())
    fs.add(_fact())
    fs.add(_fact(value=2))
    assert len(fs.dedupe().facts) == 2


# 7 — instant vs duration periods
def test_period_instant():
    assert Period(end="2025-12-31").is_instant
    assert not Period(end="2025-12-31", start="2025-01-01").is_instant
