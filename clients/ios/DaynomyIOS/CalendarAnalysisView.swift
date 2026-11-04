import SwiftUI
import Charts
import DaynomyCore

@MainActor struct CalendarAnalysisView: View {
    let client: ServiceClient
    var holdings: [LocalHolding] = []
    var calculation: ServiceValue = .null
    var showCalendar = true
    @Environment(AppSession.self) private var session
    @State private var month = Date()
    @State private var scope = "PORTFOLIO"
    @State private var calendar: ServiceValue = .null
    @State private var savedAnalysis: ServiceValue = .null
    @State private var analysis: ServiceValue = .null
    @State private var history: [ServiceValue] = []
    @State private var loading = false
    @State private var analyzing = false
    @State private var error = ""
    @State private var analysisError = ""
    @State private var retry = 0
    @State private var showAnalysisHistory = false
    @State private var analysisAccountKey = ""
    @State private var analysisGeneration: UInt64 = 0
    @State private var calendarGeneration: UInt64 = 0
    private var yearNumber: Int { Calendar(identifier: .gregorian).component(.year, from: month) }
    private var monthNumber: Int { Calendar(identifier: .gregorian).component(.month, from: month) }
    private var accountKey: String { "\(session.isLoggedIn)|\(session.user?.field("id").display ?? "guest")" }
    private var requestKey: String { "\(yearNumber)|\(monthNumber)|\(scope)|\(accountKey)|\(retry)" }
    var body: some View {
        List {
            if showCalendar {
            Section("투자 캘린더") {
                HStack {
                    Button { changeMonth(-1) } label: { Image(systemName: "chevron.left").frame(minWidth: 44, minHeight: 44) }.accessibilityLabel("이전 달")
                    Spacer(); Text("\(String(yearNumber))년 \(monthNumber)월").font(.headline); Spacer()
                    Button { changeMonth(1) } label: { Image(systemName: "chevron.right").frame(minWidth: 44, minHeight: 44) }.accessibilityLabel("다음 달")
                }
                Picker("일정 범위", selection: $scope) { Text("내 투자 관련").tag("PORTFOLIO"); Text("모든 일정").tag("ALL") }
                Text("발표 일정과 과거 반응은 미래 수익을 보장하지 않아요.").font(.footnote).foregroundStyle(.secondary)
            }
            if loading { ProgressView("투자 일정 확인 중") }
            if !error.isEmpty { Section { Text(error); Button("일정 다시 확인") { retry += 1 } } }
            if !loading && error.isEmpty && calendar.field("events").rows.isEmpty { Text("이 기간에 표시할 일정이 없어요.").foregroundStyle(.secondary) }
            ForEach(Array(calendar.field("events").rows.enumerated()), id: \.offset) { _, event in
                Section {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(event.field("title").display).font(.headline)
                        Text(event.field("announcedAt").display).font(.subheadline).foregroundStyle(.secondary)
                        let value = event.field("value")
                        if !value.field("actualValue").display.isEmpty { LabeledContent("발표값", value: value.field("actualValue").display + " " + value.field("unit").display) }
                        if !value.field("previousValue").display.isEmpty { LabeledContent("이전값", value: value.field("previousValue").display + " " + value.field("unit").display) }
                        let impact = event.field("portfolioAnalysis")
                        Text(calendarStatus(impact.field("status").display)).font(.subheadline)
                        if impact.field("status").display == "READY" {
                            LabeledContent("관련 종목", value: impact.field("relatedAssetCount").display + "개")
                            LabeledContent("영향 수준", value: impactLabel(impact.field("impactLevel").display))
                            ForEach(Array(impact.field("historicalReactions").rows.enumerated()), id: \.offset) { _, reaction in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(directionLabel(reaction.field("direction").display)) 시 과거 중앙 수익률 \(nullableText(reaction.field("medianReturnRate")))%")
                                    Text("표본 \(reaction.field("sampleCount").display)회 · 범위 \(nullableText(reaction.field("lowerReturnRate"))) ~ \(nullableText(reaction.field("upperReturnRate")))%")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        if let url = publicLink(event.field("source").field("url").display) { Link(event.field("source").field("name").display.isEmpty ? "발표 출처" : event.field("source").field("name").display, destination: url).frame(minHeight: 44) }
                    }.padding(.vertical, 4)
                }
            }
            }
            Section("AI 포트폴리오 분석") {
                if session.isLoggedIn {
                    Text(analysisStatus(savedAnalysis.field("status").display)).foregroundStyle(.secondary)
                    if !savedAnalysis.field("lastSucceededAt").display.isEmpty { Text("최근 분석 \(savedAnalysis.field("lastSucceededAt").display)").font(.footnote).foregroundStyle(.secondary) }
                    if savedAnalysis.field("matchesCurrentPortfolio") == .bool(false), savedAnalysis.field("status").display != "EMPTY" { Text("현재 포트폴리오와 분석 당시의 보유 자산이 다를 수 있어요.").font(.footnote) }
                    HStack {
                        Button("분석 확인") { Task { await runAnalysis(refresh: false) } }.disabled(analyzing || holdings.isEmpty)
                        Spacer()
                        Button("새 근거로 갱신") { Task { await runAnalysis(refresh: true) } }.disabled(analyzing || holdings.isEmpty)
                    }
                    Button("분석 이력 보기") { Task { await loadAnalysisHistory() } }.disabled(analyzing)
                } else {
                    Text("보유 자산의 평가 비중으로 분석해요. 체험 제한이 적용될 수 있어요.").font(.footnote).foregroundStyle(.secondary)
                    Button("내 자산 분석하기") { Task { await runAnalysis(refresh: false) } }.disabled(analyzing || holdings.isEmpty || calculation.field("holdings").rows.isEmpty)
                }
                if holdings.isEmpty { Text("먼저 포트폴리오에 보유 자산을 기록해 주세요.").foregroundStyle(.secondary) }
                if analyzing { ProgressView("분석 요청 처리 중") }
                if !analysisError.isEmpty { Text(analysisError) }
            }
            if analysis.object != nil { PortfolioAnalysisResultView(value: analysis) }
            if showAnalysisHistory {
                Section("저장된 분석 이력") {
                    if history.isEmpty { Text("아직 분석 이력이 없어요.").foregroundStyle(.secondary) }
                    ForEach(Array(history.enumerated()), id: \.offset) { _, value in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(value.field("analyzedAt").display.isEmpty ? value.field("createdAt").display : value.field("analyzedAt").display).font(.subheadline).foregroundStyle(.secondary)
                            Text(value.field("overallImpact").display.isEmpty ? value.field("analysis").field("overallImpact").display : value.field("overallImpact").display)
                        }
                    }
                }
            }
        }
        .navigationTitle(showCalendar ? "일정과 분석" : "AI 포트폴리오 분석")
        .onChange(of: accountKey) { _, _ in synchronizeAnalysisAccount() }
        .onDisappear { analysisGeneration &+= 1; calendarGeneration &+= 1; analyzing = false; loading = false }
        .task(id: requestKey) { if showCalendar { await loadCalendar() } }
        .task(id: accountKey) { await loadSavedAnalysis() }
        .refreshable { if showCalendar { retry += 1 }; await loadSavedAnalysis() }
    }
    private func changeMonth(_ offset: Int) { if let value = Calendar(identifier: .gregorian).date(byAdding: .month, value: offset, to: month) { month = value } }
    private func loadCalendar() async {
        synchronizeAnalysisAccount()
        calendarGeneration &+= 1; let generation = calendarGeneration
        let startedRequest = requestKey
        loading = true; error = ""; calendar = .null
        defer { if calendarGeneration == generation { loading = false } }
        do {
            let query = ["year": String(yearNumber), "month": String(monthNumber), "scope": scope]
            let result: ServiceValue
            if session.isLoggedIn { result = try await client.request(path: "/api/users/me/investment-calendar", query: query) }
            else {
                let rows: [ServiceValue] = holdings.map { .object(["assetId": .number(String($0.stock.assetId)), "quantity": .number(String($0.quantity))]) }
                result = try await client.request(path: "/api/investment-calendar", method: "POST", query: query, body: .object(["holdings": .array(rows)]), csrf: true, retryUnauthorized: false)
            }
            try Task.checkCancellation(); guard calendarGeneration == generation, requestKey == startedRequest else { return }
            guard result.field("events").array != nil, result.field("year").number != nil, result.field("month").number != nil else { throw MarketError.invalidResponse }
            calendar = result
        } catch { if !Task.isCancelled && calendarGeneration == generation && requestKey == startedRequest { self.error = friendlyServiceError(error) } }
    }
    private func synchronizeAnalysisAccount() {
        guard analysisAccountKey != accountKey else { return }
        analysisAccountKey = accountKey; analysisGeneration &+= 1
        savedAnalysis = .null; analysis = .null; history = []; showAnalysisHistory = false
        analysisError = ""; analyzing = false
        calendarGeneration &+= 1; calendar = .null; error = ""; loading = false
    }
    private func loadSavedAnalysis() async {
        synchronizeAnalysisAccount()
        guard session.isLoggedIn, !analyzing else { return }
        analysisGeneration &+= 1
        let startedAccount = accountKey, generation = analysisGeneration
        do {
            let result = try await client.request(path: "/api/users/me/portfolio/analysis")
            try Task.checkCancellation(); guard accountKey == startedAccount, analysisGeneration == generation else { return }; try acceptSaved(result)
        } catch { if !Task.isCancelled && accountKey == startedAccount && analysisGeneration == generation { analysisError = friendlyServiceError(error) } }
    }
    private func acceptSaved(_ result: ServiceValue) throws {
        guard ["EMPTY", "READY", "PORTFOLIO_CHANGED", "PROCESSING", "RECHECK_REQUIRED", "FAILED"].contains(result.field("status").display) else { throw MarketError.invalidResponse }
        savedAnalysis = result
        analysis = result.field("status").display == "EMPTY" ? .null : (result.field("analysis").object != nil ? result.field("analysis") : .null)
        analysisError = result.field("status").display == "FAILED" ? "새 분석을 완료하지 못했어요. 이전 분석이 있다면 계속 볼 수 있어요." : ""
    }
    private func runAnalysis(refresh: Bool) async {
        synchronizeAnalysisAccount()
        guard !analyzing else { return }
        analysisGeneration &+= 1
        let startedAccount = accountKey, generation = analysisGeneration; analyzing = true; analysisError = ""
        defer { if accountKey == startedAccount && analysisGeneration == generation { analyzing = false } }
        do {
            if session.isLoggedIn {
                let result = try await client.request(path: "/api/users/me/portfolio/analysis" + (refresh ? "/refresh" : ""), method: "POST", csrf: true)
                try Task.checkCancellation(); guard accountKey == startedAccount, analysisGeneration == generation else { return }; try acceptSaved(result)
            } else {
                let assets = calculation.field("holdings").rows.compactMap { row -> ServiceValue? in
                    guard let raw = row.field("weight").number, let weight = Decimal(string: raw), weight > 0 else { return nil }
                    return .object(["assetName": .string(row.field("name").display), "weight": .number(raw)])
                }
                guard !assets.isEmpty else { throw ServiceError(status: 400, message: "평가 가능한 보유 자산이 없어요. 종가가 있는 자산을 먼저 확인해 주세요.") }
                let result = try await client.request(path: "/api/portfolio/analysis", method: "POST", body: .object(["assets": .array(assets)]), retryUnauthorized: false)
                try Task.checkCancellation(); guard accountKey == startedAccount, analysisGeneration == generation else { return }; guard result.field("impacts").array != nil, result.field("overallImpact").string != nil else { throw MarketError.invalidResponse }
                analysis = result
            }
        } catch {
            if !Task.isCancelled && accountKey == startedAccount && analysisGeneration == generation {
                if (error as? ServiceError)?.status == 409 { analysisError = "이미 분석 중이거나 포트폴리오가 변경됐어요. 잠시 후 분석 확인을 눌러 주세요." }
                else { analysisError = friendlyServiceError(error) }
            }
        }
    }
    private func loadAnalysisHistory() async {
        synchronizeAnalysisAccount()
        guard session.isLoggedIn, !analyzing else { return }; let startedAccount = accountKey, generation = analysisGeneration; analyzing = true; analysisError = ""
        defer { if accountKey == startedAccount && analysisGeneration == generation { analyzing = false } }
        do {
            let result = try await client.request(path: "/api/users/me/portfolio/analysis/history")
            try Task.checkCancellation(); guard accountKey == startedAccount, analysisGeneration == generation else { return }
            guard let rows = result.array ?? result.field("items").array ?? result.field("histories").array else { throw MarketError.invalidResponse }
            history = rows; showAnalysisHistory = true
        } catch { if accountKey == startedAccount && analysisGeneration == generation && !Task.isCancelled { analysisError = friendlyServiceError(error) } }
    }
}

struct PortfolioAnalysisResultView: View {
    let value: ServiceValue
    var body: some View {
        Section("분석 결과") {
            Text(value.field("overallImpact").display).font(.body)
            LabeledContent("분석 종목", value: "\(value.field("analyzedAssetCount").display) / \(value.field("totalAssetCount").display)")
            if !value.field("coverage").display.isEmpty { Text(value.field("coverage").display == "COMPLETE" ? "전체 종목 분석" : "일부 종목의 근거가 부족해요.").font(.footnote).foregroundStyle(.secondary) }
            ForEach(Array(value.field("impacts").rows.enumerated()), id: \.offset) { _, impact in
                DisclosureGroup(impact.field("assetName").display) {
                    LabeledContent("비중", value: impact.field("weight").display + "%")
                    if !impact.field("direction").display.isEmpty { LabeledContent("영향", value: directionLabel(impact.field("direction").display) + " · " + impactLabel(impact.field("impactLevel").display)) }
                    Text(impact.field("issueSummary").display)
                    Text(impact.field("expectedReaction").display)
                    Text(impact.field("outlook").display)
                    Text(impact.field("reason").display).foregroundStyle(.secondary)
                    if !impact.field("evidenceSentence").display.isEmpty { Text(impact.field("evidenceSentence").display).font(.footnote) }
                    analysisSources(impact.field("sources").rows)
                }
            }
            analysisSources(value.field("sources").rows)
            Text("AI 분석에는 오류가 있을 수 있어요. 원문 근거와 함께 확인해 주세요.").font(.footnote).foregroundStyle(.secondary)
        }
    }
    @ViewBuilder private func analysisSources(_ rows: [ServiceValue]) -> some View {
        ForEach(Array(rows.enumerated()), id: \.offset) { _, source in
            if let url = publicLink(source.field("url").display) {
                VStack(alignment: .leading, spacing: 5) {
                    Link(source.field("title").display.isEmpty ? "근거 원문" : source.field("title").display, destination: url).frame(minHeight: 44)
                    if !source.field("factQuote").display.isEmpty { Text(source.field("factQuote").display).font(.caption).foregroundStyle(.secondary) }
                }
            }
        }
    }
}
func nullableText(_ value: ServiceValue) -> String { value.display.isEmpty ? "자료 없음" : value.display }
func directionLabel(_ value: String) -> String {
    switch value { case "POSITIVE", "INCREASED": return "상승"; case "NEGATIVE", "DECREASED": return "하락"; case "NEUTRAL", "UNCHANGED": return "보합"; default: return "자료 없음" }
}
func impactLabel(_ value: String) -> String { ["HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"][value] ?? "확인 전" }
func calendarStatus(_ value: String) -> String {
    switch value { case "READY": return "보유 자산의 과거 반응"; case "NO_PORTFOLIO": return "보유 자산을 등록하면 관련 영향을 볼 수 있어요."; default: return "과거 반응을 계산할 자료가 충분하지 않아요." }
}
func analysisStatus(_ value: String) -> String {
    switch value { case "READY": return "저장된 분석이 있어요."; case "EMPTY": return "아직 저장된 분석이 없어요."; case "PORTFOLIO_CHANGED": return "보유 자산이 바뀌었어요. 분석을 갱신해 주세요."; case "PROCESSING": return "분석이 진행 중이에요. 잠시 후 다시 확인해 주세요."; case "RECHECK_REQUIRED": return "새 근거를 다시 확인해야 해요."; case "FAILED": return "최근 분석 요청을 완료하지 못했어요."; default: return "분석 상태를 확인해 주세요." }
}

@MainActor struct PortfolioHistoryView: View {
    let client: ServiceClient
    @Environment(AppSession.self) private var session
    @State private var from = String(portfolioToday().prefix(4)) + "-01-01"
    @State private var to = portfolioToday()
    @State private var performance: ServiceValue = .null
    @State private var histories: [ServiceValue] = []
    @State private var loading = false
    @State private var error = ""
    @State private var retry = 0
    @State private var historyGeneration: UInt64 = 0
    @State private var historyAccountKey = ""
    private var accountKey: String { "\(session.isLoggedIn)|\(session.user?.field("id").display ?? "guest")" }
    var body: some View {
        List {
            Section("조회 기간") {
                TextField("시작일 YYYY-MM-DD", text: $from).textInputAutocapitalization(.never)
                TextField("종료일 YYYY-MM-DD", text: $to).textInputAutocapitalization(.never)
                Button("기간 조회") { retry += 1 }.disabled(loading)
            }
            if loading { ProgressView("기록 확인 중") }
            if !error.isEmpty { Text(error) }
            Section("자산 추이") {
                if !chartPoints.isEmpty {
                    Chart(chartPoints) { point in
                        LineMark(x: .value("기준일", point.date), y: .value("평가금액 (원)", point.amount))
                            .foregroundStyle(Color.accentColor)
                            .interpolationMethod(.linear)
                        PointMark(x: .value("기준일", point.date), y: .value("평가금액 (원)", point.amount))
                            .foregroundStyle(Color.accentColor)
                    }
                    .chartYScale(domain: .automatic(includesZero: false))
                    .frame(height: 220)
                    .accessibilityLabel("자산 평가금액 추이")
                    .accessibilityHint("날짜별 정확한 평가금액과 수익률은 아래 목록에서도 확인할 수 있어요.")
                    Text("날짜별 평가금액 · 원화 기준").font(.caption).foregroundStyle(.secondary)
                }
                if performance.field("status").display == "INSUFFICIENT_DATA" { Text("자산 추이를 표시할 과거 자료가 충분하지 않아요.").foregroundStyle(.secondary) }
                ForEach(Array(performance.field("points").rows.enumerated()), id: \.offset) { _, point in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(point.field("baseDate").display).font(.headline)
                        LabeledContent("평가금액", value: point.field("totalEvaluationAmount").display + " 원")
                        LabeledContent("누적 손익", value: point.field("totalProfitLoss").display + " 원")
                        LabeledContent("누적 수익률", value: point.field("totalReturnRate").display + "%")
                    }.padding(.vertical, 4)
                }
            }
            Section("보유 자산 변경 이력") {
                if histories.isEmpty && !loading { Text("이 기간의 변경 이력이 없어요.").foregroundStyle(.secondary) }
                ForEach(Array(histories.enumerated()), id: \.offset) { _, row in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(row.field("name").display).font(.headline)
                        Text("\(row.field("effectiveDate").display) · \(historyType(row.field("changeType").display))").foregroundStyle(.secondary)
                        LabeledContent("수량", value: row.field("transactionQuantity").display.isEmpty ? row.field("quantity").display : row.field("transactionQuantity").display)
                        if !row.field("unitPrice").display.isEmpty { LabeledContent("단가", value: row.field("unitPrice").display) }
                    }.padding(.vertical, 4)
                }
            }
        }
        .navigationTitle("자산 추이와 이력")
        .onChange(of: accountKey) { _, _ in
            if historyAccountKey != accountKey { historyAccountKey = accountKey; clearHistory() }
        }
        .onDisappear { clearHistory() }
        .task(id: "\(accountKey)|\(retry)") { await load() }
    }
    private struct PerformanceChartPoint: Identifiable {
        let id: String
        let date: Date
        let amount: Double
    }
    private var chartPoints: [PerformanceChartPoint] {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.isLenient = false
        return performance.field("points").rows.enumerated().compactMap { index, point in
            let rawDate = point.field("baseDate").display
            guard rawDate.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil,
                  let date = formatter.date(from: rawDate), formatter.string(from: date) == rawDate,
                  let rawAmount = point.field("totalEvaluationAmount").number,
                  let amount = Double(rawAmount), amount.isFinite else { return nil }
            return PerformanceChartPoint(id: "\(rawDate)|\(index)", date: date, amount: amount)
        }.sorted { $0.date < $1.date }
    }
    private func clearHistory() {
        historyGeneration &+= 1
        performance = .null; histories = []; error = ""; loading = false
    }
    private func load() async {
        historyAccountKey = accountKey
        clearHistory()
        guard session.isLoggedIn else { return }
        let startedAccount = accountKey, generation = historyGeneration
        guard from <= to, to <= portfolioToday(), from.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil, to.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil else { error = "올바른 날짜 범위를 입력해 주세요."; return }
        loading = true
        defer { if accountKey == startedAccount && historyGeneration == generation { loading = false } }
        do {
            let query = ["from": from, "to": to]
            let result = try await client.request(path: "/api/users/me/portfolio/performance", query: query)
            try Task.checkCancellation(); guard accountKey == startedAccount, historyGeneration == generation else { return }
            guard result.field("points").array != nil else { throw MarketError.invalidResponse }; performance = result
            let history = try await client.request(path: "/api/portfolio/histories", query: query)
            try Task.checkCancellation(); guard accountKey == startedAccount, historyGeneration == generation else { return }
            guard let rows = history.array else { throw MarketError.invalidResponse }; histories = rows
        } catch { if !Task.isCancelled && accountKey == startedAccount && historyGeneration == generation { self.error = friendlyServiceError(error) } }
    }
    private func historyType(_ value: String) -> String { ["BUY": "매수", "SELL": "매도", "ADJUSTED": "보유 조정", "REMOVED": "보유 삭제", "OPENING_BALANCE": "기초 잔고", "ADDED": "추가", "UPDATED": "수정"][value] ?? value }
}
