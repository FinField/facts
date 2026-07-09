"""Classification knits + fibers: shape, provenance, determinism, uniqueness."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from finfacts.classification import (  # noqa: E402
    Classification,
    Fiber,
    knit_and_fibers,
    weave_next,
)
from finfacts.model import cid  # noqa: E402


def test_knit_has_provenance_and_stable_cid():
    k = Classification("sic", "major-group", "28", "Chemicals & Allied Products",
                       {"kind": "sec-sic", "ref": "x"}, "published")
    rec = k.record()
    assert rec["kind"] == "finfield-classification"
    assert rec["source"]["kind"] == "sec-sic"
    assert k.cid == cid(rec)                      # cid is over the canonical record
    # deterministic
    assert Classification("sic", "major-group", "28", "Chemicals & Allied Products",
                          {"kind": "sec-sic", "ref": "x"}, "published").cid == k.cid


def test_fiber_carries_fact_type_tags_and_method():
    f = Fiber("maps_to", "ff1:aaa", "sector:Materials",
              {"kind": "finfield-derived", "ref": "y"}, "derived")
    rec = f.record()
    assert rec["kind"] == "finfield-fiber"
    assert rec["financial_fact"] is True and rec["news_fact"] is False
    assert rec["method"] == "derived"


def test_knit_and_fibers_is_five_fibers_with_correct_methods():
    knit, fibers = knit_and_fibers("28", "Chemicals & Allied Products")
    assert knit["level"] == "major-group"
    assert len(fibers) == 5
    rels = {f["rel"] for f in fibers}
    assert rels == {"subclass_of", "in_scheme", "sourced_from", "maps_to", "classified_as"}
    # only the derived sector mapping is method=derived; everything else published
    for f in fibers:
        assert f["method"] == ("derived" if f["rel"] == "maps_to" else "published")
    # the derived fiber cites a non-authoritative source, never sec-sic
    dv = next(f for f in fibers if f["rel"] == "maps_to")
    assert dv["source"]["kind"] == "finfield-derived"
    assert dv["object"].startswith("sector:")


def test_weave_next_batch_is_5_knits_25_fibers_all_unique():
    batch = weave_next([], n=5)
    knits = [r for r in batch if r["kind"] == "finfield-classification"]
    fibers = [r for r in batch if r["kind"] == "finfield-fiber"]
    assert len(knits) == 5 and len(fibers) == 25
    cids = [cid(r) for r in batch]
    assert len(set(cids)) == len(cids)            # every record content-unique


def test_weave_next_advances_and_never_dupes():
    first = weave_next([], n=5)
    # feeding the first batch back, the next call yields the NEXT groups, no overlap
    second = weave_next(first, n=5)
    first_codes = {r["code"] for r in first if r["kind"] == "finfield-classification"}
    second_codes = {r["code"] for r in second if r["kind"] == "finfield-classification"}
    assert first_codes.isdisjoint(second_codes)
    # and no CID from the first batch reappears in the second
    first_cids = {cid(r) for r in first}
    assert all(cid(r) not in first_cids for r in second)


def test_weave_next_is_deterministic():
    assert [cid(r) for r in weave_next([], 5)] == [cid(r) for r in weave_next([], 5)]


def test_pool_exhaustion_returns_empty():
    from finfacts.classification import SIC_MAJOR_GROUPS
    # seed with EVERY major group already woven -> nothing left
    all_batches: list[dict] = []
    existing: list[dict] = []
    for _ in range(len(SIC_MAJOR_GROUPS) + 2):
        b = weave_next(existing, n=5)
        if not b:
            break
        existing += b
    assert weave_next(existing, n=5) == []
