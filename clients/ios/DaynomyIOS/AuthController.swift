import AuthenticationServices
import CryptoKit
import Security
import UIKit
import DaynomyCore

@MainActor final class AuthController: NSObject, ASWebAuthenticationPresentationContextProviding {
    private var webSession: ASWebAuthenticationSession?
    func login(baseURL: URL) async throws -> ServiceValue {
        let verifier = try randomToken()
        let state = try randomToken()
        let url = try NativeAuthContract.startURL(baseURL: baseURL, verifier: verifier, state: state)
        let callback = try await authenticate(url)
        return try NativeAuthContract.exchangeBody(callbackURL: callback, expectedState: state, verifier: verifier)
    }
    private func randomToken() throws -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { throw ServiceError(status: 0, message: "로그인 준비에 실패했어요.") }
        return Data(bytes).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
    private func authenticate(_ url: URL) async throws -> URL {
        guard webSession == nil else { throw ServiceError(status: 409, message: "로그인이 진행 중이에요.") }
        return try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(url: url, callbackURLScheme: "org.daynomy.app") { [weak self] callback, error in
                Task { @MainActor in
                    self?.webSession = nil
                    if let callback { continuation.resume(returning: callback) }
                    else { continuation.resume(throwing: error ?? ServiceError(status: 0, message: "로그인이 취소되었어요.")) }
                }
            }
            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = true
            webSession = session
            if !session.start() { webSession = nil; continuation.resume(throwing: ServiceError(status: 0, message: "로그인 화면을 열지 못했어요.")) }
        }
    }
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap(\.windows).first(where: \.isKeyWindow) ?? ASPresentationAnchor()
    }
}
