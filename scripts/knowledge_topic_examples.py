#!/usr/bin/env python3
"""Compile/run topic examples and preserve failures. No target app/server/DB execution."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / ".local/knowledge-sdks"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("report already exists")
    report = {"started_at": datetime.now(timezone.utc).isoformat(),
              "scope": "standalone language/JSON/state/cancellation examples; no UI, real HTTP, DB, host bridge or independent review",
              "runs": {}, "source_hashes": {}}
    env = os.environ.copy()
    env.update(CARGO_HOME=str(ROOT / ".local/cargo"), CARGO_TARGET_DIR=str(ROOT / ".local/knowledge-topic-target"),
               DART_SUPPRESS_ANALYTICS="true", DART_TOOLING_ANALYTICS_DISABLED="true")

    def execute(command):
        try:
            result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env, capture_output=True,
                                    text=True, timeout=120)
            return {"command": [str(x) for x in command], "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"command": [str(x) for x in command], "exit_code": None, "error": "timeout"}

    with tempfile.TemporaryDirectory(prefix="knowledge-topics-") as temporary:
        temp = Path(temporary)
        kotlin = SDK / "kotlin/kotlinc"
        libraries = [SDK / "kotlinx-serialization-core-jvm-1.12.0.jar", SDK / "kotlinx-serialization-json-jvm-1.12.0.jar",
                     kotlin / "lib/kotlinx-coroutines-core-jvm.jar"]
        classpath = ":".join(str(path) for path in libraries)
        # Keep the original TS example intact; remove only erasable syntax in a temporary module.
        strip = ["node", "--input-type=module", "-e",
                 "import{readFileSync,writeFileSync}from'node:fs';import{stripTypeScriptTypes}from'node:module';"
                 "writeFileSync(process.argv[2],stripTypeScriptTypes(readFileSync(process.argv[1],'utf8')));",
                 "knowledge/examples/typescript/core.ts", temp / "core.mjs"]
        configurations = {
            "kotlin": ([kotlin / "bin/kotlinc", "-version"],
                       [[kotlin / "bin/kotlinc", "knowledge/examples/kotlin/Core.kt", "-cp", classpath,
                         "-Xplugin=" + str(kotlin / "lib/kotlin-serialization-compiler-plugin.jar"),
                         "-include-runtime", "-d", temp / "core.jar"]],
                       ["java", "-cp", str(temp / "core.jar") + ":" + classpath, "CoreKt"]),
            "dart": ([SDK / "dart/dart-sdk/bin/dart", "--version"], [],
                     [SDK / "dart/dart-sdk/bin/dart", "knowledge/examples/dart/core.dart"]),
            "swift": (["swiftc", "--version"], [["swiftc", "-swift-version", "6", "-parse-as-library",
                      "-module-cache-path", temp / "swift-cache", "knowledge/examples/swift/Core.swift",
                      "-o", temp / "swift-example"]], [temp / "swift-example"]),
            "typescript": (["node", "--version"], [["node", SDK / "typescript/package/bin/tsc", "--noEmit", "--strict",
                           "--target", "ES2022", "--module", "ESNext", "--moduleResolution", "bundler",
                           "--lib", "ES2022,DOM", "knowledge/examples/typescript/core.ts"], strip], ["node", temp / "core.mjs"]),
            "rust": (["rustc", "--version"], [], ["cargo", "run", "--offline", "--quiet", "--manifest-path", "knowledge/examples/rust/Cargo.toml"]),
        }
        for name, (version, builds, run) in configurations.items():
            executable = str(version[0])
            if not (Path(executable).is_file() if "/" in executable else shutil.which(executable)):
                report["runs"][name] = {"status": "unavailable"}
                print(f"{name}: unavailable", flush=True)
                continue
            entry = {"status": "failed", "version": execute(version), "builds": []}
            report["runs"][name] = entry
            for command in builds:
                entry["builds"].append(execute(command))
                if entry["builds"][-1]["exit_code"] != 0:
                    break
            if all(build["exit_code"] == 0 for build in entry["builds"]):
                entry["run"] = execute(run)
                if entry["run"]["exit_code"] == 0:
                    try:
                        checks = json.loads(entry["run"]["stdout"])
                        if isinstance(checks, dict) and checks and all(value is True for value in checks.values()):
                            entry.update(status="passed", checks=checks, checked_cases=len(checks))
                    except json.JSONDecodeError:
                        entry["error"] = "example stdout is not JSON"
            print(f"{name}: {entry['status']}", flush=True)
    source_paths = [Path(__file__).resolve()] + sorted(path for path in (ROOT / "knowledge/examples").rglob("*") if path.is_file())
    for path in source_paths:
        report["source_hashes"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if (SDK / "manifest.json").exists():
        report["example_sdk_artifacts"] = json.loads((SDK / "manifest.json").read_text())
    report["ended_at"] = datetime.now(timezone.utc).isoformat()
    report["all_five_language_examples_passed"] = all(entry["status"] == "passed" for entry in report["runs"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0 if report["all_five_language_examples_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
