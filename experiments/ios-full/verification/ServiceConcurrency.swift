import Foundation
actor RaceTransport: HTTPTransport {
    let initialWaitCount: Int
    init(initialWaitCount:Int=2) { self.initialWaitCount=initialWaitCount }
    var profileCount = 0
    var refreshCount = 0
    var firstProfiles: [Int:CheckedContinuation<HTTPResponse,any Error>] = [:]
    var pendingRefresh: CheckedContinuation<HTTPResponse,any Error>?
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        switch request.url!.path {
        case "/api/auth/csrf":return HTTPResponse(status:200,data:Data("{\"headerName\":\"X-XSRF-TOKEN\",\"token\":\"fixture\"}".utf8))
        case "/api/auth/refresh":
            refreshCount += 1
            if refreshCount == 1 { return try await withCheckedThrowingContinuation { pendingRefresh = $0 } }
            return HTTPResponse(status:204,data:Data())
        case "/api/auth/logout":return HTTPResponse(status:204,data:Data())
        default:
            let index = profileCount;profileCount += 1
            if index < initialWaitCount { return try await withCheckedThrowingContinuation { firstProfiles[index] = $0 } }
            return HTTPResponse(status:200,data:Data("{\"id\":1}".utf8))
        }
    }
    func counts() -> (Int,Int) { (profileCount,refreshCount) }
    func finishProfile(_ index:Int) { firstProfiles.removeValue(forKey:index)?.resume(returning:HTTPResponse(status:401,data:Data("{}".utf8))) }
    func finishRefresh() { pendingRefresh?.resume(returning:HTTPResponse(status:204,data:Data()));pendingRefresh=nil }
}
@main struct RaceCheck {
    @MainActor static func wait(_ test:()async->Bool) async ->Bool { for _ in 0..<10000 {if await test() {return true};await Task.yield()};return false }
    @MainActor static func main() async throws {
        let transport = RaceTransport();let client = ServiceClient(baseURL:URL(string:"https://example.invalid")!,transport:transport)
        let first = Task { try await client.request(path:"/api/users/me") }
        let second = Task { try await client.request(path:"/api/users/me") }
        guard await wait({await transport.counts().0==2}) else { print("FAIL initial requests");exit(1) }
        await transport.finishProfile(0)
        guard await wait({await transport.counts().1==1}) else { print("FAIL first refresh");exit(1) }
        await transport.finishRefresh()
        guard await wait({await transport.counts().0==3}) else { print("FAIL retried request");exit(1) }
        await transport.finishProfile(1)
        _ = try await first.value;_ = try await second.value
        let total = await transport.counts().1
        print("OBSERVED late401 refresh requests \(total), expected1 after newer authorization generation")
        let logoutTransport = RaceTransport(initialWaitCount:1)
        let logoutClient = ServiceClient(baseURL:URL(string:"https://example.invalid")!,transport:logoutTransport)
        let stale = Task { try await logoutClient.request(path:"/api/users/me") }
        guard await wait({await logoutTransport.counts().0==1}) else { print("FAIL logout initial request");exit(1) }
        await logoutTransport.finishProfile(0)
        guard await wait({await logoutTransport.counts().1==1}) else { print("FAIL logout initial refresh");exit(1) }
        _ = try await logoutClient.request(path:"/api/auth/logout",method:"POST",csrf:true)
        await logoutTransport.finishRefresh()
        var staleSucceeded=false
        do { _ = try await stale.value;staleSucceeded=true } catch {}
        print("OBSERVED prelogout request succeeds after logout \(staleSucceeded), expectedfalse")
        if total != 1 || staleSucceeded { exit(1) }
    }
}
