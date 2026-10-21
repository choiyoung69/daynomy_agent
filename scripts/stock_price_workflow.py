#!/usr/bin/env python3
"""Independent test author -> implementation -> real tests -> read-only review."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from agent_workflow import CliAgent, check_snapshot, clean_env, digest, dump, permission_probe, stop_group
from stock_price_gate import cases, run_gate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/stock-price"
SPEC = ROOT / "spec/stock-price.md"
CONFIG = ROOT / "agents/stock-price.json"
MODULE = "src/stock_price.rs"
TEST = "tests/stock_price_contract.rs"
TARGET = ROOT / ".local/stock-price-target"
ORIGINAL = ROOT / "reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy"
MUTANTS = ("wrong_currency", "wrong_date", "zero_price", "invent_missing")


def now():
    return datetime.now(timezone.utc).isoformat()


def file_set(path):
    result = {}
    for p in Path(path).rglob("*"):
        if "target" in p.relative_to(path).parts:
            continue
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink != 1):
            raise ValueError("Only independent regular files are accepted")
        if p.is_file():
            result[str(p.relative_to(path))] = digest(p)
    return result


def test_summary(text):
    match = re.search(r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out", text)
    if not match:
        raise ValueError("Missing actual Rust test summary")
    return dict(zip(("status", "passed", "failed", "ignored", "measured", "filtered"),
                    [match[1], *(int(match[n]) for n in range(2, 7))]))


def validate_test_source(text):
    if not text.startswith("#![forbid(unsafe_code)]"):
        raise ValueError("Independent test crate must forbid unsafe")
    if re.search(r"#\s*\[\s*ignore\b", text):
        raise ValueError("Ignored tests are forbidden")
    paths = re.findall(r'#\s*\[\s*path\s*=\s*"([^"]+)"\s*\]', text)
    if paths != ["../src/stock_price.rs"]:
        raise ValueError("Test module path must reference only the candidate module")
    # Defense in depth for common direct forms, not a complete Rust static analyzer.
    if re.search(r"\bunsafe\b|std\s*::\s*(?:fs|net|process|env)\b|\b(?:include|include_str|include_bytes|env|option_env)\s*!", text):
        raise ValueError("Independent tests must be pure assertions without process/file/network/env I/O")


def mutation(source, name):
    if source.count("pub fn latest(") != 1:
        raise ValueError("Cannot inject a controlled mutation into the public function")
    changed = source.replace("pub fn latest(", "fn unmutated_latest(", 1)
    action = {
        "wrong_currency": 'if status == 200 { body["currency"] = serde_json::json!("KRW"); }',
        "wrong_date": 'if status == 200 { body["baseDate"] = serde_json::json!("1900-01-01"); }',
        "zero_price": 'if status == 200 { body["closePrice"] = serde_json::json!(0); }',
        "invent_missing": 'if status == 404 { return (200, serde_json::json!({})); }',
    }[name]
    return changed + ('\npub fn latest(id: &str, data: &serde_json::Value) -> (u16, serde_json::Value) {\n'
                      'let (status, mut body) = unmutated_latest(id, data);\n' + action +
                      '\nlet _ = &mut body; (status, body)\n}\n')


def valid_http(result, output, candidate, started, *, target=None):
    path = output / "result.json"
    expected = {c[0] for c in cases()} | {"latest-live-db-insert"}
    if not path.is_file() or path.is_symlink() or result.get("report") != str(path):
        return False
    actual = json.loads(path.read_text())
    checks = actual.get("results", [])
    commands = actual.get("commands", [])
    return (actual == result and actual.get("status") == "passed"
            and actual.get("source_hashes") == {"stock_price.rs": digest(candidate / MODULE)}
            and actual.get("started_at", 0) >= started and path.stat().st_mtime >= started
            and len(checks) == len(expected) and {r.get("case") for r in checks} == expected
            and all(r.get("passed") is True and r.get("database_unchanged") is True for r in checks)
            and {"database-create", "spring-startup", "rust-startup", "spring-shutdown", "rust-shutdown"}
                <= {c.get("name") for c in commands}
            and all(c.get("exit_code") == 0 for c in commands)
            and actual.get("binary_sha256") == digest((Path(target) if target is not None else TARGET) / "debug/daynomy-stock-price"))


class StockWorkflow:
    def __init__(self, directory, config=None, parent=None, reuse_implementation=False):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.candidate = self.directory / "candidate"
        shutil.copytree(BASE, self.candidate, ignore=shutil.ignore_patterns("target"))
        (self.candidate / MODULE).write_text('pub fn latest(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n')
        (self.candidate / TEST).unlink(missing_ok=True)
        self.config = config or json.loads(CONFIG.read_text())
        if self.config["backend"] not in ("codex_cli", "desktop_bridge") or not 1 <= self.config["max_rounds"] <= 3:
            raise ValueError("Unsupported workflow configuration")
        for role in ("test_author", "implementer", "reviewer"):
            CliAgent(model=self.config[role]["model"], max_attempts=1)
            if self.config["backend"] == "desktop_bridge" and self.config[role]["model"] is not None:
                raise ValueError("Desktop bridge inherits app models; explicit model overrides require the CLI backend")
        self.frozen = {p: sha for p, sha in file_set(self.candidate).items() if p not in (MODULE, TEST)}
        criteria = [SPEC, CONFIG, ROOT / "AGENTS.md", *(ROOT / "scripts" / name for name in (
            "stock_price_workflow.py", "stock_price_gate.py", "agent_workflow.py", "sample_feature_gate.py",
            "readonly_runner.py", "run_comparison.py", "workflow_gate.py", "acceptance.py", "local-db.sh"))]
        criteria += [p for p in BASE.rglob("*") if p.is_file() and "target" not in p.parts]
        criteria += list((ROOT / "app/src").glob("*.rs"))
        self.trusted = {str(p.relative_to(ROOT)): digest(p) for p in criteria}
        refs = ["asset/service/StockPriceService.java", "asset/dto/StockPriceResponse.java",
                "asset/domain/StockMarket.java", "asset/exception/AssetErrorCode.java",
                "common/response/ErrorResponse.java"]
        bundle = "\n\n".join("SOURCE " + p + "\n" + (ORIGINAL / p).read_text() for p in refs)
        asset = (ORIGINAL / "asset/domain/Asset.java").read_text()
        bundle += "\nSOURCE Asset.getCurrency\n" + asset[asset.index("  public String getCurrency()"):asset.index("  public void recordPriceHistoryBackfill")]
        handler = (ORIGINAL / "common/exception/GlobalExceptionHandler.java").read_text()
        bundle += "\nSOURCE GlobalExceptionHandler type mismatch\n" + handler[handler.index("  @ExceptionHandler(MethodArgumentTypeMismatchException.class)"):handler.index("  @ExceptionHandler(Exception.class)")]
        self.bundle = bundle
        self.state = {"status": "preparing", "started_at": now(), "candidate": str(self.candidate),
                      "config": self.config, "agents": [], "measurements": [], "commands": [],
                      "trusted": self.trusted, "round": 0}
        if parent:
            parent = Path(parent).resolve()
            previous = json.loads((parent / "state.json").read_text())
            test = Path(previous["candidate"]) / TEST
            if test.is_symlink() or not test.is_file() or test.stat().st_nlink != 1 or digest(test) != previous.get("test_sha256"):
                raise ValueError("Parent independent tests changed")
            if previous.get("red_control", {}).get("summary", {}).get("failed", 0) < 1:
                raise ValueError("Parent tests lack actual red-control evidence")
            validate_test_source(test.read_text())
            (self.candidate / TEST).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(test, self.candidate / TEST)
            self.state.update(parent_run=str(parent), inherited_test_author={
                "test_sha256": digest(test), "agents": previous.get("inherited_test_author", {}).get("agents") or [a for a in previous.get("agents", []) if a["role"] == "test_author"],
                "note": "Reuse unchanged independent tests; rerun red control with current frozen criteria."})
            if reuse_implementation:
                source = Path(previous["candidate"]) / MODULE
                if (source.is_symlink() or not source.is_file() or source.stat().st_nlink != 1
                        or digest(source) != previous.get("http", {}).get("source_hashes", {}).get("stock_price.rs")
                        or previous.get("unit", {}).get("passed") is not True):
                    raise ValueError("Parent implementation lacks unchanged source and actual unit evidence")
                seed = self.directory / "implementation-seed.rs"
                shutil.copyfile(source, seed)
                self.state["inherited_implementation"] = {"source": str(seed), "sha256": digest(seed),
                    "agents": [a for a in previous.get("agents", []) if a["role"] == "implementer"],
                    "note": "Unapproved code reused only as input; all checks and a fresh review are still required."}
        (self.directory / "reference-excerpts.txt").write_text(bundle)
        self.env = clean_env()
        self.env.update(CARGO_HOME=str(ROOT / ".local/cargo"), CARGO_NET_OFFLINE="true", CARGO_TARGET_DIR=str(self.directory / "target"))
        self.save()

    def save(self, **values):
        self.state.update(values)
        self.state["updated_at"] = now()
        dump(self.directory / "state.json", self.state)

    def integrity(self):
        check_snapshot(ROOT, self.trusted)
        actual = file_set(self.candidate)
        if set(actual) - {MODULE, TEST} != set(self.frozen):
            raise ValueError("Candidate file list changed")
        if any(actual.get(p) != sha for p, sha in self.frozen.items()):
            raise ValueError("Protected scaffold changed")
        if self.state.get("test_sha256") and digest(self.candidate / TEST) != self.state["test_sha256"]:
            raise ValueError("Frozen independent tests changed")

    def timed(self, stage, operation):
        started, clock = now(), time.perf_counter()
        print(json.dumps({"stage": stage, "phase": "started", "at": started}), flush=True)
        try:
            return operation()
        finally:
            m = {"stage": stage, "started_at": started, "finished_at": now(),
                 "seconds": round(time.perf_counter() - clock, 3)}
            self.state["measurements"].append(m)
            self.save()
            print(json.dumps({"stage": stage, "phase": "finished", "seconds": m["seconds"]}), flush=True)

    def command(self, name, command, output, *, allow_failure=False, env_override=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w") as log:
            p = subprocess.Popen(command, cwd=self.candidate, env=env_override or self.env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True, text=True)
            try:
                p.wait(timeout=240)
            except subprocess.TimeoutExpired:
                stop_group(p)
                raise RuntimeError(name + " timed out") from None
        self.state["commands"].append({"name": name, "exit_code": p.returncode, "log": str(output)})
        self.save()
        if p.returncode and not allow_failure:
            raise RuntimeError(name + " failed; evidence=" + str(output))
        return p.returncode, output.read_text()

    def invoke(self, role, prompt, output, filename=None):
        self.integrity()
        worker = Path(tempfile.mkdtemp(prefix="daynomy-price-" + role + "-", dir="/private/tmp")) if filename else self.candidate
        before = file_set(self.candidate)
        try:
            if filename:
                source = self.candidate / (TEST if role == "test_author" else MODULE)
                (worker / filename).write_text(source.read_text() if source.exists() else "")
            probe = (permission_probe(worker, output / "control", role) if self.config["backend"] == "codex_cli"
                     else {"role": role, "backend": "desktop_bridge", "native_tool_sandbox": False,
                           "enforcement": "Role instructions plus controller artifact allowlist and candidate/test hashes"})
            self.state.setdefault("permission_probes", []).append(probe)
            self.save(status=role)
            if self.config["backend"] == "codex_cli":
                operation = lambda: CliAgent(model=self.config[role]["model"], max_attempts=1)(role, worker, prompt, output / "agent")
            else:
                operation = lambda: self.desktop_exchange(role, worker, prompt, output)
            answer, meta = self.timed(role, operation)
            if meta["session_id"] in {a["session_id"] for a in self.state["agents"]}:
                raise ValueError("Reused agent session")
            self.state["agents"].append({**meta, "name": self.config[role]["name"]})
            self.integrity()
            if file_set(self.candidate) != before:
                raise ValueError("Agent modified candidate outside its writable worker")
            if filename:
                path = worker / filename
                if {p.name for p in worker.iterdir()} != {filename} or path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 128000:
                    raise ValueError("Invalid agent artifact")
                if answer["status"] in ("tests_written", "implemented"):
                    target = self.candidate / (TEST if role == "test_author" else MODULE)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
            self.save()
            return answer
        finally:
            if filename:
                shutil.rmtree(worker)

    def desktop_exchange(self, role, worker, prompt, output):
        """Explicit bridge, dispatched by the active desktop conversation, not a daemon.

        Desktop subagents inherit app permissions; native CLI role profiles do
        not constrain their tools. Artifact and evidence integrity still apply.
        """
        from agent_workflow import validate_result
        output.mkdir(parents=True, exist_ok=True)
        request = {"request_id": uuid.uuid4().hex, "role": role, "workspace": str(worker),
                   "prompt": prompt, "response": str(output / "response.json")}
        dump(output / "request.json", request)
        print(json.dumps({"stage": role, "phase": "desktop_agent_required", "request": str(output / "request.json")}), flush=True)
        deadline = time.monotonic() + 240
        while not (output / "response.json").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Desktop agent dispatch time limit")
            time.sleep(.2)
        path = output / "response.json"
        if path.is_symlink() or path.stat().st_nlink != 1:
            raise ValueError("Invalid desktop response artifact")
        reply = json.loads(path.read_text())
        if reply.get("request_id") != request["request_id"] or not isinstance(reply.get("agent_id"), str) or not reply["agent_id"].startswith("/root/"):
            raise ValueError("Desktop response does not identify its actual dispatched subagent")
        answer = validate_result(reply["result"], role)
        return answer, {"session_id": "desktop:" + reply["agent_id"], "role": role,
                        "backend": "desktop_bridge", "request": str(output / "request.json"),
                        "result": str(path), "dispatcher": "active conversation Codex",
                        "requested_model": self.config[role]["model"], "model_selection": "desktop_inherited"}

    def compile_tests(self, candidate, output):
        # Cargo metadata paths for identical package names can share outputs.
        # A mutant must never overwrite another mutant or the actual server.
        target = Path(self.env["CARGO_TARGET_DIR"]) if candidate == self.candidate else candidate / "target"
        build_env = {**self.env, "CARGO_TARGET_DIR": str(target)}
        code, text = self.command("compile-tests", ["cargo", "test", "--locked", "--manifest-path",
            str(candidate / "Cargo.toml"), "--test", "stock_price_contract", "--no-run", "--message-format=json"], output / "compile-tests.log", env_override=build_env)
        binaries = []
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("reason") == "compiler-artifact" and event.get("target", {}).get("name") == "stock_price_contract" and event.get("executable"):
                binaries.append(event["executable"])
        if len(binaries) != 1:
            raise ValueError("Missing unique compiled independent test executable")
        if not Path(binaries[0]).resolve().is_relative_to(target.resolve()):
            raise ValueError("Test executable escaped its isolated target directory")
        command = [sys.executable, str(ROOT / "scripts/readonly_runner.py"), binaries[0]]
        _, listing = self.command("list-tests", [*command, "--list", "--format", "terse"], output / "test-list.log")
        names = [line.removesuffix(": test") for line in listing.splitlines() if line.endswith(": test")]
        if not 8 <= len(names) <= 40 or len(names) != len(set(names)):
            raise ValueError("Expected 8-40 real independent tests")
        _, ignored = self.command("list-ignored", [*command, "--list", "--ignored", "--format", "terse"], output / "ignored.log")
        if any(line.endswith(": test") for line in ignored.splitlines()):
            raise ValueError("Ignored independent tests are forbidden")
        return command, names

    def execute_tests(self, candidate, output):
        command, names = self.compile_tests(candidate, output)
        code, text = self.command("run-tests", [*command, "--test-threads=1"], output / "tests.log", allow_failure=True)
        summary = test_summary(text)
        if summary["ignored"] or summary["filtered"] or summary["passed"] + summary["failed"] != len(names):
            raise ValueError("Incomplete independent test execution")
        return {"passed": code == 0 and summary["status"] == "ok" and summary["failed"] == 0,
                "summary": summary, "names": names, "log": str(output / "tests.log"), "executable": command[-1]}

    def prompt(self, instruction, evidence=None):
        return (instruction + "\nUse only the contract and bounded original excerpts below. "
                "Do not inspect unrelated directories, build, run shell tests, start DB/server, commit or delegate. "
                "No network. The controller runs real checks. Do not claim tests passed. "
                "Report concise Korean with status/summary/findings/questions.\nCONTRACT:\n" + SPEC.read_text()
                + "\nORIGINAL EXCERPTS:\n" + self.bundle + "\nEVIDENCE:\n" + json.dumps(evidence or {}, ensure_ascii=False))

    def run(self):
        try:
            author_instruction = (
                "Write ONLY stock_price_contract.rs in cwd. You cannot see the feature implementation; "
                "derive expected values from the contract/original. Begin with #![forbid(unsafe_code)]. "
                "Include #[path = \"../src/stock_price.rs\"] mod stock_price; use latest(id,&data). "
                "At least8 independent #[test] functions with actual asserts. Use only serde_json/std. "
                "No unsafe/ignore/skip, file/network/process I/O or non-determinism. "
                "Exact decimal cases should use serde_json::from_str with arbitrary_precision. "
                "Return tests_written when the file is ready.")
            author_feedback = {}
            author_rounds = (0,) if self.state.get("inherited_test_author") else range(1, self.config["max_rounds"] + 1)
            for author_round in author_rounds:
                directory = self.directory / f"test-author-{author_round}"
                if author_round:
                    answer = self.invoke("test_author", self.prompt(author_instruction, author_feedback),
                                         directory, "stock_price_contract.rs")
                    if answer["status"] != "tests_written":
                        self.save(status=answer["status"], result=answer)
                        return
                try:
                    validate_test_source((self.candidate / TEST).read_text())
                    red = self.timed("red-control", lambda: self.execute_tests(self.candidate, directory / "red-control"))
                    if red["passed"]:
                        raise ValueError("Independent tests did not reject the unimplemented endpoint")
                except (RuntimeError, ValueError) as exc:
                    author_feedback = {"test_artifact_problem": str(exc), "logs": str(directory)}
                    self.save(test_author_feedback=author_feedback)
                    continue
                self.save(red_control=red, test_sha256=digest(self.candidate / TEST))
                break
            else:
                self.save(status="failed", reason="Test-author repair round limit")
                return
            feedback = {}
            for turn in range(1, self.config["max_rounds"] + 1):
                self.save(round=turn)
                round_dir = self.directory / f"round-{turn}"
                if turn == 1 and self.state.get("inherited_implementation"):
                    seed = self.state["inherited_implementation"]
                    if digest(seed["source"]) != seed["sha256"]:
                        raise ValueError("Implementation seed changed")
                    shutil.copyfile(seed["source"], self.candidate / MODULE)
                    self.save(status="verifying_inherited_implementation")
                    answer = {"status": "implemented"}
                else:
                    answer = self.invoke("implementer", self.prompt(
                    "Implement/repair ONLY ./stock_price.rs in cwd. The cwd IS the source workspace: "
                    "the existing stock_price.rs is directly here. DO NOT create or use a src/ subdirectory. "
                    "References to src/stock_price.rs in the contract mean the controller's logical destination, "
                    "NOT your cwd-relative path. Keep pub fn latest(id:&str,data:&Value)->(u16,Value). "
                    "Frozen tests and HTTP/DB scaffold cannot be modified. Use serde_json and std only. "
                    "Read the contract precisely; this is a read-only lookup, not a price feed. Return implemented.", feedback),
                        round_dir / "implementation", "stock_price.rs")
                if answer["status"] != "implemented":
                    self.save(status=answer["status"], result=answer)
                    return
                try:
                    self.command("format", ["rustfmt", "--edition", "2024", str(self.candidate / MODULE)], round_dir / "format.log")
                    self.command("clippy", ["cargo", "clippy", "--locked", "--manifest-path", str(self.candidate / "Cargo.toml"), "--all-targets", "--", "-D", "warnings"], round_dir / "clippy.log")
                    unit = self.timed("independent-tests", lambda: self.execute_tests(self.candidate, round_dir / "unit"))
                except RuntimeError as exc:
                    feedback = {"failure": str(exc), "logs": str(round_dir)}
                    self.save(feedback=feedback)
                    continue
                self.integrity()
                self.save(unit=unit)
                if not unit["passed"]:
                    feedback = {"independent_tests": unit}
                    self.save(feedback=feedback)
                    continue
                mutations = []
                for name in MUTANTS:
                    clone = round_dir / "mutations" / name
                    shutil.copytree(self.candidate, clone)
                    (clone / MODULE).write_text(mutation((self.candidate / MODULE).read_text(), name))
                    outcome = self.timed("mutation-" + name, lambda: self.execute_tests(clone, clone / "evidence"))
                    mutations.append({"name": name, "detected": not outcome["passed"] and outcome["summary"]["failed"] > 0, "tests": outcome})
                self.save(mutations=mutations)
                if not all(m["detected"] for m in mutations):
                    raise ValueError("Independent tests missed a seeded defect; test criteria need review")
                # Rebuild the real server only in this run's original target.
                self.command("build", ["cargo", "build", "--locked", "--manifest-path", str(self.candidate / "Cargo.toml")], round_dir / "build.log")
                self.integrity()
                expected = {MODULE: digest(self.candidate / MODULE), TEST: digest(self.candidate / TEST)}
                output, started = round_dir / "http", time.time()
                http = self.timed("real-http-db", lambda: run_gate(self.candidate, output, self.directory, target=self.env["CARGO_TARGET_DIR"]))
                self.save(http=http)
                if http["status"] == "blocked":
                    self.save(status="blocked", reason=http.get("reason"))
                    return
                if http["status"] != "passed":
                    feedback = {"http": http}
                    self.save(feedback=feedback)
                    continue
                if not valid_http(http, output, self.candidate, started, target=self.env["CARGO_TARGET_DIR"]):
                    raise ValueError("Missing/stale/incomplete real evidence")
                report_hash = digest(output / "result.json")
                review = self.invoke("reviewer", self.prompt(
                    "Independently review src/stock_price.rs and tests/stock_price_contract.rs in cwd. "
                    "Read the implementation, test expectations/coverage and actual evidence paths. Read-only tools. "
                    "Approve only when contract, independent tests, all4 seeded defects detected and realHTTP pass. "
                    "Return approve with empty findings/questions; revise with actionable code-line defects; "
                    "needs_decision for unresolved policy or incorrect test criterion. "
                    "Findings contain unresolved defects only, never positive observations.",
                    {"unit": unit, "mutations": mutations, "http": http, "source_hashes": expected}), round_dir / "review")
                self.integrity()
                if (expected != {MODULE: digest(self.candidate / MODULE), TEST: digest(self.candidate / TEST)}
                        or digest(output / "result.json") != report_hash
                        or not valid_http(http, output, self.candidate, started, target=self.env["CARGO_TARGET_DIR"])):
                    raise ValueError("Reviewed source, binary or evidence changed")
                self.save(review=review)
                if review["status"] == "approve":
                    self.save(status="completed", approved_hashes=expected)
                    return
                if review["status"] in ("blocked", "needs_decision"):
                    self.save(status=review["status"])
                    return
                feedback = {"review": review, "http": http}
                self.save(feedback=feedback)
            self.save(status="failed", reason="Repair round limit")
        except Exception as exc:
            self.save(status="blocked", reason=type(exc).__name__ + ": " + str(exc)[:500])
        finally:
            self.save(finished_at=now())
            print(json.dumps({"status": self.state["status"], "evidence": str(self.directory / "state.json")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--from-run", type=Path, help="Preserve a stopped run and reuse its unchanged independent tests")
    parser.add_argument("--backend", choices=("codex_cli", "desktop_bridge"), help="Desktop bridge requires active conversation dispatch")
    parser.add_argument("--reuse-implementation", action="store_true", help="Recheck unchanged parent code without another implementation call")
    args = parser.parse_args()
    if args.reuse_implementation and not args.from_run:
        parser.error("--reuse-implementation requires --from-run")
    config = json.loads(CONFIG.read_text())
    if args.backend:
        config["backend"] = args.backend
    if args.plan:
        print(json.dumps(config, indent=2))
        return 0
    directory = ROOT / ".local/stock-price-workflows" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    workflow = StockWorkflow(directory, config, parent=args.from_run, reuse_implementation=args.reuse_implementation)
    workflow.run()
    return 0 if workflow.state["status"] == "completed" else 3 if workflow.state["status"] == "needs_decision" else 2


if __name__ == "__main__":
    raise SystemExit(main())
