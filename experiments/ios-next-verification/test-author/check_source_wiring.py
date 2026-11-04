#!/usr/bin/env python3
"""Static UI wiring gate; it is not simulated UI or account-switch execution."""
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[3]
discovery = (ROOT / "clients/ios/DaynomyIOS/DiscoveryView.swift").read_text()
admin = (ROOT / "clients/ios/DaynomyIOS/AdminView.swift").read_text().split("struct AdminNewsEditorView", 1)[1]
calendar = (ROOT / "clients/ios/DaynomyIOS/CalendarAnalysisView.swift").read_text()
history = calendar.split("struct PortfolioHistoryView", 1)[1]
checks = {
    "Discovery actually uses NewsPresentation.items": "NewsPresentation.items(" in discovery,
    "Discovery supplies news-search mode to helper": bool(re.search(r'isNewsSearch\s*:', discovery)) and 'mode == "news"' in discovery and 'trimmingCharacters(in: .whitespacesAndNewlines)' in discovery,
    "Admin editor uses constrained categories": "NewsPresentation.adminCategoryCodes" in admin,
    "Admin editor does not offer all public news categories": 'ForEach(newsCategories.filter' not in admin,
    "History derives account identity": 'accountKey' in history and 'session.user?' in history,
    "History task restarts for account change": bool(re.search(r'\.task\(id:\s*[^\n]*accountKey', history)),
    "History captures request owner": 'let startedAccount = accountKey' in history,
    "History guards both awaited result assignments": history.count('accountKey == startedAccount') >= 2,
    "History clears prior performance and rows": 'performance = .null' in history and 'histories = []' in history,
}
for name, passed in checks.items():
    print(('PASS ' if passed else 'FAIL ') + name)
print(f'STATIC WIRING {len(checks)} checks; failures {sum(not x for x in checks.values())}')
sys.exit(0 if all(checks.values()) else 1)
