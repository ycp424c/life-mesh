from __future__ import annotations

import json
import math
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LifemeshConfig

CANDIDATE_TYPES = {"fact", "preference", "relationship", "task", "decision"}
CANDIDATE_RISKS = {"low", "medium", "high"}
CANDIDATE_LIFECYCLES = {"transient", "inbox", "confirm_required", "discard"}
LISTABLE_CANDIDATE_LIFECYCLES = {"inbox", "confirm_required", "discard"}
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
    ) -> dict[str, Any]:
        normalized = {
            "summary": _require_text(summary, "summary"),
            "type": _require_choice(candidate_type, CANDIDATE_TYPES, "type"),
            "source_refs": _clean_source_refs(source_refs or []),
            "confidence": _require_confidence(confidence),
            "risk": _require_choice(risk, CANDIDATE_RISKS, "risk"),
            "why_suggested": _require_text(why_suggested, "why_suggested"),
            "expires_at": _normalize_expires_at(expires_at),
        }
        candidate_id = _new_id("candidate")
        now = _utc_now()
        with self._connect() as con:
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
        candidate_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            raise CandidateError("--limit must be at least 1")
        if lifecycle is not None:
            lifecycle = _require_choice(lifecycle, CANDIDATE_LIFECYCLES, "lifecycle")
        if candidate_type is not None:
            candidate_type = _require_choice(candidate_type, CANDIDATE_TYPES, "type")

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

    def _connect(self) -> sqlite3.Connection:
        _ensure_private_dir(self.config.home)
        con = sqlite3.connect(self.config.db_path)
        con.row_factory = sqlite3.Row
        _create_schema(con)
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
