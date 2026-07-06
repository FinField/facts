# finfacts

The FinField data model — the shared foundation every other FinField repo builds on.

- **FinFact** — one atomic financial fact: entity, concept, value, unit, period, source.
  Values are **scaled integers** (`value * 10^-scale`), never floats: the knitweb canonical
  path forbids floats, and consensus on continuous quantities runs through
  [vank](https://github.com/Knitweb/vank) (see [FinField/knit](https://github.com/FinField/knit)).
- **Deterministic CIDs** — canonical JSON + SHA-256, so two nodes ingesting the same source
  mint byte-identical facts and P2P replication converges without coordination.
- **Universe** — 20,699 listed companies (open identifiers only: ticker, CIK, LEI, FIGI).
- **derive** — exact derived metrics (TTM, margins, YoY growth) whose `derived_from` chain
  traces every ratio back to the audited filing.

Pure Python, zero dependencies.

```bash
pip install "finfacts @ git+https://github.com/FinField/facts"
```

```python
from finfacts import FinFact, Period, Source, to_scaled, universe

value, scale = to_scaled("391035000000")  # exact, no float in sight
fact = FinFact(entity_id="ticker:AAPL US", concept="us-gaap:Revenues",
               value=value, scale=scale, unit="USD",
               period=Period(end="2024-09-28", start="2023-10-01"),
               source=Source(kind="sec-companyfacts", ref="0000320193-24-000123"))
print(fact.cid)  # ff1:… — same bytes, same CID, on every node
```

Part of the [FinField](https://github.com/FinField) field: [scrapers](https://github.com/FinField/scrapers) ·
[knit](https://github.com/FinField/knit) · [agents](https://github.com/FinField/agents) ·
[signals](https://github.com/FinField/signals) · [crypto](https://github.com/FinField/crypto)
