#!/usr/bin/env python3
"""Cargo target runner: execute candidate tests with read-only filesystem access."""
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 2:
        print("Missing Rust test executable.", file=sys.stderr)
        return 2
    command = [
        "codex", "sandbox", "-P", "daynomy_test", "-C", str(ROOT), "-c",
        'permissions.daynomy_test={filesystem={":root"="read"},network={enabled=false}}',
        *sys.argv[1:],
    ]
    try:
        # Preserve Cargo's process group so the gate can kill all descendants.
        os.execvp(command[0], command)
    except OSError as exc:
        print("Read-only test runner unavailable: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
