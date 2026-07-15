from __future__ import annotations

import contextlib
import fcntl
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lifemesh import cli
from lifemesh.config import load_config
from lifemesh.database import DatabaseError, LifeMeshDatabase


class DatabaseCliTest(unittest.TestCase):
    def test_status_reports_uninitialized_database_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            status = self.run_json(["db", "status"], home)

            self.assertEqual(status["schema_status"], "uninitialized")
            self.assertEqual(status["applied_migrations"], [])
            self.assertEqual(status["target_migration_id"], "0001_unified_write_model")
            self.assertFalse(status["database_exists"])
            self.assertFalse((home / "lifemesh.db").exists())

    def test_first_domain_write_initializes_unified_schema(self) -> None:
        cases = [
            ["candidate", "add", "bootstrap candidate", "--type", "task"],
            ["input", "add", "--kind", "note", "--text", "bootstrap input"],
            [
                "rumor",
                "add",
                "--claim-text",
                "bootstrap rumor",
                "--claim-type",
                "factual_claim",
                "--user-relevance",
                "medium",
                "--impact",
                "low",
            ],
        ]
        for argv in cases:
            with self.subTest(command=argv[0]), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "home"

                self.run_json(argv, home)
                status = self.run_json(["db", "status"], home)

                self.assertEqual(status["schema_status"], "current")
                with sqlite3.connect(home / "lifemesh.db") as con:
                    tables = {
                        str(row[0])
                        for row in con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                self.assertNotIn("promoted_objects", tables)
                self.assertNotIn("rumor_candidate_links", tables)

    def test_migrate_defaults_to_dry_run_and_does_not_create_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            report = self.run_json(["db", "migrate"], home)

            self.assertTrue(report["dry_run"])
            self.assertTrue(report["migration_required"])
            self.assertEqual(report["target_migration_id"], "0001_unified_write_model")
            self.assertEqual(report["preflight"]["legacy_tables"], {})
            self.assertEqual(report["preflight"]["expected"]["candidates"], 0)
            self.assertFalse((home / "lifemesh.db").exists())

    def test_apply_initializes_current_private_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            report = self.run_json(["db", "migrate", "--apply"], home)
            status = self.run_json(["db", "status"], home)

            self.assertFalse(report["dry_run"])
            self.assertEqual(report["postflight"]["integrity_check"], "ok")
            self.assertEqual(report["postflight"]["foreign_key_violations"], [])
            self.assertIsNone(report["backup_manifest"])
            self.assertEqual(status["schema_status"], "current")
            self.assertEqual(status["applied_migrations"][0]["migration_id"], "0001_unified_write_model")
            self.assertEqual((home.stat().st_mode & 0o777), 0o700)
            self.assertEqual(((home / "lifemesh.db").stat().st_mode & 0o777), 0o600)

    def test_migration_checksum_mismatch_is_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                con.execute(
                    "UPDATE schema_migrations SET checksum = 'tampered' WHERE migration_id = '0001_unified_write_model'"
                )

            result = self.run_cli(["db", "status"], home)

            self.assertEqual(result.returncode, 2)
            self.assertIn("checksum", result.stderr)

    def test_reapplying_current_migration_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            first = self.run_json(["db", "migrate", "--apply"], home)
            second = self.run_json(["db", "migrate", "--apply"], home)

            self.assertTrue(first["migration_required"])
            self.assertFalse(second["migration_required"])
            self.assertIsNone(second["backup_manifest"])
            self.assertEqual(second["postflight"]["candidate_count"], 0)

    def test_current_connections_hold_the_shared_database_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            self.run_json(["db", "migrate", "--apply"], home)
            database = LifeMeshDatabase(load_config(home=str(home)))
            lock_path = home / ".database.lock"

            with database.connect():
                with lock_path.open("a+b") as contender:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            with lock_path.open("a+b") as contender:
                fcntl.flock(contender.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(contender.fileno(), fcntl.LOCK_UN)
            self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)

    def test_dry_run_derives_expected_sets_from_legacy_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            _seed_legacy_database(home)

            report = self.run_json(["db", "migrate"], home)

            self.assertEqual(report["preflight"]["legacy_tables"]["manual_inputs"], 1)
            self.assertEqual(report["preflight"]["legacy_tables"]["rumor_claims"], 1)
            self.assertEqual(report["preflight"]["legacy_tables"]["knowledge_candidates"], 1)
            self.assertEqual(report["preflight"]["expected"]["candidates"], 3)
            self.assertEqual(report["preflight"]["expected"]["source_references"], 2)

    def test_apply_backs_up_legacy_data_and_unifies_candidate_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            ids = _seed_legacy_database(home)
            manual_candidate_id = ids["manual_candidate_id"]
            rumor_candidate_id = ids["rumor_candidate_id"]
            direct_candidate_id = ids["direct_candidate_id"]

            report = self.run_json(["db", "migrate", "--apply"], home)
            candidates = self.run_json(["candidate", "list", "--status", "pending"], home)

            manifest = Path(report["backup_manifest"])
            self.assertTrue(manifest.exists())
            self.assertEqual(report["postflight"]["candidate_count"], 3)
            self.assertEqual(
                {item["candidate_id"] for item in candidates},
                {manual_candidate_id, rumor_candidate_id, direct_candidate_id},
            )
            self.assertTrue(all(item["status"] == "pending" for item in candidates))

    def test_restore_replaces_migrated_database_with_validated_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            original_id = _seed_legacy_database(home, sources=False)["direct_candidate_id"]
            migrated = self.run_json(["db", "migrate", "--apply"], home)
            self.run_json(
                ["candidate", "add", "post migration candidate", "--type", "task"],
                home,
            )

            restored = self.run_json(
                ["db", "restore", migrated["backup_manifest"], "--apply"],
                home,
            )
            status = self.run_json(["db", "status"], home)
            preflight = self.run_json(["db", "migrate"], home)

            self.assertEqual(restored["integrity_check"], "ok")
            self.assertEqual(status["schema_status"], "legacy")
            self.assertEqual(preflight["preflight"]["expected"]["candidates"], 1)
            self.assertEqual(preflight["preflight"]["identity_digests"]["candidates"], restored["preflight"]["identity_digests"]["candidates"])
            self.assertTrue(Path(restored["forensic_database_path"]).exists())
            self.assertTrue(original_id.startswith("candidate_"))

    def test_revoked_legacy_sources_migrate_objects_and_candidates_into_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            ids = _seed_legacy_database(home)
            fact_id = "fact_revoked_legacy"
            with sqlite3.connect(home / "lifemesh.db") as con:
                con.execute(
                    "UPDATE manual_inputs SET status = 'revoked' WHERE input_id = ?",
                    (ids["input_id"],),
                )
                con.execute(
                    "INSERT INTO promoted_objects VALUES (?, 'fact', ?, ?, '2026-07-15T00:00:00Z')",
                    (
                        fact_id,
                        json.dumps({"statement": "revoked source fact"}),
                        ids["input_id"],
                    ),
                )

            report = self.run_json(["db", "migrate", "--apply"], home)
            fact = self.run_json(["fact", "show", fact_id], home)
            reviews = self.run_json(["review", "list"], home)

            self.assertEqual(report["postflight"]["conservation_check"], "ok")
            self.assertEqual(fact["validity"], "needs_review")
            self.assertEqual(fact["source_links"][0]["source_status"], "revoked")
            self.assertEqual(len(reviews), 2)
            self.assertEqual({item["review_kind"] for item in reviews}, {"source_revoked"})

    def test_migration_preserves_fts_rows_and_normalizes_payload_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            ids = _seed_legacy_database(home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                con.execute("CREATE TABLE manual_inputs_fts(input_id TEXT, text TEXT)")
                con.execute("INSERT INTO manual_inputs_fts VALUES ('input_legacy', 'fts payload')")
                con.execute(
                    "UPDATE promoted_objects SET target_payload_json = ? WHERE object_id = ?",
                    (
                        json.dumps(
                            {
                                "statement": "manual legacy candidate",
                                "type": "fact",
                                "source_refs": ["legacy:opaque-evidence"],
                            }
                        ),
                        ids["manual_candidate_id"],
                    ),
                )

            report = self.run_json(["db", "migrate", "--apply"], home)
            candidate = self.run_json(
                ["candidate", "show", ids["manual_candidate_id"]],
                home,
            )
            with sqlite3.connect(home / "lifemesh.db") as con:
                fts_rows = con.execute("SELECT * FROM manual_inputs_fts").fetchall()

            self.assertEqual(report["postflight"]["conservation_check"], "ok")
            self.assertEqual(len(candidate["source_links"]), 2)
            self.assertEqual(fts_rows, [("input_legacy", "fts payload")])

    def test_deleted_legacy_promotion_becomes_metadata_only_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            ids = _seed_legacy_database(home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                con.execute(
                    "UPDATE manual_inputs SET status = 'deleted', content_hash = NULL, deleted_at = updated_at WHERE input_id = ?",
                    (ids["input_id"],),
                )

            report = self.run_json(["db", "migrate", "--apply"], home)
            candidates = self.run_json(["candidate", "list", "--status", "pending"], home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                row = con.execute(
                    "SELECT new_state_json FROM audit_events WHERE action = 'legacy_target_missing'"
                ).fetchone()

            payload = json.loads(row[0])
            self.assertEqual(report["postflight"]["conservation_check"], "ok")
            self.assertNotIn(ids["manual_candidate_id"], {item["candidate_id"] for item in candidates})
            self.assertEqual(payload["object_id"], ids["manual_candidate_id"])
            self.assertEqual(payload["target_type"], "candidate")
            self.assertNotIn("statement", payload)

    def test_deleted_audit_only_promotion_does_not_copy_nested_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            ids = _seed_legacy_database(home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                con.execute(
                    "UPDATE manual_inputs SET status = 'deleted', content_hash = NULL, deleted_at = updated_at WHERE input_id = ?",
                    (ids["input_id"],),
                )
                con.execute(
                    "DELETE FROM promoted_objects WHERE object_id = ?",
                    (ids["manual_candidate_id"],),
                )
                con.execute(
                    "CREATE TABLE manual_input_audit_events(event_id INTEGER PRIMARY KEY, input_id TEXT, action TEXT, event_at TEXT, payload_json TEXT)"
                )
                con.execute(
                    "INSERT INTO manual_input_audit_events VALUES (1, ?, 'promote', '2026-07-15T00:00:00Z', ?)",
                    (
                        ids["input_id"],
                        json.dumps(
                            {
                                "object_id": ids["manual_candidate_id"],
                                "target_type": "candidate",
                                "payload": {"statement": "must not survive migration"},
                            }
                        ),
                    ),
                )

            report = self.run_json(["db", "migrate", "--apply"], home)
            with sqlite3.connect(home / "lifemesh.db") as con:
                row = con.execute(
                    "SELECT action, new_state_json FROM audit_events WHERE legacy_event_key = 'manual_input_audit_events:1'"
                ).fetchone()

            payload = json.loads(row[1])
            self.assertEqual(report["postflight"]["conservation_check"], "ok")
            self.assertEqual(row[0], "legacy_target_missing")
            self.assertEqual(set(payload), {"object_id", "target_type", "payload_hash"})
            self.assertNotIn("must not survive", row[1])

    def test_restore_keeps_database_companions_in_forensic_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            _seed_legacy_database(home, sources=False)
            migrated = self.run_json(["db", "migrate", "--apply"], home)
            companion = Path(str(home / "lifemesh.db") + "-wal")
            companion.write_bytes(b"forensic wal")

            restored = self.run_json(
                ["db", "restore", migrated["backup_manifest"], "--apply"],
                home,
            )

            forensic_dir = Path(restored["forensic_directory"])
            self.assertEqual((forensic_dir / "lifemesh.db-wal").read_bytes(), b"forensic wal")
            self.assertFalse(companion.exists())

    def test_failed_restore_validation_rolls_back_and_keeps_forensic_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            _seed_legacy_database(home, sources=False)
            migrated = self.run_json(["db", "migrate", "--apply"], home)

            with mock.patch.object(
                LifeMeshDatabase,
                "_restore_smoke_test",
                side_effect=DatabaseError("forced restore validation failure"),
            ):
                failed = self.run_cli(
                    ["db", "restore", migrated["backup_manifest"], "--apply"],
                    home,
                )

            status = self.run_json(["db", "status"], home)
            forensic_dirs = list((home / "backups").glob("forensic-before-restore-*"))
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(status["schema_status"], "current")
            self.assertEqual(len(forensic_dirs), 1)
            self.assertTrue((forensic_dirs[0] / "lifemesh.db").exists())
            self.assertTrue((forensic_dirs[0] / "failed-restore-attempt.db").exists())

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


def _seed_legacy_database(home: Path, *, sources: bool = True) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    now = "2026-07-15T00:00:00Z"
    input_id = "input_legacy"
    rumor_id = "rc_legacy"
    manual_candidate_id = "candidate_manual_legacy"
    rumor_candidate_id = "candidate_rumor_legacy"
    direct_candidate_id = "candidate_direct_legacy"
    with sqlite3.connect(home / "lifemesh.db") as con:
        con.executescript(
            """
            CREATE TABLE knowledge_candidates (
                candidate_id TEXT PRIMARY KEY, type TEXT NOT NULL, summary TEXT NOT NULL,
                confidence REAL NOT NULL, risk TEXT NOT NULL, lifecycle TEXT NOT NULL,
                source_refs_json TEXT NOT NULL, why_suggested TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT,
                tombstone_reason TEXT
            );
            CREATE TABLE manual_inputs (
                input_id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                sensitivity TEXT NOT NULL, source_type TEXT NOT NULL, content_hash TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
            );
            CREATE TABLE promoted_objects (
                object_id TEXT PRIMARY KEY, target_type TEXT NOT NULL,
                target_payload_json TEXT NOT NULL, derived_from_input_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE rumor_claims (
                rumor_claim_id TEXT PRIMARY KEY, claim_type TEXT NOT NULL,
                assessment TEXT NOT NULL, status TEXT NOT NULL, sensitivity TEXT NOT NULL,
                source_envelope_json TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE rumor_candidate_links (
                object_id TEXT PRIMARY KEY, target_payload_json TEXT NOT NULL,
                rumor_claim_id TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            "INSERT INTO knowledge_candidates VALUES (?, 'task', 'direct legacy candidate', 0.5, 'medium', 'confirm_required', '[]', 'legacy', ?, ?, NULL, NULL)",
            (direct_candidate_id, now, now),
        )
        if sources:
            con.execute(
                "INSERT INTO manual_inputs VALUES (?, 'note', 'promoted', 'Private', 'manual_cli', 'sha256:manual', ?, ?, NULL)",
                (input_id, now, now),
            )
            con.execute(
                "INSERT INTO promoted_objects VALUES (?, 'candidate', ?, ?, ?)",
                (manual_candidate_id, json.dumps({"statement": "manual legacy candidate", "type": "fact"}), input_id, now),
            )
            con.execute(
                "INSERT INTO rumor_claims VALUES (?, 'factual_claim', 'unverified', 'candidate_created', 'Private', ?, ?, ?)",
                (rumor_id, json.dumps({"source_adapter": "manual_cli"}), now, now),
            )
            con.execute(
                "INSERT INTO rumor_candidate_links VALUES (?, ?, ?, ?)",
                (rumor_candidate_id, json.dumps({"statement": "rumor legacy candidate", "type": "fact"}), rumor_id, now),
            )
    return {
        "input_id": input_id,
        "rumor_id": rumor_id,
        "manual_candidate_id": manual_candidate_id,
        "rumor_candidate_id": rumor_candidate_id,
        "direct_candidate_id": direct_candidate_id,
    }


if __name__ == "__main__":
    unittest.main()
