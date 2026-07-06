#!/usr/bin/env python3
"""Build the public-safe FinField universe from the local EDS dataset.

Reads the private EDS seed (Numerai ticker history + EDS master snapshots),
strips licensed identifier columns (SEDOL, ISIN, GICS, FactSet ids), and
emits src/finfacts/data/universe.csv with only open, factual fields:

    ticker, asset, country, name, active, first_seen, last_seen

The private seed never leaves the local machine; only this derived,
licence-clean universe is published.

    python3 scripts/build_universe.py --seed-dir ~/Documents/Signals/Data
"""
import argparse
import csv
import sys
from pathlib import Path

# The only columns ever written — no SEDOL/ISIN/GICS/FactSet ids, by construction.
FIELDS = ["ticker", "asset", "country", "name", "active", "first_seen", "last_seen"]
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "src/finfacts/data/universe.csv"


def eds_master(seed_dir: Path) -> Path | None:
    """Latest EDS master snapshot (EDS/EDS_YYYYMMDD.csv), if any."""
    snapshots = sorted((seed_dir / "EDS").glob("EDS_*.csv"))
    return snapshots[-1] if snapshots else None


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--seed-dir",
        type=Path,
        required=True,
        help="private EDS seed dir (e.g. ~/Documents/Signals/Data); never published",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="universe CSV to write")
    args = ap.parse_args(argv)

    seed = args.seed_dir.expanduser()
    numerai = seed / "Identifiers/FMP/numerai_tickers_output.csv"

    seen: dict[str, dict] = {}
    with numerai.open() as f:
        for row in csv.DictReader(f):
            t = row["ticker"].strip()
            if not t:
                continue
            rec = seen.setdefault(
                t, {"first_seen": row["start_date"], "last_seen": row["end_date"], "live": False}
            )
            if row["start_date"] and row["start_date"] < rec["first_seen"]:
                rec["first_seen"] = row["start_date"]
            if row["end_date"] and row["end_date"] > rec["last_seen"]:
                rec["last_seen"] = row["end_date"]
            if row["dataset"] == "live":
                rec["live"] = True

    names: dict[str, dict] = {}
    master = eds_master(seed)
    if master is not None:
        with master.open() as f:
            for row in csv.DictReader(f):
                t = (row.get("bloomberg_ticker") or "").strip()
                if t:
                    names[t] = {
                        "name": (row.get("Name") or "").strip(),
                        "country": (row.get("Country_of_domicile") or "").strip(),
                        "active": (row.get("Active") or "").strip(),
                    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for t in sorted(seen):
            rec = seen[t]
            meta = names.get(t, {})
            # country: prefer EDS master, else the exchange suffix of the composite ticker
            country = meta.get("country") or (t.split()[-1] if " " in t else "")
            active = meta.get("active") or ("1" if rec["live"] else "")
            w.writerow([t, "equity", country, meta.get("name", ""), active, rec["first_seen"], rec["last_seen"]])

    print(f"wrote {args.out} with {len(seen)} tickers")


if __name__ == "__main__":
    sys.exit(main())
