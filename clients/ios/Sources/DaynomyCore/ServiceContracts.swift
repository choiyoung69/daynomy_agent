import Foundation
public indirect enum ServiceValue: Equatable, Sendable {
    case object([String: ServiceValue]), array([ServiceValue]), string(String), number(String), bool(Bool), null
    public var object: [String: ServiceValue]? { if case .object(let value) = self { value } else { nil } }
    public var array: [ServiceValue]? { if case .array(let value) = self { value } else { nil } }
    public var string: String? { if case .string(let value) = self { value } else { nil } }
    public var number: String? { if case .number(let value) = self { value } else { nil } }
    public subscript(_ key: String) -> ServiceValue? { object?[key] }
}
public struct ServiceError: Error, Equatable, Sendable {
    public let status: Int
    public let code: String?
    public let message: String
    public init(status: Int, code: String? = nil, message: String = "요청을 처리하지 못했습니다.") { self.status = status; self.code = code; self.message = message }
}
public struct ServiceEndpoint: Equatable, Sendable {
    public let path: String
    public let method: String
    public let csrf: Bool
    public init(path: String, method: String = "GET", csrf: Bool = false) { self.path = path; self.method = method; self.csrf = csrf }
}
