import Foundation

public struct URLSessionTransport: SessionCookieTransport {
    private let session: URLSession
    public init(session: URLSession = .shared) { self.session = session }
    public func clearSessionCookies() async {
        guard let storage = session.configuration.httpCookieStorage else { return }
        for cookie in storage.cookies ?? [] { storage.deleteCookie(cookie) }
    }
    public func send(_ request: URLRequest) async throws -> HTTPResponse {
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw MarketError.invalidResponse }
        return HTTPResponse(status: response.statusCode, data: data)
    }
}

public struct StockAPI: MarketAPI {
    private let baseURL: URL
    private let transport: any HTTPTransport
    public init(baseURL: URL, transport: any HTTPTransport) { self.baseURL = baseURL; self.transport = transport }
    public func search(keyword: String, country: Country = .KR) async throws -> [Stock] {
        var query = [URLQueryItem(name: "q", value: keyword)]
        if country == .US { query.append(URLQueryItem(name: "country", value: "US")) }
        let value = try await get(path: "/api/stocks", query: query)
        guard case .array(let stocks)? = value.object?["stocks"] else { throw MarketError.invalidResponse }
        return try stocks.map { value in
            guard let object = value.object else { throw MarketError.invalidResponse }
            let id = try Self.id(object["assetId"])
            let code = try Self.string(object["assetCode"])
            let name = try Self.string(object["name"])
            let category = try Self.string(object["category"])
            let market = try Self.string(object["market"])
            guard ["STOCK", "ETF"].contains(category), ["KOSPI", "KOSDAQ", "NASDAQ", "NYSE", "NYSE_ARCA", "NYSE_AMERICAN", "BATS"].contains(market) else { throw MarketError.invalidResponse }
            return Stock(assetId: id, assetCode: code, name: name, category: category, market: market, currency: Self.currency(object["currency"], code: code))
        }
    }
    public func latestPrice(assetId: Int64) async throws -> Quote {
        guard (1...9_007_199_254_740_991).contains(assetId) else { throw MarketError.invalidResponse }
        let value = try await get(path: "/api/stocks/\(assetId)/price")
        guard let object = value.object, case .number(let price)? = object["closePrice"], let finite = Double(price), finite.isFinite else { throw MarketError.invalidResponse }
        let code = try Self.string(object["assetCode"])
        return Quote(assetId: try Self.id(object["assetId"]), assetCode: code, name: try Self.string(object["name"]), baseDate: try Self.string(object["baseDate"]), closePrice: price, currency: Self.currency(object["currency"], code: code))
    }
    private func get(path: String, query: [URLQueryItem] = []) async throws -> JSONValue {
        guard var parts = URLComponents(url: baseURL, resolvingAgainstBaseURL: false), ["https", "http"].contains(parts.scheme), parts.host != nil else { throw MarketError.invalidResponse }
        parts.path = path; parts.queryItems = query.isEmpty ? nil : query; parts.fragment = nil
        // URLComponents permits literal +, but the server reads form-style query
        // parameters, where + means space. Match URLSearchParams literal-plus encoding.
        parts.percentEncodedQuery = parts.percentEncodedQuery?.replacingOccurrences(of: "+", with: "%2B")
        guard let url = parts.url else { throw MarketError.invalidResponse }
        var request = URLRequest(url: url); request.httpMethod = "GET"; request.setValue("application/json", forHTTPHeaderField: "Accept")
        let response: HTTPResponse
        do { try Task.checkCancellation(); response = try await transport.send(request); try Task.checkCancellation() }
        catch is CancellationError { throw MarketError.cancelled }
        catch let error as URLError where error.code == .cancelled { throw MarketError.cancelled }
        catch let error as MarketError { throw error }
        catch { throw MarketError.network }
        if response.status == 401 { throw MarketError.unauthorized }
        if response.status == 404 {
            if let value = try? JSONParser.decode(response.data), value.object?["code"]?.text == "STOCK_PRICE_NOT_FOUND" { throw MarketError.notFound }
            throw MarketError.http(404)
        }
        guard (200..<300).contains(response.status) else { throw MarketError.http(response.status) }
        return try JSONParser.decode(response.data)
    }
    private static func string(_ value: JSONValue?) throws -> String {
        guard case .string(let string)? = value else { throw MarketError.invalidResponse }; return string
    }
    private static func currency(_ value: JSONValue?, code: String) -> String {
        if let string = value?.text, ["KRW", "USD"].contains(string) { return string }
        return code.hasSuffix(".US") ? "USD" : "KRW"
    }
    private static func id(_ value: JSONValue?) throws -> Int64 {
        guard case .number(let raw)? = value, !raw.hasPrefix("-") else { throw MarketError.invalidResponse }
        let components = raw.lowercased().split(separator: "e", omittingEmptySubsequences: false)
        let exponent = components.count == 2 ? Int(components[1]) : 0
        guard let exponent, (-9999...9999).contains(exponent) else { throw MarketError.invalidResponse }
        let decimal = components[0].split(separator: ".", omittingEmptySubsequences: false)
        var digits = String(decimal.joined().drop(while: { $0 == "0" }))
        let scale = exponent - (decimal.count == 2 ? decimal[1].count : 0)
        if scale < 0 {
            guard -scale <= digits.count, digits.suffix(-scale).allSatisfy({ $0 == "0" }) else { throw MarketError.invalidResponse }
            digits.removeLast(-scale)
        } else {
            guard digits.count + scale <= 32 else { throw MarketError.invalidResponse }
            digits += String(repeating: "0", count: scale)
        }
        guard let id = Int64(digits), (1...9_007_199_254_740_991).contains(id) else { throw MarketError.invalidResponse }
        return id
    }
}

// A small strict JSON reader retains numeric lexemes before Foundation can round them.
// Strings still use Foundation's JSON decoder for escapes and Unicode validation.
private indirect enum JSONValue {
    case object([String: JSONValue]), array([JSONValue]), string(String), number(String), other
    var object: [String: JSONValue]? { if case .object(let value) = self { value } else { nil } }
    var text: String? { if case .string(let value) = self { value } else { nil } }
}
private struct JSONParser {
    let bytes: [UInt8]
    var index = 0
    static func decode(_ data: Data) throws -> JSONValue {
        var parser = JSONParser(bytes: Array(data))
        let value = try parser.value(depth: 0); parser.whitespace()
        guard parser.index == parser.bytes.count else { throw MarketError.invalidResponse }
        return value
    }
    mutating func whitespace() { while index < bytes.count && [9, 10, 13, 32].contains(bytes[index]) { index += 1 } }
    mutating func take(_ byte: UInt8) -> Bool { if index < bytes.count && bytes[index] == byte { index += 1; return true }; return false }
    mutating func value(depth: Int) throws -> JSONValue {
        whitespace(); guard depth < 128, index < bytes.count else { throw MarketError.invalidResponse }
        if take(123) {
            var object: [String: JSONValue] = [:]; whitespace()
            if take(125) { return .object(object) }
            repeat {
                whitespace(); let key = try string(); whitespace()
                guard take(58) else { throw MarketError.invalidResponse }
                object[key] = try value(depth: depth + 1); whitespace()
                if take(125) { return .object(object) }
                guard take(44) else { throw MarketError.invalidResponse }
            } while true
        }
        if take(91) {
            var array: [JSONValue] = []; whitespace()
            if take(93) { return .array(array) }
            repeat {
                array.append(try value(depth: depth + 1)); whitespace()
                if take(93) { return .array(array) }
                guard take(44) else { throw MarketError.invalidResponse }
            } while true
        }
        if bytes[index] == 34 { return .string(try string()) }
        for literal in ["null", "true", "false"] {
            let token = Array(literal.utf8)
            if bytes[index...].starts(with: token) { index += token.count; return .other }
        }
        let start = index
        _ = take(45)
        if !take(48) { guard digit(nonzero: true) else { throw MarketError.invalidResponse }; while digit() {} }
        if take(46) { guard digit() else { throw MarketError.invalidResponse }; while digit() {} }
        if take(101) || take(69) { if !take(43) { _ = take(45) }; guard digit() else { throw MarketError.invalidResponse }; while digit() {} }
        guard index > start else { throw MarketError.invalidResponse }
        return .number(String(decoding: bytes[start..<index], as: UTF8.self))
    }
    mutating func digit(nonzero: Bool = false) -> Bool {
        guard index < bytes.count, bytes[index] >= (nonzero ? 49 : 48), bytes[index] <= 57 else { return false }; index += 1; return true
    }
    mutating func string() throws -> String {
        let start = index
        guard take(34) else { throw MarketError.invalidResponse }
        while index < bytes.count {
            let byte = bytes[index]; index += 1
            if byte == 34 {
                do { return try JSONDecoder().decode(String.self, from: Data(bytes[start..<index])) }
                catch { throw MarketError.invalidResponse }
            }
            if byte == 92 { guard index < bytes.count else { break }; index += 1 }
            else if byte < 32 { throw MarketError.invalidResponse }
        }
        throw MarketError.invalidResponse
    }
}
