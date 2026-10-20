#!/usr/bin/env python3
"""Local HTTP + PostgreSQL acceptance gate; never deletes test data."""
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
INVALID = "요청값이 올바르지 않습니다."
REASONS = {
    "content_blank": ("content", "피드백 내용을 입력해주세요."),
    "content_long": ("content", "피드백은 1000자 이하여야 합니다."),
    "path_blank": ("pagePath", "작성 화면 경로가 필요합니다."),
    "path_long": ("pagePath", "작성 화면 경로는 2048자 이하여야 합니다."),
    "body": ("requestBody", "요청 본문을 읽을 수 없습니다."),
}


class EnvironmentFailure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_local_url(value, database=False):
    try:
        url = parse.urlsplit(value)
        # Accessing port also validates malformed port strings.
        _ = url.port
    except ValueError:
        raise EnvironmentFailure("Malformed local URL (value withheld)") from None
    schemes = ("postgres", "postgresql") if database else ("http",)
    if url.scheme not in schemes or url.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise EnvironmentFailure("Only loopback test endpoints are allowed")
    if url.query or url.fragment:
        raise EnvironmentFailure("URL query/fragment options are not supported")
    if database:
        if not url.path[1:].endswith("_test") or "/" in url.path[1:]:
            raise EnvironmentFailure("Use a dedicated database with a name ending in _test")
    elif url.username or url.password or url.path not in ("", "/"):
        raise EnvironmentFailure("HTTP base URL must not contain credentials or a path")
    return value.rstrip("/") if not database else value


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base_url):
        self.base_url = base_url
        self.cookies = http.cookiejar.CookieJar()
        self.opener = request.build_opener(
            request.ProxyHandler({}), NoRedirect(), request.HTTPCookieProcessor(self.cookies)
        )

    def send(self, path, data=None, headers=None):
        req = request.Request(self.base_url + path, data=data, headers=headers or {})
        try:
            response = self.opener.open(req, timeout=5)
        except error.HTTPError as exc:
            response = exc
        except (error.URLError, TimeoutError, OSError):
            raise EnvironmentFailure("HTTP connection failed (details withheld)") from None
        with response:
            return response.status, response.headers, response.read(65537)

    def csrf(self):
        status, headers, body = self.send("/api/auth/csrf")
        require(status == 200, "CSRF GET must return 200")
        require("application/json" in headers.get("Content-Type", ""), "CSRF must be JSON")
        payload = json.loads(body)
        require(isinstance(payload, dict), "CSRF response must be an object")
        for key in ("headerName", "token"):
            require(isinstance(payload.get(key), str) and bool(payload[key]), "Missing CSRF " + key)
        require(any(cookie.value for cookie in self.cookies), "CSRF must issue a cookie")
        return payload["headerName"], payload["token"]


class Database:
    def __init__(self, url):
        if not shutil.which("psql"):
            raise EnvironmentFailure("psql is required")
        endpoint = parse.urlsplit(validate_local_url(url, database=True))
        self.env = os.environ.copy()
        # PGDATABASE does not expand a URI as psql --dbname does. Pass libpq's
        # individual connection variables and keep credentials out of argv/logs.
        for key in ("PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGUSER", "PGPASSWORD"):
            self.env.pop(key, None)
        self.env["PGHOST"] = endpoint.hostname
        self.env["PGPORT"] = str(endpoint.port or 5432)
        self.env["PGDATABASE"] = parse.unquote(endpoint.path[1:])
        if endpoint.username is not None:
            self.env["PGUSER"] = parse.unquote(endpoint.username)
        if endpoint.password is not None:
            self.env["PGPASSWORD"] = parse.unquote(endpoint.password)
        self.env["PGCONNECT_TIMEOUT"] = "5"
        self.env["PGOPTIONS"] = "-c default_transaction_read_only=on -c statement_timeout=5000"

    def query(self, sql):
        try:
            result = subprocess.run(
                ["psql", "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1"],
                input=sql, text=True, capture_output=True, env=self.env, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise EnvironmentFailure("Database command unavailable/timed out") from None
        if result.returncode:
            raise EnvironmentFailure("Read-only test DB query failed (details withheld)")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise EnvironmentFailure("Unexpected DB result format") from None

    def snapshot(self):
        return self.query(
            "SELECT json_build_object('count',count(*),'max_id',coalesce(max(id),0)) "
            "FROM feedbacks;"
        )

    def new_rows(self, previous_max):
        return self.query(
            "SELECT coalesce(json_agg(t),'[]'::json) FROM "
            "(SELECT id,content,page_path,status,created_at,updated_at FROM feedbacks "
            f"WHERE id > {int(previous_max)} ORDER BY id) t;"
        )


def check_response(status, headers, body, expected_status, expected_errors=()):
    require(status == expected_status, f"Expected HTTP {expected_status}, got {status}")
    if status == 204:
        require(body == b"", "204 must have no body")
        return
    require("application/json" in headers.get("Content-Type", ""), "Error must be JSON")
    value = json.loads(body)
    require(isinstance(value, dict), "Error must be an object")
    if status == 403:
        require(value == {"code": "FORBIDDEN", "message": "접근 권한이 없습니다."},
                "Incorrect forbidden response")
        return
    require(value.get("code") == "INVALID_REQUEST", "Incorrect validation code")
    require(value.get("message") == INVALID, "Incorrect validation message")
    fields = value.get("errors")
    require(isinstance(fields, list) and fields, "Missing validation fields")
    require(all(isinstance(item, dict) and set(item) == {"field", "reason"} for item in fields),
            "Errors must contain only field/reason")
    actual = {(item["field"], item["reason"]) for item in fields}
    require(actual == set(expected_errors), "Incorrect validation fields/reasons")


def check_storage(before, after, rows, expected):
    if expected is None:
        require(after == before and rows == [], "Failed request changed the database")
        return
    require(after["count"] == before["count"] + 1, "Success must insert exactly one row")
    require(len(rows) == 1, "Expected one newly generated row")
    row = rows[0]
    require(row["id"] > before["max_id"] and after["max_id"] == row["id"], "ID not generated")
    require(row["content"] == expected[0] and row["page_path"] == expected[1],
            "Stored text does not match the contract")
    require(row["status"] == "PENDING", "Initial status must be PENDING")
    for key in ("created_at", "updated_at"):
        require(isinstance(row[key], str) and bool(row[key]), "Missing " + key)
        datetime.fromisoformat(row[key].replace("Z", "+00:00"))


def cases():
    good = {"content": "화면이 좋아요.", "pagePath": "/news/1"}
    result = []

    def add(name, payload, expected=None, errors=(), mode="valid", raw=False):
        status = 403 if mode != "valid" else (204 if expected is not None else 400)
        result.append((name, payload, status, expected, errors, mode, raw))

    for mode in ("none", "cookie-only", "header-only", "mismatch"):
        add("csrf-" + mode, good, mode=mode)
    add("csrf-before-validation", {}, mode="none")
    add("normal", good, (good["content"], good["pagePath"]))
    add("strip", {"content": " \t화면이 좋아요.\n", "pagePath": " /news/1\t"},
        ("화면이 좋아요.", "/news/1"))
    add("internal-whitespace", {"content": "a  b\nc", "pagePath": "relative path"},
        ("a  b\nc", "relative path"))
    add("java-em-space", {"content": "\u2003hello\u2003", "pagePath": "/x"}, ("hello", "/x"))
    add("java-nbsp-preserved", {"content": "\u00a0hello\u00a0", "pagePath": "/x"},
        ("\u00a0hello\u00a0", "/x"))
    for field, blank, long, limit in (
        ("content", "content_blank", "content_long", 1000),
        ("pagePath", "path_blank", "path_long", 2048),
    ):
        for name, value in (("null", None), ("empty", ""), ("blank", " \t\n"),
                            ("unicode-blank", "\u2003")):
            add(field + "-" + name, {**good, field: value}, errors=(REASONS[blank],))
        missing = dict(good)
        del missing[field]
        add(field + "-missing", missing, errors=(REASONS[blank],))
        maximum = {**good, field: "가" * limit}
        add(field + "-max", maximum, (maximum["content"], maximum["pagePath"]))
        add(field + "-too-long", {**good, field: "가" * (limit + 1)}, errors=(REASONS[long],))
        add(field + "-validate-before-strip", {**good, field: " " + "가" * limit},
            errors=(REASONS[long],))
    add("emoji-max", {**good, "content": "😀" * 500}, ("😀" * 500, good["pagePath"]))
    add("emoji-too-long", {**good, "content": "😀" * 501}, errors=(REASONS["content_long"],))
    add("both-fields-missing", {}, errors=(REASONS["content_blank"], REASONS["path_blank"]))
    add("malformed-json", b'{"content":', errors=(REASONS["body"],), raw=True)
    add("empty-body", b"", errors=(REASONS["body"],), raw=True)
    add("duplicate-1", good, (good["content"], good["pagePath"]))
    add("duplicate-2", good, (good["content"], good["pagePath"]))
    return result


def main():
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "results": []}
    exit_code = 0
    try:
        base = validate_local_url(os.environ.get("PILOT_BASE_URL", ""))
        db_url = validate_local_url(os.environ.get("PILOT_TEST_DB_URL", ""), database=True)
        db = Database(db_url)
        db.snapshot()
        client = Client(base)
        header, token = client.csrf()
        _, other_token = Client(base).csrf()
        require(token != other_token, "Fresh clients must not share a constant CSRF token")
        report["results"].append({"case": "csrf-setup", "passed": True})
        for name, payload, status, expected, errors, mode, raw in cases():
            before = db.snapshot()
            sender = Client(base) if mode in ("none", "header-only") else client
            headers = {"Content-Type": "application/json"}
            if mode in ("valid", "header-only", "mismatch"):
                headers[header] = token + "-mismatch" if mode == "mismatch" else token
            data = payload if raw else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            actual_status, actual_headers, body = sender.send("/api/feedback", data, headers)
            after = db.snapshot()
            rows = db.new_rows(before["max_id"])
            failures = []
            for label, check in (
                ("response", lambda: check_response(actual_status, actual_headers, body, status, errors)),
                ("storage", lambda: check_storage(before, after, rows, expected)),
            ):
                try:
                    check()
                except AssertionError as exc:
                    # Do not emit request/response payloads or database row values.
                    failures.append({"check": label, "reason": str(exc)})
                except (ValueError, KeyError, TypeError):
                    failures.append({"check": label, "reason": "Invalid result shape"})
            passed = not failures
            report["results"].append({"case": name, "passed": passed, "failures": failures})
            print(("PASS " if passed else "FAIL ") + name)
            if not passed:
                exit_code = 1
    except EnvironmentFailure as exc:
        report["environment_error"] = str(exc)
        print("BLOCKED: " + str(exc), file=sys.stderr)
        exit_code = 2
    except (AssertionError, ValueError, KeyError, TypeError):
        report["results"].append({"case": "csrf-setup", "passed": False})
        print("FAIL csrf-setup", file=sys.stderr)
        exit_code = 1
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["exit_code"] = exit_code
    report["complete"] = exit_code == 0 and len(report["results"]) == len(cases()) + 1
    output = ROOT / "runs" / ("acceptance-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Report: " + str(output.relative_to(ROOT)))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
