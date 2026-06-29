from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VAULT = ROOT / "tests" / "fixtures" / "obsidian-vault"


class BundleCliTest(unittest.TestCase):
    def run_bundle(self, task: str, vault: Path, *extra: str) -> dict:
        command = [
            sys.executable,
            "-m",
            "lifemesh",
            "bundle",
            task,
            "--source",
            "obsidian",
            "--vault",
            str(vault),
            *extra,
        ]
        completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)

    def test_bundle_requires_explicit_vault_without_env_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("LIFEMESH_OBSIDIAN_VAULT", None)
            env["LIFEMESH_HOME"] = str(Path(tmp) / "empty-home")
            completed = subprocess.run(
                [sys.executable, "-m", "lifemesh", "bundle", "AI 对开源生态有什么结构性冲击？"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--vault is required", completed.stderr)

    def test_bundle_reads_vault_from_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            (home / "config.json").write_text(
                json.dumps({"obsidian_vault": str(FIXTURE_VAULT)}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("LIFEMESH_OBSIDIAN_VAULT", None)
            env["LIFEMESH_HOME"] = str(home)
            completed = subprocess.run(
                [sys.executable, "-m", "lifemesh", "bundle", "AI 对开源生态有什么结构性冲击？"],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        bundle = json.loads(completed.stdout)
        self.assertEqual(bundle["slices"][0]["provenance"]["source"], "obsidian")

    def test_bundle_returns_source_backed_raw_slice(self) -> None:
        bundle = self.run_bundle("AI 对开源生态有什么结构性冲击？", FIXTURE_VAULT)

        self.assertEqual(bundle["schema_version"], "1")
        self.assertEqual(bundle["task"]["agent_capability"], "search")
        self.assertIn("excluded_sources", bundle)
        self.assertIn("freshness_report", bundle)
        self.assertGreaterEqual(len(bundle["slices"]), 1)

        first = bundle["slices"][0]
        self.assertEqual(first["evidence_role"], "raw")
        self.assertEqual(first["citation_status"], "current")
        self.assertEqual(first["provenance"]["source"], "obsidian")
        self.assertEqual(first["provenance"]["note_path"], "hot.md")
        self.assertTrue(first["provenance"]["revision_id"].startswith("rev#sha256:"))
        self.assertTrue(first["provenance"]["content_hash"].startswith("sha256:"))
        self.assertEqual(first["heading"], "## Active Threads")
        self.assertEqual(first["line_range"], [7, 11])
        self.assertIn("AI 对开源生态的结构性冲击", first["content"])

    def test_bundle_uses_note_sensitivity_instead_of_cap_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            (vault / "internal.md").write_text(
                "---\nsensitivity: Internal\n---\n\n# Internal\n\nshared marker\n",
                encoding="utf-8",
            )

            bundle = self.run_bundle("shared marker", vault, "--sensitivity-cap", "Private")

            self.assertEqual(len(bundle["slices"]), 1)
            self.assertEqual(bundle["slices"][0]["sensitivity"], "Internal")

    def test_bundle_excludes_notes_above_sensitivity_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            (vault / "sensitive.md").write_text(
                "---\nsensitivity: Sensitive\n---\n\n# Sensitive\n\nsecret marker\n",
                encoding="utf-8",
            )

            bundle = self.run_bundle("secret marker", vault, "--sensitivity-cap", "Private")

            self.assertEqual(bundle["slices"], [])
            self.assertIn(
                {
                    "source": "obsidian",
                    "path": "sensitive.md",
                    "reason": "sensitivity_exceeds_cap",
                    "sensitivity": "Sensitive",
                    "sensitivity_cap": "Private",
                },
                bundle["excluded_sources"],
            )

    def test_excluded_paths_do_not_match(self) -> None:
        bundle = self.run_bundle("绝不应该命中", FIXTURE_VAULT)

        self.assertEqual(bundle["slices"], [])
        excluded_paths = {item["path"] for item in bundle["excluded_sources"]}
        self.assertIn("Trash", excluded_paths)
        self.assertIn(".obsidian", excluded_paths)

    def test_state_reports_stale_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            shutil.copytree(FIXTURE_VAULT, vault)
            state = Path(tmp) / "state.json"

            first = self.run_bundle("AI 对开源生态有什么结构性冲击？", vault, "--state", str(state))
            old_revision = first["slices"][0]["provenance"]["revision_id"]

            hot = vault / "hot.md"
            hot.write_text(hot.read_text(encoding="utf-8") + "\n新增：AI 影响维护者激励。\n", encoding="utf-8")
            second = self.run_bundle("AI 对开源生态有什么结构性冲击？", vault, "--state", str(state))

            stale = [item for item in second["freshness_report"] if item["citation_status"] == "stale"]
            self.assertTrue(stale)
            self.assertEqual(stale[0]["note_path"], "hot.md")
            self.assertEqual(stale[0]["revision_id"], old_revision)
            self.assertNotEqual(second["slices"][0]["provenance"]["revision_id"], old_revision)

    def test_state_reports_missing_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            shutil.copytree(FIXTURE_VAULT, vault)
            state = Path(tmp) / "state.json"

            self.run_bundle("AI 对开源生态有什么结构性冲击？", vault, "--state", str(state))
            (vault / "hot.md").unlink()
            second = self.run_bundle("AI 对开源生态有什么结构性冲击？", vault, "--state", str(state))

            missing = [item for item in second["freshness_report"] if item["citation_status"] == "missing"]
            self.assertTrue(missing)
            self.assertEqual(missing[0]["note_path"], "hot.md")
            self.assertEqual(second["slices"], [])


if __name__ == "__main__":
    unittest.main()
