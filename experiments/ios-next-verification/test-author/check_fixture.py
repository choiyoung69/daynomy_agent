#!/usr/bin/env python3
"""Fixture's own real-loopback smoke; not application integration evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("fixture", Path(__file__).with_name("ui_fixture.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
server = fixture.ThreadingHTTPServer(("127.0.0.1", 0), fixture.Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"
def request(path, body=None, csrf=False):
    headers = {"Content-Type": "application/json"}
    if csrf: headers["X-CSRF-TOKEN"] = "synthetic-loopback-only"
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(Request(base + path, data=data, headers=headers), timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
try:
    assert request("/api/users/me")[0] == 401
    assert request("/api/auth/refresh", {}, True)[0] == 401
    assert request("/api/stocks?q=%EC%82%BC%EC%84%B1")[0] == 200
    started = time.monotonic()
    status, quote = request("/api/stocks/1/price")
    assert status == 200 and b'123.4500' in quote and time.monotonic() - started >= 2
    assert json.loads(quote)["baseDate"] == "2026-10-24"
    feedback = {"content": "UI fixture feedback", "pagePath": "/ios/account"}
    assert request("/api/feedback", feedback)[0] == 403
    assert request("/api/feedback", feedback, True) == (204, b"")
    assert request("/api/feedback", {**feedback, "content": "fixture-reject"}, True)[0] == 422
    assert request("/api/portfolio/calculate", {"holdings": [{"assetId": 1, "quantity": 2, "averagePurchasePrice": 110}]}, True)[0] == 200
    status, search = request("/api/search/news?q=%EC%8B%9C%EC%9E%A5")
    search = json.loads(search)
    assert status == 200 and len(search["content"]) == 1 and "items" not in search
    assert request("/api/news/71")[0] == 200
    assert request("/api/news/71/keywords")[0] == 200
    assert request("/api/news/71/market-analysis")[0] == 200
    counters = json.loads(request("/__state")[1])
    assert counters == {"feedbackAccepted": 1, "feedbackRejected": 1, "csrfRejected": 1, "calculate": 1, "memberMutation": 0}
    print("PASS fixture real-loopback smoke; no app/UI/Rust/DB execution")
finally:
    server.shutdown()
    server.server_close()
