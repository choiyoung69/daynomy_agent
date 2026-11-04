import Foundation
import CryptoKit

struct AuthLaunch: CustomStringConvertible {
    let authorizationURL: String
    var description: String { "AuthLaunch(redacted)" }
}
struct AuthExchange: CustomStringConvertible {
    let exchangeURL: String
    let code: String
    let codeVerifier: String
    let requestId: String
    var description: String { "AuthExchange(redacted)" }
}
struct AuthCookiePlan: CustomStringConvertible {
    let originURL: String
    let reloadURL: String
    let setCookieHeaders: [String]
    var description: String { "AuthCookiePlan(redacted)" }
}

/// Native-only, one-generation state; no persistent secrets or WebKit dependencies.
final class NativeAuthSession {
    private struct Origin: Equatable { let scheme: String; let host: String; let port: Int }
    private struct Pending {
        let state: String; let verifier: String; let began: Int64; let id: String
        var received: Int64?
    }
    private let originURL: String
    private let configured: Origin?
    private let debug: Bool
    private var pending: Pending?
    private var generation: UInt64 = 0
    var isPending: Bool { pending != nil }
    private static let urlsafe = Set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_".utf8)
    private static let unreserved = urlsafe.union(Set(".~".utf8))
    private static let localHosts: Set<String> = ["localhost", "127.0.0.1", "10.0.2.2", "::1"]

    init(trustedOrigin: String, debug: Bool) {
        originURL = trustedOrigin
        self.debug = debug
        if let components = Self.parse(trustedOrigin), components.percentEncodedPath.isEmpty,
           components.percentEncodedQuery == nil, components.fragment == nil, let origin = Self.origin(components),
           origin.scheme == "https" || (debug && origin.scheme == "http" && Self.localHosts.contains(origin.host)) {
            configured = origin
        } else { configured = nil }
    }

    func begin(navigationURL: String, sourceDocumentURL: String, httpMethod: String, isMainFrame: Bool,
               userActivated: Bool, state: String, verifier: String, nowMillis: Int64) -> AuthLaunch? {
        guard let configured = configured, pending == nil, nowMillis >= 0, isMainFrame, userActivated, httpMethod == "GET",
              exact(navigationURL, path: "/api/auth/google"), let source = Self.parse(sourceDocumentURL), Self.origin(source) == configured,
              Self.safe(state, min: 32, max: 128), (43...128).contains(verifier.utf8.count),
              verifier.utf8.allSatisfy({ Self.unreserved.contains($0) }) else { return nil }
        generation &+= 1
        pending = Pending(state: state, verifier: verifier, began: nowMillis, id: String(generation), received: nil)
        let challenge = Data(SHA256.hash(data: Data(verifier.utf8))).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        return AuthLaunch(authorizationURL: originURL + "/api/auth/mobile/start?code_challenge=" + challenge + "&state=" + state + "&code_challenge_method=S256")
    }

    func receive(callbackURL: String, nowMillis: Int64) -> AuthExchange? {
        guard var current = pending else { return nil }
        guard alive(current, nowMillis) else { cancel(); return nil }
        guard current.received == nil, let components = Self.parse(callbackURL), components.scheme == "org.daynomy.app",
              components.host == "auth", components.port == nil, components.percentEncodedPath == "/callback", components.fragment == nil,
              callbackURL.components(separatedBy: "://").dropFirst().first?.components(separatedBy: "/").first == "auth",
              let query = Self.decodeQuery(components.percentEncodedQuery), query.count == 2,
              let state = query["state"], Self.constantEqual(state, current.state) else { return nil }
        if Set(query.keys) == Set(["error", "state"]), query["error"] == "oauth_failed" { cancel(); return nil }
        guard Set(query.keys) == Set(["code", "state"]), let code = query["code"], Self.safe(code, min: 32, max: 128) else { return nil }
        current.received = nowMillis
        pending = current
        return AuthExchange(exchangeURL: originURL + "/api/auth/mobile/exchange", code: code, codeVerifier: current.verifier, requestId: current.id)
    }

    func complete(requestId: String, status: Int, responseURL: String, setCookieHeaders: [String], nowMillis: Int64) -> AuthCookiePlan? {
        guard let current = pending, let received = current.received, requestId == current.id else { return nil }
        pending = nil
        guard alive(current, nowMillis), nowMillis >= received, nowMillis - received < 60_000, status == 204,
              exact(responseURL, path: "/api/auth/mobile/exchange"), cookiesValid(setCookieHeaders) else { return nil }
        return AuthCookiePlan(originURL: originURL, reloadURL: originURL + "/", setCookieHeaders: setCookieHeaders)
    }
    func cancel() { pending = nil }

    private func alive(_ current: Pending, _ time: Int64) -> Bool { time >= current.began && time - current.began < 600_000 }
    private func exact(_ text: String, path: String) -> Bool {
        guard let configured = configured, let components = Self.parse(text) else { return false }
        return Self.origin(components) == configured && components.percentEncodedPath == path && components.percentEncodedQuery == nil && components.fragment == nil
    }
    private func cookiesValid(_ headers: [String]) -> Bool {
        guard headers.count == 2, let configured = configured else { return false }
        var names = Set<String>()
        for header in headers {
            guard !header.isEmpty, header.utf8.count <= 16_384, header.utf8.allSatisfy({ $0 >= 32 && $0 != 127 }) else { return false }
            let parts = header.components(separatedBy: ";").map { $0.trimmingCharacters(in: .whitespaces) }
            let first = parts[0].split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false).map(String.init)
            guard first.count == 2, ["access_token", "refresh_token"].contains(first[0]), names.insert(first[0]).inserted,
                  !first[1].isEmpty, first[1].utf8.allSatisfy({ $0 == 0x21 || (0x23...0x2B).contains($0) || (0x2D...0x3A).contains($0) || (0x3C...0x5B).contains($0) || (0x5D...0x7E).contains($0) }) else { return false }
            // Separate presence from optional value: nil dictionary assignment would remove a flag.
            var attributes: [String: String] = [:]
            var flags = Set<String>()
            var seen = Set<String>()
            for part in parts.dropFirst() {
                let pair = part.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false).map(String.init)
                let name = pair[0].lowercased()
                guard ["path", "max-age", "httponly", "samesite", "secure", "domain"].contains(name), seen.insert(name).inserted else { return false }
                if pair.count == 2 { attributes[name] = pair[1] } else { flags.insert(name) }
            }
            let path = first[0] == "access_token" ? "/" : "/api/auth"
            guard attributes["path"] == path, flags.contains("httponly"), attributes["httponly"] == nil,
                  attributes["samesite"]?.lowercased() == "lax", let age = attributes["max-age"], !age.isEmpty,
                  age.utf8.allSatisfy({ (48...57).contains($0) }), let seconds = Int64(age), seconds > 0,
                  attributes["secure"] == nil, ((debug && configured.scheme == "http") || flags.contains("secure")),
                  !seen.contains("domain") || attributes["domain"]?.lowercased() == configured.host else { return false }
        }
        return names == Set(["access_token", "refresh_token"])
    }
    private static func decodeQuery(_ raw: String?) -> [String: String]? {
        guard let raw = raw else { return nil }
        var result: [String: String] = [:]
        for item in raw.components(separatedBy: "&") {
            let pair = item.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false).map(String.init)
            guard pair.count == 2, let key = pair[0].replacingOccurrences(of: "+", with: " ").removingPercentEncoding,
                  let value = pair[1].replacingOccurrences(of: "+", with: " ").removingPercentEncoding,
                  ["state", "code", "error"].contains(key), result[key] == nil else { return nil }
            result[key] = value
        }
        return result
    }
    private static func safe(_ text: String, min: Int, max: Int) -> Bool { (min...max).contains(text.utf8.count) && text.utf8.allSatisfy { urlsafe.contains($0) } }
    private static func constantEqual(_ a: String, _ b: String) -> Bool {
        let left = Array(a.utf8), right = Array(b.utf8)
        var difference = left.count ^ right.count
        for i in 0..<max(left.count, right.count) { difference |= Int((i < left.count ? left[i] : 0) ^ (i < right.count ? right[i] : 0)) }
        return difference == 0
    }
    private static func parse(_ text: String) -> URLComponents? {
        guard !text.isEmpty, !text.unicodeScalars.contains(where: { $0.value <= 32 || $0.value == 127 || $0.value == 92 }),
              let authority = text.components(separatedBy: "://").dropFirst().first?.components(separatedBy: CharacterSet(charactersIn: "/?#")).first,
              !authority.contains("%"), !authority.contains("@"),
              !text.contains(where: { $0 == "\n" || $0 == "\r" }),
              let components = URLComponents(string: text), components.user == nil, components.password == nil else { return nil }
        // URLComponents repairs malformed percent sequences; do not accept that repair.
        let bytes = Array(text.utf8)
        for i in bytes.indices where bytes[i] == 37 {
            guard i + 2 < bytes.count, isHex(bytes[i + 1]), isHex(bytes[i + 2]) else { return nil }
        }
        return components
    }
    private static func isHex(_ byte: UInt8) -> Bool { (48...57).contains(byte) || (65...70).contains(byte) || (97...102).contains(byte) }
    private static func origin(_ components: URLComponents) -> Origin? {
        guard let scheme = components.scheme?.lowercased(), ["https", "http"].contains(scheme),
              let rawHost = components.host?.lowercased(), !rawHost.isEmpty, !rawHost.hasSuffix(".") else { return nil }
        let host = rawHost.hasPrefix("[") && rawHost.hasSuffix("]") ? String(rawHost.dropFirst().dropLast()) : rawHost
        let port = components.port ?? (scheme == "https" ? 443 : 80)
        guard (1...65535).contains(port) else { return nil }
        return Origin(scheme: scheme, host: host, port: port)
    }
}
