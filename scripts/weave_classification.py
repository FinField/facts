#!/usr/bin/env python3
"""Weave the next batch of classification knits + fibers into a seed file.

Idempotent + unique by CID: each run appends the next unseen SIC major-group
knits (default 5) and their provenance fibers (5 each) to seeds/classification.jsonl,
skipping any record already present. Public-domain SIC data; derived sector
mappings marked method="derived". See finfacts.classification.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from finfacts.classification import weave_next  # noqa: E402
from finfacts.model import canonical_json  # noqa: E402

SEED = Path(__file__).resolve().parent.parent / "seeds" / "classification.jsonl"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    existing = load(SEED)
    new = weave_next(existing, n=n)
    if not new:
        print("no new classifications to weave (curated SIC pool exhausted)")
        return 0
    SEED.parent.mkdir(parents=True, exist_ok=True)
    with SEED.open("a", encoding="utf-8") as fh:
        for rec in new:
            fh.write(canonical_json(rec) + "\n")
    knits = sum(1 for r in new if r["kind"] == "finfield-classification")
    fibers = sum(1 for r in new if r["kind"] == "finfield-fiber")
    print(f"wove {knits} knits + {fibers} fibers -> {SEED.name} (total {len(existing)+len(new)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
