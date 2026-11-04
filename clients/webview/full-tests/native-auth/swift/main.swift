import Foundation

let origin = "https://app.example.invalid"
let state = String(repeating: "s", count: 43)
let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
let code = String(repeating: "c", count: 43)
let start: Int64 = 1_000_000
var assertions = 0
func expect(_ value: Bool, _ label: String) { assertions += 1; precondition(value, label) }
func required<T>(_ value: T?, _ label: String) -> T { guard let value = value else { fatalError(label) }; return value }
func fresh(_ configuredOrigin: String = origin, _ debug: Bool = false) -> NativeAuthSession { NativeAuthSession(trustedOrigin: configuredOrigin, debug: debug) }
func begin(_ s: NativeAuthSession, url: String = origin + "/api/auth/google", source: String = origin + "/login?returnTo=%2F", method: String = "GET", main: Bool = true, user: Bool = true, appState: String = state, codeVerifier: String = verifier, time: Int64 = start) -> AuthLaunch? {
    s.begin(navigationURL: url, sourceDocumentURL: source, httpMethod: method, isMainFrame: main, userActivated: user, state: appState, verifier: codeVerifier, nowMillis: time)
}
func callback(_ appState: String = state, _ authorizationCode: String = code) -> String { "org.daynomy.app://auth/callback?code=\(authorizationCode)&state=\(appState)" }
func cookies(_ secure: Bool = true) -> [String] { [
    "access_token=fixture.access; Path=/; Max-Age=1800; HttpOnly; SameSite=Lax" + (secure ? "; Secure" : ""),
    "refresh_token=fixture.refresh; Path=/api/auth; Max-Age=1209600; HttpOnly; SameSite=Lax" + (secure ? "; Secure" : "")
] }
func exchange(_ s: NativeAuthSession) -> AuthExchange {
    expect(begin(s) != nil, "exchange setup begins")
    return required(s.receive(callbackURL: callback(), nowMillis: start + 1), "exchange setup callback")
}
func complete(_ s: NativeAuthSession, _ e: AuthExchange, _ headers: [String] = cookies(), time: Int64 = start + 2, status: Int = 204, url: String? = nil, requestId: String? = nil) -> AuthCookiePlan? {
    s.complete(requestId: requestId ?? e.requestId, status: status, responseURL: url ?? e.exchangeURL, setCookieHeaders: headers, nowMillis: time)
}

let session = fresh()
let launch = required(begin(session), "trusted clicked login must launch")
let uri = required(URLComponents(string: launch.authorizationURL), "authorization URL parses")
let items = uri.queryItems ?? []
let params = Dictionary(uniqueKeysWithValues: items.map { ($0.name, $0.value ?? "") })
expect(uri.scheme == "https" && uri.host == "app.example.invalid" && uri.percentEncodedPath == "/api/auth/mobile/start", "authorization exact origin/path")
expect(params["code_challenge"] == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", "RFC7636 S256 vector")
expect(params["state"] == state, "state preserved")
expect(params.keys.allSatisfy { ["state", "code_challenge", "code_challenge_method"].contains($0) }, "no unexpected authorization field")
expect(items.count == params.count, "authorization query contains no duplicate fields")
expect(params["code_challenge_method"] == nil || params["code_challenge_method"] == "S256", "challenge method S256 if present")
expect(!launch.authorizationURL.contains(verifier), "verifier absent from browser URL")
expect(begin(session) == nil, "duplicate begin cannot replace pending state")
let received = required(session.receive(callbackURL: callback(), nowMillis: start + 1), "valid callback")
expect(received.exchangeURL == origin + "/api/auth/mobile/exchange", "exchange URL exact")
expect(received.code == code && received.codeVerifier == verifier, "native exchange payload retained")
expect(!received.requestId.isEmpty, "exchange ID nonempty")
expect(session.receive(callbackURL: callback(), nowMillis: start + 2) == nil, "callback single use")
let plan = required(complete(session, received), "valid cookie completion")
expect(plan.originURL == origin && plan.reloadURL == origin + "/", "cookie target and reload exact origin")
expect(plan.setCookieHeaders == cookies(), "raw cookie security attributes preserved")
expect(complete(session, received, time: start + 3) == nil, "completion single use")

for configured in ["http://app.example.invalid", "https://app.example.invalid/", "https://app.example.invalid/path", "https://user@app.example.invalid", "https://app.example.invalid?x=1", "https://app.example.invalid#x", "javascript:alert(1)", "https://app.example.invalid:99999"] {
    expect(begin(fresh(configured)) == nil, "invalid configured origin rejected")
}
for configured in ["http://127.0.0.1:18082", "http://localhost:18082", "http://10.0.2.2:18082"] {
    expect(begin(fresh(configured, true), url: configured + "/api/auth/google", source: configured + "/login") != nil, "debug local HTTP allowed")
    expect(begin(fresh(configured, false), url: configured + "/api/auth/google", source: configured + "/login") == nil, "release local HTTP denied")
}
expect(begin(fresh("http://192.168.1.2:18082", true), url: "http://192.168.1.2:18082/api/auth/google", source: "http://192.168.1.2:18082/login") == nil, "debug LAN HTTP denied")
for url in ["https://evil.invalid/api/auth/google", "http://app.example.invalid/api/auth/google", "https://app.example.invalid.evil.invalid/api/auth/google", "https://user@app.example.invalid/api/auth/google", origin + ":444/api/auth/google", origin + "/api/auth/google/", origin + "/api/auth/%67oogle", origin + "/api/auth/google?x=1", origin + "/api/auth/google#x"] {
    expect(begin(fresh(), url: url) == nil, "navigation boundary rejected")
}
for source in ["https://evil.invalid/login", "https://app.example.invalid.evil.invalid/", "https://user@app.example.invalid/login", "data:text/html,login", ""] {
    expect(begin(fresh(), source: source) == nil, "untrusted source document rejected")
}
expect(begin(fresh(), method: "POST") == nil, "nonGET login rejected")
expect(begin(fresh(), main: false) == nil, "subframe login rejected")
expect(begin(fresh(), user: false) == nil, "unactivated navigation rejected")
for invalid in [String(repeating: "s", count: 31), String(repeating: "s", count: 129), String(repeating: "s", count: 32) + "+", String(repeating: "한", count: 32)] { expect(begin(fresh(), appState: invalid) == nil, "invalid state rejected") }
for invalid in [String(repeating: "v", count: 42), String(repeating: "v", count: 129), String(repeating: "v", count: 42) + "+", String(repeating: "한", count: 43)] { expect(begin(fresh(), codeVerifier: invalid) == nil, "invalid verifier rejected") }
expect(begin(fresh(), time: -1) == nil, "negative clock rejected")

let badCallbacks = [
    "https://auth/callback?code=\(code)&state=\(state)", "org.daynomy.app://evil/callback?code=\(code)&state=\(state)",
    "org.daynomy.app://user@auth/callback?code=\(code)&state=\(state)", "org.daynomy.app://auth:443/callback?code=\(code)&state=\(state)",
    "org.daynomy.app://auth/callback/?code=\(code)&state=\(state)", "org.daynomy.app://auth/%63allback?code=\(code)&state=\(state)",
    callback() + "#fragment", callback() + "&extra=1", callback() + "&state=" + state, callback() + "&%73tate=" + state,
    callback() + "&code=" + code, callback() + "&error=oauth_failed", callback(String(repeating: "x", count: 43)),
    callback(state, String(repeating: "c", count: 31)), callback(state, String(repeating: "c", count: 129)), callback(state, ""), callback(state, String(repeating: "c", count: 32) + "+"),
    callback(state, "%ZZ"), callback(state, "%"), callback(state, String(repeating: "%2563", count: 43)), callback(state, "%00" + code),
    "org.daynomy.app://auth/callback?code=\(code)", "org.daynomy.app://auth/callback?state=\(state)",
    "org.daynomy.app://auth/callback?error=unknown&state=\(state)"
]
for bad in badCallbacks {
    let test = fresh(); _ = begin(test)
    expect(test.receive(callbackURL: bad, nowMillis: start + 1) == nil, "malformed callback rejected")
    expect(test.receive(callbackURL: callback(), nowMillis: start + 2) != nil, "malformed callback preserves legitimate pending request")
}
let percent = fresh(); _ = begin(percent)
expect(percent.receive(callbackURL: callback(state, String(repeating: "%63", count: 43)), nowMillis: start + 1)?.code == code, "callback percent decoded exactly once")
for time in [start - 1, start + 600_000, start + 600_001] {
    let test = fresh(); _ = begin(test)
    expect(test.receive(callbackURL: callback(), nowMillis: time) == nil, "expired or reversed callback clock rejected")
    expect(test.receive(callbackURL: callback(), nowMillis: start + 1) == nil, "expired pending state cleared")
}
let atBoundary = fresh(); _ = begin(atBoundary)
expect(atBoundary.receive(callbackURL: callback(), nowMillis: start + 599_999) != nil, "callback just before TTL accepted")
let failure = fresh(); _ = begin(failure)
expect(failure.receive(callbackURL: "org.daynomy.app://auth/callback?error=oauth_failed&state=" + state, nowMillis: start + 1) == nil, "matched provider failure produces no exchange")
expect(failure.receive(callbackURL: callback(), nowMillis: start + 2) == nil, "matched provider failure consumes pending state")
expect(begin(failure, time: start + 3) != nil, "new auth possible after matched failure")
let cancelled = fresh(); _ = begin(cancelled); cancelled.cancel()
expect(cancelled.receive(callbackURL: callback(), nowMillis: start + 1) == nil, "cancel blocks callback")
let cancelledExchange = fresh(); let pending = exchange(cancelledExchange); cancelledExchange.cancel()
expect(complete(cancelledExchange, pending) == nil, "cancel blocks late network completion")
let restarted = fresh(); let old = exchange(restarted); restarted.cancel(); let newer = exchange(restarted)
expect(old.requestId != newer.requestId, "new handshake has a distinct exchange generation")
expect(complete(restarted, old) == nil, "cancelled generation cannot complete replacement")
expect(complete(restarted, newer, time: start + 3) != nil, "replacement still completes")

for url in ["https://evil.invalid/api/auth/mobile/exchange", origin + "/api/auth/mobile/exchange/", origin + "/api/auth/mobile/exchange?x=1", origin + "/api/auth/mobile/exchange#x", origin + "/api/auth/mobile/%65xchange", origin + ":444/api/auth/mobile/exchange"] {
    let test = fresh(); let e = exchange(test)
    expect(complete(test, e, url: url) == nil, "redirected or different response URL rejected")
}
for status in [200, 201, 302, 400, 401, 500] {
    let test = fresh(); let e = exchange(test)
    expect(complete(test, e, status: status) == nil, "only exchange204 installs cookies")
}
let stale = fresh(); let current = exchange(stale)
expect(complete(stale, current, requestId: current.requestId + "-stale") == nil, "stale completion ID rejected")
expect(complete(stale, current, time: start + 3) != nil, "stale response cannot consume current exchange")
for time in [start, start + 60_001, start + 600_000] {
    let test = fresh(); let e = exchange(test)
    expect(complete(test, e, time: time) == nil, "completion clock/lifetime boundary rejected")
}
let beforeExpiry = fresh(); let before = exchange(beforeExpiry)
expect(complete(beforeExpiry, before, time: start + 60_000) != nil, "completion just before exchangeTTL accepted")
let overall = fresh(); _ = begin(overall)
let late = required(overall.receive(callbackURL: callback(), nowMillis: start + 599_999), "late callback valid")
expect(complete(overall, late, time: start + 600_000) == nil, "overall auth TTL also limits exchange")

let valid = cookies()
func replacing(_ value: String, _ old: String, _ new: String) -> String { value.replacingOccurrences(of: old, with: new) }
let badCookieSets: [[String]] = [
    [], [valid[0]], [valid[1]], valid + [valid[0]], Array(valid.reversed()) + ["other=x; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=10"],
    [replacing(valid[0], "HttpOnly; ", ""), valid[1]], [valid[0], replacing(valid[1], "; Secure", "")],
    [replacing(valid[0], "Path=/;", "Path=/api/auth;"), valid[1]], [valid[0], replacing(valid[1], "Path=/api/auth;", "Path=/;")],
    [replacing(valid[0], "SameSite=Lax", "SameSite=None"), valid[1]], [replacing(valid[0], "Max-Age=1800", "Max-Age=0"), valid[1]],
    [replacing(valid[0], "Max-Age=1800", "Max-Age=-1"), valid[1]], [replacing(valid[0], "Max-Age=1800", "Max-Age=oops"), valid[1]],
    [valid[0] + "; Domain=evil.invalid", valid[1]], [valid[0] + "; Domain=example.invalid", valid[1]], [valid[0] + "; Domain=sub.app.example.invalid", valid[1]],
    [valid[0] + "; Path=/", valid[1]], [valid[0] + "; HttpOnly", valid[1]], [valid[0] + "; Secure", valid[1]],
    [valid[0] + "\r\nX-Leak: fixture", valid[1]], [replacing(valid[0], "fixture.access", "a,b"), valid[1]],
    [replacing(valid[0], "fixture.access", ""), valid[1]], [valid[0] + ", " + valid[1]]
]
for headers in badCookieSets {
    let test = fresh(); let e = exchange(test)
    expect(complete(test, e, headers) == nil, "invalid cookie set never partially installs")
}
let exactDomain = fresh(); let domainExchange = exchange(exactDomain)
expect(complete(exactDomain, domainExchange, valid.map { $0 + "; Domain=app.example.invalid" }) != nil, "exact host domain accepted")
let casing = fresh(); let casingExchange = exchange(casing)
expect(complete(casing, casingExchange, valid.map { $0.replacingOccurrences(of: "HttpOnly", with: "httponly").replacingOccurrences(of: "SameSite=Lax", with: "samesite=lax").replacingOccurrences(of: "Path=", with: "path=").replacingOccurrences(of: "Max-Age=", with: "max-age=").replacingOccurrences(of: "Secure", with: "secure") }) != nil, "cookie attribute names case insensitive")
let debug = fresh("http://127.0.0.1:18082", true)
expect(begin(debug, url: "http://127.0.0.1:18082/api/auth/google", source: "http://127.0.0.1:18082/login") != nil, "debug setup")
let debugExchange = required(debug.receive(callbackURL: callback(), nowMillis: start + 1), "debug callback")
expect(complete(debug, debugExchange, cookies(false)) != nil, "debug local cookie may omit Secure while retaining HttpOnly")
print("NativeAuthSession Swift: \(assertions) assertions passed")
