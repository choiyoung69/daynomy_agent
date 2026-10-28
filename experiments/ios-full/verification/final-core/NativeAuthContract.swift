import Foundation
import CryptoKit

public enum NativeAuthContract {
    private static func safe(_ value: String, length: ClosedRange<Int>) -> Bool {
        length.contains(value.utf8.count) && value.utf8.allSatisfy { (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 45 || $0 == 95 || $0 == 46 || $0 == 126 }
    }
    public static func startURL(baseURL: URL, verifier: String, state: String) throws -> URL {
        guard safe(verifier, length: 43...128), safe(state, length: 32...128), !state.contains("."), !state.contains("~"),
              var parts = URLComponents(url: baseURL, resolvingAgainstBaseURL: false), ["https", "http"].contains(parts.scheme), parts.host != nil, parts.user == nil, parts.password == nil else { throw ServiceError(status: 0, code: "INVALID_AUTH") }
        let challenge = Data(SHA256.hash(data: Data(verifier.utf8))).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        parts.path = "/api/auth/mobile/start"; parts.fragment = nil
        parts.queryItems = [URLQueryItem(name: "code_challenge", value: challenge), URLQueryItem(name: "state", value: state)]
        guard let url = parts.url else { throw ServiceError(status: 0, code: "INVALID_AUTH") }; return url
    }
    public static func exchangeBody(callbackURL: URL, expectedState: String, verifier: String) throws -> ServiceValue {
        guard callbackURL.scheme == "org.daynomy.app", callbackURL.host == "auth", callbackURL.path == "/callback", callbackURL.user == nil, callbackURL.password == nil, callbackURL.port == nil, callbackURL.fragment == nil,
              safe(verifier, length: 43...128), let parts = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false), let query = parts.queryItems,
              query.filter({ $0.name == "state" }).count == 1, query.first(where: { $0.name == "state" })?.value == expectedState,
              !query.contains(where: { $0.name == "error" }), query.filter({ $0.name == "code" }).count == 1,
              let code = query.first(where: { $0.name == "code" })?.value, !code.isEmpty else { throw ServiceError(status: 0, code: "INVALID_AUTH", message: "로그인 응답을 확인하지 못했어요. 다시 로그인해 주세요.") }
        return .object(["code": .string(code), "codeVerifier": .string(verifier)])
    }
}
