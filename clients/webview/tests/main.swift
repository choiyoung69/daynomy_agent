import Foundation
func expect(_ policy: NavigationPolicy, _ url: String, _ user: Bool, _ expected: NavigationDecision) {
    precondition(policy.decide(url, userActivated: user) == expected, "Navigation policy mismatch: \(url) activated=\(user)")
}
let release = NavigationPolicy(trustedOrigin: "https://app.daynomy.test", debug: false)
for url in ["https://app.daynomy.test", "https://app.daynomy.test:443/path?q=x#y", "https://APP.DAYNOMY.TEST/path"] {
    expect(release, url, false, .internalPage)
}
for url in ["https://example.org", "https://app.daynomy.test:444/a", "https://sub.app.daynomy.test"] {
    expect(release, url, false, .block)
    expect(release, url, true, .externalBrowser)
}
for url in ["https://user:password@app.daynomy.test", "https://app.daynomy.test@evil.test", "http://app.daynomy.test", "javascript:alert(1)", "data:text/html,attack", "file:///etc/passwd", "intent://evil", "//evil.test", "garbage"] {
    expect(release, url, false, .block)
    expect(release, url, true, .block)
}
let debug = NavigationPolicy(trustedOrigin: "http://127.0.0.1:18082", debug: true)
expect(debug, "http://127.0.0.1:18082/", false, .internalPage)
expect(debug, "http://127.0.0.1:18083/", true, .block)
expect(debug, "http://192.168.0.5:18082/", true, .block)
print("Swift pure navigation policy assertions passed (no WKWebView runtime claim)")
