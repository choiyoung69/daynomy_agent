"""Guard against comparator false positives; no servers or database required."""
import json
import unittest

from acceptance import policy_cases, INVALID
from compare_feedback import (
    response_shape, storage_shape, difference_fields, independent_contract_check, assess_case,
)


class ComparisonTests(unittest.TestCase):
    def http(self, value):
        return response_shape(400, {"Content-Type": "application/json"},
                              json.dumps(value).encode())

    def test_error_order_is_ignored_but_duplicates_and_extra_fields_are_not(self):
        errors = [{"field": "a", "reason": "required"}, {"field": "b", "reason": "required"}]
        baseline = self.http({"errors": errors})
        self.assertEqual(baseline, self.http({"errors": list(reversed(errors))}))
        self.assertNotEqual(baseline, self.http({"errors": errors + [errors[0]]}))
        self.assertNotEqual(baseline, self.http({"errors": errors, "unexpected": True}))

    def test_success_status_alone_does_not_hide_response_body(self):
        self.assertNotEqual(response_shape(204, {}, b""), response_shape(204, {}, b"unexpected"))

    def test_generated_values_differ_but_business_content_must_match(self):
        def shape(identifier, text="hello"):
            row = {"id": identifier, "content": text, "page_path": "/", "status": "PENDING",
                   "created_at": f"2026-10-21T00:00:{identifier:02d}",
                   "updated_at": f"2026-10-21T00:00:{identifier:02d}"}
            return storage_shape({"count": 0, "max_id": 0},
                                 {"count": 1, "max_id": identifier}, [row])
        self.assertEqual(shape(1), shape(2))
        self.assertEqual(difference_fields(shape(1), shape(2, "wrong")), ["rows"])

    def test_equal_wrong_results_still_fail_contract(self):
        observation = (204, {}, b"", {"count": 0, "max_id": 0},
                       {"count": 0, "max_id": 0}, [])
        self.assertEqual(independent_contract_check(
            observation, 204, ("hello", "/"), ()), ["storage"])

    def test_missing_timestamp_and_reused_id_are_visible(self):
        row = {"id": 1, "content": "hello", "page_path": "/", "status": "PENDING",
               "created_at": None, "updated_at": None}
        shape = storage_shape({"count": 1, "max_id": 1},
                              {"count": 2, "max_id": 1}, [row])
        self.assertFalse(shape["generated_ids"])
        self.assertFalse(shape["timestamps_present"])

    def policy_observations(self):
        before = {"count": 0, "max_id": 0}
        row = {"id": 1, "content": "123", "page_path": "/probe", "status": "PENDING",
               "created_at": "2026-10-21T00:00:00+00:00", "updated_at": "2026-10-21T00:00:00+00:00"}
        spring = (204, {}, b"", before, {"count": 1, "max_id": 1}, [row])
        body = json.dumps({"code": "INVALID_REQUEST", "message": INVALID,
                           "errors": [{"field": "requestBody", "reason": "요청 본문을 읽을 수 없습니다."}]}).encode()
        rust = (400, {"Content-Type": "application/json"}, body, before, before, [])
        case = next(c for c in policy_cases() if c[0] == "numeric-content")
        return case, spring, rust

    def test_approved_difference_is_visible_and_both_sides_are_checked(self):
        case, spring, rust = self.policy_observations()
        result = assess_case("policy", case, [spring, rust])
        self.assertEqual(result["outcome"], "EXPECTED_DIFFERENCE")
        self.assertTrue(result["checks_pass"])
        self.assertFalse(result["match"])
        self.assertIn("http.status", result["differences"])

    def test_approved_case_does_not_allow_rust_to_accept_numeric_content(self):
        case, spring, _ = self.policy_observations()
        result = assess_case("policy", case, [spring, spring])
        self.assertFalse(result["checks_pass"])
        self.assertEqual(result["outcome"], "FAIL")

    def test_approved_case_still_rejects_failed_request_that_inserts(self):
        case, spring, rust = self.policy_observations()
        rust_saved = (*rust[:4], spring[4], spring[5])
        result = assess_case("policy", case, [spring, rust_saved])
        self.assertFalse(result["checks_pass"])
        self.assertIn("storage", result["rust"]["contract_failures"])

    def test_approved_case_still_checks_original_stored_value(self):
        case, spring, rust = self.policy_observations()
        spring[5][0]["content"] = "incorrect"
        result = assess_case("policy", case, [spring, rust])
        self.assertFalse(result["checks_pass"])
        self.assertIn("storage", result["spring"]["contract_failures"])

    def test_difference_on_common_case_is_not_automatically_approved(self):
        case, spring, rust = self.policy_observations()
        result = assess_case("contract", case, [spring, rust])
        self.assertFalse(result["checks_pass"])
        self.assertEqual(result["outcome"], "FAIL")


if __name__ == "__main__":
    unittest.main()
