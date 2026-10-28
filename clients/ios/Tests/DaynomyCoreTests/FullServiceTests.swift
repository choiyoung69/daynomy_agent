import Foundation
import Testing
@testable import DaynomyCore

actor ServiceScriptTransport: HTTPTransport {
    var responses: [HTTPResponse]
    var requests: [URLRequest] = []
    init(_ values: [(Int,String)]) { responses = values.map { HTTPResponse(status:$0.0,data:Data($0.1.utf8)) } }
    func send(_ request: URLRequest) async throws -> HTTPResponse {
        requests.append(request)
        guard !responses.isEmpty else { throw MarketError.network }
        return responses.removeFirst()
    }
    func captured() -> [URLRequest] { requests }
}
func service(_ transport: any HTTPTransport) -> ServiceClient { ServiceClient(baseURL:URL(string:"https://example.invalid")!,transport:transport) }
struct FullServiceTests {
    @Test func genericJSONPreservesNumbersAndNull() async throws {
        let transport = ServiceScriptTransport([(200,"{\"price\":123456789012345678901234567890123456789.001,\"missing\":null,\"list\":[true,\"한글\"]}")])
        let value = try await service(transport).request(path:"/api/news")
        #expect(value["price"]?.number == "123456789012345678901234567890123456789.001")
        #expect(value["missing"] == .null)
        #expect(value["list"]?.array == [.bool(true),.string("한글")])
    }
    @Test func formQueryAnd204Handling() async throws {
        let transport = ServiceScriptTransport([(204,"")]); let client = service(transport)
        let value = try await client.request(path:"/api/search/contents",query:["q":"삼성 A+B &C?","page":"2"])
        #expect(value == .null)
        let captured = await transport.captured(); let request = try #require(captured.first)
        let url = try #require(request.url);let parts = try #require(URLComponents(url:url,resolvingAgainstBaseURL:false))
        let raw = try #require(parts.percentEncodedQuery)
        let q = raw.split(separator:"&").first(where:{$0.hasPrefix("q=")}).map { String($0.dropFirst(2)) }
        #expect(q?.replacingOccurrences(of:"+",with:" ").removingPercentEncoding == "삼성 A+B &C?")
    }
    @Test func csrfBodyAndNoPrecisionLossOnWrite() async throws {
        let transport = ServiceScriptTransport([(200,"{\"headerName\":\"X-CSRF-TOKEN\",\"token\":\"fixture-only\"}"),(204,"")])
        _ = try await service(transport).request(path:"/api/feedback",method:"POST",body:.object(["content":.string("내용"),"amount":.number("12345678901234567890.1234")]),csrf:true)
        let requests = await transport.captured()
        #expect(requests.count == 2)
        if requests.count == 2 {
            #expect(requests[0].url?.path == "/api/auth/csrf")
            #expect(requests[1].value(forHTTPHeaderField:"X-CSRF-TOKEN") == "fixture-only")
            #expect(requests[1].httpMethod == "POST")
            let body = String(decoding: requests[1].httpBody ?? Data(),as:UTF8.self)
            #expect(body.contains("12345678901234567890.1234"))
            #expect(!body.contains("\"12345678901234567890.1234\""))
        }
    }
    @Test func unauthorizedRefreshThenRetryOnce() async throws {
        let transport = ServiceScriptTransport([(401,"{}"),(200,"{\"headerName\":\"X-CSRF\",\"token\":\"fixture\"}"),(204,""),(200,"{\"id\":1}")])
        let value = try await service(transport).request(path:"/api/users/me")
        #expect(value["id"]?.number == "1")
        let requests = await transport.captured()
        #expect(requests.map { $0.url?.path ?? "" } == ["/api/users/me","/api/auth/csrf","/api/auth/refresh","/api/users/me"])
        if requests.count == 4 { #expect(requests[2].httpMethod == "POST") }
    }
    @Test func httpErrorsKeepCodeAndMessage() async {
        do { _ = try await service(ServiceScriptTransport([(409,"{\"code\":\"ANALYSIS_IN_PROGRESS\",\"message\":\"진행 중\"}")])).request(path:"/api/users/me/portfolio/analysis",retryUnauthorized:false); Issue.record("expected409") }
        catch { #expect((error as? ServiceError) == ServiceError(status:409,code:"ANALYSIS_IN_PROGRESS",message:"진행 중")) }
    }
    @Test func malformedCSRFNeverWrites() async {
        let transport = ServiceScriptTransport([(200,"{\"headerName\":\"\",\"token\":null}")])
        do { _ = try await service(transport).request(path:"/api/feedback",method:"POST",csrf:true);Issue.record("invalid csrf accepted") }
        catch { #expect(await transport.captured().count == 1) }
    }
    @Test func mobileExchangeSkipsCSRFAndPreserves204() async throws {
        let transport = ServiceScriptTransport([(204,"")])
        let value = try await service(transport).request(path:"/api/auth/mobile/exchange",method:"POST",body:.object(["code":.string("fixture"),"codeVerifier":.string(String(repeating:"a",count:43))]),retryUnauthorized:false)
        #expect(value == .null)
        #expect(await transport.captured().count == 1)
    }
    @Test func publicEndpointCatalogMatchesOriginal() throws {
        for (name,path) in [("news","/api/news"),("today","/api/news/today"),("newsDetail","/api/news/7"),("keywords","/api/news/7/keywords"),("marketAnalysis","/api/news/7/market-analysis"),("contentSearch","/api/search/contents"),("newsSearch","/api/search/news"),("contents","/api/contents"),("assetContents","/api/assets/7/contents"),("people","/api/people"),("fx","/api/exchange-rates/usd-krw")] {
            let route = try ServiceEndpoints.resolve(name,id:7)
            #expect(route == ServiceEndpoint(path:path))
        }
    }
    @Test func memberAndWriteEndpointCatalog() throws {
        for (name,path,method,csrf) in [("profile","/api/users/me","GET",false),("updateProfile","/api/users/me","PATCH",true),("withdraw","/api/users/me","DELETE",true),("logout","/api/auth/logout","POST",true),("feedback","/api/feedback","POST",true),("portfolio","/api/users/me/portfolio","GET",false),("calculate","/api/portfolio/calculate","POST",true),("createTrade","/api/portfolio/transactions","POST",true),("updateTrade","/api/portfolio/transactions/7","PATCH",true),("deleteTrade","/api/portfolio/transactions/7","DELETE",true),("updateHolding","/api/users/me/portfolio/holdings/7","PATCH",true),("deleteHolding","/api/users/me/portfolio/holdings/7","DELETE",true),("histories","/api/portfolio/histories","GET",false),("performance","/api/users/me/portfolio/performance","GET",false),("calendar","/api/users/me/investment-calendar","GET",false),("guestCalendar","/api/investment-calendar","POST",true),("guestAnalysis","/api/portfolio/analysis","POST",false),("analysis","/api/users/me/portfolio/analysis","GET",false),("updateAnalysis","/api/users/me/portfolio/analysis","POST",true),("refreshAnalysis","/api/users/me/portfolio/analysis/refresh","POST",true),("analysisHistory","/api/users/me/portfolio/analysis/history","GET",false),("mobileExchange","/api/auth/mobile/exchange","POST",false)] {
            #expect(try ServiceEndpoints.resolve(name,id:7) == ServiceEndpoint(path:path,method:method,csrf:csrf))
        }
    }
}

struct AdminServiceTests {
    @Test func adminEndpointCatalog() throws {
        let rows: [(String,String,String)] = [
            ("adminNews","/api/admin/news","GET"),("adminNewsDetail","/api/admin/news/7","GET"),("adminCreateNews","/api/admin/news","POST"),("adminUpdateNews","/api/admin/news/7","PUT"),("adminDeleteNews","/api/admin/news/7","DELETE"),("adminPublishNews","/api/admin/news/7/publish","POST"),("adminRejectNews","/api/admin/news/7/reject","POST"),("adminGenerateKorea","/api/admin/news/generate/economy/korea","POST"),("adminGenerateUS","/api/admin/news/generate/economy/us","POST"),("adminImageSearch","/api/admin/news/image-search","GET"),("adminGenerateImage","/api/admin/news/7/generate-image","POST"),
            ("adminFeedbacks","/api/admin/feedbacks","GET"),("adminFeedback","/api/admin/feedbacks/7","GET"),("adminUpdateFeedback","/api/admin/feedbacks/7","PATCH"),("adminDeleteFeedback","/api/admin/feedbacks/7","DELETE"),
            ("adminAssetContents","/api/admin/assets/7/contents","GET"),("adminCreateContent","/api/admin/assets/7/contents","POST"),("adminDeleteContent","/api/admin/assets/7/contents/9","DELETE"),("adminYoutubeSearch","/api/admin/assets/7/contents/youtube-search","GET"),("adminSocialSearch","/api/admin/assets/7/contents/social-search","GET"),
            ("adminPeople","/api/admin/people","GET"),("adminCreatePerson","/api/admin/people","POST"),("adminUpdatePerson","/api/admin/people/7","PUT"),("adminDeletePerson","/api/admin/people/7","DELETE"),("adminSearchPosts","/api/admin/people/7/posts/search","GET"),("adminCreatePost","/api/admin/people/7/posts","POST"),("adminDeletePost","/api/admin/people/7/posts/9","DELETE"),("adminCandidates","/api/admin/people/7/post-candidates","GET"),("adminCollectPosts","/api/admin/people/7/post-candidates/collect","POST"),("adminApproveCandidate","/api/admin/people/7/post-candidates/9/approve","POST"),("adminRejectCandidate","/api/admin/people/7/post-candidates/9/reject","POST"),("adminBulkApprove","/api/admin/people/7/post-candidates/bulk-approve","POST"),("adminBulkReject","/api/admin/people/7/post-candidates/bulk-reject","POST"),("adminAllCandidates","/api/admin/people/post-candidates","GET"),("adminAllBulkApprove","/api/admin/people/post-candidates/bulk-approve","POST"),("adminAllBulkReject","/api/admin/people/post-candidates/bulk-reject","POST"),
            ("syncKR","/api/admin/stocks/sync","POST"),("syncKRPrices","/api/admin/stocks/prices/sync","POST"),("backfill","/api/admin/stocks/prices/backfill","POST"),("syncUS","/api/admin/stocks/us/sync","POST"),("syncUSPrices","/api/admin/stocks/us/prices/sync","POST")]
        for (name,path,method) in rows { #expect(try ServiceEndpoints.resolve(name,id:7,secondaryId:9) == ServiceEndpoint(path:path,method:method,csrf:method != "GET")) }
    }
    @Test func malformedOutgoingNumberNeverSent() async {
        for raw in ["NaN","01","+1","1.","1e","null,\"injected\":1"] {
            let transport = ServiceScriptTransport([(200,"{}")])
            do { _ = try await service(transport).request(path:"/api/portfolio/analysis",method:"POST",body:.object(["x":.number(raw)]));Issue.record("malformed number accepted") }
            catch { #expect(await transport.captured().isEmpty) }
        }
    }
}
struct NativeAuthServiceTests {
    @Test func pkceS256AndCallbackExchange() throws {
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        let state = String(repeating:"a",count:32)
        let url = try NativeAuthContract.startURL(baseURL:URL(string:"https://example.invalid")!,verifier:verifier,state:state)
        let parts = try #require(URLComponents(url:url,resolvingAgainstBaseURL:false))
        #expect(parts.path == "/api/auth/mobile/start")
        #expect(parts.queryItems?.first(where:{$0.name == "code_challenge"})?.value == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        #expect(parts.queryItems?.first(where:{$0.name == "state"})?.value == state)
        #expect(!url.absoluteString.contains(verifier))
        let body = try NativeAuthContract.exchangeBody(callbackURL:URL(string:"org.daynomy.app://auth/callback?code=fixture&state=\(state)")!,expectedState:state,verifier:verifier)
        #expect(body == .object(["code":.string("fixture"),"codeVerifier":.string(verifier)]))
    }
    @Test func rejectsWrongCallbackStateAndOAuthFailure() {
        let state = String(repeating:"a",count:32);let verifier = String(repeating:"v",count:43)
        for raw in ["https://auth/callback?code=x&state=\(state)","org.daynomy.app://evil/callback?code=x&state=\(state)","org.daynomy.app://auth/wrong?code=x&state=\(state)","org.daynomy.app://auth/callback?code=x&state=wrong","org.daynomy.app://auth/callback?error=oauth_failed&state=\(state)","org.daynomy.app://auth/callback?state=\(state)"] {
            do { _ = try NativeAuthContract.exchangeBody(callbackURL:URL(string:raw)!,expectedState:state,verifier:verifier);Issue.record("unsafe callback accepted") } catch {}
        }
    }
}
