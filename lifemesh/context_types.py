from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


LAYER_PRIORITIES = {
    "fact": 0,
    "memory": 1,
    "source-reference": 2,
    "candidate": 3,
    "rumor": 4,
}


@dataclass(frozen=True)
class ContextCandidate:
    slice_data: dict[str, Any]
    source: str
    layer: str
    evidence_role: str
    source_rank: int
    source_score: float | None = None
    citation_status: str = "current"
    sensitivity: str = "Private"
    retrieval_mode: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    candidates: list[ContextCandidate]
    excluded_sources: list[dict[str, Any]] = field(default_factory=list)
    freshness_report: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
