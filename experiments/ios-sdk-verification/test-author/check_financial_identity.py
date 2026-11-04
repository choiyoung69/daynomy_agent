#!/usr/bin/env python3
"""Static connection check only; cannot prove absence of a rendered stale frame."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
shell = (ROOT / "clients/ios/DaynomyIOS/AppShell.swift").read_text()
portfolio = shell.split("PortfolioView(client:", 1)[1].split(".tabItem", 1)[0]
identity = re.search(r"\.id\((.*)\)", portfolio)
passed = (
    "@Environment(AppSession.self)" in shell
    and identity is not None
    and "session.isLoggedIn" in identity[1]
    and 'session.user?.field("id")' in identity[1]
)
print(("PASS" if passed else "FAIL") + " financial navigation identity follows login state and user ID")
print("STATIC IDENTITY 1 check; failures " + str(int(not passed)))
sys.exit(0 if passed else 1)
