"""Dimensional (segment) facts — CID compatibility is the hard requirement."""
from finfacts.model import Entity, FactSet, FinFact, Period, Source, cid

SRC = Source(kind="esef-filings", ref="LEI-2025-12-31-ESEF-NL-0", fetched="2026-07-07")


def _fact(dimensions=()):
    return FinFact(
        entity_id="ticker:ASML NA",
        concept="ifrs-full:RevenueFromContractsWithCustomers",
        value=32_667_300_000,
        unit="EUR",
        period=Period(start="2025-01-01", end="2025-12-31", fiscal_year=2025, fiscal_period="FY"),
        source=SRC,
        dimensions=dimensions,
    )


def test_dimensionless_payload_has_no_dimensions_key():
    """Every pre-existing fact must keep its exact CID: the empty default
    serializes to the same payload as before the field existed."""
    p = _fact().payload()
    assert "dimensions" not in p
    legacy = {k: v for k, v in p.items()}  # what payload() produced pre-field
    assert cid(legacy) == _fact().cid


def test_dimension_order_does_not_change_cid():
    a = _fact((("asml:GeographicalAxis", "asml:NetherlandsMember"),
               ("ifrs-full:SegmentsAxis", "asml:SystemsMember")))
    b = _fact((("ifrs-full:SegmentsAxis", "asml:SystemsMember"),
               ("asml:GeographicalAxis", "asml:NetherlandsMember")))
    assert a.cid == b.cid
    assert a.payload()["dimensions"] == [
        ["asml:GeographicalAxis", "asml:NetherlandsMember"],
        ["ifrs-full:SegmentsAxis", "asml:SystemsMember"],
    ]


def test_segment_fact_differs_from_consolidated():
    seg = _fact((("asml:GeographicalAxis", "asml:NetherlandsMember"),))
    assert seg.cid != _fact().cid


def test_dedupe_keeps_segments_apart():
    fs = FactSet(entity=Entity(ticker="ASML NA"))
    fs.add(_fact())
    fs.add(_fact((("asml:GeographicalAxis", "asml:NetherlandsMember"),)))
    fs.add(_fact((("asml:GeographicalAxis", "asml:NetherlandsMember"),)))  # dup
    assert len(fs.dedupe().facts) == 2
