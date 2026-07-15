from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIGRATION_ID = "0001_unified_write_model"
MIGRATION_NAME = "unified write model"


UNIFIED_SCHEMA_SQL = """
CREATE TABLE schema_migrations (
    migration_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE migration_legacy_map (
    legacy_table TEXT NOT NULL,
    legacy_id TEXT NOT NULL,
    new_type TEXT NOT NULL,
    new_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (legacy_table, legacy_id, new_type)
);

CREATE TABLE audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT,
    action TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    old_state_json TEXT,
    new_state_json TEXT,
    reason TEXT,
    correlation_id TEXT,
    legacy_event_key TEXT UNIQUE,
    occurred_at TEXT NOT NULL
);

CREATE TABLE file_operations (
    operation_id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('promote_staged_asset', 'delete_managed_asset')),
    idempotency_key TEXT NOT NULL UNIQUE,
    source_path TEXT,
    target_path TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE source_references (
    source_ref_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('obsidian_revision', 'manual_input', 'manual_input_extraction', 'rumor_claim', 'user_assertion', 'opaque')),
    adapter TEXT NOT NULL,
    source_item_id TEXT,
    revision_id TEXT,
    content_hash TEXT,
    citation_label TEXT NOT NULL,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('Public', 'Internal', 'Private', 'Sensitive', 'Restricted')),
    status TEXT NOT NULL CHECK (status IN ('current', 'stale', 'missing', 'revoked', 'deleted', 'inactive', 'unknown')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    identity_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE source_tombstones (
    tombstone_id TEXT PRIMARY KEY,
    source_ref_id TEXT NOT NULL REFERENCES source_references(source_ref_id),
    reason TEXT NOT NULL,
    created_by TEXT NOT NULL,
    operation_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE knowledge_candidates (
    candidate_id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('fact', 'preference', 'relationship', 'task', 'decision')),
    summary TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    confidence_basis TEXT,
    risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high')),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('Public', 'Internal', 'Private', 'Sensitive', 'Restricted')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'deferred', 'confirmed', 'merged', 'discarded')),
    confirmation_required INTEGER NOT NULL CHECK (confirmation_required IN (0, 1)),
    why_suggested TEXT NOT NULL,
    expires_at TEXT,
    deferred_until TEXT,
    merged_into_candidate_id TEXT REFERENCES knowledge_candidates(candidate_id),
    resolved_at TEXT,
    handoff_key TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE candidate_source_links (
    candidate_id TEXT NOT NULL REFERENCES knowledge_candidates(candidate_id),
    source_ref_id TEXT NOT NULL REFERENCES source_references(source_ref_id),
    relationship TEXT NOT NULL CHECK (relationship IN ('derived_from', 'supports', 'contradicts', 'legacy_reference')),
    required INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    legacy_payload_json TEXT,
    legacy_risk_label TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (candidate_id, source_ref_id, relationship)
);

CREATE TABLE candidate_decisions (
    decision_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES knowledge_candidates(candidate_id),
    decision TEXT NOT NULL CHECK (decision IN ('edit', 'defer', 'resume', 'confirm', 'merge', 'discard')),
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    reason TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    decided_at TEXT NOT NULL
);

CREATE TABLE canonical_objects (
    object_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL CHECK (object_type IN ('fact', 'memory', 'task', 'event')),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('Public', 'Internal', 'Private', 'Sensitive', 'Restricted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE canonical_facts (
    fact_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id),
    statement TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high')),
    validity TEXT NOT NULL CHECK (validity IN ('valid', 'needs_review', 'invalid', 'superseded')),
    revocation_status TEXT NOT NULL CHECK (revocation_status IN ('active', 'revoked')),
    review_reason TEXT,
    review_started_at TEXT,
    reviewed_at TEXT,
    superseded_by_fact_id TEXT REFERENCES canonical_facts(fact_id)
);

CREATE TABLE memories (
    memory_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id),
    text TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('explicit', 'inferred', 'contextual')),
    scope TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    confirmation_status TEXT NOT NULL CHECK (confirmation_status IN ('manual', 'confirmed')),
    status TEXT NOT NULL CHECK (status IN ('active', 'needs_review', 'revoked', 'superseded')),
    expires_at TEXT
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id),
    title TEXT NOT NULL,
    description TEXT,
    due_at TEXT,
    task_status TEXT NOT NULL CHECK (task_status IN ('open', 'in_progress', 'completed', 'cancelled'))
);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY REFERENCES canonical_objects(object_id),
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    timezone TEXT,
    event_status TEXT NOT NULL CHECK (event_status IN ('scheduled', 'occurred', 'cancelled'))
);

CREATE TABLE object_source_links (
    object_id TEXT NOT NULL REFERENCES canonical_objects(object_id),
    source_ref_id TEXT NOT NULL REFERENCES source_references(source_ref_id),
    relationship TEXT NOT NULL CHECK (relationship IN ('derived_from', 'supports', 'contradicts')),
    required INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (object_id, source_ref_id, relationship)
);

CREATE TABLE acceptances (
    acceptance_id TEXT PRIMARY KEY,
    candidate_id TEXT REFERENCES knowledge_candidates(candidate_id),
    object_id TEXT NOT NULL REFERENCES canonical_objects(object_id),
    acceptance_path TEXT NOT NULL CHECK (acceptance_path IN ('user_confirmation', 'manual', 'policy')),
    accepted_by TEXT NOT NULL,
    policy_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_hash TEXT,
    accepted_at TEXT NOT NULL,
    UNIQUE (candidate_id)
);

CREATE TABLE object_tombstones (
    tombstone_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES canonical_objects(object_id),
    reason TEXT NOT NULL,
    replacement_object_id TEXT REFERENCES canonical_objects(object_id),
    operation_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE review_items (
    review_id TEXT PRIMARY KEY,
    candidate_id TEXT REFERENCES knowledge_candidates(candidate_id),
    object_id TEXT REFERENCES canonical_objects(object_id),
    trigger_source_ref_id TEXT NOT NULL REFERENCES source_references(source_ref_id),
    review_kind TEXT NOT NULL CHECK (review_kind IN ('source_stale', 'source_missing', 'source_revoked', 'source_deleted', 'conflict')),
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'dismissed')),
    reason TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution TEXT,
    operation_key TEXT NOT NULL UNIQUE,
    CHECK ((candidate_id IS NOT NULL) != (object_id IS NOT NULL))
);

CREATE INDEX idx_candidates_status ON knowledge_candidates(status, created_at);
CREATE INDEX idx_candidate_sources_ref ON candidate_source_links(source_ref_id);
CREATE INDEX idx_object_sources_ref ON object_source_links(source_ref_id);
CREATE INDEX idx_reviews_status ON review_items(status, opened_at);
CREATE UNIQUE INDEX idx_open_candidate_review
    ON review_items(candidate_id, trigger_source_ref_id, review_kind)
    WHERE status = 'open' AND candidate_id IS NOT NULL;
CREATE UNIQUE INDEX idx_open_object_review
    ON review_items(object_id, trigger_source_ref_id, review_kind)
    WHERE status = 'open' AND object_id IS NOT NULL;
"""


MIGRATION_CHECKSUM = hashlib.sha256(UNIFIED_SCHEMA_SQL.encode("utf-8")).hexdigest()


def build_preflight(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "database_exists": False,
            "legacy_tables": {},
            "expected": _empty_expected(),
            "identity_digests": _empty_identity_digests(),
            "preserved_table_digests": {},
        }
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        tables = {
            str(row[0])
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        legacy_table_names = [
            "manual_inputs",
            "manual_input_extractions",
            "embedding_records",
            "promoted_objects",
            "manual_input_audit_events",
            "rumor_claims",
            "rumor_mentions",
            "rumor_candidate_links",
            "rumor_audit_events",
            "knowledge_candidates",
            "candidate_audit_events",
        ]
        counts = {
            table: int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in legacy_table_names
            if table in tables
        }

        manual_rows = _rows(con, tables, "manual_inputs")
        rumor_rows = _rows(con, tables, "rumor_claims")
        manual_by_id = {str(row["input_id"]): row for row in manual_rows}
        rumor_by_id = {str(row["rumor_claim_id"]): row for row in rumor_rows}

        source_identities: set[str] = set()
        tombstone_identities: set[str] = set()
        source_shapes: dict[str, tuple[str, str]] = {}
        for row in manual_rows:
            identity = _manual_identity(row)
            source_identities.add(identity)
            source_shapes[identity] = (
                {
                    "active": "current",
                    "promoted": "current",
                    "auto_captured": "current",
                    "revoked": "revoked",
                    "deleted": "deleted",
                }.get(str(row["status"]), "unknown"),
                "manual_input",
            )
            if str(row["status"]) in {"revoked", "deleted"}:
                tombstone_identities.add(identity)
        for row in rumor_rows:
            identity = f"rumor_claim:{row['rumor_claim_id']}"
            source_identities.add(identity)
            source_shapes[identity] = (
                "current"
                if str(row["status"]) in {"parked", "reviewed_parked", "candidate_created"}
                else "inactive",
                "rumor_claim",
            )
            if str(row["status"]) in {"dismissed", "expired"}:
                tombstone_identities.add(identity)

        candidate_ids: set[str] = set()
        review_identities: set[str] = set()
        candidate_link_identities: set[str] = set()
        object_link_identities: set[str] = set()
        if "knowledge_candidates" in tables and not _is_unified_candidate_table(con):
            for row in con.execute("SELECT candidate_id, source_refs_json FROM knowledge_candidates"):
                candidate_id = str(row["candidate_id"])
                candidate_ids.add(candidate_id)
                for raw_ref in json.loads(row["source_refs_json"] or "[]"):
                    identity = _legacy_ref_identity(str(raw_ref), manual_by_id, rumor_by_id)
                    source_identities.add(identity)
                    status, source_kind = source_shapes.get(identity, ("unknown", "opaque"))
                    relationship = (
                        "supports"
                        if status == "current" and source_kind != "opaque"
                        else "legacy_reference"
                    )
                    candidate_link_identities.add(
                        f"{candidate_id}|{identity}|{relationship}|0"
                    )

        canonical_ids: set[str] = set()
        if "promoted_objects" in tables:
            for row in con.execute("SELECT * FROM promoted_objects"):
                input_row = manual_by_id.get(str(row["derived_from_input_id"]))
                if input_row is None or str(input_row["status"]) == "deleted":
                    continue
                payload = json.loads(row["target_payload_json"] or "{}")
                for raw_ref in payload.get("source_refs", []):
                    source_identities.add(_legacy_ref_identity(str(raw_ref), manual_by_id, rumor_by_id))
                if str(row["target_type"]) == "candidate":
                    subject_id = str(row["object_id"])
                    candidate_ids.add(subject_id)
                    candidate_link_identities.add(
                        f"{subject_id}|{_manual_identity(input_row)}|derived_from|1"
                    )
                    for raw_ref in payload.get("source_refs", []):
                        identity = _legacy_ref_identity(str(raw_ref), manual_by_id, rumor_by_id)
                        if identity == _manual_identity(input_row):
                            continue
                        status, source_kind = source_shapes.get(identity, ("unknown", "opaque"))
                        relationship = (
                            "supports"
                            if status == "current" and source_kind != "opaque"
                            else "legacy_reference"
                        )
                        candidate_link_identities.add(
                            f"{subject_id}|{identity}|{relationship}|0"
                        )
                    if str(input_row["status"]) == "revoked":
                        review_identities.add(
                            f"candidate:{subject_id}|{_manual_identity(input_row)}|source_revoked"
                        )
                else:
                    subject_id = str(row["object_id"])
                    canonical_ids.add(subject_id)
                    source_identity = _manual_identity(input_row)
                    object_link_identities.add(
                        f"{subject_id}|{source_identity}|derived_from|1"
                    )
                    if str(row["target_type"]) == "fact":
                        object_link_identities.add(
                            f"{subject_id}|{source_identity}|supports|1"
                        )
                    for raw_ref in payload.get("source_refs", []):
                        identity = _legacy_ref_identity(str(raw_ref), manual_by_id, rumor_by_id)
                        if identity == source_identity:
                            continue
                        status, source_kind = source_shapes.get(identity, ("unknown", "opaque"))
                        relationship = (
                            "supports"
                            if str(row["target_type"]) == "fact"
                            and status == "current"
                            and source_kind != "opaque"
                            else "derived_from"
                        )
                        object_link_identities.add(
                            f"{subject_id}|{identity}|{relationship}|0"
                        )
                    if str(input_row["status"]) == "revoked":
                        review_identities.add(
                            f"object:{subject_id}|{_manual_identity(input_row)}|source_revoked"
                        )

        if "rumor_candidate_links" in tables:
            for row in con.execute("SELECT * FROM rumor_candidate_links"):
                rumor_row = rumor_by_id.get(str(row["rumor_claim_id"]))
                if rumor_row is None or str(rumor_row["status"]) in {"dismissed", "expired"}:
                    continue
                candidate_ids.add(str(row["object_id"]))
                candidate_link_identities.add(
                    f"{row['object_id']}|rumor_claim:{row['rumor_claim_id']}|derived_from|1"
                )
                payload = json.loads(row["target_payload_json"] or "{}")
                for raw_ref in payload.get("source_refs", []):
                    identity = _legacy_ref_identity(str(raw_ref), manual_by_id, rumor_by_id)
                    source_identities.add(identity)
                    if identity == f"rumor_claim:{row['rumor_claim_id']}":
                        continue
                    status, source_kind = source_shapes.get(identity, ("unknown", "opaque"))
                    relationship = (
                        "supports"
                        if status == "current" and source_kind != "opaque"
                        else "legacy_reference"
                    )
                    candidate_link_identities.add(
                        f"{row['object_id']}|{identity}|{relationship}|0"
                    )

        legacy_audit_identities: set[str] = set()
        deleted_promotion_audit_object_ids: set[str] = set()
        for table, migrated_table in [
            ("manual_input_audit_events", "manual_input_audit_events"),
            ("rumor_audit_events", "rumor_audit_events"),
            ("candidate_audit_events", "legacy_candidate_audit_events"),
        ]:
            if table in tables:
                for row in con.execute(f'SELECT * FROM "{table}"'):
                    legacy_audit_identities.add(f"{migrated_table}:{row['event_id']}")
                    if table == "manual_input_audit_events":
                        manual = manual_by_id.get(str(row["input_id"]))
                        if manual is not None and str(manual["status"]) == "deleted" and str(row["action"]) == "promote":
                            payload = json.loads(row["payload_json"] or "{}")
                            if payload.get("object_id"):
                                deleted_promotion_audit_object_ids.add(str(payload["object_id"]))
        if "promoted_objects" in tables:
            for row in con.execute("SELECT * FROM promoted_objects"):
                input_row = manual_by_id.get(str(row["derived_from_input_id"]))
                if (
                    input_row is not None
                    and str(input_row["status"]) == "deleted"
                    and str(row["object_id"]) not in deleted_promotion_audit_object_ids
                ):
                    legacy_audit_identities.add(
                        f"promoted_objects:{row['object_id']}:legacy_target_missing"
                    )

        expected = {
            "candidates": len(candidate_ids),
            "source_references": len(source_identities),
            "source_tombstones": len(tombstone_identities),
            "canonical_objects": len(canonical_ids),
            "review_items": len(review_identities),
        }
        return {
            "database_exists": True,
            "legacy_tables": counts,
            "expected": expected,
            "identity_digests": {
                "candidates": _digest(candidate_ids),
                "source_references": _digest(source_identities),
                "source_tombstones": _digest(tombstone_identities),
                "canonical_objects": _digest(canonical_ids),
                "review_items": _digest(review_identities),
                "candidate_source_links": _digest(candidate_link_identities),
                "object_source_links": _digest(object_link_identities),
                "legacy_audit_events": _digest(legacy_audit_identities),
            },
            "preserved_table_digests": _preserved_table_digests(con, tables),
        }


def apply_empty_schema(con: sqlite3.Connection, *, applied_at: str) -> None:
    con.execute("BEGIN IMMEDIATE")
    try:
        _execute_sql_script(con, UNIFIED_SCHEMA_SQL)
        _record_migration(con, applied_at)
        con.commit()
    except Exception:
        con.rollback()
        raise


def apply_legacy_schema(con: sqlite3.Connection, *, applied_at: str) -> None:
    tables = _table_names(con)
    if "schema_migrations" in tables:
        row = con.execute(
            "SELECT checksum FROM schema_migrations WHERE migration_id = ?",
            (MIGRATION_ID,),
        ).fetchone()
        if row is not None:
            if str(row[0]) != MIGRATION_CHECKSUM:
                raise sqlite3.IntegrityError("migration checksum mismatch")
            return

    if "knowledge_candidates" in tables:
        columns = {str(row[1]) for row in con.execute("PRAGMA table_info(knowledge_candidates)")}
        if "lifecycle" in columns:
            if "legacy_knowledge_candidates" in tables:
                raise sqlite3.IntegrityError("legacy_knowledge_candidates already exists")
            con.execute("ALTER TABLE knowledge_candidates RENAME TO legacy_knowledge_candidates")
    if "candidate_audit_events" in tables:
        if "legacy_candidate_audit_events" in tables:
            raise sqlite3.IntegrityError("legacy_candidate_audit_events already exists")
        con.execute("ALTER TABLE candidate_audit_events RENAME TO legacy_candidate_audit_events")

    _execute_sql_script(con, UNIFIED_SCHEMA_SQL)
    _migrate_sources(con)
    _migrate_candidates(con)
    _migrate_promoted_objects(con)
    _migrate_legacy_audits(con)
    _record_migration(con, applied_at)


def _record_migration(con: sqlite3.Connection, applied_at: str) -> None:
    con.execute(
        "INSERT INTO schema_migrations(migration_id, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
        (MIGRATION_ID, MIGRATION_NAME, MIGRATION_CHECKSUM, applied_at),
    )


def _migrate_sources(con: sqlite3.Connection) -> None:
    tables = _table_names(con)
    if "manual_inputs" in tables:
        for row in con.execute("SELECT * FROM manual_inputs"):
            identity = _manual_identity(row)
            status = {
                "active": "current",
                "promoted": "current",
                "auto_captured": "current",
                "revoked": "revoked",
                "deleted": "deleted",
            }.get(str(row["status"]), "unknown")
            metadata = {
                "kind": row["kind"],
                "status": row["status"],
                "source_type": row["source_type"],
            }
            _insert_source_reference(
                con,
                identity=identity,
                source_kind="manual_input",
                adapter=str(row["source_type"]),
                source_item_id=str(row["input_id"]),
                content_hash=row["content_hash"],
                citation_label=f"Manual Input {row['input_id']}",
                sensitivity=str(row["sensitivity"]),
                status=status,
                metadata=metadata,
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            if status in {"revoked", "deleted"}:
                _insert_source_tombstone(con, identity, status, str(row["updated_at"]))

    if "rumor_claims" in tables:
        for row in con.execute("SELECT * FROM rumor_claims"):
            identity = f"rumor_claim:{row['rumor_claim_id']}"
            status = "current" if str(row["status"]) in {
                "parked",
                "reviewed_parked",
                "candidate_created",
            } else "inactive"
            envelope = json.loads(row["source_envelope_json"] or "{}")
            metadata = {
                "claim_type": row["claim_type"],
                "assessment": row["assessment"],
                "status": row["status"],
            }
            _insert_source_reference(
                con,
                identity=identity,
                source_kind="rumor_claim",
                adapter=str(envelope.get("source_adapter") or "unknown"),
                source_item_id=str(row["rumor_claim_id"]),
                content_hash=None,
                citation_label=f"RumorClaim {row['rumor_claim_id']}",
                sensitivity=str(row["sensitivity"]),
                status=status,
                metadata=metadata,
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            if status == "inactive":
                _insert_source_tombstone(con, identity, str(row["status"]), str(row["updated_at"]))


def _migrate_candidates(con: sqlite3.Connection) -> None:
    tables = _table_names(con)
    manual_by_id = _row_map(con, tables, "manual_inputs", "input_id")
    rumor_by_id = _row_map(con, tables, "rumor_claims", "rumor_claim_id")

    if "legacy_knowledge_candidates" in tables:
        for row in con.execute("SELECT * FROM legacy_knowledge_candidates"):
            raw_refs = json.loads(row["source_refs_json"] or "[]")
            links = [
                _ensure_legacy_source(con, str(raw_ref), manual_by_id, rumor_by_id)
                for raw_ref in raw_refs
            ]
            sensitivity = _max_sensitivity([link[1] for link in links] or ["Private"])
            lifecycle = str(row["lifecycle"])
            status = "discarded" if lifecycle == "discard" else "pending"
            _insert_candidate(
                con,
                candidate_id=str(row["candidate_id"]),
                candidate_type=str(row["type"]),
                summary=str(row["summary"]),
                confidence=_normalize_confidence(row["confidence"], default=0.5),
                confidence_basis="legacy_candidate",
                risk=_normalize_risk(row["risk"], sensitivity, str(row["type"])),
                sensitivity=sensitivity,
                status=status,
                why_suggested=str(row["why_suggested"] or "legacy_candidate_migration"),
                expires_at=row["expires_at"],
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                handoff_key=None,
                resolved_at=str(row["updated_at"]) if status == "discarded" else None,
            )
            for source_ref_id, _sensitivity, source_status, source_kind in links:
                relationship = "supports" if source_status == "current" and source_kind != "opaque" else "legacy_reference"
                _insert_candidate_link(con, str(row["candidate_id"]), source_ref_id, relationship, False)
            _legacy_map(con, "knowledge_candidates", str(row["candidate_id"]), "candidate", str(row["candidate_id"]))

    if "promoted_objects" in tables:
        for row in con.execute("SELECT * FROM promoted_objects WHERE target_type = 'candidate'"):
            manual = manual_by_id.get(str(row["derived_from_input_id"]))
            if manual is None or str(manual["status"]) == "deleted":
                continue
            payload = json.loads(row["target_payload_json"] or "{}")
            source_ref_id = _source_id(_manual_identity(manual))
            extra_sources = [
                _ensure_legacy_source(con, str(raw_ref), manual_by_id, rumor_by_id)
                for raw_ref in payload.get("source_refs", [])
            ]
            sensitivity = _max_sensitivity(
                [str(manual["sensitivity"]), *(item[1] for item in extra_sources)]
            )
            payload_hash = _payload_hash(payload)
            candidate_id = str(row["object_id"])
            _insert_candidate(
                con,
                candidate_id=candidate_id,
                candidate_type=str(payload["type"]),
                summary=str(payload.get("statement") or payload.get("summary")),
                confidence=_normalize_confidence(payload.get("confidence"), default=0.5),
                confidence_basis="legacy_manual_input_handoff",
                risk=_normalize_risk(payload.get("risk"), sensitivity, str(payload["type"])),
                sensitivity=sensitivity,
                status="pending",
                why_suggested="legacy_manual_input_handoff",
                expires_at=payload.get("expires_at"),
                created_at=str(row["created_at"]),
                updated_at=str(row["created_at"]),
                handoff_key=f"manual-input:{manual['input_id']}:candidate:{payload_hash}",
            )
            _insert_candidate_link(con, candidate_id, source_ref_id, "derived_from", True, payload)
            for extra_ref_id, _extra_sensitivity, extra_status, extra_kind in extra_sources:
                if extra_ref_id == source_ref_id:
                    continue
                relationship = (
                    "supports"
                    if extra_status == "current" and extra_kind != "opaque"
                    else "legacy_reference"
                )
                _insert_candidate_link(
                    con,
                    candidate_id,
                    extra_ref_id,
                    relationship,
                    False,
                    payload,
                )
            source_status = str(
                con.execute(
                    "SELECT status FROM source_references WHERE source_ref_id = ?",
                    (source_ref_id,),
                ).fetchone()[0]
            )
            if source_status != "current":
                _insert_migration_review(
                    con,
                    candidate_id=candidate_id,
                    object_id=None,
                    source_ref_id=source_ref_id,
                    source_status=source_status,
                    opened_at=str(row["created_at"]),
                )
            _legacy_map(con, "promoted_objects", candidate_id, "candidate", candidate_id)

    if "rumor_candidate_links" in tables:
        for row in con.execute("SELECT * FROM rumor_candidate_links"):
            rumor = rumor_by_id.get(str(row["rumor_claim_id"]))
            if rumor is None or str(rumor["status"]) in {"dismissed", "expired"}:
                continue
            payload = json.loads(row["target_payload_json"] or "{}")
            source_ref_id = _source_id(f"rumor_claim:{rumor['rumor_claim_id']}")
            extra_sources = [
                _ensure_legacy_source(con, str(raw_ref), manual_by_id, rumor_by_id)
                for raw_ref in payload.get("source_refs", [])
            ]
            sensitivity = _max_sensitivity(
                [str(rumor["sensitivity"]), *(item[1] for item in extra_sources)]
            )
            candidate_id = str(row["object_id"])
            _insert_candidate(
                con,
                candidate_id=candidate_id,
                candidate_type=str(payload["type"]),
                summary=str(payload.get("statement") or payload.get("summary")),
                confidence=_normalize_confidence(payload.get("confidence"), default=0.5),
                confidence_basis="legacy_rumor_handoff",
                risk=_normalize_risk(payload.get("risk"), sensitivity, str(payload["type"])),
                sensitivity=sensitivity,
                status="pending",
                why_suggested="legacy_rumor_handoff",
                expires_at=None,
                created_at=str(row["created_at"]),
                updated_at=str(row["created_at"]),
                handoff_key=f"rumor:{rumor['rumor_claim_id']}:candidate",
            )
            _insert_candidate_link(con, candidate_id, source_ref_id, "derived_from", True, payload)
            for extra_ref_id, _extra_sensitivity, extra_status, extra_kind in extra_sources:
                if extra_ref_id == source_ref_id:
                    continue
                relationship = (
                    "supports"
                    if extra_status == "current" and extra_kind != "opaque"
                    else "legacy_reference"
                )
                _insert_candidate_link(
                    con,
                    candidate_id,
                    extra_ref_id,
                    relationship,
                    False,
                    payload,
                )
            _legacy_map(con, "rumor_candidate_links", candidate_id, "candidate", candidate_id)


def _migrate_promoted_objects(con: sqlite3.Connection) -> None:
    tables = _table_names(con)
    if "promoted_objects" not in tables or "manual_inputs" not in tables:
        return
    manual_by_id = _row_map(con, tables, "manual_inputs", "input_id")
    rumor_by_id = _row_map(con, tables, "rumor_claims", "rumor_claim_id")
    for row in con.execute("SELECT * FROM promoted_objects WHERE target_type != 'candidate'"):
        manual = manual_by_id.get(str(row["derived_from_input_id"]))
        if manual is None or str(manual["status"]) == "deleted":
            continue
        payload = json.loads(row["target_payload_json"] or "{}")
        object_id = str(row["object_id"])
        object_type = str(row["target_type"])
        extra_sources = [
            _ensure_legacy_source(con, str(raw_ref), manual_by_id, rumor_by_id)
            for raw_ref in payload.get("source_refs", [])
        ]
        sensitivity = _max_sensitivity(
            [str(manual["sensitivity"]), *(item[1] for item in extra_sources)]
        )
        created_at = str(row["created_at"])
        source_ref_id = _source_id(_manual_identity(manual))
        source_status = str(
            con.execute(
                "SELECT status FROM source_references WHERE source_ref_id = ?",
                (source_ref_id,),
            ).fetchone()[0]
        )
        source_current = source_status == "current"
        con.execute(
            "INSERT INTO canonical_objects(object_id, object_type, sensitivity, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (object_id, object_type, sensitivity, created_at, created_at),
        )
        if object_type == "fact":
            con.execute(
                "INSERT INTO canonical_facts(fact_id, statement, confidence, risk, validity, revocation_status, review_reason, review_started_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    object_id,
                    str(payload["statement"]),
                    _normalize_confidence(payload.get("confidence"), default=0.5),
                    _normalize_risk(payload.get("risk"), sensitivity, "fact"),
                    "valid" if source_current else "needs_review",
                    None if source_current else _review_kind(source_status),
                    None if source_current else created_at,
                ),
            )
        elif object_type == "memory":
            con.execute(
                "INSERT INTO memories(memory_id, text, memory_type, scope, confidence, confirmation_status, status, expires_at) VALUES (?, ?, 'explicit', ?, ?, 'manual', ?, ?)",
                (object_id, str(payload["text"]), payload.get("scope"), _normalize_confidence(payload.get("confidence"), default=1.0), "active" if source_current else "needs_review", payload.get("expires_at")),
            )
        elif object_type == "task":
            con.execute(
                "INSERT INTO tasks(task_id, title, description, due_at, task_status) VALUES (?, ?, ?, ?, ?)",
                (object_id, str(payload["title"]), payload.get("description"), payload.get("due_at"), _task_status(payload.get("status"))),
            )
        elif object_type == "event":
            con.execute(
                "INSERT INTO events(event_id, title, starts_at, ends_at, timezone, event_status) VALUES (?, ?, ?, ?, ?, ?)",
                (object_id, str(payload["title"]), str(payload["starts_at"]), payload.get("ends_at"), payload.get("timezone"), _event_status(payload.get("status"))),
            )
        else:
            raise sqlite3.IntegrityError(f"unknown promoted object type: {object_type}")
        con.execute(
            "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'derived_from', 1, ?)",
            (object_id, source_ref_id, created_at),
        )
        if object_type == "fact":
            con.execute(
                "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                (object_id, source_ref_id, created_at),
            )
        for extra_ref_id, _extra_sensitivity, extra_status, extra_kind in extra_sources:
            if extra_ref_id == source_ref_id:
                continue
            relationship = (
                "supports"
                if object_type == "fact"
                and extra_status == "current"
                and extra_kind != "opaque"
                else "derived_from"
            )
            con.execute(
                "INSERT OR IGNORE INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, ?, 0, ?)",
                (object_id, extra_ref_id, relationship, created_at),
            )
        con.execute(
            "INSERT INTO acceptances(acceptance_id, candidate_id, object_id, acceptance_path, accepted_by, idempotency_key, payload_hash, accepted_at) VALUES (?, NULL, ?, 'manual', 'legacy_local_user', ?, ?, ?)",
            (_stable_id("acceptance", object_id), object_id, f"legacy-promoted:{object_id}", _payload_hash(payload), created_at),
        )
        if not source_current:
            _insert_migration_review(
                con,
                candidate_id=None,
                object_id=object_id,
                source_ref_id=source_ref_id,
                source_status=source_status,
                opened_at=created_at,
            )
        _legacy_map(con, "promoted_objects", object_id, object_type, object_id)


def _migrate_legacy_audits(con: sqlite3.Connection) -> None:
    tables = _table_names(con)
    manual_by_id = _row_map(con, tables, "manual_inputs", "input_id")
    deleted_promotion_audit_object_ids: set[str] = set()
    audit_sources = [
        ("manual_input_audit_events", "input_id", "manual_input"),
        ("rumor_audit_events", "rumor_claim_id", "rumor_claim"),
        ("legacy_candidate_audit_events", "candidate_id", "candidate"),
    ]
    for table, id_column, aggregate_type in audit_sources:
        if table not in tables:
            continue
        for row in con.execute(f'SELECT * FROM "{table}"'):
            event_id = str(row["event_id"])
            event_key = f"{table}:{event_id}"
            payload = json.loads(row["payload_json"] or "{}")
            action = str(row["action"])
            if table == "manual_input_audit_events":
                manual = manual_by_id.get(str(row["input_id"]))
                if manual is not None and str(manual["status"]) == "deleted" and action == "promote":
                    inner_payload = payload.get("payload")
                    normalized_payload = inner_payload if isinstance(inner_payload, dict) else {}
                    payload = {
                        "object_id": payload.get("object_id"),
                        "target_type": payload.get("target_type"),
                        "payload_hash": _payload_hash(normalized_payload),
                    }
                    action = "legacy_target_missing"
                    if payload.get("object_id"):
                        deleted_promotion_audit_object_ids.add(str(payload["object_id"]))
            con.execute(
                """
                INSERT INTO audit_events(
                    aggregate_type, aggregate_id, action, actor_type, actor_id,
                    new_state_json, legacy_event_key, occurred_at
                ) VALUES (?, ?, ?, 'migration', 'legacy', ?, ?, ?)
                """,
                (
                    aggregate_type,
                    str(row[id_column]),
                    action,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    event_key,
                    str(row["event_at"]),
                ),
            )
    if "promoted_objects" in tables and "manual_inputs" in tables:
        for row in con.execute("SELECT * FROM promoted_objects"):
            manual = manual_by_id.get(str(row["derived_from_input_id"]))
            if (
                manual is None
                or str(manual["status"]) != "deleted"
                or str(row["object_id"]) in deleted_promotion_audit_object_ids
            ):
                continue
            event_key = f"promoted_objects:{row['object_id']}:legacy_target_missing"
            payload = json.loads(row["target_payload_json"] or "{}")
            con.execute(
                """
                INSERT INTO audit_events(
                    aggregate_type, aggregate_id, action, actor_type, actor_id,
                    new_state_json, legacy_event_key, occurred_at
                ) VALUES ('manual_input', ?, 'legacy_target_missing', 'migration', 'legacy', ?, ?, ?)
                """,
                (
                    str(row["derived_from_input_id"]),
                    json.dumps(
                        {
                            "object_id": str(row["object_id"]),
                            "target_type": str(row["target_type"]),
                            "payload_hash": _payload_hash(payload),
                        },
                        sort_keys=True,
                    ),
                    event_key,
                    str(row["created_at"]),
                ),
            )


def _insert_source_reference(
    con: sqlite3.Connection,
    *,
    identity: str,
    source_kind: str,
    adapter: str,
    source_item_id: str | None,
    content_hash: str | None,
    citation_label: str,
    sensitivity: str,
    status: str,
    metadata: dict[str, Any],
    created_at: str,
    updated_at: str,
) -> str:
    source_ref_id = _source_id(identity)
    con.execute(
        """
        INSERT INTO source_references(
            source_ref_id, source_kind, adapter, source_item_id, revision_id,
            content_hash, citation_label, sensitivity, status, metadata_json,
            identity_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_ref_id,
            source_kind,
            adapter,
            source_item_id,
            content_hash,
            citation_label,
            sensitivity,
            status,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            identity,
            created_at,
            updated_at,
        ),
    )
    return source_ref_id


def _insert_source_tombstone(con: sqlite3.Connection, identity: str, reason: str, created_at: str) -> None:
    con.execute(
        "INSERT INTO source_tombstones(tombstone_id, source_ref_id, reason, created_by, operation_key, created_at) VALUES (?, ?, ?, 'migration', ?, ?)",
        (
            _stable_id("source_tombstone", identity),
            _source_id(identity),
            reason,
            f"migration:source-tombstone:{identity}",
            created_at,
        ),
    )


def _insert_migration_review(
    con: sqlite3.Connection,
    *,
    candidate_id: str | None,
    object_id: str | None,
    source_ref_id: str,
    source_status: str,
    opened_at: str,
) -> None:
    subject = f"candidate:{candidate_id}" if candidate_id is not None else f"object:{object_id}"
    review_kind = _review_kind(source_status)
    operation_key = f"migration-review:{subject}:{source_ref_id}:{review_kind}"
    con.execute(
        """
        INSERT OR IGNORE INTO review_items(
            review_id, candidate_id, object_id, trigger_source_ref_id,
            review_kind, status, reason, opened_at, operation_key
        ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)
        """,
        (
            _stable_id("review", operation_key),
            candidate_id,
            object_id,
            source_ref_id,
            review_kind,
            review_kind,
            opened_at,
            operation_key,
        ),
    )


def _review_kind(source_status: str) -> str:
    return {
        "stale": "source_stale",
        "missing": "source_missing",
        "revoked": "source_revoked",
        "deleted": "source_deleted",
    }.get(source_status, "source_missing")


def _ensure_legacy_source(
    con: sqlite3.Connection,
    raw_ref: str,
    manual_by_id: dict[str, sqlite3.Row],
    rumor_by_id: dict[str, sqlite3.Row],
) -> tuple[str, str, str, str]:
    identity = _legacy_ref_identity(raw_ref, manual_by_id, rumor_by_id)
    row = con.execute(
        "SELECT source_ref_id, sensitivity, status, source_kind FROM source_references WHERE identity_key = ?",
        (identity,),
    ).fetchone()
    if row is not None:
        return str(row[0]), str(row[1]), str(row[2]), str(row[3])
    source_ref_id = _insert_source_reference(
        con,
        identity=identity,
        source_kind="opaque",
        adapter="legacy",
        source_item_id=None,
        content_hash=None,
        citation_label=f"Legacy source {hashlib.sha256(raw_ref.encode('utf-8')).hexdigest()[:12]}",
        sensitivity="Private",
        status="unknown",
        metadata={"legacy_ref_hash": hashlib.sha256(raw_ref.encode("utf-8")).hexdigest()},
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    return source_ref_id, "Private", "unknown", "opaque"


def _insert_candidate(
    con: sqlite3.Connection,
    *,
    candidate_id: str,
    candidate_type: str,
    summary: str,
    confidence: float,
    confidence_basis: str,
    risk: str,
    sensitivity: str,
    status: str,
    why_suggested: str,
    expires_at: str | None,
    created_at: str,
    updated_at: str,
    handoff_key: str | None,
    resolved_at: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO knowledge_candidates(
            candidate_id, type, summary, confidence, confidence_basis, risk,
            sensitivity, status, confirmation_required, why_suggested,
            expires_at, deferred_until, merged_into_candidate_id, resolved_at,
            handoff_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL, NULL, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            candidate_type,
            summary,
            confidence,
            confidence_basis,
            risk,
            sensitivity,
            status,
            why_suggested,
            expires_at,
            resolved_at,
            handoff_key,
            created_at,
            updated_at,
        ),
    )


def _insert_candidate_link(
    con: sqlite3.Connection,
    candidate_id: str,
    source_ref_id: str,
    relationship: str,
    required: bool,
    legacy_payload: dict[str, Any] | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO candidate_source_links(
            candidate_id, source_ref_id, relationship, required,
            legacy_payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            source_ref_id,
            relationship,
            int(required),
            None if legacy_payload is None else json.dumps(legacy_payload, ensure_ascii=False, sort_keys=True),
            _utc_now(),
        ),
    )


def _legacy_map(con: sqlite3.Connection, legacy_table: str, legacy_id: str, new_type: str, new_id: str) -> None:
    con.execute(
        "INSERT INTO migration_legacy_map(legacy_table, legacy_id, new_type, new_id, metadata_json) VALUES (?, ?, ?, ?, '{}')",
        (legacy_table, legacy_id, new_type, new_id),
    )


def _execute_sql_script(con: sqlite3.Connection, sql: str) -> None:
    statement = ""
    for line in sql.splitlines():
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            text = statement.strip()
            if text:
                con.execute(text)
            statement = ""
    if statement.strip():
        raise sqlite3.OperationalError("incomplete migration statement")


def _table_names(con: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def _row_map(
    con: sqlite3.Connection,
    tables: set[str],
    table: str,
    key: str,
) -> dict[str, sqlite3.Row]:
    if table not in tables:
        return {}
    return {str(row[key]): row for row in con.execute(f'SELECT * FROM "{table}"')}


def _source_id(identity: str) -> str:
    return _stable_id("source", identity)


def _stable_id(prefix: str, material: str) -> str:
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_confidence(value: Any, *, default: float) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, str) and value in {"low", "unverified"}:
        return 0.25
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise sqlite3.IntegrityError(f"unknown confidence: {value}") from exc
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise sqlite3.IntegrityError(f"invalid confidence: {value}")
    return number


def _normalize_risk(value: Any, sensitivity: str, candidate_type: str) -> str:
    if value in {"low", "medium", "high"}:
        return str(value)
    if sensitivity in {"Sensitive", "Restricted"} or candidate_type == "relationship":
        return "high"
    return "medium"


def _max_sensitivity(values: list[str]) -> str:
    order = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
    return max(values, key=order.index)


def _task_status(value: Any) -> str:
    return str(value) if value in {"open", "in_progress", "completed", "cancelled"} else "open"


def _event_status(value: Any) -> str:
    return str(value) if value in {"scheduled", "occurred", "cancelled"} else "scheduled"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_expected() -> dict[str, int]:
    return {
        "candidates": 0,
        "source_references": 0,
        "source_tombstones": 0,
        "canonical_objects": 0,
        "review_items": 0,
    }


def _empty_identity_digests() -> dict[str, str]:
    empty = _digest(set())
    return {
        "candidates": empty,
        "source_references": empty,
        "source_tombstones": empty,
        "canonical_objects": empty,
        "review_items": empty,
        "candidate_source_links": empty,
        "object_source_links": empty,
        "legacy_audit_events": empty,
    }


def _rows(con: sqlite3.Connection, tables: set[str], table: str) -> list[sqlite3.Row]:
    if table not in tables:
        return []
    return list(con.execute(f'SELECT * FROM "{table}"').fetchall())


def _is_unified_candidate_table(con: sqlite3.Connection) -> bool:
    columns = {str(row[1]) for row in con.execute("PRAGMA table_info(knowledge_candidates)")}
    return "status" in columns and "sensitivity" in columns


def _manual_identity(row: sqlite3.Row) -> str:
    input_id = str(row["input_id"])
    content_hash = row["content_hash"]
    if content_hash:
        return f"manual_input:{input_id}:{content_hash}"
    deleted_at = row["deleted_at"] or row["updated_at"]
    return f"manual_input:{input_id}:tombstone:{deleted_at}"


def _legacy_ref_identity(
    raw_ref: str,
    manual_by_id: dict[str, sqlite3.Row],
    rumor_by_id: dict[str, sqlite3.Row],
) -> str:
    if raw_ref.startswith("manual-input:"):
        input_id = raw_ref.split(":", 1)[1]
        if input_id in manual_by_id:
            return _manual_identity(manual_by_id[input_id])
    if raw_ref.startswith("rumor:"):
        rumor_id = raw_ref.split(":", 1)[1]
        if rumor_id in rumor_by_id:
            return f"rumor_claim:{rumor_id}"
    return f"opaque:{hashlib.sha256(raw_ref.encode('utf-8')).hexdigest()}"


def _digest(values: set[str]) -> str:
    material = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_conservation_snapshot(con: sqlite3.Connection) -> dict[str, Any]:
    tables = _table_names(con)
    candidate_ids = {
        str(row[0]) for row in con.execute("SELECT candidate_id FROM knowledge_candidates")
    }
    source_identities = {
        str(row[0]) for row in con.execute("SELECT identity_key FROM source_references")
    }
    tombstone_identities = {
        str(row[0])
        for row in con.execute(
            """
            SELECT s.identity_key
            FROM source_tombstones t
            JOIN source_references s ON s.source_ref_id = t.source_ref_id
            """
        )
    }
    canonical_ids = {
        str(row[0]) for row in con.execute("SELECT object_id FROM canonical_objects")
    }
    review_identities = {
        (
            f"candidate:{row['candidate_id']}"
            if row["candidate_id"] is not None
            else f"object:{row['object_id']}"
        )
        + f"|{row['identity_key']}|{row['review_kind']}"
        for row in con.execute(
            """
            SELECT r.*, s.identity_key
            FROM review_items r
            JOIN source_references s ON s.source_ref_id = r.trigger_source_ref_id
            """
        )
    }
    candidate_links = {
        f"{row['candidate_id']}|{row['identity_key']}|{row['relationship']}|{row['required']}"
        for row in con.execute(
            """
            SELECT l.*, s.identity_key
            FROM candidate_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            """
        )
    }
    object_links = {
        f"{row['object_id']}|{row['identity_key']}|{row['relationship']}|{row['required']}"
        for row in con.execute(
            """
            SELECT l.*, s.identity_key
            FROM object_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            """
        )
    }
    legacy_audits = {
        str(row[0])
        for row in con.execute(
            "SELECT legacy_event_key FROM audit_events WHERE legacy_event_key IS NOT NULL"
        )
    }
    return {
        "identity_digests": {
            "candidates": _digest(candidate_ids),
            "source_references": _digest(source_identities),
            "source_tombstones": _digest(tombstone_identities),
            "canonical_objects": _digest(canonical_ids),
            "review_items": _digest(review_identities),
            "candidate_source_links": _digest(candidate_links),
            "object_source_links": _digest(object_links),
            "legacy_audit_events": _digest(legacy_audits),
        },
        "preserved_table_digests": _preserved_table_digests(con, tables),
    }


def _preserved_table_digests(
    con: sqlite3.Connection,
    tables: set[str],
) -> dict[str, dict[str, Any]]:
    selected = sorted(
        table
        for table in tables
        if table == "embedding_records"
        or table.startswith("manual_inputs_fts")
        or table.startswith("manual_input_vectors")
    )
    result: dict[str, dict[str, Any]] = {}
    for table in selected:
        try:
            rows = con.execute(f'SELECT * FROM "{table}"').fetchall()
            normalized_rows = [
                json.dumps(
                    [_digest_cell(value) for value in row],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for row in rows
            ]
            material = "\n".join(sorted(normalized_rows)).encode("utf-8")
            result[table] = {
                "count": len(rows),
                "sha256": hashlib.sha256(material).hexdigest(),
            }
        except sqlite3.Error as exc:
            schema = con.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?",
                (table,),
            ).fetchone()
            result[table] = {
                "count": None,
                "sha256": hashlib.sha256(str(schema[0] if schema else "").encode("utf-8")).hexdigest(),
                "unavailable": type(exc).__name__,
            }
    return result


def _digest_cell(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"blob_sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
    return value


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
