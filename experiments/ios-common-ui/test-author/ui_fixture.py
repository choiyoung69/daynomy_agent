#!/usr/bin/env python3
"""Additive synthetic common-UI fixture; original auth/CSRF/write checks preserved."""
import argparse
import base64
import importlib.util
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parents[2] / "ios-sdk-verification/ui_fixture.py"
spec = importlib.util.spec_from_file_location("sdk_fixture", BASE)
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)
# Deliberately synthetic photo bytes, never copied into app product data.
PHOTO = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
JPEG_PHOTO = Path(__file__).with_name("assets").joinpath("news-photo-fixture.jpg").read_bytes()
ARTICLES = [{**sdk.original.NEWS, "id": 171 + index, "title": f"검증용 오늘 기사 {index + 1}",
             "imageUrl": "/fixture/photo.jpg" if index == 0 else ("/fixture/missing.png" if index == 2 else None)}
            for index in range(11)]


class Handler(sdk.Handler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/fixture/photo.jpg":
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(JPEG_PHOTO)))
            self.end_headers()
            self.wfile.write(JPEG_PHOTO)
            return
        if parsed.path == "/fixture/photo.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PHOTO)))
            self.end_headers()
            self.wfile.write(PHOTO)
            return
        if parsed.path == "/api/news/today":
            return self.send(200, {"items": ARTICLES, "page": 1, "size": 12, "totalPages": 1, "totalElements": 11, "hasNext": False})
        if parsed.path.startswith("/api/news/") and parsed.path.removeprefix("/api/news/").isdigit():
            article = next((item for item in ARTICLES if str(item["id"]) == parsed.path.rsplit("/", 1)[1]), None)
            if article:
                return self.send(200, article)
        if parsed.path == "/api/search/news" and parse_qs(parsed.query).get("q") == ["실패"]:
            return self.send(503, {"code": "SYNTHETIC_SEARCH_FAILURE", "message": "검증용 검색 장애"})
        return super().do_GET()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18097)
    args = parser.parse_args()
    server = sdk.original.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic common UI fixture on loopback:{args.port}; no Rust/DB evidence", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
