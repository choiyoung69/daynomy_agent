#!/usr/bin/env python3
"""Compile the actual production route helper. Host evidence, never UI evidence."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
source = (ROOT / "clients/ios/DaynomyIOS/DiscoveryView.swift").read_text()
helper = source[source.index("func relatedNewsID"):source.index("let newsCategories")]
with tempfile.TemporaryDirectory(prefix="ios-news-route-") as folder:
    temporary = Path(folder)
    extracted = temporary / "ProductionNewsRoute.swift"
    extracted.write_text("import Foundation\n" + helper)
    binary = temporary / "news-route-contract"
    result = subprocess.run([
        "swiftc", "-swift-version", "6", "-parse-as-library",
        "-module-cache-path", "/tmp/ios-sdk-route-cache",
        str(extracted), str(HERE / "NewsRouteContract.swift"), "-o", str(binary),
    ], cwd=ROOT)
    if result.returncode == 0:
        result = subprocess.run([str(binary)], cwd=ROOT)
    sys.exit(result.returncode)
