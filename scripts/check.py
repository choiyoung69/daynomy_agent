#!/usr/bin/env python3
"""Fail-closed checks; preflight is not an implementation pass."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def snapshot_ok():
    snapshot = json.loads((ROOT / "spec/reference-snapshot.json").read_text())
    failures = []
    for item in snapshot["files"]:
        path = ROOT / snapshot["root"] / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            failures.append(item["path"])
    for path in failures:
        print("SOURCE CHANGED/MISSING: " + path)
    print(f"Source snapshot: {len(snapshot['files']) - len(failures)}/{len(snapshot['files'])} match")
    return not failures


def preflight():
    good = snapshot_ok()
    for name in ("cargo", "rustc", "psql"):
        available = bool(shutil.which(name))
        print(f"{name}: {'available' if available else 'MISSING'}")
        good = good and available
    print("Rust implementation: " + ("present" if (ROOT / "app/Cargo.toml").is_file() else "NOT STARTED"))
    print("No server/DB/behavior verification was performed by preflight.")
    return 0 if good else 2


def verify():
    if preflight():
        return 2
    manifest = ROOT / "app/Cargo.toml"
    if not manifest.is_file():
        print("BLOCKED: app/Cargo.toml is absent; no implementation to verify.", file=sys.stderr)
        return 2
    timeout = int(os.environ.get("PILOT_COMMAND_TIMEOUT_SECONDS", "600"))
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    test_command = ["cargo", "test", "--manifest-path", str(manifest)]
    if os.environ.get("PILOT_READ_ONLY_SERVER") == "true":
        # The compiler needs writable build output; the resulting test binary
        # must not inherit that write access to trusted criteria or controller.
        try:
            version = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print("BLOCKED: Rust target discovery timed out.")
            return 2
        host = next((line.removeprefix("host: ") for line in version.stdout.splitlines()
                     if line.startswith("host: ")), "")
        if version.returncode or not host or not all(c.isalnum() or c in "_-" for c in host):
            print("BLOCKED: unable to determine Rust target for read-only test runner.")
            return 2
        runner = ROOT / "scripts/readonly_runner.py"
        if not runner.is_file() or shutil.which("codex") is None:
            print("BLOCKED: read-only Rust test runner unavailable.")
            return 2
        runner_config = "target." + host + ".runner=" + json.dumps([sys.executable, str(runner)])
        test_command = ["cargo", "--config", runner_config, "test", "--manifest-path", str(manifest)]
    commands = [
        ["cargo", "fmt", "--manifest-path", str(manifest), "--", "--check"],
        ["cargo", "clippy", "--manifest-path", str(manifest), "--all-targets", "--", "-D", "warnings"],
        test_command,
        ["cargo", "build", "--manifest-path", str(manifest)],
        [sys.executable, str(ROOT / "scripts/test_acceptance.py")],
        [sys.executable, str(ROOT / "scripts/test_compare_feedback.py")],
        [sys.executable, str(ROOT / "scripts/test_agent_workflow.py")],
        [sys.executable, str(ROOT / "scripts/acceptance.py")],
    ]
    for command in commands:
        print("RUN " + " ".join(command), flush=True)
        try:
            code = subprocess.run(command, cwd=ROOT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            print("BLOCKED: command timed out; record evidence before changing its limit.")
            return 2
        if code:
            print(f"FAILED with exit code {code}")
            return code if code > 0 else 1
    print("Automated gate passed. Complete the manual items in spec/feedback.md before declaring done.")
    return 0


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "verify"):
        print("Usage: python3 scripts/check.py {preflight|verify}", file=sys.stderr)
        return 2
    try:
        return preflight() if sys.argv[1] == "preflight" else verify()
    except (OSError, ValueError, KeyError):
        print("BLOCKED: invalid/missing harness configuration.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
