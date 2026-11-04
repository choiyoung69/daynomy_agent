import Foundation

enum NavigationDecision { case internalPage, externalBrowser, block }

/// Foundation-only policy, shared with the independent command-line tests.
struct NavigationPolicy {
    private struct Origin: Equatable { let scheme: String; let host: String; let port: Int }
    private let trusted: Origin
    init(trustedOrigin: String, debug: Bool) {
        guard let origin = Self.configuredOrigin(trustedOrigin, debug: debug) else {
            preconditionFailure("Configure one HTTPS origin, or a local HTTP origin for debug")
        }
        trusted = origin
    }
    static func isValidConfiguration(_ text: String, debug: Bool) -> Bool { configuredOrigin(text, debug: debug) != nil }
    private static func configuredOrigin(_ text: String, debug: Bool) -> Origin? {
        guard let components = parse(text), components.path.isEmpty || components.path == "/",
              components.query == nil, components.fragment == nil, let candidate = origin(components),
              candidate.scheme == "https" || (debug && candidate.scheme == "http" && localHosts.contains(candidate.host)) else { return nil }
        return candidate
    }
    func decide(_ url: String, userActivated: Bool) -> NavigationDecision {
        guard let components = Self.parse(url), let candidate = Self.origin(components) else { return .block }
        if candidate == trusted { return .internalPage }
        return candidate.scheme == "https" && userActivated ? .externalBrowser : .block
    }
    private static let localHosts: Set<String> = ["localhost", "127.0.0.1", "10.0.2.2", "::1"]
    private static func parse(_ text: String) -> URLComponents? {
        guard !text.isEmpty, !text.unicodeScalars.contains(where: { $0.value <= 32 || $0.value == 127 || $0.value == 92 }),
              let authority = text.components(separatedBy: "://").dropFirst().first?.components(separatedBy: CharacterSet(charactersIn: "/?#")).first,
              !authority.contains("%"),
              let components = URLComponents(string: text), components.user == nil, components.password == nil else { return nil }
        return components
    }
    private static func origin(_ components: URLComponents) -> Origin? {
        guard let scheme = components.scheme?.lowercased(), scheme == "http" || scheme == "https",
              let rawHost = components.host?.lowercased(), !rawHost.isEmpty, !rawHost.hasSuffix("."),
              !rawHost.contains("%"), !rawHost.contains("@") else { return nil }
        let host = rawHost.hasPrefix("[") && rawHost.hasSuffix("]") ? String(rawHost.dropFirst().dropLast()) : rawHost
        let port = components.port ?? (scheme == "https" ? 443 : 80)
        guard (1...65535).contains(port) else { return nil }
        return Origin(scheme: scheme, host: host, port: port)
    }
}
