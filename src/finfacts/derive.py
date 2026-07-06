"""Smart layer: derived concepts computed from base facts.

Every derived fact records the CIDs of its inputs in `derived_from`, so the
chain from a headline ratio back to the audited filing is machine-checkable —
the thing no mainstream financial website gives you.

All arithmetic is exact (scaled integers / Decimal); ratios are emitted at
scale 6 (micro-units).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Optional

from finfacts.model import FactSet, FinFact, Period, Source

DERIVED = Source(kind="finfield-derived", ref="finfield.smart.derive")
RATIO_SCALE = 6
# every node must mint the same ratio bytes regardless of the host app's
# ambient decimal context
_CTX = dict(prec=28, rounding=ROUND_HALF_EVEN)

# concepts treated as the canonical income-statement lines (first match wins)
REVENUE = (
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:Revenues",
    "us-gaap:SalesRevenueNet",
)
NET_INCOME = ("us-gaap:NetIncomeLoss",)
# dei:EntityPublicFloat is the dollar value of the public float — free-float
# market cap straight from the filing, no share-count multiplication needed
PUBLIC_FLOAT = ("dei:EntityPublicFloat",)
BOOK_EQUITY = (
    "us-gaap:StockholdersEquity",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
CAPEX = ("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",)
OPEX = (
    "us-gaap:OperatingExpenses",
    "us-gaap:CostsAndExpenses",
)


def _days(f: FinFact) -> int:
    s, e = date.fromisoformat(f.period.start), date.fromisoformat(f.period.end)
    return (e - s).days


def _quarterly(fs: FactSet, concepts: tuple) -> list[FinFact]:
    """Duration facts of ~one quarter for the first concept that has them."""
    for concept in concepts:
        rows = [
            f
            for f in fs.facts
            if f.concept == concept
            and f.period.start
            and f.period.fiscal_period in ("Q1", "Q2", "Q3", "Q4")
            and _days(f) <= 100
        ]
        if rows:
            # latest restatement wins per period (accessions sort chronologically)
            dedup = {
                (f.period.start, f.period.end): f
                for f in sorted(rows, key=lambda f: f.source.ref)
            }
            return sorted(dedup.values(), key=lambda f: f.period.end)
    return []


def _latest_instant(fs: FactSet, concepts: tuple) -> Optional[FinFact]:
    """Most recent instant fact for the first concept that has any."""
    for concept in concepts:
        rows = [f for f in fs.facts if f.concept == concept and not f.period.start]
        if rows:
            # latest restatement wins per period (accessions sort chronologically)
            dedup = {
                f.period.end: f
                for f in sorted(rows, key=lambda f: f.source.ref)
            }
            return max(dedup.values(), key=lambda f: f.period.end)
    return None


def _ratio_fact(entity_id: str, concept: str, numer: FinFact, denom: FinFact, period: Period) -> FinFact:
    with localcontext(**_CTX):
        ratio = numer.decimal / denom.decimal
        scaled = int((ratio * 10**RATIO_SCALE).to_integral_value())
    return FinFact(
        entity_id=entity_id,
        concept=concept,
        value=scaled,
        scale=RATIO_SCALE,
        unit="pure",
        period=period,
        source=DERIVED,
        derived_from=(numer.cid, denom.cid),
    )


def ttm(fs: FactSet, concepts: tuple, out_concept: str) -> Optional[FinFact]:
    """Trailing-twelve-months sum of the last four distinct quarters."""
    q = _quarterly(fs, concepts)
    if len(q) < 4:
        return None
    last4 = q[-4:]
    span = (date.fromisoformat(last4[-1].period.end)
            - date.fromisoformat(last4[0].period.start)).days
    if not 350 <= span <= 380:  # four contiguous quarters, no gaps/restated holes
        return None
    common = max(f.scale for f in last4)
    total = sum(f.value * 10 ** (common - f.scale) for f in last4)
    return FinFact(
        entity_id=fs.entity.entity_id,
        concept=out_concept,
        value=total,
        scale=common,
        unit=last4[-1].unit,
        period=Period(start=last4[0].period.start, end=last4[-1].period.end),
        source=DERIVED,
        derived_from=tuple(f.cid for f in last4),
    )


def margin(numer: Optional[FinFact], denom: Optional[FinFact], out_concept: str) -> Optional[FinFact]:
    if not numer or not denom or denom.value == 0:
        return None
    return _ratio_fact(numer.entity_id, out_concept, numer, denom, numer.period)


def instant_ratio(numer: Optional[FinFact], denom: Optional[FinFact], out_concept: str) -> Optional[FinFact]:
    """Point-in-time ratio (instant/instant or ttm/instant), e.g. B/M on free float."""
    if not numer or not denom or denom.value <= 0:
        return None
    if numer.unit != "USD" or denom.unit != "USD":  # apples-to-apples dollars only
        return None
    gap = abs(date.fromisoformat(numer.period.end)
              - date.fromisoformat(denom.period.end)).days
    if gap > 400:  # a fresh float against years-old fundamentals is meaningless
        return None
    return _ratio_fact(numer.entity_id, out_concept, numer, denom,
                       Period(end=max(numer.period.end, denom.period.end)))


def yoy_growth(fs: FactSet, concepts: tuple, out_concept: str) -> Optional[FinFact]:
    """Year-over-year growth of the most recent quarter vs the same quarter last year."""
    q = _quarterly(fs, concepts)
    if not q:
        return None
    by_fp = defaultdict(list)
    for f in q:
        by_fp[f.period.fiscal_period].append(f)
    latest = q[-1]
    same_fp = sorted(by_fp[latest.period.fiscal_period], key=lambda f: f.period.end)
    if len(same_fp) < 2:
        return None
    prev = same_fp[-2]
    gap = (date.fromisoformat(latest.period.end)
           - date.fromisoformat(prev.period.end)).days
    if not 330 <= gap <= 400:  # exactly one fiscal year apart
        return None
    if prev.value <= 0:  # growth on a non-positive base is undefined, not sign-flipped
        return None
    with localcontext(**_CTX):
        growth = latest.decimal / prev.decimal - Decimal(1)
        scaled = int((growth * 10**RATIO_SCALE).to_integral_value())
    return FinFact(
        entity_id=latest.entity_id,
        concept=out_concept,
        value=scaled,
        scale=RATIO_SCALE,
        unit="pure",
        period=latest.period,
        source=DERIVED,
        derived_from=(latest.cid, prev.cid),
    )


def derive_all(fs: FactSet) -> list[FinFact]:
    """Standard smart pack: TTM lines, margin, YoY growth, free-float F&F ratios."""
    rev_ttm = ttm(fs, REVENUE, "finfield:revenue_ttm")
    ni_ttm = ttm(fs, NET_INCOME, "finfield:net_income_ttm")
    capex_ttm = ttm(fs, CAPEX, "finfield:capex_ttm")
    opex_ttm = ttm(fs, OPEX, "finfield:opex_ttm")
    float_mcap = _latest_instant(fs, PUBLIC_FLOAT)
    book = _latest_instant(fs, BOOK_EQUITY)
    out = [
        rev_ttm,
        ni_ttm,
        capex_ttm,
        opex_ttm,
        margin(ni_ttm, rev_ttm, "finfield:net_margin_ttm"),
        yoy_growth(fs, REVENUE, "finfield:revenue_yoy"),
        yoy_growth(fs, NET_INCOME, "finfield:net_income_yoy"),
        instant_ratio(book, float_mcap, "finfield:book_to_float_mcap"),
        instant_ratio(ni_ttm, float_mcap, "finfield:earnings_to_float_mcap"),
        instant_ratio(capex_ttm, float_mcap, "finfield:capex_to_float_mcap"),
    ]
    return [f for f in out if f is not None]
