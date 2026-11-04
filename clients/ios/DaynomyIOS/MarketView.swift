import SwiftUI
import DaynomyCore

@MainActor struct MarketView: View {
    let client: ServiceClient?
    @State private var model: MarketModel
    @FocusState private var priceFocused: Bool
    @Environment(\.scenePhase) private var scenePhase

    init(api: any MarketAPI, client: ServiceClient? = nil) { self.client = client; _model = State(initialValue: MarketModel(api: api)) }

    var body: some View {
        Form {
                if let stock = model.state.draft.selected {
                    Section("선택한 종목") {
                        stockLabel(stock)
                        if let client { NavigationLink("종목 관련 자료") { AssetContentsView(client: client, assetId: stock.assetId) } }
                        Button("다른 종목 선택") { priceFocused = false; model.changeStock() }
                            .accessibilityIdentifier("changeStock")
                            .frame(minHeight: 44)
                    }
                    Section {
                        TextField("단가", text: Binding(get: { model.state.draft.unitPrice }, set: model.editPrice))
                            .accessibilityIdentifier("unitPrice")
                            .keyboardType(.decimalPad)
                            .focused($priceFocused)
                            .accessibilityLabel("단가, \(stock.currency ?? "KRW")")
                            .accessibilityHint("직접 입력하거나 지운 값은 종가 조회로 덮어쓰지 않습니다")
                            .frame(minHeight: 44)
                        LabeledContent("통화", value: stock.currency ?? (stock.assetCode.hasSuffix(".US") ? "USD" : "KRW"))
                        priceStatus
                    } header: { Text("단가") } footer: {
                        Text("최근 저장된 종가를 불러옵니다. 실시간 시세가 아니며 단가는 직접 수정할 수 있어요.")
                    }
                } else {
                    Section("종목 검색") {
                        Picker("국가", selection: Binding(get: { model.state.draft.country }, set: model.updateCountry)) {
                            Text("국내").tag(Country.KR)
                            Text("미국").tag(Country.US)
                        }.accessibilityIdentifier("stockCountryPicker")
                        TextField("종목명 또는 코드", text: Binding(get: { model.state.draft.query }, set: model.updateQuery))
                            .accessibilityIdentifier("stockQuery")
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.search)
                            .accessibilityLabel("종목명 또는 코드 검색")
                            .frame(minHeight: 44)
                        Picker("종류", selection: Binding(get: { model.state.draft.filter }, set: model.updateFilter)) {
                            Text("전체").tag(CategoryFilter.ALL)
                            Text("주식").tag(CategoryFilter.STOCK)
                            Text("ETF").tag(CategoryFilter.ETF)
                        }.accessibilityIdentifier("stockCategoryPicker")
                    }
                    Section("검색 결과") { searchStatus }
                }
            }
            .navigationTitle("종목과 단가")
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("완료") { priceFocused = false }
                        .frame(minHeight: 44)
                }
            }
        .onAppear { model.activate() }
        .onDisappear { model.deactivate() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { model.activate() }
            else if phase == .background { model.deactivate() }
        }
    }

    @ViewBuilder private var searchStatus: some View {
        switch model.state.search {
        case .idle:
            Text("종목명이나 코드를 입력해 주세요.").foregroundStyle(.secondary)
        case .loading:
            ProgressView("종목 검색 중")
        case .failed:
            Text("검색 결과를 불러오지 못했어요.")
            Button("검색 다시 시도") { model.retrySearch() }.accessibilityIdentifier("retrySearch").frame(minHeight: 44)
        case .ready:
            if model.filteredResults.isEmpty {
                Text("검색 결과가 없어요. 검색어나 종목 종류를 바꿔 보세요.").foregroundStyle(.secondary)
            } else {
                ForEach(model.filteredResults, id: \.assetId) { stock in
                    Button { model.select(stock) } label: { stockLabel(stock).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle()) }
                        .accessibilityIdentifier("stockResult_\(stock.assetId)")
                        .buttonStyle(.plain)
                        .accessibilityHint("선택하고 최근 저장 종가 조회")
                }
            }
        }
    }

    @ViewBuilder private var priceStatus: some View {
        switch model.state.price {
        case .idle: EmptyView()
        case .loading: ProgressView("최근 저장 종가 조회 중")
        case .ready(let quote):
            LabeledContent("종가 기준일", value: quote.baseDate)
            LabeledContent("최근 저장 종가", value: quote.closePrice)
        case .failed(let error):
            Text(error == .notFound ? "저장된 최근 종가가 없어요. 단가를 직접 입력해 주세요." : "최근 종가를 불러오지 못했어요. 단가를 직접 입력해 주세요.")
            Button("종가 다시 조회") { model.retryPrice() }.accessibilityIdentifier("retryPrice").frame(minHeight: 44)
        }
    }

    private func stockLabel(_ stock: Stock) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(stock.name).font(.headline)
            Text("\(stock.assetCode) · \(stock.market) · \(stock.category == "ETF" ? "ETF" : "주식")")
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .padding(.vertical, 6)
        .frame(minHeight: 44, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}
