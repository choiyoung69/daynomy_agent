import SwiftUI
import DaynomyCore

struct AppShell: View {
    let client: ServiceClient
    let marketAPI: any MarketAPI
    @Environment(AppSession.self) private var session

    var body: some View {
        TabView {
            PortfolioView(client: client, marketAPI: marketAPI)
                .id("\(session.isLoggedIn)|\(session.user?.field("id").display ?? "guest")")
                .tabItem { Label("포트폴리오", systemImage: "chart.pie") }
            DiscoveryView(client: client)
                .tabItem { Label("소식", systemImage: "newspaper") }
            MarketView(api: marketAPI, client: client)
                .tabItem { Label("종목", systemImage: "magnifyingglass") }
            AccountView(client: client)
                .tabItem { Label("내 정보", systemImage: "person.crop.circle") }
        }
    }
}
