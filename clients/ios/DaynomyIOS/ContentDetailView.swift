import SwiftUI
import DaynomyCore

@MainActor struct ContentDetailView: View {
    let client: ServiceClient
    let newsId: String
    @State private var news: ServiceValue = .null
    @State private var keywords: ServiceValue = .null
    @State private var analysis: ServiceValue = .null
    @State private var error = ""
    @State private var keywordError = ""
    @State private var analysisError = ""
    @State private var keywordsLoading = false
    @State private var analysisLoading = false
    @State private var loading = false
    @State private var retry = 0
    var body: some View {
        List {
            if loading { ProgressView("이슈 불러오는 중") }
            if !error.isEmpty { Text(error); Button("다시 시도") { retry += 1 }.frame(minHeight: 44) }
            if news != .null {
                Section {
                    Text(news.field("title").display).font(.title2.bold()).accessibilityAddTraits(.isHeader)
                    Text("\(categoryLabel(news.field("category").display)) · \(news.field("publishedAt").display)").font(.subheadline).foregroundStyle(.secondary)
                    if let url = publicLink(news.field("imageUrl").display) {
                        AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { ProgressView() }
                            .accessibilityHidden(true)
                    }
                    let paragraphs = news.field("content").rows
                    if paragraphs.isEmpty { Text(news.field("content").display).textSelection(.enabled) }
                    else { ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, value in Text(value.display).textSelection(.enabled) } }
                }
                Section("출처") {
                    ForEach(Array(news.field("sources").rows.enumerated()), id: \.offset) { _, source in
                        if let url = publicLink(source.field("url").display) { Link(source.field("name").display, destination: url).frame(minHeight: 44) }
                    }
                    let imageSource = news.field("imageSource")
                    if imageSource.field("type").display == "AI_GENERATED" { Text("AI 생성 이미지").font(.caption).foregroundStyle(.secondary) }
                    if let url = publicLink(imageSource.field("url").display) { Link("이미지: \(imageSource.field("name").display) · \(imageSource.field("author").display)", destination: url) }
                    if let url = publicLink(imageSource.field("licenseUrl").display) { Link(imageSource.field("license").display, destination: url) }
                }
                Section("핵심 키워드") {
                    if keywordsLoading { ProgressView("키워드 불러오는 중") }
                    else if !keywordError.isEmpty { Text(keywordError); Button("키워드 다시 조회") { retry += 1 } }
                    else if keywords.field("keywords").rows.isEmpty { Text("등록된 키워드가 없어요.").foregroundStyle(.secondary) }
                    ForEach(Array(keywords.field("keywords").rows.enumerated()), id: \.offset) { _, item in
                        DisclosureGroup(item.field("keyword").display) {
                            Text(item.field("definition").display)
                            if !item.field("context").display.isEmpty { Text(item.field("context").display) }
                            if !item.field("watchPoint").display.isEmpty { LabeledContent("살펴볼 점", value: item.field("watchPoint").display) }
                        }
                    }
                }
                Section("시장 분석") {
                    if analysisLoading { ProgressView("시장 분석 불러오는 중") }
                    else if !analysisError.isEmpty { Text(analysisError); Button("분석 다시 조회") { retry += 1 } }
                    else if analysis == .null || (analysis.field("risk").display.isEmpty && analysis.field("watchPoint").display.isEmpty) { Text("등록된 시장 분석이 없어요.").foregroundStyle(.secondary) }
                    else {
                        if !analysis.field("risk").display.isEmpty { Text("위험 요인").font(.headline); Text(analysis.field("risk").display) }
                        if !analysis.field("watchPoint").display.isEmpty { Text("살펴볼 점").font(.headline); Text(analysis.field("watchPoint").display) }
                    }
                }
            }
        }.navigationTitle("이슈 상세").navigationBarTitleDisplayMode(.inline)
            .task(id: "\(newsId)|\(retry)") { await load() }
    }
    private func load() async {
        loading = true; error = ""; keywordError = ""; analysisError = ""; news = .null; keywords = .null; analysis = .null
        defer { if !Task.isCancelled { loading = false } }
        do {
            let detail = try await client.request(path: "/api/news/\(newsId)")
            try Task.checkCancellation(); news = detail
        } catch { if !Task.isCancelled { self.error = friendlyServiceError(error) }; return }
        keywordsLoading = true; analysisLoading = true
        async let words: Void = loadKeywords()
        async let market: Void = loadAnalysis()
        _ = await (words, market)
    }
    private func loadKeywords() async {
        defer { if !Task.isCancelled { keywordsLoading = false } }
        do { let value = try await client.request(path: "/api/news/\(newsId)/keywords"); try Task.checkCancellation(); keywords = value }
        catch { if !Task.isCancelled { keywordError = friendlyServiceError(error) } }
    }
    private func loadAnalysis() async {
        defer { if !Task.isCancelled { analysisLoading = false } }
        do { let value = try await client.request(path: "/api/news/\(newsId)/market-analysis"); try Task.checkCancellation(); analysis = value }
        catch { if !Task.isCancelled, (error as? ServiceError)?.status != 404 { analysisError = friendlyServiceError(error) } }
    }
}
