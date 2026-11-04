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
    @State private var mode = "news"
    @State private var query = ""
    @State private var category = "ALL"
    @State private var source = "ALL"
    @State private var sort = "LATEST"
    @State private var todayOnly = false
    @State private var page = 1
    @State private var retry = 0
    @State private var payload: ServiceValue = .null
    @State private var loading = false
    @State private var error = ""
    private var requestKey: String { "\(mode)|\(query)|\(category)|\(source)|\(sort)|\(todayOnly)|\(page)|\(retry)" }
    private var items: [ServiceValue] {
        if mode == "people" { return payload.field("people").rows }
        return NewsPresentation.items(payload: payload, isNewsSearch: mode == "news" && !todayOnly && !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    }
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("둘러보기", selection: $mode) {
                        Text("이슈").tag("news"); Text("통합 검색").tag("search"); Text("자료").tag("contents"); Text("인물").tag("people")
                    }.accessibilityIdentifier("discoveryMode")
                    if mode == "search" {
                        TextField("뉴스·인물·자료 검색", text: $query).submitLabel(.search).accessibilityIdentifier("contentQuery")
                        Picker("검색 범위", selection: $source) {
                            Text("전체").tag("ALL"); Text("DAYNOMY").tag("DAYNOMY"); Text("YouTube").tag("YOUTUBE"); Text("Threads").tag("THREADS"); Text("X").tag("X")
                        }
                    }
                    if mode == "news" {
                        Toggle("오늘의 이슈", isOn: $todayOnly)
                        if !todayOnly {
                            TextField("뉴스 제목·본문 검색", text: $query).submitLabel(.search)
                            if !query.isEmpty { Picker("정렬", selection: $sort) { Text("최신순").tag("LATEST"); Text("관련도순").tag("RELEVANCE") } }
                        }
                        Picker("분야", selection: $category) { ForEach(newsCategories, id: \.0) { Text($0.1).tag($0.0) } }
                    }
                }
                if loading { Section { ProgressView("불러오는 중") } }
                if !error.isEmpty { Section { Text(error); Button("다시 시도") { retry += 1 }.frame(minHeight: 44) } }
                if !loading && error.isEmpty && items.isEmpty {
                    Section { Text(mode == "search" && query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "검색어를 입력해 주세요." : "표시할 자료가 없어요.").foregroundStyle(.secondary) }
                }
                if mode == "people" {
                    ForEach(Array(items.enumerated()), id: \.offset) { _, person in
                        NavigationLink { PersonDetailView(person: person) } label: {
                            Label(person.field("name").display, systemImage: "person.crop.circle").frame(minHeight: 44)
                        }
                    }
                } else {
                    ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                        if mode == "news" || item.field("kind").display == "NEWS" {
                            NavigationLink { ContentDetailView(client: client, newsId: item.field("id").display) } label: { DiscoveryItemLabel(item: item) }
                        } else if item.field("sourceType").display == "INTERNAL_NEWS", let newsId = relatedNewsID(item.field("url").display) {
                            NavigationLink { ContentDetailView(client: client, newsId: newsId) } label: { DiscoveryItemLabel(item: item) }
                        } else if let url = publicLink(item.field("url").display) {
                            Link(destination: url) { DiscoveryItemLabel(item: item) }.accessibilityHint("원문을 외부 브라우저에서 열기")
                        } else { DiscoveryItemLabel(item: item) }
                    }
                    if !items.isEmpty && mode != "people" {
                        Section {
                            HStack {
                                Button("이전") { page = max(1, page - 1) }.disabled(page == 1 || loading).frame(minHeight: 44)
                                Spacer(); Text("\(page) 페이지").foregroundStyle(.secondary); Spacer()
                                Button("다음") { page += 1 }.disabled(loading || !hasNext).frame(minHeight: 44)
                            }
                        }
                    }
                }
            }
            .navigationTitle("둘러보기")
            .scrollDismissesKeyboard(.interactively)
            .refreshable { retry += 1 }
            .onChange(of: mode) { _, _ in page = 1 }
            .onChange(of: query) { _, _ in page = 1 }
            .onChange(of: category) { _, _ in page = 1 }
            .onChange(of: source) { _, _ in page = 1 }
            .onChange(of: todayOnly) { _, _ in page = 1 }
            .onChange(of: sort) { _, _ in page = 1 }
            .task(id: requestKey) { await load() }
        }
    }
    private var hasNext: Bool { payload.field("hasNext").flag || page < (Int(payload.field("totalPages").display) ?? 0) }
    private func load() async {
        loading = true; error = ""; payload = .null
        defer { if !Task.isCancelled { loading = false } }
        do {
            var parameters = ["page": String(page), "size": "12"]
            let path: String
            switch mode {
            case "people": path = "/api/people"; parameters = [:]
            case "contents": path = "/api/contents"
            case "search":
                let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else { loading = false; return }
                try await Task.sleep(for: .milliseconds(250))
                path = "/api/search/contents"; parameters["q"] = trimmed; parameters["source"] = source
            default:
                if todayOnly { path = "/api/news/today"; parameters = [:] }
                else if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    try await Task.sleep(for: .milliseconds(250)); path = "/api/search/news"; parameters["q"] = query.trimmingCharacters(in: .whitespacesAndNewlines); parameters["sort"] = sort
                } else { path = "/api/news" }
                if !todayOnly && category != "ALL" { parameters["category"] = category }
            }
            let result = try await client.request(path: path, query: parameters)
            try Task.checkCancellation(); payload = result
        } catch { if !Task.isCancelled { self.error = friendlyServiceError(error) } }
    }
}

struct DiscoveryItemLabel: View {
    let item: ServiceValue
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(item.field("title").display).font(.headline).foregroundStyle(.primary)
            let category = item.field("category").display
            let date = [item.field("publishedAt").display, item.field("publishedDate").display, item.field("date").display].first(where: { !$0.isEmpty }) ?? ""
            Text([categoryLabel(category), item.field("sourceType").display, item.field("source").display, date].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(.secondary)
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
