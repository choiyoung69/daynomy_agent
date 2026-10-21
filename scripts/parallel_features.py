#!/usr/bin/env python3
"""Two independent sample implementers, one reviewer slot and a trusted merge gate.

This is a bounded local runner, not a daemon. Codex CLI is the initial backend;
agent definitions and orchestration are separate from that backend.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid

from agent_workflow import CliAgent, check_snapshot, digest, dump, permission_probe, validate_result
from sample_feature_gate import cases, run_gate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/representative"
CONFIG = ROOT / "agents/representative.json"
CONTRACT = ROOT / "spec/representative-sample.md"
OWNERS = {"news": "news.rs", "portfolio": "portfolio_calc.rs"}
EXPECTED_CASES = {c[0] for c in cases()} | {"news-live-db-update"}


def now():
    return datetime.now(timezone.utc).isoformat()


def tree(path):
    out = {}
    for p in sorted(Path(path).rglob("*")):
        if "target" in p.relative_to(path).parts:
            continue
        if p.is_symlink():
            raise ValueError("Symlink in candidate")
        if p.is_file():
            if p.stat().st_nlink != 1:
                raise ValueError("Hardlink in candidate")
            out[str(p.relative_to(path))] = digest(p)
    return out


def hashes(candidate):
    return {name: digest(Path(candidate) / "src" / name) for name in sorted(OWNERS.values())}


def validate_config(config):
    if config.get("backend") != "codex_cli":
        raise ValueError("Only the installed codex_cli backend is implemented")
    if type(config.get("max_model_calls")) is not int or config["max_model_calls"] not in (1, 2):
        raise ValueError("Model concurrency must be one or two")
    if type(config.get("max_rounds")) is not int or not 1 <= config["max_rounds"] <= 3:
        raise ValueError("Repair rounds must be between one and three")
    tasks = config.get("tasks", [])
    if len(tasks) != 2 or {t.get("name") for t in tasks} != set(OWNERS):
        raise ValueError("Exactly the two approved sample tasks are required")
    for task in tasks:
        if task.get("file") != OWNERS[task["name"]]:
            raise ValueError("Task ownership cannot overlap or expand")
    for definition in [*tasks, config["reviewer"]]:
        CliAgent(model=definition.get("model"), max_attempts=1)
    return deepcopy(config)


def valid_gate(gate, output, candidate, started):
    """Require fresh, complete real evidence for these exact source bytes."""
    path = Path(output) / "result.json"
    if path.is_symlink() or not path.is_file() or gate.get("report") != str(path):
        return False
    evidence = json.loads(path.read_text())
    results = evidence.get("results", [])
    commands = evidence.get("commands", [])
    return (gate == evidence and evidence.get("status") == "passed"
            and evidence.get("source_hashes") == hashes(candidate)
            and evidence.get("started_at", 0) >= started
            and evidence.get("finished_at", 0) >= evidence["started_at"]
            and path.stat().st_mtime >= started
            and len(results) == len(EXPECTED_CASES)
            and {r.get("case") for r in results} == EXPECTED_CASES
            and all(r.get("passed") is True and not r.get("skipped") for r in results)
            and {"format", "clippy", "build", "database-create"} <= {c.get("name") for c in commands}
            and all(c.get("exit_code") == 0 for c in commands))


class ParallelSample:
    def __init__(self, directory, *, config=None, agent=None, gate=run_gate,
                 probe=permission_probe, demo=False):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.config = validate_config(config if config is not None else json.loads(CONFIG.read_text()))
        self.agent, self.gate, self.probe = agent, gate, probe
        self.lock = threading.RLock()
        self.calls = threading.BoundedSemaphore(self.config["max_model_calls"])
        self.reviewer = threading.BoundedSemaphore(1)
        self.sessions = set()
        self.demo = demo
        trusted = [CONTRACT, CONFIG, ROOT / "AGENTS.md",
                   *(ROOT / "scripts" / name for name in (
                       "parallel_features.py", "agent_workflow.py", "sample_feature_gate.py",
                       "acceptance.py", "run_comparison.py", "workflow_gate.py", "local-db.sh"))]
        trusted += [p for p in BASE.rglob("*") if p.is_file() and "target" not in p.parts]
        trusted += list((ROOT / "app/src").glob("*.rs"))
        self.trusted = {str(p.relative_to(ROOT)): digest(p) for p in trusted}
        self.base_tree = tree(BASE)
        self.jobs = {t["name"]: {"name": t["name"], "file": t["file"], "status": "queued",
                                "round": 0, "agents": [], "measurements": []}
                     for t in self.config["tasks"]}
        self.state = {"status": "preparing", "started_at": now(), "config": self.config,
                      "demo": demo, "trusted": self.trusted, "tasks": self.jobs,
                      "events": [], "measurements": [], "integration": None}
        dump(self.directory / "config.json", self.config)
        self.save()

    def save(self):
        with self.lock:
            self.state["updated_at"] = now()
            dump(self.directory / "state.json", self.state)

    def event(self, task, stage, phase, **extra):
        with self.lock:
            event = {"at": now(), "task": task, "stage": stage, "phase": phase, **extra}
            self.state["events"].append(event)
            self.save()
            print(json.dumps(event, ensure_ascii=False), flush=True)

    def update(self, job, **values):
        with self.lock:
            job.update(values)
            if "directory" in job:
                dump(Path(job["directory"]) / "state.json", job)
            self.save()

    def timed(self, job, stage, operation):
        started, clock = now(), time.perf_counter()
        self.event(job["name"], stage, "started", round=job.get("round", 0))
        try:
            return operation()
        finally:
            measurement = {"stage": stage, "round": job.get("round", 0), "started_at": started,
                           "finished_at": now(), "seconds": round(time.perf_counter() - clock, 3)}
            with self.lock:
                job["measurements"].append(measurement)
                self.save()
            self.event(job["name"], stage, "finished", seconds=measurement["seconds"])

    def integrity(self, candidate=None, owner=None):
        check_snapshot(ROOT, self.trusted)
        if tree(BASE) != self.base_tree:
            raise ValueError("Baseline file list changed")
        if candidate is not None:
            actual = tree(candidate)
            if set(actual) != set(self.base_tree):
                raise ValueError("Candidate added or removed files")
            allowed = {"src/" + owner} if owner else {"src/" + f for f in OWNERS.values()}
            if any(actual[p] != sha for p, sha in self.base_tree.items() if p not in allowed):
                raise ValueError("Candidate changed another task or protected scaffold")

    def invoke(self, job, definition, role, workspace, prompt, output):
        self.event(job["name"], role, "queued")
        with (self.reviewer if role == "reviewer" else nullcontext()), self.calls:
            def execute():
                if self.agent:
                    return self.agent(definition, role, workspace, prompt, output)
                return CliAgent(model=definition.get("model"), max_attempts=1)(role, workspace, prompt, output)
            result, meta = self.timed(job, role, execute)
        validate_result(result, role)
        with self.lock:
            identity = meta["session_id"]
            if not identity or identity in self.sessions:
                raise ValueError("Each agent call must have a fresh session")
            self.sessions.add(identity)
            meta = {**meta, "agent_name": definition["name"]}
            job["agents"].append(meta)
            self.save()
        return result

    def implement_prompt(self, task, feedback):
        return (f"You are the independent {task['name']} implementation agent. Modify ONLY {task['file']} "
                "in cwd. It is your sole writable task file; another implementation runs concurrently. "
                "Keep signatures. Do not add files/tests, delegate, build, start servers, use DB/network or commit. "
                "The controller owns tests and shared code. Implement/repair your part of the unchanged sample "
                "contract; leave the other feature to its owner. Inspect relevant original Java as needed. "
                "Return implemented/needs_decision/blocked with summary, findings, questions. "
                "Do not claim tests passed. Report concisely in Korean.\nROOT=" + str(ROOT)
                + "\nCONTRACT:\n" + CONTRACT.read_text()
                + "\nPREVIOUS EVIDENCE:\n" + json.dumps(feedback, ensure_ascii=False))

    def review_prompt(self, task, candidate, gate):
        return (f"Independently review ONLY the change to {task['file']} for the {task['name']} task. "
                "Cwd contains the full frozen candidate; all tools are read-only. "
                "Read src/" + task["file"] + " and the referenced original Java/real gate evidence. "
                "Do not edit/build/start servers/use DB/network/commit/delegate. "
                "Approve only for this sample contract and real passed gate. "
                "findings means unresolved defects only: approve requires empty findings/questions; "
                "revise requires actionable source-line findings; questions require needs_decision. "
                "Report concisely in Korean.\nROOT=" + str(ROOT)
                + "\nCONTRACT:\n" + CONTRACT.read_text()
                + "\nGATE:\n" + json.dumps(gate, ensure_ascii=False))

    def task(self, task):
        job = self.jobs[task["name"]]
        directory = self.directory / task["name"]
        worker = None
        try:
            directory.mkdir()
            candidate = directory / "candidate"
            shutil.copytree(BASE, candidate, ignore=shutil.ignore_patterns("target"))
            worker = Path(tempfile.mkdtemp(prefix="daynomy-parallel-" + task["name"] + "-", dir="/private/tmp"))
            self.update(job, directory=str(directory), candidate=str(candidate), worker=str(worker), status="preparing")
            probes = [self.probe(worker, directory / "control", "implementer"),
                      self.probe(directory / "review-probe", directory / "control", "reviewer")]
            self.update(job, permission_probes=probes)
            if self.demo:
                stub = ("pub fn list(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n"
                        "pub fn detail(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n"
                        if task["name"] == "news" else
                        "pub fn calculate(_: &[u8], _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n")
                (candidate / "src" / task["file"]).write_text(stub)
            feedback = {}
            for turn in range(1, self.config["max_rounds"] + 1):
                self.integrity(candidate, task["file"])
                self.update(job, status="implementing", round=turn)
                shutil.copyfile(candidate / "src" / task["file"], worker / task["file"])
                round_dir = directory / f"round-{turn}"
                answer = self.invoke(job, task, "implementer", worker,
                                     self.implement_prompt(task, feedback), round_dir / "implementer")
                self.integrity(candidate, task["file"])
                if answer["status"] != "implemented":
                    self.update(job, status=answer["status"], result=answer)
                    return
                if {p.name for p in worker.iterdir()} != {task["file"]}:
                    raise ValueError("Worker modified unexpected paths")
                path = worker / task["file"]
                if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 524288:
                    raise ValueError("Worker source must be a bounded independent regular file")
                shutil.copyfile(path, candidate / "src" / task["file"])
                self.integrity(candidate, task["file"])
                self.update(job, status="verifying")
                gate_dir = round_dir / "gate"
                started = time.time()
                gate = self.timed(job, "verification", lambda: self.gate(candidate, gate_dir, directory))
                self.integrity(candidate, task["file"])
                self.update(job, gate=gate)
                if gate.get("status") == "blocked":
                    self.update(job, status="blocked", reason=gate.get("reason", "Gate unavailable"))
                    return
                if gate.get("status") != "passed":
                    # Compiler/test diagnostics go directly to implementation; no review token spent.
                    feedback = {"gate": gate}
                    self.update(job, status="repairing", feedback=feedback)
                    continue
                if not valid_gate(gate, gate_dir, candidate, started):
                    raise ValueError("Missing, stale or incomplete gate evidence")
                expected, report_hash = hashes(candidate), digest(gate_dir / "result.json")
                self.update(job, status="reviewing", source_hashes=expected)
                review = self.invoke(job, self.config["reviewer"], "reviewer", candidate,
                                     self.review_prompt(task, candidate, gate), round_dir / "reviewer")
                self.integrity(candidate, task["file"])
                if hashes(candidate) != expected or digest(gate_dir / "result.json") != report_hash:
                    raise ValueError("Reviewed source/evidence changed")
                self.update(job, review=review)
                if review["status"] == "approve":
                    self.update(job, status="completed", approved_hash=expected[task["file"]])
                    return
                if review["status"] in ("needs_decision", "blocked"):
                    self.update(job, status=review["status"])
                    return
                feedback = {"gate": gate, "review": review}
                self.update(job, status="repairing", feedback=feedback)
            self.update(job, status="failed", reason="Repair round limit")
        except Exception as exc:
            self.update(job, status="blocked", reason=type(exc).__name__ + ": " + str(exc)[:500])
        finally:
            if worker is not None:
                shutil.rmtree(worker)
            self.update(job, finished_at=now())
            self.event(task["name"], "task", "finished", status=job["status"])

    def integrate(self):
        if any(j["status"] != "completed" for j in self.jobs.values()):
            states = {j["status"] for j in self.jobs.values()}
            self.state["status"] = "needs_decision" if "needs_decision" in states else "blocked" if "blocked" in states else "failed"
            return
        self.integrity()
        candidate = self.directory / "integrated"
        shutil.copytree(BASE, candidate, ignore=shutil.ignore_patterns("target"))
        for task in self.config["tasks"]:
            job = self.jobs[task["name"]]
            source = Path(job["candidate"]) / "src" / task["file"]
            self.integrity(Path(job["candidate"]), task["file"])
            if digest(source) != job["approved_hash"]:
                raise ValueError("Approved task changed before integration")
            shutil.copyfile(source, candidate / "src" / task["file"])
        before = hashes(candidate)
        integration = {"name": "integration", "round": 0, "measurements": []}
        self.state["integration"] = integration
        output, started = self.directory / "integration-gate", time.time()
        gate = self.timed(integration, "verification", lambda: self.gate(candidate, output, self.directory))
        self.integrity(candidate)
        approved = {t["file"]: self.jobs[t["name"]]["approved_hash"] for t in self.config["tasks"]}
        if hashes(candidate) != before or before != approved or not valid_gate(gate, output, candidate, started):
            integration.update(gate=gate, status="failed")
            self.state["status"] = "blocked" if gate.get("status") == "blocked" else "failed"
            return
        patch = ""
        for name in sorted(OWNERS.values()):
            patch += "".join(difflib.unified_diff((BASE / "src" / name).read_text().splitlines(True),
                             (candidate / "src" / name).read_text().splitlines(True),
                             fromfile="a/experiments/representative/src/" + name,
                             tofile="b/experiments/representative/src/" + name))
        (self.directory / "candidate.patch").write_text(patch)
        integration.update(status="passed", gate=gate, source_hashes=before, candidate=str(candidate))
        self.state["status"] = "completed"

    def run(self):
        self.state["status"] = "running"
        self.save()
        try:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="sample") as pool:
                futures = [pool.submit(self.task, t) for t in self.config["tasks"]]
                for future in as_completed(futures):
                    future.result()
            self.integrate()
        except Exception as exc:
            self.state.update(status="blocked", reason=type(exc).__name__ + ": " + str(exc)[:500])
        finally:
            self.state["finished_at"] = now()
            self.save()
            print(json.dumps({"status": self.state["status"], "evidence": str(self.directory / "state.json")}), flush=True)
        return self.state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Start each owned module from 501 stubs")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--implementer-model", help="Explicit model for both implementation agents")
    parser.add_argument("--reviewer-model", help="Explicit model for reviewer sessions")
    parser.add_argument("--plan", action="store_true", help="Show config without model/DB calls")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.implementer_model:
        for task in config["tasks"]:
            task["model"] = args.implementer_model
    if args.reviewer_model:
        config["reviewer"]["model"] = args.reviewer_model
    validate_config(config)
    if args.plan:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    directory = ROOT / ".local/parallel-features" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    workflow = ParallelSample(directory, config=config, demo=args.demo)
    state = workflow.run()
    return 0 if state["status"] == "completed" else 3 if state["status"] == "needs_decision" else 2


if __name__ == "__main__":
    raise SystemExit(main())
