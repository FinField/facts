"""finfacts — the FinField data model.

Atomic, provenance-carrying financial facts with scaled-integer values
(never floats: the knitweb canonical path forbids them, and consensus on
continuous quantities runs through vank instead). Zero dependencies.
"""
from .model import (  # noqa: F401
    CID_PREFIX,
    Entity,
    FactSet,
    FinFact,
    Period,
    Source,
    canonical_json,
    cid,
    from_scaled,
    to_scaled,
)
from . import derive, universe  # noqa: F401

__version__ = "0.1.0"
