import Foundation
import Testing
@testable import DaynomyCore

actor RecordingTransport: HTTPTransport {
    var requests: [URLRequest] = []
    let response: HTTPResponse
    let failure: MarketError?
    init(_ body: String, status: Int = 200, failure: MarketError? = nil) {
        response = HTTPResponse(status: status, data: Data(body.utf8)); self.failure = failure
    }
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        requests.append(request)
        if let failure { throw failure }
        return response
    }
    func lastRequest() -> URLRequest? { requests.last }
}
struct FailingTransport: HTTPTransport {
    enum Failure: Error { case offline }
    let cancelled: Bool
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        if cancelled { throw CancellationError() }
        throw Failure.offline
    }
}
func stockJSON(id: String = "1", currency: String = "", category: String = "STOCK", market: String = "KOSPI", code: String = "005930") -> String {
    "{\"assetId\":\(id),\"assetCode\":\"\(code)\",\"name\":\"삼성전자\",\"category\":\"\(category)\",\"market\":\"\(market)\"\(currency)}"
}
func quoteJSON(id: String = "1", price: String = "123.45", date: String = "2026-10-24", currency: String = "") -> String {
    "{\"assetId\":\(id),\"assetCode\":\"005930\",\"name\":\"삼성전자\",\"baseDate\":\"\(date)\",\"closePrice\":\(price)\(currency)}"
}
func client(_ transport: any HTTPTransport) -> StockAPI { StockAPI(baseURL: URL(string: "https://example.invalid")!, transport: transport) }

struct APIContractTests {
    @Test func queryEncodingAndCountry() async throws {
        for country in [Country.KR, .US] {
            let transport = RecordingTransport("{\"stocks\":[]}")
            let values = try await client(transport).search(keyword: "삼성 A&B+%?#/", country: country)
            #expect(values.isEmpty)
            let request = try #require(await transport.lastRequest())
            let url = try #require(request.url)
            let parts = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false))
            #expect(parts.path == "/api/stocks")
            #expect(parts.queryItems?.first(where: { $0.name == "q" })?.value == "삼성 A&B+%?#/")
            #expect(parts.queryItems?.first(where: { $0.name == "country" })?.value == (country == .US ? "US" : nil))
            #expect(request.httpMethod == "GET" || request.httpMethod == nil)
        }
    }
    @Test func validMarketsAndSafeMaximumID() async throws {
        for market in ["KOSPI", "KOSDAQ", "NASDAQ", "NYSE", "NYSE_ARCA", "NYSE_AMERICAN", "BATS"] {
            let body = "{\"stocks\":[\(stockJSON(id: "9007199254740991", category: "ETF", market: market))]}"
            let items = try await client(RecordingTransport(body)).search(keyword: "x", country: .KR)
            #expect(items.first?.assetId == 9_007_199_254_740_991)
            #expect(items.first?.market == market)
        }
    }
    @Test func malformedSearchAndIDsRejected() async {
        let bodies = ["{}", "null", "{\"stocks\":null}", "{\"stocks\":{}}", "{\"stocks\":[null]}"] +
            ["0", "-1", "1.5", "true", "\"1\"", "9007199254740992", "9007199254740993", "1.0000000000000000001"].map { "{\"stocks\":[\(stockJSON(id: $0))]}" } +
            ["{\"stocks\":[\(stockJSON(category: "BOND"))]}", "{\"stocks\":[\(stockJSON(market: "UNKNOWN"))]}"]
        for body in bodies {
            await #expect(throws: MarketError.invalidResponse) { try await client(RecordingTransport(body)).search(keyword: "x", country: .KR) }
        }
    }
    @Test func jsonLexicalAndShapeBoundaries() async throws {
        for id in ["1.0", "1e0"] {
            let values = try await client(RecordingTransport("{\"stocks\":[\(stockJSON(id: id))]}")).search(keyword: "x", country: .KR)
            #expect(values.first?.assetId == 1)
        }
        for price in ["01", "+1", "1.", ".1", "1e", "NaN"] {
            await #expect(throws: MarketError.invalidResponse) { try await client(RecordingTransport(quoteJSON(price: price))).latestPrice(assetId: 1) }
        }
        for field in ["assetCode", "name", "category", "market"] {
            var object = try #require(JSONSerialization.jsonObject(with: Data(stockJSON().utf8)) as? [String: Any])
            object[field] = NSNull()
            let data = try JSONSerialization.data(withJSONObject: ["stocks": [object]])
            await #expect(throws: MarketError.invalidResponse) { try await client(RecordingTransport(String(decoding: data, as: UTF8.self))).search(keyword: "x", country: .KR) }
        }
        let mixed = "{\"stocks\":[\(stockJSON()),null]}"
        await #expect(throws: MarketError.invalidResponse) { try await client(RecordingTransport(mixed)).search(keyword: "x", country: .KR) }
        let escaped = quoteJSON().replacingOccurrences(of: "삼성전자", with: "A\\\"B\\uD83D\\uDE00").dropLast() + ",\"extra\":{\"closePrice\":999,\"x\":[1,null]}}"
        let value = try await client(RecordingTransport(String(escaped))).latestPrice(assetId: 1)
        #expect(value.name == "A\"B😀")
        #expect(value.closePrice == "123.45")
    }
    @Test func currencyFallbackPolicy() async throws {
        for code in ["A.US", "005930", "a.us"] {
            for currency in ["", ",\"currency\":null", ",\"currency\":\"EUR\"", ",\"currency\":17"] {
                let values = try await client(RecordingTransport("{\"stocks\":[\(stockJSON(currency: currency, code: code))]}")).search(keyword: "x", country: .KR)
                #expect(values.first?.currency == (code.hasSuffix(".US") ? "USD" : "KRW"))
            }
        }
        let values = try await client(RecordingTransport("{\"stocks\":[\(stockJSON(currency: ",\"currency\":\"USD\""))]}")).search(keyword: "x", country: .KR)
        #expect(values.first?.currency == "USD")
    }
    @Test func priceLexicalPrecisionAndDateStrings() async throws {
        for price in ["0.1", "1.005", "1234567890123456789012345678901234567890.1234567890123456789", "1.2300e+2", "0", "-0.125"] {
            for date in ["2026-10-24", "", "calendar-spelling-unvalidated"] {
                let transport = RecordingTransport(quoteJSON(price: price, date: date))
                let quote = try await client(transport).latestPrice(assetId: 1)
                #expect(quote.closePrice == price)
                #expect(quote.baseDate == date)
                #expect(quote.currency == "KRW")
                #expect(await transport.lastRequest()?.url?.path == "/api/stocks/1/price")
            }
        }
    }
    @Test func invalidPricesRejected() async {
        for body in [quoteJSON(price: "\"123\""), quoteJSON(price: "null"), quoteJSON(price: "true"), quoteJSON(price: "1e9999"), quoteJSON(id: "9007199254740993"), "{}", quoteJSON().replacingOccurrences(of: "\"2026-10-24\"", with: "42")] {
            await #expect(throws: MarketError.invalidResponse) { try await client(RecordingTransport(body)).latestPrice(assetId: 1) }
        }
    }
    @Test func invalidRequestedIDNeverSent() async {
        let transport = RecordingTransport(quoteJSON())
        await #expect(throws: MarketError.invalidResponse) { try await client(transport).latestPrice(assetId: 0) }
        #expect(await transport.lastRequest() == nil)
    }
    @Test func httpErrorClassification() async {
        for (status, body, expected) in [(404, "{\"code\":\"STOCK_PRICE_NOT_FOUND\"}", MarketError.notFound), (404, "{}", .http(404)), (401, "{}", .unauthorized), (503, "<html>down</html>", .http(503)), (204, "", .invalidResponse)] {
            await #expect(throws: expected) { try await client(RecordingTransport(body, status: status)).latestPrice(assetId: 1) }
        }
    }
    @Test func networkAndCancellationClassification() async {
        await #expect(throws: MarketError.network) { try await client(FailingTransport(cancelled: false)).search(keyword: "x", country: .KR) }
        await #expect(throws: MarketError.cancelled) { try await client(FailingTransport(cancelled: true)).search(keyword: "x", country: .KR) }
    }
}
