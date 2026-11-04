#!/usr/bin/env python3
"""Run unchanged production state/method bodies, without a SwiftUI runtime.

Compared with the frozen runner, also extract the views' state declarations so
new request generations remain production code. --baseline executes the frozen
13-check Swift contract against these wrappers without editing that contract.
Neither mode is Simulator, rendered-frame, or actual login evidence.
"""
from pathlib import Path
import re
import argparse
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--baseline", action="store_true")
parser.add_argument("--revision", help="Read production view bodies from this Git revision for reproducible RED")
args = parser.parse_args()


def production(name):
    path = "clients/ios/DaynomyIOS/" + name + ".swift"
    if args.revision:
        return subprocess.check_output(["git", "show", args.revision + ":" + path], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


portfolio = production("PortfolioView")
calendar = production("CalendarAnalysisView")
discovery = production("DiscoveryView")
store = "func portfolioToday()" + portfolio.split("func portfolioToday()", 1)[1].split("@MainActor struct PortfolioView", 1)[0]
value_ext = discovery[discovery.index("extension ServiceValue"):discovery.index("func publicLink")]
friendly = discovery[discovery.index("func friendlyServiceError"):discovery.index("@MainActor struct DiscoveryView")]


def unwrapped(text):
    return text.replace("@State ", "").replace("private ", "")


editor = portfolio.split("@MainActor struct TransactionEditorView: View {", 1)[1]
search_state = editor[editor.index("    @State"):editor.index("    var body:")]
search_methods = editor[editor.index("    private func search()"):editor.index("    private func submit()")]
analysis = calendar.split("@MainActor struct CalendarAnalysisView: View {", 1)[1]
analysis_state = analysis[:analysis.index("    var body:")]
analysis_state = re.sub(r"^.*@Environment.*\n", "", analysis_state, flags=re.MULTILINE)
analysis_methods = analysis[analysis.index("    private func changeMonth"):analysis.index("\n}\n\nstruct PortfolioAnalysisResultView")]
wrappers = '''
@MainActor final class ProbeSession {
 var user: ServiceValue? = .object(["id": .number("1")])
 var isLoggedIn: Bool { user != nil }
}
@MainActor final class AnalysisProbe {
 var session = ProbeSession()
''' + unwrapped(analysis_state) + '''
 init(client: ServiceClient? = nil) {
   self.client = client ?? ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: URLSessionTransport())
 }
''' + unwrapped(analysis_methods) + '''
}
@MainActor final class SearchProbe {
 let client: ServiceClient
 let marketAPI: (any MarketAPI)?
''' + unwrapped(search_state) + '''
 init(client: ServiceClient, marketAPI: (any MarketAPI)? = nil) {
   self.client = client; self.marketAPI = marketAPI
 }
''' + unwrapped(search_methods) + '''
}
'''
contract = (ROOT / "experiments/ios-next-verification/test-author/StateRegressionContract.swift") if args.baseline else HERE / "AsyncStateContract.swift"
with tempfile.TemporaryDirectory(prefix="ios-sdk-async-") as folder:
    temporary = Path(folder)
    extracted = temporary / "ExtractedProduction.swift"
    extracted.write_text("import Foundation\nimport Observation\n" + value_ext + friendly + store + wrappers)
    sources = sorted((ROOT / "clients/ios/Sources/DaynomyCore").glob("*.swift"))
    binary = temporary / "async-state-contract"
    result = subprocess.run([
        "swiftc", "-swift-version", "6", "-parse-as-library", "-module-cache-path",
        "/tmp/ios-sdk-async-cache", *map(str, sources), str(extracted), str(contract), "-o", str(binary),
    ], cwd=ROOT)
    if result.returncode == 0:
        result = subprocess.run([str(binary)], cwd=ROOT)
    sys.exit(result.returncode)
