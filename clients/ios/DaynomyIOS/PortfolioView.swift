import SwiftUI
import Observation
import DaynomyCore

func portfolioToday() -> String {
    let formatter = DateFormatter(); formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.timeZone = TimeZone(identifier: "Asia/Seoul")
    formatter.dateFormat = "yyyy-MM-dd"; return formatter.string(from: Date())
}
func moneyText(_ amount: Decimal) -> String { NSDecimalNumber(decimal: amount).stringValue }
func portfolioError(_ error: any Error) -> String {
    if let value = error as? PortfolioError {
        switch value {
        case .oversell: return "해당 거래일의 보유 수량보다 많이 매도할 수 없어요. 이후 거래도 확인해 주세요."
        case .invalidTrade: return "날짜·수량·금액을 확인해 주세요. 단가 4자리, 수수료·세금 2자리, 환율 6자리까지 입력할 수 있어요."
        case .precisionOverflow: return "금액 또는 수량이 너무 커 정확하게 계산할 수 없어요."
        case .duplicateID: return "이미 등록한 거래입니다."
        case .notFound: return "거래를 찾지 못했어요. 내역을 새로 확인해 주세요."
        }
    }
    return friendlyServiceError(error)
}
func holdingBody(_ holdings: [LocalHolding]) -> ServiceValue {
    .array(holdings.map { .object(["assetId": .number(String($0.stock.assetId)), "quantity": .number(String($0.quantity)), "averagePurchasePrice": .number(moneyText($0.averagePurchasePrice))]) })
}
func stockFromValue(_ value: ServiceValue) throws -> Stock {
    guard let id = Int64(value.field("assetId").display), id > 0,
          !value.field("assetCode").display.isEmpty, !value.field("name").display.isEmpty else { throw MarketError.invalidResponse }
    let code = value.field("assetCode").display
    return Stock(assetId: id, assetCode: code, name: value.field("name").display,
                 category: value.field("category").display.isEmpty ? "STOCK" : value.field("category").display,
                 market: value.field("market").display, currency: ["USD", "KRW"].contains(value.field("currency").display) ? value.field("currency").display : (code.hasSuffix(".US") ? "USD" : "KRW"))
}

@Observable @MainActor final class PortfolioStore {
    var guest = PortfolioEngine(today: portfolioToday())
    var holdings: [LocalHolding] = []
    var transactions: [LocalTrade] = []
    var history: [ServiceValue] = []
    var calculation: ServiceValue = .null
    var performance: ServiceValue = .null
    var realized = Decimal.zero
    var busy = false
    var error = ""
    var member = false
    var accountKey = ""
    private var loadGeneration: UInt64 = 0
    func reload(client: ServiceClient, member: Bool, accountKey: String) async {
        loadGeneration &+= 1; let generation = loadGeneration
        self.member = member
        if self.accountKey != accountKey {
            holdings = []; transactions = []; history = []; calculation = .null; performance = .null; realized = 0
            self.accountKey = accountKey
        }
        busy = true; error = ""
        defer { if loadGeneration == generation { busy = false } }
        do {
            if member {
                let value = try await client.request(path: "/api/users/me/portfolio")
                try Task.checkCancellation(); guard loadGeneration == generation else { return }
                guard let rows = value.field("holdings").array,
                      let profit = Decimal(string: value.field("totalRealizedProfitLoss").display) else { throw MarketError.invalidResponse }
                let nextHoldings = try rows.map { item in
                    guard let quantity = Int64(item.field("quantity").display), quantity > 0,
                          let price = Decimal(string: item.field("averagePurchasePrice").display), price > 0 else { throw MarketError.invalidResponse }
                    return LocalHolding(stock: try stockFromValue(item), quantity: quantity, averagePurchasePrice: price)
                }
                // A valuation belongs to one holdings snapshot, including when a later request fails.
                calculation = .null; holdings = nextHoldings; realized = profit
                history = []; transactions = []
                let histories = try await client.request(path: "/api/portfolio/histories", query: ["from": "1900-01-01", "to": portfolioToday()])
                try Task.checkCancellation(); guard loadGeneration == generation else { return }; guard let rows = histories.array else { throw MarketError.invalidResponse }
                let nextTransactions = try rows.filter { ["BUY", "SELL"].contains($0.field("changeType").display) }.map { item in
                    guard let id = Int64(item.field("historyId").display), let quantity = Int64(item.field("transactionQuantity").display),
                          let type = LocalTradeType(rawValue: item.field("changeType").display) else { throw MarketError.invalidResponse }
                    return LocalTrade(id: id, stock: try stockFromValue(item), type: type, date: item.field("effectiveDate").display, quantity: quantity,
                                      unitPrice: item.field("unitPrice").display, fee: item.field("fee").display, tax: item.field("tax").display,
                                      exchangeRate: item.field("exchangeRate").display.isEmpty ? nil : item.field("exchangeRate").display)
                }
                history = rows; transactions = nextTransactions
            } else {
                let nextHoldings = try guest.holdings()
                let nextRealized = try guest.realizedProfitLoss()
                calculation = .null; holdings = nextHoldings; transactions = guest.trades; realized = nextRealized
            }
            if !holdings.isEmpty {
                let result = try await client.request(path: "/api/portfolio/calculate", method: "POST", body: .object(["holdings": holdingBody(holdings)]), csrf: true, retryUnauthorized: member)
                try Task.checkCancellation(); guard loadGeneration == generation else { return }
                guard result.field("holdings").array != nil, ["COMPLETE", "PARTIAL", "MIXED_DATES"].contains(result.field("pricingStatus").display) else { throw MarketError.invalidResponse }
                calculation = result
            } else { calculation = .null }
        } catch {
            if !Task.isCancelled && loadGeneration == generation {
                if (error as? ServiceError)?.code == "PORTFOLIO_NOT_FOUND" { holdings = []; transactions = []; history = []; realized = 0; calculation = .null }
                else { self.error = portfolioError(error) }
            }
        }
    }
    func save(_ trade: LocalTrade, editing: Bool, client: ServiceClient) async -> Bool {
        guard !busy else { return false }; let startedAccount = accountKey; busy = true; error = ""
        do {
            if member {
                // Validation is independent of current holdings; historical replay belongs to the server.
                let initial = LocalHolding(stock: trade.stock, quantity: trade.quantity, averagePurchasePrice: 1)
                var validation = PortfolioEngine(openingHoldings: trade.type == .SELL ? [initial] : [], today: portfolioToday())
                try validation.add(trade)
                var fields: [String: ServiceValue] = ["tradeDate": .string(trade.date), "quantity": .number(String(trade.quantity)), "unitPrice": .number(trade.unitPrice), "fee": .number(trade.fee), "tax": .number(trade.tax)]
                if let rate = trade.exchangeRate { fields["exchangeRate"] = .number(rate) }
                if !editing { fields["assetId"] = .number(String(trade.stock.assetId)); fields["type"] = .string(trade.type.rawValue) }
                let value = try await client.request(path: editing ? "/api/portfolio/transactions/\(trade.id)" : "/api/portfolio/transactions", method: editing ? "PATCH" : "POST", body: .object(fields), csrf: true)
                guard accountKey == startedAccount else { busy = false; return false }
                guard Int64(value.field("transactionId").display) != nil, value.field("totalRealizedProfitLoss").number != nil else { throw MarketError.invalidResponse }
            } else {
                var current = try refreshedGuest()
                if editing { try current.update(trade) } else { try current.add(trade) }
                guest = current
            }
            busy = false; return true
        } catch { if accountKey == startedAccount { self.error = mutationError(error) }; busy = false; return false }
    }
    var nextGuestID: Int64 { max(guest.trades.map(\.id).max() ?? 0, guest.holdingChanges.map(\.id).max() ?? 0) + 1 }
    private func refreshedGuest() throws -> PortfolioEngine {
        var refreshed = PortfolioEngine(today: portfolioToday())
        var events: [(date: String, id: Int64, trade: LocalTrade?, change: HoldingAdjustment?)] = guest.trades.map { ($0.date, $0.id, $0, nil) }
        events += guest.holdingChanges.map { ($0.date, $0.id, nil, $0) }
        for event in events.sorted(by: { $0.date == $1.date ? $0.id < $1.id : $0.date < $1.date }) {
            if let trade = event.trade { try refreshed.add(trade) }
            if let change = event.change { try refreshed.changeHolding(change) }
        }
        return refreshed
    }
    private func mutationError(_ error: any Error) -> String {
        if member, let service = error as? ServiceError, service.status == 0, ["NETWORK", "INVALID_JSON"].contains(service.code ?? "") {
            return "처리 결과를 확인하지 못했어요. 중복 기록을 피하려면 창을 닫고 내역을 새로 확인한 뒤 다시 시도해 주세요."
        }
        return portfolioError(error)
    }
    func adjustHolding(_ holding: LocalHolding, quantity: String, average: String, removing: Bool, client: ServiceClient) async -> Bool {
        guard !busy else { return false }; let startedAccount = accountKey; busy = true; error = ""
        defer { busy = false }
        do {
            var body: ServiceValue?
            if !removing {
                guard quantity.range(of: "^[0-9]+$", options: .regularExpression) != nil,
                      let count = Int64(quantity), count > 0, count <= 9_007_199_254_740_991,
                      average.range(of: #"^[0-9]{1,15}(\.[0-9]{1,2})?$"#, options: .regularExpression) != nil,
                      let price = Decimal(string: average), price >= Decimal(string: "0.01")! else { throw PortfolioError.invalidTrade }
                body = .object(["quantity": .number(String(count)), "averagePurchasePrice": .number(moneyText(price))])
            }
            if !member {
                let count: Int64
                if removing { count = 0 }
                else { guard let parsed = Int64(quantity) else { throw PortfolioError.invalidTrade }; count = parsed }
                var proposed = try refreshedGuest()
                let change = HoldingAdjustment(id: nextGuestID, stock: holding.stock, date: portfolioToday(), quantity: removing ? 0 : count, averagePurchasePrice: removing ? "0" : average, kind: removing ? .removed : .adjusted)
                try proposed.changeHolding(change)
                guest = proposed
                return true
            }
            let result = try await client.request(path: "/api/users/me/portfolio/holdings/\(holding.stock.assetId)", method: removing ? "DELETE" : "PATCH", body: body, csrf: true)
            guard accountKey == startedAccount else { return false }
            if !removing { guard result.field("assetId").display == String(holding.stock.assetId), result.field("quantity").number != nil else { throw MarketError.invalidResponse } }
            return true
        } catch { if accountKey == startedAccount { self.error = mutationError(error) }; return false }
    }
    func delete(_ trade: LocalTrade, client: ServiceClient) async -> Bool {
        guard !busy else { return false }; let startedAccount = accountKey; busy = true; error = ""
        defer { busy = false }
        do {
            if member {
                let result = try await client.request(path: "/api/portfolio/transactions/\(trade.id)", method: "DELETE", csrf: true)
                guard accountKey == startedAccount else { return false }
                guard Int64(result.field("transactionId").display) != nil else { throw MarketError.invalidResponse }
            } else { try guest.remove(id: trade.id) }
            return true
        } catch { if accountKey == startedAccount { self.error = mutationError(error) }; return false }
    }
}

@MainActor struct PortfolioView: View {
    let client: ServiceClient
    let marketAPI: (any MarketAPI)?
    @Environment(AppSession.self) private var session
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var store = PortfolioStore()
    @State private var editor = false
    @State private var editing: LocalTrade?
    @State private var deleting: LocalTrade?
    @State private var adjusting: LocalHolding?
    @State private var retry = 0
    @State private var ledgerTab = "holdings"
    @State private var amountsHidden = false
    init(client: ServiceClient, marketAPI: (any MarketAPI)? = nil) { self.client = client; self.marketAPI = marketAPI }
    private var accountKey: String { session.user?.field("id").display ?? "guest" }
    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            Text(session.isLoggedIn ? "내 자산 요약" : "게스트 투자 기록").foregroundStyle(.secondary)
                            Spacer()
                            Button(amountsHidden ? "금액 보기" : "금액 숨기기") { amountsHidden.toggle() }
                                .font(.subheadline).frame(minHeight: 44).accessibilityIdentifier("portfolioAmountVisibility")
                        }
                        if !store.holdings.isEmpty {
                            Text("전체 자산 평가금액").foregroundStyle(.secondary)
                            Text(displayAmount("totalEvaluationAmount")).font(.largeTitle.bold()).monospacedDigit()
                            LabeledContent("평가손익", value: displayAmount("totalProfitLoss"))
                            LabeledContent("총 매입금액", value: displayAmount("totalPurchaseAmount"))
                            LabeledContent("실현손익", value: amountsHidden ? "숨김" : "\(moneyText(store.realized)) 원")
                        } else if !store.busy && store.error.isEmpty {
                            Text(store.transactions.isEmpty ? "첫 투자 기록을 시작해 보세요" : "현재 보유 자산이 없어요").font(.title2.bold())
                        }
                        if store.holdings.isEmpty && !store.transactions.isEmpty { LabeledContent("실현손익", value: amountsHidden ? "숨김" : "\(moneyText(store.realized)) 원") }
                        if !session.isLoggedIn { Text("게스트 기록은 현재 앱 실행 중에만 유지돼요.").font(.footnote).foregroundStyle(.secondary) }
                        if store.calculation.field("pricingStatus").display == "PARTIAL" { Text("종가가 없는 종목은 평가금액에서 제외돼요.").font(.footnote).foregroundStyle(.secondary) }
                        if store.calculation.field("pricingStatus").display == "MIXED_DATES" { Text("종목마다 종가 기준일이 달라요.").font(.footnote).foregroundStyle(.secondary) }
                        actionLayout {
                            Button { editing = nil; editor = true } label: { Label("거래 기록", systemImage: "plus").frame(maxWidth: .infinity, minHeight: 44).padding(.horizontal, 12).foregroundStyle(Color(uiColor: .systemBackground)) }
                                .buttonStyle(.borderedProminent).tint(.primary).buttonBorderShape(.capsule)
                                .accessibilityIdentifier("addTransaction").disabled(store.busy)
                            if let marketAPI {
                                NavigationLink { MarketView(api: marketAPI, client: client) } label: { Label("종목 조회", systemImage: "magnifyingglass").frame(maxWidth: .infinity, minHeight: 44) }
                                    .accessibilityIdentifier("portfolioMarket")
                            }
                        }
                    }.padding(.vertical, 12)
                }.listRowSeparator(.hidden)
                Section {
                    Picker("자산 보기", selection: $ledgerTab) {
                        Text("보유 자산").tag("holdings")
                        Text("거래 내역").tag("trades")
                    }.pickerStyle(.segmented).accessibilityIdentifier("portfolioLedgerPicker")
                }.listRowSeparator(.hidden)
                if store.busy { ProgressView("투자 기록 확인 중") }
                if !store.error.isEmpty { Section { Text(store.error).accessibilityIdentifier("portfolioError"); Button("다시 확인") { retry += 1 } } }
                if ledgerTab == "holdings" {
                Section("보유 자산") {
                    if store.holdings.isEmpty { Text(store.transactions.isEmpty ? "아직 보유 자산이 없어요. 첫 거래를 기록해 보세요." : "현재 보유 자산이 없어요.").foregroundStyle(.secondary) }
                    ForEach(store.holdings, id: \.stock.assetId) { holding in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(holding.stock.name).font(.headline)
                            Text(amountsHidden ? "\(holding.quantity) 주 · 평균 매입가 숨김" : "\(holding.quantity) 주 · 평균 매입가 \(moneyText(holding.averagePurchasePrice)) 원").foregroundStyle(.secondary)
                            if let result = store.calculation.field("holdings").rows.first(where: { $0.field("assetId").display == String(holding.stock.assetId) }) {
                                Text(amountsHidden ? "평가 금액 숨김" : result.field("priceAvailable").flag ? "평가 \(result.field("evaluationAmount").display) 원 · \(result.field("returnRate").display)% · \(result.field("baseDate").display) 기준" : "종가 정보 없음").font(.caption).foregroundStyle(.secondary)
                            }
                            Button("보유 수량·원가 조정") { adjusting = holding }.font(.subheadline).disabled(store.busy)
                        }.padding(.vertical, 4)
                    }
                }
                }
                if ledgerTab == "trades" {
                Section("거래 내역") {
                    if store.transactions.isEmpty { Text("기록한 매수·매도 거래가 없어요.").foregroundStyle(.secondary) }
                    ForEach(store.transactions.sorted { $0.date > $1.date || ($0.date == $1.date && $0.id > $1.id) }, id: \.id) { trade in
                        Button { editing = trade; editor = true } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("\(trade.stock.name) · \(trade.type == .BUY ? "매수" : "매도")").foregroundStyle(.primary)
                                Text(amountsHidden ? "\(trade.date) · \(trade.quantity) 주 · 단가 숨김" : "\(trade.date) · \(trade.quantity) 주 × \(trade.unitPrice) \(trade.stock.currency ?? "KRW")").font(.subheadline).foregroundStyle(.secondary)
                            }.padding(.vertical, 4)
                        }.swipeActions { Button("삭제", role: .destructive) { deleting = trade }.disabled(store.busy) }
                    }
                }
                }
                if ledgerTab == "trades" && !session.isLoggedIn && !store.guest.holdingChanges.isEmpty {
                    Section("보유 조정 이력") {
                        ForEach(store.guest.holdingChanges.reversed(), id: \.id) { change in
                            VStack(alignment: .leading, spacing: 5) {
                                Text(change.stock.name).font(.headline)
                                Text("\(change.date) · \(change.kind == .removed ? "보유 삭제" : "보유 조정")").foregroundStyle(.secondary)
                                if change.kind == .adjusted { Text(amountsHidden ? "\(change.quantity) 주 · 평균 매입가 숨김" : "\(change.quantity) 주 · 평균 매입가 \(change.averagePurchasePrice) 원").font(.subheadline) }
                            }
                        }
                    }
                }
                if session.isLoggedIn {
                    Section("투자 살펴보기") {
                        NavigationLink("자산 추이와 변경 이력") { PortfolioHistoryView(client: client) }
                    }
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(Color(uiColor: .systemBackground))
            .navigationTitle("포트폴리오")
            .refreshable { await reload() }
            .task(id: "\(accountKey)|\(session.isLoggedIn)|\(retry)") { await reload() }
            .sheet(isPresented: $editor) {
                TransactionEditorView(client: client, marketAPI: marketAPI, store: store, existing: editing) { await reload() }
            }
            .sheet(isPresented: Binding(get: { adjusting != nil }, set: { if !$0 { adjusting = nil } })) {
                if let holding = adjusting { HoldingAdjustmentView(client: client, store: store, holding: holding) { await reload() } }
            }
            .confirmationDialog("이 거래를 삭제할까요? 이후 거래의 보유 수량도 다시 계산합니다.", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
                Button("거래 삭제", role: .destructive) { if let trade = deleting { Task { if await store.delete(trade, client: client) { await reload() }; deleting = nil } } }
            }
        }
    }
    private var actionLayout: AnyLayout {
        typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 12)) : AnyLayout(HStackLayout(spacing: 12))
    }
    private func reload() async { await store.reload(client: client, member: session.isLoggedIn, accountKey: accountKey) }
    private func displayAmount(_ key: String) -> String { if amountsHidden { return "숨김" }; let text = store.calculation.field(key).display; return text.isEmpty ? "확인 전" : "\(text) 원" }
}

@MainActor struct TransactionEditorView: View {
    let client: ServiceClient
    let marketAPI: (any MarketAPI)?
    let store: PortfolioStore
    let existing: LocalTrade?
    let saved: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var selected: Stock?
    @State private var country: Country = .KR
    @State private var query = ""
    @State private var matches: [Stock] = []
    @State private var type = LocalTradeType.BUY
    @State private var date = portfolioToday()
    @State private var quantity = "1"
    @State private var price = ""
    @State private var fee = "0"
    @State private var tax = "0"
    @State private var rate = ""
    @State private var priceEdited = false
    @State private var searching = false
    @State private var searchGeneration: UInt64 = 0
    @State private var quoteStatus = ""
    @State private var localError = ""
    @State private var quoteTask: Task<Void, Never>?
    private var usd: Bool { guard let selected else { return false }; return (selected.currency ?? (selected.assetCode.hasSuffix(".US") ? "USD" : "KRW")) == "USD" }
    var body: some View {
        NavigationStack {
            Form {
                if let stock = selected {
                    Section("종목") {
                        Text(stock.name).font(.headline); Text(stock.assetCode).foregroundStyle(.secondary)
                        if existing == nil { Button("종목 변경") { selected = nil; quoteTask?.cancel(); price = ""; priceEdited = false; quoteStatus = "" } }
                    }
                } else {
                    Section("종목 선택") {
                        Picker("시장", selection: $country) { Text("국내").tag(Country.KR); Text("미국").tag(Country.US) }
                        TextField("종목명 또는 코드", text: $query).accessibilityIdentifier("tradeStockQuery")
                        if searching { ProgressView("검색 중") }
                        ForEach(matches, id: \.assetId) { stock in Button(stock.name) { select(stock) }.accessibilityIdentifier("tradeStock_\(stock.assetId)") }
                        if !searching && !query.isEmpty && matches.isEmpty { Text("검색 결과가 없어요.").foregroundStyle(.secondary) }
                    }
                }
                Section("거래 입력") {
                    Picker("유형", selection: $type) { Text("매수").tag(LocalTradeType.BUY); Text("매도").tag(LocalTradeType.SELL) }.disabled(existing != nil)
                    LabeledContent("거래일") { TextField("YYYY-MM-DD", text: $date) }.accessibilityIdentifier("tradeDate").textInputAutocapitalization(.never)
                    LabeledContent("수량") { TextField("정수", text: $quantity) }.keyboardType(.numberPad).accessibilityIdentifier("tradeQuantity")
                    TextField("단가", text: Binding(get: { price }, set: { price = $0; priceEdited = true })).keyboardType(.decimalPad).accessibilityIdentifier("tradeUnitPrice")
                    if !quoteStatus.isEmpty { Text(quoteStatus).font(.footnote).foregroundStyle(.secondary) }
                    LabeledContent("수수료") { TextField("0", text: $fee) }.keyboardType(.decimalPad).accessibilityIdentifier("tradeFee")
                    LabeledContent("세금") { TextField("0", text: $tax) }.keyboardType(.decimalPad).accessibilityIdentifier("tradeTax")
                    if usd {
                        TextField("1 USD당 원화 환율", text: $rate).keyboardType(.decimalPad).accessibilityIdentifier("tradeExchangeRate")
                        Text("미국 종목의 단가·수수료·세금은 USD로 입력해 주세요. 매입 원가와 손익은 입력한 환율로 원화 환산합니다.").font(.footnote).foregroundStyle(.secondary)
                    }
                }
                if !localError.isEmpty { Text(localError) }
                if !store.error.isEmpty { Text(store.error) }
                if store.busy { ProgressView("거래 저장 중") }
                Button(existing == nil ? "거래 등록" : "변경 저장") { Task { await submit() } }.disabled(selected == nil || store.busy).accessibilityIdentifier("saveTransaction")
            }
            .navigationTitle(existing == nil ? "거래 기록" : "거래 수정")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("닫기") { dismiss() }.disabled(store.busy) } }
            .scrollDismissesKeyboard(.interactively)
            .task(id: "\(query)|\(country.rawValue)|\(selected?.assetId.description ?? "none")") { await search() }
            .onAppear {
                store.error = ""
                if let trade = existing { selected = trade.stock; type = trade.type; date = trade.date; quantity = String(trade.quantity); price = trade.unitPrice; fee = trade.fee; tax = trade.tax; rate = trade.exchangeRate ?? ""; priceEdited = true }
            }
            .onDisappear { quoteTask?.cancel(); searchGeneration &+= 1; searching = false; matches = [] }
        }
    }
    private func search() async {
        searchGeneration &+= 1; let generation = searchGeneration
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        let requestedCountry = country
        matches = []; searching = false; localError = ""
        guard selected == nil, !text.isEmpty, !Task.isCancelled else { return }
        searching = true
        defer { if searchGeneration == generation { searching = false } }
        do {
            try await Task.sleep(for: .milliseconds(300))
            let result: [Stock]
            if let marketAPI { result = try await marketAPI.search(keyword: text, country: requestedCountry) }
            else {
                let response = try await client.request(path: "/api/stocks", query: ["q": text, "country": requestedCountry.rawValue], retryUnauthorized: false)
                result = try response.field("stocks").rows.map(stockFromValue)
            }
            try Task.checkCancellation()
            guard searchGeneration == generation, selected == nil, country == requestedCountry,
                  query.trimmingCharacters(in: .whitespacesAndNewlines) == text else { return }
            matches = result
        } catch {
            if !Task.isCancelled && searchGeneration == generation && selected == nil && country == requestedCountry && query.trimmingCharacters(in: .whitespacesAndNewlines) == text {
                localError = "종목 검색에 실패했어요. 검색어를 다시 입력해 주세요."
            }
        }
    }
    private func select(_ stock: Stock) {
        searchGeneration &+= 1; searching = false; matches = []
        selected = stock; price = ""; priceEdited = false; quoteStatus = "최근 종가를 확인하는 중이에요."; quoteTask?.cancel()
        quoteTask = Task {
            do {
                let amount: String, baseDate: String
                if let marketAPI { let quote = try await marketAPI.latestPrice(assetId: stock.assetId); amount = quote.closePrice; baseDate = quote.baseDate }
                else {
                    let quote = try await client.request(path: "/api/stocks/\(stock.assetId)/price", retryUnauthorized: false)
                    amount = quote.field("closePrice").display; baseDate = quote.field("baseDate").display
                }
                try Task.checkCancellation(); guard selected?.assetId == stock.assetId else { return }
                if !priceEdited { price = amount }
                quoteStatus = "\(baseDate) 종가 기준 · 직접 단가를 수정할 수 있어요."
            } catch { if !Task.isCancelled && selected?.assetId == stock.assetId { quoteStatus = "종가를 확인하지 못했어요. 거래 단가를 직접 입력해 주세요." } }
        }
    }
    private func submit() async {
        guard let selected, let count = Int64(quantity), quantity.range(of: "^[0-9]+$", options: .regularExpression) != nil else { localError = "수량은 1 이상의 정수로 입력해 주세요."; return }
        let id = existing?.id ?? store.nextGuestID
        let trade = LocalTrade(id: id, stock: selected, type: type, date: date, quantity: count, unitPrice: price, fee: fee, tax: tax, exchangeRate: usd ? rate : nil)
        if await store.save(trade, editing: existing != nil, client: client) { await saved(); dismiss() }
    }
}

@MainActor struct HoldingAdjustmentView: View {
    let client: ServiceClient
    let store: PortfolioStore
    let holding: LocalHolding
    let saved: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var quantity = ""
    @State private var average = ""
    @State private var confirmRemoval = false
    var body: some View {
        NavigationStack {
            Form {
                Section(holding.stock.name) {
                    LabeledContent("종목 코드", value: holding.stock.assetCode)
                    TextField("보유 수량", text: $quantity).keyboardType(.numberPad)
                    TextField("평균 매입가 (원화)", text: $average).keyboardType(.decimalPad)
                    Text("실제 매수·매도는 거래 기록을 이용해 주세요. 이 기능은 현재 보유 수량과 원가를 정정하고 조정 이력을 남겨요.").font(.footnote).foregroundStyle(.secondary)
                }
                if !store.error.isEmpty { Text(store.error) }
                if store.busy { ProgressView("조정 내용 저장 중") }
                Button("보유 정보 저장") { Task { await apply(removing: false) } }.disabled(store.busy)
                Section {
                    Button("현재 보유에서 삭제", role: .destructive) { confirmRemoval = true }.disabled(store.busy)
                } footer: { Text("보유 정보 삭제는 매도 거래가 아니에요. 기존 거래 내역은 유지돼요.") }
            }
            .navigationTitle("보유 정보 정정")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("닫기") { dismiss() }.disabled(store.busy) } }
            .onAppear { quantity = String(holding.quantity); average = moneyText(holding.averagePurchasePrice); store.error = "" }
            .confirmationDialog("현재 보유에서 이 종목을 삭제할까요?", isPresented: $confirmRemoval, titleVisibility: .visible) {
                Button("보유 삭제", role: .destructive) { Task { await apply(removing: true) } }
            }
        }
    }
    private func apply(removing: Bool) async {
        if await store.adjustHolding(holding, quantity: quantity, average: average, removing: removing, client: client) { await saved(); dismiss() }
    }
}
