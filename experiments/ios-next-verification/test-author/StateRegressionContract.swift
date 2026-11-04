import Foundation

actor QuoteThenFailure: HTTPTransport {
    var calculations = 0
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        if request.url?.path == "/api/auth/csrf" {
            return HTTPResponse(status: 200, data: Data(#"{"headerName":"X-CSRF-TOKEN","token":"synthetic"}"#.utf8))
        }
        calculations += 1
        if calculations == 1 {
            return HTTPResponse(status: 200, data: Data(#"{"holdings":[],"pricingStatus":"COMPLETE","totalEvaluationAmount":100}"#.utf8))
        }
        return HTTPResponse(status: 503, data: Data(#"{"code":"UNAVAILABLE"}"#.utf8))
    }
}
actor NoGuestMutationTransport: HTTPTransport {
    var sends = 0
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        sends += 1
        return HTTPResponse(status: 401, data: Data("{}".utf8))
    }
}
@main struct StateRegressionContract {
    @MainActor static func main() async throws {
        var failures = 0
        func check(_ value: Bool, _ name: String) {
            print("\(value ? "PASS" : "FAIL") \(name)")
            if !value { failures += 1 }
        }
        let stock = Stock(assetId: 1, assetCode: "005930", name: "삼성전자", category: "STOCK", market: "KOSPI", currency: "KRW")
        let client = ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: QuoteThenFailure())
        let store = PortfolioStore()
        try store.guest.add(LocalTrade(id: 1, stock: stock, type: .BUY, date: "2020-01-01", quantity: 1, unitPrice: "100"))
        await store.reload(client: client, member: false, accountKey: "guest")
        check(store.calculation.field("totalEvaluationAmount").display == "100", "first calculation accepted")
        try store.guest.add(LocalTrade(id: 2, stock: stock, type: .BUY, date: "2020-01-01", quantity: 1, unitPrice: "200"))
        await store.reload(client: client, member: false, accountKey: "guest")
        check(store.holdings.first?.quantity == 2, "holdings updated before failed valuation")
        check(!store.error.isEmpty, "failed valuation reports error")
        check(store.calculation == .null, "failed valuation cannot retain old-holdings result")
        let analysis = AnalysisProbe()
        let old = ServiceValue.object(["overallImpact": .string("previous account result")])
        try analysis.acceptSaved(.object(["status": .string("READY"), "analysis": old]))
        check(analysis.analysis == old, "ready saved analysis accepted")
        try analysis.acceptSaved(.object(["status": .string("EMPTY"), "analysis": .null]))
        check(analysis.analysis == .null, "EMPTY clears previously visible analysis")
        try analysis.acceptSaved(.object(["status": .string("READY"), "analysis": old]))
        try analysis.acceptSaved(.object(["status": .string("FAILED"), "analysis": old]))
        check(analysis.analysis == old, "FAILED explicitly supplied last-good analysis retained")
        try analysis.acceptSaved(.object(["status": .string("FAILED"), "analysis": .null]))
        check(analysis.analysis == .null, "FAILED without last-good analysis clears stale result")
        let search = SearchProbe(client: client)
        search.query = "삼성"
        let task = Task { await search.search() }
        try await Task.sleep(for: .milliseconds(50)); task.cancel(); await task.value
        search.query = ""; await search.search()
        check(search.searching == false && search.matches.isEmpty, "cancel then clear query removes spinner")
        search.searching = true; search.selected = stock; search.query = "삼성"
        await search.search()
        check(search.searching == false, "selected-stock search guard removes stale spinner")
        let removing = PortfolioStore()
        try removing.guest.add(LocalTrade(id: 1, stock: stock, type: .BUY, date: "2020-01-01", quantity: 3, unitPrice: "100"))
        let holding = try removing.guest.holdings()[0]
        let transport = NoGuestMutationTransport()
        let removalClient = ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: transport)
        let removed = await removing.adjustHolding(holding, quantity: "", average: "", removing: true, client: removalClient)
        check(removed, "remove guest holding ignores empty correction fields")
        check(try removing.guest.holdings().isEmpty, "guest holding actually removed")
        let sends = await transport.sends
        check(sends == 0, "guest holding removal never sends member mutation")
        print("STATE CONTRACT 13 checks; failures \(failures)")
        exit(failures == 0 ? 0 : 1)
    }
}
