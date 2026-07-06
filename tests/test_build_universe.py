"""Universe builder tests: licence-clean output from a synthetic EDS seed."""
import csv
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/build_universe.py"

spec = importlib.util.spec_from_file_location("build_universe", SCRIPT)
build_universe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_universe)


def _seed(tmp_path):
    seed = tmp_path / "seed"
    numerai = seed / "Identifiers/FMP/numerai_tickers_output.csv"
    numerai.parent.mkdir(parents=True)
    numerai.write_text(
        "ticker,start_date,end_date,dataset\n"
        "AAPL US,2003-01-01,2026-07-01,live\n"
        "AAPL US,2000-01-01,2010-01-01,history\n"
        "DEAD LN,2001-01-01,2005-06-30,history\n"
        ",2001-01-01,2005-06-30,history\n"  # blank ticker dropped
    )
    master = seed / "EDS/EDS_20230824.csv"
    master.parent.mkdir(parents=True)
    # the seed carries licensed identifier columns; they must never propagate
    master.write_text(
        "bloomberg_ticker,Name,Country_of_domicile,Active,SEDOL,ISIN,GICS_sector\n"
        "AAPL US,Apple Inc,US,1,2046251,US0378331005,45\n"
    )
    return seed


def test_build_universe_is_licence_clean_and_deterministic(tmp_path):
    seed = _seed(tmp_path)
    out = tmp_path / "universe.csv"
    build_universe.main(["--seed-dir", str(seed), "--out", str(out)])

    with out.open() as f:
        rows = list(csv.DictReader(f))
    header = rows[0].keys()
    assert list(header) == build_universe.FIELDS
    for licensed in ("SEDOL", "ISIN", "GICS"):
        assert not any(licensed.lower() in h.lower() for h in header)

    assert [r["ticker"] for r in rows] == ["AAPL US", "DEAD LN"]  # sorted
    aapl, dead = rows
    assert aapl["name"] == "Apple Inc" and aapl["country"] == "US"
    assert aapl["active"] == "1"
    assert (aapl["first_seen"], aapl["last_seen"]) == ("2000-01-01", "2026-07-01")
    # no EDS row: country falls back to the composite-ticker suffix, active unknown
    assert dead["country"] == "LN" and dead["active"] == "" and dead["asset"] == "equity"

    first = out.read_bytes()
    build_universe.main(["--seed-dir", str(seed), "--out", str(out)])
    assert out.read_bytes() == first  # byte-identical rebuild


def test_build_universe_without_eds_master(tmp_path):
    seed = _seed(tmp_path)
    (seed / "EDS/EDS_20230824.csv").unlink()
    out = tmp_path / "universe.csv"
    build_universe.main(["--seed-dir", str(seed), "--out", str(out)])
    with out.open() as f:
        rows = list(csv.DictReader(f))
    assert [r["ticker"] for r in rows] == ["AAPL US", "DEAD LN"]
    assert rows[0]["active"] == "1"  # live dataset row still marks it active
