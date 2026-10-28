import Foundation

public enum CategoryFilter: String, Codable, Sendable { case ALL, STOCK, ETF }
public enum Country: String, Codable, Sendable { case KR, US }
public enum MarketError: Error, Equatable, Sendable {
    case invalidResponse, notFound, unauthorized, http(Int), network, cancelled
}
public struct Stock: Equatable, Codable, Sendable {
    public var assetId: Int64
    public var assetCode: String
    public var name: String
    public var category: String
    public var market: String
    public var currency: String?
    public init(assetId: Int64, assetCode: String, name: String, category: String = "STOCK", market: String = "KOSPI", currency: String? = nil) {
        self.assetId = assetId; self.assetCode = assetCode; self.name = name; self.category = category; self.market = market; self.currency = currency
    }
}
public struct Quote: Equatable, Sendable {
    public var assetId: Int64
    public var assetCode: String
    public var name: String
    public var baseDate: String
    public var closePrice: String
    public var currency: String?
    public init(assetId: Int64, assetCode: String, name: String, baseDate: String, closePrice: String, currency: String? = nil) {
        self.assetId = assetId; self.assetCode = assetCode; self.name = name; self.baseDate = baseDate; self.closePrice = closePrice; self.currency = currency
    }
}
public enum LoadState<Value: Equatable & Sendable>: Equatable, Sendable {
    case idle, loading, ready(Value), failed(MarketError)
}
public struct MarketDraft: Equatable, Codable, Sendable {
    public var query: String = ""
    public var country: Country = .KR
    public var selected: Stock? = nil
    public var unitPrice: String = ""
    public var priceEdited: Bool = false
    public var filter: CategoryFilter = .ALL
    public init(query: String = "", country: Country = .KR, selected: Stock? = nil, unitPrice: String = "", priceEdited: Bool = false, filter: CategoryFilter = .ALL) {
        self.query = query; self.country = country; self.selected = selected; self.unitPrice = unitPrice; self.priceEdited = priceEdited; self.filter = filter
    }
}
public struct MarketState: Equatable, Sendable {
    public var draft: MarketDraft = .init()
    public var search: LoadState<[Stock]> = .idle
    public var price: LoadState<Quote> = .idle
    public var active: Bool = true
    public init() {}
}
public struct HTTPResponse: Sendable {
    public let status: Int
    public let data: Data
    public init(status: Int, data: Data) { self.status = status; self.data = data }
}
public protocol HTTPTransport: Sendable {
    func send(_ request: URLRequest) async throws -> HTTPResponse
}
public protocol MarketAPI: Sendable {
    func search(keyword: String, country: Country) async throws -> [Stock]
    func latestPrice(assetId: Int64) async throws -> Quote
}
