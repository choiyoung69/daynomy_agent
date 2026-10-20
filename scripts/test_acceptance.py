"""Tests for false-positive risks in the acceptance gate, not for the future Rust app."""
import json
import os
import unittest
from unittest.mock import patch
from acceptance import (
    Database, EnvironmentFailure, INVALID, REASONS, check_response, check_storage, validate_local_url,
)


class GateTests(unittest.TestCase):
    def test_database_uri_is_split_into_libpq_variables(self):
        with patch.dict(os.environ, {"PGHOSTADDR": "192.0.2.1", "PGSERVICE": "unrelated",
                                     "PGPASSWORD": "inherited"}):
            db = Database("postgresql://pilot@127.0.0.1:55439/daynomy_feedback_test")
        self.assertEqual(db.env["PGHOST"], "127.0.0.1")
        self.assertEqual(db.env["PGPORT"], "55439")
        self.assertEqual(db.env["PGDATABASE"], "daynomy_feedback_test")
        self.assertEqual(db.env["PGUSER"], "pilot")
        for key in ("PGHOSTADDR", "PGSERVICE", "PGPASSWORD"):
            self.assertNotIn(key, db.env)

    def test_success_without_persistence_fails(self):
        before = {"count": 0, "max_id": 0}
        with self.assertRaises(AssertionError):
            check_storage(before, before, [], ("hi", "/"))

    def test_rejected_request_that_saved_data_fails(self):
        with self.assertRaises(AssertionError):
            check_storage({"count": 0, "max_id": 0}, {"count": 1, "max_id": 1}, [{}], None)

    def test_wrong_stored_content_fails(self):
        row = dict(id=1, content=" hi ", page_path="/", status="PENDING",
                   created_at="2026-10-20T00:00:00+00:00", updated_at="2026-10-20T00:00:00+00:00")
        with self.assertRaises(AssertionError):
            check_storage({"count": 0, "max_id": 0}, {"count": 1, "max_id": 1}, [row], ("hi", "/"))
        row["content"] = "hi"
        check_storage({"count": 0, "max_id": 0}, {"count": 1, "max_id": 1}, [row], ("hi", "/"))

    def test_always_204_fails_security_check(self):
        with self.assertRaises(AssertionError):
            check_response(204, {}, b"", 403)

    def test_204_with_body_fails(self):
        with self.assertRaises(AssertionError):
            check_response(204, {}, b"{}", 204)

    def test_validation_order_independent_but_wrong_fields_fail(self):
        expected = (REASONS["content_blank"], REASONS["path_blank"])
        body = {"code": "INVALID_REQUEST", "message": INVALID,
                "errors": [{"field": f, "reason": r} for f, r in reversed(expected)]}
        headers = {"Content-Type": "application/json"}
        check_response(400, headers, json.dumps(body).encode(), 400, expected)
        body["errors"] = body["errors"][:1]
        with self.assertRaises(AssertionError):
            check_response(400, headers, json.dumps(body).encode(), 400, expected)

    def test_input_echo_is_rejected(self):
        field, reason = REASONS["content_blank"]
        body = {"code": "INVALID_REQUEST", "message": INVALID,
                "errors": [{"field": field, "reason": reason, "rejectedValue": "private"}]}
        with self.assertRaises(AssertionError):
            check_response(400, {"Content-Type": "application/json"}, json.dumps(body).encode(),
                           400, ((field, reason),))

    def test_remote_or_non_test_database_is_rejected(self):
        for url in ("postgresql://example.com/daynomy_test", "postgresql://localhost/daynomy",
                    "postgresql://localhost/daynomy_test?host=example.com"):
            with self.subTest(url=url), self.assertRaises(EnvironmentFailure):
                validate_local_url(url, database=True)
        validate_local_url("postgresql://localhost/daynomy_test", database=True)


if __name__ == "__main__":
    unittest.main()
