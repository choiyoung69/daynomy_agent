"""Independent regression-author contracts; no model, HTTP, or database calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import admin_feedback_queue as queue


REGRESSION = '''#![forbid(unsafe_code)]
#[path = "../src/feedback_detail.rs"]
mod feedback_detail;

#[test]
fn absent_positive_id() {
    assert_eq!(feedback_detail::detail("42", &serde_json::json!([])).0, 404);
}

#[test]
fn malformed_id() {
    assert_eq!(feedback_detail::detail("abc", &serde_json::json!([])).0, 400);
}

#[test]
fn overflowing_id() {
    assert_eq!(feedback_detail::detail("9223372036854775808", &serde_json::json!([])).0, 400);
}
'''


class RegressionArtifactTests(unittest.TestCase):
    def rejected(self, text, feature="detail"):
        with self.assertRaises(ValueError):
            queue.validate_regression_tests(text, feature)

    def test_three_real_pure_asserting_tests_are_accepted(self):
        queue.validate_regression_tests(REGRESSION, "detail")

    def test_fewer_than_three_tests_are_rejected(self):
        self.rejected(REGRESSION[:REGRESSION.index("#[test]\nfn overflowing_id")])

    def test_attribute_occurrences_in_comments_do_not_count_as_tests(self):
        self.rejected(REGRESSION[:REGRESSION.index("#[test]\nfn malformed_id")] +
                      "\n// #[test] fn fake_one() { assert!(true); }\n"
                      "// #[test] fn fake_two() { assert!(true); }\n")

    def test_empty_test_functions_do_not_replace_assertions(self):
        self.rejected(REGRESSION.replace(
            'assert_eq!(feedback_detail::detail("abc", &serde_json::json!([])).0, 400);', ""))

    def test_forbid_unsafe_attribute_is_required(self):
        self.rejected(REGRESSION.replace("#![forbid(unsafe_code)]", ""))

    def test_correct_feature_module_and_relative_path_are_required(self):
        self.rejected(REGRESSION, "list")
        self.rejected(REGRESSION.replace("../src/feedback_detail.rs", "../../other/src/feedback_detail.rs"))

    def test_ignored_or_conditionally_disabled_tests_are_rejected(self):
        for attribute in ("#[ignore]", '#[ignore = "later"]', "#[cfg(any())]"):
            with self.subTest(attribute=attribute):
                self.rejected(REGRESSION.replace("#[test]", attribute + "\n#[test]", 1))

    def test_side_effectful_test_sources_are_rejected(self):
        for expression in ('std::fs::read("secret")',
                           'std::process::Command::new("sh").status()',
                           'std::net::TcpStream::connect("127.0.0.1:1")',
                           'std::env::var("TOKEN")',
                           'include_str!("other.rs")'):
            with self.subTest(expression=expression):
                self.rejected(REGRESSION.replace("fn malformed_id() {", "fn malformed_id() {\n    let _ = " + expression + ";"))


class RevisionFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="regression-revision-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.experiment = queue.Experiment(self.root / "run", 3, 30, executable="unused-test-executable")
        self.candidate = self.experiment.candidate
        tests = self.candidate / "tests"
        original = tests / "feedback_detail_contract.rs"
        original.write_text(REGRESSION)
        self.artifact = tests / "feedback_detail_regression.rs"
        self.artifact.write_text(REGRESSION)
        self.findings = ["TEST_REVISION add missing malformed-ID regression cases"]
        self.experiment.pending_test_revisions = {"detail": self.findings.copy()}
        self.experiment.previous_review_revisions = {}
        self.experiment.frozen_tests = {"tests/feedback_detail_contract.rs": self.sha(original)}
        self.experiment.regression_artifacts = {"detail": {
            "path": "tests/feedback_detail_regression.rs", "sha256": self.sha(self.artifact),
            "findings": self.findings.copy(), "identity": {"role": "test_author"}}}
        self.experiment._verified_regression_checks = {}
        self.experiment.generated = {
            str(path.relative_to(self.candidate)): self.sha(path)
            for path in self.candidate.rglob("*") if path.is_file()
        }
        self.evidence = {"detail": {"red": True, "green": True, "sha256": self.sha(self.artifact)}}

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def clear(self, final=True):
        try:
            self.experiment.clear_test_revisions(self.evidence, final_checks_passed=final)
        except (ValueError, RuntimeError):
            # Rejecting stale evidence explicitly and retaining it for repair are
            # both valid; silently dropping a pending request is not.
            pass

    def assert_pending(self):
        self.assertEqual(self.experiment.pending_test_revisions, {"detail": self.findings})


class PendingRevisionTests(RevisionFixture, unittest.TestCase):
    def test_fabricated_success_booleans_cannot_clear_pending(self):
        self.clear()
        self.assert_pending()

    def test_failed_final_gate_cannot_clear_even_verified_regression(self):
        self.experiment._verified_regression_checks = self.evidence.copy()
        self.clear(final=False)
        self.assert_pending()

    def test_changed_regression_bytes_cannot_clear_pending(self):
        self.experiment._verified_regression_checks = self.evidence.copy()
        self.artifact.write_text(REGRESSION + "\n// changed after check\n")
        self.clear()
        self.assert_pending()

    def test_changed_original_contract_cannot_clear_pending(self):
        self.experiment._verified_regression_checks = self.evidence.copy()
        (self.candidate / "tests/feedback_detail_contract.rs").write_text(REGRESSION + "\n// changed\n")
        self.clear()
        self.assert_pending()

    def test_unaddressed_new_findings_cannot_clear_pending(self):
        self.experiment._verified_regression_checks = self.evidence.copy()
        self.experiment.regression_artifacts["detail"]["findings"] = ["different request"]
        self.clear()
        self.assert_pending()


class VerificationFlowTests(RevisionFixture, unittest.TestCase):
    """Replace only external commands: verify must still parse real-shaped logs.

    These test the harness gate, not Rust correctness. The separate live run must
    supply actual Cargo and HTTP evidence before claiming the feature complete.
    """
    def setUp(self):
        super().setUp()
        list_contract = self.candidate / "tests/feedback_list_contract.rs"
        list_contract.write_text(REGRESSION.replace("feedback_detail", "feedback_list"))
        self.experiment.frozen_tests["tests/feedback_list_contract.rs"] = self.sha(list_contract)
        self.experiment.generated["tests/feedback_list_contract.rs"] = self.sha(list_contract)
        self.calls = []
        self.original_sources = {
            feature: (self.candidate / ("src/feedback_" + feature + ".rs")).read_text()
            for feature in ("list", "detail")}

    def verify(self, *, http_status="passed", fail_command=None, mutate=None, red_summary=None):
        def command(name, args, deadline, allowed=(0,)):
            self.calls.append(name)
            if name == fail_command:
                raise RuntimeError("synthetic command failure")
            red = name.startswith("red-")
            if red:
                for feature in ("list", "detail"):
                    self.assertIn("501", (self.candidate / ("src/feedback_" + feature + ".rs")).read_text())
                summary = red_summary or "test result: FAILED. 0 passed; 3 failed; 0 ignored; 0 measured; 0 filtered out"
                code = 101
            else:
                for feature, original in self.original_sources.items():
                    self.assertEqual((self.candidate / ("src/feedback_" + feature + ".rs")).read_text(), original)
                summary = "test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
                code = 0
            log = self.experiment.directory / (name + ".log")
            log.write_text(summary + "\n")
            self.assertIn(code, allowed)
            return {"name": name, "exit_code": code, "log": str(log)}

        def http_gate(*args, **kwargs):
            if mutate:
                mutate()
            return {"status": http_status, "case_sha256": self.sha(queue.BASE / "tests/cases.json"),
                    "results": [{"case": "unit-fixture-http", "passed": http_status == "passed"}]}

        with patch.object(self.experiment, "command", side_effect=command), patch(
                "admin_feedback_gate.run_gate", side_effect=http_gate):
            return self.experiment.verify(time.monotonic() + 10)

    def test_success_requires_regression_red_and_green_before_pending_is_cleared(self):
        result = self.verify()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.experiment.pending_test_revisions, {})
        self.assertIn("red-detail-regression", self.calls)
        self.assertIn("unit-detail-regression", self.calls)
        self.assertLess(self.calls.index("red-detail-regression"), self.calls.index("unit-detail-regression"))
        self.assertIn("clippy", self.calls)

    def test_failed_regression_red_preserves_pending_and_restores_sources(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.verify(fail_command="red-detail-regression")
        self.assert_pending()
        for feature, source in self.original_sources.items():
            self.assertEqual((self.candidate / ("src/feedback_" + feature + ".rs")).read_text(), source)

    def test_compile_error_is_not_accepted_as_red_test_failure(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.verify(red_summary="error[E0308]: mismatched types")
        self.assert_pending()

    def test_failed_regression_green_preserves_pending(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.verify(fail_command="unit-detail-regression")
        self.assert_pending()

    def test_failed_http_gate_preserves_pending(self):
        self.assertNotEqual(self.verify(http_status="failed")["status"], "completed")
        self.assert_pending()

    def test_changed_artifact_during_verification_cannot_clear_pending(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.verify(mutate=lambda: self.artifact.write_text(REGRESSION + "\n// changed during gate\n"))
        self.assert_pending()


class RegressionAuthorDispatchTests(RevisionFixture, unittest.TestCase):
    def test_revision_author_is_isolated_and_import_is_additional_only(self):
        original = self.candidate / "tests/feedback_detail_contract.rs"
        original_bytes = original.read_bytes()
        http_cases = (queue.BASE / "tests/cases.json").read_bytes()
        # A fresh author must create the supplement; remove the fixture copy.
        self.artifact.unlink()
        self.experiment.regression_artifacts = {}
        self.experiment.generated.pop("tests/feedback_detail_regression.rs")
        dispatched = []

        def author(role, worker, prompt, evidence):
            dispatched.append(role)
            self.assertEqual(role, "test_author")
            self.assertTrue((worker / "reference.txt").is_file())
            self.assertTrue((worker / "review-findings.json").is_file())
            self.assertEqual((worker / "frozen-original-tests.rs").read_bytes(), original_bytes)
            self.assertFalse((worker / "candidate").exists())
            self.assertFalse(any(path.name == "feedback_detail.rs" for path in worker.rglob("*")))
            self.assertFalse(any(path.name == "feedback_list.rs" for path in worker.rglob("*")))
            self.assertIn("TEST_REVISION", (worker / "review-findings.json").read_text())
            (worker / "feedback_detail_regression.rs").write_text(REGRESSION)
            return {"status": "tests_written", "findings": []}, {"role": "test_author", "model": "unit-fixture"}

        with patch.object(queue, "CliAgent", return_value=author) as cli:
            result = self.experiment.agent(queue.Job("test-regression-detail", "agent"), time.monotonic() + 10)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(dispatched, ["test_author"])
        self.assertEqual(cli.call_args.kwargs["max_attempts"], 1)
        self.assertEqual(cli.call_args.kwargs["model"], queue.ROLES["test_author"]["model"])
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual((queue.BASE / "tests/cases.json").read_bytes(), http_cases)
        self.assertEqual(self.artifact.read_text(), REGRESSION)
        self.assertEqual(self.experiment.regression_artifacts["detail"]["sha256"], self.sha(self.artifact))
        self.assert_pending()

    def test_review_is_blocked_while_test_revision_is_pending(self):
        with patch.object(queue, "CliAgent") as cli:
            result = self.experiment.agent(queue.Job("review-detail", "agent"), time.monotonic() + 10)
        self.assertNotEqual(result["status"], "completed")
        cli.assert_not_called()
        self.assert_pending()


class RecoveryRoutingTests(unittest.TestCase):
    def setUp(self):
        # Reuse the preserved original parent-fixture builder, not its expected
        # dispatch decisions. This setup only creates temporary local files.
        from test_admin_feedback_queue import ExperimentIsolationTests
        self.fixture = ExperimentIsolationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def planned_jobs(self, findings):
        parent, verification = self.fixture.verified_parent_artifacts()
        verification["status"] = "passed"
        for case in verification["http"]["results"]:
            case["passed"] = True
        (parent / "verification.json").write_text(json.dumps(verification))
        state = {"status": "failed", "tasks": {
            "verify": {"status": "completed"},
            "review-list": {"status": "failed", "result": {
                "verdict": {"status": "revise", "findings": findings}}}}}
        (parent / "queue/state.json").write_text(json.dumps(state))
        before = queue.files(parent)
        with patch.object(queue, "TaskQueue") as scheduler, patch.object(queue, "CliAgent") as cli:
            scheduler.return_value.run.return_value = {"status": "failed"}
            self.fixture.experiment.repair_once(parent)
            jobs = scheduler.call_args.args[0]
        cli.assert_not_called()
        self.assertEqual(queue.files(parent), before)
        return {job.id: job for job in jobs}

    def test_test_only_revision_dispatches_author_instead_of_source_repair(self):
        jobs = self.planned_jobs(["TEST_REVISION add missing integer overflow cases"])
        self.assertIn("test-regression-list", jobs)
        self.assertFalse(any(name.startswith("repair-") for name in jobs))
        self.assertEqual(jobs["verify"].deps, ("test-regression-list",))
        self.assertEqual(jobs["review-list"].deps, ("verify",))
        self.assertEqual(jobs["review-detail"].deps, ("verify",))

    def test_mixed_revision_dispatches_author_and_separate_source_repair(self):
        jobs = self.planned_jobs(["TEST_REVISION add missing boundary assertion",
                                  "CODE_REVISION list field set is wrong"])
        self.assertIn("test-regression-list", jobs)
        self.assertIn("repair-list", jobs)
        self.assertEqual(set(jobs["verify"].deps), {"test-regression-list", "repair-list"})


if __name__ == "__main__":
    unittest.main()
