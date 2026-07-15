from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import LifemeshConfig
from .context_types import ContextCandidate, RetrievalResult
from .database import LifeMeshDatabase


class CanonicalStoreError(RuntimeError):
    pass


class CanonicalStore:
    def __init__(self, config: LifemeshConfig, *, read_only: bool = False) -> None:
        self.database = LifeMeshDatabase(config)
        self.read_only = read_only

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            return self.database.connect_read_only()
        return self.database.connect()

    def show_object(self, object_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM canonical_objects WHERE object_id = ?",
                (object_id,),
            ).fetchone()
            if row is None:
                raise CanonicalStoreError(f"Canonical object not found: {object_id}")
            object_type = str(row["object_type"])
            if object_type == "fact":
                result = self._fact(con, row)
            elif object_type == "memory":
                result = self._memory(con, row)
            elif object_type == "task":
                result = self._task(con, row)
            elif object_type == "event":
                result = self._event(con, row)
            else:
                raise CanonicalStoreError(f"Unsupported canonical object type: {object_type}")
            result["acceptance"] = self._acceptance(con, object_id)
            result["source_links"] = self._source_links(con, object_id)
            result["review_items"] = [
                dict(item)
                for item in con.execute(
                    "SELECT * FROM review_items WHERE object_id = ? ORDER BY opened_at, review_id",
                    (object_id,),
                ).fetchall()
            ]
            result["tombstones"] = [
                dict(item)
                for item in con.execute(
                    "SELECT * FROM object_tombstones WHERE object_id = ? ORDER BY created_at, tombstone_id",
                    (object_id,),
                ).fetchall()
            ]
            return result

    def show_fact(self, fact_id: str) -> dict[str, Any]:
        result = self.show_object(fact_id)
        if result["object_type"] != "fact":
            raise CanonicalStoreError(f"Canonical object is not a Fact: {fact_id}")
        return result

    def show_typed(self, object_id: str, expected_type: str) -> dict[str, Any]:
        result = self.show_object(object_id)
        if result["object_type"] != expected_type:
            raise CanonicalStoreError(
                f"Canonical object is not a {expected_type}: {object_id}"
            )
        return result

    def list_objects(self, object_type: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if object_type not in {"fact", "memory", "task", "event"}:
            raise CanonicalStoreError(f"Unsupported canonical object type: {object_type}")
        if limit < 1:
            raise CanonicalStoreError("--limit must be at least 1")
        table, id_column = {
            "fact": ("canonical_facts", "fact_id"),
            "memory": ("memories", "memory_id"),
            "task": ("tasks", "task_id"),
            "event": ("events", "event_id"),
        }[object_type]
        with self._connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    f"""
                    SELECT o.*, t.*
                    FROM canonical_objects o
                    JOIN {table} t ON t.{id_column} = o.object_id
                    WHERE o.object_type = ?
                    ORDER BY o.created_at DESC, o.object_id DESC
                    LIMIT ?
                    """,
                    (object_type, limit),
                ).fetchall()
            ]

    def list_all_objects(self, *, limit: int = 80) -> list[dict[str, Any]]:
        if limit < 1:
            raise CanonicalStoreError("limit must be at least 1")
        with self._connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    """
                    SELECT
                        o.object_id,
                        o.object_type,
                        o.sensitivity,
                        o.created_at,
                        o.updated_at,
                        CASE o.object_type
                            WHEN 'fact' THEN f.statement
                            WHEN 'memory' THEN m.text
                            WHEN 'task' THEN t.title
                            WHEN 'event' THEN e.title
                        END AS title,
                        CASE o.object_type
                            WHEN 'fact' THEN f.review_reason
                            WHEN 'memory' THEN m.scope
                            WHEN 'task' THEN t.description
                            WHEN 'event' THEN e.starts_at
                        END AS excerpt,
                        CASE o.object_type
                            WHEN 'fact' THEN f.validity
                            WHEN 'memory' THEN m.status
                            WHEN 'task' THEN t.task_status
                            WHEN 'event' THEN e.event_status
                        END AS status,
                        f.risk,
                        m.memory_type
                    FROM canonical_objects o
                    LEFT JOIN canonical_facts f ON f.fact_id = o.object_id
                    LEFT JOIN memories m ON m.memory_id = o.object_id
                    LEFT JOIN tasks t ON t.task_id = o.object_id
                    LEFT JOIN events e ON e.event_id = o.object_id
                    ORDER BY o.updated_at DESC, o.object_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]

    def list_reviews(self, *, status: str = "open", limit: int = 20) -> list[dict[str, Any]]:
        if status not in {"open", "resolved", "dismissed"}:
            raise CanonicalStoreError("review status must be open, resolved, or dismissed")
        with self._connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM review_items WHERE status = ? ORDER BY opened_at, review_id LIMIT ?",
                    (status, limit),
                ).fetchall()
            ]

    def list_review_contexts(self, *, status: str = "open", limit: int = 80) -> list[dict[str, Any]]:
        if status not in {"open", "resolved", "dismissed"}:
            raise CanonicalStoreError("review status must be open, resolved, or dismissed")
        if limit < 1:
            raise CanonicalStoreError("limit must be at least 1")
        with self._connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    """
                    SELECT
                        r.*,
                        COALESCE(o.sensitivity, c.sensitivity, 'Unclassified') AS sensitivity,
                        CASE
                            WHEN r.object_id IS NOT NULL THEN o.object_type
                            ELSE 'candidate:' || COALESCE(c.type, 'unknown')
                        END AS target_type,
                        COALESCE(f.statement, m.text, t.title, e.title, c.summary, r.object_id, r.candidate_id) AS target_title,
                        s.citation_label AS trigger_citation_label,
                        s.status AS trigger_source_status
                    FROM review_items r
                    LEFT JOIN canonical_objects o ON o.object_id = r.object_id
                    LEFT JOIN canonical_facts f ON f.fact_id = o.object_id
                    LEFT JOIN memories m ON m.memory_id = o.object_id
                    LEFT JOIN tasks t ON t.task_id = o.object_id
                    LEFT JOIN events e ON e.event_id = o.object_id
                    LEFT JOIN knowledge_candidates c ON c.candidate_id = r.candidate_id
                    JOIN source_references s ON s.source_ref_id = r.trigger_source_ref_id
                    WHERE r.status = ?
                    ORDER BY r.opened_at, r.review_id
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            ]

    def show_review(self, review_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM review_items WHERE review_id = ?", (review_id,)).fetchone()
            if row is None:
                raise CanonicalStoreError(f"Review not found: {review_id}")
            return dict(row)

    def list_fact_reviews(self, *, status: str = "open", limit: int = 20) -> list[dict[str, Any]]:
        if status not in {"open", "resolved", "dismissed"}:
            raise CanonicalStoreError("review status must be open, resolved, or dismissed")
        with self._connect() as con:
            return [
                dict(row)
                for row in con.execute(
                    """
                    SELECT r.*
                    FROM review_items r
                    JOIN canonical_objects o ON o.object_id = r.object_id
                    WHERE o.object_type = 'fact' AND r.status = ?
                    ORDER BY r.opened_at, r.review_id
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            ]

    def retrieve_candidates(
        self,
        *,
        task: str,
        max_candidates: int,
        sensitivity_cap: str,
    ) -> RetrievalResult:
        levels = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
        if sensitivity_cap not in levels:
            raise CanonicalStoreError(f"Unknown sensitivity cap: {sensitivity_cap}")
        allowed = set(levels[: levels.index(sensitivity_cap) + 1])
        terms = [term.lower() for term in task.replace("/", " ").split() if term.strip()]
        candidates: list[ContextCandidate] = []
        excluded: list[dict[str, Any]] = []
        with self._connect() as con:
            facts = con.execute(
                """
                SELECT o.*, f.*
                FROM canonical_objects o
                JOIN canonical_facts f ON f.fact_id = o.object_id
                ORDER BY o.created_at DESC
                """
            ).fetchall()
            for row in facts:
                if row["sensitivity"] not in allowed:
                    excluded.append({"source": "canonical", "object_id": row["object_id"], "reason": "sensitivity_cap_exceeded"})
                    continue
                if row["validity"] != "valid" or row["revocation_status"] != "active":
                    excluded.append({"source": "canonical", "object_id": row["object_id"], "reason": str(row["validity"])})
                    continue
                if not self._has_current_fact_support(con, str(row["object_id"])):
                    excluded.append({"source": "canonical", "object_id": row["object_id"], "reason": "support_not_current"})
                    continue
                score = _term_score(str(row["statement"]), terms)
                if score <= 0:
                    continue
                candidates.append(_fact_candidate(dict(row), score, len(candidates) + 1))

            memories = con.execute(
                """
                SELECT o.*, m.*
                FROM canonical_objects o
                JOIN memories m ON m.memory_id = o.object_id
                WHERE m.status = 'active'
                ORDER BY o.created_at DESC
                """
            ).fetchall()
            for row in memories:
                if row["sensitivity"] not in allowed or _is_expired(row["expires_at"]):
                    continue
                score = _term_score(str(row["text"]), terms)
                if score <= 0:
                    continue
                candidates.append(_memory_candidate(dict(row), score, len(candidates) + 1))
        candidates.sort(key=lambda item: (0 if item.layer == "fact" else 1, -(item.source_score or 0)))
        return RetrievalResult(
            candidates=candidates[:max_candidates],
            excluded_sources=excluded,
            diagnostics={"candidate_count": len(candidates), "source": "canonical"},
        )

    def _has_current_fact_support(self, con: sqlite3.Connection, object_id: str) -> bool:
        rows = con.execute(
            """
            SELECT l.required, s.status, s.source_kind
            FROM object_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            WHERE l.object_id = ? AND l.relationship = 'supports'
            """,
            (object_id,),
        ).fetchall()
        current = [row for row in rows if row["status"] == "current" and row["source_kind"] != "opaque"]
        required_invalid = any(
            row["required"]
            and (row["status"] != "current" or row["source_kind"] == "opaque")
            for row in rows
        )
        return bool(current) and not required_invalid

    def _fact(self, con: sqlite3.Connection, base: sqlite3.Row) -> dict[str, Any]:
        row = con.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (base["object_id"],)).fetchone()
        if row is None:
            raise CanonicalStoreError(f"Canonical Fact row missing: {base['object_id']}")
        return {**dict(base), **dict(row)}

    def _memory(self, con: sqlite3.Connection, base: sqlite3.Row) -> dict[str, Any]:
        row = con.execute("SELECT * FROM memories WHERE memory_id = ?", (base["object_id"],)).fetchone()
        if row is None:
            raise CanonicalStoreError(f"Memory row missing: {base['object_id']}")
        return {**dict(base), **dict(row)}

    def _task(self, con: sqlite3.Connection, base: sqlite3.Row) -> dict[str, Any]:
        row = con.execute("SELECT * FROM tasks WHERE task_id = ?", (base["object_id"],)).fetchone()
        if row is None:
            raise CanonicalStoreError(f"Task row missing: {base['object_id']}")
        return {**dict(base), **dict(row)}

    def _event(self, con: sqlite3.Connection, base: sqlite3.Row) -> dict[str, Any]:
        row = con.execute("SELECT * FROM events WHERE event_id = ?", (base["object_id"],)).fetchone()
        if row is None:
            raise CanonicalStoreError(f"Event row missing: {base['object_id']}")
        return {**dict(base), **dict(row)}

    def _acceptance(self, con: sqlite3.Connection, object_id: str) -> dict[str, Any] | None:
        row = con.execute("SELECT * FROM acceptances WHERE object_id = ?", (object_id,)).fetchone()
        return None if row is None else dict(row)

    def _source_links(self, con: sqlite3.Connection, object_id: str) -> list[dict[str, Any]]:
        rows = con.execute(
            """
            SELECT l.*, s.source_kind, s.adapter, s.source_item_id, s.revision_id,
                   s.content_hash, s.citation_label, s.sensitivity AS source_sensitivity,
                   s.status AS source_status, s.identity_key, s.metadata_json
            FROM object_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            WHERE l.object_id = ?
            ORDER BY l.created_at, l.source_ref_id, l.relationship
            """,
            (object_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["required"] = bool(item["required"])
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
        return result


def _term_score(text: str, terms: list[str]) -> float:
    lowered = text.lower()
    if not terms:
        return 1.0
    hits = sum(1 for term in terms if term in lowered)
    return hits / len(terms)


def _fact_candidate(row: dict[str, Any], score: float, rank: int) -> ContextCandidate:
    object_id = str(row["object_id"])
    return ContextCandidate(
        slice_data={
            "slice_id": f"fact-{object_id}",
            "evidence_role": "fact",
            "provenance": {"source": "canonical", "object_id": object_id, "status": "active"},
            "citation_status": "current",
            "citation": {"format": "canonical-fact-v1", "object_id": object_id, "label": f"Canonical Fact {object_id}"},
            "sensitivity": row["sensitivity"],
            "content": row["statement"],
            "confidence": row["confidence"],
            "risk": row["risk"],
        },
        source="canonical",
        layer="fact",
        evidence_role="fact",
        source_rank=rank,
        source_score=score,
        sensitivity=str(row["sensitivity"]),
        retrieval_mode="term",
    )


def _memory_candidate(row: dict[str, Any], score: float, rank: int) -> ContextCandidate:
    object_id = str(row["object_id"])
    return ContextCandidate(
        slice_data={
            "slice_id": f"memory-{object_id}",
            "evidence_role": "context",
            "provenance": {"source": "canonical", "object_id": object_id, "status": "active"},
            "citation_status": "current",
            "citation": {"format": "memory-v1", "object_id": object_id, "label": f"Memory {object_id}"},
            "sensitivity": row["sensitivity"],
            "content": row["text"],
            "scope": row["scope"],
        },
        source="canonical",
        layer="memory",
        evidence_role="context",
        source_rank=rank,
        source_score=score,
        sensitivity=str(row["sensitivity"]),
        retrieval_mode="term",
    )


def _is_expired(value: str | None) -> bool:
    if not value:
        return False
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)
