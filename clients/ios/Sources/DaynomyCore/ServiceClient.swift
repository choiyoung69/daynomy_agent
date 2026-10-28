import Foundation

public actor ServiceClient {
    private let baseURL: URL
    private let transport: any HTTPTransport
    private var refresh: (UUID, Task<Void, any Error>)?
    private var authorizationGeneration: UInt64 = 0
    private var sessionEpoch: UInt64 = 0
    public init(baseURL: URL, transport: any HTTPTransport) { self.baseURL = baseURL; self.transport = transport }
    public func request(path: String, method: String = "GET", query: [String: String] = [:], body: ServiceValue? = nil, csrf: Bool = false, retryUnauthorized: Bool = true) async throws -> ServiceValue {
        try await requestPrepared(path: path, method: method, query: query, body: body, csrf: csrf, retryUnauthorized: retryUnauthorized)
    }
    func requestPrepared(path: String, method: String, query: [String: String] = [:], body: ServiceValue? = nil, csrf: Bool, retryUnauthorized: Bool = true, preparedBody: Data? = nil, contentType: String = "application/json") async throws -> ServiceValue {
        if path == "/api/auth/logout" || (path == "/api/users/me" && method == "DELETE") { invalidateSession() }
        let requestEpoch = sessionEpoch
        // Validate the complete body before any CSRF or network side effect.
        let encoded = try preparedBody ?? body.map { Data(try ServiceJSON.encode($0).utf8) }
        guard path.hasPrefix("/api/"), !path.contains("?"), !path.contains("#"), !path.contains("\\"),
              var parts = URLComponents(url: baseURL, resolvingAgainstBaseURL: false),
              ["http", "https"].contains(parts.scheme), parts.host != nil, parts.user == nil, parts.password == nil else { throw ServiceError(status: 0, code: "INVALID_REQUEST") }
        parts.path = path; parts.fragment = nil
        parts.queryItems = query.isEmpty ? nil : query.sorted(by: { $0.key < $1.key }).map { URLQueryItem(name: $0.key, value: $0.value) }
        parts.percentEncodedQuery = parts.percentEncodedQuery?.replacingOccurrences(of: "+", with: "%2B")
        guard let url = parts.url else { throw ServiceError(status: 0, code: "INVALID_REQUEST") }
        var request = URLRequest(url: url); request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let encoded { request.httpBody = encoded; request.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        if csrf {
            let token = try await self.request(path: "/api/auth/csrf", retryUnauthorized: false)
            guard let header = token["headerName"]?.string, !header.isEmpty,
                  header.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 45 }),
                  let value = token["token"]?.string, !value.isEmpty, !value.contains("\r"), !value.contains("\n") else { throw ServiceError(status: 0, code: "INVALID_CSRF", message: "보안 확인에 실패했어요. 다시 시도해 주세요.") }
            request.setValue(value, forHTTPHeaderField: header)
        }
        try Task.checkCancellation()
        guard requestEpoch == sessionEpoch else { throw ServiceError(status: 401, code: "SESSION_CHANGED") }
        let sentAuthorization = authorizationGeneration
        let response: HTTPResponse
        do { response = try await transport.send(request) }
        catch is CancellationError {
            if requestEpoch != sessionEpoch && path == "/api/auth/refresh" { await clearCookies() }
            throw CancellationError()
        }
        catch let error as URLError where error.code == .cancelled {
            if requestEpoch != sessionEpoch && path == "/api/auth/refresh" { await clearCookies() }
            throw CancellationError()
        }
        catch { throw ServiceError(status: 0, code: "NETWORK", message: "서버에 연결하지 못했어요.") }
        if requestEpoch != sessionEpoch {
            if path == "/api/auth/refresh" { await clearCookies() }
            throw ServiceError(status: 401, code: "SESSION_CHANGED")
        }
        try Task.checkCancellation()
        if response.status == 401 && retryUnauthorized && path != "/api/auth/refresh" && path != "/api/auth/logout" {
            // A delayed 401 from a request sent before a completed refresh must use
            // those new credentials instead of rotating the refresh token again.
            if sentAuthorization != authorizationGeneration {
                return try await self.requestPrepared(path: path, method: method, query: query, body: body, csrf: csrf, retryUnauthorized: false, preparedBody: preparedBody, contentType: contentType)
            }
            let shared: (UUID, Task<Void, any Error>)
            if let refresh { shared = refresh }
            else {
                let refreshEpoch = sessionEpoch
                shared = (UUID(), Task {
                    _ = try await self.request(path: "/api/auth/refresh", method: "POST", csrf: true, retryUnauthorized: false)
                    try Task.checkCancellation()
                    guard self.sessionEpoch == refreshEpoch else { throw CancellationError() }
                    self.authorizationGeneration &+= 1
                })
                refresh = shared
            }
            do { try await shared.1.value; if refresh?.0 == shared.0 { refresh = nil } }
            catch { if refresh?.0 == shared.0 { refresh = nil }; throw error }
            try Task.checkCancellation()
            guard requestEpoch == sessionEpoch else { throw ServiceError(status: 401, code: "SESSION_CHANGED") }
            return try await self.requestPrepared(path: path, method: method, query: query, body: body, csrf: csrf, retryUnauthorized: false, preparedBody: preparedBody, contentType: contentType)
        }
        guard (200..<300).contains(response.status) else {
            let value = try? ServiceJSON.decode(response.data)
            throw ServiceError(status: response.status, code: value?["code"]?.string, message: value?["message"]?.string ?? "요청을 처리하지 못했어요.")
        }
        if path == "/api/auth/logout" || (path == "/api/users/me" && method == "DELETE") { await clearCookies() }
        if response.status == 204 { return .null }
        return try ServiceJSON.decode(response.data)
    }
    private func clearCookies() async {
        if let transport = transport as? any SessionCookieTransport { await transport.clearSessionCookies() }
    }
    public func invalidateSession() {
        sessionEpoch &+= 1; authorizationGeneration &+= 1
        refresh?.1.cancel(); refresh = nil
    }
    public func call(_ endpoint: ServiceEndpoint, query: [String: String] = [:], body: ServiceValue? = nil) async throws -> ServiceValue {
        try await request(path: endpoint.path, method: endpoint.method, query: query, body: body, csrf: endpoint.csrf)
    }
}

struct ServiceJSON {
    let bytes: [UInt8]
    var index = 0
    static func decode(_ data: Data) throws -> ServiceValue {
        var parser = ServiceJSON(bytes: Array(data)); let value = try parser.value(depth: 0); parser.whitespace()
        guard parser.index == parser.bytes.count else { throw invalid() }; return value
    }
    static func invalid() -> ServiceError { ServiceError(status: 0, code: "INVALID_JSON", message: "서버 응답 형식이 올바르지 않아요.") }
    static func encode(_ value: ServiceValue) throws -> String {
        switch value {
        case .null: return "null"
        case .bool(let value): return value ? "true" : "false"
        case .string(let value): return String(decoding: try JSONEncoder().encode(value), as: UTF8.self)
        case .number(let value):
            guard value.range(of: #"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\z"#, options: .regularExpression) != nil else { throw invalid() }; return value
        case .array(let values): return "[" + (try values.map(encode)).joined(separator: ",") + "]"
        case .object(let values): return "{" + (try values.sorted(by: { $0.key < $1.key }).map { try encode(.string($0.key)) + ":" + encode($0.value) }).joined(separator: ",") + "}"
        }
    }
    mutating func whitespace() { while index < bytes.count && [9, 10, 13, 32].contains(bytes[index]) { index += 1 } }
    mutating func take(_ byte: UInt8) -> Bool { if index < bytes.count && bytes[index] == byte { index += 1; return true }; return false }
    mutating func value(depth: Int) throws -> ServiceValue {
        whitespace(); guard depth < 128, index < bytes.count else { throw Self.invalid() }
        if take(123) {
            var object: [String: ServiceValue] = [:]; whitespace()
            if take(125) { return .object(object) }
            repeat {
                whitespace(); let key = try string(); whitespace(); guard take(58) else { throw Self.invalid() }
                object[key] = try value(depth: depth + 1); whitespace()
                if take(125) { return .object(object) }; guard take(44) else { throw Self.invalid() }
            } while true
        }
        if take(91) {
            var array: [ServiceValue] = []; whitespace(); if take(93) { return .array(array) }
            repeat { array.append(try value(depth: depth + 1)); whitespace(); if take(93) { return .array(array) }; guard take(44) else { throw Self.invalid() } } while true
        }
        if bytes[index] == 34 { return .string(try string()) }
        for (literal, result) in [("null", ServiceValue.null), ("true", .bool(true)), ("false", .bool(false))] {
            let token = Array(literal.utf8); if bytes[index...].starts(with: token) { index += token.count; return result }
        }
        let start = index; _ = take(45)
        if !take(48) { guard digit(nonzero: true) else { throw Self.invalid() }; while digit() {} }
        if take(46) { guard digit() else { throw Self.invalid() }; while digit() {} }
        if take(101) || take(69) { if !take(43) { _ = take(45) }; guard digit() else { throw Self.invalid() }; while digit() {} }
        guard index > start else { throw Self.invalid() }; return .number(String(decoding: bytes[start..<index], as: UTF8.self))
    }
    mutating func digit(nonzero: Bool = false) -> Bool { guard index < bytes.count, bytes[index] >= (nonzero ? 49 : 48), bytes[index] <= 57 else { return false }; index += 1; return true }
    mutating func string() throws -> String {
        let start = index; guard take(34) else { throw Self.invalid() }
        while index < bytes.count {
            let byte = bytes[index]; index += 1
            if byte == 34 { do { return try JSONDecoder().decode(String.self, from: Data(bytes[start..<index])) } catch { throw Self.invalid() } }
            if byte == 92 { guard index < bytes.count else { break }; index += 1 } else if byte < 32 { throw Self.invalid() }
        }; throw Self.invalid()
    }
}
