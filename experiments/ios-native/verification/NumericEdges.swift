import Foundation
struct BodyTransport: HTTPTransport {
    let body: String
    func send(_ request: URLRequest) async throws -> HTTPResponse { HTTPResponse(status: 200, data: Data(body.utf8)) }
}
struct EdgeFailure: Error { let input: String }
@main struct NumericEdges {
    static func main() async throws {
        let validIDs = ["1.0", "1e0", "100e-2", "0.1e1", "0." + String(repeating: "0", count: 39) + "1e40", "900719925474099100e-2"]
        for token in validIDs {
            let body = "{\"stocks\":[{\"assetId\":\(token),\"assetCode\":\"A\",\"name\":\"A\",\"category\":\"STOCK\",\"market\":\"KOSPI\"}]}"
            let api = StockAPI(baseURL: URL(string: "https://example.invalid")!, transport: BodyTransport(body: body))
            let stocks = try await api.search(keyword: "A")
            guard stocks.first?.assetId == (token.hasPrefix("900") ? 9_007_199_254_740_991 : 1) else { throw EdgeFailure(input: token) }
            print("PASS exact integral ID \(token)")
        }
        for token in ["1.00000000000000000000000000000001", "9007199254740991.00000000000001", "9007199254740992", "1e99999", "1e-99999"] {
            let body = "{\"stocks\":[{\"assetId\":\(token),\"assetCode\":\"A\",\"name\":\"A\",\"category\":\"STOCK\",\"market\":\"KOSPI\"}]}"
            let api = StockAPI(baseURL: URL(string: "https://example.invalid")!, transport: BodyTransport(body: body))
            do { _ = try await api.search(keyword: "A"); throw EdgeFailure(input: token) }
            catch MarketError.invalidResponse { print("PASS reject exact noninteger/out-of-range ID \(token)") }
        }
        let duplicate = "{\"stocks\":[{\"assetId\":0,\"assetId\":1,\"assetCode\":\"A\",\"name\":\"old\",\"name\":\"new\",\"category\":\"STOCK\",\"market\":\"KOSPI\"}]}"
        let duplicateAPI = StockAPI(baseURL: URL(string: "https://example.invalid")!, transport: BodyTransport(body: duplicate))
        let duplicateStocks = try await duplicateAPI.search(keyword: "A")
        guard duplicateStocks.first?.assetId == 1 && duplicateStocks.first?.name == "new" else { throw EdgeFailure(input: "duplicate last wins") }
        print("PASS duplicate JSON keys use final value")
        let tiny = "{\"assetId\":1,\"assetCode\":\"A\",\"name\":\"A\",\"baseDate\":\"date\",\"closePrice\":1e-400}"
        let tinyAPI = StockAPI(baseURL: URL(string: "https://example.invalid")!, transport: BodyTransport(body: tiny))
        let tinyQuote = try await tinyAPI.latestPrice(assetId: 1)
        guard tinyQuote.closePrice == "1e-400" else { throw EdgeFailure(input: "tiny lexical retention") }
        let model = MarketModel(api: tinyAPI, debounce: {})
        model.select(Stock(assetId: 1, assetCode: "A", name: "A"))
        for _ in 0..<3000 {
            if case .failed = model.state.price { break }
            await Task.yield()
        }
        guard model.state.price == .failed(.notFound) && model.state.draft.unitPrice.isEmpty else { throw EdgeFailure(input: "subnormal price UI rejection") }
        print("PASS subnormal lexical decoding preserved but UI nonpositive rejected")
        print("NUMERIC EDGE ASSERTIONS 14")
    }
}
