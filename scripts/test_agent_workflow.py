#!/usr/bin/env python3
"""Controller unit tests with explicitly synthetic agents and gate evidence.

These tests exercise failure handling and state transitions only. They do not
invoke an AI, compile Rust, or verify HTTP/PostgreSQL behavior. The real-model,
real-DB fault demonstration is a separate workflow run.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import agent_workflow as workflow
from workflow_gate import (
    ACCEPTANCE_CASES, LIFECYCLE_CASES, _acceptance_valid, _lifecycle_valid,
)


ROOT = Path(__file__).resolve().parents[1]


def result(status, *, findings=None, questions=None):
    return {"status": status, "summary": "Synthetic controller unit-test result",
            "findings": findings or [], "questions": questions or []}


def acceptance_evidence():
    return {"started_at": workflow.now(), "finished_at": workflow.now(),
            "complete": True, "exit_code": 0,
            "results": [{"case": name, "passed": True, "failures": []}
                        for name in sorted(ACCEPTANCE_CASES)]}


def lifecycle_evidence():
    return {"finished_at": workflow.now(), "exit_code": 0,
            "passed": sorted(LIFECYCLE_CASES)}


def synthetic_gate(output_dir, *, status="passed"):
    """Create fake but fresh and complete evidence; never a real test pass."""
    output_dir.mkdir(parents=True, exist_ok=True)
    started = workflow.now()
    acceptance_path, lifecycle_path = output_dir / "acceptance.json", output_dir / "lifecycle.json"
    workflow.dump(acceptance_path, acceptance_evidence())
    workflow.dump(lifecycle_path, lifecycle_evidence())
    checks = []
    for name in sorted(workflow.REQUIRED_CHECKS):
        log_path = output_dir / (name + ".log")
        log_path.write_text("SYNTHETIC unit-test evidence; no process executed.\n")
        checks.append({"name": name, "exit_code": 0, "log": str(log_path)})
    if status == "failed":
        checks_by_name = {item["name"]: item for item in checks}
        checks_by_name["verify"]["exit_code"] = 1
        evidence = acceptance_evidence()
        evidence["complete"] = False
        for item in evidence["results"]:
            if item["case"] == "normal":
                item.update(passed=False, failures=[{"check": "storage", "reason": "Synthetic missing row"}])
        evidence["exit_code"] = 1
        workflow.dump(acceptance_path, evidence)
    return {"status": status, "started_at": started, "finished_at": workflow.now(),
            "checks": checks, "acceptance": {"count": len(ACCEPTANCE_CASES),
                "passed": status == "passed", "report": str(acceptance_path)},
            "lifecycle": {"count": len(LIFECYCLE_CASES), "passed": True,
                "report": str(lifecycle_path)}}


class SyntheticAgent:
    """Fresh fake identities and scripted verdicts; never contacts a model."""

    def __init__(self, reviews=None, implementations=None, *, repeat_identity=False,
                 mutate=None):
        self.reviews = list(reviews or [result("approve")])
        self.implementations = list(implementations or [result("implemented")])
        self.repeat_identity = repeat_identity
        self.mutate = mutate
        self.calls = []
        self.prompts = []

    def __call__(self, role, workspace, prompt, output_dir):
        self.calls.append(role)
        self.prompts.append(prompt)
        output_dir.mkdir(parents=True, exist_ok=True)
        if role == "implementer":
            if {item.name for item in workspace.iterdir()} != workflow.SOURCES:
                raise AssertionError("Implementer workspace must contain only three Rust sources")
            if self.mutate:
                self.mutate(workspace, len([call for call in self.calls if call == role]))
            verdict = self.implementations.pop(0) if len(self.implementations) > 1 else self.implementations[0]
        else:
            verdict = self.reviews.pop(0) if len(self.reviews) > 1 else self.reviews[0]
        return deepcopy(verdict), {"session_id": "synthetic-repeat" if self.repeat_identity
                                  else "synthetic-session-" + str(len(self.calls)),
                                  "role": role, "exit_code": 0}


class SyntheticGate:
    """Scripted controller dependency; all emitted evidence is synthetic."""

    def __init__(self, statuses=None, *, missing_report=False):
        self.statuses = list(statuses or ["passed"])
        self.missing_report = missing_report
        self.calls = 0

    def __call__(self, candidate, trusted_root, output_dir, db_name):
        self.calls += 1
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        evidence = synthetic_gate(output_dir, status=status)
        if self.missing_report:
            Path(evidence["acceptance"]["report"]).unlink()
        return evidence


class ImportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daynomy-import-unit-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.worker = self.directory / "worker"
        self.worker.mkdir()
        self.candidate = self.directory / "candidate"
        (self.candidate / "app/src").mkdir(parents=True)
        self.baseline = {name: (ROOT / "app/src" / name).read_text() for name in workflow.SOURCES}
        for name, source in self.baseline.items():
            (self.worker / name).write_text(source)
            (self.candidate / "app/src" / name).write_text(source)

    def assert_rejected(self):
        before = workflow.source_hash(self.candidate / "app/src")
        with self.assertRaises(ValueError):
            workflow.import_sources(self.worker, self.candidate, self.baseline)
        self.assertEqual(workflow.source_hash(self.candidate / "app/src"), before)

    def test_accepts_source_change_and_preserves_original_embedded_tests(self):
        path = self.worker / "main.rs"
        path.write_text(path.read_text() + "\n// Synthetic non-functional edit.\n")
        workflow.import_sources(self.worker, self.candidate, self.baseline)
        self.assertEqual((self.candidate / "app/src/main.rs").read_text(), path.read_text())

    def test_rejects_symlink(self):
        path = self.worker / "main.rs"
        path.unlink()
        path.symlink_to(ROOT / "app/src/main.rs")
        self.assert_rejected()

    def test_rejects_hard_link(self):
        path = self.worker / "main.rs"
        alias = self.directory / "alias.rs"
        os.link(path, alias)
        self.assert_rejected()

    def test_rejects_missing_source(self):
        (self.worker / "main.rs").unlink()
        self.assert_rejected()

    def test_rejects_extra_path(self):
        (self.worker / "build.rs").write_text("fn main() {}\n")
        self.assert_rejected()

    def test_rejects_directory_instead_of_source(self):
        path = self.worker / "main.rs"
        path.unlink()
        path.mkdir()
        self.assert_rejected()

    def test_rejects_modified_embedded_tests(self):
        path = self.worker / "feedback.rs"
        before, marker, tail = path.read_text().partition("#[cfg(test)]")
        self.assertTrue(marker)
        path.write_text(before + marker + tail + "\n// Changed protected test tail.\n")
        self.assert_rejected()

    def test_rejects_removed_embedded_tests(self):
        path = self.worker / "csrf.rs"
        path.write_text(path.read_text().partition("#[cfg(test)]")[0])
        self.assert_rejected()

    def test_rejects_removed_unsafe_prohibition(self):
        path = self.worker / "main.rs"
        path.write_text(path.read_text().replace("#![forbid(unsafe_code)]\n", "", 1))
        self.assert_rejected()


class ResultValidationTests(unittest.TestCase):
    def test_valid_role_verdicts(self):
        for role, verdict in (("implementer", result("implemented")),
                              ("reviewer", result("approve")),
                              ("reviewer", result("revise", findings=["Storage is missing."])),
                              ("reviewer", result("needs_decision", questions=["Which policy applies?"]))):
            with self.subTest(role=role, status=verdict["status"]):
                self.assertEqual(workflow.validate_result(verdict, role), verdict)

    def test_invalid_json_shapes_and_wrong_role_status(self):
        invalid = [None, [], "approve", {}, {**result("approve"), "extra": True},
                   {**result("approve"), "summary": 1},
                   {**result("approve"), "findings": "none"},
                   {**result("approve"), "questions": [None]}, result("implemented")]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    workflow.validate_result(value, "reviewer")

    def test_approval_with_findings_or_questions_is_rejected(self):
        for verdict in (result("approve", findings=["Missing insert"]),
                        result("approve", questions=["Policy?"])):
            with self.subTest(verdict=verdict):
                with self.assertRaises(ValueError):
                    workflow.validate_result(verdict, "reviewer")

    def test_decision_without_concrete_question_is_rejected(self):
        for questions in ([], [""], ["   "]):
            with self.subTest(questions=questions):
                with self.assertRaises(ValueError):
                    workflow.validate_result(result("needs_decision", questions=questions), "reviewer")

    def test_revision_without_findings_is_rejected(self):
        with self.assertRaises(ValueError):
            workflow.validate_result(result("revise"), "reviewer")


class EvidenceValidationTests(unittest.TestCase):
    def test_complete_exact_evidence_is_accepted(self):
        self.assertTrue(_acceptance_valid(acceptance_evidence()))
        self.assertTrue(_lifecycle_valid(lifecycle_evidence()))

    def test_acceptance_rejects_incomplete_or_tampered_case_sets(self):
        base = acceptance_evidence()
        variants = [None, [], {}, {**base, "complete": False},
                    {**base, "exit_code": 1}, {**base, "skipped": True},
                    {**base, "results": base["results"][:-1]}]
        wrong = deepcopy(base)
        wrong["results"][0]["case"] = "not-a-trusted-case"
        variants.append(wrong)
        duplicate = deepcopy(base)
        duplicate["results"][0]["case"] = duplicate["results"][1]["case"]
        variants.append(duplicate)
        for field, value in (("passed", False), ("skipped", True),
                             ("failures", [{"reason": "failure"}])):
            changed = deepcopy(base)
            changed["results"][0][field] = value
            variants.append(changed)
        for index, evidence in enumerate(variants):
            with self.subTest(variant=index):
                self.assertFalse(_acceptance_valid(evidence))

    def test_lifecycle_rejects_missing_wrong_duplicate_or_skipped_results(self):
        base = lifecycle_evidence()
        variants = [None, [], {}, {**base, "exit_code": 1}, {**base, "skipped": True},
                    {**base, "passed": base["passed"][:-1]},
                    {**base, "passed": ["not-a-trusted-case"] + base["passed"][1:]},
                    {**base, "passed": [base["passed"][1]] + base["passed"][1:]}]
        for index, evidence in enumerate(variants):
            with self.subTest(variant=index):
                self.assertFalse(_lifecycle_valid(evidence))

    def test_gate_requires_actual_evidence_not_just_claimed_counts(self):
        with tempfile.TemporaryDirectory(prefix="daynomy-gate-unit-") as directory:
            gate = synthetic_gate(Path(directory))
            gate["source_sha256"] = "synthetic-source-hash"
            self.assertTrue(workflow.gate_passes(gate, "synthetic-source-hash"))
            Path(gate["acceptance"]["report"]).unlink()
            self.assertFalse(workflow.gate_passes(gate, "synthetic-source-hash"))

    def test_gate_rejects_stale_evidence_and_mismatched_source(self):
        with tempfile.TemporaryDirectory(prefix="daynomy-gate-unit-") as directory:
            gate = synthetic_gate(Path(directory))
            gate["source_sha256"] = "synthetic-source-hash"
            self.assertFalse(workflow.gate_passes(gate, "different-source-hash"))
            old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            path = Path(gate["acceptance"]["report"])
            evidence = json.loads(path.read_text())
            evidence.update(started_at=old, finished_at=old)
            workflow.dump(path, evidence)
            old_epoch = datetime.fromisoformat(old).timestamp()
            os.utime(path, (old_epoch, old_epoch))
            self.assertFalse(workflow.gate_passes(gate, "synthetic-source-hash"))

    def test_gate_rejects_failed_or_missing_required_command(self):
        with tempfile.TemporaryDirectory(prefix="daynomy-gate-unit-") as directory:
            gate = synthetic_gate(Path(directory))
            gate["source_sha256"] = "synthetic-source-hash"
            for name in workflow.REQUIRED_CHECKS:
                missing = deepcopy(gate)
                missing["checks"] = [c for c in missing["checks"] if c["name"] != name]
                self.assertFalse(workflow.gate_passes(missing, "synthetic-source-hash"))
                failed = deepcopy(gate)
                next(c for c in failed["checks"] if c["name"] == name)["exit_code"] = 1
                self.assertFalse(workflow.gate_passes(failed, "synthetic-source-hash"))


class CliRetryTests(unittest.TestCase):
    """Mock CLI transport only; no model process, network, sleep, or sandbox."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daynomy-cli-unit-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.workspace = self.directory / "workspace"
        self.workspace.mkdir()
        self.output = self.directory / "output"
        self.sleep = mock.patch("agent_workflow.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def capture_script(self, attempts):
        remaining = list(attempts)
        calls = []

        def capture(command, prompt, events, timeout, env):
            index = len(calls) + 1
            calls.append({"events": Path(events), "command": command})
            if not remaining:
                raise AssertionError("CLI retry exceeded scripted attempt count")
            event_list, code, verdict = remaining.pop(0)
            events.parent.mkdir(parents=True, exist_ok=True)
            events.write_text("".join(json.dumps(event) + "\n" for event in event_list))
            result_path = Path(command[command.index("-o") + 1])
            if verdict is not None:
                workflow.dump(result_path, verdict)
            return code

        return capture, calls

    @staticmethod
    def success():
        return ([{"type": "thread.started", "thread_id": "synthetic-retry-success"},
                 {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}],
                0, result("approve"))

    def invoke(self, attempts):
        capture, calls = self.capture_script(attempts)
        with mock.patch("agent_workflow.capture", side_effect=capture), redirect_stdout(io.StringIO()):
            verdict, identity = workflow.CliAgent(timeout=1)(
                "reviewer", self.workspace, "Synthetic retry test", self.output)
        return verdict, identity, calls

    def test_explicit_model_and_effort_reach_cli_and_evidence(self):
        capture, calls = self.capture_script([self.success()])
        with mock.patch("agent_workflow.capture", side_effect=capture):
            _, identity = workflow.CliAgent(
                timeout=1, model="gpt-6.1-sol", reasoning_effort="medium", max_attempts=1
            )("reviewer", self.workspace, "Synthetic configuration test", self.output)
        command = calls[0]["command"]
        self.assertEqual(command[command.index("--model") + 1], "gpt-6.1-sol")
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertEqual(identity["requested_reasoning_effort"], "medium")
        self.assertEqual(identity["requested_model"], "gpt-6.1-sol")

    def test_invalid_reasoning_effort_is_rejected_before_transport(self):
        with self.assertRaises(ValueError):
            workflow.CliAgent(reasoning_effort="unlimited")

    def test_explicit_cli_executable_is_used_without_model_substitution(self):
        capture, calls = self.capture_script([self.success()])
        executable = "/synthetic/app-bundled/codex"
        with mock.patch("agent_workflow.capture", side_effect=capture):
            _, identity = workflow.CliAgent(
                timeout=1, model="gpt-6.1-sol", executable=executable
            )("reviewer", self.workspace, "Synthetic executable selection", self.output)
        self.assertEqual(calls[0]["command"][0], executable)
        self.assertEqual(identity["executable"], executable)
        self.assertEqual(identity["requested_model"], "gpt-6.1-sol")

    def test_429_error_retries_then_uses_fresh_success_identity(self):
        failure = ([{"type": "error", "message": "429 Too Many Requests"}], 1, None)
        verdict, identity, calls = self.invoke([failure, self.success()])
        self.assertEqual(verdict["status"], "approve")
        self.assertEqual(identity["session_id"], "synthetic-retry-success")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(identity["attempts"]), 2)
        self.assertNotEqual(calls[0]["events"], calls[1]["events"])
        self.sleep.assert_called_once()

    def test_503_failed_turn_retries(self):
        failure = ([{"type": "turn.failed", "error": {"message": "503 Service Unavailable"}}], 1, None)
        verdict, identity, calls = self.invoke([failure, self.success()])
        self.assertEqual(verdict["status"], "approve")
        self.assertEqual(len(calls), 2)
        self.sleep.assert_called_once()

    def test_retry_budget_is_three_failed_attempts(self):
        failure = ([{"type": "error", "message": "429 Too Many Requests"}], 1, None)
        capture, calls = self.capture_script([failure] * 3)
        with mock.patch("agent_workflow.capture", side_effect=capture), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                workflow.CliAgent(timeout=1)("reviewer", self.workspace, "Synthetic test", self.output)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.sleep.call_count, 2)
        self.assertEqual(len({call["events"] for call in calls}), 3)

    def test_unknown_error_does_not_retry(self):
        failure = ([{"type": "error", "message": "Authentication failed"}], 1, None)
        capture, calls = self.capture_script([failure])
        with mock.patch("agent_workflow.capture", side_effect=capture), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                workflow.CliAgent(timeout=1)("reviewer", self.workspace, "Synthetic test", self.output)
        self.assertEqual(len(calls), 1)
        self.sleep.assert_not_called()

    def test_quoted_429_in_nonerror_event_does_not_retry(self):
        failure = ([{"type": "item.completed", "item": {
            "type": "agent_message", "text": "The source fixture contains 429 Too Many Requests."}}],
                   1, None)
        capture, calls = self.capture_script([failure])
        with mock.patch("agent_workflow.capture", side_effect=capture), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                workflow.CliAgent(timeout=1)("reviewer", self.workspace, "Synthetic test", self.output)
        self.assertEqual(len(calls), 1)
        self.sleep.assert_not_called()

    def test_failed_attempt_result_is_not_accepted_as_success(self):
        failure = ([{"type": "error", "message": "429 Too Many Requests"}],
                   1, result("needs_decision", questions=["Stale failed-attempt question?"]))
        verdict, identity, calls = self.invoke([failure, self.success()])
        self.assertEqual(verdict["status"], "approve")
        self.assertEqual(identity["session_id"], "synthetic-retry-success")
        self.assertEqual(len(calls), 2)
        self.assertTrue((self.output / "failed-result-1.json").is_file())


class CostSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.run=self.root/'run';self.run.mkdir()
        agent=self.run/'agent';agent.mkdir()
        workflow.dump(agent/'input.json',{'context_mode':'fresh-ephemeral','prompt_bytes':20})
        workflow.dump(agent/'attempts.json',[{'attempt':1,'session_ids':['a'],'capture_seconds':4,
            'usage_records':[{'input_tokens':100,'cached_input_tokens':80,'output_tokens':10}]},
            {'attempt':2,'session_ids':['b'],'capture_seconds':5,
            'usage_records':[{'input_tokens':200,'cached_input_tokens':150,'output_tokens':20}]}])

    def rollout(self,cwd=None):
        path=self.root/'rollout.jsonl'
        events=[{'type':'event_msg','timestamp':'2026-11-04T00:00:00Z','payload':{'type':'task_started','turn_id':'wanted'}},
          {'type':'turn_context','payload':{'cwd':str(cwd or self.root)}},
          {'type':'token_usage_record','payload':{'turn_id':'wanted','response_id':'r','usage':{'input_tokens':900,'cached_input_tokens':700,'output_tokens':30}}},
          {'type':'token_usage_record','payload':{'turn_id':'wanted','response_id':'r','usage':{'input_tokens':1000,'cached_input_tokens':800,'output_tokens':30}}},
          {'type':'token_usage_record','payload':{'turn_id':'other','response_id':'other','usage':{'input_tokens':99999,'cached_input_tokens':0,'output_tokens':0}}},
          {'type':'event_msg','timestamp':'2026-11-04T00:00:10Z','payload':{'type':'task_complete','turn_id':'wanted'}}]
        path.write_text(''.join(json.dumps(x)+'\n' for x in events));return path

    def test_total_includes_failed_attempts_and_deduplicated_coordinator(self):
        r=workflow.summarize_run(self.run,self.rollout(),'wanted',self.root)
        self.assertEqual(r['combined_measured']['input_tokens'],1300)
        self.assertEqual(r['combined_measured']['cached_input_tokens'],1030)
        self.assertEqual(r['combined_measured']['non_cached_input_tokens'],270)
        self.assertEqual(r['combined_measured']['output_tokens'],60)
        self.assertEqual(r['combined_measured']['total_tokens'],1360)
        self.assertEqual(r['coordinator']['usage_records'],1)
        self.assertEqual(r['elapsed_seconds'],10)
        self.assertEqual(r['agent_capture_seconds_sum'],9)
        self.assertTrue((self.run/'cost-summary.md').is_file())

    def test_copied_agent_artifacts_are_not_counted_twice(self):
        shutil.copytree(self.run/'agent',self.run/'copied-agent')
        r=workflow.summarize_run(self.run)
        self.assertEqual(r['agent']['total_tokens'],330)
        self.assertEqual(r['agent_capture_seconds_sum'],9)

    def test_report_cli_does_not_start_workflow_or_model(self):
        out=io.StringIO()
        with mock.patch('sys.argv',['agent_workflow','--summarize-run',str(self.run)]),mock.patch('agent_workflow.Workflow') as runner,redirect_stdout(out):
            self.assertEqual(workflow.main(),0)
        runner.assert_not_called()
        self.assertLess(len(out.getvalue()),1024)

    def test_missing_usage_is_unknown_and_missing_coordinator_not_hidden(self):
        workflow.dump(self.run/'agent/attempts.json',[{'attempt':1,'usage_records':[]}])
        r=workflow.summarize_run(self.run)
        self.assertFalse(r['complete'])
        self.assertEqual(r['agent']['unmeasured_attempts'],1)
        self.assertIsNone(r['agent']['total_tokens'])
        self.assertIsNone(r['coordinator'])

    def test_other_project_coordinator_is_rejected(self):
        with self.assertRaises(ValueError):workflow.summarize_run(self.run,self.rollout(Path('/other-project')),'wanted',self.root)
        self.assertFalse((self.run/'cost-summary.json').exists())

    def test_missing_cache_is_unknown_and_inconsistent_total_rejected(self):
        workflow.dump(self.run/'agent/attempts.json',[{'attempt':1,'usage_records':[{'input_tokens':10,'output_tokens':2}]}])
        r=workflow.summarize_run(self.run)
        self.assertIsNone(r['agent']['cached_input_tokens'])
        self.assertIsNone(r['agent']['non_cached_input_tokens'])
        self.assertFalse(r['complete'])
        workflow.dump(self.run/'agent/attempts.json',[{'attempt':1,'usage_records':[{'input_tokens':10,'output_tokens':2,'total_tokens':99}]}])
        with self.assertRaises(ValueError):workflow.summarize_run(self.run)

    def test_invalid_cached_usage_is_not_silently_counted(self):
        workflow.dump(self.run/'agent/attempts.json',[{'attempt':1,'usage_records':[{'input_tokens':1,'cached_input_tokens':2,'output_tokens':0}]}])
        with self.assertRaises(ValueError):workflow.summarize_run(self.run)

    def test_events_preserve_full_details_but_bound_stdout_and_phase_time(self):
        out=io.StringIO()
        with mock.patch('agent_workflow.time.perf_counter',side_effect=[0,2,5]),redirect_stdout(out):
            ctl=workflow.Workflow(self.root,self.run,'Task',probe=False)
            ctl.event('implementing',questions=['X'*20000])
            ctl.event('verifying')
        self.assertLess(len(out.getvalue()),2048)
        self.assertEqual(ctl.state['events'][0]['questions'],['X'*20000])
        self.assertEqual(ctl.state['phase_seconds']['preparing'],2)
        self.assertEqual(ctl.state['phase_seconds']['implementing'],3)


class InputBoundaryTests(unittest.TestCase):
    def test_workflow_does_not_silently_drop_profile_for_custom_adapter(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):workflow.Workflow(Path(t),Path(t)/'run','Task',agent=object(),knowledge_task='query-reset')

    def test_workflow_passes_named_profile_to_common_adapter(self):
        with tempfile.TemporaryDirectory() as t,mock.patch('agent_workflow.CliAgent') as factory:
            workflow.Workflow(Path(t),Path(t)/'run','Task',probe=False,knowledge_task='query-reset',knowledge_base='.local/task-kb')
            factory.assert_called_once_with(knowledge_task='query-reset',knowledge_base='.local/task-kb')

    def test_selected_kb_reaches_actual_transport_and_input_hash(self):
        helper=CliRetryTests();helper.setUp()
        try:
            capture,calls=helper.capture_script([helper.success()]);seen=[]
            def observed(command,prompt,events,timeout,env):
                seen.append(prompt)
                return capture(command,prompt,events,timeout,env)
            metadata={"task":"query-reset","documents":{"knowledge/selected.md":"hash"}}
            with mock.patch("android_knowledge.model_input",return_value=("SELECTED_KB_RULE",metadata)),mock.patch("agent_workflow.capture",side_effect=observed):
                _,identity=workflow.CliAgent(knowledge_task="query-reset")("reviewer",helper.workspace,"Fix task",helper.output)
            self.assertIn("SELECTED_KB_RULE",seen[0]);self.assertNotIn("UNSELECTED_KB",seen[0])
            self.assertEqual(identity['input']['prompt_sha256'],__import__('hashlib').sha256(seen[0].encode()).hexdigest())
            self.assertEqual(identity['input']['knowledge'],metadata)
        finally:helper.doCleanups()

    def test_kb_preparation_failure_prevents_model_call(self):
        with tempfile.TemporaryDirectory() as t,mock.patch('android_knowledge.model_input',side_effect=ValueError('not ready')),mock.patch('agent_workflow.capture') as capture:
            with self.assertRaises(ValueError):workflow.CliAgent(knowledge_task='unknown')('reviewer',Path(t),'Task',Path(t)/'out')
            capture.assert_not_called()

    def test_budget_counts_inserted_kb(self):
        with tempfile.TemporaryDirectory() as t,mock.patch('android_knowledge.model_input',return_value=('X'*1000,{})),mock.patch('agent_workflow.capture') as capture:
            with self.assertRaises(ValueError):workflow.CliAgent(knowledge_task='query-reset',max_prompt_bytes=100)('reviewer',Path(t),'Task',Path(t)/'out')
            capture.assert_not_called()

    def test_utf8_budget_rejects_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("agent_workflow.capture") as capture:
            out = Path(tmp) / "out"
            with self.assertRaisesRegex(ValueError, "prompt.*bytes"):
                workflow.CliAgent(max_prompt_bytes=5)("reviewer", Path(tmp), "한글", out)
            capture.assert_not_called()
            self.assertFalse(out.exists())

    def test_input_metadata_and_failed_attempt_usage(self):
        helper = CliRetryTests(); helper.setUp()
        try:
            failure = ([{"type": "turn.failed", "error": {"message": "429 Too Many Requests"},
                        "usage": {"input_tokens": 9, "cached_input_tokens": 7, "output_tokens": 2}}], 1, None)
            _, identity, calls = helper.invoke([failure, helper.success()])
            info = json.loads((helper.output / "input.json").read_text())
            self.assertEqual(info["prompt_bytes"], len("Synthetic retry test".encode()))
            self.assertEqual(len(info["prompt_sha256"]), 64)
            self.assertNotIn("Synthetic retry test", json.dumps(info))
            self.assertEqual(identity["input"], info)
            self.assertIn("--ephemeral", calls[0]["command"])
            self.assertNotIn("resume", calls[0]["command"])
            attempts = json.loads((helper.output / "attempts.json").read_text())
            self.assertEqual(attempts, identity["attempts"])
            self.assertEqual(attempts[0]["usage_records"][0]["input_tokens"], 9)
            self.assertEqual(len(attempts[1]["usage_records"]), 1)
        finally:
            helper.doCleanups()

    def test_terminal_failure_keeps_unknown_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            def failed(command, prompt, events, timeout, env):
                events.write_text('{"type":"error","message":"offline"}\n')
                return 1
            with mock.patch("agent_workflow.capture", side_effect=failed):
                with self.assertRaises(RuntimeError):
                    workflow.CliAgent()("reviewer", Path(tmp), "task", out)
            attempts = json.loads((out / "attempts.json").read_text())
            self.assertEqual(attempts[0]["usage_records"], [])

    def test_default_evidence_mode_retains_the_full_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = workflow.Workflow(Path(tmp), Path(tmp) / "run", "task", probe=False)
            self.assertEqual(ctl.evidence_mode, "inline")
            ctl.candidate = Path(tmp) / "candidate"
            (Path(tmp) / "prompts").mkdir()
            (Path(tmp) / "prompts/worker.md").write_text("Role rules")
            feedback = {"gate": {"status": "failed", "failures": ["Critical failure"]}}
            self.assertTrue(ctl.prompt("implementer", feedback).endswith(json.dumps(feedback, ensure_ascii=False)))
            self.assertFalse((ctl.run_dir / "prompt-evidence").exists())

    def test_capture_timeout_preserves_partial_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            def timeout(command, prompt, events, limit, env):
                events.write_text(json.dumps({"type": "turn.failed", "usage": {"input_tokens": 8}}) + "\n")
                raise RuntimeError("Agent time limit exceeded")
            with mock.patch("agent_workflow.capture", side_effect=timeout):
                with self.assertRaisesRegex(RuntimeError, "time limit"):
                    workflow.CliAgent()("reviewer", Path(tmp), "task", out)
            attempt = json.loads((out / "attempts.json").read_text())[0]
            self.assertIsNone(attempt["exit_code"])
            self.assertEqual(attempt["error_type"], "RuntimeError")
            self.assertEqual(attempt["usage_records"][0]["input_tokens"], 8)

    def test_gate_log_is_referenced_without_losing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = workflow.Workflow.__new__(workflow.Workflow)
            ctl.root = Path(tmp); ctl.candidate = ctl.root / "candidate"
            ctl.run_dir = ctl.root / "run"; ctl.task = "Fix storage"
            ctl.evidence_mode = "reference"
            (ctl.root / "prompts").mkdir()
            (ctl.root / "prompts/worker.md").write_text("Role rules")
            feedback = {"gate": {"status": "failed", "log": "X" * 100000, "failures": ["Missing row"]},
                        "review": result("revise", findings=["Restore persistence"])}
            prompt = ctl.prompt("implementer", feedback)
            self.assertLess(len(prompt.encode()), 4000)
            self.assertIn("Restore persistence", prompt)
            paths = list((ctl.run_dir / "prompt-evidence").glob("*.json"))
            self.assertEqual(len(paths), 1)
            self.assertEqual(json.loads(paths[0].read_text()), feedback)
            self.assertIn(str(paths[0]), prompt)
            self.assertIn("failed", prompt)


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        # The real controller formats candidates with Cargo. State-machine unit
        # tests isolate that dependency and must never spawn compiler processes.
        formatter = mock.patch.object(workflow.Workflow, "format_sources", return_value=None, create=True)
        formatter.start()
        self.addCleanup(formatter.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="daynomy-flow-unit-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "synthetic-root"
        self.root.mkdir()
        # Minimal trusted tree for state tests. No server or subprocess is run.
        for name in ("AGENTS.md", "README.md", "app/Cargo.toml", "app/Cargo.lock",
                     "app/README.md", "spec/feedback.md"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        workflow.dump(self.root / "spec/reference-snapshot.json", {"root": "reference/synthetic", "files": []})
        for role in ("worker", "reviewer"):
            path = self.root / "prompts" / (role + ".md")
            path.parent.mkdir(exist_ok=True)
            path.write_text("Synthetic unit-test role prompt.\n")
        (self.root / "app/src").mkdir()
        for name in workflow.SOURCES:
            # Controller-state fixtures must not depend on candidate behavior:
            # the real gate also runs this suite against intentionally broken code.
            source = ('#![forbid(unsafe_code)]\nfn main() { let _sql = '
                      '"INSERT INTO feedbacks (content, page_path) VALUES ($1, $2) RETURNING id"; }\n'
                      if name == "main.rs" else '#[cfg(test)]\nmod tests {}\n')
            (self.root / "app/src" / name).write_text(source)
        self.original = workflow.source_hash(self.root / "app/src")
        self.run_dir = self.directory / "run"

    def execute(self, agent=None, gate=None, *, rounds=2, demo=False):
        controller = workflow.Workflow(self.root, self.run_dir, "Synthetic controller unit test",
                                       agent=agent or SyntheticAgent(), gate=gate or SyntheticGate(),
                                       rounds=rounds, demo=demo, probe=False)
        with redirect_stdout(io.StringIO()):
            state = controller.execute()
        self.assertEqual(workflow.source_hash(self.root / "app/src"), self.original,
                         "Workflow must never auto-apply candidate sources to the original app")
        self.assertFalse(controller.worker.exists(), "Worker workspace must be cleaned")
        self.assertEqual(json.loads((self.run_dir / "state.json").read_text())["status"], state["status"])
        return state

    def test_passed_gate_and_approval_complete_without_auto_applying(self):
        def edit(workspace, number):
            path = workspace / "main.rs"
            path.write_text(path.read_text() + "\n// Synthetic candidate-only edit.\n")
        state = self.execute(agent=SyntheticAgent(mutate=edit))
        self.assertEqual(state["status"], "completed")
        self.assertEqual([a["role"] for a in state["agents"]], ["implementer", "reviewer"])
        self.assertIn("Synthetic candidate-only edit", (self.run_dir / "candidate.patch").read_text())

    def test_failed_gate_cannot_be_overridden_by_reviewer_approval(self):
        state = self.execute(gate=SyntheticGate(["failed"]), rounds=1)
        self.assertEqual(state["status"], "failed")
        self.assertNotIn("completed", [event["status"] for event in state["events"]])
        self.assertFalse((self.run_dir / "candidate.patch").exists())

    def test_review_revision_repairs_then_completes(self):
        agent = SyntheticAgent(reviews=[result("revise", findings=["Review requests a fix."]),
                                        result("approve")])
        state = self.execute(agent=agent)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(agent.calls, ["implementer", "reviewer", "implementer", "reviewer"])
        self.assertEqual(len(state["rounds"]), 2)
        self.assertIn("Review requests a fix.", agent.prompts[2])

    def test_failed_gate_feeds_next_implementation_then_completes(self):
        agent = SyntheticAgent(reviews=[result("revise", findings=["Missing stored row."]),
                                        result("approve")])
        gate = SyntheticGate(["failed", "passed"])
        state = self.execute(agent=agent, gate=gate)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(gate.calls, 2)
        self.assertIn("Missing stored row.", agent.prompts[2])
        self.assertEqual([r["gate"]["status"] for r in state["rounds"]], ["failed", "passed"])

    def test_decision_request_stops_without_completion(self):
        agent = SyntheticAgent(reviews=[result("needs_decision", questions=["Which input policy applies?"])])
        state = self.execute(agent=agent)
        self.assertEqual(state["status"], "needs_decision")
        self.assertEqual(state["events"][-1]["questions"], ["Which input policy applies?"])
        self.assertEqual(len(state["rounds"]), 1)
        self.assertFalse((self.run_dir / "candidate.patch").exists())

    def test_implementer_decision_request_skips_gate(self):
        agent = SyntheticAgent(implementations=[result("needs_decision", questions=["Policy question?"])])
        gate = SyntheticGate()
        state = self.execute(agent=agent, gate=gate)
        self.assertEqual(state["status"], "needs_decision")
        self.assertEqual(gate.calls, 0)
        self.assertEqual(agent.calls, ["implementer"])

    def test_reused_session_identity_blocks_completion(self):
        state = self.execute(agent=SyntheticAgent(repeat_identity=True))
        self.assertEqual(state["status"], "blocked")
        self.assertIn("independent", state["events"][-1]["reason"])

    def test_workflow_automatically_writes_cost_summary(self):
        state=self.execute()
        report=json.loads((self.run_dir/'cost-summary.json').read_text())
        self.assertEqual(report['workflow_status'],state['status'])
        self.assertIn('phase_seconds',report)
        self.assertIn('cost_report',state)

    def test_round_limit_stops_perpetual_review_revision(self):
        agent = SyntheticAgent(reviews=[result("revise", findings=["Still incomplete."])])
        state = self.execute(agent=agent)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(len(state["rounds"]), 2)
        self.assertFalse((self.run_dir / "candidate.patch").exists())

    def test_claimed_gate_success_with_missing_evidence_cannot_complete(self):
        state = self.execute(gate=SyntheticGate(missing_report=True), rounds=1)
        self.assertNotEqual(state["status"], "completed")
        self.assertFalse((self.run_dir / "candidate.patch").exists())

    def test_invalid_agent_result_blocks_completion(self):
        agent = SyntheticAgent(reviews=[result("approve", findings=["Unresolved defect."])])
        state = self.execute(agent=agent)
        self.assertEqual(state["status"], "blocked")

    def test_candidate_source_changed_during_gate_blocks_completion(self):
        def mutating_gate(candidate, root, output_dir, db_name):
            evidence = synthetic_gate(output_dir)
            path = candidate / "app/src/main.rs"
            path.write_text(path.read_text() + "\n// Gate must not mutate source.\n")
            return evidence
        state = self.execute(gate=mutating_gate)
        self.assertEqual(state["status"], "blocked")
        self.assertIn("changed during validation", state["events"][-1]["reason"])

    def test_synthetic_fault_demo_injects_once_then_uses_repair(self):
        observed_faults = []

        def repair(workspace, number):
            if number == 2:
                shutil.copyfile(self.root / "app/src/main.rs", workspace / "main.rs")

        def observing_gate(candidate, root, output_dir, db_name):
            source = (candidate / "app/src/main.rs").read_text()
            fault = "SELECT 1::bigint AS id WHERE" in source
            observed_faults.append(fault)
            return synthetic_gate(output_dir, status="failed" if fault else "passed")

        agent = SyntheticAgent(mutate=repair,
                               reviews=[result("revise", findings=["Synthetic no-save defect."]),
                                        result("approve")])
        state = self.execute(agent=agent, gate=observing_gate, demo=True)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(observed_faults, [True, False])
        self.assertEqual(sum(event["status"] == "fault_injected" for event in state["events"]), 1)
        self.assertIn("Synthetic no-save defect.", agent.prompts[2])

    def test_protected_criteria_change_blocks_completion(self):
        def change_criteria(workspace, number):
            path = self.root / "spec/feedback.md"
            path.write_text(path.read_text() + "\nSynthetic unauthorized contract change.\n")

        state = self.execute(agent=SyntheticAgent(mutate=change_criteria))
        self.assertEqual(state["status"], "blocked")
        self.assertIn("Trusted criteria changed", state["events"][-1]["reason"])


if __name__ == "__main__":
    unittest.main()
