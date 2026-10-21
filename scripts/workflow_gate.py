#!/usr/bin/env python3
"""Trusted, real HTTP/PostgreSQL gate for an isolated workflow candidate.

The controller owns the candidate's scripts, spec, manifests and migrations.
No AI claim is used as test evidence. This module does not contact a model.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from acceptance import cases


ACCEPTANCE_CASES = {"csrf-setup"} | {case[0] for case in cases()}

LIFECYCLE_CASES = {
    "restart-preserves-row",
    "storage-error-is-500-without-insert",
    "recovers-after-statement-error",
    "app-logs-do-not-echo-probe-input",
}


class GateStop(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def _acceptance_valid(evidence):
    if not isinstance(evidence, dict):
        return False
    results = evidence.get("results")
    return (
        evidence.get("exit_code") == 0 and evidence.get("complete") is True
        and not evidence.get("skipped") and isinstance(results, list)
        and len(results) == len(ACCEPTANCE_CASES)
        and all(isinstance(item, dict) and item.get("passed") is True
                and not item.get("failures") and not item.get("skipped")
                and isinstance(item.get("case"), str) for item in results)
        and {item["case"] for item in results} == ACCEPTANCE_CASES
    )


def _lifecycle_valid(evidence):
    if not isinstance(evidence, dict):
        return False
    results = evidence.get("passed")
    return (
        evidence.get("exit_code") == 0 and not evidence.get("skipped")
        and isinstance(results, list) and len(results) == len(LIFECYCLE_CASES)
        and all(isinstance(item, str) for item in results)
        and set(results) == LIFECYCLE_CASES
    )


def _stop_group(process, grace=20):
    """Include descendants such as lifecycle probe servers on timeout."""
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)
    finally:
        # A leader can exit on SIGTERM while descendants ignore it. Reaping the
        # leader alone does not establish that the original process group died.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _stop_server(process, runtime_pid):
    if process.poll() is None and runtime_pid is not None:
        try:
            os.kill(runtime_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=20)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        except subprocess.TimeoutExpired:
            pass
    _stop_group(process)


def _fresh_report(directory, pattern, previous, started_ns):
    paths = [p for p in directory.glob(pattern)
             if p.name not in previous and p.stat().st_mtime_ns >= started_ns]
    if len(paths) != 1:
        raise GateStop("failed", "Missing or ambiguous fresh " + pattern + " evidence")
    try:
        report = json.loads(paths[0].read_text())
    except (OSError, ValueError):
        raise GateStop("failed", "Invalid JSON test evidence") from None
    if not isinstance(report, dict):
        raise GateStop("failed", "Invalid test evidence shape")
    return paths[0], report


def run_gate(candidate: Path, trusted_root: Path, output_dir: Path, db_name: str) -> dict:
    """Build and verify one candidate; leave its dedicated DB rows as evidence.

    status=failed means a candidate/check contract was violated. status=blocked
    means the environment or startup prevented the behavioral checks completing.
    Each subprocess has a <=600 second timeout and its own process group.
    """
    candidate, trusted_root, output_dir = map(
        lambda p: Path(p).resolve(), (candidate, trusted_root, output_dir)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "blocked", "checks": [], "acceptance": None, "lifecycle": None,
        "started_at": datetime.now(timezone.utc).isoformat(), "logs": [],
    }
    server = None
    runtime_pid = None
    server_log = None
    started_pg = False
    db_url = ""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "TZ") if key in os.environ}
    env.setdefault("PATH", os.defpath)
    env.update({
        "CARGO_HOME": str(trusted_root / ".local/cargo"),
        "CARGO_NET_OFFLINE": "true", "PILOT_COMMAND_TIMEOUT_SECONDS": "600",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PILOT_READ_ONLY_SERVER": "true",
    })

    def run(name, args, *, input_text=None, timeout=600):
        log_path = output_dir / (name + ".log")
        record = {"name": name, "exit_code": None, "log": str(log_path)}
        report["checks"].append(record)
        report["logs"].append(str(log_path))
        process = None
        try:
            with log_path.open("w") as log:
                process = subprocess.Popen(
                    [str(a) for a in args], cwd=candidate, env=env,
                    stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                    stdout=log, stderr=log, text=True, start_new_session=True,
                )
                try:
                    process.communicate(input=input_text, timeout=min(timeout, 600))
                except subprocess.TimeoutExpired:
                    _stop_group(process)
                    record.update(exit_code=process.returncode, timed_out=True)
                    raise GateStop("blocked", name + " timed out") from None
            record["exit_code"] = process.returncode
            return process.returncode
        except OSError as exc:
            record["exception"] = type(exc).__name__
            raise GateStop("blocked", name + ": " + type(exc).__name__) from None
        finally:
            # Subprocess diagnostics are retained locally, never emitted as text.
            # Remove the test-only connection string if a tool repeats it.
            if db_url and log_path.is_file():
                contents = log_path.read_text(errors="replace")
                log_path.write_text(contents.replace(db_url, "[test-db-redacted]"))

    def require_zero(name, args, *, status="failed", input_text=None, timeout=600):
        code = run(name, args, input_text=input_text, timeout=timeout)
        if code:
            raise GateStop(status, name + " exited " + str(code))

    try:
        if candidate == trusted_root or not (candidate / "app/src/main.rs").is_file():
            raise GateStop("blocked", "An isolated candidate root is required")
        if not re.fullmatch(r"daynomy_workflow_[0-9a-f]{8,32}_test", db_name):
            raise GateStop("blocked", "Invalid workflow test DB identifier")
        for executable in ("cargo", "rustc", "psql", "pg_ctl", "createdb", "bash", "codex"):
            if not shutil.which(executable, path=env["PATH"]):
                raise GateStop("blocked", "Required tool unavailable: " + executable)
        candidate.joinpath("runs").mkdir(exist_ok=True)
        candidate.joinpath(".local").mkdir(exist_ok=True)
        require_zero("preflight", [sys.executable, candidate / "scripts/check.py", "preflight"],
                     status="blocked", timeout=60)
        build_code = run("build", ["cargo", "build", "--locked", "--manifest-path",
                                   candidate / "app/Cargo.toml"])
        if build_code:
            diagnostic = (output_dir / "build.log").read_text(errors="replace")
            unavailable = any(message in diagnostic for message in (
                "no matching package named", "attempting to make an HTTP request",
                "failed to download", "could not execute process", "Permission denied",
                "Operation not permitted", "No space left on device",
            ))
            raise GateStop("blocked" if unavailable else "failed", "build exited " + str(build_code))

        pg_ctl = Path(shutil.which("pg_ctl", path=env["PATH"]))
        env["PG_BIN"] = str(pg_ctl.parent)
        env["PILOT_DB_PORT"] = "55439"
        already_running = run("postgres-status", [pg_ctl, "-D", trusted_root / ".local/pgdata",
                                                  "status"], timeout=30) == 0
        # Existing local-db.sh creates only the established dedicated local cluster.
        if not already_running:
            started_pg = True
        require_zero("postgres-start", ["bash", trusted_root / "scripts/local-db.sh", "start"],
                     status="blocked", timeout=120)
        connection = ["-h", "127.0.0.1", "-p", "55439", "-U", "pilot"]
        require_zero("database-create", ["createdb", *connection, db_name], status="blocked", timeout=30)
        require_zero("database-schema", ["psql", "-X", "-w", *connection, "-d", db_name,
                                          "-v", "ON_ERROR_STOP=1", "-f",
                                          candidate / "app/migrations/001_feedbacks.sql"],
                     status="blocked", timeout=30)
        db_url = "postgresql://pilot@127.0.0.1:55439/" + db_name
        env.update(DATABASE_URL=db_url, PILOT_TEST_DB_URL=db_url, PORT="0")
        server_log_path = output_dir / "server.log"
        report["logs"].append(str(server_log_path))
        server_log = server_log_path.open("w")
        server = subprocess.Popen(
            ["codex", "sandbox", "-P", "daynomy_runtime", "-C", str(candidate),
             "-c", 'permissions.daynomy_runtime={filesystem={":root"="read"},network={enabled=true}}',
             sys.executable, "-c",
             'import os,sys; print("sandbox_runtime_pid="+str(os.getpid()),flush=True); '
             'os.execv(sys.argv[1],sys.argv[1:])',
             str(candidate / "app/target/debug/daynomy-feedback")], cwd=candidate, env=env,
            stdin=subprocess.DEVNULL, stdout=server_log, stderr=server_log,
            start_new_session=True,
        )
        deadline = time.monotonic() + 15
        while True:
            if server.poll() is not None:
                raise GateStop("blocked", "Candidate server exited before readiness")
            log_text = server_log_path.read_text(errors="replace")
            pid_match = re.search(r"^sandbox_runtime_pid=([0-9]+)$", log_text, re.MULTILINE)
            if pid_match and int(pid_match[1]) > 1:
                runtime_pid = int(pid_match[1])
            match = re.search(r"event=server.started address=(127\.0\.0\.1:([0-9]+))", log_text)
            if runtime_pid is not None and match and 0 < int(match[2]) <= 65535:
                env["PILOT_BASE_URL"] = "http://" + match[1]
                break
            if time.monotonic() >= deadline:
                raise GateStop("blocked", "Candidate server startup timeout")
            time.sleep(0.05)

        runs = candidate / "runs"
        previous = {p.name for p in runs.glob("acceptance-*.json")}
        started_ns = time.time_ns()
        verify_code = run("verify", [sys.executable, candidate / "scripts/check.py", "verify"])
        try:
            path, evidence = _fresh_report(runs, "acceptance-*.json", previous, started_ns)
        except GateStop:
            if verify_code:
                raise GateStop("blocked" if verify_code == 2 else "failed",
                               "verify exited " + str(verify_code)) from None
            raise
        results = evidence.get("results", [])
        valid = _acceptance_valid(evidence)
        report["acceptance"] = {
            "count": len(results) if isinstance(results, list) else 0,
            "passed": valid, "report": str(path),
            "failed_cases": [item.get("case") for item in results
                             if isinstance(item, dict) and item.get("passed") is not True]
                            if isinstance(results, list) else [],
        }
        shutil.copyfile(path, output_dir / "acceptance.json")
        if verify_code:
            raise GateStop("blocked" if verify_code == 2 else "failed",
                           "verify exited " + str(verify_code))
        if not valid:
            raise GateStop("failed", "Incomplete or failed acceptance evidence; exactly 46 required")

        previous = {p.name for p in runs.glob("lifecycle-*.json")}
        started_ns = time.time_ns()
        lifecycle_code = run("lifecycle", [sys.executable, candidate / "scripts/check_lifecycle.py"])
        try:
            path, evidence = _fresh_report(runs, "lifecycle-*.json", previous, started_ns)
        except GateStop:
            if lifecycle_code:
                raise GateStop("failed", "lifecycle exited " + str(lifecycle_code)) from None
            raise
        results = evidence.get("passed", [])
        valid = _lifecycle_valid(evidence)
        report["lifecycle"] = {
            "count": len(results) if isinstance(results, list) else 0,
            "passed": valid, "report": str(path),
        }
        shutil.copyfile(path, output_dir / "lifecycle.json")
        if lifecycle_code:
            raise GateStop("failed", "lifecycle exited " + str(lifecycle_code))
        if not valid:
            raise GateStop("failed", "Incomplete lifecycle evidence; all four probes required")
        report["status"] = "passed"
    except GateStop as exc:
        report.update(status=exc.status, reason=exc.reason)
    except Exception as exc:
        report.update(status="blocked", reason="Gate environment exception: " + type(exc).__name__)
    finally:
        if server is not None:
            try:
                _stop_server(server, runtime_pid)
                report["checks"].append({"name": "server-stop", "exit_code": server.returncode})
                if server.returncode != 0 and report["status"] == "passed":
                    report.update(status="failed", reason="Candidate server did not shut down cleanly")
            except Exception as exc:
                report.update(status="blocked", reason="Server cleanup: " + type(exc).__name__)
        if server_log is not None:
            server_log.close()
        if started_pg:
            try:
                require_zero("postgres-stop", ["bash", trusted_root / "scripts/local-db.sh", "stop"],
                             status="blocked", timeout=60)
            except GateStop as exc:
                report.update(status="blocked", reason=exc.reason)
        report["database"] = db_name if re.fullmatch(r"daynomy_workflow_[0-9a-f]{8,32}_test", db_name) else None
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output_dir / "gate.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
