#!/usr/bin/env python3
"""A bounded DAG dispatcher for real, deadline-aware agent/check callbacks.

This module does not launch agents, retry jobs, resume runs, or kill processes.
The execute callback owns its subprocess lifecycle and must honor the absolute
monotonic deadline supplied to it. Threads cannot forcibly stop that callback.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    deps: tuple[str, ...] = ()
    priority: int = 10


_TERMINAL = {"completed", "failed", "blocked_dependency", "timed_out"}
_SENSITIVE_KEYS = {
    "command", "cmd", "args", "argv", "stdout", "stderr", "output",
    "exception", "traceback", "error", "message", "prompt", "body",
    "headers", "environment", "env", "cookies", "cookie", "authorization",
}


def _safe_result(value: object, depth: int = 0) -> object:
    """Keep JSON metadata, redact known payload/credential fields, bound nesting.

    Callbacks should return evidence paths/counts/statuses rather than raw model
    output or credentials. Raw exception strings are never persisted here.
    """
    if depth > 12:
        return "[redacted]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:4096]
    if isinstance(value, (list, tuple)):
        return [_safe_result(item, depth + 1) for item in value[:1000]]
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:1000]:
            if not isinstance(key, str):
                continue
            normalized = key.lower().replace("-", "_")
            sensitive = normalized in _SENSITIVE_KEYS or any(
                fragment in normalized for fragment in
                ("token", "secret", "password", "credential", "connection_string", "database_url", "api_key")
            )
            result[key] = "[redacted]" if sensitive else _safe_result(item, depth + 1)
        return result
    return "[non-JSON result]"


def _dump(path: Path, value: object) -> None:
    """Publish a complete JSON file with atomic replacement on the same FS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class TaskQueue:
    def __init__(
        self,
        jobs: list[Job],
        execute: Callable[[Job, float], dict],
        output: Path,
        agent_slots: int = 3,
        check_slots: int = 1,
        timeout_seconds: float = 600,
    ):
        if type(agent_slots) is not int or not 1 <= agent_slots <= 3:
            raise ValueError("agent_slots must be between 1 and 3")
        if type(check_slots) is not int or check_slots != 1:
            raise ValueError("check_slots must be 1")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be positive and finite")
        if not callable(execute):
            raise ValueError("execute must be callable")
        self.jobs = list(jobs)
        by_id = {}
        for job in self.jobs:
            if (not isinstance(job, Job) or not isinstance(job.id, str) or not job.id
                    or job.kind not in ("agent", "check")
                    or type(job.priority) is not int
                    or not isinstance(job.deps, tuple)
                    or any(not isinstance(dep, str) for dep in job.deps)):
                raise ValueError("invalid job definition")
            if job.id in by_id:
                raise ValueError("job ids must be unique")
            by_id[job.id] = job
        for job in self.jobs:
            if any(dep not in by_id for dep in job.deps):
                raise ValueError("unknown dependency")
        # Kahn's algorithm avoids recursion limits for larger valid task graphs.
        remaining = {job.id: set(job.deps) for job in self.jobs}
        resolved = {key for key, deps in remaining.items() if not deps}
        visited = set()
        while resolved:
            visited.update(resolved)
            for key in resolved:
                remaining.pop(key)
            for deps in remaining.values():
                deps.difference_update(resolved)
            resolved = {key for key, deps in remaining.items() if not deps}
        if remaining:
            raise ValueError("dependencies must be acyclic")
        self.execute = execute
        self.output = Path(output)
        if self.output.suffix.lower() == ".json":
            self.state_path = self.output
            self.events_path = self.output.with_name(self.output.stem + ".events.json")
        else:
            self.state_path = self.output / "state.json"
            self.events_path = self.output / "events.json"
        self.agent_slots = agent_slots
        self.check_slots = check_slots
        self.timeout_seconds = float(timeout_seconds)
        self._has_run = False

    def run(self) -> dict:
        if self._has_run:
            raise RuntimeError("TaskQueue instances cannot be resumed or rerun")
        self._has_run = True
        start = time.monotonic()
        deadline = start + self.timeout_seconds
        events: list[dict] = []
        records = {
            job.id: {
                "id": job.id, "kind": job.kind, "deps": list(job.deps),
                "priority": job.priority, "status": "queued", "queued_at": 0.0,
                "ready_at": None, "dispatched_at": None, "started_at": None, "finished_at": None,
                "slot_id": None, "result": None, "error": None,
            } for job in self.jobs
        }
        for job in self.jobs:
            events.append({"sequence": len(events), "job_id": job.id,
                           "kind": job.kind, "status": "queued", "at": 0.0})
        free = {
            "agent": [f"agent-{i + 1}" for i in range(self.agent_slots)],
            "check": [f"check-{i + 1}" for i in range(self.check_slots)],
        }
        running: dict[Future, tuple[Job, str]] = {}
        peak = {"agent": 0, "check": 0}
        active = {"agent": 0, "check": 0}
        runtime: dict[str, dict] = {}
        runtime_lock = threading.Lock()
        stopping = threading.Event()

        def offset() -> float:
            return max(0.0, time.monotonic() - start)

        def transition(job: Job, state: str, at: float | None = None) -> None:
            stamp = offset() if at is None else at
            record = records[job.id]
            record["status"] = state
            field = {"ready": "ready_at", "running": "started_at"}.get(state)
            if state in _TERMINAL:
                field = "finished_at"
            if field is not None:
                record[field] = stamp
            event = {"sequence": len(events), "job_id": job.id,
                     "kind": job.kind, "status": state, "at": stamp}
            if record["slot_id"] is not None:
                event["slot_id"] = record["slot_id"]
            events.append(event)

        def sync_starts() -> None:
            with runtime_lock:
                starts = [(job, runtime.get(job.id, {}).get("started"))
                          for job, _ in running.values()]
            for job, began in starts:
                if began is not None and records[job.id]["started_at"] is None:
                    transition(job, "running", began - start)

        def report() -> dict:
            sync_starts()
            wall = offset()
            with runtime_lock:
                actual = {key: value.copy() for key, value in runtime.items()}
                actual_peak = peak.copy()
            agent_busy = 0.0
            for record in records.values():
                ready, began, ended = record["ready_at"], record["started_at"], record["finished_at"]
                record["dependency_wait_seconds"] = max(0.0, (ready if ready is not None else ended if ended is not None else wall) - record["queued_at"])
                record["ready_wait_seconds"] = None if ready is None else max(0.0, (began if began is not None else ended if ended is not None else wall) - ready)
                callback = actual.get(record["id"], {})
                callback_end = callback.get("ended")
                record["callback_finished_at"] = None if callback_end is None else callback_end - start
                record["busy_seconds"] = 0.0 if began is None else max(0.0, (callback_end - start if callback_end is not None else wall) - began)
                if record["kind"] == "agent":
                    agent_busy += record["busy_seconds"]
            states = [r["status"] for r in records.values()]
            status = ("completed" if all(s == "completed" for s in states)
                      else "timed_out" if "timed_out" in states
                      else "failed" if any(s in ("failed", "blocked_dependency") for s in states)
                      else "running")
            return {
                "status": status, "time_basis": "seconds since run start (monotonic)",
                "timeout_seconds": self.timeout_seconds,
                "agent_slots": self.agent_slots, "check_slots": self.check_slots,
                "tasks": records, "events": events,
                "metrics": {
                    "peak_running_agents": actual_peak["agent"], "peak_running_checks": actual_peak["check"],
                    "wall_seconds": wall, "sum_agent_busy_seconds": agent_busy,
                    "agent_slot_utilization": agent_busy / (self.agent_slots * wall) if wall else 0.0,
                },
                "limitations": [
                    "No automatic retries or resume.",
                    "Callbacks must honor the deadline and own subprocess cleanup; threads cannot kill arbitrary callbacks.",
                    "A timed-out running callback may still be executing after run returns.",
                ],
            }

        def persist() -> dict:
            value = report()
            # Worker starts/finishes can be observed later than another task's
            # event. Publish the actual monotonic timeline in sequence order.
            events.sort(key=lambda event: event["at"])
            for sequence, event in enumerate(events):
                event["sequence"] = sequence
            _dump(self.events_path, events)
            _dump(self.state_path, value)
            return value

        def invoke(job: Job) -> tuple[float | None, float, object, str | None]:
            with runtime_lock:
                began = time.monotonic()
                if stopping.is_set() or began >= deadline:
                    return None, began, None, "deadline reached before callback invocation"
                runtime[job.id] = {"started": began, "ended": None}
                active[job.kind] += 1
                peak[job.kind] = max(peak[job.kind], active[job.kind])
            result, error = None, None
            try:
                result = self.execute(job, deadline)
            except BaseException:
                # Never serialize exception text, argv, environment or traceback.
                error = "execute callback raised an exception"
            finally:
                with runtime_lock:
                    ended = time.monotonic()
                    runtime[job.id]["ended"] = ended
                    active[job.kind] -= 1
            return began, ended, result, error

        pool = ThreadPoolExecutor(max_workers=self.agent_slots + self.check_slots,
                                  thread_name_prefix="task-queue")
        try:
            persist()
            while True:
                sync_starts()
                # Collect completions first so newly unblocked jobs can use all
                # available slots in this same control-thread iteration.
                for future in list(running):
                    if not future.done():
                        continue
                    job, slot = running.pop(future)
                    free[job.kind].append(slot)
                    free[job.kind].sort()
                    began, ended, result, error = future.result()
                    record = records[job.id]
                    if began is not None and record["started_at"] is None:
                        transition(job, "running", began - start)
                    record["result"] = _safe_result(result)
                    record["error"] = error
                    if ended > deadline:
                        record["error"] = "execute callback exceeded deadline"
                        state = "timed_out"
                    elif error is not None or not isinstance(result, dict):
                        record["error"] = error or "execute callback returned an invalid result"
                        state = "failed"
                    else:
                        state = "completed" if result.get("status") == "completed" else "failed"
                        if state != "completed":
                            record["error"] = "execute callback did not complete successfully"
                    transition(job, state, max(0.0, ended - start))

                # Failure propagation is transitive before any new dispatch.
                changed = True
                while changed:
                    changed = False
                    for job in self.jobs:
                        record = records[job.id]
                        if record["status"] not in ("queued", "ready"):
                            continue
                        failures = [dep for dep in job.deps if records[dep]["status"] in _TERMINAL - {"completed"}]
                        if failures:
                            record["error"] = "dependency did not complete successfully"
                            record["blocked_by"] = failures
                            transition(job, "blocked_dependency")
                            changed = True

                if all(record["status"] in _TERMINAL for record in records.values()):
                    return persist()
                if time.monotonic() >= deadline:
                    stopping.set()
                    for future in running:
                        future.cancel()
                    sync_starts()
                    for job in self.jobs:
                        record = records[job.id]
                        if record["status"] not in _TERMINAL:
                            record["error"] = "queue deadline exceeded"
                            if record["status"] == "running":
                                record["execution_still_running"] = True
                            transition(job, "timed_out")
                    for future in running:
                        future.cancel()
                    return persist()

                for job in self.jobs:
                    if records[job.id]["status"] == "queued" and all(records[dep]["status"] == "completed" for dep in job.deps):
                        ready_at = max((records[dep]["finished_at"] for dep in job.deps), default=0.0)
                        transition(job, "ready", ready_at)
                eligible = sorted(
                    ((index, job) for index, job in enumerate(self.jobs) if records[job.id]["status"] == "ready" and records[job.id]["slot_id"] is None),
                    key=lambda item: (item[1].priority, item[0]),
                )
                for _, job in eligible:
                    if time.monotonic() >= deadline:
                        break
                    if not free[job.kind]:
                        continue
                    slot = free[job.kind].pop(0)
                    records[job.id]["slot_id"] = slot
                    records[job.id]["dispatched_at"] = offset()
                    future = pool.submit(invoke, job)
                    running[future] = (job, slot)
                persist()
                if running:
                    wait(tuple(running), timeout=max(0.0, deadline - time.monotonic()), return_when=FIRST_COMPLETED)
                # A valid acyclic graph either has runnable work or a running
                # predecessor. The next iteration handles deadline exhaustion.
        finally:
            stopping.set()
            pool.shutdown(wait=False, cancel_futures=True)
