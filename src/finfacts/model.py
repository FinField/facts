"""Core FinField data model.

A FinFact is one atomic, provenance-carrying financial fact about one listed
entity: concept, value, unit, period, source. Facts serialize to canonical
JSON and hash to a deterministic content id (CID), so any two nodes that
ingest the same source data mint byte-identical facts — the property that
makes P2P replication converge without coordination.

Values are scaled integers (value * 10^-scale), never floats: the knitweb
canonical path (deterministic CBOR) forbids floats, and exact decimals are
what audited filings contain anyway.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Optional, Union

CID_PREFIX = "ff1"  # finfield standalone fact hash, canonicalization version 1


def to_scaled(value: Union[int, float, str, Decimal]) -> tuple[int, int]:
    """Convert a number to (int_value, scale) with actual = value * 10^-scale."""
    d = Decimal(str(value)).normalize()
    exp = d.as_tuple().exponent
    if exp >= 0:
        return int(d), 0
    scale = -exp
    return int(d.scaleb(scale)), scale


def from_scaled(value: int, scale: int) -> Decimal:
    return Decimal(value).scaleb(-scale)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, unicode preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def cid(obj: Any) -> str:
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return f"{CID_PREFIX}:{digest}"


@dataclass(frozen=True)
class Entity:
    """A listed company, keyed on its composite ticker (e.g. 'AAPL US').

    Only open identifiers are carried; licensed schemes (SEDOL, GICS) are
    deliberately absent so entities are safe to publish.
    """

    ticker: str
    name: str = ""
    country: str = ""
    asset: str = "equity"  # asset class: equity | crypto
    cik: Optional[str] = None  # SEC Central Index Key (public domain)
    lei: Optional[str] = None  # GLEIF Legal Entity Identifier (open)
    figi: Optional[str] = None  # OpenFIGI (open standard)

    @property
    def entity_id(self) -> str:
        return f"ticker:{self.ticker}"


@dataclass(frozen=True)
class Period:
    """Instant (end only) or duration (start+end) reporting period."""

    end: str  # ISO date
    start: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None  # FY, Q1..Q4

    @property
    def is_instant(self) -> bool:
        return self.start is None


@dataclass(frozen=True)
class Source:
    """Where a fact came from — every published number must be traceable."""

    kind: str  # e.g. "sec-companyfacts"
    ref: str = ""  # accession number, URL, or dataset id
    fetched: str = ""  # ISO date the source was read


@dataclass(frozen=True)
class FinFact:
    entity_id: str
    concept: str  # namespaced, e.g. "us-gaap:Revenues" or "finfield:pe_ttm"
    value: int  # scaled integer; actual = value * 10^-scale
    unit: str  # "USD", "shares", "pure", ...
    period: Period
    source: Source
    scale: int = 0
    derived_from: tuple = ()  # CIDs of input facts, for derived concepts

    @property
    def decimal(self) -> Decimal:
        return from_scaled(self.value, self.scale)

    def payload(self) -> dict:
        d = asdict(self)
        d["derived_from"] = list(self.derived_from)
        # drop empty optionals so equal facts canonicalize identically
        d["period"] = {k: v for k, v in d["period"].items() if v is not None}
        return d

    @property
    def cid(self) -> str:
        return cid(self.payload())


@dataclass
class FactSet:
    """A batch of facts for one entity from one ingestion run."""

    entity: Entity
    facts: list = field(default_factory=list)

    def add(self, fact: FinFact) -> None:
        self.facts.append(fact)

    def dedupe(self) -> "FactSet":
        seen: dict[str, FinFact] = {}
        for f in self.facts:
            seen[f.cid] = f
        self.facts = list(seen.values())
        return self
