#!/usr/bin/env python3
"""Compare the documented non-league API inventory with original Java mappings."""

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = "reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/"


def paths(arguments):
    match = re.search(r"\b(?:path|value)\s*=\s*(\{[^}]*\}|\"[^\"]*\")", arguments)
    value = match.group(1) if match else arguments.split(",", 1)[0] if not arguments.lstrip().startswith("{") else arguments.split("}", 1)[0]
    return re.findall(r'"([^"\\]*)"', value) or [""]


def java_mappings(text):
    class_start = re.search(r"\bclass\s+\w+", text).start()
    prefix = re.search(r"@RequestMapping\s*\(([^)]*)\)", text[:class_start])
    bases = paths(prefix.group(1)) if prefix else [""]
    handlers = []
    for match in re.finditer(r"@(Get|Post|Put|Patch|Delete)Mapping\b(?:\s*\(([^)]*)\))?", text[class_start:]):
        handlers.append((match.group(1).upper(), [base + suffix for base in bases for suffix in paths(match.group(2) or "")]))
    return handlers


def build_inventory(root):
    specification = root / "spec/service.md"
    appendix = specification.read_text().split("## 6. API 전체 목록", 1)[1]
    rows = []
    controller = None
    for line in appendix.splitlines():
        if line.startswith("### ") and line.endswith(".java"):
            controller = line[4:]
        if re.match(r"\| (GET|POST|PUT|PATCH|DELETE) \|", line):
            columns = line.strip("|").split("|")
            method, route_text, description, access = [column.strip() for column in columns[:4]]
            route_paths = re.findall(r"`([^`]+)`", route_text)
            if not controller or not route_paths:
                raise ValueError("unrecognized specification mapping")
            rows.append(dict(controller=BASE + controller, method=method, paths=route_paths,
                             description=description, access=access))
    controllers = sorted({row["controller"] for row in rows})
    all_controllers = sorted(str(path.relative_to(root)) for path in (root / BASE).rglob("*Controller*.java")
                             if "league" not in path.relative_to(root / BASE).parts)
    if controllers != all_controllers:
        raise ValueError("controller set differs from reference")
    for controller in controllers:
        actual = sorted((method, tuple(sorted(route_paths))) for method, route_paths in java_mappings((root / controller).read_text()))
        expected = sorted((row["method"], tuple(sorted(row["paths"]))) for row in rows if row["controller"] == controller)
        if actual != expected:
            raise ValueError(f"Java/specification mapping mismatch: {controller}")
    source_paths = ["spec/service.md"] + controllers
    return {"schema_version": 1, "scope": "non-league Java HTTP mappings; not DTO/authorization/runtime parity",
            "controller_count": len(controllers), "handler_count": len(rows),
            "expanded_route_count": sum(len(row["paths"]) for row in rows),
            "source_hashes": {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest() for relative in source_paths},
            "handlers": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="knowledge/contracts/api-index.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = build_inventory(ROOT)
    path = (ROOT / args.output).resolve()
    if not path.is_relative_to(ROOT / "knowledge/contracts"):
        raise ValueError("output must be under knowledge/contracts")
    if args.check:
        if json.loads(path.read_text()) != inventory:
            raise ValueError("saved API inventory differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as output:
            json.dump(inventory, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(f"PASS Java/spec mappings: {inventory['controller_count']} controllers, {inventory['handler_count']} handlers, {inventory['expanded_route_count']} routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
