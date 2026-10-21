#!/usr/bin/env python3
"""Restart/fault probe on the dedicated test DB. Temporarily rejects inserts."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

from acceptance import Client, Database, check_response, check_storage, require, validate_local_url

ROOT = Path(__file__).resolve().parents[1]


def alter(db, sql):
    env = db.env.copy()
    env["PGOPTIONS"] = "-c statement_timeout=5000 -c lock_timeout=2000"
    result = subprocess.run(
        ["psql", "-X", "-w", "-v", "ON_ERROR_STOP=1"],
        input=sql, capture_output=True, text=True, env=env, timeout=10,
    )
    require(result.returncode == 0, "Fault setup/cleanup failed (DB details withheld)")


def start(log_path, env):
    log = log_path.open("w")
    command = [str(ROOT / "app/target/debug/daynomy-feedback")]
    if env.get("PILOT_READ_ONLY_SERVER") == "true":
        command = [
            "codex", "sandbox", "-P", "daynomy_runtime", "-C", str(ROOT), "-c",
            'permissions.daynomy_runtime={filesystem={":root"="read"},network={enabled=true}}',
            sys.executable, "-c",
            'import os,sys; print("sandbox_runtime_pid="+str(os.getpid()),flush=True); '
            'os.execv(sys.argv[1],sys.argv[1:])', *command,
        ]
    process = subprocess.Popen(
        command, env={**env, "PORT": "0"}, stdout=log, stderr=log, start_new_session=True,
    )
    log.close()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            require(process.poll() is None, "Probe server exited before becoming ready")
            match = re.search(r"event=server.started address=(127\.0\.0\.1:\d+)", log_path.read_text())
            if match:
                pid = re.search(r"sandbox_runtime_pid=(\d+)", log_path.read_text())
                if env.get("PILOT_READ_ONLY_SERVER") == "true":
                    require(pid is not None, "Missing sandbox runtime PID")
                    process.runtime_pid = int(pid[1])
                return process, Client("http://" + match[1])
            time.sleep(0.05)
        raise AssertionError("Probe server startup timeout")
    except BaseException:
        stop(process)
        raise


def stop(process):
    if process is None:
        return
    if process.poll() is None:
        try:
            if hasattr(process, "runtime_pid"):
                os.kill(process.runtime_pid, signal.SIGTERM)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise AssertionError("Server did not shut down gracefully") from None
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    else:
        # A previously exited wrapper may still have live descendants.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main():
    results = []
    process = None
    fault_installed = False
    code = 1
    try:
        url = validate_local_url(os.environ.get("PILOT_TEST_DB_URL", ""), database=True)
        db = Database(url)
        env = {**os.environ, "DATABASE_URL": url}
        log_dir = ROOT / ".local"
        log_dir.mkdir(exist_ok=True)
        first_log, second_log = log_dir / "lifecycle-1.log", log_dir / "lifecycle-2.log"
        process, client = start(first_log, env)
        header, token = client.csrf()
        body = json.dumps({"content": "lifecycle-storage-marker", "pagePath": "/probe"}).encode()
        headers = {"Content-Type": "application/json", header: token}
        before = db.snapshot()
        status, response_headers, response_body = client.send("/api/feedback", body, headers)
        check_response(status, response_headers, response_body, 204)
        saved = db.snapshot()
        rows = db.new_rows(before["max_id"])
        check_storage(before, saved, rows, ("lifecycle-storage-marker", "/probe"))
        stop(process)
        require(process.returncode == 0, "Server shutdown was not clean")
        process = None
        process, client = start(second_log, env)
        require(db.snapshot() == saved and db.new_rows(before["max_id"]) == rows,
                "Saved row changed/disappeared after server restart")
        results.append("restart-preserves-row")
        header, token = client.csrf()
        headers = {"Content-Type": "application/json", header: token}
        # Only this dedicated DB. NOT VALID preserves pre-existing test rows.
        alter(db, "ALTER TABLE feedbacks ADD CONSTRAINT pilot_failure_probe CHECK (false) NOT VALID;")
        fault_installed = True
        status, _, response_body = client.send("/api/feedback", body, headers)
        require(status == 500, "Storage failure must not return success")
        require(json.loads(response_body) == {
            "code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."
        }, "Incorrect storage failure response")
        check_storage(saved, db.snapshot(), db.new_rows(saved["max_id"]), None)
        results.append("storage-error-is-500-without-insert")
        alter(db, "ALTER TABLE feedbacks DROP CONSTRAINT pilot_failure_probe;")
        fault_installed = False
        status, response_headers, response_body = client.send("/api/feedback", body, headers)
        check_response(status, response_headers, response_body, 204)
        check_storage(saved, db.snapshot(), db.new_rows(saved["max_id"]),
                      ("lifecycle-storage-marker", "/probe"))
        results.append("recovers-after-statement-error")
        stop(process)
        require(process.returncode == 0, "Server shutdown was not clean")
        process = None
        for log_path in (first_log, second_log):
            text = log_path.read_text()
            require("lifecycle-storage-marker" not in text and token not in text and url not in text,
                    "Sensitive input appeared in app logs")
        results.append("app-logs-do-not-echo-probe-input")
        code = 0
    except Exception as exc:
        # No DSN, SQL parameter, token, or response contents are printed.
        print("FAIL lifecycle probe: " + type(exc).__name__, file=sys.stderr)
    finally:
        if fault_installed:
            try:
                alter(db, "ALTER TABLE feedbacks DROP CONSTRAINT pilot_failure_probe;")
            except Exception:
                print("CLEANUP FAILED: remove pilot_failure_probe from the dedicated test DB.", file=sys.stderr)
                code = 1
        try:
            stop(process)
        except Exception:
            print("Probe server cleanup failed.", file=sys.stderr)
            code = 1
    for result in results:
        print("PASS " + result)
    report = {"finished_at": datetime.now(timezone.utc).isoformat(), "passed": results, "exit_code": code}
    output = ROOT / "runs" / ("lifecycle-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Report: " + str(output.relative_to(ROOT)))
    return code


if __name__ == "__main__":
    sys.exit(main())
