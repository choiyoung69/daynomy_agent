"""Independent, local-only scheduling contract tests (no real agent calls)."""
import dataclasses
from pathlib import Path
import tempfile
import threading
import time
import unittest

from task_queue import Job, TaskQueue


class TaskQueueContractTests(unittest.TestCase):
    def run_queue(self, jobs, execute, **options):
        with tempfile.TemporaryDirectory(prefix="task-queue-contract-") as directory:
            return TaskQueue(jobs, execute, Path(directory) / "state.json", **options).run()

    def completed(self, state, ids):
        self.assertEqual(state["status"], "completed")
        self.assertEqual(set(state["tasks"]), set(ids))
        for job_id in ids:
            self.assertEqual(state["tasks"][job_id]["status"], "completed")

    def test_job_is_frozen(self):
        job = Job("a", "agent")
        self.assertEqual(job.deps, ())
        self.assertEqual(job.priority, 10)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            job.id = "changed"

    def test_rejects_duplicate_job_ids(self):
        with self.assertRaises(ValueError):
            self.run_queue([Job("a", "agent"), Job("a", "check")], lambda *_: {"status": "completed"})

    def test_rejects_unknown_dependency(self):
        with self.assertRaises(ValueError):
            self.run_queue([Job("a", "agent", ("missing",))], lambda *_: {"status": "completed"})

    def test_rejects_cycles_and_self_dependency(self):
        for jobs in ([Job("a", "agent", ("a",))],
                     [Job("a", "agent", ("b",)), Job("b", "check", ("a",))]):
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                self.run_queue(jobs, lambda *_: {"status": "completed"})

    def test_rejects_invalid_slot_counts(self):
        for options in ({"agent_slots": 0}, {"agent_slots": 4}, {"check_slots": 0}, {"check_slots": 2}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_queue([Job("a", "agent")], lambda *_: {"status": "completed"}, **options)

    def test_failure_blocks_transitive_dependents_but_independent_work_completes(self):
        called = set()
        lock = threading.Lock()
        def execute(job, deadline):
            with lock:
                called.add(job.id)
            return {"status": "failed" if job.id == "implementation" else "completed"}
        jobs = [Job("implementation", "agent"), Job("review", "agent", ("implementation",)),
                Job("gate", "check", ("review",)), Job("independent", "agent")]
        state = self.run_queue(jobs, execute)
        self.assertNotEqual(state["status"], "completed")
        self.assertEqual(called, {"implementation", "independent"})
        self.assertEqual(state["tasks"]["implementation"]["status"], "failed")
        self.assertEqual(state["tasks"]["independent"]["status"], "completed")
        for job_id in ("review", "gate"):
            self.assertEqual(state["tasks"][job_id]["status"], "blocked_dependency")

    def test_only_completed_executor_status_unlocks_dependents(self):
        for returned_status in ("approve", "failed"):
            with self.subTest(returned_status=returned_status):
                called = []
                def execute(job, deadline):
                    called.append(job.id)
                    return {"status": returned_status}
                state = self.run_queue([Job("review", "agent"), Job("gate", "check", ("review",))], execute)
                self.assertNotEqual(state["status"], "completed")
                self.assertNotEqual(state["tasks"]["review"]["status"], "completed")
                self.assertEqual(state["tasks"]["gate"]["status"], "blocked_dependency")
                self.assertEqual(called, ["review"])

    def test_dependencies_are_completed_before_execution(self):
        finished = set()
        lock = threading.Lock()
        def execute(job, deadline):
            with lock:
                self.assertTrue(set(job.deps) <= finished)
                self.assertGreater(deadline, time.monotonic())
                finished.add(job.id)
            return {"status": "completed"}
        jobs = [Job("gate", "check", ("review", "tests")), Job("review", "agent", ("implementation",)),
                Job("tests", "agent"), Job("implementation", "agent")]
        state = self.run_queue(jobs, execute)
        self.completed(state, [job.id for job in jobs])

    def test_three_agent_slots_are_filled_and_never_exceeded(self):
        lock = threading.Lock()
        initial_three = threading.Event()
        active = 0
        peak = 0
        started = 0
        def execute(job, deadline):
            nonlocal active, peak, started
            with lock:
                active += 1
                started += 1
                peak = max(peak, active)
                if started >= 3:
                    initial_three.set()
            try:
                self.assertTrue(initial_three.wait(3), "three independent agents must start together")
                return {"status": "completed"}
            finally:
                with lock:
                    active -= 1
        jobs = [Job(str(i), "agent") for i in range(9)]
        state = self.run_queue(jobs, execute)
        self.completed(state, [job.id for job in jobs])
        self.assertEqual(peak, 3)
        self.assertEqual(state["metrics"]["peak_running_agents"], 3)

    def test_freed_slot_is_backfilled_before_other_running_agents_finish(self):
        lock = threading.Lock()
        initial_three = threading.Event()
        replacement_started = threading.Event()
        started = set()
        def execute(job, deadline):
            with lock:
                started.add(job.id)
                if {"a", "b", "c"} <= started:
                    initial_three.set()
            if job.id == "a":
                self.assertTrue(initial_three.wait(3))
            elif job.id in ("b", "c"):
                self.assertTrue(replacement_started.wait(3), "a free slot must be backfilled while peers run")
            else:
                self.assertTrue(initial_three.is_set())
                replacement_started.set()
            return {"status": "completed"}
        jobs = [Job(name, "agent", priority=0) for name in ("a", "b", "c")]
        jobs.append(Job("replacement", "agent", priority=100))
        state = self.run_queue(jobs, execute)
        self.completed(state, [job.id for job in jobs])
        self.assertTrue(replacement_started.is_set())

    def test_check_slot_is_separate_and_serialized(self):
        lock = threading.Lock()
        all_kinds_running = threading.Event()
        active_agents = 0
        active_checks = 0
        peak_checks = 0
        def execute(job, deadline):
            nonlocal active_agents, active_checks, peak_checks
            with lock:
                if job.kind == "agent":
                    active_agents += 1
                else:
                    active_checks += 1
                    peak_checks = max(peak_checks, active_checks)
                if active_agents == 3 and active_checks == 1:
                    all_kinds_running.set()
            try:
                self.assertTrue(all_kinds_running.wait(3), "one check must run alongside three agents")
                return {"status": "completed"}
            finally:
                with lock:
                    if job.kind == "agent":
                        active_agents -= 1
                    else:
                        active_checks -= 1
        jobs = [Job("agent-" + str(i), "agent") for i in range(3)]
        jobs += [Job("check-" + str(i), "check") for i in range(3)]
        state = self.run_queue(jobs, execute)
        self.completed(state, [job.id for job in jobs])
        self.assertEqual(peak_checks, 1)
        self.assertEqual(state["metrics"]["peak_running_checks"], 1)

    def test_metrics_and_task_kinds_describe_actual_successful_run(self):
        started = time.monotonic()
        state = self.run_queue([Job("work", "agent"), Job("gate", "check", ("work",))],
                               lambda *_: {"status": "completed"})
        elapsed = time.monotonic() - started
        self.completed(state, ["work", "gate"])
        self.assertEqual(state["tasks"]["work"]["kind"], "agent")
        self.assertEqual(state["tasks"]["gate"]["kind"], "check")
        metrics = state["metrics"]
        for name in ("wall_seconds", "sum_agent_busy_seconds", "agent_slot_utilization"):
            self.assertIsInstance(metrics[name], (int, float))
            self.assertGreaterEqual(metrics[name], 0)
        self.assertLessEqual(metrics["wall_seconds"], elapsed + 0.25)
        self.assertLessEqual(metrics["sum_agent_busy_seconds"], metrics["wall_seconds"] * 3 + 0.01)
        self.assertLessEqual(metrics["agent_slot_utilization"], 1)
        self.assertEqual(metrics["peak_running_agents"], 1)
        self.assertEqual(metrics["peak_running_checks"], 1)


if __name__ == "__main__":
    unittest.main()
