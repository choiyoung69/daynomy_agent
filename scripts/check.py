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
    commands = [
        ["cargo", "fmt", "--manifest-path", str(manifest), "--", "--check"],
        ["cargo", "clippy", "--manifest-path", str(manifest), "--all-targets", "--", "-D", "warnings"],
        ["cargo", "test", "--manifest-path", str(manifest)],
        ["cargo", "build", "--manifest-path", str(manifest)],
        [sys.executable, str(ROOT / "scripts/test_acceptance.py")],
        [sys.executable, str(ROOT / "scripts/test_compare_feedback.py")],
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
