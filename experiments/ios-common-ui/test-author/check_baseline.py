#!/usr/bin/env python3
"""Static RED marker at frozen preimplementation source, not SDK/UI execution."""
from pathlib import Path
import subprocess

BASELINE = "e3c9616f"
FILES = ["AppShell.swift", "DiscoveryView.swift", "PortfolioView.swift"]
source = {name: subprocess.check_output(["git", "show", f"{BASELINE}:clients/ios/DaynomyIOS/{name}"], text=True) for name in FILES}
checks = {
    "three destinations use current labels": 'Label("이슈"' in source["AppShell.swift"] and 'Label("내 계정"' in source["AppShell.swift"] and '.tabItem { Label("종목"' not in source["AppShell.swift"],
    "portfolio contextual stock lookup entry": 'portfolioMarket' in source["PortfolioView.swift"],
    "separate today carousel control surface": 'todayNewsNext' in source["DiscoveryView.swift"] and 'todayNewsPrevious' in source["DiscoveryView.swift"],
    "explicit keyboard search submission": '.onSubmit' in source["DiscoveryView.swift"],
}
print(f"Frozen baseline {BASELINE}; static presence checks only; SDK/Simulator not executed")
for label, passed in checks.items():
    print(f"{'PASS' if passed else 'RED'} {label}")
raise SystemExit(0 if all(checks.values()) else 1)
