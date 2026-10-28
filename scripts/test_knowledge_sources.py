#!/usr/bin/env python3
"""Exercise source revision handling without network or product data."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from knowledge_sources import capture, pin, validate_snapshot


class SourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="knowledge-source-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "knowledge/wiki").mkdir(parents=True)
        (self.root / "knowledge/wiki/topic.md").write_text('---\nsource_ids: ["E01"]\n---\n')
        self.registry_path = self.root / "knowledge/sources.json"
        self.registry_path.write_text(json.dumps({"sources": [{"id": "E01", "kind": "external",
            "url": "https://example.org/source", "review_status": "catalogued", "content_snapshot": None}]}))
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def source(self):
        return json.loads(self.registry_path.read_text())["sources"][0]

    def fetch(self, body, name="first"):
        report = f"knowledge/evidence/{name}.json"
        with patch("knowledge_sources.retrieve", return_value=(body, "text/plain", "https://example.org/source")):
            status = capture(self.root, ["E01"], report)
        item = json.loads((self.root / report).read_text())["results"][0]
        return status, report, item

    def test_first_capture_requires_pin_and_does_not_mark_source_read(self):
        status, report, item = self.fetch(b"first source")
        self.assertEqual(status, 0)
        self.assertIsNone(self.source()["content_snapshot"])
        self.assertEqual(item["affected_documents"], ["knowledge/wiki/topic.md"])
        pin(self.root, report, "E01", "Inspected synthetic source")
        self.assertEqual(self.source()["review_status"], "catalogued")
        self.assertEqual(self.source()["content_snapshot"]["sha256"], item["candidate_snapshot"]["sha256"])

    def test_changed_source_keeps_old_pin_and_bytes_until_review(self):
        _, first_report, first = self.fetch(b"first source")
        pin(self.root, first_report, "E01", "First review")
        before = self.registry_path.read_bytes()
        status, report, changed = self.fetch(b"second source", "changed")
        self.assertEqual(status, 2)
        self.assertEqual(changed["status"], "changed")
        self.assertEqual(self.registry_path.read_bytes(), before)
        old = validate_snapshot(self.root, first["candidate_snapshot"])
        self.assertEqual(old.read_bytes(), b"first source")
        pin(self.root, report, "E01", "Reviewed change and linked claims")
        self.assertEqual(len(self.source()["snapshot_history"]), 2)
        self.assertEqual(old.read_bytes(), b"first source")

    def test_failed_fetch_preserves_baseline_and_has_no_candidate(self):
        _, report, _ = self.fetch(b"first source")
        pin(self.root, report, "E01", "First review")
        before = self.registry_path.read_bytes()
        with patch("knowledge_sources.retrieve", side_effect=OSError("simulated network failure")):
            self.assertEqual(capture(self.root, ["E01"], "knowledge/evidence/failed.json"), 1)
        item = json.loads((self.root / "knowledge/evidence/failed.json").read_text())["results"][0]
        self.assertEqual(item["status"], "unavailable")
        self.assertNotIn("candidate_snapshot", item)
        self.assertEqual(self.registry_path.read_bytes(), before)
        with self.assertRaises(ValueError):
            pin(self.root, "knowledge/evidence/failed.json", "E01", "Cannot accept")

    def test_unchanged_source_and_report_no_overwrite(self):
        _, report, _ = self.fetch(b"same source")
        pin(self.root, report, "E01", "First review")
        status, _, item = self.fetch(b"same source", "repeat")
        self.assertEqual(status, 0)
        self.assertEqual(item["status"], "unchanged")
        before = (self.root / report).read_bytes()
        with self.assertRaises(ValueError):
            self.fetch(b"different", "first")
        self.assertEqual((self.root / report).read_bytes(), before)

    def test_tampered_candidate_and_stale_baseline_cannot_be_pinned(self):
        _, report, item = self.fetch(b"first source")
        path = self.root / item["candidate_snapshot"]["path"]
        path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            pin(self.root, report, "E01", "Review")
        path.write_bytes(b"first source")
        _, stale, _ = self.fetch(b"other source", "stale")
        pin(self.root, report, "E01", "First review")
        with self.assertRaises(ValueError):
            pin(self.root, stale, "E01", "Stale review")

    def test_path_escape_and_missing_review_note_rejected(self):
        with self.assertRaises(ValueError):
            capture(self.root, ["E01"], "outside.json")
        _, report, item = self.fetch(b"source")
        with self.assertRaises(ValueError):
            pin(self.root, report, "E01", " ")
        snapshot = dict(item["candidate_snapshot"], path="../outside.txt")
        with self.assertRaises(ValueError):
            validate_snapshot(self.root, snapshot)


if __name__ == "__main__":
    unittest.main()
