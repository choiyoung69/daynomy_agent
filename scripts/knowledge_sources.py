#!/usr/bin/env python3
"""Capture public source responses; review and pin separately. No wiki/model execution."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 2 * 1024 * 1024


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(root, relative, prefix):
    path = (root / relative).resolve()
    boundary = (root / prefix).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(boundary):
        raise ValueError(f"path must be inside {prefix}")
    return path


def validate_snapshot(root, snapshot):
    path = inside(root, snapshot["path"], "knowledge/raw/external")
    data = path.read_bytes()
    if digest(data) != snapshot["sha256"] or len(data) != snapshot["bytes"]:
        raise ValueError("snapshot bytes or hash changed")
    data.decode("utf-8")
    return path


def retrieve(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("public HTTPS source required")
    request = Request(url, headers={"User-Agent": "DAYNOMY-knowledge/1.0", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=20) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme != "https":
            raise ValueError("redirected outside HTTPS")
        media_type = response.headers.get_content_type()
        if not media_type.startswith("text/"):
            raise ValueError("expected a text response")
        data = response.read(LIMIT + 1)
    if not data or len(data) > LIMIT:
        raise ValueError("empty response or source larger than 2 MiB")
    data.decode("utf-8")
    return data, media_type, final_url


def capture(root, identifiers, output):
    root = root.resolve()
    output = inside(root, output, "knowledge/evidence")
    if output.exists():
        raise ValueError("report exists; choose a new output path")
    registry = json.loads((root / "knowledge/sources.json").read_text())
    sources = {source["id"]: source for source in registry["sources"]}
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("provide unique source IDs")
    for identifier in identifiers:
        if not re.fullmatch(r"[A-Z][A-Z0-9]*", identifier) or sources[identifier]["kind"] != "external":
            raise ValueError("external source IDs required")
    report = {"schema_version": 1, "started_at": timestamp(),
              "collector": {"path": "scripts/knowledge_sources.py",
                            "sha256": digest(Path(__file__).read_bytes())}, "results": []}
    for identifier in identifiers:
        source = sources[identifier]
        baseline = source.get("content_snapshot")
        item = {"source_id": identifier, "baseline_sha256": baseline["sha256"] if baseline else None,
                "affected_documents": []}
        for page in sorted((root / "knowledge/wiki").rglob("*.md")):
            # Source IDs are JSON strings in wiki metadata; this reports direct references only.
            front = page.read_text().partition("\n---\n")[0]
            if f'"{identifier}"' in front:
                item["affected_documents"].append(str(page.relative_to(root)))
        try:
            if baseline:
                validate_snapshot(root, baseline)
            data, media_type, retrieved_url = retrieve(source.get("snapshot_url", source["url"]))
            sha256 = digest(data)
            suffix = ".html" if media_type == "text/html" else ".txt"
            relative = f"knowledge/raw/external/{identifier}/{sha256}{suffix}"
            path = inside(root, relative, "knowledge/raw/external")
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_bytes() != data:
                    raise ValueError("existing content-addressed file differs")
            else:
                with path.open("xb") as output_file:
                    output_file.write(data)
            item["candidate_snapshot"] = {"path": relative, "sha256": sha256, "bytes": len(data),
                "media_type": media_type, "retrieved_url": retrieved_url, "retrieved_at": timestamp(),
                "scope": "exact HTTP response body; completeness and applicability require review"}
            item["status"] = "captured" if not baseline else "unchanged" if baseline["sha256"] == sha256 else "changed"
        except (OSError, ValueError) as error:
            # Do not record headers, credentials or full HTTP response bodies in error logs.
            item["status"] = "unavailable"
            item["error_type"] = type(error).__name__
        report["results"].append(item)
        print(f"{identifier}: {item['status']}", flush=True)
    report["ended_at"] = timestamp()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as output_file:
        json.dump(report, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
    return 1 if any(item["status"] == "unavailable" for item in report["results"]) else 2 if any(
        item["status"] == "changed" for item in report["results"]) else 0


def pin(root, report_path, identifier, note):
    root = root.resolve()
    if not note.strip():
        raise ValueError("a review note is required")
    path = inside(root, report_path, "knowledge/evidence")
    report = json.loads(path.read_text())
    matches = [item for item in report["results"] if item["source_id"] == identifier]
    if len(matches) != 1 or matches[0]["status"] not in {"captured", "unchanged", "changed"}:
        raise ValueError("one successful capture is required")
    item = matches[0]
    snapshot = item["candidate_snapshot"]
    validate_snapshot(root, snapshot)
    registry_path = root / "knowledge/sources.json"
    registry = json.loads(registry_path.read_text())
    source = next(source for source in registry["sources"] if source["id"] == identifier)
    if source["kind"] != "external":
        raise ValueError("external source required")
    previous = source.get("content_snapshot")
    current_hash = previous["sha256"] if previous else None
    if current_hash != item["baseline_sha256"]:
        raise ValueError("baseline changed since capture; fetch and review again")
    source.setdefault("snapshot_history", []).append({"previous": previous, "selected": snapshot,
        "report": str(path.relative_to(root)), "reviewed_at": timestamp(), "review_note": note,
        "pin_tool_sha256": digest(Path(__file__).read_bytes())})
    source["content_snapshot"] = snapshot
    # Downloading/pinning is not proof that the source was read or wiki claims were reviewed.
    temporary = registry_path.with_suffix(".json.tmp")
    with temporary.open("x") as output_file:
        json.dump(registry, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
    temporary.replace(registry_path)
    print(f"{identifier}: pinned; review_status unchanged ({source['review_status']})")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="capture or compare with pinned bytes, without changing baseline")
    fetch.add_argument("--source", action="append", required=True)
    fetch.add_argument("--output", required=True, help="new report under knowledge/evidence")
    accept = commands.add_parser("pin", help="select inspected bytes as a baseline, leaving wiki/review state unchanged")
    accept.add_argument("--report", required=True)
    accept.add_argument("--source", required=True)
    accept.add_argument("--review-note", required=True)
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            return capture(ROOT, args.source, args.output)
        return pin(ROOT, args.report, args.source, args.review_note)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print(f"FAIL source workflow: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
