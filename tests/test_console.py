from __future__ import annotations

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path
from urllib import request

from lifemesh.candidates import CandidateStore
from lifemesh.config import load_config
from lifemesh.console_server import create_console_server
from lifemesh.console_service import ConsoleService
from lifemesh.knowledge_workflow import KnowledgeWorkflow
from lifemesh.manual_input import ManualInputStore
from lifemesh.rumor_claims import RumorClaimStore


class ConsoleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.config = load_config(home=str(self.home))
        self.input_store = ManualInputStore(self.config)
        self.rumor_store = RumorClaimStore(self.config)
        self.candidate_store = CandidateStore(self.config)
        self.input_id = self.input_store.add(
            kind="note",
            text="warm garden marker for console",
            sensitivity="Private",
            tags=["garden", "console"],
        )["input_id"]
        self.sensitive_id = self.input_store.add(
            kind="note",
            text="sensitive orchard marker stays visible",
            sensitivity="Sensitive",
        )["input_id"]
        self.rumor_id = self.rumor_store.add(
            claim_text="unknown seed may affect project dawn",
            claim_type="risk_claim",
            entity_mentions=["Project Dawn"],
            relation_mentions=["unknown seed affects Project Dawn"],
            user_relevance="medium",
            impact="high",
        )["rumor_claim_id"]
        self.candidate_id = self.candidate_store.add(
            summary="Garden notes could become a reusable preference",
            candidate_type="preference",
            source_refs=[f"manual-input:{self.input_id}"],
            confidence=0.74,
            risk="low",
        )["candidate_id"]
        self.service = ConsoleService(self.config)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_overview_and_read_views_use_real_local_records(self) -> None:
        overview = self.service.overview()
        inputs = self.service.records("inputs")
        rumors = self.service.records("rumors")
        candidates = self.service.records("candidates")

        self.assertEqual(overview["counts"]["inputs"], 2)
        self.assertEqual(overview["counts"]["rumors"], 1)
        self.assertEqual(overview["counts"]["candidates"], 1)
        self.assertEqual(overview["counts"]["sensitive"], 1)
        self.assertEqual({item["id"] for item in inputs}, {self.input_id, self.sensitive_id})
        self.assertEqual(rumors[0]["id"], self.rumor_id)
        self.assertEqual(candidates[0]["id"], self.candidate_id)

    def test_canonical_objects_are_browsable_with_acceptance_and_provenance(self) -> None:
        fact = KnowledgeWorkflow(self.config).promote_manual_input(
            self.input_id,
            "fact",
            {"statement": "A warm garden is a canonical console fact"},
        )

        objects = self.service.records("objects")
        detail = self.service.record("objects", fact["object_id"])
        overview = self.service.overview()

        self.assertEqual(objects[0]["id"], fact["object_id"])
        self.assertEqual(objects[0]["kind"], "fact")
        self.assertEqual(objects[0]["status"], "valid")
        self.assertEqual(detail["data"]["acceptance"]["acceptance_path"], "manual")
        self.assertEqual(detail["data"]["source_links"][0]["source_status"], "current")
        self.assertEqual(overview["counts"]["objects"], 1)

    def test_open_reviews_show_the_triggering_source_and_target_context(self) -> None:
        fact = KnowledgeWorkflow(self.config).promote_manual_input(
            self.input_id,
            "fact",
            {"statement": "Changing the garden source opens a review"},
        )
        self.input_store.update(self.input_id, text="garden source changed after acceptance")

        reviews = self.service.records("reviews")
        detail = self.service.record("reviews", reviews[0]["id"])
        overview = self.service.overview()

        self.assertEqual(reviews[0]["kind"], "source_stale")
        self.assertEqual(reviews[0]["status"], "open")
        self.assertEqual(detail["data"]["target"]["object_id"], fact["object_id"])
        self.assertEqual(detail["data"]["trigger_source"]["status"], "stale")
        self.assertEqual(overview["counts"]["reviews"], 1)
        self.assertEqual(overview["queues"]["object_review"], 1)

    def test_open_candidate_review_keeps_candidate_target_context(self) -> None:
        candidate = KnowledgeWorkflow(self.config).handoff_manual_input(
            self.input_id,
            {"statement": "Garden source may become a fact", "type": "fact"},
        )
        self.input_store.update(self.input_id, text="candidate source changed after suggestion")

        reviews = self.service.records("reviews")
        detail = self.service.record("reviews", reviews[0]["id"])
        overview = self.service.overview()

        self.assertEqual(reviews[0]["target_scope"], "candidate")
        self.assertEqual(reviews[0]["target_id"], candidate["candidate_id"])
        self.assertEqual(detail["data"]["target"]["candidate_id"], candidate["candidate_id"])
        self.assertEqual(detail["data"]["trigger_source"]["status"], "stale")
        self.assertEqual(overview["queues"]["object_review"], 0)

    def test_sensitive_content_is_visible_but_bundle_requires_explicit_inclusion(self) -> None:
        detail = self.service.record("inputs", self.sensitive_id)
        default_bundle = self.service.assemble_bundle(
            {
                "task": "sensitive orchard marker",
                "sources": ["manual-input"],
                "max_slices": 8,
            }
        )
        included_bundle = self.service.assemble_bundle(
            {
                "task": "sensitive orchard marker",
                "sources": ["manual-input"],
                "max_slices": 8,
                "include_sensitive": True,
            }
        )

        self.assertIn("sensitive orchard marker", detail["data"]["text"])
        self.assertNotIn(
            self.sensitive_id,
            {item["provenance"].get("input_id") for item in default_bundle["slices"]},
        )
        self.assertIn("sensitivity_cap_exceeded", {item["reason"] for item in default_bundle["excluded_sources"]})
        self.assertEqual(included_bundle["permission_scope"]["sensitivity_cap"], "Sensitive")
        self.assertTrue(
            any("sensitive orchard marker" in item["content"] for item in included_bundle["slices"])
        )

    def test_search_graph_and_timeline_keep_domain_boundaries(self) -> None:
        search = self.service.search("garden")
        graph = self.service.graph()
        timeline = self.service.timeline()

        self.assertIn("inputs", {item["domain"] for item in search["results"]})
        self.assertIn("candidates", {item["domain"] for item in search["results"]})
        self.assertIn(f"entity:Project Dawn", {item["id"] for item in graph["nodes"]})
        self.assertIn(
            (f"rumor:{self.rumor_id}", "entity:Project Dawn", "mentions"),
            {(item["source"], item["target"], item["label"]) for item in graph["edges"]},
        )
        self.assertEqual({item["domain"] for item in timeline["items"]}, {"inputs", "rumors", "candidates"})

    def test_global_search_stays_local_and_does_not_wait_for_embedding(self) -> None:
        with mock.patch.object(
            self.service.inputs.client,
            "embed",
            side_effect=AssertionError("Console global search must not call embedding"),
        ):
            search = self.service.search("garden")

        self.assertIn(self.input_id, {item["id"] for item in search["results"]})

    def test_overview_does_not_mutate_database_metadata(self) -> None:
        with sqlite3.connect(self.config.db_path) as con:
            con.execute(
                "INSERT OR REPLACE INTO lifemesh_meta(key, value) VALUES ('vector_status', 'sentinel')"
            )
        observer = sqlite3.connect(self.config.db_path)
        try:
            before = observer.execute("PRAGMA data_version").fetchone()[0]
            self.service.overview()
            after = observer.execute("PRAGMA data_version").fetchone()[0]
            vector_status = observer.execute(
                "SELECT value FROM lifemesh_meta WHERE key = 'vector_status'"
            ).fetchone()[0]
        finally:
            observer.close()

        self.assertEqual(after, before)
        self.assertEqual(vector_status, "sentinel")

    def test_console_database_connection_rejects_writes(self) -> None:
        with self.service.database.connect_read_only() as con:
            self.assertEqual(con.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                con.execute(
                    "UPDATE lifemesh_meta SET value = 'mutated' WHERE key = 'vector_status'"
                )


class ConsoleReadOnlyBoundaryTest(unittest.TestCase):
    def test_empty_home_overview_does_not_create_database_or_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            config = load_config(home=str(home))

            overview = ConsoleService(config).overview()

            self.assertEqual(overview["counts"]["total"], 0)
            self.assertEqual(overview["health"][0]["status"], "empty")
            self.assertFalse(config.db_path.exists())
            self.assertFalse((home / ".database.lock").exists())


class ConsoleHTTPTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = load_config(home=str(Path(self.tmp.name) / "home"))
        ManualInputStore(self.config).add(kind="note", text="console http marker", sensitivity="Private")
        self.server = create_console_server(self.config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.server.allowed_origin

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def test_static_ui_and_overview_have_security_headers_without_cors(self) -> None:
        with request.urlopen(f"{self.origin}/") as response:
            html = response.read().decode("utf-8")
            headers = response.headers
        with request.urlopen(f"{self.origin}/api/overview") as response:
            overview = json.loads(response.read())

        self.assertIn("LifeMesh Console", html)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual(overview["counts"]["inputs"], 1)

    def test_rejects_wrong_host_and_missing_origin(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.putrequest("GET", "/api/overview", skip_host=True)
        connection.putheader("Host", "attacker.example")
        connection.endheaders()
        wrong_host = connection.getresponse()
        wrong_host.read()
        connection.close()

        post = request.Request(
            f"{self.origin}/api/bundles",
            data=json.dumps({"task": "console http marker", "sources": ["manual-input"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(request.HTTPError) as missing_origin:
            request.urlopen(post)

        self.assertEqual(wrong_host.status, 403)
        self.assertEqual(missing_origin.exception.code, 403)
        missing_origin.exception.close()

    def test_same_origin_bundle_request_is_allowed(self) -> None:
        post = request.Request(
            f"{self.origin}/api/bundles",
            data=json.dumps({"task": "console http marker", "sources": ["manual-input"]}).encode(),
            headers={"Content-Type": "application/json", "Origin": self.origin},
            method="POST",
        )
        with request.urlopen(post) as response:
            bundle = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertIn("console http marker", bundle["slices"][0]["content"])


if __name__ == "__main__":
    unittest.main()
