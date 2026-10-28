import SwiftUI
import Foundation
import DaynomyCore

@main @MainActor
struct DaynomyApp: App {
    @State private var session: AppSession?
    private let client: ServiceClient?
    private let market: StockAPI?

    init() {
        if let url = try? APIConfiguration.load() {
            let configuration = URLSessionConfiguration.ephemeral
            configuration.httpShouldSetCookies = true
            let transport = URLSessionTransport(session: URLSession(configuration: configuration))
            let service = ServiceClient(baseURL: url, transport: transport)
            client = service
            market = StockAPI(baseURL: url, transport: transport)
            _session = State(initialValue: AppSession(client: service))
        } else {
            client = nil
            market = nil
            _session = State(initialValue: nil)
        }
    }

    var body: some Scene {
        WindowGroup {
            if let client, let market, let session {
                AppShell(client: client, marketAPI: market)
                    .environment(session)
                    .task { await session.reloadProfile() }
            } else {
                ContentUnavailableView("서버 주소를 확인해 주세요", systemImage: "network.slash", description: Text("서버 연결 설정을 확인해 주세요."))
            }
        }
    }
}
