import Foundation

struct VerificationFailure: Error { let name: String }
@main struct LiveHTTP {
    static func check(_ value: @autoclosure () -> Bool, _ name: String) throws {
        guard value() else { throw VerificationFailure(name: name) }
        print("PASS \(name)")
    }
    @MainActor static func expectError(_ expected: MarketError, _ name: String, work: () async throws -> Void) async throws {
        do { try await work(); throw VerificationFailure(name: name + " unexpectedly succeeded") }
        catch let error as MarketError { try check(error == expected, name) }
    }
    static func main() async throws {
        let mode = CommandLine.arguments[1]
        let base = URL(string: CommandLine.arguments[2])!
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 5
        let session = URLSession(configuration: config)
        defer { session.invalidateAndCancel() }
        let api = StockAPI(baseURL: base, transport: URLSessionTransport(session: session))
        if mode == "rust" {
            let kr = try await api.search(keyword: "삼성", country: .KR)
            try check(kr.count == 1 && kr[0].assetId == 910001 && kr[0].assetCode == "005930" && kr[0].currency == "KRW", "rust KR search/listed filter")
            let us = try await api.search(keyword: "Apple", country: .US)
            try check(us.count == 1 && us[0].assetId == 910002 && us[0].market == "NASDAQ" && us[0].currency == "USD", "rust US search")
            let empty = try await api.search(keyword: "NO_SUCH_STOCK_917", country: .KR)
            try check(empty.isEmpty, "rust empty search")
            let limit = try await api.search(keyword: "LIMIT", country: .KR)
            try check(limit.count == 20, "rust search server limit")
            let krQuote = try await api.latestPrice(assetId: kr[0].assetId)
            try check(krQuote.assetId == 910001 && krQuote.baseDate == "2026-10-23" && Decimal(string: krQuote.closePrice) == Decimal(string: "71000.1250"), "rust latest stored date and decimal")
            let usQuote = try await api.latestPrice(assetId: us[0].assetId)
            try check(usQuote.baseDate == "2026-10-22" && Decimal(string: usQuote.closePrice) == Decimal(string: "193.4000") && usQuote.currency == "USD", "rust US stored quote")
            try await expectError(.notFound, "rust missing price 404") { _ = try await api.latestPrice(assetId: 910003) }
        } else {
            let stocks = try await api.search(keyword: "삼성 & ETF%_!+?#", country: .US)
            try check(stocks.count == 1 && stocks[0].assetId == 1, "loopback UTF8 query GET")
            let quote = try await api.latestPrice(assetId: 1)
            try check(quote.closePrice == "123456789012345678901234567890123456789.0000000001", "loopback exact long decimal token")
            try await expectError(.notFound, "loopback business 404") { _ = try await api.latestPrice(assetId: 404) }
            try await expectError(.http(404), "loopback generic 404") { _ = try await api.latestPrice(assetId: 405) }
            try await expectError(.invalidResponse, "loopback invalid numeric grammar") { _ = try await api.latestPrice(assetId: 2) }
            let pending = Task { try await api.search(keyword: "cancel", country: .KR) }
            for _ in 0..<100 {
                let (data, _) = try await session.data(from: base.appendingPathComponent("__status"))
                if String(decoding: data, as: UTF8.self).contains("requested") { break }
                try await Task.sleep(for: .milliseconds(10))
            }
            let started = ContinuousClock.now
            pending.cancel()
            do { _ = try await pending.value; throw VerificationFailure(name: "cancel unexpectedly succeeded") }
            catch let error as MarketError { try check(error == .cancelled, "loopback URLSession cancel classification") }
            catch is CancellationError { throw VerificationFailure(name: "cancellation bypassed public MarketError contract") }
            try check(started.duration(to: .now) < .seconds(1), "loopback URLSession cancellation latency")
        }
        print("COMPLETE \(mode) macOS URLSession (not iOS runtime)")
    }
}
