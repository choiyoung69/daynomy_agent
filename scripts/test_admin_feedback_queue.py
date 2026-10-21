"""Local orchestrator safeguards; no model, subprocess, HTTP or database calls."""
from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import admin_feedback_queue as workflow
from task_queue import Job


def contract(feature="list", count=3, extra=""):
    return ('#![forbid(unsafe_code)]\n'
            f'#[path="../src/feedback_{feature}.rs"] mod subject;\n' + extra + '\n' +
            '\n'.join(f'#[test] fn case_{i}() {{ assert_eq!(1, 1); }}' for i in range(count)))


class GeneratedTestValidationTests(unittest.TestCase):
    def test_valid_pure_test_module_is_accepted(self):
        for feature in ("list", "detail"):
            workflow.validate_tests(contract(feature), feature)

    def test_missing_assertions_or_less_than_three_tests_are_rejected(self):
        for text in (contract(count=2), contract().replace('assert_eq!(1, 1);', '')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                workflow.validate_tests(text, "list")

    def test_ignored_unsafe_or_io_tests_are_rejected(self):
        additions = (
            '#[ignore] #[test] fn ignored() {}',
            'fn bad() { unsafe { unreachable!() } }',
            'use std::fs;', 'use std::net;', 'use std::process;', 'use std::env;',
            'const BAD: &str = include_str!("secret");',
        )
        for extra in additions:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                workflow.validate_tests(contract(extra=extra), "list")

    def test_grouped_io_import_is_rejected(self):
        with self.assertRaises(ValueError):
            workflow.validate_tests(contract(extra='use std::{fs}; fn reads_file() { let _ = fs::read_to_string("secret"); }'), "list")

    def test_wrong_module_and_missing_unsafe_prohibition_are_rejected(self):
        variants = [contract("detail"), contract().replace('../src/', '../../src/'),
                    contract().replace('#![forbid(unsafe_code)]\n', ''),
                    contract() + '\n#[path="../src/feedback_detail.rs"] mod other;']
        for text in variants:
            with self.subTest(text=text), self.assertRaises(ValueError):
                workflow.validate_tests(text, "list")


class ExperimentIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="admin-feedback-queue-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.root / "baseline"
        (self.base / "src").mkdir(parents=True)
        (self.base / "tests").mkdir()
        for feature in ("list", "detail"):
            (self.base / f"src/feedback_{feature}.rs").write_text("existing implementation " + feature)
        (self.base / "tests/existing_contract.rs").write_text("existing tests must not be reused")
        (self.base / "Cargo.toml").write_text("trusted baseline manifest")
        original = self.root / "original"
        references = ["feedback/controller/AdminFeedbackController.java", "feedback/service/FeedbackService.java",
                      "feedback/dto/AdminFeedbackPageResponse.java", "feedback/dto/AdminFeedbackResponse.java",
                      "feedback/exception/FeedbackErrorCode.java", "common/exception/GlobalExceptionHandler.java",
                      "common/exception/CommonErrorCode.java", "common/response/ErrorResponse.java",
                      "common/response/ValidationErrorField.java"]
        for name in references:
            path = original / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("reference " + name)
        (self.base / "tests/cases.json").write_text(json.dumps([
            {"name": "list-invalid-page", "path": "/api/admin/feedbacks?page=0"},
            {"name": "detail-not-found", "path": "/api/admin/feedbacks/999"},
            {"name": "list-success", "path": "/api/admin/feedbacks"},
        ]))
        self.baseline_hashes = workflow.files(self.base)
        for target, value in (("BASE", self.base), ("ORIGINAL", original), ("clean_env", lambda: {})):
            patcher = patch.object(workflow, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.experiment = workflow.Experiment(self.root / "run", 3, 10)

    def tearDown(self):
        self.assertEqual(workflow.files(self.base), self.baseline_hashes)

    def test_candidate_starts_with_two_501_sources_and_empty_tests(self):
        for feature in ("list", "detail"):
            path = self.experiment.candidate / f"src/feedback_{feature}.rs"
            self.assertEqual(path.read_text(), workflow.STUBS[feature])
            self.assertIn("501", path.read_text())
        self.assertEqual(list((self.experiment.candidate / "tests").iterdir()), [])
        self.experiment.integrity()
        self.assertEqual(json.loads((self.experiment.directory / "criteria.json").read_text()),
                         {"case_sha256": workflow.digest(self.base / "tests/cases.json")})

    def test_failed_backend_never_calls_transport_or_unlocks_checks(self):
        self.experiment.backend_failed.set()
        with patch.object(workflow, "CliAgent") as transport, patch.object(self.experiment, "verify") as verify:
            result = self.experiment.run()
        transport.assert_not_called()
        verify.assert_not_called()
        self.assertNotEqual(result["status"], "completed")
        for name in ("implement-list", "test-list", "implement-detail", "test-detail"):
            self.assertNotEqual(result["tasks"][name]["status"], "completed")
            self.assertEqual(result["tasks"][name]["result"]["reason"], "model_backend_unavailable")
        for name in ("verify", "review-list", "review-detail"):
            self.assertEqual(result["tasks"][name]["status"], "blocked_dependency")

    def test_first_transport_failure_sets_stop_flag_for_next_dispatch(self):
        failed_call = Mock(side_effect=RuntimeError("private transport detail must not leak"))
        with patch.object(workflow, "CliAgent", return_value=failed_call) as transport:
            first = self.experiment.agent(Job("implement-list", "agent"), time.monotonic() + 10)
            second = self.experiment.agent(Job("test-detail", "agent"), time.monotonic() + 10)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(failed_call.call_count, 1)
        self.assertTrue(self.experiment.backend_failed.is_set())
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(first["reason"], "model_transport_failed")
        self.assertEqual(second, {"status": "blocked", "reason": "model_backend_unavailable"})
        self.assertNotIn("private transport detail", str(first))


    def parent_artifacts(self):
        parent = self.root / "parent"
        (parent / "queue").mkdir(parents=True)
        (parent / "candidate/src").mkdir(parents=True)
        (parent / "candidate/tests").mkdir()
        state = {"status": "failed", "tasks": {"verify": {"status": "failed"}}}
        for role in ("implement", "test"):
            for feature in ("list", "detail"):
                relative = f"feedback_{feature}.rs" if role == "implement" else f"feedback_{feature}_contract.rs"
                worker = parent / f"{role}-{feature}"
                worker.mkdir()
                text = workflow.STUBS[feature] if role == "implement" else contract(feature)
                (worker / relative).write_text(text)
                destination = parent / "candidate" / ("src" if role == "implement" else "tests") / relative
                destination.write_text(text)
                state["tasks"][f"{role}-{feature}"] = {"status": "completed"}
        (parent / "queue/state.json").write_text(json.dumps(state))
        (parent / "criteria.json").write_text(json.dumps({"case_sha256": workflow.digest(self.base / "tests/cases.json")}))
        (parent / "clippy.log").write_text("error: implementation lint at src/feedback_list.rs:12:1")
        return parent, state

    def test_recovery_refuses_failed_transport_or_incomplete_parent(self):
        parent, state = self.parent_artifacts()
        state["tasks"]["implement-list"]["status"] = "failed"
        (parent / "queue/state.json").write_text(json.dumps(state))
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaises(ValueError):
                self.experiment.repair_once(parent)
            state["tasks"]["implement-list"]["status"] = "completed"
            state["tasks"]["verify"]["status"] = "blocked_dependency"
            (parent / "queue/state.json").write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()

    def test_recovery_refuses_parent_test_tampering(self):
        parent, _ = self.parent_artifacts()
        changed = parent / "candidate/tests/feedback_list_contract.rs"
        changed.write_text(changed.read_text() + "\n// modified after worker import\n")
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaises(ValueError):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()

    def test_valid_recovery_dispatches_only_repair_check_review_and_freezes_tests(self):
        parent, _ = self.parent_artifacts()
        parent_before = workflow.files(parent)
        captured = []

        class LocalQueue:
            def __init__(self, jobs, execute, output, **options):
                self.jobs, self.execute = jobs, execute
                captured.extend(jobs)

            def run(self):
                completed = set()
                for job in self.jobs:
                    if not set(job.deps) <= completed:
                        raise AssertionError("recovery dependency order changed")
                    result = self.execute(job, time.monotonic() + 10)
                    if result["status"] != "completed":
                        raise AssertionError("mock recovery operation failed")
                    completed.add(job.id)
                return {"status": "completed"}

        with patch.object(workflow, "TaskQueue", LocalQueue), \
                patch.object(self.experiment, "agent", return_value={"status": "completed"}) as agent, \
                patch.object(self.experiment, "verify", return_value={"status": "completed"}) as verify, \
                patch.object(workflow, "CliAgent") as transport:
            result = self.experiment.repair_once(parent)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([job.id for job in captured], ["repair-list", "verify", "review-list", "review-detail"])
        self.assertEqual([call.args[0].id for call in agent.call_args_list], ["repair-list", "review-list", "review-detail"])
        verify.assert_called_once()
        transport.assert_not_called()
        self.assertEqual(captured[1].deps, ("repair-list",))
        self.assertTrue(all(job.deps == ("verify",) for job in captured[2:]))
        self.assertEqual(workflow.files(parent), parent_before)
        manifest = json.loads((self.experiment.directory / "recovery.json").read_text())
        self.assertEqual(manifest["features"], ["list"])
        self.assertEqual(set(manifest["frozen_tests"]), {f"tests/feedback_{feature}_contract.rs" for feature in ("list", "detail")})
        for feature in ("list", "detail"):
            relative = f"tests/feedback_{feature}_contract.rs"
            self.assertEqual((self.experiment.candidate / relative).read_bytes(),
                             (parent / "candidate" / relative).read_bytes())
            self.assertEqual(manifest["frozen_tests"][relative], workflow.digest(self.experiment.candidate / relative))


    def verified_parent_artifacts(self):
        parent, _ = self.parent_artifacts()
        # A preceding recovery has no initial implementation/test task records;
        # the actual verification manifest supplies its frozen artifact hashes.
        state = {"status": "failed", "tasks": {
            "repair-list": {"status": "completed"}, "verify": {"status": "failed"}}}
        (parent / "queue/state.json").write_text(json.dumps(state))
        (parent / "clippy.log").unlink()
        (parent / "unit.log").write_text("test result: ok. 12 passed; 0 failed")
        hashes = workflow.files(parent / "candidate")
        verification = {"status": "failed", "generated_hashes": hashes, "http": {"case_sha256": workflow.digest(self.base / "tests/cases.json"), "results": [
            {"case": "list-invalid-page", "passed": False, "reason": "wrong 400 message"},
            {"case": "detail-not-found", "passed": False, "reason": "errors field should be absent"},
            {"case": "list-success", "passed": True},
        ]}}
        (parent / "verification.json").write_text(json.dumps(verification))
        # Recovery must not depend on initial worker source directories.
        import shutil
        for name in ("implement-list", "implement-detail", "test-list", "test-detail"):
            shutil.rmtree(parent / name)
        return parent, verification

    def test_verified_parent_recovery_rejects_frozen_test_hash_tampering(self):
        parent, verification = self.verified_parent_artifacts()
        changed = parent / "candidate/tests/feedback_detail_contract.rs"
        frozen = verification["generated_hashes"]["tests/feedback_detail_contract.rs"]
        changed.write_text(changed.read_text() + "\n// changed after actual verification\n")
        self.assertNotEqual(workflow.digest(changed), frozen)
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaises(ValueError):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()

    def test_verified_parent_http_failures_select_repairs_and_keep_frozen_tests(self):
        parent, verification = self.verified_parent_artifacts()
        parent_before = workflow.files(parent)
        captured = []

        class LocalQueue:
            def __init__(self, jobs, execute, output, **options):
                self.jobs, self.execute = jobs, execute
                captured.extend(jobs)

            def run(self):
                completed = set()
                for job in self.jobs:
                    if not set(job.deps) <= completed:
                        raise AssertionError("unmet recovery prerequisite")
                    if self.execute(job, time.monotonic() + 10)["status"] != "completed":
                        raise AssertionError("mock callback failed")
                    completed.add(job.id)
                return {"status": "completed"}

        with patch.object(workflow, "TaskQueue", LocalQueue), \
                patch.object(self.experiment, "agent", return_value={"status": "completed"}) as agent, \
                patch.object(self.experiment, "verify", return_value={"status": "completed"}) as verify, \
                patch.object(workflow, "CliAgent") as transport:
            result = self.experiment.repair_once(parent)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([job.id for job in captured], ["repair-detail", "repair-list", "verify", "review-list", "review-detail"])
        self.assertEqual(captured[2].deps, ("repair-detail", "repair-list"))
        self.assertTrue(all(job.deps == ("verify",) for job in captured[3:]))
        self.assertEqual([call.args[0].id for call in agent.call_args_list],
                         ["repair-detail", "repair-list", "review-list", "review-detail"])
        verify.assert_called_once()
        transport.assert_not_called()
        self.assertEqual(workflow.files(parent), parent_before)
        manifest = json.loads((self.experiment.directory / "recovery.json").read_text())
        self.assertEqual(manifest["features"], ["detail", "list"])
        for feature in ("list", "detail"):
            relative = f"tests/feedback_{feature}_contract.rs"
            self.assertEqual(workflow.digest(self.experiment.candidate / relative),
                             verification["generated_hashes"][relative])
            self.assertEqual(manifest["frozen_tests"][relative], verification["generated_hashes"][relative])
        self.assertIn("Actual frozen HTTP failures", self.experiment.repair_notes)
        self.assertIn("CommonErrorCode", self.experiment.repair_notes)


    def compile_failed_recovery_parent(self):
        parent, verification = self.verified_parent_artifacts()
        (parent / "verification.json").unlink()
        hashes = verification["generated_hashes"]
        (parent / "artifacts.json").write_text(json.dumps(hashes))
        (parent / "unit.log").write_text("error[E0308]: mismatched types at src/feedback_list.rs:5:1")
        return parent, hashes

    def test_compile_failed_recovery_without_initial_jobs_reuses_artifact_manifest(self):
        parent, hashes = self.compile_failed_recovery_parent()
        self.assertFalse((parent / "verification.json").exists())
        self.assertEqual(set(json.loads((parent / "queue/state.json").read_text())["tasks"]),
                         {"repair-list", "verify"})
        self.assertEqual(len(hashes), 4)
        parent_before = workflow.files(parent)
        with patch.object(workflow, "TaskQueue") as queue, \
                patch.object(self.experiment, "agent", return_value={"status": "completed"}) as agent, \
                patch.object(self.experiment, "verify", return_value={"status": "completed"}) as verify, \
                patch.object(workflow, "CliAgent") as transport:
            queue.return_value.run.return_value = {"status": "completed"}
            result = self.experiment.repair_once(parent)
            jobs, execute, _ = queue.call_args.args
            self.assertEqual([job.id for job in jobs],
                             ["repair-list", "verify", "review-list", "review-detail"])
            self.assertEqual(jobs[1].deps, ("repair-list",))
            self.assertTrue(all(job.deps == ("verify",) for job in jobs[2:]))
            for job in jobs:
                self.assertEqual(execute(job, time.monotonic() + 10)["status"], "completed")
        self.assertEqual(result["status"], "completed")
        self.assertEqual([call.args[0].id for call in agent.call_args_list],
                         ["repair-list", "review-list", "review-detail"])
        verify.assert_called_once()
        transport.assert_not_called()
        self.assertEqual(workflow.files(parent), parent_before)
        self.assertEqual(json.loads((self.experiment.directory / "artifacts.json").read_text()), hashes)
        manifest = json.loads((self.experiment.directory / "recovery.json").read_text())
        for feature in ("list", "detail"):
            relative = f"tests/feedback_{feature}_contract.rs"
            self.assertEqual(workflow.digest(self.experiment.candidate / relative), hashes[relative])
            self.assertEqual(manifest["frozen_tests"][relative], hashes[relative])

    def test_compile_failed_recovery_rejects_tampered_artifact_frozen_tests(self):
        parent, hashes = self.compile_failed_recovery_parent()
        changed = parent / "candidate/tests/feedback_list_contract.rs"
        changed.write_text(changed.read_text() + "\n// altered after failed recovery compile\n")
        self.assertNotEqual(workflow.digest(changed), hashes["tests/feedback_list_contract.rs"])
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaises(ValueError):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()


    def test_verified_recovery_rejects_http_criteria_drift(self):
        parent, verification = self.verified_parent_artifacts()
        verification["http"]["case_sha256"] = "0" * 64
        (parent / "verification.json").write_text(json.dumps(verification))
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaisesRegex(ValueError, "criteria changed"):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()

    def test_verified_recovery_requires_http_criteria_hash(self):
        parent, verification = self.verified_parent_artifacts()
        del verification["http"]["case_sha256"]
        (parent / "verification.json").write_text(json.dumps(verification))
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaisesRegex(ValueError, "criteria changed"):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()

    def test_compile_failed_recovery_rejects_recorded_criteria_drift(self):
        parent, _ = self.compile_failed_recovery_parent()
        (parent / "criteria.json").write_text(json.dumps({"case_sha256": "0" * 64}))
        self.assertFalse((parent / "verification.json").exists())
        with patch.object(workflow, "TaskQueue") as queue, patch.object(workflow, "CliAgent") as transport:
            with self.assertRaisesRegex(ValueError, "criteria changed"):
                self.experiment.repair_once(parent)
        queue.assert_not_called()
        transport.assert_not_called()


    def test_pending_test_revision_blocks_review_before_cli_without_test_mutation(self):
        self.assertEqual(self.experiment.pending_test_revisions, {})
        self.assertEqual(self.experiment.previous_review_revisions, {})
        for feature in ("list", "detail"):
            (self.experiment.candidate / f"tests/feedback_{feature}_contract.rs").write_text(contract(feature))
        frozen = workflow.files(self.experiment.candidate / "tests")
        self.experiment.pending_test_revisions = {"list": ["TEST_REVISION missing boundary assertion"]}
        (self.experiment.directory / "pending-test-revisions.json").write_text(json.dumps(self.experiment.pending_test_revisions))
        with patch.object(workflow, "CliAgent") as transport:
            outcomes = [self.experiment.agent(Job(f"review-{feature}", "agent"), time.monotonic() + 10)
                        for feature in ("list", "detail")]
        transport.assert_not_called()
        for outcome in outcomes:
            self.assertEqual(outcome["status"], "needs_test_revision")
            self.assertTrue(Path(outcome["report"]).is_file())
        self.assertEqual(workflow.files(self.experiment.candidate / "tests"), frozen)
        self.assertFalse((self.experiment.directory / "review-list").exists())
        self.assertFalse((self.experiment.directory / "review-detail").exists())

    def test_recovery_persists_test_findings_and_source_fix_cannot_close_review(self):
        parent, verification = self.verified_parent_artifacts()
        for row in verification["http"]["results"]:
            row["passed"] = True
        verification["status"] = "passed"
        (parent / "verification.json").write_text(json.dumps(verification))
        test_findings = ["TEST_REVISION add a missing boundary assertion",
                         "tests/feedback_list_contract.rs: precision assertion is absent"]
        # Source repair now requires its own finding; TEST_REVISION requests go
        # to an independent supplement author and must survive a source fix.
        findings = test_findings + ["CODE_REVISION correct the list response"]
        verdict = {"status": "revise", "findings": findings}
        state = {"status": "failed", "tasks": {
            "verify": {"status": "completed"},
            "review-list": {"status": "failed", "result": {"verdict": verdict}},
        }}
        (parent / "queue/state.json").write_text(json.dumps(state))
        inherited = {"detail": ["TEST_REVISION unresolved detail test"]}
        (parent / "pending-test-revisions.json").write_text(json.dumps(inherited))
        parent_before = workflow.files(parent)
        frozen = {relative: digest for relative, digest in verification["generated_hashes"].items()
                  if relative.startswith("tests/")}
        actual_agent = self.experiment.agent
        outcomes = {}

        def local_agent(job, deadline):
            if job.id.startswith("test-regression-"):
                return {"status": "failed", "reason": "test revision remains unresolved"}
            if job.id == "repair-list":
                source = self.experiment.candidate / "src/feedback_list.rs"
                source.write_text(source.read_text().replace("501", "200"))
                return {"status": "completed"}
            return actual_agent(job, deadline)

        class LocalQueue:
            def __init__(self, jobs, execute, output, **options):
                self.jobs, self.execute = jobs, execute

            def run(self):
                for job in self.jobs:
                    outcomes[job.id] = self.execute(job, time.monotonic() + 10)
                return {"status": "completed" if all(result["status"] == "completed" for result in outcomes.values()) else "failed"}

        with patch.object(workflow, "TaskQueue", LocalQueue), \
                patch.object(self.experiment, "agent", side_effect=local_agent), \
                patch.object(self.experiment, "verify", return_value={"status": "completed"}) as verify, \
                patch.object(workflow, "CliAgent") as transport:
            result = self.experiment.repair_once(parent)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(outcomes["repair-list"]["status"], "completed")
        self.assertEqual(outcomes["verify"]["status"], "completed")
        for feature in ("list", "detail"):
            self.assertEqual(outcomes[f"review-{feature}"]["status"], "needs_test_revision")
        verify.assert_called_once()
        transport.assert_not_called()
        expected = {"detail": inherited["detail"], "list": sorted(test_findings)}
        self.assertEqual(self.experiment.pending_test_revisions, expected)
        self.assertEqual(json.loads((self.experiment.directory / "pending-test-revisions.json").read_text()), expected)
        self.assertEqual(self.experiment.previous_review_revisions, {"list": verdict})
        self.assertEqual(workflow.files(parent), parent_before)
        self.assertNotEqual(workflow.digest(self.experiment.candidate / "src/feedback_list.rs"),
                            verification["generated_hashes"]["src/feedback_list.rs"])
        for relative, expected_hash in frozen.items():
            self.assertEqual(workflow.digest(self.experiment.candidate / relative), expected_hash)


if __name__ == "__main__":
    unittest.main()
