from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lifemesh import cli
from lifemesh.config import load_config
from lifemesh.database import LifeMeshDatabase
from lifemesh.knowledge_workflow import KnowledgeWorkflow, KnowledgeWorkflowError


FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "obsidian-vault"


class UnifiedWorkflowCliTest(unittest.TestCase):
    def test_candidate_can_be_deferred_and_resumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            candidate_id = self.run_json(
                ["candidate", "add", "Review unified workflow", "--type", "task"],
                home,
            )["candidate_id"]

            deferred = self.run_json(
                [
                    "candidate",
                    "defer",
                    candidate_id,
                    "--until",
                    "2030-01-02T03:04:05+08:00",
                    "--reason",
                    "wait for more context",
                ],
                home,
            )
            resumed = self.run_json(["candidate", "resume", candidate_id], home)

            self.assertEqual(deferred["stored_status"], "deferred")
            self.assertEqual(deferred["deferred_until"], "2030-01-01T19:04:05Z")
            self.assertEqual(deferred["decisions"][-1]["decision"], "defer")
            self.assertEqual(resumed["status"], "pending")
            self.assertIsNone(resumed["deferred_until"])
            self.assertEqual(resumed["decisions"][-1]["decision"], "resume")

    def test_candidate_merge_preserves_sources_and_max_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            winner_id = self.run_json(
                [
                    "candidate",
                    "add",
                    "Primary preference",
                    "--type",
                    "preference",
                    "--source-ref",
                    "source:primary",
                ],
                home,
            )["candidate_id"]
            loser_id = self.run_json(
                [
                    "candidate",
                    "add",
                    "Duplicate preference",
                    "--type",
                    "preference",
                    "--source-ref",
                    "source:duplicate",
                    "--sensitivity",
                    "Sensitive",
                ],
                home,
            )["candidate_id"]

            winner = self.run_json(
                ["candidate", "merge", winner_id, loser_id, "--reason", "same preference"],
                home,
            )
            loser = self.run_json(["candidate", "show", loser_id], home)

            self.assertEqual(winner["sensitivity"], "Sensitive")
            self.assertEqual(len(winner["source_links"]), 2)
            self.assertEqual(loser["status"], "merged")
            self.assertEqual(loser["merged_into_candidate_id"], winner_id)

    def test_candidate_edit_updates_reviewable_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            candidate_id = self.run_json(
                ["candidate", "add", "Draft task", "--type", "task"],
                home,
            )["candidate_id"]

            edited = self.run_json(
                [
                    "candidate",
                    "edit",
                    candidate_id,
                    "--summary",
                    "Remember this decision",
                    "--type",
                    "decision",
                    "--confidence",
                    "0.8",
                    "--risk",
                    "high",
                    "--sensitivity",
                    "Sensitive",
                    "--expires-at",
                    "2030-01-02T03:04:05+08:00",
                ],
                home,
            )

            self.assertEqual(edited["summary"], "Remember this decision")
            self.assertEqual(edited["type"], "decision")
            self.assertEqual(edited["confidence"], 0.8)
            self.assertEqual(edited["risk"], "high")
            self.assertEqual(edited["sensitivity"], "Sensitive")
            self.assertEqual(edited["expires_at"], "2030-01-01T19:04:05Z")
            self.assertEqual(edited["decisions"][-1]["decision"], "edit")

    def test_fact_candidate_requires_support_or_explicit_user_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            candidate_id = self.run_json(
                ["candidate", "add", "The project uses a unified write model", "--type", "fact"],
                home,
            )["candidate_id"]

            rejected = self.run_cli(["candidate", "confirm", candidate_id], home)
            confirmed = self.run_json(
                ["candidate", "confirm", candidate_id, "--user-asserted"],
                home,
            )
            fact = self.run_json(["fact", "show", confirmed["object"]["object_id"]], home)
            candidate = self.run_json(["candidate", "show", candidate_id], home)

            self.assertEqual(rejected.returncode, 2)
            self.assertIn("--user-asserted", rejected.stderr)
            self.assertEqual(candidate["status"], "confirmed")
            self.assertEqual(fact["statement"], "The project uses a unified write model")
            self.assertEqual(fact["validity"], "valid")
            self.assertEqual(fact["revocation_status"], "active")
            self.assertEqual(fact["acceptance"]["acceptance_path"], "user_confirmation")
            self.assertEqual(fact["source_links"][0]["source_kind"], "user_assertion")
            self.assertEqual(fact["source_links"][0]["relationship"], "supports")

    def test_candidate_type_maps_to_task_or_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            task_candidate = self.run_json(
                ["candidate", "add", "Ship unified workflow", "--type", "task"],
                home,
            )["candidate_id"]
            memory_candidate = self.run_json(
                ["candidate", "add", "Prefer explicit provenance", "--type", "preference"],
                home,
            )["candidate_id"]

            task_result = self.run_json(["candidate", "confirm", task_candidate], home)
            memory_result = self.run_json(["candidate", "confirm", memory_candidate], home)
            task = self.run_json(["task", "show", task_result["object"]["object_id"]], home)
            memory = self.run_json(["memory", "show", memory_result["object"]["object_id"]], home)

            self.assertEqual(task["object_type"], "task")
            self.assertEqual(task["title"], "Ship unified workflow")
            self.assertEqual(task["task_status"], "open")
            self.assertEqual(memory["object_type"], "memory")
            self.assertEqual(memory["text"], "Prefer explicit provenance")
            self.assertEqual(memory["confirmation_status"], "confirmed")
            self.assertEqual(memory["status"], "active")

    def test_manual_input_and_rumor_handoff_share_candidate_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "manual unified source"],
                home,
            )["input_id"]
            manual = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "manual unified candidate",
                    "--type",
                    "fact",
                ],
                home,
            )
            rumor_id = self.run_json(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "rumor unified source",
                    "--claim-type",
                    "factual_claim",
                    "--user-relevance",
                    "medium",
                    "--impact",
                    "low",
                ],
                home,
            )["rumor_claim_id"]
            rumor = self.run_json(
                [
                    "rumor",
                    "promote",
                    rumor_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "rumor unified candidate",
                    "--type",
                    "fact",
                ],
                home,
            )
            candidates = self.run_json(["candidate", "list"], home)

            self.assertEqual(
                {item["candidate_id"] for item in candidates},
                {manual["object_id"], rumor["object_id"]},
            )
            self.assertEqual(manual["candidate"]["source_links"][0]["source_kind"], "manual_input")
            self.assertEqual(rumor["candidate"]["source_links"][0]["source_kind"], "rumor_claim")

    def test_manual_input_direct_fact_promotion_uses_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "fact source"],
                home,
            )["input_id"]

            promoted = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "fact",
                    "--statement",
                    "Manual promotion is unified",
                ],
                home,
            )
            fact = self.run_json(["fact", "show", promoted["object_id"]], home)

            self.assertEqual(fact["acceptance"]["acceptance_path"], "manual")
            self.assertIsNone(fact["acceptance"]["candidate_id"])
            self.assertEqual(fact["source_links"][0]["source_kind"], "manual_input")
            self.assertEqual(
                {item["relationship"] for item in fact["source_links"]},
                {"derived_from", "supports"},
            )

    def test_direct_fact_memory_and_task_writes_share_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)

            rejected = self.run_cli(["fact", "add", "Unsupported fact"], home)
            fact = self.run_json(
                ["fact", "add", "Explicit local fact", "--user-asserted"],
                home,
            )
            memory = self.run_json(["remember", "Prefer deep modules", "--scope", "engineering"], home)
            task = self.run_json(["task", "add", "Finish migration", "--due-at", "2030-01-01"], home)

            self.assertEqual(rejected.returncode, 2)
            self.assertIn("--user-asserted", rejected.stderr)
            self.assertEqual(fact["object_type"], "fact")
            self.assertEqual(fact["acceptance"]["acceptance_path"], "manual")
            self.assertEqual(memory["memory_type"], "explicit")
            self.assertEqual(memory["confirmation_status"], "manual")
            self.assertEqual(memory["scope"], "engineering")
            self.assertEqual(task["task_status"], "open")
            self.assertEqual(task["due_at"], "2030-01-01")

    def test_revoked_manual_source_opens_fact_review_and_removes_fact_from_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "cascade source marker"],
                home,
            )["input_id"]
            promoted = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "fact",
                    "--statement",
                    "Cascade source marker is current",
                ],
                home,
            )
            before = self.run_json(
                [
                    "bundle",
                    "Cascade source marker",
                    "--source",
                    "all",
                    "--vault",
                    str(FIXTURE_VAULT),
                ],
                home,
            )

            self.run_json(["input", "revoke", input_id], home)
            fact = self.run_json(["fact", "show", promoted["object_id"]], home)
            reviews = self.run_json(["review", "list"], home)
            after = self.run_json(
                [
                    "bundle",
                    "Cascade source marker",
                    "--source",
                    "all",
                    "--vault",
                    str(FIXTURE_VAULT),
                ],
                home,
            )

            self.assertIn("fact", {item["evidence_role"] for item in before["slices"]})
            self.assertEqual(fact["validity"], "needs_review")
            self.assertEqual(reviews[0]["object_id"], promoted["object_id"])
            self.assertEqual(reviews[0]["review_kind"], "source_revoked")
            self.assertNotIn("fact", {item["evidence_role"] for item in after["slices"]})

    def test_fact_revalidate_with_user_assertion_closes_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "revalidate source"],
                home,
            )["input_id"]
            fact_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "fact",
                    "--statement",
                    "Revalidation keeps explicit history",
                ],
                home,
            )["object_id"]
            self.run_json(["input", "revoke", input_id], home)

            fact_reviews = self.run_json(["fact", "review", "list"], home)
            shown_review = self.run_json(
                ["fact", "review", "show", fact_reviews[0]["review_id"]],
                home,
            )

            fact = self.run_json(
                ["fact", "review", "revalidate", fact_id, "--user-asserted"],
                home,
            )
            resolved = self.run_json(["review", "list", "--status", "resolved"], home)

            self.assertEqual(fact["validity"], "valid")
            self.assertEqual(shown_review["object_id"], fact_id)
            self.assertIsNone(fact["review_reason"])
            self.assertEqual(resolved[0]["resolution"], "revalidate")
            self.assertIn("user_assertion", {item["source_kind"] for item in fact["source_links"]})

    def test_fact_revise_and_revoke_preserve_tombstone_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            old_fact = self.run_json(
                ["fact", "add", "Old wording", "--user-asserted"],
                home,
            )

            revised = self.run_json(
                [
                    "fact",
                    "review",
                    "revise",
                    old_fact["object_id"],
                    "--statement",
                    "New wording",
                    "--user-asserted",
                ],
                home,
            )
            old_after = self.run_json(["fact", "show", old_fact["object_id"]], home)
            revoked = self.run_json(
                ["fact", "revoke", revised["object_id"], "--reason", "no longer valid"],
                home,
            )

            self.assertNotEqual(revised["object_id"], old_fact["object_id"])
            self.assertEqual(revised["statement"], "New wording")
            self.assertEqual(old_after["validity"], "superseded")
            self.assertEqual(old_after["superseded_by_fact_id"], revised["object_id"])
            self.assertEqual(revoked["revocation_status"], "revoked")
            self.assertEqual(revoked["tombstones"][0]["reason"], "no longer valid")

    def test_review_resolve_keep_restores_memory_with_user_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "memory source"],
                home,
            )["input_id"]
            memory_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "memory",
                    "--text",
                    "Keep review memory",
                ],
                home,
            )["object_id"]
            self.run_json(["input", "revoke", input_id], home)
            review_id = self.run_json(["review", "list"], home)[0]["review_id"]

            resolved = self.run_json(
                ["review", "resolve", review_id, "--action", "keep"],
                home,
            )
            memory = self.run_json(["memory", "show", memory_id], home)

            self.assertEqual(resolved["review"]["status"], "resolved")
            self.assertEqual(resolved["review"]["resolution"], "keep")
            self.assertEqual(memory["status"], "active")
            self.assertIn("user_assertion", {item["source_kind"] for item in memory["source_links"]})

    def test_memory_task_and_event_lifecycle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            memory = self.run_json(["remember", "Lifecycle memory"], home)
            task = self.run_json(["task", "add", "Lifecycle task"], home)
            input_id = self.run_json(
                ["input", "add", "--kind", "event", "--text", "Lifecycle event source"],
                home,
            )["input_id"]
            event = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "event",
                    "--title",
                    "Lifecycle event",
                    "--starts-at",
                    "2030-01-01T09:00:00+08:00",
                ],
                home,
            )["object"]

            memories = self.run_json(["memory", "list"], home)
            tasks = self.run_json(["task", "list"], home)
            events = self.run_json(["event", "list"], home)
            revoked_memory = self.run_json(["memory", "revoke", memory["object_id"]], home)
            closed_task = self.run_json(["task", "close", task["object_id"]], home)
            cancelled_event = self.run_json(["event", "cancel", event["object_id"]], home)

            self.assertEqual(memories[0]["object_id"], memory["object_id"])
            self.assertEqual(tasks[0]["object_id"], task["object_id"])
            self.assertEqual(events[0]["object_id"], event["object_id"])
            self.assertEqual(revoked_memory["status"], "revoked")
            self.assertEqual(closed_task["task_status"], "completed")
            self.assertEqual(cancelled_event["event_status"], "cancelled")

    def test_managed_asset_delete_uses_reconcilable_file_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            image = Path(tmp) / "capture.png"
            image.write_bytes(b"private-image")
            added = self.run_json(
                [
                    "input",
                    "add",
                    "--kind",
                    "screenshot",
                    "--file",
                    str(image),
                    "--text",
                    "outbox screenshot",
                    "--no-extract",
                ],
                home,
            )
            stored_path = Path(added["stored_path"])

            deleted = self.run_json(["input", "delete", added["input_id"]], home)
            reconcile = self.run_json(["db", "reconcile-files"], home)

            self.assertEqual(deleted["status"], "deleted")
            self.assertFalse(deleted["file_cleanup_pending"])
            self.assertFalse(stored_path.exists())
            self.assertTrue(reconcile["dry_run"])
            self.assertEqual(reconcile["pending_count"], 0)

    def test_manual_input_update_stales_old_source_and_opens_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "old source content"],
                home,
            )["input_id"]
            fact_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "fact",
                    "--statement",
                    "Source update must trigger review",
                ],
                home,
            )["object_id"]

            self.run_json(["input", "update", input_id, "--text", "new source content"], home)
            fact = self.run_json(["fact", "show", fact_id], home)
            reviews = self.run_json(["review", "list"], home)

            self.assertEqual(fact["validity"], "needs_review")
            self.assertEqual(reviews[0]["review_kind"], "source_stale")
            self.assertEqual(
                {item["source_status"] for item in fact["source_links"]},
                {"stale"},
            )

    def test_candidate_open_review_blocks_confirm_and_discard_resolves_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "candidate review source"],
                home,
            )["input_id"]
            candidate_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "Candidate review closure",
                    "--type",
                    "fact",
                ],
                home,
            )["object_id"]
            self.run_json(["input", "update", input_id, "--text", "changed candidate source"], home)

            rejected = self.run_cli(
                ["candidate", "confirm", candidate_id, "--user-asserted"],
                home,
            )
            discarded = self.run_json(
                ["candidate", "discard", candidate_id, "--reason", "source changed"],
                home,
            )
            resolved = self.run_json(["review", "list", "--status", "resolved"], home)

            self.assertEqual(rejected.returncode, 2)
            self.assertIn("open review", rejected.stderr)
            self.assertEqual(discarded["status"], "discarded")
            self.assertEqual(resolved[0]["resolution"], "discard")

    def test_direct_fact_inherits_the_highest_source_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                [
                    "input",
                    "add",
                    "--kind",
                    "note",
                    "--text",
                    "sensitive source",
                    "--sensitivity",
                    "Sensitive",
                ],
                home,
            )["input_id"]
            promoted = self.run_json(
                ["input", "promote", input_id, "--to", "memory", "--text", "source memory"],
                home,
            )
            source_ref_id = promoted["object"]["source_links"][0]["source_ref_id"]

            fact = self.run_json(
                [
                    "fact",
                    "add",
                    "sensitivity cannot be downgraded",
                    "--source-ref",
                    source_ref_id,
                    "--sensitivity",
                    "Public",
                ],
                home,
            )

            self.assertEqual(fact["sensitivity"], "Sensitive")

    def test_optional_fact_support_failure_does_not_open_fact_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            primary_input = self.run_json(
                ["input", "add", "--kind", "note", "--text", "primary support"],
                home,
            )["input_id"]
            fact_id = self.run_json(
                [
                    "input",
                    "promote",
                    primary_input,
                    "--to",
                    "fact",
                    "--statement",
                    "multi source fact",
                ],
                home,
            )["object_id"]
            optional_input = self.run_json(
                ["input", "add", "--kind", "note", "--text", "optional support"],
                home,
            )["input_id"]
            optional_memory = self.run_json(
                [
                    "input",
                    "promote",
                    optional_input,
                    "--to",
                    "memory",
                    "--text",
                    "optional source memory",
                ],
                home,
            )
            optional_ref = optional_memory["object"]["source_links"][0]["source_ref_id"]
            with LifeMeshDatabase(load_config(home=str(home))).transaction() as con:
                con.execute(
                    "INSERT INTO object_source_links(object_id, source_ref_id, relationship, required, created_at) VALUES (?, ?, 'supports', 0, '2026-07-15T00:00:00Z')",
                    (fact_id, optional_ref),
                )

            self.run_json(["input", "revoke", optional_input], home)
            fact = self.run_json(["fact", "show", fact_id], home)
            reviews = self.run_json(["review", "list"], home)

            self.assertEqual(fact["validity"], "valid")
            self.assertNotIn(fact_id, {item["object_id"] for item in reviews})

    def test_candidate_edit_removing_invalid_source_closes_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "candidate source"],
                home,
            )["input_id"]
            candidate_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "candidate edit closes review",
                    "--type",
                    "fact",
                ],
                home,
            )["object_id"]
            self.run_json(["input", "update", input_id, "--text", "changed source"], home)
            source_ref_id = self.run_json(["candidate", "show", candidate_id], home)["source_links"][0]["source_ref_id"]

            edited = self.run_json(
                ["candidate", "edit", candidate_id, "--remove-source-ref", source_ref_id],
                home,
            )
            resolved = self.run_json(["review", "list", "--status", "resolved"], home)

            self.assertEqual(edited["source_links"], [])
            self.assertEqual(resolved[0]["resolution"], "edit")

    def test_candidate_merge_moves_invalid_source_review_to_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "merge source"],
                home,
            )["input_id"]
            loser_id = self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "loser candidate",
                    "--type",
                    "task",
                ],
                home,
            )["object_id"]
            winner_id = self.run_json(
                ["candidate", "add", "winner candidate", "--type", "task"],
                home,
            )["candidate_id"]
            self.run_json(["input", "update", input_id, "--text", "changed merge source"], home)

            self.run_json(["candidate", "merge", winner_id, loser_id], home)
            open_reviews = self.run_json(["review", "list"], home)
            resolved = self.run_json(["review", "list", "--status", "resolved"], home)

            self.assertEqual({item["candidate_id"] for item in open_reviews}, {winner_id})
            self.assertEqual({item["candidate_id"] for item in resolved}, {loser_id})
            self.assertEqual(resolved[0]["resolution"], "merge")

    def test_manual_input_update_and_source_cascade_rollback_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "atomic old text"],
                home,
            )["input_id"]
            self.run_json(
                [
                    "input",
                    "promote",
                    input_id,
                    "--to",
                    "fact",
                    "--statement",
                    "atomic cascade fact",
                ],
                home,
            )
            before = self.run_json(["input", "show", input_id], home)

            with mock.patch.object(
                KnowledgeWorkflow,
                "_cascade_dependents",
                side_effect=KnowledgeWorkflowError("forced cascade failure"),
            ):
                failed = self.run_cli(
                    ["input", "update", input_id, "--text", "atomic new text"],
                    home,
                )
            after = self.run_json(["input", "show", input_id], home)

            self.assertEqual(failed.returncode, 2)
            self.assertEqual(after["text"], before["text"])
            self.assertEqual(after["content_hash"], before["content_hash"])

    def test_screenshot_promotion_failure_is_reported_and_reconcilable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            image = Path(tmp) / "capture.png"
            image.write_bytes(b"private-image")

            with mock.patch.object(
                LifeMeshDatabase,
                "_apply_file_operation",
                side_effect=OSError("forced rename failure"),
            ):
                result = self.run_cli(
                    [
                        "input",
                        "add",
                        "--kind",
                        "screenshot",
                        "--file",
                        str(image),
                        "--text",
                        "staged screenshot",
                        "--no-extract",
                    ],
                    home,
                )

            payload = json.loads(result.stdout)
            reconcile = self.run_json(["db", "reconcile-files"], home)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(payload["file_cleanup_pending"])
            self.assertEqual(reconcile["pending_count"], 1)

    def test_staged_asset_reconcile_is_idempotent_after_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            image = Path(tmp) / "capture.png"
            image.write_bytes(b"private-image")
            added = self.run_json(
                [
                    "input",
                    "add",
                    "--kind",
                    "screenshot",
                    "--file",
                    str(image),
                    "--text",
                    "idempotent staged screenshot",
                    "--no-extract",
                ],
                home,
            )
            target = Path(added["stored_path"])
            with LifeMeshDatabase(load_config(home=str(home))).transaction() as con:
                con.execute(
                    "UPDATE file_operations SET status = 'failed', completed_at = NULL WHERE operation_type = 'promote_staged_asset'"
                )

            reconciled = self.run_json(["db", "reconcile-files", "--apply"], home)

            self.assertEqual(reconciled["completed_count"], 1)
            self.assertEqual(reconciled["pending_count"], 0)
            self.assertTrue(target.exists())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def run_json(self, argv: list[str], home: Path) -> object:
        result = self.run_cli(argv, home)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def run_cli(self, argv: list[str], home: Path) -> object:
        stdout = io.StringIO()
        stderr = io.StringIO()
        env = {"LIFEMESH_HOME": str(home)}
        with mock.patch.dict(os.environ, env, clear=True):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    returncode = cli.main(argv)
                except SystemExit as exc:
                    returncode = int(exc.code)
        return CliResult(returncode, stdout.getvalue(), stderr.getvalue())


class CliResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


if __name__ == "__main__":
    unittest.main()
