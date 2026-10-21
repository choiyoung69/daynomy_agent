"""Lock regression checks; never start models, servers, or a database."""
from contextlib import ExitStack
import fcntl
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import admin_feedback_gate as gate


class GateLockTests(unittest.TestCase):
    def blocked_gate(self, root):
        output = root / "output"
        with ExitStack() as stack:
            stack.enter_context(patch.object(gate.sample_gate, "ROOT", root))
            worker = stack.enter_context(patch.object(gate, "_run"))
            subprocess_run = stack.enter_context(patch.object(gate.subprocess, "run"))
            subprocess_start = stack.enter_context(patch.object(gate.subprocess, "Popen"))
            spring_start = stack.enter_context(patch.object(gate.spring, "start"))
            started = time.monotonic()
            state = gate.run_gate(root / "candidate", output, root / "target", timeout_seconds=.08)
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 1.5, "lock contention must return without waiting for its owner")
            self.assertGreaterEqual(elapsed, .06)
            self.assertEqual(state["status"], "blocked")
            self.assertEqual(state["reason"], "lock-timeout")
            self.assertEqual(state["commands"], [])
            self.assertEqual(state["results"], [])
            self.assertGreaterEqual(state["elapsed_seconds"], .06)
            self.assertEqual(json.loads(Path(state["report"]).read_text()), state)
            for operation in (worker, subprocess_run, subprocess_start, spring_start):
                operation.assert_not_called()

    def test_held_thread_lock_times_out_before_any_runtime_work(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(gate.sample_gate._GATE_LOCK.acquire(timeout=1))
            try:
                self.blocked_gate(Path(directory))
                self.assertTrue(gate.sample_gate._GATE_LOCK.locked())
            finally:
                gate.sample_gate._GATE_LOCK.release()

    def test_held_file_lock_times_out_and_releases_thread_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path = root / ".local/sample-gate.lock"
            lock_path.parent.mkdir()
            with lock_path.open("a") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX)
                try:
                    self.blocked_gate(root)
                    self.assertTrue(gate.sample_gate._GATE_LOCK.acquire(timeout=.2))
                    gate.sample_gate._GATE_LOCK.release()
                finally:
                    fcntl.flock(held.fileno(), fcntl.LOCK_UN)

    def test_locks_are_released_when_gate_worker_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(gate.sample_gate, "ROOT", root), patch.object(gate, "_run", side_effect=RuntimeError):
                state = gate.run_gate(root / "candidate", root / "output", root / "target", timeout_seconds=1)
            self.assertEqual(state["status"], "blocked")
            self.assertTrue(gate.sample_gate._GATE_LOCK.acquire(timeout=.2))
            gate.sample_gate._GATE_LOCK.release()
            with (root / ".local/sample-gate.lock").open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    unittest.main()
