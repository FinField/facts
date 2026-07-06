"""Load the FinField universe: 20,000+ listed companies from the EDS seed."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

from .model import Entity

DEFAULT_UNIVERSE = Path(__file__).resolve().parent / "data/universe.csv"


def load(path: Optional[Path] = None, active_only: bool = False) -> list[Entity]:
    return list(iter_universe(path, active_only=active_only))


def iter_universe(path: Optional[Path] = None, active_only: bool = False) -> Iterator[Entity]:
    src = Path(path) if path else DEFAULT_UNIVERSE
    with src.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if active_only and row.get("active") != "1":
                continue
            yield Entity(
                ticker=row["ticker"],
                name=row.get("name", ""),
                country=row.get("country", ""),
                asset=row.get("asset") or "equity",
            )


def by_country(entities: list[Entity]) -> dict[str, list[Entity]]:
    out: dict[str, list[Entity]] = {}
    for e in entities:
        out.setdefault(e.country or "??", []).append(e)
    return out
