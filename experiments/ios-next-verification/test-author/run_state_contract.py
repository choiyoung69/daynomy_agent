#!/usr/bin/env python3
"""Execute production Store/method bodies without SwiftUI runtime.
Extraction preserves method logic; only SwiftUI wrapper/state attributes are omitted.
This is host state evidence, never an iOS build or rendered-view result.
"""
from pathlib import Path
import subprocess
import tempfile
import sys
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
portfolio = (ROOT / "clients/ios/DaynomyIOS/PortfolioView.swift").read_text()
calendar = (ROOT / "clients/ios/DaynomyIOS/CalendarAnalysisView.swift").read_text()
discovery = (ROOT / "clients/ios/DaynomyIOS/DiscoveryView.swift").read_text()
# Exact top-level slices, never replacement implementations of tested logic.
store = portfolio.split("func portfolioToday()", 1)[1].split("@MainActor struct PortfolioView", 1)[0]
store = "func portfolioToday()" + store
value_ext = discovery[discovery.index("extension ServiceValue"):discovery.index("func publicLink")]
friendly = discovery[discovery.index("func friendlyServiceError"):discovery.index("@MainActor struct DiscoveryView")]
accept = calendar[calendar.index("    private func acceptSaved"):calendar.index("    private func runAnalysis")].replace("private func acceptSaved", "func acceptSaved")
search = portfolio[portfolio.index("    private func search() async"):portfolio.index("    private func select(")].replace("private func search()", "func search()")
wrappers = '''
@MainActor final class AnalysisProbe {
 var savedAnalysis: ServiceValue = .null
 var analysis: ServiceValue = .null
 var analysisError = ""
''' + accept + '''
}
@MainActor final class SearchProbe {
 let client: ServiceClient
 let marketAPI: (any MarketAPI)? = nil
 var selected: Stock? = nil
 var query = ""
 var country = Country.KR
 var matches: [Stock] = []
 var searching = false
 var localError = ""
 init(client: ServiceClient) { self.client = client }
''' + search + '\n}\n'
with tempfile.TemporaryDirectory(prefix="ios-state-") as folder:
    temporary = Path(folder)
    extracted = temporary / "ExtractedProduction.swift"
    extracted.write_text("import Foundation\nimport Observation\n" + value_ext + friendly + store + wrappers)
    sources = sorted((ROOT / "clients/ios/Sources/DaynomyCore").glob("*.swift"))
    binary = temporary / "state-contract"
    result = subprocess.run(["swiftc", "-swift-version", "6", "-parse-as-library", "-module-cache-path", "/tmp/ios-next-state-cache", *map(str, sources), str(extracted), str(HERE / "StateRegressionContract.swift"), "-o", str(binary)], cwd=ROOT)
    if result.returncode == 0:
        result = subprocess.run([str(binary)], cwd=ROOT)
    sys.exit(result.returncode)
