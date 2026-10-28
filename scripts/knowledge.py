#!/usr/bin/env python3
"""Read-only checks and lexical search for the local knowledge base."""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from knowledge_sources import validate_snapshot
from knowledge_inventory import build_inventory


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
WIKI = KNOWLEDGE / "wiki"
TOPIC_NAMES = {"types-and-json", "numbers-and-money", "dates-and-unicode", "collections-and-models",
               "async-and-cancellation", "state-and-navigation", "errors-and-transactions",
               "auth-and-storage", "modules-and-testing"}
PACKAGE_PLATFORMS = {"android-kotlin": "android", "ios-swift": "ios",
                     "react-native-typescript": "react-native", "flutter-dart": "flutter",
                     "webview": "webview", "rust-backend": None}


def metadata(path):
    body = path.read_text(encoding="utf-8")
    if not body.startswith("---\n"):
        raise ValueError("missing metadata")
    front, marker, _ = body[4:].partition("\n---\n")
    if not marker:
        raise ValueError("unterminated metadata")
    values = {}
    for line in front.splitlines():
        key, separator, value = line.partition(":")
        if not separator or key in values:
            raise ValueError("invalid or duplicate metadata field")
        values[key] = value.strip()
    for key in ("title", "confirmed_on", "review_status", "runtime_status", "source_ids"):
        if not values.get(key):
            raise ValueError(f"missing {key}")
    date.fromisoformat(values["confirmed_on"])
    if values["review_status"] not in {"draft", "static-reviewed"}:
        raise ValueError("unknown review_status")
    if values["runtime_status"] not in {"not-run", "evidence-linked"}:
        raise ValueError("unknown runtime_status")
    sources = json.loads(values["source_ids"])
    if not isinstance(sources, list) or not sources or not all(isinstance(x, str) for x in sources):
        raise ValueError("source_ids must be a nonempty JSON string array")
    values["source_ids"] = sources
    return values


def knowledge_document(relative):
    path = (KNOWLEDGE / relative).resolve()
    if not path.is_relative_to(KNOWLEDGE) or not path.is_file() or path.suffix != ".md":
        raise ValueError(f"missing or invalid knowledge document: {relative}")
    metadata(path)
    return path


def load_packs():
    packs = json.loads((KNOWLEDGE / "packs.json").read_text(encoding="utf-8"))
    platforms = packs["platforms"]
    languages = packs["languages"]
    if set(languages) != {"kotlin", "swift", "typescript", "dart", "rust"}:
        raise ValueError("language packages must contain kotlin, swift, typescript, dart and rust")
    for slug, language in languages.items():
        if language["document"] != f"wiki/languages/{slug}.md":
            raise ValueError(f"{slug}: language document mapping mismatch")
        knowledge_document(language["document"])
    if set(platforms) != {"android", "ios", "react-native", "flutter", "webview"}:
        raise ValueError("platform mappings must contain the five supported development approaches")
    detailed = packs.get("packages", {})
    if set(detailed) != set(PACKAGE_PLATFORMS):
        raise ValueError("six detailed language/platform packages are required")
    for slug, package in detailed.items():
        prefix = f"wiki/packages/{slug}/"
        if package["index"] != prefix + "index.md" or package["platform"] != PACKAGE_PLATFORMS[slug]:
            raise ValueError(f"{slug}: detailed package mapping mismatch")
        knowledge_document(package["index"])
        if set(package["topics"]) != TOPIC_NAMES:
            raise ValueError(f"{slug}: nine detailed topics are required")
        defaults = package["default_topics"]
        if not defaults or len(set(defaults)) != len(defaults) or not set(defaults) <= TOPIC_NAMES:
            raise ValueError(f"{slug}: invalid default topics")
        for topic, document in package["topics"].items():
            if document != prefix + topic + ".md":
                raise ValueError(f"{slug}: detailed topic document mapping mismatch")
            knowledge_document(document)
        expected = platforms[package["platform"]]["language_packages"] if package["platform"] else ["rust"]
        if package["languages"] != expected:
            raise ValueError(f"{slug}: detailed package languages mismatch")
    if not packs["features"]:
        raise ValueError("feature mapping is empty")
    for feature in packs["features"].values():
        if not feature["shared_documents"] or not feature["required_topics"]:
            raise ValueError("feature requires shared documents and required topics")
        for document in feature["shared_documents"]:
            if not document.startswith(("wiki/shared/", "wiki/projects/")):
                raise ValueError("shared context must use common or project documents")
            knowledge_document(document)
    for slug, platform in platforms.items():
        if platform["document"] != f"wiki/platforms/{slug}.md":
            raise ValueError(f"{slug}: platform document mapping mismatch")
        knowledge_document(platform["document"])
        expected_languages = {"android": ["kotlin"], "ios": ["swift"], "react-native": ["typescript"],
                              "flutter": ["dart"], "webview": ["typescript", "kotlin", "swift"]}
        if platform["language_packages"] != expected_languages[slug]:
            raise ValueError(f"{slug}: missing or unexpected language package")
        selected_package = platform.get("implementation_package")
        if selected_package not in detailed or detailed[selected_package]["platform"] != slug:
            raise ValueError(f"{slug}: missing or unexpected detailed package")
        if not isinstance(platform["pending_decisions"], list):
            raise ValueError(f"{slug}: pending_decisions must be a list")
        if not platform["source_ids"]:
            raise ValueError(f"{slug}: missing platform sources")
        if not platform["required_version_fields"] or not all(isinstance(field, str) and field for field in platform["required_version_fields"]):
            raise ValueError(f"{slug}: missing required version field names")
        if any(value not in {"pending", "partial", "documented"} for value in platform["topics"].values()):
            raise ValueError(f"{slug}: invalid topic preparation status")
        for feature in packs["features"].values():
            for topic in feature["required_topics"] + platform["extra_required_topics"]:
                if topic not in platform["topics"]:
                    raise ValueError(f"{slug}: missing required topic {topic}")
    evidence_path = (KNOWLEDGE / packs["example_evidence"]).resolve()
    if not evidence_path.is_relative_to(KNOWLEDGE / "evidence"):
        raise ValueError("example evidence must be inside knowledge/evidence")
    evidence = json.loads(evidence_path.read_text())
    if set(evidence["runs"]) != set(languages) or evidence["all_five_language_examples_passed"] is not True:
        raise ValueError("five-language example evidence is incomplete")
    for slug, run in evidence["runs"].items():
        checks = run.get("checks", {})
        if (run["status"] != "passed" or not checks or not all(value is True for value in checks.values()) or
                run["checked_cases"] != len(checks) or run["run"]["exit_code"] != 0 or
                any(build["exit_code"] != 0 for build in run.get("builds", []))):
            raise ValueError(f"{slug}: example evidence did not pass")
    expected_files = {"scripts/knowledge_topic_examples.py"} | {
        str(path.relative_to(ROOT)) for path in (KNOWLEDGE / "examples").rglob("*") if path.is_file()}
    if set(evidence["source_hashes"]) != expected_files:
        raise ValueError("example evidence source set differs")
    for relative, expected_hash in evidence["source_hashes"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"stale example evidence: {relative}")
    return packs


def check():
    registry = json.loads((KNOWLEDGE / "sources.json").read_text(encoding="utf-8"))
    errors = []
    known = set()
    local_count = 0
    external_count = 0
    snapshot_count = 0
    for source in registry["sources"]:
        identifier = source["id"]
        if identifier in known:
            errors.append(f"duplicate source ID: {identifier}")
        known.add(identifier)
        if source["kind"] == "local":
            local_count += 1
            relative = Path(source["path"])
            path = (ROOT / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(ROOT):
                errors.append(f"{identifier}: source outside repository")
                continue
            if not path.is_file():
                errors.append(f"{identifier}: missing source {relative}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                errors.append(f"{identifier}: changed source {relative}; review dependent claims")
        elif source["kind"] == "external":
            external_count += 1
            if not source["url"].startswith("https://"):
                errors.append(f"{identifier}: expected HTTPS source URL")
            if source["review_status"] not in {"read", "catalogued"}:
                errors.append(f"{identifier}: invalid source review status")
            if source["review_status"] == "read" and not source.get("reviewed_on"):
                errors.append(f"{identifier}: missing reviewed_on")
            if source.get("content_snapshot"):
                try:
                    validate_snapshot(ROOT, source["content_snapshot"])
                    snapshot_count += 1
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"{identifier}: invalid external snapshot ({error})")
        else:
            errors.append(f"{identifier}: unknown source kind")

    pages = sorted(WIKI.rglob("*.md"))
    index_text = (WIKI / "index.md").read_text(encoding="utf-8")
    for path in pages:
        relative = path.relative_to(ROOT)
        try:
            values = metadata(path)
            for identifier in values["source_ids"]:
                if identifier not in known:
                    errors.append(f"{relative}: unknown source ID {identifier}")
        except (ValueError, KeyError) as error:
            errors.append(f"{relative}: {error}")
        if path.name != "index.md" and path.relative_to(WIKI).as_posix() not in index_text:
            errors.append(f"{relative}: missing index entry")

    for path in sorted(KNOWLEDGE.rglob("*.md")):
        # Code such as native[message.method](payload) is not a Markdown link.
        prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", "", path.read_text(encoding="utf-8"))
        prose = re.sub(r"`[^`\n]+`", "", prose)
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", prose):
            target = link.strip("<>").split("#", 1)[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken local link {link}")

    questions = json.loads((KNOWLEDGE / "evals/questions.json").read_text(encoding="utf-8"))
    question_ids = set()
    for item in questions["questions"]:
        if item["id"] in question_ids:
            errors.append(f"duplicate evaluation question {item['id']}")
        question_ids.add(item["id"])
        if not item.get("question") or not item.get("expected_points") or not item.get("source_ids"):
            errors.append(f"{item['id']}: incomplete evaluation criteria")
        for identifier in item.get("source_ids", []):
            if identifier not in known:
                errors.append(f"{item['id']}: unknown source ID {identifier}")
    if not questions["questions"]:
        errors.append("evaluation question list is empty")

    packs = load_packs()
    for slug, platform in packs["platforms"].items():
        for identifier in platform["source_ids"]:
            if identifier not in known:
                errors.append(f"{slug}: unknown platform source ID {identifier}")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1
    print(f"PASS local source hashes {local_count}/{local_count}; wiki pages {len(pages)}; "
          f"evaluation questions {len(question_ids)}; metadata, source IDs and local links")
    print(f"External sources {external_count}: pinned response hashes {snapshot_count}; live content not checked.")
    print(f"Platform mappings {len(packs['platforms'])}: structure checked, preparation status assessed by context.")
    print("No semantic answer evaluation or app/server/DB/UI verification was performed.")
    return 0


def search(query):
    terms = query.casefold().split()
    if not terms:
        print("Enter at least one search term.", file=sys.stderr)
        return 2
    results = []
    for path in sorted(WIKI.rglob("*.md")):
        values = metadata(path)
        body = path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        for paragraph in body.split("\n\n"):
            entries = paragraph.splitlines() if re.match(r"(?:\||\d+\.)", paragraph) else [paragraph]
            for entry in entries:
                lowered = entry.casefold()
                if all(term in lowered for term in terms):
                    score = sum(lowered.count(term) for term in terms)
                    score += sum(term in values["title"].casefold() for term in terms) * 2
                    results.append((-score, path.relative_to(ROOT).as_posix(), entry))
    for _, path, paragraph in sorted(results)[:8]:
        excerpt = " ".join(paragraph.split())
        first_match = min(excerpt.casefold().index(term) for term in terms)
        start = max(0, first_match - 100)
        print(f"{path}\n  {'…' if start else ''}{excerpt[start:start + 450]}\n")
    if not results:
        print("No matching wiki paragraph. Consult the index, sources and open questions.")
        return 1
    return 0


def topic_documents(package, requested=None, include_auth=False):
    topics = list(dict.fromkeys(requested if requested else package["default_topics"]))
    if include_auth and not requested and "auth-and-storage" not in topics:
        topics.append("auth-and-storage")
    unknown = set(topics) - set(package["topics"])
    if unknown:
        raise ValueError("unknown detailed topic: " + ", ".join(sorted(unknown)))
    return [package["index"]] + [package["topics"][topic] for topic in topics]


def context(feature_slug, platform_slug, require_ready=False, topics=None):
    if check():
        return 1
    packs = load_packs()
    if feature_slug not in packs["features"] or platform_slug not in packs["platforms"]:
        raise ValueError("unknown feature or platform")
    feature = packs["features"][feature_slug]
    platform = packs["platforms"][platform_slug]
    registry = json.loads((KNOWLEDGE / "sources.json").read_text(encoding="utf-8"))
    sources = {item["id"]: item for item in registry["sources"]}
    package = packs["packages"][platform["implementation_package"]]
    detailed = topic_documents(package, topics,
                               include_auth="wiki/shared/auth-storage.md" in feature["shared_documents"])
    documents = list(dict.fromkeys(feature["shared_documents"] +
                     [packs["languages"][slug]["document"] for slug in platform["language_packages"]] +
                     [platform["document"]] + detailed))
    selected_sources = set(platform["source_ids"])
    issues = []
    if feature["status"] == "deferred":
        issues.append("feature is deferred; implementation is outside the approved baseline")
    versions = platform["selected_versions"]
    for field in platform["required_version_fields"]:
        value = versions.get(field) if isinstance(versions, dict) else None
        if not isinstance(value, str) or not value.strip():
            issues.append(f"target version is not selected: {field}")
    for topic in feature["required_topics"] + platform["extra_required_topics"]:
        if platform["topics"][topic] != "documented":
            issues.append(f"topic {topic}: {platform['topics'][topic]}")
    issues.extend(f"decision: {item}" for item in platform["pending_decisions"])
    for relative in documents:
        values = metadata(knowledge_document(relative))
        selected_sources.update(values["source_ids"])
        if values["review_status"] != "static-reviewed":
            issues.append(f"document awaiting static review: {relative}")
    for identifier in sorted(selected_sources):
        if sources[identifier]["review_status"] != "read":
            issues.append(f"source not yet reviewed: {identifier}")

    print(f"\nContext: {feature_slug} / {platform_slug}")
    print("Preparation: " + ("NOT READY" if issues else "READY FOR IMPLEMENTATION; app execution still unverified"))
    for issue in issues:
        print(f"- {issue}")
    if issues and require_ready:
        print("No implementation context emitted because preparation is incomplete.")
        return 2
    if topics:
        print("Topic-filtered reading context; omitted topics remain necessary when relevant to implementation.")
    print("\nSelected documents only; no agent invocation or file-access isolation:")
    for relative in documents:
        path = knowledge_document(relative)
        print(f"\n--- {path.relative_to(ROOT).as_posix()} ---\n")
        print(path.read_text(encoding="utf-8"))
    print("\nSelected source records:")
    for identifier in sorted(selected_sources):
        source = sources[identifier]
        location = source.get("path", source.get("url"))
        print(f"{identifier}: {location} [{source['review_status']}; {source.get('reviewed_on')}]")
        if source.get("content_snapshot"):
            snapshot = source["content_snapshot"]
            print(f"  pinned snapshot: {snapshot['path']} [sha256 {snapshot['sha256']}]")
    return 0


def language_package(slug):
    if check():
        return 1
    packs = load_packs()
    if slug not in packs["languages"]:
        raise ValueError("unknown language package")
    path = knowledge_document(packs["languages"][slug]["document"])
    print(f"--- {path.relative_to(ROOT)} ---\n\n{path.read_text()}")
    return 0


def detailed_package(slug, topics=None):
    if check():
        return 1
    packs = load_packs()
    if slug not in packs["packages"]:
        raise ValueError("unknown detailed package")
    package = packs["packages"][slug]
    # Direct package reading includes all topics unless the caller narrows the selection.
    for relative in topic_documents(package, topics or list(package["topics"])):
        path = knowledge_document(relative)
        print(f"--- {path.relative_to(ROOT)} ---\n\n{path.read_text()}")
    print("Reading package only; target app preparation/readiness is not certified.")
    return 0


def coverage(as_json=False):
    # Structural completeness is deliberately separate from target app readiness.
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        if check():
            raise ValueError("knowledge integrity check failed; run check for details")
    packs = load_packs()
    service = json.loads((KNOWLEDGE / "service-map.json").read_text())
    identifiers = {feature["feature_id"] for feature in service["features"].values()}
    if identifiers != {f"F{i:02}" for i in range(1, 15)}:
        raise ValueError("service knowledge must cover F01-F14, including deferred F14")
    for slug, feature in service["features"].items():
        if slug not in packs["features"] or feature["document"] not in packs["features"][slug]["shared_documents"]:
            raise ValueError(f"feature has no context mapping: {slug}")
        knowledge_document(feature["document"])
    required = set(packs["baseline_documents"])
    for relative in required:
        if metadata(knowledge_document(relative))["review_status"] != "static-reviewed":
            raise ValueError(f"baseline document awaiting static review: {relative}")
    registry = json.loads((KNOWLEDGE / "sources.json").read_text())
    external = [source for source in registry["sources"] if source["kind"] == "external"]
    missing = [source["id"] for source in external if not source.get("content_snapshot")]
    if missing:
        raise ValueError("external snapshots not pinned: " + ", ".join(missing))
    for relative in ("contracts/api-index.json", "contracts/stock-search-price.json"):
        if not (KNOWLEDGE / relative).is_file():
            raise ValueError(f"missing contract artifact: {relative}")
    inventory = build_inventory(ROOT)
    if json.loads((KNOWLEDGE / "contracts/api-index.json").read_text()) != inventory:
        raise ValueError("API inventory differs from original source")
    if (sum(feature["handler_count"] for feature in service["features"].values()) != inventory["handler_count"] or
            sum(feature["route_count"] for feature in service["features"].values()) != inventory["expanded_route_count"]):
        raise ValueError("feature-to-API coverage totals differ")
    result = {"baseline_structure_complete": True,
              "scope": "F01-F13, F14 deferred; five language and five platform knowledge packages",
              "service_features": len(identifiers), "language_packages": len(packs["languages"]),
              "platform_packages": len(packs["platforms"]), "required_documents": len(required),
              "detailed_packages": len(packs["packages"]),
              "detailed_topic_documents": sum(len(package["topics"]) for package in packs["packages"].values()),
              "external_sources_pinned": len(external),
              "controller_count": inventory["controller_count"], "handler_count": inventory["handler_count"],
              "expanded_route_count": inventory["expanded_route_count"],
              "implementation_readiness": "Use context --require-ready per feature/platform; not certified by coverage",
              "independent_semantic_evaluation": "not-run", "target_app_runtime_validation": "not-run"}
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PASS baseline structure: 14 feature entries, 5 language packages, 5 platform packages")
        print(f"Required documents {len(required)}; external snapshots {len(external)}/{len(external)}")
        print("This does not certify semantic accuracy, implementation readiness or target app execution.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="read-only source and document checks")
    coverage_parser = subparsers.add_parser("coverage", help="check bounded baseline coverage, not app readiness")
    coverage_parser.add_argument("--json", action="store_true")
    package_parser = subparsers.add_parser("package", help="read a language hub or detailed language/platform package")
    package_selection = package_parser.add_mutually_exclusive_group(required=True)
    package_selection.add_argument("--language")
    package_selection.add_argument("--package", dest="package_slug")
    package_parser.add_argument("--topic", action="append", help="repeat to narrow a detailed package")
    search_parser = subparsers.add_parser("search", help="all query terms must occur in a paragraph")
    search_parser.add_argument("query")
    context_parser = subparsers.add_parser("context", help="select common feature knowledge and one platform")
    context_parser.add_argument("--feature", required=True)
    context_parser.add_argument("--platform", required=True)
    context_parser.add_argument("--require-ready", action="store_true")
    context_parser.add_argument("--topic", action="append", help="repeat for a topic-filtered reading context")
    args = parser.parse_args()
    try:
        if args.command == "check":
            return check()
        if args.command == "search":
            return search(args.query)
        if args.command == "package":
            if args.language:
                if args.topic:
                    raise ValueError("--topic requires --package; --language selects the stable overview hub")
                return language_package(args.language)
            return detailed_package(args.package_slug, args.topic)
        if args.command == "coverage":
            return coverage(args.json)
        return context(args.feature, args.platform, args.require_ready, args.topic)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL knowledge data: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
