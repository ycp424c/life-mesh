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


class CandidateCliTest(unittest.TestCase):
    def test_add_list_and_show_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            added = self.run_json(
                [
                    "candidate",
                    "add",
                    "Tailwind traffic decline should be reviewed as a fact",
                    "--type",
                    "fact",
                    "--source-ref",
                    "obsidian:hot.md#L16-L22",
                    "--confidence",
                    "0.72",
                    "--risk",
                    "medium",
                    "--why-suggested",
                    "Q20 source-backed answer surfaced this as reusable context",
                ],
                home,
            )

            candidate_id = added["candidate_id"]
            self.assertTrue(candidate_id.startswith("candidate_"))
            self.assertEqual(added["summary"], "Tailwind traffic decline should be reviewed as a fact")
            self.assertEqual(added["type"], "fact")
            self.assertEqual(added["lifecycle"], "confirm_required")
            self.assertEqual(added["source_refs"], ["obsidian:hot.md#L16-L22"])
            self.assertEqual(added["confidence"], 0.72)
            self.assertEqual(added["risk"], "medium")

            listed = self.run_json(["candidate", "list"], home)
            self.assertEqual([item["candidate_id"] for item in listed], [candidate_id])
            self.assertNotIn("audit_events", listed[0])

            shown = self.run_json(["candidate", "show", candidate_id], home)
            self.assertEqual(shown["candidate_id"], candidate_id)
            self.assertEqual(shown["audit_events"][0]["action"], "add")

    def test_list_sorts_by_risk_then_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            low = self.run_json(
                [
                    "candidate",
                    "add",
                    "low risk candidate",
                    "--type",
                    "preference",
                    "--risk",
                    "low",
                    "--confidence",
                    "0.95",
                ],
                home,
            )["candidate_id"]
            high = self.run_json(
                [
                    "candidate",
                    "add",
                    "high risk candidate",
                    "--type",
                    "task",
                    "--risk",
                    "high",
                    "--confidence",
                    "0.4",
                ],
                home,
            )["candidate_id"]

            listed = self.run_json(["candidate", "list"], home)

            self.assertEqual([item["candidate_id"] for item in listed], [high, low])

    def test_discard_hides_candidate_from_default_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            candidate_id = self.run_json(
                ["candidate", "add", "discardable candidate", "--type", "decision"],
                home,
            )["candidate_id"]

            discarded = self.run_json(["candidate", "discard", candidate_id, "--reason", "not useful"], home)
            listed = self.run_json(["candidate", "list"], home)
            discarded_list = self.run_json(["candidate", "list", "--lifecycle", "discard"], home)

            self.assertEqual(discarded["lifecycle"], "discard")
            self.assertEqual(discarded["tombstone_reason"], "not useful")
            self.assertEqual(listed, [])
            self.assertEqual([item["candidate_id"] for item in discarded_list], [candidate_id])

    def test_add_validates_type_and_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            bad_type = self.run_cli(["candidate", "add", "bad type", "--type", "person"], home)
            bad_confidence = self.run_cli(
                ["candidate", "add", "bad confidence", "--type", "fact", "--confidence", "1.5"],
                home,
            )

            self.assertEqual(bad_type.returncode, 2)
            self.assertIn("--type", bad_type.stderr)
            self.assertEqual(bad_confidence.returncode, 2)
            self.assertIn("confidence", bad_confidence.stderr)

    def test_add_rejects_non_finite_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            for value in ["nan", "inf", "-inf"]:
                with self.subTest(value=value):
                    result = self.run_cli(
                        ["candidate", "add", "bad confidence", "--type", "fact", "--confidence", value],
                        home,
                    )

                    self.assertEqual(result.returncode, 2)
                    self.assertIn("confidence", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_add_normalizes_and_validates_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            added = self.run_json(
                [
                    "candidate",
                    "add",
                    "expiring candidate",
                    "--type",
                    "fact",
                    "--expires-at",
                    "2030-01-02T03:04:05+08:00",
                ],
                home,
            )
            invalid = self.run_cli(
                ["candidate", "add", "bad expiry", "--type", "fact", "--expires-at", "not-a-date"],
                home,
            )

            self.assertEqual(added["expires_at"], "2030-01-01T19:04:05Z")
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("expires-at must be ISO-8601", invalid.stderr)

    def test_list_rejects_transient_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            result = self.run_cli(["candidate", "list", "--lifecycle", "transient"], home)

            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid choice", result.stderr)

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
