#!/usr/bin/env python3
"""Exercise stock-price completion guards without models, servers or compilation."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import stock_price_workflow as workflow
from agent_workflow import CliAgent, permission_config, validate_result


def answer(status):
    return {"status": status, "summary": "artifact ready", "findings": [], "questions": []}


class IndependentTestsExecutionTests(unittest.TestCase):
    def execute(self, summary, count=8, exit_code=0):
        controller = workflow.StockWorkflow.__new__(workflow.StockWorkflow)
        controller.compile_tests = lambda candidate, output: (["fake-test-binary"], [f"case-{n}" for n in range(count)])
        controller.command = lambda *args, **kwargs: (exit_code, summary)
        return controller.execute_tests(Path("candidate"), Path("evidence"))

    def test_all_listed_tests_must_really_run(self):
        complete = "test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
        self.assertTrue(self.execute(complete)["passed"])
        for incomplete in (
            "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
            "test result: ok. 7 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out",
            "test result: ok. 7 passed; 0 failed; 0 ignored; 0 measured; 1 filtered out",
            "test result: ok. 7 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out",
            "compilation succeeded, tests passed",
        ):
            with self.subTest(summary=incomplete), self.assertRaises(ValueError):
                self.execute(incomplete)

    def test_failure_or_nonzero_process_exit_never_counts_as_success(self):
        failed = "test result: FAILED. 7 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out"
        self.assertFalse(self.execute(failed, exit_code=101)["passed"])
        ok = "test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
        self.assertFalse(self.execute(ok, exit_code=1)["passed"])

    def test_mutants_preserve_original_logic_but_change_one_public_result(self):
        source = 'pub fn latest(id: &str, data: &serde_json::Value) -> (u16, serde_json::Value) { (404, data.clone()) }'
        expected = {
            "wrong_currency": 'body["currency"] = serde_json::json!("KRW")',
            "wrong_date": 'body["baseDate"] = serde_json::json!("1900-01-01")',
            "zero_price": 'body["closePrice"] = serde_json::json!(0)',
            "invent_missing": 'if status == 404 { return (200, serde_json::json!({})); }',
        }
        for name, action in expected.items():
            with self.subTest(name=name):
                mutant = workflow.mutation(source, name)
                self.assertEqual(mutant.count("pub fn latest("), 1)
                self.assertIn("fn unmutated_latest(", mutant)
                self.assertIn("unmutated_latest(id, data)", mutant)
                self.assertIn(action, mutant)
                for other_name, other_action in expected.items():
                    if other_name != name:
                        self.assertNotIn(other_action, mutant)
        for invalid in ("", source + "\n" + source):
            with self.assertRaises(ValueError):
                workflow.mutation(invalid, "zero_price")


class HttpEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.source = self.candidate / workflow.MODULE
        self.source.parent.mkdir(parents=True)
        self.source.write_text("verified source\n")
        self.output = self.root / "evidence"
        self.output.mkdir()
        self.report = self.output / "result.json"
        self.target = self.root / "target"
        self.binary = self.target / "debug/daynomy-stock-price"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b"verified binary")
        self.started = time.time() - 2
        self.patch_target = patch.object(workflow, "TARGET", self.target)
        self.patch_target.start()
        self.addCleanup(self.patch_target.stop)
        names = [case[0] for case in workflow.cases()] + ["latest-live-db-insert"]
        self.assertEqual(len(names), 22)
        self.assertEqual(len(names), len(set(names)))
        self.result = {
            "status": "passed", "report": str(self.report), "started_at": self.started + 1,
            "source_hashes": {"stock_price.rs": workflow.digest(self.source)},
            "binary_sha256": workflow.digest(self.binary),
            "results": [{"case": name, "passed": True, "database_unchanged": True} for name in names],
            "commands": [{"name": name, "exit_code": 0} for name in (
                "database-create", "spring-startup", "rust-startup", "spring-shutdown", "rust-shutdown")],
        }

    def accepted(self, result=None):
        result = self.result if result is None else result
        self.report.write_text(json.dumps(result))
        return workflow.valid_http(result, self.output, self.candidate, self.started)

    def test_only_complete_fresh_report_for_exact_source_and_binary_is_accepted(self):
        self.assertTrue(self.accepted())
        self.source.write_text("different source\n")
        self.assertFalse(workflow.valid_http(self.result, self.output, self.candidate, self.started))
        self.source.write_text("verified source\n")
        self.binary.write_bytes(b"different binary")
        self.assertFalse(workflow.valid_http(self.result, self.output, self.candidate, self.started))

    def test_missing_empty_duplicate_or_substituted_cases_are_rejected(self):
        for kind in ("missing", "empty", "duplicate", "substituted"):
            broken = copy.deepcopy(self.result)
            if kind == "missing":
                broken["results"].pop()
            elif kind == "empty":
                broken["results"] = []
            elif kind == "duplicate":
                broken["results"][-1] = copy.deepcopy(broken["results"][0])
            else:
                broken["results"][-1]["case"] = "unrelated-test"
            with self.subTest(kind=kind):
                self.assertFalse(self.accepted(broken))

    def test_every_case_requires_true_result_and_no_database_changes(self):
        for field in ("passed", "database_unchanged"):
            for value in (False, None, 1, "true"):
                broken = copy.deepcopy(self.result)
                broken["results"][0][field] = value
                with self.subTest(field=field, value=value):
                    self.assertFalse(self.accepted(broken))

    def test_stale_report_or_mismatched_returned_evidence_is_rejected(self):
        broken = copy.deepcopy(self.result)
        broken["started_at"] = self.started - 1
        self.assertFalse(self.accepted(broken))
        self.assertTrue(self.accepted())
        os.utime(self.report, (self.started - 1, self.started - 1))
        self.assertFalse(workflow.valid_http(self.result, self.output, self.candidate, self.started))
        self.assertTrue(self.accepted())
        self.report.write_text(json.dumps({**self.result, "status": "failed"}))
        self.assertFalse(workflow.valid_http(self.result, self.output, self.candidate, self.started))

    def test_actual_startup_and_cleanup_commands_are_required(self):
        for change in ("missing-startup", "failed-cleanup", "blocked-status", "different-report"):
            broken = copy.deepcopy(self.result)
            if change == "missing-startup":
                broken["commands"] = [c for c in broken["commands"] if c["name"] != "spring-startup"]
            elif change == "failed-cleanup":
                broken["commands"][-1]["exit_code"] = 1
            elif change == "blocked-status":
                broken["status"] = "blocked"
            else:
                broken["report"] = str(self.root / "another-report.json")
            with self.subTest(change=change):
                self.assertFalse(self.accepted(broken))
        self.report.unlink()
        self.assertFalse(workflow.valid_http(self.result, self.output, self.candidate, self.started))


class AgentRolesTests(unittest.TestCase):
    def test_independent_test_source_requires_unsafe_prohibition_and_exact_module_path(self):
        valid = '#![forbid(unsafe_code)]\n#[path = "../src/stock_price.rs"] mod stock_price;\n'
        workflow.validate_test_source(valid)
        for invalid in (valid.replace('#![forbid(unsafe_code)]', ''),
                        valid.replace('../src/stock_price.rs', '../../other.rs'),
                        valid + '#[path = "../../other.rs"] mod other;'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                workflow.validate_test_source(invalid)

    def test_ignored_tests_and_direct_process_file_network_access_are_rejected(self):
        valid = '#![forbid(unsafe_code)]\n#[path = "../src/stock_price.rs"] mod stock_price;\n'
        for extra in ('#[ignore] #[test] fn hidden() {}', 'use std::process::Command;',
                      'use std :: fs;', 'use std::net::TcpStream;',
                      'include_str!("/private/data");', 'env!("TOKEN");',
                      'unsafe { arbitrary(); }'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                workflow.validate_test_source(valid + extra)

    def test_test_author_cannot_report_implementation_or_review_as_its_result(self):
        self.assertEqual(validate_result(answer("tests_written"), "test_author")["status"], "tests_written")
        for status in ("implemented", "approve", "revise"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_result(answer(status), "test_author")
        with self.assertRaises(ValueError):
            validate_result(answer("tests_written"), "implementer")

    def test_author_can_only_write_its_worker_and_reviewer_cannot_write(self):
        worker = Path("/private/tmp/daynomy-test-author-unit")
        author = permission_config("test_author", worker)
        reviewer = permission_config("reviewer", worker)
        self.assertIn(json.dumps(str(worker.resolve())) + '="write"', author)
        self.assertIn('":root"="read"', author)
        self.assertNotIn('="write"', reviewer)
        self.assertIn("network={enabled=false}", author)
        self.assertIn("network={enabled=false}", reviewer)

    def test_config_has_three_distinct_roles_and_single_attempt_clients(self):
        config = json.loads(workflow.CONFIG.read_text())
        self.assertEqual(config["backend"], "codex_cli")
        self.assertGreaterEqual(config["max_rounds"], 1)
        self.assertLessEqual(config["max_rounds"], 3)
        names = []
        for role in ("test_author", "implementer", "reviewer"):
            names.append(config[role]["name"])
            client = CliAgent(model=config[role]["model"], max_attempts=1)
            self.assertEqual(client.model, config[role]["model"])
            self.assertEqual(client.max_attempts, 1)
        self.assertEqual(len(set(names)), 3)


class IsolatedBuildTargetTests(unittest.TestCase):
    def test_actual_server_and_each_mutant_compile_into_different_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = workflow.StockWorkflow.__new__(workflow.StockWorkflow)
            controller.candidate = root / "candidate"
            controller.env = {"CARGO_TARGET_DIR": str(root / "actual-target")}
            targets = []
            def command(name, args, output, **kwargs):
                if name == "compile-tests":
                    target = Path(kwargs["env_override"]["CARGO_TARGET_DIR"])
                    targets.append(target)
                    return 0, json.dumps({"reason": "compiler-artifact", "target": {"name": "stock_price_contract"},
                                         "executable": str(target / "debug/deps/contract-test")})
                if name == "list-tests":
                    return 0, "\n".join(f"case-{n}: test" for n in range(8))
                return 0, ""
            controller.command = command
            for candidate in (controller.candidate, root / "mutant-a", root / "mutant-b"):
                controller.compile_tests(candidate, root / "evidence")
            self.assertEqual(targets, [root / "actual-target", root / "mutant-a/target", root / "mutant-b/target"])
            self.assertEqual(len(set(targets)), 3)

    def test_executable_from_another_targets_cache_is_rejected(self):
        controller = workflow.StockWorkflow.__new__(workflow.StockWorkflow)
        controller.candidate = Path("/private/tmp/controller-candidate")
        controller.env = {"CARGO_TARGET_DIR": "/private/tmp/right-target"}
        controller.command = lambda *args, **kwargs: (0, json.dumps({
            "reason": "compiler-artifact", "target": {"name": "stock_price_contract"},
            "executable": "/private/tmp/wrong-mutant-target/debug/deps/test"}))
        with self.assertRaisesRegex(ValueError, "isolated target"):
            controller.compile_tests(controller.candidate, Path("evidence"))


class WorkflowFailureGuardsTests(unittest.TestCase):
    def controller(self, directory, test_results):
        controller = workflow.StockWorkflow.__new__(workflow.StockWorkflow)
        controller.directory = directory
        controller.candidate = directory / "candidate"
        (controller.candidate / "src").mkdir(parents=True)
        (controller.candidate / workflow.MODULE).write_text(
            "pub fn latest(id: &str, data: &serde_json::Value) -> (u16, serde_json::Value) { (501, data.clone()) }")
        controller.state = {"status": "preparing"}
        controller.config = {"max_rounds": 1}
        controller.calls = []
        controller.save = lambda **values: controller.state.update(values)
        controller.integrity = lambda: None
        controller.timed = lambda stage, operation: operation()
        controller.prompt = lambda instruction, evidence=None: instruction
        controller.command = lambda *args, **kwargs: (0, "")
        outcomes = iter(test_results)
        def execute_tests(*args):
            passed = next(outcomes)
            return {"passed": passed, "summary": {"failed": 0 if passed else 1}}

        controller.execute_tests = execute_tests

        def invoke(role, prompt, output, filename=None):
            controller.calls.append(role)
            if role == "test_author":
                target = controller.candidate / workflow.TEST
                target.parent.mkdir(parents=True)
                target.write_text('#![forbid(unsafe_code)]\n#[path = "../src/stock_price.rs"] mod stock_price;\n')
                return answer("tests_written")
            return answer("implemented")

        controller.invoke = invoke
        return controller

    def test_green_tests_against_unimplemented_stub_stop_before_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(Path(directory), [True])
            with contextlib.redirect_stdout(io.StringIO()):
                controller.run()
            self.assertEqual(controller.state["status"], "failed")
            self.assertIn("did not reject the unimplemented endpoint", controller.state["test_author_feedback"]["test_artifact_problem"])
            self.assertEqual(controller.calls, ["test_author"])

    def test_undetected_mutation_blocks_http_and_approval_even_if_tests_are_green(self):
        with tempfile.TemporaryDirectory() as directory:
            # Red control fails, implementation passes, one seeded fault survives.
            controller = self.controller(Path(directory), [False, True, True, False, False, False])
            with patch.object(workflow, "run_gate") as http, contextlib.redirect_stdout(io.StringIO()):
                controller.run()
            self.assertEqual(controller.state["status"], "blocked")
            self.assertIn("missed a seeded defect", controller.state["reason"])
            self.assertEqual(controller.calls, ["test_author", "implementer"])
            self.assertEqual(len(controller.state["mutations"]), 4)
            http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
