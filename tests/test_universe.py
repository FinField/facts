"""Universe guard tests: coverage and licence-cleanliness."""
import csv

from finfacts.universe import DEFAULT_UNIVERSE, iter_universe

LICENSED_COLUMNS = {"sedol", "isin", "isin_code", "gics", "gics_subindustry", "bb_exch_code"}


# 1 — the universe covers 20,000+ companies
def test_universe_size():
    assert sum(1 for _ in iter_universe()) > 20_000


# 2 — no licensed identifier columns ever ship publicly
def test_no_licensed_columns():
    with DEFAULT_UNIVERSE.open() as f:
        header = {c.strip().lower() for c in next(csv.reader(f))}
    assert not header & LICENSED_COLUMNS


# 3 — every row has a ticker; countries look like ISO-ish codes
def test_rows_wellformed():
    for e in iter_universe():
        assert e.ticker
        assert len(e.country) <= 3
        assert e.asset in ("equity", "crypto")
