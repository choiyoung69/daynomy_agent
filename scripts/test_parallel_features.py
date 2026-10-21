#!/usr/bin/env python3
"""Synthetic parallel-controller tests: no model, native sandbox, Rust or DB runs.

The agent/probe/gate dependencies below are explicitly fake. Full source copies
are real, but a synthetic pass proves controller decisions only, never API
compatibility or a real agent's permission enforcement.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid

import parallel_features as workflow
import agent_workflow
import sample_feature_gate

REAL_ROOT = workflow.ROOT
TRUSTED_SCRIPTS = (
    "parallel_features.py", "agent_workflow.py", "sample_feature_gate.py",
    "acceptance.py", "run_comparison.py", "workflow_gate.py", "local-db.sh",
)


def verdict(status, **extra):
    return {"status": status, "summary": "SYNTHETIC controller test, no AI invoked",
            "findings": [], "questions": [], **extra}


def synthetic_probe(workspace, control, role):
    """A dependency stub, deliberately not evidence of OS sandbox enforcement."""
    return {"role": role, "passed": True, "synthetic": True}


class SyntheticAgent:
    def __init__(self, hook=None, barrier=None):
        self.hook, self.barrier = hook, barrier
        self.lock = threading.Lock()
        self.calls = []
        self.counts = Counter()
        self.active = self.max_active = self.active_reviewers = self.max_reviewers = 0

    def __call__(self, definition, role, workspace, prompt, output):
        owner = definition["name"] if role == "implementer" else Path(output).parents[1].name
        with self.lock:
            self.calls.append((owner, role, definition.get("model")))
            self.counts[(owner, role)] += 1
            number = self.counts[(owner, role)]
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if role == "reviewer":
                self.active_reviewers += 1
                self.max_reviewers = max(self.max_reviewers, self.active_reviewers)
        try:
            if self.barrier and role == "implementer" and number == 1:
                self.barrier.wait(timeout=5)
            time.sleep(0.01)
            answer = self.hook(owner, role, Path(workspace), number) if self.hook else None
            return answer or verdict("implemented" if role == "implementer" else "approve"), {
                "session_id": "synthetic-" + uuid.uuid4().hex, "role": role, "synthetic": True}
        finally:
            with self.lock:
                self.active -= 1
                if role == "reviewer":
                    self.active_reviewers -= 1


class SyntheticGate:
    def __init__(self, statuses=None, corrupt=None):
        self.statuses = statuses or {}
        self.corrupt = corrupt
        self.counts = Counter()
        self.lock = threading.Lock()

    def __call__(self, candidate, output, directory):
        candidate, output = Path(candidate), Path(output)
        owner = "integration" if candidate.name == "integrated" else candidate.parent.name
        with self.lock:
            self.counts[owner] += 1
            count = self.counts[owner]
        script = self.statuses.get(owner, ["passed"])
        status = script[min(count - 1, len(script) - 1)]
        stamp = time.time()
        evidence = {
            "synthetic": True, "status": status,
            "report": str(output / "result.json"),
            "source_hashes": workflow.hashes(candidate),
            "started_at": stamp, "finished_at": time.time(),
            "results": [{"case": name, "passed": status == "passed"}
                        for name in sorted(workflow.EXPECTED_CASES)],
            "commands": [{"name": name, "exit_code": 0 if status == "passed" else 1}
                         for name in ("format", "clippy", "build", "database-create")],
        }
        if self.corrupt:
            self.corrupt(owner, evidence)
        workflow.dump(output / "result.json", evidence)
        return evidence


class ParallelControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daynomy-parallel-synthetic-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "experiments/representative"
        shutil.copytree(REAL_ROOT / "experiments/representative", self.base,
                        ignore=shutil.ignore_patterns("target"))
        for relative in ["AGENTS.md", "agents/representative.json", "spec/representative-sample.md",
                         *("scripts/" + name for name in TRUSTED_SCRIPTS)]:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REAL_ROOT / relative, destination)
        shutil.copytree(REAL_ROOT / "app/src", self.root / "app/src")
        for name, value in {"ROOT": self.root, "BASE": self.base,
                            "CONFIG": self.root / "agents/representative.json",
                            "CONTRACT": self.root / "spec/representative-sample.md"}.items():
            patcher = mock.patch.object(workflow, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        import json
        self.config = json.loads(workflow.CONFIG.read_text())
        self.baseline = workflow.tree(self.base)

    def runner(self, agent=None, gate=None, config=None):
        return workflow.ParallelSample(self.root / ("run-" + uuid.uuid4().hex),
                                       config=config or self.config, agent=agent or SyntheticAgent(),
                                       gate=gate or SyntheticGate(), probe=synthetic_probe)

    def run_quiet(self, runner):
        with redirect_stdout(io.StringIO()):
            state = runner.run()
        self.assertEqual(workflow.tree(self.base), self.baseline)
        for job in runner.jobs.values():
            self.assertFalse(Path(job["worker"]).exists(), "Temporary worker must be cleaned")
        return state

    def test_independent_implementations_overlap_with_two_total_calls_and_one_reviewer(self):
        agent = SyntheticAgent(barrier=threading.Barrier(2))
        runner = self.runner(agent)
        state = self.run_quiet(runner)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(agent.max_active, 2)
        self.assertEqual(agent.max_reviewers, 1)
        self.assertEqual(len(runner.sessions), 4)
        self.assertEqual(state["integration"]["status"], "passed")

    def test_one_call_setting_serializes_model_calls(self):
        config = deepcopy(self.config)
        config["max_model_calls"] = 1
        agent = SyntheticAgent()
        self.assertEqual(self.run_quiet(self.runner(agent, config=config))["status"], "completed")
        self.assertEqual(agent.max_active, 1)

    def test_one_worker_failure_does_not_cancel_other_task(self):
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "implementer":
                raise RuntimeError("Synthetic independent task failure")
        runner = self.runner(SyntheticAgent(hook))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertEqual(runner.jobs["portfolio"]["status"], "completed")
        self.assertIn("Synthetic independent task failure", runner.jobs["news"]["reason"])
        self.assertFalse((runner.directory / "integrated").exists())

    def test_failed_gate_repairs_without_spending_review_on_bad_candidate(self):
        agent = SyntheticAgent()
        gate = SyntheticGate(statuses={"news": ["failed", "passed"]})
        runner = self.runner(agent, gate)
        self.assertEqual(self.run_quiet(runner)["status"], "completed")
        self.assertEqual(agent.counts[("news", "implementer")], 2)
        self.assertEqual(agent.counts[("news", "reviewer")], 1)
        self.assertEqual(gate.counts["news"], 2)

    def test_review_revision_routes_back_to_owned_implementation(self):
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "reviewer" and number == 1:
                return verdict("revise", findings=["news.rs:1: Synthetic missing branch"])
        agent = SyntheticAgent(hook)
        runner = self.runner(agent)
        self.assertEqual(self.run_quiet(runner)["status"], "completed")
        self.assertEqual(agent.counts[("news", "implementer")], 2)
        self.assertEqual(agent.counts[("news", "reviewer")], 2)
        self.assertEqual(agent.counts[("portfolio", "implementer")], 1)

    def test_needs_decision_preserves_question_and_prevents_integration(self):
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "reviewer":
                return verdict("needs_decision", questions=["Synthetic missing publication policy?"])
        runner = self.runner(SyntheticAgent(hook))
        self.assertEqual(self.run_quiet(runner)["status"], "needs_decision")
        self.assertTrue(runner.jobs["news"]["review"]["questions"])
        self.assertIsNone(runner.state["integration"])
        self.assertFalse((runner.directory / "candidate.patch").exists())

    def test_rejects_extra_worker_file(self):
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "implementer":
                (workspace / "unauthorized.rs").write_text("synthetic")
        runner = self.runner(SyntheticAgent(hook))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertIn("unexpected paths", runner.jobs["news"]["reason"])

    def test_rejects_symlink_instead_of_owned_worker_source(self):
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "implementer":
                source = workspace / "news.rs"
                source.unlink()
                source.symlink_to(self.base / "src/news.rs")
        runner = self.runner(SyntheticAgent(hook))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertIn("regular file", runner.jobs["news"]["reason"])

    def test_rejects_edit_to_other_tasks_candidate_source(self):
        runner = None
        def hook(owner, role, workspace, number):
            if owner == "news" and role == "implementer":
                other = Path(runner.jobs["news"]["candidate"]) / "src/portfolio_calc.rs"
                other.write_text(other.read_text() + "\n// Synthetic unauthorized edit\n")
        runner = self.runner(SyntheticAgent(hook))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertIn("protected scaffold", runner.jobs["news"]["reason"])

    def test_missing_report_cannot_be_approved(self):
        class MissingGate(SyntheticGate):
            def __call__(self, candidate, output, directory):
                evidence = super().__call__(candidate, output, directory)
                Path(evidence["report"]).unlink()
                return evidence
        agent = SyntheticAgent()
        runner = self.runner(agent, MissingGate())
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertEqual(sum(v for (owner, role), v in agent.counts.items() if role == "reviewer"), 0)

    def test_stale_report_cannot_be_approved(self):
        def corrupt(owner, evidence):
            evidence["started_at"] = evidence["finished_at"] = 1
        runner = self.runner(gate=SyntheticGate(corrupt=corrupt))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")
        self.assertTrue(all("stale" in job["reason"] for job in runner.jobs.values()))

    def test_incomplete_case_set_cannot_be_approved(self):
        def corrupt(owner, evidence):
            evidence["results"].pop()
        runner = self.runner(gate=SyntheticGate(corrupt=corrupt))
        self.assertEqual(self.run_quiet(runner)["status"], "blocked")

    def test_successful_merge_contains_only_reviewed_hashes(self):
        def hook(owner, role, workspace, number):
            if role == "implementer":
                path = workspace / workflow.OWNERS[owner]
                path.write_text(path.read_text() + f"\n// Synthetic {owner} change\n")
        runner = self.runner(SyntheticAgent(hook))
        state = self.run_quiet(runner)
        self.assertEqual(state["status"], "completed")
        integrated = Path(state["integration"]["candidate"])
        self.assertEqual(workflow.hashes(integrated), {
            job["file"]: job["approved_hash"] for job in runner.jobs.values()})
        self.assertIn("Synthetic news change", (runner.directory / "candidate.patch").read_text())
        self.assertIn("Synthetic portfolio change", (runner.directory / "candidate.patch").read_text())

    def test_post_review_source_mutation_blocks_merge(self):
        runner = self.runner()
        tasks = self.config["tasks"]
        with redirect_stdout(io.StringIO()):
            for task in tasks:
                runner.task(task)
        self.assertTrue(all(j["status"] == "completed" for j in runner.jobs.values()))
        source = Path(runner.jobs["news"]["candidate"]) / "src/news.rs"
        source.write_text(source.read_text() + "\n// Synthetic mutation after approval\n")
        with self.assertRaisesRegex(ValueError, "Approved task changed"):
            runner.integrate()
        self.assertFalse((runner.directory / "candidate.patch").exists())

    def test_failed_final_integration_gate_blocks_completion(self):
        runner = self.runner(gate=SyntheticGate(statuses={"integration": ["failed"]}))
        state = self.run_quiet(runner)
        self.assertEqual(state["status"], "failed")
        self.assertTrue(all(j["status"] == "completed" for j in runner.jobs.values()))
        self.assertEqual(state["integration"]["status"], "failed")
        self.assertFalse((runner.directory / "candidate.patch").exists())

    def test_configuration_rejects_overlapping_task_ownership(self):
        config = deepcopy(self.config)
        config["tasks"][1]["file"] = "news.rs"
        with self.assertRaisesRegex(ValueError, "ownership"):
            workflow.validate_config(config)

    def test_explicit_models_reach_separate_agent_definitions(self):
        config = deepcopy(self.config)
        config["tasks"][0]["model"] = "synthetic-news-model"
        config["tasks"][1]["model"] = "synthetic-portfolio-model"
        config["reviewer"]["model"] = "synthetic-review-model"
        agent = SyntheticAgent()
        self.assertEqual(self.run_quiet(self.runner(agent, config=config))["status"], "completed")
        self.assertIn(("news", "implementer", "synthetic-news-model"), agent.calls)
        self.assertIn(("portfolio", "implementer", "synthetic-portfolio-model"), agent.calls)
        self.assertEqual([model for _, role, model in agent.calls if role == "reviewer"],
                         ["synthetic-review-model"] * 2)


class CliConfigurationTests(unittest.TestCase):
    def test_explicit_model_is_forwarded_as_separate_cli_argument(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            def capture(command, prompt, events, timeout, env):
                self.assertEqual(command[command.index("--model") + 1], "synthetic-model-id")
                self.assertEqual(command[-1], "-")
                Path(command[command.index("-o") + 1]).write_text(json.dumps(verdict("implemented")))
                events.write_text(json.dumps({"type": "thread.started", "thread_id": "synthetic-session"}) + "\n")
                return 0
            with mock.patch.object(agent_workflow, "capture", side_effect=capture):
                _, meta = agent_workflow.CliAgent(model="synthetic-model-id", max_attempts=1)(
                    "implementer", root, "synthetic prompt", root / "output")
            self.assertEqual(meta["model_selection"], "explicit")
            self.assertEqual(meta["requested_model"], "synthetic-model-id")

    def test_parallel_mode_does_not_retry_rate_limited_calls(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            def capture(command, prompt, events, timeout, env):
                events.write_text(json.dumps({"type": "error", "message": "429 Too Many Requests"}) + "\n")
                return 1
            with mock.patch.object(agent_workflow, "capture", side_effect=capture) as call:
                with self.assertRaisesRegex(RuntimeError, "429"):
                    agent_workflow.CliAgent(max_attempts=1)("implementer", root, "synthetic", root / "output")
            self.assertEqual(call.call_count, 1)


class GateResourceLockTests(unittest.TestCase):
    def test_separate_processes_serialize_with_file_lock(self):
        """Independent interpreters cannot share the in-process threading lock."""
        program = r'''
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, sys.argv[1])
import sample_feature_gate
root, identity = Path(sys.argv[2]), sys.argv[3]
sample_feature_gate.ROOT = root
(root / (identity + ".ready")).touch()
deadline = time.monotonic() + 5
while not (root / "start").exists():
    if time.monotonic() >= deadline:
        raise RuntimeError("Synthetic lock-test start deadline")
    time.sleep(0.005)
with sample_feature_gate.gate_lock():
    entered = time.monotonic()
    time.sleep(0.1)
    exited = time.monotonic()
print(json.dumps({"entered": entered, "exited": exited}))
'''
        with tempfile.TemporaryDirectory(prefix="daynomy-processlock-synthetic-", dir="/private/tmp") as directory:
            root, children = Path(directory), []
            try:
                for identity in ("first", "second"):
                    children.append(subprocess.Popen(
                        [sys.executable, "-c", program, str(REAL_ROOT / "scripts"), directory, identity],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                deadline = time.monotonic() + 5
                while not all((root / (identity + ".ready")).exists() for identity in ("first", "second")):
                    if time.monotonic() >= deadline or any(child.poll() is not None for child in children):
                        self.fail("Synthetic lock-test children did not become ready")
                    time.sleep(0.005)
                (root / "start").touch()
                intervals = []
                for child in children:
                    stdout, stderr = child.communicate(timeout=5)
                    self.assertEqual(child.returncode, 0, stderr)
                    intervals.append(json.loads(stdout))
                first, second = sorted(intervals, key=lambda interval: interval["entered"])
                self.assertGreater(first["exited"], first["entered"])
                self.assertGreater(second["exited"], second["entered"])
                self.assertGreaterEqual(second["entered"], first["exited"])
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)

    def test_threads_serialize_shared_real_gate_resources_without_running_gate(self):
        with tempfile.TemporaryDirectory(prefix="daynomy-gatelock-synthetic-", dir="/private/tmp") as directory:
            active = maximum = 0
            mutex = threading.Lock()
            ready = threading.Barrier(4)
            def contender():
                nonlocal active, maximum
                ready.wait(timeout=5)
                with sample_feature_gate.gate_lock():
                    with mutex:
                        active += 1
                        maximum = max(maximum, active)
                    time.sleep(0.01)
                    with mutex:
                        active -= 1
            with mock.patch.object(sample_feature_gate, "ROOT", Path(directory)):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = [pool.submit(contender) for _ in range(4)]
                    for future in futures:
                        future.result(timeout=5)
            self.assertEqual(maximum, 1)
            self.assertEqual(active, 0)


if __name__ == "__main__":
    unittest.main()
