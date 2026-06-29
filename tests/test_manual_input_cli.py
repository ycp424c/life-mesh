from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sqlite3
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from lifemesh import cli

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VAULT = ROOT / "tests" / "fixtures" / "obsidian-vault"


class FakeVectorBackend:
    def setup(self, con: sqlite3.Connection, extension_path: Path) -> None:
        return None

    def insert(self, con: sqlite3.Connection, rowid: int, vector: list[float]) -> None:
        return None

    def delete(self, con: sqlite3.Connection, rowids: list[int]) -> None:
        return None

    def search(self, con: sqlite3.Connection, vector: list[float], limit: int) -> list[tuple[int, float]]:
        rows = con.execute(
            "SELECT embedding_id, vector_json FROM embedding_records WHERE status = 'ready'"
        ).fetchall()
        ranked = []
        for row in rows:
            stored = json.loads(row["vector_json"])
            width = max(len(stored), len(vector))
            left = stored + [0.0] * (width - len(stored))
            right = vector + [0.0] * (width - len(vector))
            distance = math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(width)))
            ranked.append((int(row["embedding_id"]), distance))
        ranked.sort(key=lambda item: item[1])
        return ranked[:limit]


class FirstRowsVectorBackend(FakeVectorBackend):
    def search(self, con: sqlite3.Connection, vector: list[float], limit: int) -> list[tuple[int, float]]:
        rows = con.execute(
            "SELECT embedding_id FROM embedding_records WHERE status = 'ready' ORDER BY embedding_id LIMIT ?",
            (limit,),
        ).fetchall()
        return [(int(row["embedding_id"]), 0.0) for row in rows]


class FakeLMStudio:
    def __init__(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), FakeLMHandler)
        self.server.fail_embeddings = False
        self.server.fail_vlm = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1"

    def __enter__(self) -> "FakeLMStudio":
        self.thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


class FakeLMHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path.endswith("/embeddings"):
            if self.server.fail_embeddings:
                self.send_error(500, "embedding failed")
                return
            text = str(payload.get("input", ""))
            self._json({"data": [{"embedding": _embedding(text)}]})
            return
        if self.path.endswith("/chat/completions"):
            if self.server.fail_vlm:
                self.send_error(500, "vlm failed")
                return
            self._json({"choices": [{"message": {"content": "receipt total from screenshot"}}]})
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _embedding(text: str) -> list[float]:
    lower = text.lower()
    terms = [
        "garden",
        "meeting",
        "updated",
        "receipt",
        "task",
        "event",
        "memory",
        "fact",
        "candidate",
        "manual",
        "ai",
    ]
    values = [float(lower.count(term)) for term in terms]
    if not any(values):
        values[0] = float(len(lower) % 7) / 10.0
    return values


class ManualInputCliTest(unittest.TestCase):
    def test_add_note_search_show_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)

            added = self.run_json(["input", "add", "--kind", "note", "--text", "garden manual note", "--tag", "garden"], home)
            input_id = added["input_id"]

            self.assertEqual(added["status"], "active")
            self.assertEqual(added["embedding_status"], "ready")
            self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((home / "lifemesh.db").stat().st_mode), 0o600)

            hits = self.run_json(["input", "search", "garden"], home)
            self.assertEqual(hits[0]["input_id"], input_id)
            self.assertEqual(hits[0]["record"]["kind"], "note")

            shown = self.run_json(["input", "show", input_id], home)
            self.assertEqual(shown["text"], "garden manual note")
            self.assertEqual(shown["audit_events"][0]["action"], "add")

            listed = self.run_json(["input", "list"], home)
            self.assertEqual(listed[0]["input_id"], input_id)

    def test_screenshot_add_copies_asset_stores_extraction_and_searches_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"not a real png but enough for local tests")

            added = self.run_json(
                ["input", "add", "--kind", "screenshot", "--file", str(image), "--text", "receipt image"],
                home,
            )

            stored_path = Path(added["stored_path"])
            self.assertTrue(stored_path.exists())
            self.assertIn("raw-assets/manual-input", str(stored_path))
            self.assertEqual(stat.S_IMODE(stored_path.stat().st_mode), 0o600)
            self.assertEqual(added["extraction_status"], "ready")
            self.assertIn("receipt total", added["extractions"][0]["text"])

            hits = self.run_json(["input", "search", "receipt"], home)
            self.assertEqual(hits[0]["input_id"], added["input_id"])

    def test_update_reembeds_updates_title_and_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(["input", "add", "--kind", "note", "--text", "garden old"], home)["input_id"]

            updated = self.run_json(["input", "update", input_id, "--text", "updated meeting"], home)

            self.assertEqual(updated["title"], "updated meeting")
            self.assertEqual([item["status"] for item in updated["embeddings"]], ["stale", "ready"])
            self.assertEqual(updated["audit_events"][-1]["action"], "update")
            self.assertNotIn("updated meeting", json.dumps(updated["audit_events"], ensure_ascii=False))
            self.assertIn("text_hash", updated["audit_events"][-1]["payload"])
            hits = self.run_json(["input", "search", "updated"], home)
            self.assertEqual(hits[0]["input_id"], input_id)

    def test_revoke_excludes_input_from_search_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(["input", "add", "--kind", "note", "--text", "garden revoke marker"], home)["input_id"]

            revoked = self.run_json(["input", "revoke", input_id], home)

            self.assertEqual(revoked["status"], "revoked")
            hits = self.run_json(["input", "search", "garden revoke marker"], home)
            self.assertEqual([hit["input_id"] for hit in hits if hit["input_id"] == input_id], [])
            bundle = self.run_json(["bundle", "garden revoke marker", "--source", "manual-input"], home)
            self.assertEqual(bundle["slices"], [])

    def test_delete_removes_managed_asset_and_keeps_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"image")
            added = self.run_json(
                ["input", "add", "--kind", "screenshot", "--file", str(image), "--text", "delete receipt"],
                home,
            )
            stored_path = Path(added["stored_path"])

            deleted = self.run_json(["input", "delete", added["input_id"]], home)

            self.assertFalse(stored_path.exists())
            self.assertEqual(deleted["status"], "deleted")
            self.assertIsNone(deleted["text"])
            self.assertIsNone(deleted["content_hash"])
            self.assertEqual(deleted["tags"], [])
            self.assertEqual(deleted["embeddings"], [])
            self.assertEqual(deleted["audit_events"][-1]["action"], "delete")

    def test_promote_each_target_type_preserves_derivation(self) -> None:
        cases = [
            ("task", ["--title", "task title"]),
            ("event", ["--title", "event title", "--starts-at", "2026-06-29T10:00:00+08:00"]),
            ("memory", ["--text", "memory text"]),
            ("fact", ["--statement", "fact statement"]),
            ("candidate", ["--statement", "candidate statement", "--type", "fact"]),
        ]
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)

            for target, fields in cases:
                input_id = self.run_json(
                    ["input", "add", "--kind", "note", "--text", f"{target} promotion source"],
                    home,
                )["input_id"]
                promoted = self.run_json(["input", "promote", input_id, "--to", target, *fields], home)
                self.assertEqual(promoted["target_type"], target)
                self.assertEqual(promoted["derived_from_input_id"], input_id)
                self.assertEqual(promoted["input"]["status"], "promoted")
                self.assertEqual(promoted["input"]["derived_objects"][0]["derived_from_input_id"], input_id)

    def test_candidate_promote_rejects_unknown_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(["input", "add", "--kind", "note", "--text", "candidate source"], home)["input_id"]

            result = self.run_cli(
                ["input", "promote", input_id, "--to", "candidate", "--statement", "candidate statement", "--type", "person"],
                home,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--type must be one of", result.stderr)

    def test_bundle_all_merges_obsidian_and_manual_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            self.run_json(["input", "add", "--kind", "note", "--text", "manual bundle marker"], home)

            bundle = self.run_json(
                [
                    "bundle",
                    "manual bundle marker AI 对开源生态",
                    "--source",
                    "all",
                    "--vault",
                    str(FIXTURE_VAULT),
                    "--max-slices",
                    "5",
                ],
                home,
            )

            self.assertEqual(bundle["permission_scope"]["allowed_sources"], ["obsidian", "manual-input"])
            sources = {item["provenance"]["source"] for item in bundle["slices"]}
            self.assertIn("obsidian", sources)
            self.assertIn("manual-input", sources)

    def test_missing_manual_config_degrades_to_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            result = self.run_cli(["input", "list"], home, patch_backend=False)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), [])

    def test_sqlite_vec_load_failure_degrades_to_fts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            extension = self.write_config(home, lm.base_url)
            extension.write_text("not a sqlite extension", encoding="utf-8")

            added = self.run_json(["input", "add", "--kind", "note", "--text", "garden degraded vector"], home, patch_backend=False)
            hits = self.run_json(["input", "search", "garden"], home, patch_backend=False)

            self.assertEqual(added["embedding_status"], "ready")
            self.assertEqual(hits[0]["input_id"], added["input_id"])
            self.assertIn("vector_error", added["audit_events"][-1]["payload"])

    def test_lmstudio_embedding_failure_saves_record_and_searches_with_fts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            lm.server.fail_embeddings = True

            added = self.run_json(["input", "add", "--kind", "note", "--text", "garden"], home)
            hits = self.run_json(["input", "search", "garden"], home)

            self.assertEqual(added["embedding_status"], "failed")
            self.assertEqual(hits[0]["input_id"], added["input_id"])
            self.assertIn("embedding_error", added["audit_events"][-1]["payload"])

    def test_screenshot_vlm_failure_saves_asset_and_text_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            lm.server.fail_vlm = True
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"image")

            added = self.run_json(
                ["input", "add", "--kind", "screenshot", "--file", str(image), "--text", "fallback receipt"],
                home,
            )

            self.assertEqual(added["extraction_status"], "failed")
            self.assertTrue(Path(added["stored_path"]).exists())
            self.assertIn("extraction_error", added["audit_events"][-1]["payload"])
            hits = self.run_json(["input", "search", "fallback"], home)
            self.assertEqual(hits[0]["input_id"], added["input_id"])

    def test_screenshot_no_extract_without_text_keeps_managed_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            image = Path(tmp) / "shot.png"
            image.write_bytes(b"image")

            added = self.run_json(
                ["input", "add", "--kind", "screenshot", "--file", str(image), "--no-extract"],
                home,
            )

            self.assertEqual(added["embedding_status"], "failed")
            self.assertEqual(added["extraction_status"], "skipped")
            self.assertTrue(Path(added["stored_path"]).exists())
            self.assertIn("embedding_error", added["audit_events"][-1]["payload"])

    def test_fts_hit_is_candidate_even_when_vector_topn_misses_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            for index in range(25):
                text = "needle exact marker" if index == 24 else f"generic filler {index}"
                self.run_json(["input", "add", "--kind", "note", "--text", text], home)

            hits = self.run_json(["input", "search", "needle", "--limit", "1"], home, backend=FirstRowsVectorBackend)

            self.assertEqual(hits[0]["record"]["text"], "needle exact marker")

    def test_date_only_occurred_at_does_not_break_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "date marker", "--occurred-at", "2026-06-29"],
                home,
            )["input_id"]

            hits = self.run_json(["input", "search", "date"], home)

            self.assertEqual(hits[0]["input_id"], input_id)

    def test_search_can_explicitly_return_revoked_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(["input", "add", "--kind", "note", "--text", "revoked marker"], home)["input_id"]
            self.run_json(["input", "revoke", input_id], home)

            default_hits = self.run_json(["input", "search", "revoked marker"], home)
            revoked_hits = self.run_json(["input", "search", "revoked marker", "--status", "revoked"], home)

            self.assertNotIn(input_id, [hit["input_id"] for hit in default_hits])
            self.assertEqual(revoked_hits[0]["input_id"], input_id)

    def test_deleted_input_cannot_be_revoked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(["input", "add", "--kind", "note", "--text", "delete then revoke"], home)["input_id"]
            self.run_json(["input", "delete", input_id], home)

            result = self.run_cli(["input", "revoke", input_id], home)

            self.assertEqual(result.returncode, 2)
            self.assertIn("Cannot revoke deleted input", result.stderr)

    def test_sensitive_manual_input_is_reported_as_excluded_from_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            input_id = self.run_json(
                ["input", "add", "--kind", "note", "--text", "sensitive marker", "--sensitivity", "Sensitive"],
                home,
            )["input_id"]

            bundle = self.run_json(["bundle", "sensitive marker", "--source", "manual-input"], home)

            self.assertEqual(bundle["slices"], [])
            self.assertEqual(
                bundle["excluded_sources"],
                [{"source": "manual-input", "input_id": input_id, "reason": "sensitivity_cap_exceeded"}],
            )

    def test_manual_bundle_content_does_not_duplicate_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeLMStudio() as lm:
            home = Path(tmp) / "home"
            self.write_config(home, lm.base_url)
            self.run_json(["input", "add", "--kind", "note", "--text", "single line marker"], home)

            bundle = self.run_json(["bundle", "single line marker", "--source", "manual-input"], home)

            self.assertEqual(bundle["slices"][0]["content"], "single line marker")

    def write_config(self, home: Path, base_url: str) -> Path:
        home.mkdir(parents=True, exist_ok=True)
        extension = home / "vec0"
        extension.write_bytes(b"")
        (home / "config.json").write_text(
            json.dumps(
                {
                    "lmstudio_base_url": base_url,
                    "embedding_model": "fake-embedding",
                    "vlm_model": "fake-vlm",
                    "sqlite_vec_extension": str(extension),
                }
            ),
            encoding="utf-8",
        )
        return extension

    def run_json(self, argv: list[str], home: Path, *, patch_backend: bool = True, backend: type = FakeVectorBackend) -> object:
        result = self.run_cli(argv, home, patch_backend=patch_backend, backend=backend)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def run_cli(self, argv: list[str], home: Path, *, patch_backend: bool = True, backend: type = FakeVectorBackend) -> object:
        stdout = io.StringIO()
        stderr = io.StringIO()
        env = {"LIFEMESH_HOME": str(home)}
        patches = [mock.patch.dict(os.environ, env, clear=True)]
        if patch_backend:
            patches.append(mock.patch("lifemesh.manual_input.SqliteVecBackend", backend))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
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
