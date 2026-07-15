from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .assembler import BundleAssembler
from .config import LifemeshConfig
from .context_types import ContextCandidate, RetrievalResult
from .database import LifeMeshDatabase

SENSITIVITY_LEVELS = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
SENSITIVITY_RANK = {name.lower(): index for index, name in enumerate(SENSITIVITY_LEVELS)}

CLAIM_TYPES = {
    "factual_claim",
    "relationship_claim",
    "intent_or_plan_claim",
    "risk_claim",
    "preference_claim",
    "unknown_claim",
}
USER_RELEVANCE_LEVELS = ["none", "low", "medium", "high"]
USER_RELEVANCE_RANK = {name: index for index, name in enumerate(USER_RELEVANCE_LEVELS)}
IMPACT_LEVELS = ["low", "medium", "high", "critical"]
IMPACT_RANK = {name: index for index, name in enumerate(IMPACT_LEVELS)}
EXTRACTION_CONFIDENCE_LEVELS = {"low", "medium", "high"}
EVIDENCE_STATES = {"unknown", "single_source", "corroborated", "contradicted"}
CLAIM_QUALITIES = {"vague", "specific", "verifiable"}
ASSESSMENTS = {"unverified", "weak", "plausible", "supported", "contradicted"}
RUMOR_STATUSES = {"parked", "reviewed_parked", "candidate_created", "dismissed", "expired"}
DEFAULT_LIST_STATUSES = {"parked", "candidate_created"}
BUNDLE_ELIGIBLE_STATUSES = {"parked", "reviewed_parked"}
REVIEW_QUEUES = {"general_review", "conflict_review", "sensitive_review"}
RAW_RETENTION_VALUES = {"none", "temporary", "user_saved"}
CANDIDATE_TYPES = {"fact", "preference", "relationship", "task", "decision"}
SOURCE = "rumor"


class RumorClaimError(RuntimeError):
    pass


class RumorClaimStore:
    def __init__(self, config: LifemeshConfig) -> None:
        self.config = config

    def add(
        self,
        *,
        claim_text: str,
        claim_type: str,
        entity_mentions: list[str] | None = None,
        relation_mentions: list[str] | None = None,
        user_relevance: str = "none",
        relevance_reason: str = "",
        impact: str = "low",
        impact_reason: str = "",
        extraction_confidence: str = "medium",
        evidence_state: str = "unknown",
        claim_quality: str = "specific",
        assessment: str | None = None,
        sensitivity: str = "Private",
        review_queue: str | None = None,
        source_adapter: str = "manual_cli",
        source_item_id: str | None = None,
        material_fingerprint: str | None = None,
        source_summary: str | None = None,
        raw_retention: str = "none",
        review_pointer: str | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        claim_text = _require_text(claim_text, "claim text")
        claim_type = _require_choice(claim_type, CLAIM_TYPES, "claim type")
        user_relevance = _require_choice(user_relevance, set(USER_RELEVANCE_LEVELS), "user relevance")
        impact = _require_choice(impact, set(IMPACT_LEVELS), "impact")
        extraction_confidence = _require_choice(
            extraction_confidence,
            EXTRACTION_CONFIDENCE_LEVELS,
            "extraction confidence",
        )
        evidence_state = _require_choice(evidence_state, EVIDENCE_STATES, "evidence state")
        claim_quality = _require_choice(claim_quality, CLAIM_QUALITIES, "claim quality")
        normalized_sensitivity = _require_sensitivity(sensitivity)
        raw_retention = _require_choice(raw_retention, RAW_RETENTION_VALUES, "raw retention")
        derived_assessment = _resolve_assessment(
            assessment,
            extraction_confidence,
            evidence_state,
            claim_quality,
        )
        review_queue = review_queue or _default_review_queue(normalized_sensitivity, evidence_state, derived_assessment)
        review_queue = _require_choice(review_queue, REVIEW_QUEUES, "review queue")
        if not _passes_persistence_gate(user_relevance, impact):
            raise RumorClaimError("RumorClaim did not meet persistence gate: user_relevance >= medium OR impact >= high")

        now = _utc_now()
        normalized_expires_at = _normalize_expires_at(expires_at) or _default_expiry(now, user_relevance, impact)
        rumor_claim_id = _new_id("rc")
        source_envelope = {
            "source_adapter": _require_text(source_adapter, "source adapter"),
            "source_item_id": source_item_id,
            "captured_at": now,
            "material_fingerprint": material_fingerprint,
            "source_summary": source_summary,
            "raw_retention": raw_retention,
            "processing_run_id": _new_id("run"),
            "review_pointer": review_pointer,
        }
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO rumor_claims (
                    rumor_claim_id, claim_text, claim_type, user_relevance, relevance_reason,
                    impact, impact_reason, extraction_confidence, evidence_state, claim_quality,
                    assessment, status, review_queue, sensitivity, source_envelope_json,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rumor_claim_id,
                    claim_text,
                    claim_type,
                    user_relevance,
                    relevance_reason,
                    impact,
                    impact_reason,
                    extraction_confidence,
                    evidence_state,
                    claim_quality,
                    derived_assessment,
                    "parked",
                    review_queue,
                    normalized_sensitivity,
                    json.dumps(source_envelope, ensure_ascii=False, sort_keys=True),
                    normalized_expires_at,
                    now,
                    now,
                ),
            )
            self._replace_mentions(con, rumor_claim_id, entity_mentions or [], relation_mentions or [])
            self._audit(
                con,
                rumor_claim_id,
                "add",
                {
                    "claim_type": claim_type,
                    "assessment": derived_assessment,
                    "review_queue": review_queue,
                    "source_adapter": source_envelope["source_adapter"],
                },
            )
        return self.show(rumor_claim_id)

    def list_claims(
        self,
        *,
        status: str | None = None,
        queue: str | None = None,
        sensitivity_cap: str = "Private",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if status is not None:
            status = _require_choice(status, RUMOR_STATUSES, "status")
        if queue is not None:
            queue = _require_choice(queue, REVIEW_QUEUES, "review queue")
        normalized_cap = _require_sensitivity(sensitivity_cap)
        if limit < 1:
            raise RumorClaimError("--limit must be at least 1")
        query = "SELECT * FROM rumor_claims WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        else:
            query += _status_in_clause(DEFAULT_LIST_STATUSES)
        if queue:
            query += " AND review_queue = ?"
            params.append(queue)
        query += " AND sensitivity_rank(sensitivity) <= sensitivity_rank(?)"
        params.append(normalized_cap)
        query += " ORDER BY created_at DESC, rumor_claim_id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as con:
            con.create_function("sensitivity_rank", 1, _sensitivity_rank)
            return [_summarize_claim(_row_to_claim(row)) for row in con.execute(query, params).fetchall()]

    def show(self, rumor_claim_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM rumor_claims WHERE rumor_claim_id = ?", (rumor_claim_id,)).fetchone()
            if row is None:
                raise RumorClaimError(f"RumorClaim not found: {rumor_claim_id}")
            claim = _row_to_claim(row)
            claim["entity_mentions"] = self._mentions(con, rumor_claim_id, "entity")
            claim["relation_mentions"] = self._mentions(con, rumor_claim_id, "relation")
            claim["candidate_links"] = []
            if _table_exists(con, "rumor_candidate_links"):
                claim["candidate_links"] = [
                    _decode_candidate_link(dict(item))
                    for item in con.execute(
                        "SELECT * FROM rumor_candidate_links WHERE rumor_claim_id = ? ORDER BY created_at",
                        (rumor_claim_id,),
                    ).fetchall()
                ]
            if _has_unified_schema(con):
                claim["candidate_links"].extend(
                    {
                        "object_id": item["candidate_id"],
                        "target_type": "candidate",
                        "target_payload": {
                            "statement": item["summary"],
                            "type": item["type"],
                            "confidence": item["confidence"],
                            "risk": item["risk"],
                        },
                        "rumor_claim_id": rumor_claim_id,
                        "created_at": item["created_at"],
                    }
                    for item in con.execute(
                        """
                        SELECT DISTINCT c.*
                        FROM knowledge_candidates c
                        JOIN candidate_source_links l ON l.candidate_id = c.candidate_id
                        JOIN source_references s ON s.source_ref_id = l.source_ref_id
                        WHERE s.source_kind = 'rumor_claim' AND s.source_item_id = ?
                          AND l.relationship = 'derived_from'
                        """,
                        (rumor_claim_id,),
                    ).fetchall()
                )
            claim["audit_events"] = [
                _decode_audit(dict(item))
                for item in con.execute(
                    "SELECT * FROM rumor_audit_events WHERE rumor_claim_id = ? ORDER BY event_id",
                    (rumor_claim_id,),
                ).fetchall()
            ]
        return claim

    def dismiss(self, rumor_claim_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._set_terminal_status(rumor_claim_id, "dismissed", reason or "dismissed")

    def expire(self, rumor_claim_id: str) -> dict[str, Any]:
        return self._set_terminal_status(rumor_claim_id, "expired", "expired")

    def keep(self, rumor_claim_id: str, *, reason: str | None = None) -> dict[str, Any]:
        now = _utc_now()
        review_reason = reason or "reviewed and kept parked"
        with self._connect() as con:
            claim = _row_to_claim(self._require_existing(con, rumor_claim_id))
            if claim["status"] in {"candidate_created", "dismissed", "expired"}:
                raise RumorClaimError(f"Cannot keep {claim['status']} RumorClaim: {rumor_claim_id}")
            con.execute(
                "UPDATE rumor_claims SET status = 'reviewed_parked', updated_at = ? WHERE rumor_claim_id = ?",
                (now, rumor_claim_id),
            )
            self._audit(
                con,
                rumor_claim_id,
                "keep",
                {"status": "reviewed_parked", "reason": review_reason},
            )
        return self.show(rumor_claim_id)

    def promote(self, rumor_claim_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_candidate_payload(payload)
        if LifeMeshDatabase(self.config).status()["schema_status"] == "current":
            from .knowledge_workflow import KnowledgeWorkflow

            candidate = KnowledgeWorkflow(self.config).handoff_rumor_claim(rumor_claim_id, payload)
            return {
                "object_id": candidate["candidate_id"],
                "target_type": "candidate",
                "derived_from_rumor_claim_id": rumor_claim_id,
                "candidate": candidate,
                "rumor_claim": self.show(rumor_claim_id),
            }
        object_id = _new_id("candidate")
        now = _utc_now()
        with self._connect() as con:
            claim = _row_to_claim(self._require_existing(con, rumor_claim_id))
            if claim["status"] in {"dismissed", "expired"}:
                raise RumorClaimError(f"Cannot promote {claim['status']} RumorClaim: {rumor_claim_id}")
            con.execute(
                """
                INSERT INTO rumor_candidate_links (
                    object_id, target_payload_json, rumor_claim_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (object_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), rumor_claim_id, now),
            )
            con.execute(
                "UPDATE rumor_claims SET status = 'candidate_created', updated_at = ? WHERE rumor_claim_id = ?",
                (now, rumor_claim_id),
            )
            self._audit(
                con,
                rumor_claim_id,
                "promote",
                {"object_id": object_id, "target_type": "candidate", "payload": payload},
            )
        return {
            "object_id": object_id,
            "target_type": "candidate",
            "derived_from_rumor_claim_id": rumor_claim_id,
            "rumor_claim": self.show(rumor_claim_id),
        }

    def bundle(self, *, task: str, max_slices: int, sensitivity_cap: str) -> dict[str, Any]:
        result = self.retrieve_candidates(
            task=task,
            max_candidates=max(max_slices * 4, 20),
            sensitivity_cap=sensitivity_cap,
        )
        return BundleAssembler().assemble(
            task=task,
            allowed_sources=[SOURCE],
            sensitivity_cap=sensitivity_cap,
            max_slices=max_slices,
            candidates=result.candidates,
            excluded_sources=result.excluded_sources,
            freshness_report=result.freshness_report,
            include_unverified=True,
        )

    def retrieve_candidates(self, *, task: str, max_candidates: int, sensitivity_cap: str) -> RetrievalResult:
        if max_candidates < 1:
            raise RumorClaimError("--max-slices must be at least 1")
        normalized_cap = _require_sensitivity(sensitivity_cap)
        terms = _query_terms(task)
        candidates: list[ContextCandidate] = []
        excluded: list[dict[str, Any]] = []
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM rumor_claims WHERE {_status_condition(BUNDLE_ELIGIBLE_STATUSES)} ORDER BY created_at DESC"
            ).fetchall()
            scored: list[tuple[float, dict[str, Any]]] = []
            for row in rows:
                claim = _row_to_claim(row)
                claim["entity_mentions"] = self._mentions(con, claim["rumor_claim_id"], "entity")
                claim["relation_mentions"] = self._mentions(con, claim["rumor_claim_id"], "relation")
                score = _score_claim(claim, terms)
                if score <= 0:
                    continue
                if _sensitivity_rank(claim["sensitivity"]) > _sensitivity_rank(normalized_cap):
                    excluded.append(_rumor_exclusion(claim, "sensitivity_cap_exceeded"))
                    continue
                if _is_expired(claim["expires_at"]):
                    excluded.append(_rumor_exclusion(claim, "expired"))
                    continue
                if claim["assessment"] == "contradicted" or claim["evidence_state"] == "contradicted":
                    excluded.append(_rumor_exclusion(claim, "contradicted_unverified"))
                    continue
                scored.append((score, claim))
            scored.sort(key=lambda item: (-item[0], item[1]["expires_at"], item[1]["rumor_claim_id"]))
            for index, (score, claim) in enumerate(scored[:max_candidates], start=1):
                slice_data = _claim_to_slice(claim, index, score)
                candidates.append(
                    ContextCandidate(
                        slice_data=slice_data,
                        source=SOURCE,
                        layer="rumor",
                        evidence_role="lead",
                        source_rank=index,
                        source_score=score,
                        citation_status="current",
                        sensitivity=claim["sensitivity"],
                        retrieval_mode="term",
                    )
                )
        return RetrievalResult(
            candidates=candidates,
            excluded_sources=excluded,
            freshness_report=[],
            diagnostics={"candidate_count": len(candidates), "source": SOURCE},
        )

    def _connect(self) -> sqlite3.Connection:
        database = LifeMeshDatabase(self.config)
        database.ensure_current_for_write()
        _ensure_private_dir(self.config.home)
        con = database.connect()
        _create_schema(con)
        _chmod_file(self.config.db_path, 0o600)
        return con

    def _replace_mentions(
        self,
        con: sqlite3.Connection,
        rumor_claim_id: str,
        entity_mentions: list[str],
        relation_mentions: list[str],
    ) -> None:
        con.execute("DELETE FROM rumor_mentions WHERE rumor_claim_id = ?", (rumor_claim_id,))
        rows = [
            (rumor_claim_id, "entity", _require_text(value, "entity mention"), index)
            for index, value in enumerate(entity_mentions)
        ]
        rows.extend(
            (rumor_claim_id, "relation", _require_text(value, "relation mention"), index)
            for index, value in enumerate(relation_mentions)
        )
        con.executemany(
            "INSERT INTO rumor_mentions(rumor_claim_id, mention_type, value, position) VALUES (?, ?, ?, ?)",
            rows,
        )

    def _mentions(self, con: sqlite3.Connection, rumor_claim_id: str, mention_type: str) -> list[str]:
        rows = con.execute(
            """
            SELECT value
            FROM rumor_mentions
            WHERE rumor_claim_id = ? AND mention_type = ?
            ORDER BY position
            """,
            (rumor_claim_id, mention_type),
        ).fetchall()
        return [str(row["value"]) for row in rows]

    def _set_terminal_status(self, rumor_claim_id: str, status: str, reason: str) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as con:
            claim = _row_to_claim(self._require_existing(con, rumor_claim_id))
            if claim["status"] == "candidate_created":
                raise RumorClaimError(f"Cannot {status} candidate_created RumorClaim: {rumor_claim_id}")
            con.execute(
                "UPDATE rumor_claims SET status = ?, tombstone_reason = ?, updated_at = ? WHERE rumor_claim_id = ?",
                (status, reason, now, rumor_claim_id),
            )
            self._audit(con, rumor_claim_id, status, {"status": status, "reason": reason})
        return self.show(rumor_claim_id)

    def _require_existing(self, con: sqlite3.Connection, rumor_claim_id: str) -> sqlite3.Row:
        row = con.execute("SELECT * FROM rumor_claims WHERE rumor_claim_id = ?", (rumor_claim_id,)).fetchone()
        if row is None:
            raise RumorClaimError(f"RumorClaim not found: {rumor_claim_id}")
        return row

    def _audit(self, con: sqlite3.Connection, rumor_claim_id: str, action: str, payload: dict[str, Any]) -> None:
        con.execute(
            "INSERT INTO rumor_audit_events(rumor_claim_id, action, event_at, payload_json) VALUES (?, ?, ?, ?)",
            (rumor_claim_id, action, _utc_now(), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS rumor_claims (
            rumor_claim_id TEXT PRIMARY KEY,
            claim_text TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            user_relevance TEXT NOT NULL,
            relevance_reason TEXT NOT NULL,
            impact TEXT NOT NULL,
            impact_reason TEXT NOT NULL,
            extraction_confidence TEXT NOT NULL,
            evidence_state TEXT NOT NULL,
            claim_quality TEXT NOT NULL,
            assessment TEXT NOT NULL,
            status TEXT NOT NULL,
            review_queue TEXT NOT NULL,
            sensitivity TEXT NOT NULL,
            source_envelope_json TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tombstone_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS rumor_mentions (
            mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rumor_claim_id TEXT NOT NULL,
            mention_type TEXT NOT NULL,
            value TEXT NOT NULL,
            position INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rumor_audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rumor_claim_id TEXT NOT NULL,
            action TEXT NOT NULL,
            event_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        """
    )
    if not _has_unified_schema(con):
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS rumor_candidate_links (
                object_id TEXT PRIMARY KEY,
                target_payload_json TEXT NOT NULL,
                rumor_claim_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _has_unified_schema(con: sqlite3.Connection) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone() is not None


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _claim_to_slice(claim: dict[str, Any], index: int, score: float) -> dict[str, Any]:
    citation = _rumor_citation(claim)
    return {
        "slice_id": f"rumor{index}",
        "evidence_role": "lead",
        "provenance": {
            "source": SOURCE,
            "rumor_claim_id": claim["rumor_claim_id"],
            "status": claim["status"],
            "source_adapter": claim["source_envelope"].get("source_adapter"),
        },
        "citation_status": "current",
        "citation": citation,
        "sensitivity": claim["sensitivity"],
        "content": claim["claim_text"],
        "claim_type": claim["claim_type"],
        "entity_mentions": claim.get("entity_mentions", []),
        "relation_mentions": claim.get("relation_mentions", []),
        "rumor": {
            "user_relevance": claim["user_relevance"],
            "impact": claim["impact"],
            "extraction_confidence": claim["extraction_confidence"],
            "evidence_state": claim["evidence_state"],
            "claim_quality": claim["claim_quality"],
            "assessment": claim["assessment"],
            "review_queue": claim["review_queue"],
            "expires_at": claim["expires_at"],
            "note": "未验证流言线索，不能支撑事实回答。",
        },
        "score": score,
        "retrieval": {
            "match_status": "unverified",
            "match_reason": "rumor_term_match",
            "evidence_eligible": False,
            "note": "RumorClaim 仅作为未验证 lead，不能支撑事实回答。",
        },
    }


def _rumor_citation(claim: dict[str, Any]) -> dict[str, Any]:
    label = (
        f"RumorClaim {claim['rumor_claim_id']} · {claim['claim_type']} · "
        f"{claim['assessment']} · citation_status: current"
    )
    return {
        "format": "rumor-claim-v1",
        "source": SOURCE,
        "rumor_claim_id": claim["rumor_claim_id"],
        "claim_type": claim["claim_type"],
        "assessment": claim["assessment"],
        "status": claim["status"],
        "citation_status": "current",
        "label": label,
    }


def _rumor_exclusion(claim: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"source": SOURCE, "rumor_claim_id": claim["rumor_claim_id"], "reason": reason}


def _status_in_clause(statuses: set[str]) -> str:
    return f" AND {_status_condition(statuses)}"


def _status_condition(statuses: set[str]) -> str:
    quoted = ", ".join(f"'{status}'" for status in sorted(statuses))
    return f"status IN ({quoted})"


def _row_to_claim(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise RumorClaimError("Expected database row")
    claim = dict(row)
    claim["source_envelope"] = json.loads(claim.pop("source_envelope_json") or "{}")
    return claim


def _summarize_claim(claim: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "rumor_claim_id",
        "claim_text",
        "claim_type",
        "user_relevance",
        "impact",
        "assessment",
        "status",
        "review_queue",
        "sensitivity",
        "expires_at",
        "created_at",
    ]
    return {key: claim.get(key) for key in keys}


def _decode_candidate_link(row: dict[str, Any]) -> dict[str, Any]:
    row["target_payload"] = json.loads(row.pop("target_payload_json") or "{}")
    row["target_type"] = "candidate"
    return row


def _decode_audit(row: dict[str, Any]) -> dict[str, Any]:
    row["payload"] = json.loads(row.pop("payload_json") or "{}")
    return row


def _validate_candidate_payload(payload: dict[str, Any]) -> None:
    missing = [key for key in ["statement", "type"] if not str(payload.get(key, "")).strip()]
    if missing:
        raise RumorClaimError(f"rumor promote --to candidate requires: {', '.join(missing)}")
    if str(payload.get("type")) not in CANDIDATE_TYPES:
        allowed = ", ".join(sorted(CANDIDATE_TYPES))
        raise RumorClaimError(f"rumor promote --to candidate --type must be one of: {allowed}")


def _resolve_assessment(
    supplied: str | None,
    extraction_confidence: str,
    evidence_state: str,
    claim_quality: str,
) -> str:
    if supplied is None:
        return _derive_assessment(extraction_confidence, evidence_state, claim_quality)
    normalized = _require_choice(supplied, ASSESSMENTS, "assessment")
    if evidence_state == "contradicted" and normalized != "contradicted":
        raise RumorClaimError("contradicted evidence must use assessment=contradicted")
    if (extraction_confidence == "low" or claim_quality == "vague") and normalized in {"plausible", "supported"}:
        raise RumorClaimError("low-confidence or vague claims cannot use assessment=plausible/supported")
    return normalized


def _derive_assessment(extraction_confidence: str, evidence_state: str, claim_quality: str) -> str:
    if evidence_state == "contradicted":
        return "contradicted"
    if extraction_confidence == "low" or claim_quality == "vague":
        return "weak"
    if evidence_state == "corroborated":
        return "supported"
    if evidence_state == "single_source" and claim_quality in {"specific", "verifiable"}:
        return "plausible"
    return "unverified"


def _default_review_queue(sensitivity: str, evidence_state: str, assessment: str) -> str:
    if _sensitivity_rank(sensitivity) >= _sensitivity_rank("Sensitive"):
        return "sensitive_review"
    if evidence_state == "contradicted" or assessment == "contradicted":
        return "conflict_review"
    return "general_review"


def _passes_persistence_gate(user_relevance: str, impact: str) -> bool:
    return USER_RELEVANCE_RANK[user_relevance] >= USER_RELEVANCE_RANK["medium"] or IMPACT_RANK[impact] >= IMPACT_RANK["high"]


def _default_expiry(created_at: str, user_relevance: str, impact: str) -> str:
    start = _parse_datetime(created_at) or datetime.now(timezone.utc)
    days = 180 if user_relevance == "high" or IMPACT_RANK[impact] >= IMPACT_RANK["high"] else 60
    return (start + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _normalize_expires_at(value: str | None) -> str | None:
    if value is None:
        return None
    dt = _parse_datetime(value)
    if dt is None:
        raise RumorClaimError("--expires-at must be ISO-8601")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_expired(value: Any) -> bool:
    dt = _parse_datetime(value)
    return dt is not None and dt <= datetime.now(timezone.utc)


def _score_claim(claim: dict[str, Any], terms: list[str]) -> float:
    if not terms:
        return 0.0
    haystack = " ".join(
        [
            claim["claim_text"],
            claim["claim_type"],
            claim["user_relevance"],
            claim["impact"],
            claim["assessment"],
            claim.get("relevance_reason") or "",
            claim.get("impact_reason") or "",
            " ".join(str(item) for item in claim.get("entity_mentions", [])),
            " ".join(str(item) for item in claim.get("relation_mentions", [])),
        ]
    ).lower()
    matched = [term for term in terms if term in haystack]
    if not matched:
        return 0.0
    return len(set(matched)) * 10 + sum(min(haystack.count(term), 2) for term in matched)


def _query_terms(task: str) -> list[str]:
    return sorted({token.lower() for token in task.split() if token.strip()}, key=len, reverse=True)


def _require_choice(value: str, allowed: set[str], label: str) -> str:
    normalized = value.strip()
    if normalized not in allowed:
        raise RumorClaimError(f"Unknown {label}: {value}")
    return normalized


def _require_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise RumorClaimError(f"{label} is required")
    return text


def _require_sensitivity(value: str) -> str:
    rank = SENSITIVITY_RANK.get(value.strip().lower())
    if rank is None:
        raise RumorClaimError(f"Unknown sensitivity: {value}")
    return SENSITIVITY_LEVELS[rank]


def _sensitivity_rank(value: str) -> int:
    return SENSITIVITY_RANK[str(value).lower()]


def _parse_datetime(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _chmod_file(path: Path, mode: int) -> None:
    if path.exists():
        os.chmod(path, mode)


def material_fingerprint(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
