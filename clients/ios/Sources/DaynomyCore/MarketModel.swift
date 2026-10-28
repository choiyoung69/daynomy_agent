import Foundation
import Observation

@Observable @MainActor public final class MarketModel {
    public private(set) var state = MarketState()
    @ObservationIgnored private let api: any MarketAPI
    @ObservationIgnored private let debounce: @Sendable () async throws -> Void
    @ObservationIgnored private var searchTask: Task<Void, Never>?
    @ObservationIgnored private var priceTask: Task<Void, Never>?
    @ObservationIgnored private var searchGeneration: UInt64 = 0
    @ObservationIgnored private var priceGeneration: UInt64 = 0

    public var filteredResults: [Stock] {
        guard case .ready(let stocks) = state.search else { return [] }
        return stocks.filter { state.draft.filter == .ALL || $0.category == state.draft.filter.rawValue }
    }
    public init(api: any MarketAPI, debounce: @escaping @Sendable () async throws -> Void = { try await Task.sleep(for: .milliseconds(250)) }) {
        self.api = api; self.debounce = debounce
    }
    public func updateQuery(_ value: String) { state.draft.query = value; startSearch() }
    public func updateCountry(_ value: Country) { state.draft.country = value; startSearch() }
    public func updateFilter(_ value: CategoryFilter) { state.draft.filter = value }
    public func select(_ stock: Stock) {
        invalidateSearch(); state.search = .idle
        state.draft.selected = stock; state.draft.unitPrice = ""; state.draft.priceEdited = false
        startPrice()
    }
    public func editPrice(_ value: String) { state.draft.unitPrice = value; state.draft.priceEdited = true }
    public func changeStock() {
        invalidatePrice(); state.price = .idle
        state.draft.selected = nil; state.draft.unitPrice = ""; state.draft.priceEdited = false
        startSearch()
    }
    public func deactivate() {
        state.active = false; invalidateSearch(); invalidatePrice()
        state.search = .idle; state.price = .idle
    }
    public func activate() {
        guard !state.active else { return }
        state.active = true; resume()
    }
    public func retrySearch() { startSearch() }
    public func retryPrice() { startPrice() }
    public func restore(snapshot: MarketDraft) {
        invalidateSearch(); invalidatePrice(); state.search = .idle; state.price = .idle
        state.draft = snapshot; resume()
    }
    public func snapshot() -> MarketDraft { state.draft }
    private func resume() { if state.draft.selected == nil { startSearch() } else { startPrice() } }
    private func invalidateSearch() { searchGeneration &+= 1; searchTask?.cancel(); searchTask = nil }
    private func invalidatePrice() { priceGeneration &+= 1; priceTask?.cancel(); priceTask = nil }

    private func startSearch() {
        invalidateSearch(); state.search = .idle
        let keyword = Self.trim(state.draft.query)
        guard state.active, state.draft.selected == nil, !keyword.isEmpty else { return }
        let generation = searchGeneration; let country = state.draft.country
        let api = api; let debounce = debounce
        state.search = .loading
        searchTask = Task { [weak self] in
            do {
                try await debounce(); try Task.checkCancellation()
                let stocks = try await api.search(keyword: keyword, country: country)
                try Task.checkCancellation()
                guard let self, self.state.active, self.searchGeneration == generation else { return }
                self.state.search = .ready(stocks)
            } catch {
                guard let self, self.state.active, self.searchGeneration == generation, !Task.isCancelled else { return }
                let error = Self.classify(error)
                self.state.search = error == .cancelled ? .idle : .failed(error)
            }
        }
    }
    private func startPrice() {
        invalidatePrice(); state.price = .idle
        guard state.active, let stock = state.draft.selected else { return }
        let generation = priceGeneration; let api = api
        state.price = .loading
        priceTask = Task { [weak self] in
            do {
                let quote = try await api.latestPrice(assetId: stock.assetId)
                try Task.checkCancellation()
                guard let self, self.state.active, self.priceGeneration == generation, self.state.draft.selected == stock else { return }
                // Match the original finite Number > 0 acceptance boundary while
                // retaining the exact JSON spelling for display and manual editing.
                guard let positive = Double(quote.closePrice), positive.isFinite, positive > 0 else {
                    self.state.price = .failed(.notFound); return
                }
                self.state.price = .ready(quote)
                if !self.state.draft.priceEdited && self.state.draft.unitPrice.isEmpty { self.state.draft.unitPrice = quote.closePrice }
            } catch {
                guard let self, self.state.active, self.priceGeneration == generation, self.state.draft.selected == stock, !Task.isCancelled else { return }
                let error = Self.classify(error)
                self.state.price = error == .cancelled ? .idle : .failed(error)
            }
        }
    }
    private static func classify(_ error: any Error) -> MarketError {
        if error is CancellationError || (error as? URLError)?.code == .cancelled { return .cancelled }
        return error as? MarketError ?? .network
    }
    private static func trim(_ value: String) -> String {
        let whitespace = CharacterSet(charactersIn: "\u{0009}\u{000a}\u{000b}\u{000c}\u{000d}\u{0020}\u{00a0}\u{1680}\u{2000}\u{2001}\u{2002}\u{2003}\u{2004}\u{2005}\u{2006}\u{2007}\u{2008}\u{2009}\u{200a}\u{2028}\u{2029}\u{202f}\u{205f}\u{3000}\u{feff}")
        return value.trimmingCharacters(in: whitespace)
    }
}
