#!/usr/bin/env python3
"""Add controlled stock-search latency to the unchanged synthetic iOS fixture.

All response bodies, CSRF checks, feedback validation, and quote latency remain
owned by the original Handler. Loopback fixture only; never Rust/DB evidence.
"""
import argparse
import importlib.util
import math
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
ORIGINAL = Path(__file__).resolve().parents[1] / "ios-next-verification/test-author/ui_fixture.py"
spec = importlib.util.spec_from_file_location("daynomy_original_ios_fixture", ORIGINAL)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


class Handler(original.Handler):
    stock_delay = 3.0

    def do_GET(self):
        if urlsplit(self.path).path == "/api/stocks":
            time.sleep(self.stock_delay)
        super().do_GET()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18097)
    parser.add_argument("--stock-delay", type=float, default=3.0)
    args = parser.parse_args()
    if not math.isfinite(args.stock_delay) or args.stock_delay < 0:
        parser.error("--stock-delay must be a finite nonnegative number")
    Handler.stock_delay = args.stock_delay
    server = original.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic iOS fixture http://127.0.0.1:{args.port}; stock delay {args.stock_delay:g}s; no Rust/DB evidence", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
