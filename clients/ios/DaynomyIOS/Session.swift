import Foundation
import Observation
import AuthenticationServices
import DaynomyCore

@Observable @MainActor final class AppSession {
    let client: ServiceClient
    private let auth = AuthController()
    private var generation: UInt64 = 0
    var user: ServiceValue?
    var busy = false
    var error = ""
    var isLoggedIn: Bool { user != nil }
    var isAdmin: Bool { user?.field("role").display == "ADMIN" }
    init(client: ServiceClient) { self.client = client }
    func reloadProfile() async {
        generation &+= 1; let current = generation
        do {
            let value = try await client.request(path: "/api/users/me")
            guard generation == current, !Task.isCancelled else { return }
            user = value; error = ""
        } catch {
            guard generation == current, !Task.isCancelled else { return }
            user = nil
            if (error as? ServiceError)?.status != 401 { self.error = friendlyServiceError(error) }
        }
    }
    func login() async {
        guard !busy else { return }; busy = true; error = ""; generation &+= 1
        defer { busy = false }
        do {
            let body = try await auth.login(baseURL: APIConfiguration.load())
            _ = try await client.request(path: "/api/auth/mobile/exchange", method: "POST", body: body, retryUnauthorized: false)
            await reloadProfile()
        } catch {
            if (error as? ASWebAuthenticationSessionError)?.code != .canceledLogin { self.error = friendlyServiceError(error) }
        }
    }
    func logout() async {
        guard !busy else { return }; busy = true; error = ""; generation &+= 1
        defer { busy = false }
        do { _ = try await client.request(path: "/api/auth/logout", method: "POST", csrf: true); user = nil }
        catch { self.error = friendlyServiceError(error) }
    }
    func clearAfterWithdrawal() { generation &+= 1; user = nil }
}
