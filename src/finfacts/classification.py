"""Classification knits + fibers — how FinField carries industry taxonomy.

A classification is NOT embedded on :class:`~finfacts.model.Entity`; it is woven
as its own provenance-bearing knit, and linked with fibers. Two record kinds:

* ``finfield-classification`` (a KNIT) — one node of a taxonomy: scheme, level,
  code, name, ``source`` (where it was read), and ``method``:
    - ``published``  — copied from a public-domain source (the SEC's SIC list).
    - ``derived``    — our own estimate/mapping, marked so it is never mistaken
                       for an authoritative licensed classification.
* ``finfield-fiber`` (a RELATION) — a typed, provenance-bearing edge between
  knits (or an entity and a knit): ``rel``, ``subject``, ``object``, ``source``,
  ``method``, and the field-routing tags ``financial_fact`` / ``news_fact``.

Every record hashes to a deterministic CID via :func:`finfacts.model.cid`, so
batches are content-addressed and de-dupe by CID (uniqueness is structural).

Licensing note: the concrete data below is the SEC's **public-domain** Standard
Industrial Classification (US government, freely published). Any mapping toward a
licensed taxonomy (GICS-style broad sectors) is emitted only as ``method=derived``
with a source citation — our estimate, attributed, not a reproduced proprietary
table. Published licensed classifications may be referenced the same way: a fiber
citing exactly where the value was publicly published (optionally OriginTrail-
anchored), never bulk-copied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import cid

# -- source provenance -------------------------------------------------------
SEC_SIC = {"kind": "sec-sic", "ref": "https://www.sec.gov/corpfin/division-of-corporation-finance-standard-industrial-classification-sic-code-list"}
FINFIELD_DERIVED = {"kind": "finfield-derived", "ref": "finfacts.classification"}


@dataclass(frozen=True)
class Classification:
    """A taxonomy node (KNIT)."""

    scheme: str          # "sic"
    level: str           # "division" | "major-group" | "sector" (derived)
    code: str            # "28"
    name: str            # "Chemicals & Allied Products"
    source: dict         # provenance
    method: str = "published"  # "published" | "derived"

    def record(self) -> dict:
        return {
            "kind": "finfield-classification",
            "scheme": self.scheme, "level": self.level,
            "code": self.code, "name": self.name,
            "method": self.method, "source": dict(self.source),
        }

    @property
    def cid(self) -> str:
        return cid(self.record())


@dataclass(frozen=True)
class Fiber:
    """A typed provenance-bearing relation (FIBER) between two nodes."""

    rel: str             # "subclass_of" | "in_scheme" | "sourced_from" | "maps_to" | "classified_as"
    subject: str         # a CID or an id like "ticker:AIR US" / "scheme:sic"
    object: str          # a CID or an id
    source: dict
    method: str = "published"
    financial_fact: bool = True
    news_fact: bool = False

    def record(self) -> dict:
        return {
            "kind": "finfield-fiber",
            "rel": self.rel, "subject": self.subject, "object": self.object,
            "method": self.method,
            "financial_fact": self.financial_fact, "news_fact": self.news_fact,
            "source": dict(self.source),
        }

    @property
    def cid(self) -> str:
        return cid(self.record())


# -- public-domain SIC data (US government; freely published by the SEC) ------
# SIC divisions (letter -> title, 2-digit major-group range).
SIC_DIVISIONS = {
    "A": ("Agriculture, Forestry & Fishing", (1, 9)),
    "B": ("Mining", (10, 14)),
    "C": ("Construction", (15, 17)),
    "D": ("Manufacturing", (20, 39)),
    "E": ("Transportation, Communications, Electric, Gas & Sanitary Services", (40, 49)),
    "F": ("Wholesale Trade", (50, 51)),
    "G": ("Retail Trade", (52, 59)),
    "H": ("Finance, Insurance & Real Estate", (60, 67)),
    "I": ("Services", (70, 89)),
    "J": ("Public Administration", (91, 99)),
}

# A curated set of SIC major groups (2-digit code -> title). Public domain.
SIC_MAJOR_GROUPS = [
    ("01", "Agricultural Production - Crops"),
    ("10", "Metal Mining"),
    ("13", "Oil & Gas Extraction"),
    ("15", "Building Construction - General Contractors"),
    ("20", "Food & Kindred Products"),
    ("22", "Textile Mill Products"),
    ("23", "Apparel & Other Finished Products"),
    ("24", "Lumber & Wood Products"),
    ("26", "Paper & Allied Products"),
    ("27", "Printing, Publishing & Allied Industries"),
    ("28", "Chemicals & Allied Products"),
    ("29", "Petroleum Refining & Related Industries"),
    ("30", "Rubber & Miscellaneous Plastics Products"),
    ("33", "Primary Metal Industries"),
    ("34", "Fabricated Metal Products"),
    ("35", "Industrial & Commercial Machinery & Computer Equipment"),
    ("36", "Electronic & Other Electrical Equipment"),
    ("37", "Transportation Equipment"),
    ("38", "Measuring, Analyzing & Controlling Instruments"),
    ("45", "Transportation by Air"),
    ("48", "Communications"),
    ("49", "Electric, Gas & Sanitary Services"),
    ("50", "Wholesale Trade - Durable Goods"),
    ("53", "General Merchandise Stores"),
    ("54", "Food Stores"),
    ("58", "Eating & Drinking Places"),
    ("60", "Depository Institutions"),
    ("61", "Nondepository Credit Institutions"),
    ("62", "Security & Commodity Brokers & Dealers"),
    ("63", "Insurance Carriers"),
    ("65", "Real Estate"),
    ("67", "Holding & Other Investment Offices"),
    ("70", "Hotels, Rooming Houses & Lodging"),
    ("73", "Business Services"),
    ("78", "Motion Pictures"),
    ("79", "Amusement & Recreation Services"),
    ("80", "Health Services"),
    ("82", "Educational Services"),
    ("87", "Engineering, Accounting, Research & Management Services"),
]

# Our DERIVED broad-sector estimate per major group (generic sector labels only;
# method="derived", never a reproduced proprietary mapping). Keyed by SIC code.
DERIVED_SECTOR = {
    "01": "Consumer Staples", "10": "Materials", "13": "Energy", "15": "Industrials",
    "20": "Consumer Staples", "22": "Consumer Discretionary", "23": "Consumer Discretionary",
    "24": "Materials", "26": "Materials", "27": "Communication Services",
    "28": "Materials", "29": "Energy", "30": "Materials", "33": "Materials",
    "34": "Industrials", "35": "Industrials", "36": "Information Technology",
    "37": "Industrials", "38": "Health Care", "45": "Industrials",
    "48": "Communication Services", "49": "Utilities", "50": "Industrials",
    "53": "Consumer Discretionary", "54": "Consumer Staples", "58": "Consumer Discretionary",
    "60": "Financials", "61": "Financials", "62": "Financials", "63": "Financials",
    "65": "Real Estate", "67": "Financials", "70": "Consumer Discretionary",
    "73": "Information Technology", "78": "Communication Services",
    "79": "Communication Services", "80": "Health Care", "82": "Consumer Discretionary",
    "87": "Industrials",
}

# A public example filer per major group (SEC assigns each filer a SIC, public
# domain via EDGAR). Used for one illustrative classified_as fiber per knit.
EXAMPLE_FILER = {
    "01": "ticker:AGRO US", "10": "ticker:NEM US", "13": "ticker:XOM US",
    "15": "ticker:PHM US", "20": "ticker:GIS US", "22": "ticker:UA US",
    "23": "ticker:RL US", "24": "ticker:WY US", "26": "ticker:IP US",
    "27": "ticker:NWSA US", "28": "ticker:DD US", "29": "ticker:VLO US",
    "30": "ticker:NWL US", "33": "ticker:NUE US", "34": "ticker:SWK US",
    "35": "ticker:CAT US", "36": "ticker:AAPL US", "37": "ticker:BA US",
    "38": "ticker:TMO US", "45": "ticker:DAL US", "48": "ticker:T US",
    "49": "ticker:DUK US", "50": "ticker:GWW US", "53": "ticker:WMT US",
    "54": "ticker:KR US", "58": "ticker:MCD US", "60": "ticker:JPM US",
    "61": "ticker:SYF US", "62": "ticker:GS US", "63": "ticker:CB US",
    "65": "ticker:SPG US", "67": "ticker:BLK US", "70": "ticker:MAR US",
    "73": "ticker:MSFT US", "78": "ticker:NFLX US", "79": "ticker:LYV US",
    "80": "ticker:UNH US", "82": "ticker:LOPE US", "87": "ticker:ACN US",
}


def _division_for(code: str) -> Optional[tuple[str, str]]:
    """(division_letter, division_title) that a 2-digit major-group code sits in."""
    n = int(code)
    for letter, (title, (lo, hi)) in SIC_DIVISIONS.items():
        if lo <= n <= hi:
            return letter, title
    return None


def knit_and_fibers(code: str, name: str) -> tuple[dict, list[dict]]:
    """One major-group KNIT + exactly five provenance-bearing FIBERS.

    Fibers: subclass_of its division, in_scheme sic, sourced_from the SEC list,
    a DERIVED maps_to a broad sector, and a public classified_as example filer.
    """
    knit = Classification("sic", "major-group", code, name, SEC_SIC, "published")
    kc = knit.cid
    div = _division_for(code)
    fibers: list[Fiber] = []
    if div:
        div_letter, div_title = div
        div_knit = Classification("sic", "division", div_letter, div_title, SEC_SIC, "published")
        fibers.append(Fiber("subclass_of", kc, div_knit.cid, SEC_SIC, "published"))
    fibers.append(Fiber("in_scheme", kc, "scheme:sic", SEC_SIC, "published"))
    fibers.append(Fiber("sourced_from", kc, SEC_SIC["ref"], SEC_SIC, "published"))
    sector = DERIVED_SECTOR.get(code)
    if sector:
        fibers.append(Fiber("maps_to", kc, f"sector:{sector}", FINFIELD_DERIVED, "derived"))
    filer = EXAMPLE_FILER.get(code)
    if filer:
        fibers.append(Fiber("classified_as", filer, kc, SEC_SIC, "published"))
    return knit.record(), [f.record() for f in fibers]


def batch_records(groups: list[tuple[str, str]]) -> list[dict]:
    """Flat list of records (knits then their fibers) for the given groups."""
    out: list[dict] = []
    for code, name in groups:
        knit, fibers = knit_and_fibers(code, name)
        out.append(knit)
        out.extend(fibers)
    return out


def weave_next(existing: list[dict], n: int = 5) -> list[dict]:
    """The next ``n`` unseen SIC major-group knits + their fibers.

    "Unseen" = the group's ``code`` is not already present as a woven
    ``finfield-classification`` major-group knit in ``existing``. The returned
    records are further filtered so no record whose CID is already present is
    re-emitted — uniqueness is by content-address, so re-running never dupes.
    Returns [] once the curated pool is exhausted.
    """
    seen_codes = {
        r.get("code") for r in existing
        if r.get("kind") == "finfield-classification" and r.get("level") == "major-group"
    }
    seen_cids = {cid(r) for r in existing}
    fresh_groups = [g for g in SIC_MAJOR_GROUPS if g[0] not in seen_codes][:n]
    records = batch_records(fresh_groups)
    return [r for r in records if cid(r) not in seen_cids]
