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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VAULT = ROOT / "tests" / "fixtures" / "obsidian-vault"


class RumorClaimCliTest(unittest.TestCase):
    def test_add_list_and_show_structured_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            added = self.run_json(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "supplier risk marker affects project alpha",
                    "--claim-type",
                    "risk_claim",
                    "--entity-mention",
                    "SupplierA",
                    "--relation-mention",
                    "SupplierA affects ProjectAlpha",
                    "--user-relevance",
                    "medium",
                    "--relevance-reason",
                    "related to active project",
                    "--impact",
                    "high",
                    "--impact-reason",
                    "could block delivery",
                    "--extraction-confidence",
                    "high",
                    "--evidence-state",
                    "single_source",
                    "--claim-quality",
                    "verifiable",
                    "--source-adapter",
                    "test_feed",
                    "--source-summary",
                    "internal feed snippet",
                ],
                home,
            )

            rumor_claim_id = added["rumor_claim_id"]
            self.assertEqual(added["status"], "parked")
            self.assertEqual(added["assessment"], "plausible")
            self.assertEqual(added["review_queue"], "general_review")
            self.assertEqual(added["entity_mentions"], ["SupplierA"])
            self.assertEqual(added["relation_mentions"], ["SupplierA affects ProjectAlpha"])
            self.assertEqual(added["source_envelope"]["raw_retention"], "none")
            self.assertEqual(added["source_envelope"]["source_adapter"], "test_feed")

            listed = self.run_json(["rumor", "list"], home)
            self.assertEqual(listed[0]["rumor_claim_id"], rumor_claim_id)

            shown = self.run_json(["rumor", "show", rumor_claim_id], home)
            self.assertEqual(shown["claim_text"], "supplier risk marker affects project alpha")
            self.assertEqual(shown["audit_events"][0]["action"], "add")

    def test_add_rejects_claims_below_persistence_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            result = self.run_cli(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "low value noise",
                    "--claim-type",
                    "factual_claim",
                    "--user-relevance",
                    "low",
                    "--impact",
                    "low",
                ],
                home,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("persistence gate", result.stderr)

    def test_add_requires_explicit_relevance_and_impact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            result = self.run_cli(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "untriaged supplier risk marker",
                    "--claim-type",
                    "risk_claim",
                ],
                home,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("required", result.stderr)

    def test_default_credibility_starts_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            added = self.run_json(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "supplier risk marker affects project alpha",
                    "--claim-type",
                    "risk_claim",
                    "--user-relevance",
                    "medium",
                    "--impact",
                    "high",
                ],
                home,
            )

            self.assertEqual(added["evidence_state"], "unknown")
            self.assertEqual(added["assessment"], "unverified")

    def test_contradicted_evidence_cannot_be_overridden_into_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            result = self.run_cli(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "supplier risk marker affects project alpha",
                    "--claim-type",
                    "risk_claim",
                    "--user-relevance",
                    "medium",
                    "--impact",
                    "high",
                    "--evidence-state",
                    "contradicted",
                    "--assessment",
                    "supported",
                ],
                home,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("contradicted evidence", result.stderr)

    def test_dismiss_excludes_claim_from_rumor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home)["rumor_claim_id"]

            dismissed = self.run_json(["rumor", "dismiss", rumor_claim_id, "--reason", "not relevant"], home)
            bundle = self.run_json(["bundle", "supplier risk marker", "--source", "rumor"], home)

            self.assertEqual(dismissed["status"], "dismissed")
            self.assertEqual(dismissed["tombstone_reason"], "not relevant")
            self.assertEqual(bundle["slices"], [])

    def test_expired_claim_is_reported_as_excluded_from_rumor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home, expires_at="2000-01-01T00:00:00Z")["rumor_claim_id"]

            bundle = self.run_json(["bundle", "supplier risk marker", "--source", "rumor"], home)

            self.assertEqual(bundle["slices"], [])
            self.assertEqual(
                bundle["excluded_sources"],
                [{"source": "rumor", "rumor_claim_id": rumor_claim_id, "reason": "expired"}],
            )

    def test_invalid_expiry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"

            result = self.run_cli(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "supplier risk marker affects project alpha",
                    "--claim-type",
                    "risk_claim",
                    "--user-relevance",
                    "medium",
                    "--impact",
                    "high",
                    "--expires-at",
                    "not-a-date",
                ],
                home,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("expires-at must be ISO-8601", result.stderr)

    def test_promote_marks_candidate_created_and_preserves_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home)["rumor_claim_id"]

            promoted = self.run_json(
                [
                    "rumor",
                    "promote",
                    rumor_claim_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "Supplier risk marker should be reviewed",
                    "--type",
                    "fact",
                    "--confidence",
                    "low",
                    "--risk",
                    "unverified",
                ],
                home,
            )

            self.assertEqual(promoted["target_type"], "candidate")
            self.assertEqual(promoted["derived_from_rumor_claim_id"], rumor_claim_id)
            claim = promoted["rumor_claim"]
            self.assertEqual(claim["status"], "candidate_created")
            self.assertEqual(claim["candidate_links"][0]["target_type"], "candidate")
            self.assertEqual(claim["candidate_links"][0]["target_payload"]["statement"], "Supplier risk marker should be reviewed")

    def test_keep_marks_claim_reviewed_without_requeueing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home)["rumor_claim_id"]

            kept = self.run_json(["rumor", "keep", rumor_claim_id, "--reason", "human reviewed"], home)
            default_list = self.run_json(["rumor", "list"], home)
            reviewed_list = self.run_json(["rumor", "list", "--status", "reviewed_parked"], home)
            bundle = self.run_json(["bundle", "supplier risk marker", "--source", "rumor"], home)

            self.assertEqual(kept["status"], "reviewed_parked")
            self.assertEqual(kept["audit_events"][-1]["action"], "keep")
            self.assertEqual(kept["audit_events"][-1]["payload"]["reason"], "human reviewed")
            self.assertEqual(default_list, [])
            self.assertEqual(reviewed_list[0]["rumor_claim_id"], rumor_claim_id)
            self.assertEqual(bundle["slices"][0]["provenance"]["rumor_claim_id"], rumor_claim_id)
            self.assertEqual(bundle["slices"][0]["provenance"]["status"], "reviewed_parked")
            self.assertEqual(bundle["slices"][0]["evidence_role"], "lead")

    def test_keep_rejects_terminal_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            dismissed_id = self.add_claim(home)["rumor_claim_id"]
            expired_id = self.add_claim(home)["rumor_claim_id"]
            candidate_id = self.add_claim(home)["rumor_claim_id"]

            self.run_json(["rumor", "dismiss", dismissed_id], home)
            self.run_json(["rumor", "expire", expired_id], home)
            self.run_json(
                [
                    "rumor",
                    "promote",
                    candidate_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "Supplier risk marker should be reviewed",
                    "--type",
                    "fact",
                ],
                home,
            )

            dismissed_result = self.run_cli(["rumor", "keep", dismissed_id], home)
            expired_result = self.run_cli(["rumor", "keep", expired_id], home)
            candidate_result = self.run_cli(["rumor", "keep", candidate_id], home)

            self.assertEqual(dismissed_result.returncode, 2)
            self.assertIn("Cannot keep dismissed", dismissed_result.stderr)
            self.assertEqual(expired_result.returncode, 2)
            self.assertIn("Cannot keep expired", expired_result.stderr)
            self.assertEqual(candidate_result.returncode, 2)
            self.assertIn("Cannot keep candidate_created", candidate_result.stderr)

    def test_reviewed_parked_claim_can_still_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home)["rumor_claim_id"]

            self.run_json(["rumor", "keep", rumor_claim_id], home)
            promoted = self.run_json(
                [
                    "rumor",
                    "promote",
                    rumor_claim_id,
                    "--to",
                    "candidate",
                    "--statement",
                    "Supplier risk marker should be reviewed",
                    "--type",
                    "fact",
                ],
                home,
            )

            self.assertEqual(promoted["rumor_claim"]["status"], "candidate_created")
            self.assertEqual(promoted["rumor_claim"]["candidate_links"][0]["target_type"], "candidate")

    def test_bundle_all_requires_explicit_include_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home)["rumor_claim_id"]

            default_bundle = self.run_json(
                ["bundle", "supplier risk marker", "--source", "all", "--vault", str(FIXTURE_VAULT)],
                home,
            )
            included_bundle = self.run_json(
                [
                    "bundle",
                    "supplier risk marker",
                    "--source",
                    "all",
                    "--include-unverified",
                    "--vault",
                    str(FIXTURE_VAULT),
                ],
                home,
            )

            self.assertNotIn("rumor", default_bundle["permission_scope"]["allowed_sources"])
            self.assertFalse(any(item["provenance"].get("source") == "rumor" for item in default_bundle["slices"]))
            self.assertIn("rumor", included_bundle["permission_scope"]["allowed_sources"])
            self.assertTrue(included_bundle["permission_scope"]["include_unverified"])
            rumor_slice = next(item for item in included_bundle["slices"] if item["provenance"].get("source") == "rumor")
            self.assertEqual(rumor_slice["provenance"]["rumor_claim_id"], rumor_claim_id)
            self.assertEqual(rumor_slice["evidence_role"], "lead")
            self.assertFalse(rumor_slice["retrieval"]["evidence_eligible"])
            self.assertEqual(rumor_slice["citation"]["format"], "rumor-claim-v1")

    def test_bundle_can_match_entity_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.run_json(
                [
                    "rumor",
                    "add",
                    "--claim-text",
                    "dependency outage may affect delivery",
                    "--claim-type",
                    "risk_claim",
                    "--entity-mention",
                    "SupplierZeta",
                    "--user-relevance",
                    "medium",
                    "--impact",
                    "high",
                ],
                home,
            )["rumor_claim_id"]

            bundle = self.run_json(["bundle", "SupplierZeta", "--source", "rumor"], home)

            self.assertEqual(bundle["slices"][0]["provenance"]["rumor_claim_id"], rumor_claim_id)
            self.assertEqual(bundle["slices"][0]["entity_mentions"], ["SupplierZeta"])

    def test_sensitive_claim_is_reported_as_excluded_from_rumor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            rumor_claim_id = self.add_claim(home, sensitivity="Sensitive")["rumor_claim_id"]

            bundle = self.run_json(["bundle", "supplier risk marker", "--source", "rumor"], home)

            self.assertEqual(bundle["slices"], [])
            self.assertEqual(
                bundle["excluded_sources"],
                [{"source": "rumor", "rumor_claim_id": rumor_claim_id, "reason": "sensitivity_cap_exceeded"}],
            )

    def add_claim(self, home: Path, *, sensitivity: str = "Private", expires_at: str | None = None) -> dict:
        argv = [
            "rumor",
            "add",
            "--claim-text",
            "supplier risk marker affects project alpha",
            "--claim-type",
            "risk_claim",
            "--user-relevance",
            "medium",
            "--impact",
            "high",
            "--extraction-confidence",
            "high",
            "--evidence-state",
            "single_source",
            "--claim-quality",
            "verifiable",
            "--sensitivity",
            sensitivity,
        ]
        if expires_at is not None:
            argv.extend(["--expires-at", expires_at])
        return self.run_json(
            argv,
            home,
        )

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
