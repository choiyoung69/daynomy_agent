#!/usr/bin/env python3
"""Send identical feedback bodies to two real servers; compare HTTP and DB effects."""
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from acceptance import (
    Client, Database, EnvironmentFailure, shared_cases, policy_cases, check_response,
    check_storage, require, validate_local_url,
)

ROOT = Path(__file__).resolve().parents[1]

# Exact, observed Spring behavior for the explicitly approved Rust differences.
# Each side must satisfy its own HTTP/body/storage expectation; no blanket skip.
SPRING_POLICY_STORAGE = {
    "numeric-content": ("123", "/probe"),
    "boolean-content": ("true", "/probe"),
    "duplicate-content-key": ("second", "/probe"),
    "duplicate-same-content-key": ("same", "/probe"),
    "duplicate-escaped-content-key": ("second", "/probe"),
    "duplicate-page-path-key": ("probe", "/second"),
    "duplicate-unknown-key": ("probe", "/probe"),
    "duplicate-nested-key": ("probe", "/probe"),
}


def response_shape(status, headers, body):
    media = headers.get("Content-Type", "").split(";")[0].strip().lower()
    value = json.loads(body) if media == "application/json" and body else body.decode("utf-8")
    # JSON key order and validation-error order are not part of the contract.
    # Preserve duplicates and every other field; do not normalize away differences.
    if isinstance(value, dict) and isinstance(value.get("errors"), list):
        value["errors"] = sorted(value["errors"], key=lambda v: json.dumps(v, sort_keys=True))
    return {"status": status, "media_type": media, "body": value}


def storage_shape(before, after, rows):
    return {
        "added_count": after["count"] - before["count"],
        "rows": [
            {key: row[key] for key in ("content", "page_path", "status")}
            for row in rows
        ],
        "generated_ids": (
            len({row["id"] for row in rows}) == len(rows)
            and all(row["id"] > before["max_id"] for row in rows)
            and after["max_id"] == max([before["max_id"]] + [row["id"] for row in rows])
        ),
        "timestamps_present": all(row["created_at"] and row["updated_at"] for row in rows),
    }


def difference_fields(left, right):
    """Return field names, never potentially sensitive values."""
    return [key for key in left if left[key] != right[key]]


def probes():
    # Remaining exploratory behavior, outside the approved policy cases.
    for name, payload, raw in [
        ("unknown-field", {"content": "probe", "pagePath": "/probe", "extra": 1}, False),
        ("trailing-json", b'{"content":"probe","pagePath":"/probe"} {}', True),
        ("null-document", b"null", True),
        ("array-document", b"[]", True),
    ]:
        yield name, payload, None, None, (), "valid", raw


class Endpoint:
    def __init__(self, base, db_url):
        self.base = validate_local_url(base)
        self.db = Database(db_url)
        self.client = Client(self.base)
        self.header, self.token = self.client.csrf()
        _, other = Client(self.base).csrf()
        require(self.token != other, "Fresh CSRF clients must receive different tokens")

    def observe(self, payload, mode, raw):
        before = self.db.snapshot()
        sender = Client(self.base) if mode in ("none", "header-only") else self.client
        headers = {"Content-Type": "application/json"}
        if mode in ("valid", "header-only", "mismatch"):
            headers[self.header] = self.token + "-mismatch" if mode == "mismatch" else self.token
        data = payload if raw else json.dumps(payload, ensure_ascii=False).encode()
        status, received, body = sender.send("/api/feedback", data, headers)
        after = self.db.snapshot()
        rows = self.db.new_rows(before["max_id"])
        return status, received, body, before, after, rows


def independent_contract_check(observation, status, expected, errors):
    actual_status, headers, body, before, after, rows = observation
    failures = []
    for name, check in [
        ("response", lambda: check_response(actual_status, headers, body, status, errors)),
        ("storage", lambda: check_storage(before, after, rows, expected)),
    ]:
        try:
            check()
        except (AssertionError, ValueError, KeyError, TypeError):
            failures.append(name)
    return failures


def assess_case(group, case, observations):
    name, _, status, expected, errors, _, _ = case
    http = [response_shape(*o[:3]) for o in observations]
    storage = [storage_shape(*o[3:]) for o in observations]
    differences = ["http." + field for field in difference_fields(*http)]
    differences += ["db." + field for field in difference_fields(*storage)]
    if group == "policy":
        failures = [
            independent_contract_check(observations[0], 204, SPRING_POLICY_STORAGE[name], ()),
            independent_contract_check(observations[1], status, expected, errors),
        ]
        passed = bool(differences) and not any(failures)
        outcome = "EXPECTED_DIFFERENCE" if passed else "FAIL"
    else:
        failures = [independent_contract_check(o, status, expected, errors)
                    if group == "contract" else [] for o in observations]
        passed = not differences and not any(failures)
        outcome = "MATCH" if passed else "FAIL"
    item = {"case": name, "group": group, "match": not differences,
            "differences": differences, "checks_pass": passed, "outcome": outcome,
            "contract_pass": not any(failures) if group != "probe" else None}
    for label, o, failed, stored in zip(("spring", "rust"), observations, failures, storage):
        item[label] = {"http_status": o[0], "rows_before": o[3]["count"],
                       "rows_after": o[4]["count"], "contract_failures": failed,
                       "generated_ids": stored["generated_ids"],
                       "timestamps_present": stored["timestamps_present"]}
    return item


def main():
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "results": [],
              "normalization": ["JSON key order", "validation error order",
                                "generated IDs/timestamps compared by invariants",
                                "per-server CSRF token/cookie values"],
              "complete": False}
    source_manifest = ROOT / ".local/comparison/source-snapshot.json"
    if source_manifest.is_file():
        report["source_manifest_sha256"] = hashlib.sha256(source_manifest.read_bytes()).hexdigest()
    exit_code = 2
    try:
        spring_url = validate_local_url(os.environ.get("COMPARE_SPRING_DB_URL", ""), database=True)
        rust_url = validate_local_url(os.environ.get("COMPARE_RUST_DB_URL", ""), database=True)
        require(urlsplit(spring_url).path != urlsplit(rust_url).path,
                "Use separate database names for comparison")
        spring_base = validate_local_url(os.environ.get("COMPARE_SPRING_BASE_URL", ""))
        rust_base = validate_local_url(os.environ.get("COMPARE_RUST_BASE_URL", ""))
        require(spring_base != rust_base, "Use separate HTTP endpoints")
        endpoints = [Endpoint(spring_base, spring_url), Endpoint(rust_base, rust_url)]
        header_match = endpoints[0].header == endpoints[1].header
        report["results"].append({"case": "csrf-setup", "group": "contract",
                                  "match": header_match, "contract_pass": True,
                                  "checks_pass": header_match,
                                  "outcome": "MATCH" if header_match else "FAIL"})
        print(("MATCH " if header_match else "DIFFERENCE ") + "csrf-setup", flush=True)
        all_cases = ([("contract", c) for c in shared_cases()]
                     + [("policy", c) for c in policy_cases()]
                     + [("probe", c) for c in probes()])
        for group, case in all_cases:
            name, payload, _, _, _, mode, raw = case
            observations = [endpoint.observe(payload, mode, raw) for endpoint in endpoints]
            item = assess_case(group, case, observations)
            report["results"].append(item)
            print(f'{item["outcome"]} {group}/{name}: '
                  f'Spring {observations[0][0]}, Rust {observations[1][0]}', flush=True)
        report["complete"] = True
        report["summary"] = dict(Counter(
            f'{r["group"]}_{r["outcome"].lower()}' for r in report["results"]
        ))
        report["contract_pass"] = all(
            r["checks_pass"] for r in report["results"] if r["group"] != "probe"
        )
        report["full_match"] = all(r["match"] for r in report["results"])
        report["checks_pass"] = all(r["checks_pass"] for r in report["results"])
        # Approved differences remain visible. Unexpected results still fail.
        exit_code = 0 if report["checks_pass"] else 1
    except (EnvironmentFailure, AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        report["blocked_by"] = type(exc).__name__
        print("BLOCKED comparison: " + type(exc).__name__, flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = exit_code
    output = ROOT / "runs" / ("comparison-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Report: " + str(output.relative_to(ROOT)), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
