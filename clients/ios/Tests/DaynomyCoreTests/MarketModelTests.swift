import Foundation
import Testing
@testable import DaynomyCore

// Deliberately ignores task cancellation until explicitly resolved: tests generation guards.
actor ControlledAPI: MarketAPI {
    struct SearchCall: Sendable { let keyword: String; let country: Country }
    var calls: [SearchCall] = []
    var ids: [Int64] = []
    var searches: [Int: CheckedContinuation<[Stock], any Error>] = [:]
    var prices: [Int: CheckedContinuation<Quote, any Error>] = [:]
    func search(keyword: String, country: Country) async throws -> [Stock] {
        let index = calls.count
        calls.append(SearchCall(keyword: keyword, country: country))
        return try await withCheckedThrowingContinuation { searches[index] = $0 }
    }
    func latestPrice(assetId: Int64) async throws -> Quote {
        let index = ids.count; ids.append(assetId)
        return try await withCheckedThrowingContinuation { prices[index] = $0 }
    }
    func counts() -> (Int, Int) { (calls.count, ids.count) }
    func searchCall(_ index: Int) -> SearchCall { calls[index] }
    func finishSearch(_ index: Int, _ result: Result<[Stock], any Error>) { searches.removeValue(forKey: index)?.resume(with: result) }
    func finishPrice(_ index: Int, _ result: Result<Quote, any Error>) { prices.removeValue(forKey: index)?.resume(with: result) }
    func drain() {
        for value in searches.values { value.resume(throwing: CancellationError()) }; searches.removeAll()
        for value in prices.values { value.resume(throwing: CancellationError()) }; prices.removeAll()
    }
}
actor DebounceGate {
    var waiting: [CheckedContinuation<Void, any Error>] = []
    func sleep() async throws { try await withCheckedThrowingContinuation { waiting.append($0) } }
    func count() -> Int { waiting.count }
    func release() { let all = waiting; waiting.removeAll(); all.forEach { $0.resume() } }
}
@MainActor func settle(_ predicate: @escaping @MainActor () async -> Bool) async -> Bool {
    for _ in 0..<3000 { if await predicate() { return true }; await Task.yield() }
    return false
}
func sample(_ id: Int64 = 1, category: String = "STOCK") -> Stock { Stock(assetId: id, assetCode: "S\(id)", name: "Stock \(id)", category: category) }
func quote(_ id: Int64 = 1, price: String = "123.4500", date: String = "2026-10-24") -> Quote { Quote(assetId: id, assetCode: "S\(id)", name: "Stock \(id)", baseDate: date, closePrice: price, currency: "KRW") }

@MainActor struct MarketModelTests {
    @Test func debounceTrimsJSWhitespaceAndBlankSkips() async {
        let api = ControlledAPI(); let gate = DebounceGate()
        let model = MarketModel(api: api, debounce: { try await gate.sleep() })
        model.updateQuery("\u{feff} 삼성 \n")
        #expect(await settle { await gate.count() > 0 })
        #expect(await api.counts().0 == 0)
        await gate.release()
        if await settle({ await api.counts().0 == 1 }) {
            #expect(await api.searchCall(0).keyword == "삼성")
        } else { Issue.record("debounced query never requested") }
        model.updateQuery(" \n\u{feff}")
        #expect(model.state.search == .idle)
        await api.finishSearch(0, .success([sample()]))
        #expect(await settle { model.state.search == .idle })
        await api.drain()
    }
    @Test func nelPreservedAndCountryReissues() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.updateQuery("\u{85}A\u{85}")
        guard await settle({ await api.counts().0 == 1 }) else { Issue.record("missing search"); return }
        #expect(await api.searchCall(0).keyword == "\u{85}A\u{85}")
        model.updateCountry(.US)
        #expect(await settle { await api.counts().0 == 2 })
        if await api.counts().0 == 2 { #expect(await api.searchCall(1).country == .US) }
        await api.drain()
    }
    @Test func staleSearchSuccessErrorAndLoadingGuard() async {
        for fail in [false, true] {
            let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
            model.updateQuery("A")
            guard await settle({ await api.counts().0 == 1 }) else { Issue.record("missing A"); continue }
            model.updateQuery("B")
            guard await settle({ await api.counts().0 == 2 }) else { Issue.record("missing B"); await api.drain(); continue }
            await api.finishSearch(0, fail ? .failure(MarketError.network) : .success([sample(1)]))
            for _ in 0..<50 { await Task.yield() }
            #expect(model.state.search == .loading)
            await api.finishSearch(1, .success([sample(2)]))
            #expect(await settle { model.state.search == .ready([sample(2)]) })
            await api.drain()
        }
    }
    @Test func selectionAutofillExactAndManualDeletionDirty() async {
        for input in [Optional<String>.none, "77.010", ""] {
            let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
            model.select(sample())
            guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing quote"); continue }
            if let input { model.editPrice(input) }
            await api.finishPrice(0, .success(quote()))
            #expect(await settle { model.state.price == .ready(quote()) })
            #expect(model.state.draft.unitPrice == (input ?? "123.4500"))
            #expect(model.state.draft.priceEdited == (input != nil))
            await api.drain()
        }
    }
    @Test func nonpositiveQuoteFailsWithoutFilling() async {
        for price in ["0", "-0", "-2", "0e99"] {
            let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
            model.select(sample())
            guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing quote"); continue }
            await api.finishPrice(0, .success(quote(price: price)))
            #expect(await settle { if case .failed = model.state.price { true } else { false } })
            #expect(model.state.draft.unitPrice.isEmpty)
            await api.drain()
        }
    }
    @Test func staleQuoteSuccessAndFailureCannotMutateNewSelection() async {
        for failure in [false, true] {
            let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
            model.select(sample(1))
            guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing quote1"); continue }
            model.changeStock(); model.select(sample(2))
            guard await settle({ await api.counts().1 == 2 }) else { Issue.record("missing quote2"); await api.drain(); continue }
            await api.finishPrice(0, failure ? .failure(MarketError.notFound) : .success(quote(1)))
            for _ in 0..<50 { await Task.yield() }
            #expect(model.state.price == .loading)
            #expect(model.state.draft.unitPrice == "")
            await api.finishPrice(1, .success(quote(2, price: "456.70")))
            #expect(await settle { model.state.draft.unitPrice == "456.70" })
            await api.drain()
        }
    }
    @Test func deactivateBackPreservesDraftAndActivationRefetches() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.select(sample()); model.editPrice("88.00")
        guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing quote"); return }
        let saved = model.snapshot(); model.deactivate()
        #expect(!model.state.active)
        #expect(model.state.price == .idle)
        #expect(model.snapshot() == saved)
        await api.finishPrice(0, .success(quote()))
        for _ in 0..<50 { await Task.yield() }
        #expect(model.state.price == .idle)
        model.activate()
        #expect(await settle { await api.counts().1 == 2 })
        await api.finishPrice(1, .success(quote()))
        #expect(await settle { model.state.price == .ready(quote()) })
        #expect(model.state.draft.unitPrice == "88.00")
        await api.drain()
    }
    @Test func restoreDirtyEmptyAndChangeStockReset() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        let draft = MarketDraft(query: "삼성", country: .US, selected: sample(), unitPrice: "", priceEdited: true)
        model.restore(snapshot: draft)
        #expect(model.snapshot() == draft)
        guard await settle({ await api.counts().1 == 1 }) else { Issue.record("restore did not fetch quote"); return }
        await api.finishPrice(0, .success(quote()))
        #expect(await settle { model.state.price == .ready(quote()) })
        #expect(model.state.draft.unitPrice == "")
        model.changeStock()
        #expect(model.state.draft.selected == nil)
        #expect(model.state.draft.query == "삼성")
        #expect(!model.state.draft.priceEdited)
        #expect(model.state.price == .idle)
        #expect(await settle { await api.counts().0 == 1 })
        await api.drain()
    }
    @Test func localCategoryFilterRetainsFullResults() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.updateQuery("x")
        guard await settle({ await api.counts().0 == 1 }) else { Issue.record("missing search"); return }
        let all = [sample(), sample(2, category: "ETF")]
        await api.finishSearch(0, .success(all))
        #expect(await settle { model.state.search == .ready(all) })
        model.updateFilter(.ETF)
        #expect(model.filteredResults == [all[1]])
        #expect(model.state.search == .ready(all))
        model.updateFilter(.ALL)
        #expect(model.filteredResults == all)
        #expect(await api.counts().0 == 1)
    }
    @Test func completedNewSearchSurvivesLateOldCompletion() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.updateQuery("A")
        guard await settle({ await api.counts().0 == 1 }) else { Issue.record("missing A"); return }
        model.updateQuery("B")
        guard await settle({ await api.counts().0 == 2 }) else { Issue.record("missing B"); await api.drain(); return }
        await api.finishSearch(1, .success([sample(2)]))
        #expect(await settle { model.state.search == .ready([sample(2)]) })
        await api.finishSearch(0, .failure(MarketError.network))
        for _ in 0..<50 { await Task.yield() }
        #expect(model.state.search == .ready([sample(2)]))
        await api.drain()
    }
    @Test func restoredNonDirtyNonemptyPricePreserved() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.restore(snapshot: MarketDraft(selected: sample(), unitPrice: "90.00", priceEdited: false))
        guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing restored quote"); return }
        await api.finishPrice(0, .success(quote()))
        #expect(await settle { model.state.price == .ready(quote()) })
        #expect(model.state.draft.unitPrice == "90.00")
        await api.drain()
    }
    @Test func explicitRetryAfterFailureAndNoAutomaticRetry() async {
        let api = ControlledAPI(); let model = MarketModel(api: api, debounce: {})
        model.updateQuery("x")
        guard await settle({ await api.counts().0 == 1 }) else { Issue.record("missing search"); return }
        await api.finishSearch(0, .failure(MarketError.network))
        #expect(await settle { model.state.search == .failed(.network) })
        #expect(await api.counts().0 == 1)
        model.retrySearch()
        #expect(await settle { await api.counts().0 == 2 })
        await api.drain()
        model.select(sample())
        guard await settle({ await api.counts().1 == 1 }) else { Issue.record("missing quote"); return }
        await api.finishPrice(0, .failure(MarketError.notFound))
        #expect(await settle { model.state.price == .failed(.notFound) })
        model.editPrice("88")
        model.retryPrice()
        #expect(await settle { await api.counts().1 == 2 })
        await api.finishPrice(1, .success(quote()))
        #expect(await settle { model.state.price == .ready(quote()) })
        #expect(model.state.draft.unitPrice == "88")
        await api.drain()
    }
}
