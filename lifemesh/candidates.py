from __future__ import annotations

import json
import hashlib
import math
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LifemeshConfig
from .database import LifeMeshDatabase

CANDIDATE_TYPES = {"fact", "preference", "relationship", "task", "decision"}
CANDIDATE_RISKS = {"low", "medium", "high"}
CANDIDATE_LIFECYCLES = {"transient", "inbox", "confirm_required", "discard"}
LISTABLE_CANDIDATE_LIFECYCLES = {"inbox", "confirm_required", "discard"}
CANDIDATE_STATUSES = {"pending", "deferred", "confirmed", "merged", "discarded", "expired"}
SENSITIVITY_LEVELS = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
DEFAULT_LIFECYCLE = "confirm_required"
DEFAULT_CONFIDENCE = 0.5
DEFAULT_RISK = "medium"
DEFAULT_WHY_SUGGESTED = "Added via candidate CLI."


class CandidateError(RuntimeError):
    pass


class CandidateStore:
    def __init__(self, config: LifemeshConfig) -> None:
        self.config = config

    def add(
        self,
        *,
        summary: str,
        candidate_type: str,
        source_refs: list[str] | None = None,
        confidence: float = DEFAULT_CONFIDENCE,
        risk: str = DEFAULT_RISK,
        why_suggested: str = DEFAULT_WHY_SUGGESTED,
        expires_at: str | None = None,
        sensitivity: str = "Private",
    ) -> dict[str, Any]:
        normalized = {
            "summary": _require_text(summary, "summary"),
            "type": _require_choice(candidate_type, CANDIDATE_TYPES, "type"),
            "source_refs": _clean_source_refs(source_refs or []),
            "confidence": _require_confidence(confidence),
            "risk": _require_choice(risk, CANDIDATE_RISKS, "risk"),
            "why_suggested": _require_text(why_suggested, "why_suggested"),
            "expires_at": _normalize_expires_at(expires_at),
            "sensitivity": _require_choice(sensitivity, set(SENSITIVITY_LEVELS), "sensitivity"),
        }
        candidate_id = _new_id("candidate")
        now = _utc_now()
        with self._connect() as con:
            if _is_unified_schema(con):
                resolved_sources = [
                    _resolve_candidate_source(con, raw_ref, normalized["sensitivity"], now)
                    for raw_ref in normalized["source_refs"]
                ]
                effective_sensitivity = _max_sensitivity(
                    [
                        normalized["sensitivity"],
                        *(str(source["sensitivity"]) for source, _relationship in resolved_sources),
                    ]
                )
                normalized["sensitivity"] = effective_sensitivity
                con.execute(
                    """
                    INSERT INTO knowledge_candidates(
                        candidate_id, type, summary, confidence, confidence_basis,
                        risk, sensitivity, status, confirmation_required,
                        why_suggested, expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'direct_cli', ?, ?, 'pending', 1, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        normalized["type"],
                        normalized["summary"],
                        normalized["confidence"],
                        normalized["risk"],
                        effective_sensitivity,
                        normalized["why_suggested"],
                        normalized["expires_at"],
                        now,
                        now,
                    ),
                )
                for source, relationship in resolved_sources:
                    con.execute(
                        "INSERT INTO candidate_source_links(candidate_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, ?, 0, ?)",
                        (candidate_id, source["source_ref_id"], relationship, now),
                    )
                self._audit_unified(con, candidate_id, "add", normalized)
                return self._show_unified(con, candidate_id)
            con.execute(
                """
                INSERT INTO knowledge_candidates (
                    candidate_id, type, summary, confidence, risk, lifecycle,
                    source_refs_json, why_suggested, created_at, updated_at,
                    expires_at, tombstone_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    candidate_id,
                    normalized["type"],
                    normalized["summary"],
                    normalized["confidence"],
                    normalized["risk"],
                    DEFAULT_LIFECYCLE,
                    json.dumps(normalized["source_refs"], ensure_ascii=False),
                    normalized["why_suggested"],
                    now,
                    now,
                    normalized["expires_at"],
                ),
            )
            self._audit(con, candidate_id, "add", normalized)
        return self.show(candidate_id)

    def list_candidates(
        self,
        *,
        lifecycle: str | None = None,
        status: str | None = None,
        candidate_type: str | None = None,
        sensitivity_cap: str = "Private",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            raise CandidateError("--limit must be at least 1")
        if lifecycle is not None:
            lifecycle = _require_choice(lifecycle, CANDIDATE_LIFECYCLES, "lifecycle")
        if candidate_type is not None:
            candidate_type = _require_choice(candidate_type, CANDIDATE_TYPES, "type")

        with self._connect() as con:
            if _is_unified_schema(con):
                if lifecycle is not None:
                    status = {"inbox": "pending", "confirm_required": "pending", "discard": "discarded"}[lifecycle]
                if status is not None:
                    status = _require_choice(status, CANDIDATE_STATUSES, "status")
                cap = _require_choice(sensitivity_cap, set(SENSITIVITY_LEVELS), "sensitivity cap")
                rows = con.execute(
                    """
                    SELECT * FROM knowledge_candidates
                    WHERE sensitivity IN ({})
                    ORDER BY CASE risk WHEN 'high' THEN 2 WHEN 'medium' THEN 1 ELSE 0 END DESC,
                             confidence DESC, created_at DESC
                    """.format(",".join("?" for _ in _allowed_sensitivities(cap))),
                    _allowed_sensitivities(cap),
                ).fetchall()
                candidates = [_row_to_unified_candidate(con, row) for row in rows]
                visible = [
                    item
                    for item in candidates
                    if (status is None and item["effective_status"] in {"pending", "deferred"})
                    or (status is not None and item["effective_status"] == status)
                ]
                if candidate_type is not None:
                    visible = [item for item in visible if item["type"] == candidate_type]
                return [_summarize_unified_candidate(item) for item in visible[:limit]]

        clauses: list[str] = []
        values: list[Any] = []
        if lifecycle is None:
            clauses.append("lifecycle != 'discard'")
        else:
            clauses.append("lifecycle = ?")
            values.append(lifecycle)
        if candidate_type is not None:
            clauses.append("type = ?")
            values.append(candidate_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT *
                FROM knowledge_candidates
                {where}
                ORDER BY
                  CASE risk WHEN 'high' THEN 2 WHEN 'medium' THEN 1 ELSE 0 END DESC,
                  confidence DESC,
                  created_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [_summarize_candidate(_row_to_candidate(row)) for row in rows]

    def show(self, candidate_id: str) -> dict[str, Any]:
        with self._connect() as con:
            if _is_unified_schema(con):
                return self._show_unified(con, candidate_id)
            candidate = _row_to_candidate(self._require_existing(con, candidate_id))
            candidate["audit_events"] = [
                _decode_audit(dict(row))
                for row in con.execute(
                    "SELECT * FROM candidate_audit_events WHERE candidate_id = ? ORDER BY event_id",
                    (candidate_id,),
                ).fetchall()
            ]
        return candidate

    def discard(self, candidate_id: str, *, reason: str | None = None) -> dict[str, Any]:
        tombstone_reason = reason or "discarded"
        now = _utc_now()
        with self._connect() as con:
            row = self._require_existing(con, candidate_id)
            if _is_unified_schema(con):
                candidate = _row_to_unified_candidate(con, row)
                if candidate["stored_status"] == "discarded":
                    raise CandidateError(f"Candidate already discarded: {candidate_id}")
                if candidate["stored_status"] in {"confirmed", "merged"}:
                    raise CandidateError(f"Cannot discard {candidate['stored_status']} Candidate: {candidate_id}")
                con.execute(
                    "UPDATE knowledge_candidates SET status = 'discarded', resolved_at = ?, updated_at = ? WHERE candidate_id = ?",
                    (now, now, candidate_id),
                )
                con.execute(
                    "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'discard' WHERE candidate_id = ? AND status = 'open'",
                    (now, candidate_id),
                )
                self._decision(con, candidate_id, "discard", reason=tombstone_reason)
                self._audit_unified(con, candidate_id, "discard", {"reason": tombstone_reason})
                return self._show_unified(con, candidate_id)
            candidate = _row_to_candidate(row)
            if candidate["lifecycle"] == "discard":
                raise CandidateError(f"Candidate already discarded: {candidate_id}")
            con.execute(
                """
                UPDATE knowledge_candidates
                SET lifecycle = 'discard', updated_at = ?, tombstone_reason = ?
                WHERE candidate_id = ?
                """,
                (now, tombstone_reason, candidate_id),
            )
            self._audit(con, candidate_id, "discard", {"reason": tombstone_reason})
        return self.show(candidate_id)

    def defer(
        self,
        candidate_id: str,
        *,
        until: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        deferred_until = _normalize_expires_at(until)
        now = _utc_now()
        with self._connect() as con:
            if not _is_unified_schema(con):
                raise CandidateError("candidate defer requires unified database migration")
            candidate = _row_to_unified_candidate(con, self._require_existing(con, candidate_id))
            if candidate["effective_status"] != "pending":
                raise CandidateError(f"Cannot defer {candidate['effective_status']} Candidate: {candidate_id}")
            con.execute(
                "UPDATE knowledge_candidates SET status = 'deferred', deferred_until = ?, updated_at = ? WHERE candidate_id = ?",
                (deferred_until, now, candidate_id),
            )
            self._decision(con, candidate_id, "defer", reason=reason, payload={"until": deferred_until})
            self._audit_unified(con, candidate_id, "defer", {"until": deferred_until, "reason": reason})
            return self._show_unified(con, candidate_id)

    def resume(self, candidate_id: str) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as con:
            if not _is_unified_schema(con):
                raise CandidateError("candidate resume requires unified database migration")
            candidate = _row_to_unified_candidate(con, self._require_existing(con, candidate_id))
            if candidate["stored_status"] != "deferred":
                raise CandidateError(f"Cannot resume {candidate['stored_status']} Candidate: {candidate_id}")
            con.execute(
                "UPDATE knowledge_candidates SET status = 'pending', deferred_until = NULL, updated_at = ? WHERE candidate_id = ?",
                (now, candidate_id),
            )
            self._decision(con, candidate_id, "resume")
            self._audit_unified(con, candidate_id, "resume", {})
            return self._show_unified(con, candidate_id)

    def merge(
        self,
        winner_id: str,
        loser_id: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if winner_id == loser_id:
            raise CandidateError("candidate merge requires two different candidates")
        now = _utc_now()
        with self._connect() as con:
            if not _is_unified_schema(con):
                raise CandidateError("candidate merge requires unified database migration")
            winner = _row_to_unified_candidate(con, self._require_existing(con, winner_id))
            loser = _row_to_unified_candidate(con, self._require_existing(con, loser_id))
            if winner["type"] != loser["type"]:
                raise CandidateError("candidate merge requires matching types")
            if winner["effective_status"] != "pending" or loser["effective_status"] != "pending":
                raise CandidateError("candidate merge requires two pending candidates")
            con.execute(
                """
                INSERT OR IGNORE INTO candidate_source_links(
                    candidate_id, source_ref_id, relationship, required,
                    legacy_payload_json, legacy_risk_label, created_at
                )
                SELECT ?, source_ref_id, relationship, required,
                       legacy_payload_json, legacy_risk_label, ?
                FROM candidate_source_links
                WHERE candidate_id = ?
                """,
                (winner_id, now, loser_id),
            )
            sensitivity = _max_sensitivity([winner["sensitivity"], loser["sensitivity"]])
            con.execute(
                "UPDATE knowledge_candidates SET sensitivity = ?, updated_at = ? WHERE candidate_id = ?",
                (sensitivity, now, winner_id),
            )
            con.execute(
                """
                UPDATE knowledge_candidates
                SET status = 'merged', merged_into_candidate_id = ?, resolved_at = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (winner_id, now, now, loser_id),
            )
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'merge' WHERE candidate_id = ? AND status = 'open'",
                (now, loser_id),
            )
            _sync_candidate_reviews(con, winner_id, now)
            self._decision(con, winner_id, "merge", reason=reason, payload={"merged_candidate_id": loser_id})
            self._decision(con, loser_id, "merge", reason=reason, payload={"merged_into_candidate_id": winner_id})
            self._audit_unified(con, winner_id, "merge", {"merged_candidate_id": loser_id, "reason": reason})
            self._audit_unified(con, loser_id, "merge", {"merged_into_candidate_id": winner_id, "reason": reason})
            return self._show_unified(con, winner_id)

    def edit(
        self,
        candidate_id: str,
        *,
        summary: str | None = None,
        candidate_type: str | None = None,
        confidence: float | None = None,
        risk: str | None = None,
        sensitivity: str | None = None,
        expires_at: str | None = None,
        add_source_refs: list[str] | None = None,
        remove_source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as con:
            if not _is_unified_schema(con):
                raise CandidateError("candidate edit requires unified database migration")
            candidate = _row_to_unified_candidate(con, self._require_existing(con, candidate_id))
            if candidate["stored_status"] not in {"pending", "deferred"}:
                raise CandidateError(f"Cannot edit {candidate['stored_status']} Candidate: {candidate_id}")
            updates: dict[str, Any] = {}
            if summary is not None:
                updates["summary"] = _require_text(summary, "summary")
            if candidate_type is not None:
                updates["type"] = _require_choice(candidate_type, CANDIDATE_TYPES, "type")
            if confidence is not None:
                updates["confidence"] = _require_confidence(confidence)
                updates["confidence_basis"] = "user_edit"
            if risk is not None:
                updates["risk"] = _require_choice(risk, CANDIDATE_RISKS, "risk")
            if sensitivity is not None:
                normalized_sensitivity = _require_choice(sensitivity, set(SENSITIVITY_LEVELS), "sensitivity")
                if SENSITIVITY_LEVELS.index(normalized_sensitivity) < SENSITIVITY_LEVELS.index(candidate["sensitivity"]):
                    raise CandidateError("candidate sensitivity cannot be lowered")
                updates["sensitivity"] = normalized_sensitivity
            if expires_at is not None:
                updates["expires_at"] = _normalize_expires_at(expires_at)

            for raw_ref in _clean_source_refs(remove_source_refs or []):
                identity = _opaque_identity(raw_ref)
                con.execute(
                    """
                    DELETE FROM candidate_source_links
                    WHERE candidate_id = ? AND source_ref_id IN (
                        SELECT source_ref_id
                        FROM source_references
                        WHERE source_ref_id = ? OR identity_key IN (?, ?)
                    )
                    """,
                    (candidate_id, raw_ref, raw_ref, identity),
                )
            target_sensitivity = str(updates.get("sensitivity", candidate["sensitivity"]))
            for raw_ref in _clean_source_refs(add_source_refs or []):
                source, relationship = _resolve_candidate_source(con, raw_ref, target_sensitivity, now)
                con.execute(
                    "INSERT OR IGNORE INTO candidate_source_links(candidate_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, ?, 0, ?)",
                    (candidate_id, source["source_ref_id"], relationship, now),
                )

            source_sensitivities = [
                str(row[0])
                for row in con.execute(
                    """
                    SELECT s.sensitivity
                    FROM candidate_source_links l
                    JOIN source_references s ON s.source_ref_id = l.source_ref_id
                    WHERE l.candidate_id = ?
                    """,
                    (candidate_id,),
                ).fetchall()
            ]
            if source_sensitivities:
                updates["sensitivity"] = _max_sensitivity([target_sensitivity, *source_sensitivities])
            updates["updated_at"] = now
            assignments = ", ".join(f"{key} = ?" for key in updates)
            con.execute(
                f"UPDATE knowledge_candidates SET {assignments} WHERE candidate_id = ?",
                [*updates.values(), candidate_id],
            )
            _sync_candidate_reviews(con, candidate_id, now)
            payload = {
                **updates,
                "add_source_refs": _clean_source_refs(add_source_refs or []),
                "remove_source_refs": _clean_source_refs(remove_source_refs or []),
            }
            self._decision(con, candidate_id, "edit", payload=payload)
            self._audit_unified(con, candidate_id, "edit", payload)
            return self._show_unified(con, candidate_id)

    def _connect(self) -> sqlite3.Connection:
        database = LifeMeshDatabase(self.config)
        database.ensure_current_for_write()
        _ensure_private_dir(self.config.home)
        con = database.connect()
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_candidates'"
        ).fetchone()
        if exists is None:
            _create_schema(con)
        else:
            con.execute("PRAGMA foreign_keys = ON")
        _chmod_file(self.config.db_path, 0o600)
        return con

    def _require_existing(self, con: sqlite3.Connection, candidate_id: str) -> sqlite3.Row:
        row = con.execute(
            "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise CandidateError(f"Candidate not found: {candidate_id}")
        return row

    def _audit(self, con: sqlite3.Connection, candidate_id: str, action: str, payload: dict[str, Any]) -> None:
        con.execute(
            "INSERT INTO candidate_audit_events(candidate_id, action, event_at, payload_json) VALUES (?, ?, ?, ?)",
            (candidate_id, action, _utc_now(), json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )

    def _show_unified(self, con: sqlite3.Connection, candidate_id: str) -> dict[str, Any]:
        row = self._require_existing(con, candidate_id)
        candidate = _row_to_unified_candidate(con, row)
        candidate["decisions"] = [
            {**dict(item), "payload": json.loads(item["payload_json"] or "{}")}
            for item in con.execute(
                "SELECT * FROM candidate_decisions WHERE candidate_id = ? ORDER BY decided_at, decision_id",
                (candidate_id,),
            ).fetchall()
        ]
        for item in candidate["decisions"]:
            item.pop("payload_json", None)
        discarded = next(
            (item for item in reversed(candidate["decisions"]) if item["decision"] == "discard"),
            None,
        )
        candidate["tombstone_reason"] = None if discarded is None else discarded.get("reason")
        candidate["audit_events"] = [
            _decode_unified_audit(dict(item))
            for item in con.execute(
                "SELECT * FROM audit_events WHERE aggregate_type = 'candidate' AND aggregate_id = ? ORDER BY event_id",
                (candidate_id,),
            ).fetchall()
        ]
        return candidate

    def _decision(
        self,
        con: sqlite3.Connection,
        candidate_id: str,
        decision: str,
        *,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        con.execute(
            "INSERT INTO candidate_decisions(decision_id, candidate_id, decision, actor_type, actor_id, reason, payload_json, decided_at) VALUES (?, ?, ?, 'local_user', 'local-user', ?, ?, ?)",
            (_new_id("decision"), candidate_id, decision, reason, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True), _utc_now()),
        )

    def _audit_unified(
        self,
        con: sqlite3.Connection,
        candidate_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> None:
        con.execute(
            """
            INSERT INTO audit_events(
                aggregate_type, aggregate_id, action, actor_type, actor_id,
                new_state_json, occurred_at
            ) VALUES ('candidate', ?, ?, 'local_user', 'local-user', ?, ?)
            """,
            (candidate_id, action, json.dumps(payload, ensure_ascii=False, sort_keys=True), _utc_now()),
        )


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS knowledge_candidates (
            candidate_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence REAL NOT NULL,
            risk TEXT NOT NULL,
            lifecycle TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            why_suggested TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            tombstone_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS candidate_audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL,
            action TEXT NOT NULL,
            event_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        """
    )


def _row_to_candidate(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise CandidateError("Expected database row")
    candidate = dict(row)
    candidate["source_refs"] = json.loads(candidate.pop("source_refs_json") or "[]")
    return candidate


def _is_unified_schema(con: sqlite3.Connection) -> bool:
    columns = {str(row[1]) for row in con.execute("PRAGMA table_info(knowledge_candidates)")}
    return "status" in columns and "sensitivity" in columns


def _row_to_unified_candidate(con: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    candidate = dict(row)
    candidate["stored_status"] = candidate.pop("status")
    candidate["effective_status"] = _effective_status(candidate)
    candidate["status"] = candidate["effective_status"]
    candidate["lifecycle"] = {
        "pending": "confirm_required",
        "deferred": "inbox",
        "discarded": "discard",
    }.get(candidate["stored_status"], candidate["stored_status"])
    candidate["source_links"] = [
        _decode_source_link(dict(item))
        for item in con.execute(
            """
            SELECT l.*, s.source_kind, s.adapter, s.source_item_id, s.citation_label,
                   s.sensitivity AS source_sensitivity, s.status AS source_status,
                   s.identity_key, s.metadata_json
            FROM candidate_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            WHERE l.candidate_id = ?
            ORDER BY l.created_at, l.source_ref_id
            """,
            (candidate["candidate_id"],),
        ).fetchall()
    ]
    candidate["source_refs"] = [item["identity_key"] for item in candidate["source_links"]]
    return candidate


def _effective_status(candidate: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    expires_at = _parse_datetime(candidate.get("expires_at"))
    if candidate["stored_status"] in {"pending", "deferred"} and expires_at and expires_at <= now:
        return "expired"
    deferred_until = _parse_datetime(candidate.get("deferred_until"))
    if candidate["stored_status"] == "deferred" and deferred_until and deferred_until <= now:
        return "pending"
    return str(candidate["stored_status"])


def _summarize_unified_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "candidate_id",
        "type",
        "summary",
        "confidence",
        "confidence_basis",
        "risk",
        "sensitivity",
        "status",
        "stored_status",
        "effective_status",
        "lifecycle",
        "source_refs",
        "why_suggested",
        "created_at",
        "updated_at",
        "expires_at",
        "deferred_until",
    ]
    return {key: candidate.get(key) for key in keys}


def _decode_source_link(row: dict[str, Any]) -> dict[str, Any]:
    row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
    if row.get("legacy_payload_json"):
        row["legacy_payload"] = json.loads(row.pop("legacy_payload_json"))
    else:
        row.pop("legacy_payload_json", None)
    row["required"] = bool(row["required"])
    return row


def _decode_unified_audit(row: dict[str, Any]) -> dict[str, Any]:
    for source, target in [("old_state_json", "old_state"), ("new_state_json", "new_state")]:
        value = row.pop(source)
        row[target] = None if value is None else json.loads(value)
    return row


def _ensure_opaque_source(con: sqlite3.Connection, raw_ref: str, sensitivity: str, now: str) -> str:
    digest = hashlib.sha256(raw_ref.encode("utf-8")).hexdigest()
    identity = _opaque_identity(raw_ref)
    row = con.execute(
        "SELECT source_ref_id FROM source_references WHERE identity_key = ?",
        (identity,),
    ).fetchone()
    if row is not None:
        return str(row[0])
    source_ref_id = f"source_{digest[:24]}"
    con.execute(
        """
        INSERT INTO source_references(
            source_ref_id, source_kind, adapter, citation_label, sensitivity,
            status, metadata_json, identity_key, created_at, updated_at
        ) VALUES (?, 'opaque', 'candidate_cli', ?, ?, 'unknown', ?, ?, ?, ?)
        """,
        (
            source_ref_id,
            f"Opaque source {digest[:12]}",
            sensitivity,
            json.dumps({"raw_ref_hash": digest}, sort_keys=True),
            identity,
            now,
            now,
        ),
    )
    return source_ref_id


def _resolve_candidate_source(
    con: sqlite3.Connection,
    raw_ref: str,
    sensitivity: str,
    now: str,
) -> tuple[sqlite3.Row, str]:
    source = con.execute(
        """
        SELECT * FROM source_references
        WHERE source_ref_id = ? OR identity_key = ? OR identity_key = ?
        """,
        (raw_ref, raw_ref, _opaque_identity(raw_ref)),
    ).fetchone()
    if source is None:
        source_ref_id = _ensure_opaque_source(con, raw_ref, sensitivity, now)
        source = con.execute(
            "SELECT * FROM source_references WHERE source_ref_id = ?",
            (source_ref_id,),
        ).fetchone()
    relationship = (
        "supports"
        if source["status"] == "current" and source["source_kind"] != "opaque"
        else "legacy_reference"
    )
    return source, relationship


def _sync_candidate_reviews(con: sqlite3.Connection, candidate_id: str, now: str) -> None:
    con.execute(
        """
        UPDATE review_items
        SET status = 'resolved', resolved_at = ?, resolution = 'edit'
        WHERE candidate_id = ? AND status = 'open'
          AND NOT EXISTS (
              SELECT 1
              FROM candidate_source_links l
              JOIN source_references s ON s.source_ref_id = l.source_ref_id
              WHERE l.candidate_id = review_items.candidate_id
                AND l.source_ref_id = review_items.trigger_source_ref_id
                AND l.required = 1
                AND (s.status != 'current' OR s.source_kind = 'opaque')
          )
        """,
        (now, candidate_id),
    )
    rows = con.execute(
        """
        SELECT l.source_ref_id, s.status, s.source_kind
        FROM candidate_source_links l
        JOIN source_references s ON s.source_ref_id = l.source_ref_id
        WHERE l.candidate_id = ? AND l.required = 1
          AND (s.status != 'current' OR s.source_kind = 'opaque')
        """,
        (candidate_id,),
    ).fetchall()
    for row in rows:
        review_kind = {
            "stale": "source_stale",
            "missing": "source_missing",
            "revoked": "source_revoked",
            "deleted": "source_deleted",
        }.get(str(row["status"]), "source_missing")
        operation_key = f"candidate-review:{candidate_id}:{row['source_ref_id']}:{review_kind}"
        review_id = f"review_{hashlib.sha256(operation_key.encode('utf-8')).hexdigest()[:24]}"
        con.execute(
            """
            INSERT OR IGNORE INTO review_items(
                review_id, candidate_id, object_id, trigger_source_ref_id,
                review_kind, status, reason, opened_at, operation_key
            ) VALUES (?, ?, NULL, ?, ?, 'open', ?, ?, ?)
            """,
            (
                review_id,
                candidate_id,
                row["source_ref_id"],
                review_kind,
                review_kind,
                now,
                operation_key,
            ),
        )


def _allowed_sensitivities(cap: str) -> list[str]:
    return SENSITIVITY_LEVELS[: SENSITIVITY_LEVELS.index(cap) + 1]


def _max_sensitivity(values: list[str]) -> str:
    return max(values, key=SENSITIVITY_LEVELS.index)


def _opaque_identity(raw_ref: str) -> str:
    return f"opaque:{hashlib.sha256(raw_ref.encode('utf-8')).hexdigest()}"


def _summarize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "candidate_id",
        "type",
        "summary",
        "confidence",
        "risk",
        "lifecycle",
        "source_refs",
        "why_suggested",
        "created_at",
        "updated_at",
        "expires_at",
    ]
    return {key: candidate.get(key) for key in keys}


def _decode_audit(row: dict[str, Any]) -> dict[str, Any]:
    row["payload"] = json.loads(row.pop("payload_json") or "{}")
    return row


def _clean_source_refs(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _require_text(value: str, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise CandidateError(f"candidate {field} is required")
    return text


def _require_choice(value: str, allowed: set[str], field: str) -> str:
    text = str(value).strip()
    if text not in allowed:
        choices = ", ".join(sorted(allowed))
        raise CandidateError(f"candidate {field} must be one of: {choices}")
    return text


def _require_confidence(value: float) -> float:
    confidence = float(value)
    if not math.isfinite(confidence) or confidence < 0 or confidence > 1:
        raise CandidateError("candidate confidence must be between 0 and 1")
    return confidence


def _normalize_expires_at(value: str | None) -> str | None:
    if value is None:
        return None
    dt = _parse_datetime(value)
    if dt is None:
        raise CandidateError("--expires-at must be ISO-8601")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _chmod_file(path, 0o700)


def _chmod_file(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
