import Foundation

actor ControlledMarket: MarketAPI {
    private var requests: [Int: CheckedContinuation<[Stock], any Error>] = [:]
    private var count = 0
    var requestCount: Int { count }
    func search(keyword: String, country: Country) async throws -> [Stock] {
        count += 1
        let id = count
        return try await withCheckedThrowingContinuation { requests[id] = $0 }
    }
    func latestPrice(assetId: Int64) async throws -> Quote { throw MarketError.network }
    func finish(_ id: Int, stocks: [Stock]? = nil) {
        guard let request = requests.removeValue(forKey: id) else { fatalError("missing market request") }
        if let stocks { request.resume(returning: stocks) }
        else { request.resume(throwing: MarketError.network) }
    }
}

actor ControlledService: HTTPTransport {
    private var requests: [Int: CheckedContinuation<HTTPResponse, any Error>] = [:]
    private var count = 0
    var requestCount: Int { count }
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        count += 1
        let id = count
        return try await withCheckedThrowingContinuation { requests[id] = $0 }
    }
    func finish(_ id: Int, json: String? = nil) {
        guard let request = requests.removeValue(forKey: id) else { fatalError("missing service request") }
        if let json { request.resume(returning: HTTPResponse(status: 200, data: Data(json.utf8))) }
        else { request.resume(throwing: URLError(.cannotConnectToHost)) }
    }
}

actor CountingTransport: HTTPTransport {
    var sends = 0
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        sends += 1
        throw URLError(.cannotConnectToHost)
    }
}

@main struct AsyncStateContract {
    @MainActor static func main() async throws {
        var failures = 0, checks = 0
        func check(_ passed: Bool, _ name: String) {
            checks += 1
            print("\(passed ? "PASS" : "FAIL") \(name)")
            if !passed { failures += 1 }
        }
        func waitFor(_ ready: () async -> Bool) async throws {
            let deadline = ContinuousClock.now + .seconds(5)
            while !(await ready()) {
                guard ContinuousClock.now < deadline else { fatalError("request did not start within deadline") }
                try await Task.sleep(for: .milliseconds(10))
            }
        }
        let oldStock = Stock(assetId: 1, assetCode: "005930", name: "old KR", category: "STOCK", market: "KOSPI", currency: "KRW")
        let newStock = Stock(assetId: 2, assetCode: "000660", name: "new KR", category: "STOCK", market: "KOSPI", currency: "KRW")
        let market = ControlledMarket()
        let transport = CountingTransport()
        let client = ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: transport)
        let search = SearchProbe(client: client, marketAPI: market)
        search.query = "삼성"; search.matches = [oldStock]
        let first = Task { await search.search() }
        try await Task.sleep(for: .milliseconds(20))
        check(search.matches.isEmpty, "new search immediately removes selectable old matches")
        try await waitFor { await market.requestCount == 1 }
        search.country = .US
        let second = Task { await search.search() }
        try await waitFor { await market.requestCount == 2 }
        search.country = .KR
        let third = Task { await search.search() }
        try await waitFor { await market.requestCount == 3 }
        await market.finish(1); await first.value
        check(search.localError.isEmpty && search.searching, "ABA old failure cannot set error or stop newer loading")
        await market.finish(3, stocks: [newStock]); await third.value
        await market.finish(2, stocks: [oldStock]); await second.value
        check(search.matches == [newStock] && !search.searching && search.localError.isEmpty, "uncancelled old success cannot replace newest country result")
        let fourth = Task { await search.search() }
        try await waitFor { await market.requestCount == 4 }
        search.selected = newStock
        await search.search()
        await market.finish(4, stocks: [oldStock]); await fourth.value
        check(search.matches.isEmpty && !search.searching, "selecting stock invalidates pending search result")

        let removal = PortfolioStore()
        try removal.guest.add(LocalTrade(id: 1, stock: oldStock, type: .BUY, date: "2020-01-01", quantity: 3, unitPrice: "100"))
        let originalTrades = removal.guest.trades
        let holding = try removal.guest.holdings()[0]
        let removed = await removal.adjustHolding(holding, quantity: "invalid", average: "invalid", removing: true, client: client)
        let remaining = try removal.guest.holdings()
        check(removed && remaining.isEmpty, "explicit guest removal ignores invalid editable quantity and average")
        check(removal.guest.trades == originalTrades && removal.guest.holdingChanges.count == 1, "guest removal records adjustment while preserving all original transactions")
        let sends = await transport.sends
        check(sends == 0, "invalid-field guest removal stays entirely local")

        let memberService = ControlledService()
        let memberClient = ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: memberService)
        let memberStore = PortfolioStore()
        memberStore.accountKey = "member-A"
        memberStore.holdings = [LocalHolding(stock: oldStock, quantity: 1, averagePurchasePrice: 100)]
        memberStore.calculation = .object(["totalEvaluationAmount": .number("100")])
        let memberReload = Task { await memberStore.reload(client: memberClient, member: true, accountKey: "member-A") }
        try await waitFor { await memberService.requestCount == 1 }
        await memberService.finish(1, json: #"{"totalRealizedProfitLoss":0,"holdings":[{"assetId":1,"assetCode":"005930","name":"synthetic","quantity":2,"averagePurchasePrice":100}]}"#)
        try await waitFor { await memberService.requestCount == 2 }
        check(memberStore.holdings.first?.quantity == 2 && memberStore.calculation == .null, "member holdings change invalidates old valuation before histories completes")
        await memberService.finish(2); await memberReload.value
        check(memberStore.calculation == .null && !memberStore.error.isEmpty, "history failure after changed holdings cannot leave previous valuation")

        let service = ControlledService()
        let analysisClient = ServiceClient(baseURL: URL(string: "http://127.0.0.1:18097")!, transport: service)
        let analysis = AnalysisProbe(client: analysisClient)
        let loadA = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 1 }
        await service.finish(1, json: #"{"status":"READY","analysis":{"overallImpact":"A private result"}}"#)
        await loadA.value
        check(analysis.analysis.field("overallImpact").display == "A private result", "A saved analysis initially accepted")
        analysis.history = [.string("A private history")]; analysis.showAnalysisHistory = true
        analysis.session.user = .object(["id": .number("2")])
        let loadB = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 2 }
        check(analysis.analysis == .null && analysis.savedAnalysis == .null && analysis.history.isEmpty && !analysis.showAnalysisHistory, "B request clears A data before network completes")
        await service.finish(2)
        await loadB.value
        check(analysis.analysis == .null, "B network failure cannot restore A analysis")
        let bReady = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 3 }
        await service.finish(3, json: #"{"status":"READY","analysis":{"overallImpact":"B last good"}}"#)
        await bReady.value
        let bOldFailure = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 4 }
        check(analysis.analysis.field("overallImpact").display == "B last good", "same-account refresh preserves last good while pending")
        await service.finish(4); await bOldFailure.value
        check(analysis.analysis.field("overallImpact").display == "B last good" && !analysis.analysisError.isEmpty, "same-account transport failure preserves last good analysis with error")
        let bLate = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 5 }
        analysis.session.user = .object(["id": .number("3")])
        let cLoad = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 6 }
        await service.finish(6, json: #"{"status":"READY","analysis":{"overallImpact":"C current"}}"#)
        await cLoad.value
        await service.finish(5); await bLate.value
        check(analysis.analysis.field("overallImpact").display == "C current" && analysis.analysisError.isEmpty, "late previous-account transport error cannot overwrite current account")
        let cOld = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 7 }
        let cNew = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 8 }
        await service.finish(8, json: #"{"status":"READY","analysis":{"overallImpact":"C newest"}}"#)
        await cNew.value
        await service.finish(7); await cOld.value
        check(analysis.analysis.field("overallImpact").display == "C newest" && analysis.analysisError.isEmpty, "older same-account refresh failure cannot overwrite newer success")
        let staleGet = Task { await analysis.loadSavedAnalysis() }
        try await waitFor { await service.requestCount == 9 }
        let newPost = Task { await analysis.runAnalysis(refresh: false) }
        try await waitFor { await service.requestCount == 10 }
        await service.finish(10, json: #"{"headerName":"X-CSRF-TOKEN","token":"synthetic"}"#)
        try await waitFor { await service.requestCount == 11 }
        await service.finish(11, json: #"{"status":"READY","analysis":{"overallImpact":"C posted newest"}}"#)
        await newPost.value
        await service.finish(9, json: #"{"status":"EMPTY","analysis":null}"#)
        await staleGet.value
        check(analysis.analysis.field("overallImpact").display == "C posted newest" && !analysis.analyzing, "late GET EMPTY cannot clear newer POST READY analysis")
        print("ASYNC STATE CONTRACT \(checks) checks; failures \(failures)")
        exit(failures == 0 ? 0 : 1)
    }
}
