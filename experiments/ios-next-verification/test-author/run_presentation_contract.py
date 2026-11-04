#!/usr/bin/env python3
"""Independent new presentation contract. Does not edit the existing host tests."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="ios-presentation-") as folder:
    binary = str(Path(folder) / "contract")
    sources = sorted((ROOT / "clients/ios/Sources/DaynomyCore").glob("*.swift"))
    command = ["swiftc", "-swift-version", "6", "-parse-as-library", "-module-cache-path", "/tmp/ios-next-contract-cache", *map(str, sources), str(HERE / "NewsPresentationContract.swift"), "-o", binary]
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode == 0:
        result = subprocess.run([binary], cwd=ROOT)
    sys.exit(result.returncode)
