#!/usr/bin/env python3
"""Run synthetic language boundary probes, without starting apps or databases.

The output path is required so an old evidence report is never overwritten by default.
Missing runtimes are reported as unavailable; exit 0 only means available probes passed.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "experiments/knowledge-probes"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; use a fresh evidence filename")
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic language/decoder examples; not target app, HTTP or DB validation",
        "source_hashes": {}, "probes": {},
    }
    expected = json.loads((FIXTURES / "expected.json").read_text())
    env = os.environ.copy()
    env["CARGO_HOME"] = str(ROOT / ".local/cargo")
    env["CARGO_TARGET_DIR"] = str(ROOT / ".local/knowledge-probe-target")

    def execute(command):
        relative = [str(x) for x in command]
        try:
            result = subprocess.run(relative, cwd=ROOT, env=env, capture_output=True,
                                    text=True, timeout=120)
            return {"command": relative, "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"command": relative, "exit_code": None, "error": "timeout after 120 seconds"}

    with tempfile.TemporaryDirectory(prefix="knowledge-probes-") as temporary:
        temp = Path(temporary)
        configurations = {
            "node": (["node", "--version"], [], ["node", FIXTURES / "node.mjs"]),
            "swift": (["swiftc", "--version"], ["swiftc", "-module-cache-path", temp / "cache",
                       FIXTURES / "swift.swift", "-o", temp / "swift-probe"], [temp / "swift-probe"]),
            "rust": (["rustc", "--version"], [], ["cargo", "run", "--offline", "--quiet",
                     "--manifest-path", FIXTURES / "rust/Cargo.toml"]),
        }
        for name, (version_command, build_command, run_command) in configurations.items():
            required = [version_command[0]] + (["cargo"] if name == "rust" else [])
            if any(shutil.which(tool) is None for tool in required):
                report["probes"][name] = {"status": "unavailable", "required": required}
                continue
            entry = {"status": "failed", "version": execute(version_command)}
            report["probes"][name] = entry
            if build_command:
                entry["build"] = execute(build_command)
                if entry["build"]["exit_code"] != 0:
                    continue
            entry["run"] = execute(run_command)
            if entry["run"]["exit_code"] != 0:
                continue
            try:
                entry["actual"] = json.loads(entry["run"]["stdout"])
            except json.JSONDecodeError:
                entry["error"] = "stdout is not a single JSON value"
                continue
            entry["expected"] = expected[name]
            entry["status"] = "passed" if entry["actual"] == expected[name] else "failed"
            entry["checked_fields"] = len(expected[name])
        for name, tool in (("kotlin", "kotlinc"), ("dart", "dart"), ("flutter", "flutter")):
            report["probes"][name] = {
                "status": "not-run" if shutil.which(tool) else "unavailable",
                "note": "No probe implemented; compiler inventory only", "executable": shutil.which(tool),
            }
    paths = [Path(__file__).resolve()] + sorted(
        path for path in FIXTURES.rglob("*") if path.is_file() and "target" not in path.parts)
    for path in paths:
        report["source_hashes"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["ended_at"] = datetime.now(timezone.utc).isoformat()
    report["available_probes_passed"] = all(
        report["probes"][name]["status"] == "passed"
        for name in configurations if report["probes"][name]["status"] != "unavailable")
    report["all_platforms_validated"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier evidence even if another process wrote meanwhile.
    with args.output.open("x") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    for name, entry in report["probes"].items():
        print(f"{name}: {entry['status']}")
    return 0 if report["available_probes_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
