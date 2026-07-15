from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from .assembler import BundleAssembler
from .candidates import CandidateError, CandidateStore
from .config import LifemeshConfig
from .context_types import ContextCandidate
from .manual_input import ManualInputError, ManualInputStore
from .obsidian import retrieve_candidates as retrieve_obsidian_candidates
from .rumor_claims import RumorClaimError, RumorClaimStore


DOMAINS = {"inputs", "rumors", "candidates"}
SENSITIVITY_LEVELS = ["Public", "Internal", "Private", "Sensitive", "Restricted"]


class ConsoleError(RuntimeError):
    pass


class ConsoleService:
    """Read-side adapter used by the local LifeMesh Console."""

    def __init__(self, config: LifemeshConfig) -> None:
        self.config = config
        self.inputs = ManualInputStore(config)
        self.rumors = RumorClaimStore(config)
        self.candidates = CandidateStore(config)

    def overview(self) -> dict[str, Any]:
        inputs = self.records("inputs", limit=200)
        rumors = self.records("rumors", limit=200)
        candidates = self.records("candidates", limit=200)
        records = [*inputs, *rumors, *candidates]
        recent = sorted(records, key=lambda item: item.get("timestamp") or "", reverse=True)[:8]
        sensitivity = Counter(item.get("sensitivity") or "Unclassified" for item in records)

        return {
            "generated_at": _utc_now(),
            "counts": {
                "total": len(records),
                "inputs": len(inputs),
                "rumors": len(rumors),
                "candidates": len(candidates),
                "sensitive": sensitivity.get("Sensitive", 0) + sensitivity.get("Restricted", 0),
            },
            "queues": {
                "manual_active": sum(item["status"] in {"active", "auto_captured"} for item in inputs),
                "rumor_review": sum(item["status"] in {"parked", "reviewed_parked"} for item in rumors),
                "candidate_review": sum(
                    item["status"] in {"inbox", "confirm_required"} for item in candidates
                ),
            },
            "sensitivity": dict(sensitivity),
            "health": self._health(records),
            "recent": recent,
        }

    def records(self, domain: str, *, limit: int = 80) -> list[dict[str, Any]]:
        domain = _require_domain(domain)
        limit = _bounded_limit(limit)
        try:
            if domain == "inputs":
                raw = self.inputs.list_inputs()[:limit]
            elif domain == "rumors":
                raw = self._all_rumors(limit)
            else:
                raw = self._all_candidates(limit)
        except (CandidateError, ManualInputError, RumorClaimError, sqlite3.Error) as exc:
            raise ConsoleError(str(exc)) from exc
        return [_card(domain, item) for item in raw]

    def record(self, domain: str, record_id: str) -> dict[str, Any]:
        domain = _require_domain(domain)
        if not str(record_id).strip():
            raise ConsoleError("record id is required")
        try:
            if domain == "inputs":
                data = self.inputs.show(record_id)
            elif domain == "rumors":
                data = self.rumors.show(record_id)
            else:
                data = self.candidates.show(record_id)
        except (CandidateError, ManualInputError, RumorClaimError, sqlite3.Error) as exc:
            raise ConsoleError(str(exc)) from exc
        if domain == "inputs":
            data = dict(data)
            data.pop("original_path", None)
            data.pop("stored_path", None)
        return {"card": _card(domain, data), "data": data}

    def search(self, query: str, *, limit: int = 30) -> dict[str, Any]:
        query = str(query).strip()
        if not query:
            return {"query": "", "results": []}
        limit = _bounded_limit(limit, maximum=50)
        results: list[dict[str, Any]] = []

        try:
            hits = self.inputs.search(query, sensitivity_cap="Restricted", limit=limit)
        except (ManualInputError, sqlite3.Error):
            hits = []
        seen_inputs: set[str] = set()
        for hit in hits:
            seen_inputs.add(hit.input_id)
            results.append(
                _card("inputs", hit.record)
                | {
                    "score": round(float(hit.score), 4),
                    "match_reason": hit.match_reason,
                }
            )

        # FTS can be unavailable in a partially initialized local database. Keep a
        # deterministic title fallback while retaining hybrid search when available.
        for item in self.records("inputs", limit=200):
            if item["id"] in seen_inputs:
                continue
            score = _text_score(query, f"{item['title']} {item['excerpt']}")
            if score:
                results.append(item | {"score": score, "match_reason": "title/text match"})

        for domain in ("rumors", "candidates"):
            for item in self.records(domain, limit=200):
                score = _text_score(query, f"{item['title']} {item['excerpt']} {' '.join(item['tags'])}")
                if score:
                    results.append(item | {"score": score, "match_reason": "structured text match"})

        results.sort(key=lambda item: (-float(item.get("score") or 0), item["domain"], item["id"]))
        return {"query": query, "results": results[:limit]}

    def timeline(self, *, limit: int = 120) -> dict[str, Any]:
        items = [
            *self.records("inputs", limit=limit),
            *self.records("rumors", limit=limit),
            *self.records("candidates", limit=limit),
        ]
        items.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return {"items": items[:_bounded_limit(limit, maximum=200)]}

    def graph(self, *, limit: int = 40) -> dict[str, Any]:
        limit = _bounded_limit(limit, maximum=80)
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[tuple[str, str, str], dict[str, str]] = {}

        def add_node(node: dict[str, Any]) -> None:
            nodes.setdefault(node["id"], node)

        def add_edge(source: str, target: str, label: str) -> None:
            edges.setdefault((source, target, label), {"source": source, "target": target, "label": label})

        for card in self.records("inputs", limit=limit):
            node_id = f"input:{card['id']}"
            add_node(_graph_node(node_id, card["title"], "input", card))
            try:
                detail = self.inputs.show(card["id"])
            except (ManualInputError, sqlite3.Error):
                continue
            for tag in detail.get("tags", []):
                tag_id = f"tag:{tag}"
                add_node({"id": tag_id, "label": str(tag), "type": "tag", "status": "current"})
                add_edge(node_id, tag_id, "tagged")
            for derived in detail.get("derived_objects", []):
                object_id = f"object:{derived.get('object_id')}"
                add_node(
                    {
                        "id": object_id,
                        "label": str(derived.get("target_type") or "promoted object"),
                        "type": "object",
                        "status": "current",
                    }
                )
                add_edge(node_id, object_id, "promoted_to")

        for card in self.records("rumors", limit=limit):
            node_id = f"rumor:{card['id']}"
            add_node(_graph_node(node_id, card["title"], "rumor", card))
            try:
                detail = self.rumors.show(card["id"])
            except (RumorClaimError, sqlite3.Error):
                continue
            for entity in detail.get("entity_mentions", []):
                entity_id = f"entity:{entity}"
                add_node({"id": entity_id, "label": str(entity), "type": "entity", "status": "mentioned"})
                add_edge(node_id, entity_id, "mentions")
            for relation in detail.get("relation_mentions", []):
                relation_id = f"relation:{relation}"
                add_node(
                    {"id": relation_id, "label": str(relation), "type": "relation", "status": "unverified"}
                )
                add_edge(node_id, relation_id, "reports")
            for link in detail.get("candidate_links", []):
                object_id = f"object:{link.get('object_id')}"
                add_node(
                    {
                        "id": object_id,
                        "label": str(link.get("target_payload", {}).get("statement") or "candidate link"),
                        "type": "object",
                        "status": "candidate",
                    }
                )
                add_edge(node_id, object_id, "promoted_to")

        for card in self.records("candidates", limit=limit):
            node_id = f"candidate:{card['id']}"
            add_node(_graph_node(node_id, card["title"], "candidate", card))
            try:
                detail = self.candidates.show(card["id"])
            except (CandidateError, sqlite3.Error):
                continue
            for source_ref in detail.get("source_refs", []):
                source_id = f"source:{source_ref}"
                add_node(
                    {"id": source_id, "label": str(source_ref), "type": "source", "status": "referenced"}
                )
                add_edge(node_id, source_id, "sourced_by")

        return {
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "truth_boundary": "Only stored tags, mentions, promotion links, and source references are shown.",
        }

    def assemble_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = str(payload.get("task") or "").strip()
        if not task:
            raise ConsoleError("Bundle task is required")
        sources = payload.get("sources") or ["obsidian", "manual-input"]
        if not isinstance(sources, list):
            raise ConsoleError("sources must be an array")
        source_names = _dedupe(str(source) for source in sources)
        unknown = sorted(set(source_names) - {"obsidian", "manual-input", "rumor"})
        if unknown:
            raise ConsoleError(f"Unknown bundle sources: {', '.join(unknown)}")
        max_slices = int(payload.get("max_slices") or 12)
        if max_slices < 1 or max_slices > 50:
            raise ConsoleError("max_slices must be between 1 and 50")
        include_sensitive = payload.get("include_sensitive") is True
        include_unverified = payload.get("include_unverified") is True
        sensitivity_cap = "Sensitive" if include_sensitive else "Private"
        candidate_limit = max(max_slices * 4, 20)

        candidates: list[ContextCandidate] = []
        excluded: list[dict[str, Any]] = []
        freshness: list[dict[str, Any]] = []
        allowed_sources: list[str] = []

        try:
            if "obsidian" in source_names:
                if self.config.obsidian_vault is None:
                    excluded.append({"source": "obsidian", "reason": "source_not_configured"})
                elif not self.config.obsidian_vault.exists():
                    excluded.append({"source": "obsidian", "reason": "source_missing"})
                else:
                    result = retrieve_obsidian_candidates(
                        task=task,
                        vault_path=self.config.obsidian_vault,
                        max_candidates=candidate_limit,
                        sensitivity_cap=sensitivity_cap,
                    )
                    candidates.extend(result.candidates)
                    excluded.extend(result.excluded_sources)
                    freshness.extend(result.freshness_report)
                    allowed_sources.append("obsidian")

            if "manual-input" in source_names:
                result = self.inputs.retrieve_candidates(
                    task=task,
                    max_candidates=candidate_limit,
                    sensitivity_cap=sensitivity_cap,
                )
                candidates.extend(result.candidates)
                excluded.extend(result.excluded_sources)
                freshness.extend(result.freshness_report)
                allowed_sources.append("manual-input")

            if "rumor" in source_names:
                if not include_unverified:
                    excluded.append({"source": "rumor", "reason": "unverified_not_requested"})
                else:
                    result = self.rumors.retrieve_candidates(
                        task=task,
                        max_candidates=candidate_limit,
                        sensitivity_cap=sensitivity_cap,
                    )
                    candidates.extend(result.candidates)
                    excluded.extend(result.excluded_sources)
                    freshness.extend(result.freshness_report)
                    allowed_sources.append("rumor")
        except (ManualInputError, RumorClaimError, ValueError, OSError, sqlite3.Error) as exc:
            raise ConsoleError(str(exc)) from exc

        return BundleAssembler().assemble(
            task=task,
            allowed_sources=allowed_sources,
            sensitivity_cap=sensitivity_cap,
            max_slices=max_slices,
            candidates=candidates,
            excluded_sources=excluded,
            freshness_report=freshness,
            include_unverified=include_unverified,
        )

    def _all_rumors(self, limit: int) -> list[dict[str, Any]]:
        items: dict[str, dict[str, Any]] = {}
        for status in ("parked", "reviewed_parked", "candidate_created", "dismissed", "expired"):
            for item in self.rumors.list_claims(
                status=status,
                sensitivity_cap="Restricted",
                limit=limit,
            ):
                items[item["rumor_claim_id"]] = item
        return sorted(items.values(), key=lambda item: item.get("created_at") or "", reverse=True)[:limit]

    def _all_candidates(self, limit: int) -> list[dict[str, Any]]:
        items: dict[str, dict[str, Any]] = {}
        for lifecycle in ("inbox", "confirm_required", "discard"):
            for item in self.candidates.list_candidates(lifecycle=lifecycle, limit=limit):
                items[item["candidate_id"]] = item
        return sorted(items.values(), key=lambda item: item.get("created_at") or "", reverse=True)[:limit]

    def _health(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        database_exists = self.config.db_path.exists()
        vector_status = "not configured"
        if database_exists:
            try:
                with sqlite3.connect(f"file:{self.config.db_path}?mode=ro", uri=True) as con:
                    row = con.execute(
                        "SELECT value FROM lifemesh_meta WHERE key = 'vector_status'"
                    ).fetchone()
                    if row:
                        vector_status = str(row[0])
            except sqlite3.Error:
                vector_status = "unknown"
        vault_status = "not configured"
        if self.config.obsidian_vault is not None:
            vault_status = "ready" if self.config.obsidian_vault.is_dir() else "missing"
        model_status = "configured" if self.config.lmstudio_base_url else "optional / offline"
        return [
            {
                "name": "Local database",
                "status": "ready" if database_exists else "empty",
                "detail": f"{len(records)} visible records",
            },
            {"name": "Obsidian source", "status": vault_status, "detail": "read-only adapter"},
            {"name": "Vector index", "status": vector_status, "detail": "hybrid search degrades to FTS"},
            {"name": "Local models", "status": model_status, "detail": "no network probe from Console"},
        ]


def _card(domain: str, item: dict[str, Any]) -> dict[str, Any]:
    if domain == "inputs":
        record_id = item.get("input_id")
        title = item.get("title") or item.get("text") or item.get("kind") or "Untitled input"
        excerpt = item.get("text") or item.get("title") or ""
        status = item.get("status") or "unknown"
        timestamp = item.get("occurred_at") or item.get("created_at")
        tags = [str(tag) for tag in item.get("tags", [])]
        kind = item.get("kind") or "input"
    elif domain == "rumors":
        record_id = item.get("rumor_claim_id")
        title = item.get("claim_text") or "Unverified claim"
        excerpt = item.get("source_envelope", {}).get("source_summary") or item.get("claim_type") or ""
        status = item.get("status") or item.get("assessment") or "unverified"
        timestamp = item.get("created_at")
        tags = [str(value) for value in [item.get("claim_type"), item.get("review_queue")] if value]
        kind = item.get("claim_type") or "rumor"
    else:
        record_id = item.get("candidate_id")
        title = item.get("summary") or "Knowledge candidate"
        excerpt = item.get("why_suggested") or ""
        status = item.get("lifecycle") or "unknown"
        timestamp = item.get("created_at")
        tags = [str(value) for value in [item.get("type"), item.get("risk")] if value]
        kind = item.get("type") or "candidate"

    return {
        "domain": domain,
        "id": str(record_id or ""),
        "title": _single_line(title, 180),
        "excerpt": _single_line(excerpt, 260),
        "status": str(status),
        "kind": str(kind),
        "sensitivity": str(item.get("sensitivity") or ("Unclassified" if domain == "candidates" else "Private")),
        "timestamp": timestamp,
        "tags": tags,
    }


def _graph_node(node_id: str, label: str, node_type: str, card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "status": card.get("status"),
        "sensitivity": card.get("sensitivity"),
        "domain": card.get("domain"),
        "record_id": card.get("id"),
    }


def _require_domain(value: str) -> str:
    domain = str(value).strip()
    if domain not in DOMAINS:
        raise ConsoleError(f"Unknown Console domain: {domain}")
    return domain


def _bounded_limit(value: int, *, maximum: int = 200) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ConsoleError("limit must be an integer") from exc
    if limit < 1:
        raise ConsoleError("limit must be at least 1")
    return min(limit, maximum)


def _single_line(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _text_score(query: str, text: str) -> float:
    normalized_query = query.casefold()
    normalized_text = text.casefold()
    if normalized_query in normalized_text:
        return 2.0 + min(len(normalized_query) / max(len(normalized_text), 1), 0.5)
    terms = [term for term in normalized_query.split() if term]
    if not terms:
        return 0.0
    matches = sum(term in normalized_text for term in terms)
    return round(matches / len(terms), 4) if matches else 0.0


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
