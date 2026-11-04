#!/usr/bin/env python3
"""Real-loopback wrapper smoke; no app/UI/Rust/DB execution."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("delayed_fixture", Path(__file__).resolve().parents[1] / "ui_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
server = fixture.original.ThreadingHTTPServer(("127.0.0.1", 0), fixture.Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"


def request(path, body=None, csrf=False):
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-TOKEN"] = "synthetic-loopback-only"
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(Request(base + path, data=data, headers=headers), timeout=6) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


try:
    started = time.monotonic()
    status, body = request("/api/stocks?q=%EC%82%BC%EC%84%B1")
    elapsed = time.monotonic() - started
    assert status == 200 and json.loads(body) == {"stocks": [fixture.original.STOCK]}
    assert elapsed >= 2.9, "default pending-search prerequisite requires three-second latency"
    assert request("/api/users/me")[0] == 401
    assert request("/api/news/71")[0] == 200
    feedback = {"content": "UI fixture feedback", "pagePath": "/ios/account"}
    assert request("/api/feedback", feedback)[0] == 403
    assert request("/api/feedback", feedback, True) == (204, b"")
    assert request("/api/feedback", {**feedback, "content": "fixture-reject"}, True)[0] == 422
    assert request("/api/portfolio/calculate", {"holdings": [{"assetId": 1, "quantity": 2, "averagePurchasePrice": 110}]}, True)[0] == 200
    print("PASS delayed fixture real-loopback: stock latency >= 2.9s; original stock/news/auth/CSRF/feedback/calculate preserved; no app/UI/Rust/DB execution")
finally:
    server.shutdown()
    server.server_close()
