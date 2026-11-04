#!/usr/bin/env python3
"""Loopback-only synthetic iOS fixture. No credentials, DB, or provider execution.
No request payloads, cookies, or token values are logged. Never run on a public bind.
Compatible with the existing two delayed-quote UI cases plus next-verification cases.
"""
import argparse
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock
import time
from urllib.parse import parse_qs, urlsplit

LOCK = Lock()
COUNTS = {"feedbackAccepted": 0, "feedbackRejected": 0, "csrfRejected": 0, "calculate": 0, "memberMutation": 0}
STOCK = {"assetId": 1, "assetCode": "005930", "name": "삼성전자", "category": "STOCK", "market": "KOSPI", "currency": "KRW"}
NEWS = {"id": 71, "title": "검증용 시장 이슈", "category": "STOCK", "publishedAt": "2026-10-24T09:00:00", "content": "검증용 상세 본문입니다.", "sources": [{"name": "검증용 출처", "url": "https://example.org/source"}]}
SEARCH = {**NEWS, "id": 72, "title": "검색 전용 결과"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, body=None):
        data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def count(self, key):
        with LOCK:
            COUNTS[key] += 1

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        if path == "/__state":
            with LOCK:
                result = dict(COUNTS)
            return self.send(200, result)
        if path == "/api/auth/csrf":
            return self.send(200, {"headerName": "X-CSRF-TOKEN", "token": "synthetic-loopback-only"})
        if path == "/api/users/me":
            return self.send(401, {"code": "UNAUTHORIZED"})
        if path == "/api/stocks":
            return self.send(200, {"stocks": [STOCK] if query.get("q") == ["삼성"] else []})
        if path == "/api/stocks/1/price":
            time.sleep(2.5)
            # Raw numeric spelling matters for the existing unitPrice UI assertion.
            data = b'{"assetId":1,"assetCode":"005930","name":"Samsung","closePrice":123.4500,"baseDate":"2026-10-24","currency":"KRW"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if path in ("/api/news", "/api/news/today"):
            return self.send(200, {"items": [NEWS], "page": 1, "size": 12, "totalPages": 1, "totalElements": 1, "hasNext": False})
        if path == "/api/search/news":
            # Real search contract uses content, deliberately no items fallback.
            return self.send(200, {"content": [SEARCH] if query.get("q") == ["시장"] else [], "page": 1, "totalPages": 1, "hasNext": False})
        if path in ("/api/news/71", "/api/news/72"):
            return self.send(200, NEWS if path.endswith("71") else SEARCH)
        if path.endswith("/keywords") and path.startswith("/api/news/"):
            return self.send(200, {"keywords": [{"keyword": "검증 키워드", "definition": "검증용 정의", "context": "검증용 맥락", "watchPoint": "검증용 관찰점"}]})
        if path.endswith("/market-analysis") and path.startswith("/api/news/"):
            return self.send(200, {"risk": "검증용 위험 요인", "watchPoint": "검증용 분석 관찰점"})
        return self.send(404, {"code": "FIXTURE_ROUTE_NOT_FOUND"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if self.headers.get("X-CSRF-TOKEN") != "synthetic-loopback-only":
            self.count("csrfRejected")
            return self.send(403, {"code": "CSRF_INVALID"})
        if path == "/api/auth/refresh":
            return self.send(401, {"code": "UNAUTHORIZED"})
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65536:
            return self.send(413, {"code": "TOO_LARGE"})
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, TypeError):
            return self.send(400, {"code": "INVALID_JSON"})
        if path == "/api/feedback":
            if not isinstance(payload, dict) or payload.get("pagePath") != "/ios/account" or not isinstance(payload.get("content"), str):
                return self.send(400, {"code": "INVALID_FEEDBACK"})
            if payload["content"] == "fixture-reject":
                self.count("feedbackRejected")
                return self.send(422, {"code": "FIXTURE_REJECT", "message": "검증용 피드백 거절"})
            if payload["content"] != "UI fixture feedback":
                return self.send(400, {"code": "UNEXPECTED_SYNTHETIC_INPUT"})
            self.count("feedbackAccepted")
            return self.send(204)
        if path == "/api/portfolio/calculate":
            if not isinstance(payload, dict) or not isinstance(payload.get("holdings"), list):
                return self.send(400, {"code": "INVALID_HOLDINGS"})
            self.count("calculate")
            rows = []
            total = Decimal(0)
            for holding in payload["holdings"]:
                cost = Decimal(str(holding["averagePurchasePrice"])) * int(holding["quantity"])
                total += cost
                rows.append({**holding, "priceAvailable": True, "evaluationAmount": str(cost), "returnRate": 0, "baseDate": "2026-10-24"})
            return self.send(200, {"holdings": rows, "pricingStatus": "COMPLETE", "totalPurchaseAmount": str(total), "totalEvaluationAmount": str(total), "totalProfitLoss": 0})
        if path.startswith("/api/portfolio/transactions"):
            self.count("memberMutation")
            return self.send(401, {"code": "GUEST_MUST_NOT_WRITE_MEMBER_LEDGER"})
        return self.send(404, {"code": "FIXTURE_ROUTE_NOT_FOUND"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18097)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic iOS fixture http://127.0.0.1:{args.port}; no Rust/DB evidence", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
