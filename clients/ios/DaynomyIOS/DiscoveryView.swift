import SwiftUI
import DaynomyCore

extension ServiceValue {
    func field(_ key: String) -> ServiceValue { if case .object(let values) = self { return values[key] ?? .null }; return .null }
    var display: String {
        switch self { case .string(let value), .number(let value): return value; case .bool(let value): return value ? "예" : "아니요"; default: return "" }
    }
    var rows: [ServiceValue] { if case .array(let values) = self { return values }; return [] }
    var flag: Bool { if case .bool(let value) = self { return value }; return false }
}
func publicLink(_ text: String) -> URL? {
    guard let url = URL(string: text), ["http", "https"].contains(url.scheme?.lowercased() ?? ""), url.host != nil, url.user == nil, url.password == nil else { return nil }; return url
}
func relatedNewsID(_ value: String) -> String? {
    guard value.hasPrefix("/news/"), let id = Int64(value.dropFirst(6)), id > 0,
          value == "/news/\(id)" else { return nil }
    return String(id)
}
let newsCategories = [("ALL", "전체"), ("STOCK", "주식"), ("ETF", "ETF"), ("ECONOMY", "경제지표"), ("REAL_ESTATE", "부동산"), ("DEPOSIT_SAVINGS", "예금·적금"), ("BOND", "채권"), ("PENSION", "연금"), ("FOREIGN_EXCHANGE", "외화·환율"), ("VIRTUAL_ASSET", "가상자산"), ("GOLD", "금")]
func categoryLabel(_ value: String) -> String { newsCategories.first(where: { $0.0 == value })?.1 ?? value }
func friendlyServiceError(_ error: any Error) -> String {
    if let error = error as? ServiceError {
        if error.status == 401 { return "로그인 후 이용해 주세요." }
        if error.status == 403 { return "이 기능을 이용할 권한이 없어요." }
        if error.status == 404 { return "요청한 자료를 찾을 수 없어요." }
        return error.message.isEmpty ? "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요." : error.message
    }
    return "연결을 확인하고 다시 시도해 주세요."
}

@MainActor struct DiscoveryView: View {
    let client: ServiceClient
    var imageBaseURL: URL? = try? APIConfiguration.load()
    @State private var mode = "news"
    @State private var query = ""
    @State private var submittedQuery = ""
    @State private var searchError = ""
    @State private var category = "ALL"
    @State private var source = "ALL"
    @State private var sort = "LATEST"
    @State private var page = 1
    @State private var retry = 0
    @State private var payload: ServiceValue = .null
    @State private var loading = true
    @State private var error = ""
    @State private var todayPayload: ServiceValue = .null
    @State private var todayLoading = true
    @State private var todayError = ""
    @State private var todayRetry = 0
    @State private var selectedTodayID: String?
    @FocusState private var searchFocused: Bool
    private var requestKey: String { "\(mode)|\(submittedQuery)|\(category)|\(source)|\(sort)|\(page)|\(retry)" }
    private var todayItems: [ServiceValue] { Array(NewsPresentation.items(payload: todayPayload, isNewsSearch: false).prefix(9)) }
    private var todayIndex: Int { todayItems.firstIndex(where: { $0.field("id").display == selectedTodayID }) ?? 0 }
    private var items: [ServiceValue] {
        if mode == "people" { return payload.field("people").rows }
        return NewsPresentation.items(payload: payload, isNewsSearch: mode == "news" && !submittedQuery.isEmpty)
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if mode == "news" {
                        todaySection
                        VStack(alignment: .leading, spacing: 16) {
                            Text("전체 이슈").font(.title2.bold()).accessibilityAddTraits(.isHeader)
                            searchField
                            if !submittedQuery.isEmpty {
                                Text("검색 중: \(submittedQuery)").font(.subheadline).foregroundStyle(.secondary)
                                Picker("정렬", selection: $sort) {
                                    Text("최신순").tag("LATEST"); Text("관련도순").tag("RELEVANCE")
                                }.pickerStyle(.segmented).accessibilityIdentifier("newsSort")
                            }
                            Picker("분야", selection: $category) {
                                ForEach(newsCategories.filter { ["ALL", "STOCK", "ETF", "REAL_ESTATE"].contains($0.0) }, id: \.0) { Text($0.1).tag($0.0) }
                            }.frame(minHeight: 44).accessibilityIdentifier("newsCategory")
                        }
                    } else if mode == "search" {
                        searchField
                        Picker("검색 범위", selection: $source) {
                            Text("전체").tag("ALL"); Text("DAYNOMY").tag("DAYNOMY"); Text("YouTube").tag("YOUTUBE"); Text("Threads").tag("THREADS"); Text("X").tag("X")
                        }.frame(minHeight: 44)
                    }
                    results
                    Divider()
                    Picker("추가 둘러보기", selection: $mode) {
                        Text("이슈").tag("news"); Text("통합 검색").tag("search"); Text("자료").tag("contents"); Text("인물").tag("people")
                    }.frame(minHeight: 44).accessibilityIdentifier("discoveryMode")
                }.padding(.horizontal, 20).padding(.vertical, 16)
            }
            .background(Color(uiColor: .systemBackground))
            .navigationTitle(mode == "news" ? "이슈" : mode == "search" ? "통합 검색" : mode == "people" ? "인물" : "자료")
            .scrollDismissesKeyboard(.interactively)
            .tint(Color(red: 50 / 255, green: 107 / 255, blue: 213 / 255))
            .refreshable { retry += 1; todayRetry += 1 }
            .onChange(of: mode) { _, _ in query = ""; submittedQuery = ""; searchError = ""; page = 1 }
            .onChange(of: category) { _, _ in page = 1 }
            .onChange(of: source) { _, _ in page = 1 }
            .onChange(of: sort) { _, _ in page = 1 }
            .task(id: requestKey) { await load(key: requestKey) }
            .task(id: todayRetry) { await loadToday(generation: todayRetry) }
        }
    }
    private var searchField: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
                TextField(mode == "news" ? "이슈 검색" : "뉴스·인물·자료 검색", text: $query)
                    .submitLabel(.search).focused($searchFocused)
                    .onSubmit { submitSearch() }
                    .accessibilityIdentifier(mode == "news" ? "newsQuery" : "contentQuery")
            }.padding(12).frame(minHeight: 48)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(uiColor: .separator), lineWidth: 0.5))
            if !query.isEmpty || !submittedQuery.isEmpty {
                Button("검색 해제") { query = ""; submittedQuery = ""; searchError = ""; page = 1; retry += 1; searchFocused = false }
                    .frame(minHeight: 44).accessibilityIdentifier("clearNewsSearch")
            }
            if !searchError.isEmpty { Text(searchError).foregroundStyle(.red).font(.subheadline) }
        }
    }
    private func submitSearch() {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { searchError = "검색어를 입력해 주세요."; return }
        guard trimmed.utf16.count <= 100, trimmed.rangeOfCharacter(from: .alphanumerics) != nil,
              trimmed.rangeOfCharacter(from: CharacterSet(charactersIn: "\n\r\u{0085}\u{2028}\u{2029}")) == nil else {
            searchError = "검색어는 문자 또는 숫자를 포함해 100자 이내로 입력해 주세요."; return
        }
        searchError = ""; submittedQuery = trimmed; page = 1; retry += 1; searchFocused = false
    }
    @ViewBuilder private var todaySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("오늘 뉴스").font(.title2.bold()).accessibilityAddTraits(.isHeader)
            Text("최신 발행 소식 · 좌우로 넘겨보세요").font(.subheadline).foregroundStyle(.secondary)
            if todayLoading { ProgressView("오늘 뉴스 불러오는 중").frame(minHeight: 44) }
            else if !todayError.isEmpty {
                Text(todayError)
                Button("오늘 뉴스 다시 조회") { todayRetry += 1 }.frame(minHeight: 44)
            } else if todayItems.isEmpty {
                Text("오늘 발행된 뉴스가 없어요.").foregroundStyle(.secondary)
            } else {
                ScrollView(.horizontal) {
                    HStack(spacing: 0) {
                        ForEach(todayItems, id: \.newsIdentity) { item in
                            NavigationLink {
                                ContentDetailView(client: client, newsId: item.field("id").display)
                            } label: {
                                TodayNewsCard(item: item, imageBaseURL: imageBaseURL)
                                    .containerRelativeFrame(.horizontal)
                            }.buttonStyle(.plain)
                                .accessibilityIdentifier("todayNewsArticle_\(item.field("id").display)")
                                .id(item.field("id").display)
                        }
                    }.scrollTargetLayout()
                }.scrollIndicators(.hidden).scrollTargetBehavior(.paging)
                    .scrollPosition(id: $selectedTodayID)
                    .accessibilityIdentifier("todayNewsCarousel")
                HStack {
                    Button { moveToday(-1) } label: { Label("이전 뉴스", systemImage: "chevron.left").labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44).contentShape(Rectangle()) }
                        .labelStyle(.iconOnly).disabled(todayIndex == 0).frame(minWidth: 44, minHeight: 44).accessibilityIdentifier("todayNewsPrevious")
                    Spacer(minLength: 8)
                    Text("\(todayIndex + 1) / \(todayItems.count)").monospacedDigit().font(.subheadline)
                        .accessibilityIdentifier("todayNewsPosition")
                    Spacer(minLength: 8)
                    Button { moveToday(1) } label: { Label("다음 뉴스", systemImage: "chevron.right").labelStyle(.iconOnly).frame(minWidth: 44, minHeight: 44).contentShape(Rectangle()) }
                        .labelStyle(.iconOnly).disabled(todayIndex == todayItems.count - 1).frame(minWidth: 44, minHeight: 44).accessibilityIdentifier("todayNewsNext")
                }
            }
        }
    }
    private func moveToday(_ delta: Int) {
        let index = todayIndex + delta
        guard todayItems.indices.contains(index) else { return }
        selectedTodayID = todayItems[index].field("id").display
    }
    @ViewBuilder private var results: some View {
        if loading { ProgressView("불러오는 중").frame(minHeight: 44) }
        else if !error.isEmpty {
            Text(error).accessibilityIdentifier("newsSearchError")
            Button("다시 시도") { retry += 1 }.frame(minHeight: 44)
        } else if items.isEmpty {
            Text(mode == "search" && submittedQuery.isEmpty ? "검색어를 입력해 주세요." : mode == "news" && !submittedQuery.isEmpty ? "검색 결과가 없어요." : "표시할 자료가 없어요.").foregroundStyle(.secondary)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    if mode == "people" {
                        NavigationLink { PersonDetailView(person: item) } label: {
                            Label(item.field("name").display, systemImage: "person.crop.circle").frame(minHeight: 44)
                        }
                    } else if mode == "news" || item.field("kind").display == "NEWS" {
                        NavigationLink { ContentDetailView(client: client, newsId: item.field("id").display) } label: { DiscoveryItemLabel(item: item) }
                    } else if item.field("sourceType").display == "INTERNAL_NEWS", let newsId = relatedNewsID(item.field("url").display) {
                        NavigationLink { ContentDetailView(client: client, newsId: newsId) } label: { DiscoveryItemLabel(item: item) }
                    } else if let url = publicLink(item.field("url").display) {
                        Link(destination: url) { DiscoveryItemLabel(item: item) }.accessibilityHint("원문을 외부 브라우저에서 열기")
                    } else { DiscoveryItemLabel(item: item) }
                    Divider()
                }
            }
            if mode != "people" {
                HStack {
                    Button("이전") { page = max(1, page - 1) }.disabled(page == 1).frame(minHeight: 44)
                    Spacer(); Text("\(page) 페이지").foregroundStyle(.secondary); Spacer()
                    Button("다음") { page += 1 }.disabled(!hasNext).frame(minHeight: 44)
                }
            }
        }
    }
    private var hasNext: Bool { payload.field("hasNext").flag || page < (Int(payload.field("totalPages").display) ?? 0) }
    private func load(key: String) async {
        loading = true; error = ""; payload = .null
        defer { if !Task.isCancelled && key == requestKey { loading = false } }
        do {
            var parameters = ["page": String(page), "size": "12"]
            let path: String
            switch mode {
            case "people": path = "/api/people"; parameters = [:]
            case "contents": path = "/api/contents"
            case "search":
                guard !submittedQuery.isEmpty else { return }
                path = "/api/search/contents"; parameters["q"] = submittedQuery; parameters["source"] = source
            default:
                if !submittedQuery.isEmpty {
                    path = "/api/search/news"; parameters["q"] = submittedQuery; parameters["sort"] = sort
                } else { path = "/api/news" }
                if category != "ALL" { parameters["category"] = category }
            }
            let result = try await client.request(path: path, query: parameters)
            try Task.checkCancellation()
            guard key == requestKey else { return }
            payload = result
        } catch { if !Task.isCancelled && key == requestKey { self.error = friendlyServiceError(error) } }
    }
    private func loadToday(generation: Int) async {
        todayLoading = true; todayError = ""
        defer { if !Task.isCancelled && generation == todayRetry { todayLoading = false } }
        do {
            let value = try await client.request(path: "/api/news/today")
            try Task.checkCancellation()
            guard generation == todayRetry else { return }
            todayPayload = value
            if !todayItems.contains(where: { $0.field("id").display == selectedTodayID }) { selectedTodayID = todayItems.first?.field("id").display }
        } catch { if !Task.isCancelled && generation == todayRetry { todayError = "오늘 뉴스: " + friendlyServiceError(error) } }
    }
}

private extension ServiceValue {
    var newsIdentity: String { field("id").display }
}

private struct TodayNewsCard: View {
    let item: ServiceValue
    let imageBaseURL: URL?
    @ScaledMetric(relativeTo: .title2) private var minimumHeight = 280.0
    private var imageURL: URL? {
        let raw = item.field("imageUrl").display.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty, let url = URL(string: raw, relativeTo: imageBaseURL)?.absoluteURL else { return nil }
        return publicLink(url.absoluteString)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Spacer(minLength: 90)
            Text(item.field("title").display).font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
            Text([categoryLabel(item.field("category").display), String(item.field("publishedAt").display.prefix(10))].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).fixedSize(horizontal: false, vertical: true)
        }.foregroundStyle(.white).padding(20).frame(maxWidth: .infinity, minHeight: minimumHeight, alignment: .bottomLeading)
            .background {
                GeometryReader { geometry in
                    ZStack(alignment: .topTrailing) {
                        Color(white: 0.13)
                        if let imageURL {
                            AsyncImage(url: imageURL) { phase in
                                switch phase {
                                case .empty: photoStatus("이미지 불러오는 중")
                                case .success(let image): image.resizable().scaledToFill().frame(width: geometry.size.width, height: geometry.size.height).clipped()
                                case .failure: photoStatus("이미지를 불러오지 못했어요")
                                @unknown default: photoStatus("이미지를 불러오지 못했어요")
                                }
                            }
                        } else { photoStatus(item.field("imageUrl").display.isEmpty ? "이미지 없음" : "이미지를 불러오지 못했어요") }
                        LinearGradient(colors: [.black.opacity(0.08), .black.opacity(0.5), .black.opacity(0.95)], startPoint: .top, endPoint: .bottom).accessibilityHidden(true)
                    }.frame(width: geometry.size.width, height: geometry.size.height)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .accessibilityElement(children: .combine)
    }
    private func photoStatus(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.white).padding(16)
    }
}

struct DiscoveryItemLabel: View {
    let item: ServiceValue
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(item.field("title").display).font(.headline).foregroundStyle(Color.primary)
            let category = item.field("category").display
            let date = [item.field("publishedAt").display, item.field("publishedDate").display, item.field("date").display].first(where: { !$0.isEmpty }) ?? ""
            Text([categoryLabel(category), item.field("sourceType").display, item.field("source").display, date].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(Color.secondary)
        }.padding(.vertical, 6).frame(minHeight: 44).accessibilityElement(children: .combine)
    }
}
struct PersonDetailView: View {
    let person: ServiceValue
    var body: some View {
        List {
            Section("프로필") {
                ForEach([("xProfileUrl", "X 프로필"), ("threadsProfileUrl", "Threads 프로필"), ("youtubeProfileUrl", "YouTube 채널")], id: \.0) { key, label in
                    if let url = publicLink(person.field(key).display) { Link(label, destination: url).frame(minHeight: 44) }
                }
            }
            Section("공개 게시물") {
                if person.field("posts").rows.isEmpty { Text("공개 게시물이 없어요.").foregroundStyle(.secondary) }
                ForEach(Array(person.field("posts").rows.enumerated()), id: \.offset) { _, post in
                    if let url = publicLink(post.field("url").display) { Link(destination: url) { DiscoveryItemLabel(item: post) } }
                }
            }
        }.navigationTitle(person.field("name").display)
    }
}

@MainActor struct AssetContentsView: View {
    let client: ServiceClient
    let assetId: Int64
    @State private var payload: ServiceValue = .null
    @State private var error = ""
    @State private var loading = false
    @State private var retry = 0
    var body: some View {
        List {
            if loading { ProgressView("종목 자료 불러오는 중") }
            if !error.isEmpty { Text(error); Button("다시 시도") { retry += 1 } }
            let contents = payload.field("contents").rows
            if !loading && error.isEmpty && contents.isEmpty { Text("연결된 자료가 없어요.").foregroundStyle(.secondary) }
            ForEach(Array(contents.enumerated()), id: \.offset) { _, item in
                let raw = item.field("url").display
                if item.field("sourceType").display == "INTERNAL_NEWS", let id = relatedNewsID(raw) {
                    NavigationLink { ContentDetailView(client: client, newsId: id) } label: { DiscoveryItemLabel(item: item) }
                } else if let url = publicLink(raw) { Link(destination: url) { DiscoveryItemLabel(item: item) } }
                else { DiscoveryItemLabel(item: item) }
            }
        }.navigationTitle(payload.field("assetName").display.isEmpty ? "종목 자료" : payload.field("assetName").display)
            .task(id: "\(assetId)|\(retry)") {
                loading = true; error = ""; payload = .null
                defer { if !Task.isCancelled { loading = false } }
                do { let value = try await client.request(path: "/api/assets/\(assetId)/contents"); try Task.checkCancellation(); payload = value }
                catch { if !Task.isCancelled { self.error = friendlyServiceError(error) } }
            }
    }
}
