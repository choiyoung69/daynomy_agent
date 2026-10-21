"""Focused callback measurement regressions; local callbacks, not agent evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import task_queue
from task_queue import Job, TaskQueue


class CallbackMetricTests(unittest.TestCase):
    def test_immediate_callbacks_measure_actual_concurrency(self):
        lock = threading.Lock()
        active = 0
        observed_peak = 0

        def execute(job, deadline):
            nonlocal active, observed_peak
            with lock:
                active += 1
                observed_peak = max(observed_peak, active)
                active -= 1
            return {"status": "completed"}

        with tempfile.TemporaryDirectory() as directory:
            state = TaskQueue([Job(str(i), "agent") for i in range(30)], execute,
                              Path(directory) / "state.json").run()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(observed_peak, 1)
        self.assertEqual(state["metrics"]["peak_running_agents"], observed_peak)
        for record in state["tasks"].values():
            self.assertLessEqual(record["dispatched_at"], record["started_at"])
            self.assertLessEqual(record["started_at"], record["callback_finished_at"])
            self.assertAlmostEqual(record["busy_seconds"],
                                   record["callback_finished_at"] - record["started_at"])

    def test_executor_queue_delay_is_not_callback_busy_time(self):
        release = threading.Event()
        released_at = []

        class DelayedExecutor(ThreadPoolExecutor):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.submitted = 0

            def submit(self, function, *args, **kwargs):
                def after_release():
                    if not release.wait(3):
                        raise AssertionError("dispatcher did not fill its slots")
                    return function(*args, **kwargs)
                future = super().submit(after_release)
                self.submitted += 1
                if self.submitted == 3:
                    released_at.append(time.monotonic())
                    release.set()
                return future

        with tempfile.TemporaryDirectory() as directory, patch.object(task_queue, "ThreadPoolExecutor", DelayedExecutor):
            observed = {}
            def execute(job, deadline):
                observed[job.id] = time.monotonic()
                return {"status": "completed"}
            state = TaskQueue([Job(str(i), "agent") for i in range(3)], execute,
                              Path(directory) / "state.json").run()
        self.assertEqual(state["status"], "completed")
        # The initial two submissions happened before the last submit released
        # executor workers. Started timestamps must capture actual invocation.
        first, second, third = (state["tasks"][str(i)] for i in range(3))
        for record in (first, second):
            self.assertGreaterEqual(record["started_at"], third["dispatched_at"])
        self.assertTrue(all(stamp >= released_at[0] for stamp in observed.values()))
        self.assertEqual(state["metrics"]["peak_running_agents"], 1)

    def test_published_event_sequence_follows_actual_timeline(self):
        jobs = [Job("a", "agent"), Job("b", "agent"), Job("review", "agent", ("a",)),
                Job("gate", "check", ("review", "b"))]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = TaskQueue(jobs, lambda *_: {"status": "completed"}, path).run()
            persisted = json.loads(path.read_text())
            timeline = json.loads(path.with_name("state.events.json").read_text())
        self.assertEqual(state["status"], "completed")
        self.assertEqual(timeline, persisted["events"])
        self.assertEqual(timeline, state["events"])
        self.assertEqual([event["sequence"] for event in timeline], list(range(len(timeline))))
        self.assertEqual([event["at"] for event in timeline], sorted(event["at"] for event in timeline))
        for record in state["tasks"].values():
            self.assertLessEqual(record["ready_at"], record["dispatched_at"])
            self.assertLessEqual(record["dispatched_at"], record["started_at"])
            self.assertLessEqual(record["started_at"], record["finished_at"])


if __name__ == "__main__":
    unittest.main()
