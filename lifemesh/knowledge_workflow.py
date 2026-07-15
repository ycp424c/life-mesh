from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .candidates import CandidateStore
from .canonical_store import CanonicalStore
from .config import LifemeshConfig
from .database import LifeMeshDatabase


class KnowledgeWorkflowError(RuntimeError):
    pass


class KnowledgeWorkflow:
    def __init__(self, config: LifemeshConfig) -> None:
        self.config = config
        self.database = LifeMeshDatabase(config)
        self.candidates = CandidateStore(config)
        self.canonical = CanonicalStore(config)

    def confirm_candidate(
        self,
        candidate_id: str,
        *,
        user_asserted: bool = False,
        accepted_by: str = "local-user",
    ) -> dict[str, Any]:
        object_id: str
        with self.database.transaction() as con:
            candidate = con.execute(
                "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise KnowledgeWorkflowError(f"Candidate not found: {candidate_id}")
            existing = con.execute(
                "SELECT object_id FROM acceptances WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if existing is not None:
                object_id = str(existing["object_id"])
            else:
                self._require_confirmable(con, candidate)
                source_links = con.execute(
                    """
                    SELECT l.*, s.source_kind, s.status AS source_status
                    FROM candidate_source_links l
                    JOIN source_references s ON s.source_ref_id = l.source_ref_id
                    WHERE l.candidate_id = ?
                    """,
                    (candidate_id,),
                ).fetchall()
                has_support = any(
                    row["relationship"] == "supports"
                    and row["source_status"] == "current"
                    and row["source_kind"] != "opaque"
                    for row in source_links
                )
                if candidate["type"] == "fact" and not has_support and not user_asserted:
                    raise KnowledgeWorkflowError(
                        "Fact Candidate has no current supporting source; confirm again with --user-asserted"
                    )
                object_type = _object_type_for_candidate(str(candidate["type"]))
                object_id = _new_id(object_type)
                now = _utc_now()
                con.execute(
                    "INSERT INTO canonical_objects(object_id, object_type, sensitivity, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (object_id, object_type, candidate["sensitivity"], now, now),
                )
                self._insert_typed_object(con, object_id, object_type, candidate)
                for link in source_links:
                    relationship = str(link["relationship"])
                    if relationship == "legacy_reference":
                        relationship = "derived_from"
                    if relationship == "supports" and (
                        link["source_status"] != "current" or link["source_kind"] == "opaque"
                    ):
                        relationship = "derived_from"
                    con.execute(
                        "INSERT OR IGNORE INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, ?, ?, ?)",
                        (object_id, link["source_ref_id"], relationship, link["required"], now),
                    )
                if candidate["type"] == "fact" and not has_support:
                    assertion_ref_id = self._create_user_assertion(
                        con,
                        statement=str(candidate["summary"]),
                        sensitivity=str(candidate["sensitivity"]),
                        created_at=now,
                    )
                    con.execute(
                        "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                        (object_id, assertion_ref_id, now),
                    )
                acceptance_id = _new_id("acceptance")
                con.execute(
                    """
                    INSERT INTO acceptances(
                        acceptance_id, candidate_id, object_id, acceptance_path,
                        accepted_by, idempotency_key, accepted_at
                    ) VALUES (?, ?, ?, 'user_confirmation', ?, ?, ?)
                    """,
                    (acceptance_id, candidate_id, object_id, accepted_by, f"candidate-confirm:{candidate_id}", now),
                )
                con.execute(
                    "UPDATE knowledge_candidates SET status = 'confirmed', resolved_at = ?, updated_at = ? WHERE candidate_id = ?",
                    (now, now, candidate_id),
                )
                con.execute(
                    "INSERT INTO candidate_decisions(decision_id, candidate_id, decision, actor_type, actor_id, payload_json, decided_at) VALUES (?, ?, 'confirm', 'local_user', ?, ?, ?)",
                    (_new_id("decision"), candidate_id, accepted_by, json.dumps({"object_id": object_id}), now),
                )
                self._audit(con, "candidate", candidate_id, "confirm", {"object_id": object_id}, now)
                self._audit(con, object_type, object_id, "accept", {"candidate_id": candidate_id}, now)
        return {
            "candidate": self.candidates.show(candidate_id),
            "object": self.canonical.show_object(object_id),
        }

    def handoff_manual_input(self, input_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.transaction() as con:
            row = con.execute("SELECT * FROM manual_inputs WHERE input_id = ?", (input_id,)).fetchone()
            if row is None:
                raise KnowledgeWorkflowError(f"Manual Input not found: {input_id}")
            if row["status"] in {"revoked", "deleted"}:
                raise KnowledgeWorkflowError(f"Cannot promote {row['status']} input: {input_id}")
            content_hash = row["content_hash"]
            identity = (
                f"manual_input:{input_id}:{content_hash}"
                if content_hash
                else f"manual_input:{input_id}:tombstone:{row['updated_at']}"
            )
            source_ref_id = self._ensure_source(
                con,
                identity=identity,
                source_kind="manual_input",
                adapter=str(row["source_type"]),
                source_item_id=input_id,
                content_hash=content_hash,
                citation_label=f"Manual Input {input_id}",
                sensitivity=str(row["sensitivity"]),
                status="current",
                metadata={"kind": row["kind"], "status": row["status"]},
                now=str(row["updated_at"]),
            )
            key = f"manual-input:{input_id}:candidate:{_payload_hash(payload)}"
            candidate_id = self._handoff_candidate(
                con,
                payload=payload,
                source_ref_id=source_ref_id,
                sensitivity=str(row["sensitivity"]),
                handoff_key=key,
                why_suggested="manual_input_handoff",
            )
            now = _utc_now()
            con.execute(
                "UPDATE manual_inputs SET status = 'promoted', updated_at = ? WHERE input_id = ?",
                (now, input_id),
            )
            con.execute(
                "INSERT INTO manual_input_audit_events(input_id, action, event_at, payload_json) VALUES (?, 'promote', ?, ?)",
                (input_id, now, json.dumps({"candidate_id": candidate_id, "target_type": "candidate"}, sort_keys=True)),
            )
            self._audit(con, "manual_input", input_id, "candidate_handoff", {"candidate_id": candidate_id}, now)
        return self.candidates.show(candidate_id)

    def promote_manual_input(
        self,
        input_id: str,
        target_type: str,
        payload: dict[str, Any],
        *,
        accepted_by: str = "local-user",
    ) -> dict[str, Any]:
        if target_type not in {"fact", "memory", "task", "event"}:
            raise KnowledgeWorkflowError(f"Unsupported manual promote target: {target_type}")
        object_id: str
        with self.database.transaction() as con:
            row = con.execute("SELECT * FROM manual_inputs WHERE input_id = ?", (input_id,)).fetchone()
            if row is None:
                raise KnowledgeWorkflowError(f"Manual Input not found: {input_id}")
            if row["status"] in {"revoked", "deleted"}:
                raise KnowledgeWorkflowError(f"Cannot promote {row['status']} input: {input_id}")
            content_hash = row["content_hash"]
            identity = (
                f"manual_input:{input_id}:{content_hash}"
                if content_hash
                else f"manual_input:{input_id}:tombstone:{row['updated_at']}"
            )
            source_ref_id = self._ensure_source(
                con,
                identity=identity,
                source_kind="manual_input",
                adapter=str(row["source_type"]),
                source_item_id=input_id,
                content_hash=content_hash,
                citation_label=f"Manual Input {input_id}",
                sensitivity=str(row["sensitivity"]),
                status="current",
                metadata={"kind": row["kind"], "status": row["status"]},
                now=str(row["updated_at"]),
            )
            payload_hash = _payload_hash(payload)
            idempotency_key = f"manual-input:{input_id}:{target_type}:{payload_hash}"
            existing = con.execute(
                "SELECT object_id FROM acceptances WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                object_id = str(existing["object_id"])
            else:
                object_id = _new_id(target_type)
                now = _utc_now()
                con.execute(
                    "INSERT INTO canonical_objects(object_id, object_type, sensitivity, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (object_id, target_type, row["sensitivity"], now, now),
                )
                self._insert_direct_typed_object(con, object_id, target_type, payload)
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'derived_from', 1, ?)",
                    (object_id, source_ref_id, now),
                )
                if target_type == "fact":
                    con.execute(
                        "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                        (object_id, source_ref_id, now),
                    )
                con.execute(
                    """
                    INSERT INTO acceptances(
                        acceptance_id, candidate_id, object_id, acceptance_path,
                        accepted_by, idempotency_key, payload_hash, accepted_at
                    ) VALUES (?, NULL, ?, 'manual', ?, ?, ?, ?)
                    """,
                    (_new_id("acceptance"), object_id, accepted_by, idempotency_key, payload_hash, now),
                )
                con.execute(
                    "UPDATE manual_inputs SET status = 'promoted', updated_at = ? WHERE input_id = ?",
                    (now, input_id),
                )
                con.execute(
                    "INSERT INTO manual_input_audit_events(input_id, action, event_at, payload_json) VALUES (?, 'promote', ?, ?)",
                    (input_id, now, json.dumps({"object_id": object_id, "target_type": target_type}, sort_keys=True)),
                )
                self._audit(con, "manual_input", input_id, "accept", {"object_id": object_id}, now)
                self._audit(con, target_type, object_id, "accept", {"input_id": input_id}, now)
        return self.canonical.show_object(object_id)

    def accept_direct(
        self,
        object_type: str,
        payload: dict[str, Any],
        *,
        sensitivity: str = "Private",
        user_asserted: bool = False,
        source_refs: list[str] | None = None,
        accepted_by: str = "local-user",
    ) -> dict[str, Any]:
        if object_type not in {"fact", "memory", "task", "event"}:
            raise KnowledgeWorkflowError(f"Unsupported direct acceptance type: {object_type}")
        object_id = _new_id(object_type)
        with self.database.transaction() as con:
            resolved_sources = []
            for value in source_refs or []:
                source = con.execute(
                    """
                    SELECT * FROM source_references
                    WHERE source_ref_id = ? OR identity_key = ?
                    """,
                    (value, value),
                ).fetchone()
                if source is None:
                    raise KnowledgeWorkflowError(f"Source reference not found: {value}")
                resolved_sources.append(source)
            valid_supports = [
                row
                for row in resolved_sources
                if row["status"] == "current" and row["source_kind"] != "opaque"
            ]
            if object_type == "fact" and not valid_supports and not user_asserted:
                raise KnowledgeWorkflowError(
                    "fact add requires a current source ref or explicit --user-asserted"
                )
            effective_sensitivity = _max_sensitivity(
                [sensitivity, *(str(row["sensitivity"]) for row in resolved_sources)]
            )
            now = _utc_now()
            con.execute(
                "INSERT INTO canonical_objects(object_id, object_type, sensitivity, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (object_id, object_type, effective_sensitivity, now, now),
            )
            self._insert_direct_typed_object(con, object_id, object_type, payload)
            for source in resolved_sources:
                relationship = "supports" if source in valid_supports and object_type == "fact" else "derived_from"
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, ?, ?, ?)",
                    (object_id, source["source_ref_id"], relationship, int(relationship == "supports"), now),
                )
            if object_type == "fact" and not valid_supports:
                assertion_ref_id = self._create_user_assertion(
                    con,
                    statement=str(payload["statement"]),
                    sensitivity=effective_sensitivity,
                    created_at=now,
                )
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                    (object_id, assertion_ref_id, now),
                )
            con.execute(
                """
                INSERT INTO acceptances(
                    acceptance_id, candidate_id, object_id, acceptance_path,
                    accepted_by, idempotency_key, payload_hash, accepted_at
                ) VALUES (?, NULL, ?, 'manual', ?, ?, ?, ?)
                """,
                (
                    _new_id("acceptance"),
                    object_id,
                    accepted_by,
                    f"direct:{object_type}:{uuid.uuid4().hex}",
                    _payload_hash(payload),
                    now,
                ),
            )
            self._audit(con, object_type, object_id, "accept", {"path": "direct"}, now)
        return self.canonical.show_object(object_id)

    def cascade_manual_input(self, input_id: str, status: str) -> None:
        if status not in {"revoked", "deleted"}:
            raise KnowledgeWorkflowError(f"Unsupported Manual Input source status: {status}")
        with self.database.transaction() as con:
            row = con.execute("SELECT * FROM manual_inputs WHERE input_id = ?", (input_id,)).fetchone()
            if row is None:
                raise KnowledgeWorkflowError(f"Manual Input not found: {input_id}")
            if row["status"] == "deleted" and status == "revoked":
                raise KnowledgeWorkflowError(f"Cannot revoke deleted input: {input_id}")
            now = _utc_now()
            content_hash = row["content_hash"]
            identity = (
                f"manual_input:{input_id}:{content_hash}"
                if content_hash
                else f"manual_input:{input_id}:tombstone:{row['deleted_at'] or row['updated_at']}"
            )
            source = con.execute(
                "SELECT * FROM source_references WHERE identity_key = ?",
                (identity,),
            ).fetchone()
            con.execute(
                "UPDATE manual_inputs SET status = ?, updated_at = ?, tombstone_reason = ? WHERE input_id = ?",
                (status, now, status, input_id),
            )
            con.execute(
                "INSERT INTO manual_input_audit_events(input_id, action, event_at, payload_json) VALUES (?, ?, ?, ?)",
                (input_id, status[:-1] if status == "revoked" else "delete", now, json.dumps({"status": status}, sort_keys=True)),
            )
            if source is None:
                return
            source_ref_id = str(source["source_ref_id"])
            con.execute(
                "UPDATE source_references SET status = ?, updated_at = ? WHERE source_ref_id = ?",
                (status, now, source_ref_id),
            )
            operation_key = f"source:{source_ref_id}:{status}"
            con.execute(
                """
                INSERT OR IGNORE INTO source_tombstones(
                    tombstone_id, source_ref_id, reason, created_by, operation_key, created_at
                ) VALUES (?, ?, ?, 'local_user', ?, ?)
                """,
                (_stable_id("tombstone", operation_key), source_ref_id, status, operation_key, now),
            )
            review_kind = f"source_{status}"
            self._cascade_dependents(con, source_ref_id, review_kind, now)
            self._audit(con, "manual_input", input_id, status, {"source_ref_id": source_ref_id}, now)

    def delete_manual_input(self, input_id: str) -> bool:
        with self.database.transaction() as con:
            row = con.execute("SELECT * FROM manual_inputs WHERE input_id = ?", (input_id,)).fetchone()
            if row is None:
                raise KnowledgeWorkflowError(f"Manual Input not found: {input_id}")
            if row["status"] == "deleted":
                raise KnowledgeWorkflowError(f"Manual Input already deleted: {input_id}")
            now = _utc_now()
            content_hash = row["content_hash"]
            identity = (
                f"manual_input:{input_id}:{content_hash}"
                if content_hash
                else f"manual_input:{input_id}:tombstone:{row['updated_at']}"
            )
            source = con.execute(
                "SELECT * FROM source_references WHERE identity_key = ?",
                (identity,),
            ).fetchone()
            if row["stored_path"]:
                operation_key = f"delete-managed-asset:{input_id}:{row['stored_path']}"
                con.execute(
                    """
                    INSERT OR IGNORE INTO file_operations(
                        operation_id, operation_type, idempotency_key, source_path,
                        status, attempts, created_at
                    ) VALUES (?, 'delete_managed_asset', ?, ?, 'pending', 0, ?)
                    """,
                    (_stable_id("fileop", operation_key), operation_key, row["stored_path"], now),
                )
            con.execute("DELETE FROM embedding_records WHERE input_id = ?", (input_id,))
            con.execute("DELETE FROM manual_input_extractions WHERE input_id = ?", (input_id,))
            con.execute("DELETE FROM manual_inputs_fts WHERE input_id = ?", (input_id,))
            con.execute(
                """
                UPDATE manual_inputs
                SET status = 'deleted', text = NULL, title = NULL, stored_path = NULL,
                    original_path = NULL, asset_sha256 = NULL, media_type = NULL,
                    content_hash = NULL, tags_json = '[]', source_excerpt = NULL,
                    captured_reason = NULL, embedding_status = 'deleted',
                    extraction_status = 'deleted', updated_at = ?, deleted_at = ?,
                    tombstone_reason = 'deleted'
                WHERE input_id = ?
                """,
                (now, now, input_id),
            )
            con.execute(
                "INSERT INTO manual_input_audit_events(input_id, action, event_at, payload_json) VALUES (?, 'delete', ?, ?)",
                (input_id, now, json.dumps({"status": "deleted"}, sort_keys=True)),
            )
            if source is not None:
                source_ref_id = str(source["source_ref_id"])
                con.execute(
                    "UPDATE source_references SET status = 'deleted', updated_at = ? WHERE source_ref_id = ?",
                    (now, source_ref_id),
                )
                operation_key = f"source:{source_ref_id}:deleted"
                con.execute(
                    """
                    INSERT OR IGNORE INTO source_tombstones(
                        tombstone_id, source_ref_id, reason, created_by,
                        operation_key, created_at
                    ) VALUES (?, ?, 'deleted', 'local_user', ?, ?)
                    """,
                    (_stable_id("tombstone", operation_key), source_ref_id, operation_key, now),
                )
                self._cascade_dependents(con, source_ref_id, "source_deleted", now)
                self._audit(con, "manual_input", input_id, "deleted", {"source_ref_id": source_ref_id}, now)
        report = self.database.reconcile_files(apply=True)
        return bool(report["pending_count"])

    def cascade_manual_input_update(self, input_id: str, old_content_hash: str) -> None:
        with self.database.transaction() as con:
            self.cascade_manual_input_update_in_transaction(con, input_id, old_content_hash)

    def cascade_manual_input_update_in_transaction(
        self,
        con: sqlite3.Connection,
        input_id: str,
        old_content_hash: str,
    ) -> None:
        row = con.execute("SELECT * FROM manual_inputs WHERE input_id = ?", (input_id,)).fetchone()
        if row is None:
            raise KnowledgeWorkflowError(f"Manual Input not found: {input_id}")
        old_identity = f"manual_input:{input_id}:{old_content_hash}"
        old_source = con.execute(
            "SELECT * FROM source_references WHERE identity_key = ?",
            (old_identity,),
        ).fetchone()
        if old_source is None:
            return
        now = _utc_now()
        old_source_ref_id = str(old_source["source_ref_id"])
        con.execute(
            "UPDATE source_references SET status = 'stale', updated_at = ? WHERE source_ref_id = ?",
            (now, old_source_ref_id),
        )
        new_hash = row["content_hash"]
        if new_hash:
            self._ensure_source(
                con,
                identity=f"manual_input:{input_id}:{new_hash}",
                source_kind="manual_input",
                adapter=str(row["source_type"]),
                source_item_id=input_id,
                content_hash=str(new_hash),
                citation_label=f"Manual Input {input_id}",
                sensitivity=str(row["sensitivity"]),
                status="current",
                metadata={"kind": row["kind"], "status": row["status"]},
                now=now,
            )
        self._cascade_dependents(con, old_source_ref_id, "source_stale", now)
        self._audit(
            con,
            "manual_input",
            input_id,
            "source_revision_changed",
            {"old_source_ref_id": old_source_ref_id},
            now,
        )

    def _cascade_dependents(
        self,
        con: sqlite3.Connection,
        source_ref_id: str,
        review_kind: str,
        now: str,
    ) -> None:
        for candidate in con.execute(
            "SELECT DISTINCT candidate_id FROM candidate_source_links WHERE source_ref_id = ? AND required = 1",
            (source_ref_id,),
        ).fetchall():
            self._open_review(
                con,
                candidate_id=str(candidate["candidate_id"]),
                object_id=None,
                source_ref_id=source_ref_id,
                review_kind=review_kind,
                now=now,
            )
        for item in con.execute(
            "SELECT DISTINCT object_id FROM object_source_links WHERE source_ref_id = ?",
            (source_ref_id,),
        ).fetchall():
            object_id = str(item["object_id"])
            object_row = con.execute(
                "SELECT object_type FROM canonical_objects WHERE object_id = ?",
                (object_id,),
            ).fetchone()
            if object_row is None:
                continue
            object_type = str(object_row["object_type"])
            if object_type == "fact" and self._fact_requires_review(con, object_id):
                con.execute(
                    "UPDATE canonical_facts SET validity = 'needs_review', review_reason = ?, review_started_at = ? WHERE fact_id = ? AND revocation_status = 'active'",
                    (review_kind, now, object_id),
                )
            elif object_type == "memory":
                con.execute(
                    "UPDATE memories SET status = 'needs_review' WHERE memory_id = ? AND status = 'active'",
                    (object_id,),
                )
            if object_type != "fact" or self._fact_requires_review(con, object_id):
                self._open_review(
                    con,
                    candidate_id=None,
                    object_id=object_id,
                    source_ref_id=source_ref_id,
                    review_kind=review_kind,
                    now=now,
                )

    @staticmethod
    def _fact_requires_review(con: sqlite3.Connection, object_id: str) -> bool:
        rows = con.execute(
            """
            SELECT l.required, s.status, s.source_kind
            FROM object_source_links l
            JOIN source_references s ON s.source_ref_id = l.source_ref_id
            WHERE l.object_id = ? AND l.relationship = 'supports'
            """,
            (object_id,),
        ).fetchall()
        current = [
            row
            for row in rows
            if row["status"] == "current" and row["source_kind"] != "opaque"
        ]
        required_invalid = any(
            row["required"]
            and (row["status"] != "current" or row["source_kind"] == "opaque")
            for row in rows
        )
        return not current or required_invalid

    def revalidate_fact(
        self,
        fact_id: str,
        *,
        user_asserted: bool = False,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as con:
            fact = con.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,)).fetchone()
            if fact is None:
                raise KnowledgeWorkflowError(f"Canonical Fact not found: {fact_id}")
            if fact["revocation_status"] == "revoked":
                raise KnowledgeWorkflowError(f"Cannot revalidate revoked Fact: {fact_id}")
            object_row = con.execute(
                "SELECT sensitivity FROM canonical_objects WHERE object_id = ?",
                (fact_id,),
            ).fetchone()
            supports: list[str] = []
            for value in source_refs or []:
                source = con.execute(
                    "SELECT * FROM source_references WHERE source_ref_id = ? OR identity_key = ?",
                    (value, value),
                ).fetchone()
                if source is None:
                    raise KnowledgeWorkflowError(f"Source reference not found: {value}")
                if source["status"] != "current" or source["source_kind"] == "opaque":
                    raise KnowledgeWorkflowError(f"Source reference is not current supporting evidence: {value}")
                supports.append(str(source["source_ref_id"]))
            now = _utc_now()
            if user_asserted:
                supports.append(
                    self._create_user_assertion(
                        con,
                        statement=str(fact["statement"]),
                        sensitivity=str(object_row["sensitivity"]),
                        created_at=now,
                    )
                )
            if not supports:
                raise KnowledgeWorkflowError(
                    "fact revalidate requires a current source ref or explicit --user-asserted"
                )
            con.execute(
                """
                UPDATE object_source_links
                SET required = 0
                WHERE object_id = ? AND relationship = 'supports'
                  AND source_ref_id IN (
                      SELECT source_ref_id FROM source_references WHERE status != 'current'
                  )
                """,
                (fact_id,),
            )
            for source_ref_id in supports:
                con.execute(
                    "INSERT OR REPLACE INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                    (fact_id, source_ref_id, now),
                )
            con.execute(
                "UPDATE canonical_facts SET validity = 'valid', review_reason = NULL, review_started_at = NULL, reviewed_at = ? WHERE fact_id = ?",
                (now, fact_id),
            )
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'revalidate' WHERE object_id = ? AND status = 'open'",
                (now, fact_id),
            )
            self._audit(con, "fact", fact_id, "revalidate", {"source_refs": supports}, now)
        return self.canonical.show_fact(fact_id)

    def revise_fact(
        self,
        fact_id: str,
        *,
        statement: str,
        user_asserted: bool = False,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        new_fact_id = _new_id("fact")
        with self.database.transaction() as con:
            fact = con.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,)).fetchone()
            base = con.execute("SELECT * FROM canonical_objects WHERE object_id = ?", (fact_id,)).fetchone()
            if fact is None or base is None:
                raise KnowledgeWorkflowError(f"Canonical Fact not found: {fact_id}")
            if fact["revocation_status"] == "revoked" or fact["validity"] == "superseded":
                raise KnowledgeWorkflowError(f"Cannot revise inactive Fact: {fact_id}")
            text = statement.strip()
            if not text:
                raise KnowledgeWorkflowError("revised Fact statement is required")
            now = _utc_now()
            supports: list[str] = []
            for value in source_refs or []:
                source = con.execute(
                    "SELECT * FROM source_references WHERE source_ref_id = ? OR identity_key = ?",
                    (value, value),
                ).fetchone()
                if source is None or source["status"] != "current" or source["source_kind"] == "opaque":
                    raise KnowledgeWorkflowError(f"Source reference is not current supporting evidence: {value}")
                supports.append(str(source["source_ref_id"]))
            if user_asserted:
                supports.append(
                    self._create_user_assertion(
                        con,
                        statement=text,
                        sensitivity=str(base["sensitivity"]),
                        created_at=now,
                    )
                )
            if not supports:
                raise KnowledgeWorkflowError(
                    "fact revise requires a current source ref or explicit --user-asserted"
                )
            con.execute(
                "INSERT INTO canonical_objects(object_id, object_type, sensitivity, created_at, updated_at) VALUES (?, 'fact', ?, ?, ?)",
                (new_fact_id, base["sensitivity"], now, now),
            )
            con.execute(
                "INSERT INTO canonical_facts(fact_id, statement, confidence, risk, validity, revocation_status) VALUES (?, ?, ?, ?, 'valid', 'active')",
                (new_fact_id, text, fact["confidence"], fact["risk"]),
            )
            for source_ref_id in supports:
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                    (new_fact_id, source_ref_id, now),
                )
            con.execute(
                "UPDATE canonical_facts SET validity = 'superseded', superseded_by_fact_id = ?, reviewed_at = ? WHERE fact_id = ?",
                (new_fact_id, now, fact_id),
            )
            operation_key = f"fact-revise:{fact_id}:{new_fact_id}"
            con.execute(
                "INSERT INTO object_tombstones(tombstone_id, object_id, reason, replacement_object_id, operation_key, created_at) VALUES (?, ?, 'revised', ?, ?, ?)",
                (_stable_id("tombstone", operation_key), fact_id, new_fact_id, operation_key, now),
            )
            con.execute(
                "INSERT INTO acceptances(acceptance_id, candidate_id, object_id, acceptance_path, accepted_by, idempotency_key, payload_hash, accepted_at) VALUES (?, NULL, ?, 'manual', 'local-user', ?, ?, ?)",
                (_new_id("acceptance"), new_fact_id, f"fact-revise:{fact_id}:{_payload_hash({'statement': text})}", _payload_hash({"statement": text}), now),
            )
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'revise' WHERE object_id = ? AND status = 'open'",
                (now, fact_id),
            )
            self._audit(con, "fact", fact_id, "revise", {"replacement_object_id": new_fact_id}, now)
            self._audit(con, "fact", new_fact_id, "accept", {"replaces": fact_id}, now)
        return self.canonical.show_fact(new_fact_id)

    def invalidate_fact(self, fact_id: str, *, reason: str | None = None) -> dict[str, Any]:
        with self.database.transaction() as con:
            fact = con.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,)).fetchone()
            if fact is None:
                raise KnowledgeWorkflowError(f"Canonical Fact not found: {fact_id}")
            now = _utc_now()
            con.execute(
                "UPDATE canonical_facts SET validity = 'invalid', review_reason = ?, reviewed_at = ? WHERE fact_id = ?",
                (reason or "invalidated", now, fact_id),
            )
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'invalidate' WHERE object_id = ? AND status = 'open'",
                (now, fact_id),
            )
            self._audit(con, "fact", fact_id, "invalidate", {"reason": reason}, now)
        return self.canonical.show_fact(fact_id)

    def revoke_object(self, object_id: str, *, reason: str | None = None) -> dict[str, Any]:
        with self.database.transaction() as con:
            base = con.execute("SELECT * FROM canonical_objects WHERE object_id = ?", (object_id,)).fetchone()
            if base is None:
                raise KnowledgeWorkflowError(f"Canonical object not found: {object_id}")
            object_type = str(base["object_type"])
            now = _utc_now()
            if object_type == "fact":
                con.execute(
                    "UPDATE canonical_facts SET revocation_status = 'revoked', reviewed_at = ? WHERE fact_id = ?",
                    (now, object_id),
                )
            elif object_type == "memory":
                con.execute("UPDATE memories SET status = 'revoked' WHERE memory_id = ?", (object_id,))
            elif object_type == "task":
                con.execute("UPDATE tasks SET task_status = 'cancelled' WHERE task_id = ?", (object_id,))
            elif object_type == "event":
                con.execute("UPDATE events SET event_status = 'cancelled' WHERE event_id = ?", (object_id,))
            operation_key = f"object-revoke:{object_id}"
            con.execute(
                "INSERT OR IGNORE INTO object_tombstones(tombstone_id, object_id, reason, operation_key, created_at) VALUES (?, ?, ?, ?, ?)",
                (_stable_id("tombstone", operation_key), object_id, reason or "revoked", operation_key, now),
            )
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = 'revoke' WHERE object_id = ? AND status = 'open'",
                (now, object_id),
            )
            self._audit(con, object_type, object_id, "revoke", {"reason": reason}, now)
        return self.canonical.show_object(object_id)

    def resolve_review(self, review_id: str, *, action: str) -> dict[str, Any]:
        if action not in {"keep", "revoke"}:
            raise KnowledgeWorkflowError("review resolution action must be keep or revoke")
        object_id: str
        with self.database.transaction() as con:
            review = con.execute("SELECT * FROM review_items WHERE review_id = ?", (review_id,)).fetchone()
            if review is None:
                raise KnowledgeWorkflowError(f"Review not found: {review_id}")
            if review["status"] != "open":
                raise KnowledgeWorkflowError(f"Review is not open: {review_id}")
            if review["object_id"] is None:
                raise KnowledgeWorkflowError(
                    "Candidate reviews must be resolved by edit, merge, or discard"
                )
            object_id = str(review["object_id"])
            base = con.execute("SELECT * FROM canonical_objects WHERE object_id = ?", (object_id,)).fetchone()
            if base is None:
                raise KnowledgeWorkflowError(f"Canonical object not found: {object_id}")
            now = _utc_now()
            if action == "keep":
                assertion_text = self._object_assertion_text(con, object_id, str(base["object_type"]))
                assertion_ref_id = self._create_user_assertion(
                    con,
                    statement=assertion_text,
                    sensitivity=str(base["sensitivity"]),
                    created_at=now,
                )
                con.execute(
                    "UPDATE object_source_links SET required = 0 WHERE object_id = ? AND source_ref_id = ?",
                    (object_id, review["trigger_source_ref_id"]),
                )
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 1, ?)",
                    (object_id, assertion_ref_id, now),
                )
                if base["object_type"] == "memory":
                    con.execute("UPDATE memories SET status = 'active' WHERE memory_id = ?", (object_id,))
                elif base["object_type"] == "fact":
                    con.execute(
                        "UPDATE canonical_facts SET validity = 'valid', review_reason = NULL, review_started_at = NULL, reviewed_at = ? WHERE fact_id = ?",
                        (now, object_id),
                    )
            else:
                self._revoke_in_transaction(con, object_id, str(base["object_type"]), "review revoked", now)
            con.execute(
                "UPDATE review_items SET status = 'resolved', resolved_at = ?, resolution = ? WHERE review_id = ?",
                (now, action, review_id),
            )
            self._audit(con, "review", review_id, "resolve", {"action": action}, now)
        return {
            "review": self.canonical.show_review(review_id),
            "object": self.canonical.show_object(object_id),
        }

    def set_business_status(self, object_id: str, *, action: str) -> dict[str, Any]:
        with self.database.transaction() as con:
            base = con.execute("SELECT * FROM canonical_objects WHERE object_id = ?", (object_id,)).fetchone()
            if base is None:
                raise KnowledgeWorkflowError(f"Canonical object not found: {object_id}")
            object_type = str(base["object_type"])
            now = _utc_now()
            if object_type == "task" and action == "close":
                con.execute("UPDATE tasks SET task_status = 'completed' WHERE task_id = ?", (object_id,))
            elif object_type == "event" and action == "cancel":
                con.execute("UPDATE events SET event_status = 'cancelled' WHERE event_id = ?", (object_id,))
            else:
                raise KnowledgeWorkflowError(f"Cannot {action} canonical {object_type}: {object_id}")
            con.execute("UPDATE canonical_objects SET updated_at = ? WHERE object_id = ?", (now, object_id))
            self._audit(con, object_type, object_id, action, {}, now)
        return self.canonical.show_object(object_id)

    def _object_assertion_text(self, con: sqlite3.Connection, object_id: str, object_type: str) -> str:
        query = {
            "fact": ("canonical_facts", "fact_id", "statement"),
            "memory": ("memories", "memory_id", "text"),
            "task": ("tasks", "task_id", "title"),
            "event": ("events", "event_id", "title"),
        }[object_type]
        row = con.execute(
            f"SELECT {query[2]} FROM {query[0]} WHERE {query[1]} = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            raise KnowledgeWorkflowError(f"Canonical {object_type} row missing: {object_id}")
        return str(row[0])

    def _revoke_in_transaction(
        self,
        con: sqlite3.Connection,
        object_id: str,
        object_type: str,
        reason: str,
        now: str,
    ) -> None:
        if object_type == "fact":
            con.execute("UPDATE canonical_facts SET revocation_status = 'revoked', reviewed_at = ? WHERE fact_id = ?", (now, object_id))
        elif object_type == "memory":
            con.execute("UPDATE memories SET status = 'revoked' WHERE memory_id = ?", (object_id,))
        elif object_type == "task":
            con.execute("UPDATE tasks SET task_status = 'cancelled' WHERE task_id = ?", (object_id,))
        elif object_type == "event":
            con.execute("UPDATE events SET event_status = 'cancelled' WHERE event_id = ?", (object_id,))
        operation_key = f"object-revoke:{object_id}"
        con.execute(
            "INSERT OR IGNORE INTO object_tombstones(tombstone_id, object_id, reason, operation_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (_stable_id("tombstone", operation_key), object_id, reason, operation_key, now),
        )

    def _open_review(
        self,
        con: sqlite3.Connection,
        *,
        candidate_id: str | None,
        object_id: str | None,
        source_ref_id: str,
        review_kind: str,
        now: str,
    ) -> None:
        subject_type = "candidate" if candidate_id else "object"
        subject_id = candidate_id or object_id
        operation_key = f"review:{subject_type}:{subject_id}:{source_ref_id}:{review_kind}"
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
                now,
                operation_key,
            ),
        )

    def handoff_rumor_claim(self, rumor_claim_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.transaction() as con:
            row = con.execute(
                "SELECT * FROM rumor_claims WHERE rumor_claim_id = ?",
                (rumor_claim_id,),
            ).fetchone()
            if row is None:
                raise KnowledgeWorkflowError(f"RumorClaim not found: {rumor_claim_id}")
            if row["status"] in {"dismissed", "expired"}:
                raise KnowledgeWorkflowError(f"Cannot promote {row['status']} RumorClaim: {rumor_claim_id}")
            envelope = json.loads(row["source_envelope_json"] or "{}")
            identity = f"rumor_claim:{rumor_claim_id}"
            source_ref_id = self._ensure_source(
                con,
                identity=identity,
                source_kind="rumor_claim",
                adapter=str(envelope.get("source_adapter") or "unknown"),
                source_item_id=rumor_claim_id,
                content_hash=None,
                citation_label=f"RumorClaim {rumor_claim_id}",
                sensitivity=str(row["sensitivity"]),
                status="current",
                metadata={"claim_type": row["claim_type"], "assessment": row["assessment"], "status": row["status"]},
                now=str(row["updated_at"]),
            )
            candidate_id = self._handoff_candidate(
                con,
                payload=payload,
                source_ref_id=source_ref_id,
                sensitivity=str(row["sensitivity"]),
                handoff_key=f"rumor:{rumor_claim_id}:candidate",
                why_suggested="rumor_handoff",
            )
            now = _utc_now()
            con.execute(
                "UPDATE rumor_claims SET status = 'candidate_created', updated_at = ? WHERE rumor_claim_id = ?",
                (now, rumor_claim_id),
            )
            con.execute(
                "INSERT INTO rumor_audit_events(rumor_claim_id, action, event_at, payload_json) VALUES (?, 'promote', ?, ?)",
                (rumor_claim_id, now, json.dumps({"candidate_id": candidate_id, "target_type": "candidate"}, sort_keys=True)),
            )
            self._audit(con, "rumor_claim", rumor_claim_id, "candidate_handoff", {"candidate_id": candidate_id}, now)
        return self.candidates.show(candidate_id)

    def _handoff_candidate(
        self,
        con: sqlite3.Connection,
        *,
        payload: dict[str, Any],
        source_ref_id: str,
        sensitivity: str,
        handoff_key: str,
        why_suggested: str,
    ) -> str:
        existing = con.execute(
            "SELECT candidate_id FROM knowledge_candidates WHERE handoff_key = ?",
            (handoff_key,),
        ).fetchone()
        if existing is not None:
            return str(existing["candidate_id"])
        candidate_type = str(payload.get("type", "")).strip()
        if candidate_type not in {"fact", "preference", "relationship", "task", "decision"}:
            raise KnowledgeWorkflowError(f"Unsupported Candidate type: {candidate_type}")
        summary = str(payload.get("statement") or payload.get("summary") or "").strip()
        if not summary:
            raise KnowledgeWorkflowError("Candidate statement is required")
        confidence = _normalize_confidence(payload.get("confidence"), default=0.5)
        risk = _normalize_risk(payload.get("risk"), sensitivity, candidate_type)
        now = _utc_now()
        candidate_id = _new_id("candidate")
        con.execute(
            """
            INSERT INTO knowledge_candidates(
                candidate_id, type, summary, confidence, confidence_basis, risk,
                sensitivity, status, confirmation_required, why_suggested,
                expires_at, handoff_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                candidate_type,
                summary,
                confidence,
                "source_handoff",
                risk,
                sensitivity,
                why_suggested,
                payload.get("expires_at"),
                handoff_key,
                now,
                now,
            ),
        )
        con.execute(
            "INSERT INTO candidate_source_links(candidate_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'derived_from', 1, ?)",
            (candidate_id, source_ref_id, now),
        )
        self._audit(con, "candidate", candidate_id, "handoff", {"handoff_key": handoff_key}, now)
        return candidate_id

    def _ensure_source(
        self,
        con: sqlite3.Connection,
        *,
        identity: str,
        source_kind: str,
        adapter: str,
        source_item_id: str,
        content_hash: str | None,
        citation_label: str,
        sensitivity: str,
        status: str,
        metadata: dict[str, Any],
        now: str,
    ) -> str:
        existing = con.execute(
            "SELECT source_ref_id FROM source_references WHERE identity_key = ?",
            (identity,),
        ).fetchone()
        if existing is not None:
            return str(existing["source_ref_id"])
        source_ref_id = _new_id("source")
        con.execute(
            """
            INSERT INTO source_references(
                source_ref_id, source_kind, adapter, source_item_id, content_hash,
                citation_label, sensitivity, status, metadata_json, identity_key,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now,
                now,
            ),
        )
        return source_ref_id

    def _require_confirmable(self, con: sqlite3.Connection, candidate: sqlite3.Row) -> None:
        if candidate["status"] not in {"pending", "deferred"}:
            raise KnowledgeWorkflowError(f"Cannot confirm {candidate['status']} Candidate: {candidate['candidate_id']}")
        expires_at = _parse_datetime(candidate["expires_at"])
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise KnowledgeWorkflowError(f"Cannot confirm expired Candidate: {candidate['candidate_id']}")
        open_review = con.execute(
            "SELECT 1 FROM review_items WHERE candidate_id = ? AND status = 'open'",
            (candidate["candidate_id"],),
        ).fetchone()
        if open_review is not None:
            raise KnowledgeWorkflowError(f"Candidate has an open review: {candidate['candidate_id']}")

    def _insert_typed_object(
        self,
        con: sqlite3.Connection,
        object_id: str,
        object_type: str,
        candidate: sqlite3.Row,
    ) -> None:
        if object_type == "fact":
            con.execute(
                "INSERT INTO canonical_facts(fact_id, statement, confidence, risk, validity, revocation_status) VALUES (?, ?, ?, ?, 'valid', 'active')",
                (object_id, candidate["summary"], candidate["confidence"], candidate["risk"]),
            )
        elif object_type == "memory":
            con.execute(
                "INSERT INTO memories(memory_id, text, memory_type, confidence, confirmation_status, status, expires_at) VALUES (?, ?, 'inferred', ?, 'confirmed', 'active', ?)",
                (object_id, candidate["summary"], candidate["confidence"], candidate["expires_at"]),
            )
        elif object_type == "task":
            con.execute(
                "INSERT INTO tasks(task_id, title, task_status) VALUES (?, ?, 'open')",
                (object_id, candidate["summary"]),
            )
        else:
            raise KnowledgeWorkflowError(f"Unsupported Candidate target: {object_type}")

    def _insert_direct_typed_object(
        self,
        con: sqlite3.Connection,
        object_id: str,
        object_type: str,
        payload: dict[str, Any],
    ) -> None:
        if object_type == "fact":
            con.execute(
                "INSERT INTO canonical_facts(fact_id, statement, confidence, risk, validity, revocation_status) VALUES (?, ?, ?, ?, 'valid', 'active')",
                (
                    object_id,
                    str(payload["statement"]),
                    _normalize_confidence(payload.get("confidence"), default=0.5),
                    _normalize_risk(payload.get("risk"), "Private", "fact"),
                ),
            )
        elif object_type == "memory":
            con.execute(
                "INSERT INTO memories(memory_id, text, memory_type, scope, confidence, confirmation_status, status, expires_at) VALUES (?, ?, 'explicit', ?, ?, 'manual', 'active', ?)",
                (object_id, str(payload["text"]), payload.get("scope"), _normalize_confidence(payload.get("confidence"), default=1.0), payload.get("expires_at")),
            )
        elif object_type == "task":
            status = payload.get("status") if payload.get("status") in {"open", "in_progress", "completed", "cancelled"} else "open"
            con.execute(
                "INSERT INTO tasks(task_id, title, description, due_at, task_status) VALUES (?, ?, ?, ?, ?)",
                (object_id, str(payload["title"]), payload.get("description"), payload.get("due_at"), status),
            )
        elif object_type == "event":
            status = payload.get("status") if payload.get("status") in {"scheduled", "occurred", "cancelled"} else "scheduled"
            con.execute(
                "INSERT INTO events(event_id, title, starts_at, ends_at, timezone, event_status) VALUES (?, ?, ?, ?, ?, ?)",
                (object_id, str(payload["title"]), str(payload["starts_at"]), payload.get("ends_at"), payload.get("timezone"), status),
            )
        else:
            raise KnowledgeWorkflowError(f"Unsupported canonical object type: {object_type}")

    def _create_user_assertion(
        self,
        con: sqlite3.Connection,
        *,
        statement: str,
        sensitivity: str,
        created_at: str,
    ) -> str:
        assertion_id = _new_id("assertion")
        statement_hash = hashlib.sha256(statement.encode("utf-8")).hexdigest()
        identity = f"user_assertion:{assertion_id}:{statement_hash}"
        source_ref_id = _new_id("source")
        con.execute(
            """
            INSERT INTO source_references(
                source_ref_id, source_kind, adapter, source_item_id, content_hash,
                citation_label, sensitivity, status, metadata_json, identity_key,
                created_at, updated_at
            ) VALUES (?, 'user_assertion', 'local_cli', ?, ?, ?, ?, 'current', '{}', ?, ?, ?)
            """,
            (
                source_ref_id,
                assertion_id,
                statement_hash,
                f"User assertion {assertion_id}",
                sensitivity,
                identity,
                created_at,
                created_at,
            ),
        )
        return source_ref_id

    def _audit(
        self,
        con: sqlite3.Connection,
        aggregate_type: str,
        aggregate_id: str,
        action: str,
        state: dict[str, Any],
        occurred_at: str,
    ) -> None:
        con.execute(
            "INSERT INTO audit_events(aggregate_type, aggregate_id, action, actor_type, actor_id, new_state_json, occurred_at) VALUES (?, ?, ?, 'local_user', 'local-user', ?, ?)",
            (aggregate_type, aggregate_id, action, json.dumps(state, ensure_ascii=False, sort_keys=True), occurred_at),
        )


def _object_type_for_candidate(candidate_type: str) -> str:
    if candidate_type == "fact":
        return "fact"
    if candidate_type == "task":
        return "task"
    if candidate_type in {"preference", "relationship", "decision"}:
        return "memory"
    raise KnowledgeWorkflowError(f"Unsupported Candidate type: {candidate_type}")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payload_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_confidence(value: Any, *, default: float) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, str) and value in {"low", "unverified"}:
        return 0.25
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise KnowledgeWorkflowError(f"Unknown confidence: {value}") from exc
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise KnowledgeWorkflowError("Candidate confidence must be between 0 and 1")
    return number


def _normalize_risk(value: Any, sensitivity: str, candidate_type: str) -> str:
    if value in {"low", "medium", "high"}:
        return str(value)
    if sensitivity in {"Sensitive", "Restricted"} or candidate_type == "relationship":
        return "high"
    return "medium"


def _max_sensitivity(values: list[str]) -> str:
    order = ["Public", "Internal", "Private", "Sensitive", "Restricted"]
    try:
        return max(values, key=order.index)
    except ValueError as exc:
        raise KnowledgeWorkflowError("Unknown sensitivity") from exc


def _stable_id(prefix: str, material: str) -> str:
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"
