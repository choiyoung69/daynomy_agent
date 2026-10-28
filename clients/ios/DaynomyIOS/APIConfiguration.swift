import Foundation

enum APIConfiguration {
    static func load() throws -> URL {
        var text = Bundle.main.object(forInfoDictionaryKey: "DaynomyAPIURL") as? String ?? ""
        #if DEBUG
        if let override = ProcessInfo.processInfo.environment["DAYNOMY_API_BASE_URL"] {
            guard let candidate = URL(string: override), candidate.scheme == "http" || candidate.scheme == "https",
                  let host = candidate.host, ["127.0.0.1", "localhost", "::1"].contains(host) else {
                throw ConfigurationError.invalidURL
            }
            text = override
        }
        #endif
        guard let url = URL(string: text), let host = url.host,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil else {
            throw ConfigurationError.invalidURL
        }
        if url.scheme == "https" { return url }
        #if DEBUG
        if url.scheme == "http" && ["127.0.0.1", "localhost", "::1"].contains(host) { return url }
        #endif
        throw ConfigurationError.invalidURL
    }
    enum ConfigurationError: Error { case invalidURL }
}
