#!/usr/bin/env python3
"""Measured sample using the existing real CLI adapter and a separate local gate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid

from agent_workflow import CliAgent, digest, dump, permission_probe, snapshot_files, check_snapshot

ROOT = Path(__file__).resolve().parents[1]
FILES = {"news.rs", "portfolio_calc.rs"}
BASE = ROOT / "experiments/representative"
CONTRACT = ROOT / "spec/representative-sample.md"


def now():
    return datetime.now(timezone.utc).isoformat()


def sources(path):
    return {name: digest(Path(path) / name) for name in sorted(FILES)}


def collect(worker, candidate):
    if {p.name for p in worker.iterdir()} != FILES:
        raise ValueError("Unexpected worker source paths")
    for name in FILES:
        p = worker / name
        if p.is_symlink() or not p.is_file() or p.stat().st_nlink != 1 or p.stat().st_size > 524288:
            raise ValueError("Invalid worker source file")
    for name in FILES:
        shutil.copyfile(worker / name, candidate / "src" / name)


class Sample:
    def __init__(self, directory, resume=False):
        self.directory = directory.resolve()
        if resume:
            self.state = json.loads((directory / "state.json").read_text())
        else:
            directory.mkdir(parents=True, exist_ok=False)
            candidate = directory / "candidate"
            shutil.copytree(BASE, candidate, ignore=shutil.ignore_patterns("target"))
            worker = Path(tempfile.mkdtemp(prefix="daynomy-sample-", dir="/private/tmp"))
            trusted = {p.relative_to(ROOT) for p in BASE.rglob("*")
                       if p.is_file() and "target" not in p.parts and p.name not in FILES}
            trusted |= {CONTRACT.relative_to(ROOT), Path("scripts/agent_workflow.py")}
            original = {str(p.relative_to(ROOT)): digest(p) for p in (ROOT / "app/src").glob("*.rs")}
            self.state = {"status": "preparing", "started_at": now(), "candidate": str(candidate),
                          "worker": str(worker), "round": 1, "agents": [], "measurements": [],
                          "trusted": snapshot_files(ROOT, sorted(trusted)), "original_app": original}
            for name in FILES:
                shutil.copyfile(BASE / "src" / name, worker / name)
            self.state["permission_probes"] = [permission_probe(worker, directory / "control", "implementer"),
                permission_probe(directory / "review-probe", directory / "control", "reviewer")]
            self.save()

    @property
    def candidate(self):
        return Path(self.state["candidate"])

    def save(self, **updates):
        self.state.update(updates)
        self.state["updated_at"] = now()
        dump(self.directory / "state.json", self.state)

    def integrity(self):
        check_snapshot(ROOT, self.state["trusted"])
        check_snapshot(ROOT, self.state["original_app"])
        for relative, sha in self.state["trusted"].items():
            if relative.startswith("experiments/representative/"):
                p = self.candidate / Path(relative).relative_to("experiments/representative")
                if p.is_symlink() or digest(p) != sha:
                    raise ValueError("Candidate scaffold changed")

    def timed(self, stage, operation):
        started, clock = now(), time.perf_counter()
        try:
            return operation()
        finally:
            self.state["measurements"].append({"stage": stage, "round": self.state["round"],
                "started_at": started, "finished_at": now(), "seconds": round(time.perf_counter()-clock, 3)})
            self.save()

    def implement(self):
        self.integrity()
        worker = Path(self.state["worker"])
        if self.state["round"] > 1:
            for p in worker.iterdir():
                p.unlink()
            for name in FILES:
                shutil.copyfile(self.candidate / "src" / name, worker / name)
        prompt = ("Implement the three sample Rust endpoints defined below. Your cwd contains only "
                  "news.rs and portfolio_calc.rs; modify only these files, without new files, tests, "
                  "builds, databases, network, commits or delegation. The controller owns HTTP/DB and tests. "
                  "Read the referenced original Java when needed. Start from the provided signatures. "
                  "Return JSON status implemented/needs_decision/blocked, concise summary, findings and questions arrays. "
                  "Do not assert tests passed. Report in Korean.\n\n" + CONTRACT.read_text()
                  + "\nROOT=" + str(ROOT) + "\nPREVIOUS EVIDENCE="
                  + json.dumps(self.state.get("feedback", {}), ensure_ascii=False))
        self.save(status="implementing")
        result, meta = self.timed("implementation", lambda: CliAgent()("implementer", worker, prompt,
            self.directory / f"round-{self.state['round']}" / "implementer"))
        self.state["agents"].append(meta)
        self.integrity()
        if result["status"] != "implemented":
            self.save(status=result["status"], result=result)
            return
        collect(worker, self.candidate)
        self.save(status="implemented", implementation=result, source_hashes=sources(self.candidate / "src"))

    def verify(self):
        from sample_feature_gate import run_gate
        self.integrity()
        criteria = {Path("scripts/sample_features.py"), Path("scripts/sample_feature_gate.py"),
                    Path("spec/representative-sample.md")}
        self.state["verification_criteria"] = snapshot_files(ROOT, sorted(criteria))
        self.save(status="verifying")
        gate = self.timed("verification", lambda: run_gate(self.candidate, self.directory /
            f"round-{self.state['round']}" / "gate", self.directory))
        self.integrity()
        check_snapshot(ROOT, self.state["verification_criteria"])
        self.save(status="verified" if gate["status"] != "blocked" else "blocked", gate=gate,
                  source_hashes=sources(self.candidate / "src"))

    def review(self):
        from sample_feature_gate import cases
        self.integrity()
        check_snapshot(ROOT, self.state["verification_criteria"])
        expected = self.state["source_hashes"]
        if sources(self.candidate / "src") != expected:
            raise ValueError("Source changed after gate")
        prompt = ("Independently review the sample code and real gate evidence against the contract below. "
                  "You are read-only. Do not edit, run builds/DB/server, escalate, commit or delegate. "
                  "Inspect news.rs and portfolio_calc.rs in cwd. Read Java references if needed. "
                  "No approval if gate fails/missing evidence or questions remain. "
                  "Return JSON status approve/revise/needs_decision/blocked, summary, findings and questions arrays. "
                  "approve requires empty findings/questions. revise requires actionable source-line findings. "
                  "Do not invent scope beyond the sample. Report in Korean.\n" + CONTRACT.read_text()
                  + "\nROOT=" + str(ROOT) + "\nGATE=" + json.dumps(self.state["gate"], ensure_ascii=False))
        self.save(status="reviewing")
        result, meta = self.timed("review", lambda: CliAgent()("reviewer", self.candidate / "src", prompt,
            self.directory / f"round-{self.state['round']}" / "reviewer"))
        if meta["session_id"] in {a["session_id"] for a in self.state["agents"]}:
            raise ValueError("Reused agent identity")
        self.state["agents"].append(meta)
        self.integrity()
        check_snapshot(ROOT, self.state["verification_criteria"])
        if sources(self.candidate / "src") != expected:
            raise ValueError("Source changed during review")
        gate = self.state["gate"]
        report = Path(gate.get("report", ""))
        evidence = json.loads(report.read_text()) if report.is_file() and not report.is_symlink() else {}
        expected_cases = {case[0] for case in cases()} | {"news-live-db-update"}
        results = evidence.get("results", [])
        passed = (gate.get("status") == "passed" and evidence.get("status") == "passed"
                  and len(results) == len(expected_cases)
                  and all(c.get("passed") is True and not c.get("skipped") for c in results)
                  and {c.get("case") for c in results} == expected_cases
                  and report.stat().st_mtime >= gate["started_at"]
                  and evidence.get("source_hashes") == expected)
        if result["status"] == "approve" and passed:
            self.save(status="completed", review=result, finished_at=now())
        elif result["status"] in ("blocked", "needs_decision"):
            self.save(status=result["status"], review=result, finished_at=now())
        else:
            self.save(status="repairing", feedback={"gate": gate, "review": result})

    def run(self, stage):
        try:
            if stage == "implement":
                self.implement()
                return
            for _ in range(3):
                if self.state["status"] in ("preparing", "repairing"):
                    if self.state["status"] == "repairing":
                        self.state["round"] += 1
                        if self.state["round"] > 3:
                            self.save(status="failed", reason="Repair limit", finished_at=now())
                            break
                    self.implement()
                if self.state["status"] == "implemented":
                    self.verify()
                if self.state["status"] == "verified":
                    self.review()
                if self.state["status"] != "repairing":
                    break
            else:
                if self.state["status"] == "repairing":
                    self.save(status="failed",reason="Repair limit",finished_at=now())
        except Exception as exc:
            self.save(status="blocked", reason=type(exc).__name__+": "+str(exc)[:500], finished_at=now())
        finally:
            if self.state["status"] in ("blocked", "failed", "needs_decision") and not self.state.get("finished_at"):
                self.save(finished_at=now())
            print(json.dumps({"status": self.state["status"], "evidence": str(self.directory / "state.json")},
                             ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["implement", "all"], default="all")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--from-run", type=Path, help="New bounded run seeded from a preserved failed run")
    args = parser.parse_args()
    directory = args.resume or ROOT / ".local/feature-samples" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8])
    sample = Sample(directory, resume=bool(args.resume))
    if args.from_run:
        if args.resume:
            parser.error("--from-run starts a new run; cannot combine with --resume")
        parent=json.loads((args.from_run/"state.json").read_text())
        source=Path(parent["candidate"])/"src"
        for name in FILES:
            original=source/name
            if original.is_symlink() or not original.is_file() or original.stat().st_nlink!=1:
                raise ValueError("Invalid parent source")
            if digest(original)!=parent["source_hashes"][name]:
                raise ValueError("Parent source changed since its gate")
            shutil.copyfile(original, sample.candidate/"src"/name)
            shutil.copyfile(original, Path(sample.state["worker"])/name)
        sample.save(parent_run=str(args.from_run.resolve()),feedback={"gate":parent.get("gate"),
            "review":parent.get("feedback",{}).get("review",parent.get("review")),
            "parent_status":parent.get("status"),
            "note":"Preserve parent evidence; repair concrete findings against the current unchanged contract and current regression gate."})
    sample.run(args.stage)
    return 0 if sample.state["status"] in ("implemented", "completed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
