import SwiftUI
import DaynomyCore

struct AppShell: View {
    let client: ServiceClient
    let marketAPI: any MarketAPI
    @Environment(AppSession.self) private var session
    @Environment(\.horizontalSizeClass) private var widthClass
    var body: some View {
        TabView {
            PortfolioView(client: client, marketAPI: marketAPI)
                .id("\(session.isLoggedIn)|\(session.user?.field("id").display ?? "guest")")
                .environment(\.horizontalSizeClass, widthClass)
                .tabItem { Label("포트폴리오", systemImage: "house") }
            DiscoveryView(client: client)
                .environment(\.horizontalSizeClass, widthClass)
                .tabItem { Label("이슈", systemImage: "list.bullet.rectangle") }
            AccountView(client: client)
                .environment(\.horizontalSizeClass, widthClass)
                .tabItem { Label("내 계정", systemImage: "person.crop.circle") }
        }
        .environment(\.horizontalSizeClass, .compact)
        .tint(Color(red: 0.196, green: 0.42, blue: 0.835))
        .toolbarBackground(.visible, for: .tabBar)
        .toolbarBackground(Color(uiColor: .systemBackground), for: .tabBar)
    }
}
