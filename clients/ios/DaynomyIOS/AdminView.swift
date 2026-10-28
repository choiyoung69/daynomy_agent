import SwiftUI
import DaynomyCore
import PhotosUI
import UIKit

@MainActor struct AdminView: View {
    let client: ServiceClient
    @Environment(AppSession.self) private var session
    var body: some View {
        Group {
            if session.isAdmin {
                List {
                    Section("콘텐츠 관리") {
                        NavigationLink("뉴스와 이슈") { AdminListView(client: client, kind: .news) }
                        NavigationLink("주요 인물") { AdminListView(client: client, kind: .people) }
                        NavigationLink("게시물 후보 대기함") { AdminListView(client: client, kind: .candidates) }
                        NavigationLink("종목 관련 자료") { AdminAssetView(client: client) }
                    }
                    Section("서비스 관리") {
                        NavigationLink("접수된 피드백") { AdminListView(client: client, kind: .feedback) }
                        NavigationLink("뉴스 생성·시장 데이터 동기화") { AdminOperationsView(client: client) }
                    }
                }
            } else { ContentUnavailableView("관리자 전용", systemImage: "lock", description: Text("관리자 계정으로 로그인해 주세요.")) }
        }.navigationTitle("서비스 관리")
    }
}
private enum AdminKind: String {
    case news, people, candidates, feedback
    var title: String { switch self { case .news: "뉴스 관리"; case .people: "인물 관리"; case .candidates: "게시물 후보"; case .feedback: "피드백 관리" } }
    var path: String { switch self { case .news: "/api/admin/news"; case .people: "/api/admin/people"; case .candidates: "/api/admin/people/post-candidates"; case .feedback: "/api/admin/feedbacks" } }
    var key: String { switch self { case .people: "people"; case .candidates: "candidates"; default: "items" } }
}
@MainActor private struct AdminListView: View {
    let client: ServiceClient
    let kind: AdminKind
    @State private var payload: ServiceValue = .null
    @State private var page = 1
    @State private var status = "ALL"
    @State private var query = ""
    @State private var retry = 0
    @State private var loading = false
    @State private var busy = false
    @State private var error = ""
    @State private var selected: Set<String> = []
    @State private var candidatePerson = ""
    @State private var candidateSource = "ALL"
    var body: some View {
        List {
            if kind == .news {
                Section {
                    TextField("제목·본문 검색", text: $query)
                    Picker("상태", selection: $status) { Text("전체").tag("ALL"); Text("초안").tag("DRAFT"); Text("발행").tag("PUBLISHED"); Text("거절").tag("REJECTED") }
                }
            }
            if kind == .candidates {
                Section("후보 필터") {
                    TextField("인물 ID (선택)", text: $candidatePerson).keyboardType(.numberPad)
                    Picker("플랫폼", selection: $candidateSource) { Text("전체").tag("ALL"); Text("X").tag("X"); Text("Threads").tag("THREADS"); Text("YouTube").tag("YOUTUBE") }
                }
            }
            if kind == .news { Section { NavigationLink("새 뉴스 작성") { AdminNewsEditorView(client: client, news: .null) } } }
            if kind == .people { Section { NavigationLink("새 인물 등록") { AdminPersonForm(client: client, person: .null) } } }
            if kind == .candidates && !selected.isEmpty {
                Section("선택 \(selected.count)건") {
                    Button("선택 승인") { Task { await bulk("bulk-approve") } }.disabled(busy)
                    Button("선택 거절", role: .destructive) { Task { await bulk("bulk-reject") } }.disabled(busy)
                }
            }
            if loading { ProgressView("불러오는 중") }
            if !error.isEmpty { Text(error); Button("다시 시도") { retry += 1 } }
            let items = payload.field(kind.key).rows
            if !loading && error.isEmpty && items.isEmpty { Text("표시할 항목이 없어요.").foregroundStyle(.secondary) }
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                HStack {
                    if kind == .candidates {
                        let id = item.field("id").display
                        Button { if selected.contains(id) { selected.remove(id) } else { selected.insert(id) } } label: {
                            Image(systemName: selected.contains(id) ? "checkmark.circle.fill" : "circle").frame(width: 44, height: 44)
                        }.buttonStyle(.borderless).accessibilityLabel("후보 선택")
                    }
                    NavigationLink {
                        AdminRecordView(client: client, kind: kind, initial: item)
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(kind == .people ? item.field("name").display : kind == .feedback ? item.field("content").display : item.field("title").display).font(.headline).lineLimit(3)
                            Text([item.field("status").display, item.field("personName").display, item.field("createdAt").display].filter { !$0.isEmpty }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                        }.frame(minHeight: 44)
                    }
                }
            }
            if kind != .people && !items.isEmpty {
                HStack {
                    Button("이전") { page = max(1, page - 1) }.disabled(page == 1 || loading)
                    Spacer(); Text("\(page) 페이지"); Spacer()
                    Button("다음") { page += 1 }.disabled(loading || !(payload.field("hasNext").flag || page < (Int(payload.field("totalPages").display) ?? 0)))
                }.frame(minHeight: 44)
            }
        }.navigationTitle(kind.title).scrollDismissesKeyboard(.interactively)
            .onChange(of: status) { _, _ in page = 1 }.onChange(of: query) { _, _ in page = 1 }
            .onChange(of: candidatePerson) { _, _ in page = 1 }.onChange(of: candidateSource) { _, _ in page = 1 }
            .task(id: "\(page)|\(status)|\(query)|\(candidatePerson)|\(candidateSource)|\(retry)") { await load() }
    }
    private func load() async {
        loading = true; error = ""; payload = .null; selected = []
        defer { if !Task.isCancelled { loading = false } }
        do {
            var parameters = kind == .people ? [:] : ["page": String(page), "size": "15"]
            if kind == .news { if status != "ALL" { parameters["status"] = status }; if !query.isEmpty { parameters["q"] = query } }
            if kind == .candidates {
                if !candidatePerson.isEmpty { parameters["personId"] = candidatePerson }
                if candidateSource != "ALL" { parameters["sourceType"] = candidateSource }
            }
            let value = try await client.request(path: kind.path, query: parameters); try Task.checkCancellation(); payload = value
        } catch { if !Task.isCancelled { self.error = friendlyServiceError(error) } }
    }
    private func bulk(_ action: String) async {
        busy = true; error = ""; defer { busy = false }
        do {
            let result = try await client.request(path: kind.path + "/" + action, method: "POST", body: .object(["candidateIds": .array(selected.sorted().map { .number($0) })]), csrf: true)
            let failed = result.field("failed").rows
            await load()
            if !failed.isEmpty { error = failed.map { "후보 \($0.field("candidateId").display): \($0.field("message").display)" }.joined(separator: "\n") }
        } catch { self.error = friendlyServiceError(error) }
    }
}
@MainActor private struct AdminRecordView: View {
    let client: ServiceClient
    let kind: AdminKind
    let initial: ServiceValue
    @State private var record: ServiceValue = .null
    @State private var status = "PENDING"
    @State private var message = ""
    @State private var busy = false
    @State private var confirmDelete = false
    @State private var postTitle = ""
    @State private var postURL = ""
    @State private var platform = "X"
    @State private var fromDate = ""
    @State private var toDate = ""
    @Environment(\.dismiss) private var dismiss
    private var id: String { initial.field("id").display }
    private var item: ServiceValue { record == .null ? initial : record }
    var body: some View {
        Form {
            if kind == .news {
                Section("뉴스") {
                    Text(item.field("title").display).font(.title2.bold())
                    LabeledContent("상태", value: item.field("status").display)
                    LabeledContent("분야", value: categoryLabel(item.field("category").display))
                    Text(item.field("content").display.isEmpty ? item.field("content").rows.map(\.display).joined(separator: "\n\n") : item.field("content").display)
                    NavigationLink("뉴스 수정") { AdminNewsEditorView(client: client, news: item) }.disabled(record == .null)
                    Button("발행") { Task { await mutate("/api/admin/news/\(id)/publish") } }.disabled(busy)
                    Button("거절") { Task { await mutate("/api/admin/news/\(id)/reject") } }.disabled(busy)
                    Button("이미지 생성") { Task { await mutate("/api/admin/news/\(id)/generate-image") } }.disabled(busy)
                }
            } else if kind == .feedback {
                Section("접수 내용") { Text(item.field("content").display); LabeledContent("접수 위치", value: item.field("pagePath").display); LabeledContent("접수일", value: item.field("createdAt").display) }
                Section("처리 상태") {
                    Picker("상태", selection: $status) { Text("미처리").tag("PENDING"); Text("처리 완료").tag("RESOLVED") }
                    Button("상태 저장") { Task { await mutate("/api/admin/feedbacks/\(id)", method: "PATCH", body: .object(["status": .string(status)])) } }.disabled(busy)
                }
            } else if kind == .people {
                Section { NavigationLink("프로필 수정") { AdminPersonForm(client: client, person: item) } }
                Section("공개 게시물") {
                    ForEach(Array(item.field("posts").rows.enumerated()), id: \.offset) { _, post in
                        VStack(alignment: .leading) {
                            if let url = publicLink(post.field("url").display) { Link(post.field("title").display, destination: url) }
                            Button("게시물 삭제", role: .destructive) { Task { await mutate("/api/admin/people/\(id)/posts/\(post.field("id").display)", method: "DELETE") } }.disabled(busy)
                        }
                    }
                }
                Section("게시물 등록") {
                    Picker("플랫폼", selection: $platform) { Text("X").tag("X"); Text("Threads").tag("THREADS"); Text("YouTube").tag("YOUTUBE") }
                    TextField("제목 (선택)", text: $postTitle); TextField("게시물 URL", text: $postURL).textInputAutocapitalization(.never).keyboardType(.URL)
                    Button("게시물 등록") { Task { await mutate("/api/admin/people/\(id)/posts", body: .object(["sourceType": .string(platform), "title": postTitle.isEmpty ? .null : .string(postTitle), "url": .string(postURL)])) } }.disabled(busy || publicLink(postURL) == nil)
                    NavigationLink("게시물 후보 보기") { AdminPersonCandidatesView(client: client, personId: id) }
                    NavigationLink("게시물 검색") { AdminPostSearchView(client: client, personId: id) }
                }
            } else {
                Section("게시물 후보") {
                    Text(item.field("title").display).font(.headline)
                    Text(item.field("personName").display)
                    if let url = publicLink(item.field("url").display) { Link("원문 보기", destination: url) }
                    Button("승인") { Task { await candidate("approve") } }.disabled(busy)
                    Button("거절", role: .destructive) { Task { await candidate("reject") } }.disabled(busy)
                }
            }
            if busy { ProgressView("처리 중") }
            if !message.isEmpty { Text(message) }
            if kind != .candidates { Button("삭제", role: .destructive) { confirmDelete = true }.disabled(busy) }
        }.navigationTitle(kind == .feedback ? "피드백 상세" : "관리 상세").scrollDismissesKeyboard(.interactively)
            .task { await load() }
            .confirmationDialog("이 항목을 삭제하시겠어요?", isPresented: $confirmDelete, titleVisibility: .visible) { Button("삭제", role: .destructive) { Task { await remove() } } }
    }
    private func load() async {
        do {
            if kind == .news || kind == .feedback { let value = try await client.request(path: kind.path + "/" + id); try Task.checkCancellation(); record = value }
            else if kind == .people {
                let value = try await client.request(path: kind.path); try Task.checkCancellation()
                record = value.field("people").rows.first(where: { $0.field("id").display == id }) ?? initial
            }
            status = item.field("status").display
        } catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
    private func mutate(_ path: String, method: String = "POST", body: ServiceValue? = nil) async {
        busy = true; message = ""; defer { busy = false }
        do { _ = try await client.request(path: path, method: method, body: body, csrf: true); await load(); message = "처리했어요." }
        catch { message = friendlyServiceError(error) }
    }
    private func candidate(_ action: String) async {
        let person = item.field("personId").display
        busy = true; defer { busy = false }
        do { _ = try await client.request(path: "/api/admin/people/\(person)/post-candidates/\(id)/\(action)", method: "POST", csrf: true); dismiss() }
        catch { message = friendlyServiceError(error) }
    }
    private func remove() async {
        busy = true; defer { busy = false }
        do { _ = try await client.request(path: kind.path + "/" + id, method: "DELETE", csrf: true); dismiss() }
        catch { message = friendlyServiceError(error) }
    }
}
@MainActor private struct AdminPersonForm: View {
    let client: ServiceClient
    let person: ServiceValue
    @State private var name = ""
    @State private var x = ""
    @State private var threads = ""
    @State private var youtube = ""
    @State private var message = ""
    @State private var busy = false
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        Form {
            Section("프로필") {
                TextField("이름", text: $name)
                TextField("X 프로필 URL", text: $x).keyboardType(.URL).textInputAutocapitalization(.never)
                TextField("Threads 프로필 URL", text: $threads).keyboardType(.URL).textInputAutocapitalization(.never)
                TextField("YouTube 채널 URL", text: $youtube).keyboardType(.URL).textInputAutocapitalization(.never)
                Button("저장") { Task { await save() } }.disabled(busy || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            if busy { ProgressView("저장 중") }; if !message.isEmpty { Text(message) }
        }.navigationTitle(person == .null ? "인물 등록" : "인물 수정").scrollDismissesKeyboard(.interactively)
            .onAppear { name = person.field("name").display; x = person.field("xProfileUrl").display; threads = person.field("threadsProfileUrl").display; youtube = person.field("youtubeProfileUrl").display }
    }
    private func save() async {
        busy = true; defer { busy = false }
        let body: ServiceValue = .object(["name": .string(name), "xProfileUrl": x.isEmpty ? .null : .string(x), "threadsProfileUrl": threads.isEmpty ? .null : .string(threads), "youtubeProfileUrl": youtube.isEmpty ? .null : .string(youtube)])
        do { _ = try await client.request(path: "/api/admin/people" + (person == .null ? "" : "/" + person.field("id").display), method: person == .null ? "POST" : "PUT", body: body, csrf: true); dismiss() }
        catch { message = friendlyServiceError(error) }
    }
}

@MainActor private struct AdminPersonCandidatesView: View {
    let client: ServiceClient
    let personId: String
    @State private var payload: ServiceValue = .null
    @State private var from = ""
    @State private var to = ""
    @State private var message = ""
    @State private var busy = false
    @State private var retry = 0
    var body: some View {
        List {
            Section("기간별 수집") {
                TextField("시작일 YYYY-MM-DD", text: $from).keyboardType(.numbersAndPunctuation)
                TextField("종료일 YYYY-MM-DD", text: $to).keyboardType(.numbersAndPunctuation)
                Button("게시물 수집") { Task { await collect() } }.disabled(busy || from.isEmpty || to.isEmpty)
            }
            if busy { ProgressView("처리 중") }; if !message.isEmpty { Text(message) }
            Section("대기 중인 후보") {
                let candidates = payload.field("candidates").rows
                if candidates.isEmpty { Text("대기 중인 후보가 없어요.").foregroundStyle(.secondary) }
                ForEach(Array(candidates.enumerated()), id: \.offset) { _, candidate in
                    NavigationLink { AdminRecordView(client: client, kind: .candidates, initial: withPerson(candidate)) } label: { DiscoveryItemLabel(item: candidate) }
                }
                Button("새로고침") { retry += 1 }
            }
        }.navigationTitle("게시물 후보").task(id: retry) { await load() }
    }
    private func withPerson(_ value: ServiceValue) -> ServiceValue {
        guard case .object(var object) = value else { return value }; object["personId"] = .number(personId); return .object(object)
    }
    private func load() async {
        do { let value = try await client.request(path: "/api/admin/people/\(personId)/post-candidates"); try Task.checkCancellation(); payload = value }
        catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
    private func collect() async {
        busy = true; message = ""; defer { busy = false }
        do { _ = try await client.request(path: "/api/admin/people/\(personId)/post-candidates/collect", method: "POST", query: ["from": from, "to": to], csrf: true); await load(); message = "수집 결과를 반영했어요." }
        catch { message = friendlyServiceError(error) }
    }
}
@MainActor private struct AdminPostSearchView: View {
    let client: ServiceClient
    let personId: String
    @State private var items: [ServiceValue] = []
    @State private var message = ""
    @State private var busy = false
    var body: some View {
        List {
            if busy { ProgressView("게시물 검색 중") }; if !message.isEmpty { Text(message) }
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                VStack(alignment: .leading, spacing: 8) {
                    DiscoveryItemLabel(item: item)
                    if let url = publicLink(item.field("url").display) { Link("원문 보기", destination: url) }
                    Button("이 게시물 등록") { Task { await add(item) } }.disabled(busy)
                }
            }
            Button("다시 검색") { Task { await search() } }.disabled(busy)
        }.navigationTitle("게시물 검색").task { await search() }
    }
    private func search() async {
        busy = true; message = ""; defer { busy = false }
        do { let value = try await client.request(path: "/api/admin/people/\(personId)/posts/search"); try Task.checkCancellation(); items = value.field("items").rows }
        catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
    private func add(_ item: ServiceValue) async {
        busy = true; message = ""; defer { busy = false }
        do { _ = try await client.request(path: "/api/admin/people/\(personId)/posts", method: "POST", body: .object(["sourceType": item.field("sourceType"), "title": item.field("title"), "url": item.field("url"), "publishedAt": .null]), csrf: true); message = "게시물을 등록했어요." }
        catch { message = friendlyServiceError(error) }
    }
}
@MainActor private struct AdminAssetView: View {
    let client: ServiceClient
    @State private var assetId = ""
    @State private var loadedAsset = ""
    @State private var title = ""
    @State private var url = ""
    @State private var publishedDate = ""
    @State private var source = "YOUTUBE"
    @State private var payload: ServiceValue = .null
    @State private var message = ""
    @State private var busy = false
    @State private var removeID: String?
    @State private var searchItems: [ServiceValue] = []
    @State private var searchKeyword = ""
    var body: some View {
        Form {
            Section("종목") {
                TextField("종목 ID", text: $assetId).keyboardType(.numberPad)
                Button("자료 조회") { Task { await load() } }.disabled(busy || (Int64(assetId) ?? 0) <= 0)
            }
            if !loadedAsset.isEmpty {
                Section(payload.field("assetName").display) {
                    let contents = payload.field("contents").rows
                    if contents.isEmpty { Text("등록된 자료가 없어요.") }
                    ForEach(Array(contents.enumerated()), id: \.offset) { _, content in
                        VStack(alignment: .leading, spacing: 8) {
                            DiscoveryItemLabel(item: content)
                            if let link = publicLink(content.field("url").display) { Link("원문 보기", destination: link) }
                            if content.field("sourceType").display == "INTERNAL_NEWS" { Text("내부 뉴스 연결은 뉴스 편집에서 관리합니다.").font(.caption).foregroundStyle(.secondary) }
                            else { Button("자료 삭제", role: .destructive) { removeID = content.field("id").display }.disabled(busy) }
                        }
                    }
                }
                Section("자료 등록") {
                    Picker("출처", selection: $source) { Text("YouTube").tag("YOUTUBE"); Text("Threads").tag("THREADS"); Text("X").tag("X"); Text("기타").tag("OTHER") }
                    TextField("제목", text: $title)
                    TextField("자료 URL", text: $url).keyboardType(.URL).textInputAutocapitalization(.never)
                    TextField("발행일 YYYY-MM-DD (선택)", text: $publishedDate)
                    Button("자료 등록") { Task { await add() } }.disabled(busy || title.isEmpty || publicLink(url) == nil)
                    TextField("자료 검색어 (2자 이상)", text: $searchKeyword)
                    Button(source == "YOUTUBE" ? "YouTube 검색" : "소셜 게시물 검색") { Task { await search() } }.disabled(busy || searchKeyword.trimmingCharacters(in: .whitespacesAndNewlines).count < 2 || !["YOUTUBE", "X", "THREADS"].contains(source))
                }
                if !searchItems.isEmpty {
                    Section("검색된 자료") {
                        ForEach(Array(searchItems.enumerated()), id: \.offset) { _, item in
                            Button { title = item.field("title").display; url = item.field("url").display; publishedDate = item.field("publishedDate").display } label: { DiscoveryItemLabel(item: item) }
                        }
                    }
                }
            }
            if busy { ProgressView("처리 중") }; if !message.isEmpty { Text(message) }
        }.navigationTitle("종목 관련 자료").scrollDismissesKeyboard(.interactively)
            .confirmationDialog("자료를 삭제하시겠어요?", isPresented: Binding(get: { removeID != nil }, set: { if !$0 { removeID = nil } })) {
                Button("삭제", role: .destructive) { if let id = removeID { Task { await remove(id) } } }
            }
    }
    private func load() async {
        busy = true; message = ""; defer { busy = false }
        do {
            let requestedAsset = assetId
            let value = try await client.request(path: "/api/admin/assets/\(requestedAsset)/contents"); try Task.checkCancellation()
            guard assetId == requestedAsset else { return }; loadedAsset = requestedAsset; payload = value
        }
        catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
    private func add() async {
        busy = true; message = ""; defer { busy = false }
        do {
            _ = try await client.request(path: "/api/admin/assets/\(loadedAsset)/contents", method: "POST", body: .object(["sourceType": .string(source), "title": .string(title), "url": .string(url), "publishedDate": publishedDate.isEmpty ? .null : .string(publishedDate)]), csrf: true)
            title = ""; url = ""; await load(); message = "자료를 등록했어요."
        } catch { message = friendlyServiceError(error) }
    }
    private func remove(_ id: String) async {
        busy = true; defer { busy = false }
        do { _ = try await client.request(path: "/api/admin/assets/\(loadedAsset)/contents/\(id)", method: "DELETE", csrf: true); await load() }
        catch { message = friendlyServiceError(error) }; removeID = nil
    }
    private func search() async {
        busy = true; message = ""; defer { busy = false }
        do {
            let path = "/api/admin/assets/\(loadedAsset)/contents/" + (source == "YOUTUBE" ? "youtube-search" : "social-search")
            let value = try await client.request(path: path, query: ["keyword": searchKeyword]); try Task.checkCancellation(); searchItems = value.field("items").rows
            if searchItems.isEmpty { message = "검색된 자료가 없어요." }
        } catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
}
@MainActor private struct AdminOperationsView: View {
    let client: ServiceClient
    @State private var selected: String?
    @State private var date = ""
    @State private var from = ""
    @State private var to = ""
    @State private var message = ""
    @State private var busy = false
    let operations = [("adminGenerateKorea", "한국 경제 뉴스 초안 생성"), ("adminGenerateUS", "미국 경제 뉴스 초안 생성"), ("syncKR", "국내 종목 동기화"), ("syncKRPrices", "국내 종가 동기화"), ("syncUS", "미국 종목 동기화"), ("syncUSPrices", "미국 종가 동기화"), ("backfill", "국내 과거 종가 채우기")]
    var body: some View {
        Form {
            Section("조회 기간") { TextField("미국 종가 기준일 YYYY-MM-DD (선택)", text: $date); TextField("과거 종가 시작일 YYYY-MM-DD", text: $from); TextField("과거 종가 종료일 YYYY-MM-DD", text: $to) }
            Section("실행") { ForEach(operations, id: \.0) { key, title in Button(title) { selected = key }.disabled(busy || (key == "backfill" && (from.isEmpty || to.isEmpty))) } }
            if busy { ProgressView("요청 처리 중") }; if !message.isEmpty { Section { Text(message) } }
        }.navigationTitle("생성·동기화")
            .confirmationDialog("이 작업을 실행하시겠어요?", isPresented: Binding(get: { selected != nil }, set: { if !$0 { selected = nil } }), titleVisibility: .visible) {
                Button("실행") { if let key = selected { Task { await run(key) } } }
            } message: { Text("서버의 저장된 뉴스 또는 시장 데이터가 갱신됩니다.") }
    }
    private func run(_ name: String) async {
        busy = true; message = ""; defer { busy = false; selected = nil }
        do {
            var query: [String: String] = [:]
            if name == "syncUSPrices" && !date.isEmpty { query["date"] = date }
            if name == "backfill" { query = ["from": from, "to": to] }
            let value = try await client.call(ServiceEndpoints.resolve(name), query: query)
            let count = ["savedCount", "successCount", "stockCount", "syncedCount"].map { value.field($0).display }.first(where: { !$0.isEmpty })
            message = count.map { "작업을 처리했어요. 반영 건수 \($0)" } ?? "서버가 작업 요청을 처리했어요."
        } catch { message = friendlyServiceError(error) }
    }
}

private struct NewsSourceField: Identifiable {
    let id = UUID()
    var name = ""
    var url = ""
}
@MainActor private struct AdminNewsEditorView: View {
    let client: ServiceClient
    let news: ServiceValue
    @State private var title = ""
    @State private var content = ""
    @State private var category = "STOCK"
    @State private var sources = [NewsSourceField()]
    @State private var assets: [ServiceValue] = []
    @State private var assetQuery = ""
    @State private var assetCountry = "KR"
    @State private var assetResults: [ServiceValue] = []
    @State private var photo: PhotosPickerItem?
    @State private var imageData: Data?
    @State private var imageSelection: ServiceValue = .null
    @State private var imageKeyword = ""
    @State private var imageResults: [ServiceValue] = []
    @State private var message = ""
    @State private var imageMessage = ""
    @State private var busy = false
    @State private var searchingImage = false
    @State private var initialized = false
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        Form {
            Section("뉴스") {
                TextField("제목", text: $title).accessibilityIdentifier("adminNewsTitle")
                Picker("분야", selection: $category) { ForEach(newsCategories.filter { $0.0 != "ALL" }, id: \.0) { Text($0.1).tag($0.0) } }
                TextField("본문", text: $content, axis: .vertical).lineLimit(8...24).accessibilityIdentifier("adminNewsContent")
            }
            Section("출처") {
                ForEach($sources) { $source in
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("출처 이름", text: $source.name)
                        TextField("출처 URL", text: $source.url).keyboardType(.URL).textInputAutocapitalization(.never)
                        Button("이 출처 삭제", role: .destructive) { sources.removeAll { $0.id == source.id } }.disabled(sources.count == 1)
                    }
                }
                Button("출처 추가") { sources.append(NewsSourceField()) }
            }
            Section("관련 종목 (최대 20개)") {
                ForEach(Array(assets.enumerated()), id: \.offset) { index, asset in
                    HStack { Text(asset.field("name").display); Spacer(); Button("제외", role: .destructive) { assets.remove(at: index) }.buttonStyle(.borderless) }
                }
                Picker("국가", selection: $assetCountry) { Text("국내").tag("KR"); Text("미국").tag("US") }
                TextField("관련 종목 검색", text: $assetQuery)
                ForEach(Array(assetResults.enumerated()), id: \.offset) { _, asset in
                    Button("\(asset.field("name").display) · \(asset.field("assetCode").display)") {
                        if !assets.contains(where: { $0.field("assetId") == asset.field("assetId") }) { assets.append(asset) }
                        assetQuery = ""; assetResults = []
                    }.disabled(assets.count >= 20)
                }
            }
            Section {
                PhotosPicker("사진에서 이미지 선택", selection: $photo, matching: .images)
                if let imageData, let image = UIImage(data: imageData) { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 220).accessibilityLabel("선택한 뉴스 이미지") }
                if imageSelection != .null { Text("선택한 Wikimedia 이미지: \(imageSelection.field("title").display)") }
                if imageData != nil || imageSelection != .null { Button("새 이미지 선택 취소", role: .destructive) { imageData = nil; imageSelection = .null; photo = nil } }
                if !imageMessage.isEmpty { Text(imageMessage) }
            } header: { Text("뉴스 이미지") } footer: { Text("선택한 사진은 JPEG로 변환하며 5MB 이하여야 합니다. 이미지 변경은 선택 사항입니다.") }
            Section("Wikimedia 이미지 검색") {
                TextField("이미지 검색어 (2자 이상)", text: $imageKeyword)
                Button("이미지 검색") { Task { await searchImages() } }.disabled(searchingImage || imageKeyword.trimmingCharacters(in: .whitespacesAndNewlines).count < 2)
                if searchingImage { ProgressView("이미지 검색 중") }
                ForEach(Array(imageResults.enumerated()), id: \.offset) { _, image in
                    VStack(alignment: .leading, spacing: 8) {
                        if let url = publicLink(image.field("thumbnailUrl").display) { AsyncImage(url: url) { picture in picture.resizable().scaledToFit().frame(maxHeight: 160) } placeholder: { ProgressView() } }
                        Text(image.field("title").display).font(.headline)
                        Text("\(image.field("author").display) · \(image.field("license").display)").font(.caption)
                        if let url = publicLink(image.field("sourceUrl").display) { Link("이미지 원문", destination: url) }
                        if let url = publicLink(image.field("licenseUrl").display) { Link("라이선스 확인", destination: url) }
                        Button("이 이미지 선택") { imageSelection = .object(["title": image.field("title")]); imageData = nil; photo = nil; imageResults = [] }
                    }
                }
            }
            Section {
                Button(news == .null ? "초안 등록" : "변경 저장") { Task { await save() } }
                    .disabled(busy || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || sources.contains(where: { $0.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || publicLink($0.url) == nil }))
                if busy { ProgressView("뉴스 저장 중") }; if !message.isEmpty { Text(message) }
            }
        }.navigationTitle(news == .null ? "뉴스 작성" : "뉴스 수정").scrollDismissesKeyboard(.interactively)
            .onAppear { initialize() }
            .task(id: assetQuery + "|" + assetCountry) { await searchAssets() }
            .task(id: photo) { await loadPhoto() }
    }
    private func initialize() {
        guard !initialized else { return }; initialized = true
        title = news.field("title").display
        content = news.field("content").display.isEmpty ? news.field("content").rows.map(\.display).joined(separator: "\n\n") : news.field("content").display
        if !news.field("category").display.isEmpty { category = news.field("category").display }
        let existing = news.field("sources").rows.map { NewsSourceField(name: $0.field("name").display, url: $0.field("url").display) }
        if !existing.isEmpty { sources = existing }; assets = news.field("relatedAssets").rows
    }
    private func loadPhoto() async {
        guard let photo else { return }; imageMessage = ""
        do {
            guard let raw = try await photo.loadTransferable(type: Data.self), let picture = UIImage(data: raw), let jpeg = picture.jpegData(compressionQuality: 0.9) else { throw ServiceError(status: 0, message: "이미지를 읽지 못했어요.") }
            try Task.checkCancellation()
            guard jpeg.count <= 5 * 1024 * 1024 else { imageMessage = "이미지는 5MB 이하여야 해요."; return }
            imageData = jpeg; imageSelection = .null
        } catch { if !Task.isCancelled { imageMessage = friendlyServiceError(error) } }
    }
    private func searchAssets() async {
        assetResults = []; let query = assetQuery.trimmingCharacters(in: .whitespacesAndNewlines); guard !query.isEmpty else { return }
        do {
            try await Task.sleep(for: .milliseconds(250)); let value = try await client.request(path: "/api/stocks", query: ["q": query, "country": assetCountry]); try Task.checkCancellation(); assetResults = value.field("stocks").rows
        } catch { if !Task.isCancelled { message = friendlyServiceError(error) } }
    }
    private func searchImages() async {
        searchingImage = true; imageMessage = ""; defer { searchingImage = false }
        do { let value = try await client.request(path: "/api/admin/news/image-search", query: ["keyword": imageKeyword.trimmingCharacters(in: .whitespacesAndNewlines)]); try Task.checkCancellation(); imageResults = value.field("items").rows; if imageResults.isEmpty { imageMessage = "검색된 이미지가 없어요." } }
        catch { if !Task.isCancelled { imageMessage = friendlyServiceError(error) } }
    }
    private func save() async {
        busy = true; message = ""; defer { busy = false }
        var fields: [String: ServiceValue] = ["title": .string(title), "content": .string(content), "category": .string(category), "sources": .array(sources.map { .object(["name": .string($0.name), "url": .string($0.url)]) }), "assetIds": .array(assets.map { $0.field("assetId") })]
        if imageSelection != .null { fields["imageSelection"] = imageSelection }
        let image = imageData.map { MultipartImage(data: $0, filename: "news.jpg", mimeType: "image/jpeg") }
        do { _ = try await client.requestMultipart(path: "/api/admin/news" + (news == .null ? "" : "/" + news.field("id").display), method: news == .null ? "POST" : "PUT", body: .object(fields), image: image); dismiss() }
        catch { message = friendlyServiceError(error) }
    }
}
