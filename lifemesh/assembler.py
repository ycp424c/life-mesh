from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from .context_types import ContextCandidate, LAYER_PRIORITIES


SELECTION_POLICY = "layered-diversified-v1"
SENSITIVITY_LEVELS = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
SENSITIVITY_RANK = {name.lower(): index for index, name in enumerate(SENSITIVITY_LEVELS)}
BLOCKED_SOURCE_STATUSES = {"promoted", "revoked", "deleted"}


class BundleAssembler:
    def assemble(
        self,
        *,
        task: str,
        allowed_sources: list[str],
        sensitivity_cap: str,
        max_slices: int,
        candidates: list[ContextCandidate],
        excluded_sources: list[dict[str, Any]] | None = None,
        freshness_report: list[dict[str, Any]] | None = None,
        include_unverified: bool = False,
    ) -> dict[str, Any]:
        if max_slices < 1:
            raise ValueError("--max-slices must be at least 1")
        normalized_cap = _normalize_sensitivity(sensitivity_cap)
        if normalized_cap is None:
            raise ValueError(f"Unknown sensitivity cap: {sensitivity_cap}")

        admitted: list[ContextCandidate] = []
        rejected: list[dict[str, Any]] = []
        for candidate in candidates:
            rejection = _rejection_for(candidate, allowed_sources, normalized_cap, include_unverified)
            if rejection is None:
                admitted.append(candidate)
            else:
                rejected.append(rejection)
        selected = self._select(admitted, max_slices)
        slices = [dict(candidate.slice_data) for candidate in selected]

        return {
            "schema_version": "1",
            "bundle_id": str(uuid.uuid4()),
            "task": {"description": task, "agent_capability": "search"},
            "permission_scope": {
                "allowed_sources": allowed_sources,
                "sensitivity_cap": sensitivity_cap,
                "include_unverified": include_unverified,
            },
            "assembled_at": _utc_now(),
            "slices": slices,
            "excluded_sources": _dedupe_exclusions([*(excluded_sources or []), *rejected]),
            "freshness_report": freshness_report or [],
            "assembly_report": self._assembly_report(candidates, admitted, selected),
        }

    def _select(self, candidates: list[ContextCandidate], max_slices: int) -> list[ContextCandidate]:
        selected: list[ContextCandidate] = []
        seen_keys: set[tuple[Any, ...]] = set()
        for layer in sorted(LAYER_PRIORITIES, key=LAYER_PRIORITIES.get):
            layer_candidates = [candidate for candidate in candidates if candidate.layer == layer]
            for candidate in _diversified(layer_candidates):
                key = _dedupe_key(candidate)
                if key in seen_keys:
                    continue
                selected.append(candidate)
                seen_keys.add(key)
                if len(selected) >= max_slices:
                    return selected
        return selected

    def _assembly_report(
        self,
        candidates: list[ContextCandidate],
        admitted: list[ContextCandidate],
        selected: list[ContextCandidate],
    ) -> dict[str, Any]:
        return {
            "selection_policy": SELECTION_POLICY,
            "candidate_counts": _count_by(candidates, "source"),
            "admitted_counts": _count_by(admitted, "layer"),
            "selected_counts": _count_by(selected, "source"),
            "sources": {
                source: {
                    "candidate_count": count,
                    "selected_count": _count_by(selected, "source").get(source, 0),
                }
                for source, count in sorted(_count_by(candidates, "source").items())
            },
        }


def _diversified(candidates: list[ContextCandidate]) -> list[ContextCandidate]:
    grouped: dict[str, list[ContextCandidate]] = {}
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item.source_rank,
            -float(item.source_score or 0.0),
            _dedupe_key(item),
        ),
    ):
        grouped.setdefault(candidate.source, []).append(candidate)

    ordered_sources = sorted(
        grouped,
        key=lambda source: (
            grouped[source][0].source_rank,
            -float(grouped[source][0].source_score or 0.0),
            source,
        ),
    )
    diversified: list[ContextCandidate] = []
    while ordered_sources:
        next_sources: list[str] = []
        for source in ordered_sources:
            queue = grouped[source]
            if queue:
                diversified.append(queue.pop(0))
            if queue:
                next_sources.append(source)
        ordered_sources = next_sources
    return diversified


def _dedupe_key(candidate: ContextCandidate) -> tuple[Any, ...]:
    provenance = candidate.slice_data.get("provenance", {})
    if candidate.source == "manual-input":
        return (candidate.source, provenance.get("input_id"))
    if candidate.source == "rumor":
        return (candidate.source, provenance.get("rumor_claim_id"))
    if candidate.source == "obsidian":
        return (
            candidate.source,
            provenance.get("note_path"),
            tuple(candidate.slice_data.get("line_range", [])),
        )
    return (
        candidate.source,
        provenance.get("object_id")
        or provenance.get("id")
        or candidate.slice_data.get("slice_id"),
    )


def _rejection_for(
    candidate: ContextCandidate,
    allowed_sources: list[str],
    sensitivity_cap: str,
    include_unverified: bool,
) -> dict[str, Any] | None:
    provenance = candidate.slice_data.get("provenance", {})
    if candidate.source not in allowed_sources:
        return _exclusion(candidate, "source_not_allowed")
    if candidate.source == "rumor" and not include_unverified:
        return _exclusion(candidate, "unverified_not_requested")
    if candidate.layer not in LAYER_PRIORITIES:
        return _exclusion(candidate, "unsupported_layer")
    citation_status = candidate.citation_status or candidate.slice_data.get("citation_status")
    if citation_status != "current":
        return _exclusion(candidate, "citation_not_current", citation_status=citation_status)
    status = provenance.get("status")
    if status in BLOCKED_SOURCE_STATUSES:
        return _exclusion(candidate, str(status))
    sensitivity = str(candidate.sensitivity or candidate.slice_data.get("sensitivity") or "")
    sensitivity_rank = SENSITIVITY_RANK.get(sensitivity.lower())
    if sensitivity_rank is None:
        return _exclusion(candidate, "unknown_sensitivity")
    if sensitivity_rank > _sensitivity_rank(sensitivity_cap):
        return _exclusion(candidate, "sensitivity_cap_exceeded")
    return None


def _exclusion(candidate: ContextCandidate, reason: str, **extra: Any) -> dict[str, Any]:
    provenance = candidate.slice_data.get("provenance", {})
    item: dict[str, Any] = {"source": candidate.source}
    for key in ["input_id", "rumor_claim_id", "note_path", "path", "object_id", "id"]:
        if provenance.get(key):
            item[key] = provenance[key]
    item["reason"] = reason
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


def _dedupe_exclusions(exclusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in exclusions:
        key = (
            item.get("source"),
            item.get("input_id")
            or item.get("rumor_claim_id")
            or item.get("note_path")
            or item.get("path")
            or item.get("object_id")
            or item.get("id"),
            item.get("reason"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _count_by(candidates: list[ContextCandidate], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        key = str(getattr(candidate, attribute))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _normalize_sensitivity(value: str) -> str | None:
    rank = SENSITIVITY_RANK.get(value.strip().lower())
    if rank is None:
        return None
    return SENSITIVITY_LEVELS[rank]


def _sensitivity_rank(value: str) -> int:
    return SENSITIVITY_RANK[value.lower()]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
