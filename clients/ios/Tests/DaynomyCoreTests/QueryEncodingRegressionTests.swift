import Foundation
import Testing
@testable import DaynomyCore

// Original frontend stocks/api.ts searchStocks uses URLSearchParams (form encoding).
// app/src/api.rs query() applies application/x-www-form-urlencoded '+' -> space decoding.
// URLComponents.queryItems round-trip alone misses this client/server boundary.
struct QueryEncodingRegressionTests {
    @Test func formDecoderPreservesLiteralPlus() async throws {
        for keyword in ["삼성 & ETF%_!+?#", "A+B C++", "+ +한글 +"] {
            let transport = RecordingTransport("{\"stocks\":[]}")
            _ = try await client(transport).search(keyword: keyword, country: .KR)
            let request = try #require(await transport.lastRequest())
            let url = try #require(request.url)
            let components = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false))
            let query = try #require(components.percentEncodedQuery)
            let fields = query.split(separator: "&").map { String($0).split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false).map(String.init) }
            let encodedQ = try #require(fields.first(where: { $0.first == "q" })?.last)
            let serverDecodedQ = encodedQ.replacingOccurrences(of: "+", with: " ").removingPercentEncoding
            #expect(serverDecodedQ == keyword)
        }
    }
}
