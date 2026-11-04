import Foundation

/// Separate document trust from HTTPS assets; browser CSP and SOP remain active.
struct FullResourcePolicy {
    private let navigation: NavigationPolicy
    init(trustedOrigin: String, debug: Bool) { navigation = NavigationPolicy(trustedOrigin: trustedOrigin, debug: debug) }
    func allows(_ url: String, isMainFrame: Bool) -> Bool {
        switch navigation.decide(url, userActivated: !isMainFrame) {
        case .internalPage: return true
        case .externalBrowser: return !isMainFrame
        case .block: return false
        }
    }
    static func acceptsImage(scheme: String?, mime: String?) -> Bool {
        guard scheme == "content", let mime = mime else { return false }
        return mime.range(of: "^image/[a-zA-Z0-9.+-]+$", options: .regularExpression) != nil
    }
}
