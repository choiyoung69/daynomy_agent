import Foundation
var count = 0
func expect(_ policy: FullResourcePolicy, _ url: String, _ main: Bool, _ expected: Bool) {
    count += 1
    precondition(policy.allows(url, isMainFrame: main) == expected, "Resource policy mismatch for \(url), main=\(main), expected=\(expected)")
}
let release = FullResourcePolicy(trustedOrigin: "https://app.daynomy.test", debug: false)
for url in ["https://app.daynomy.test", "https://app.daynomy.test:443/assets/app.js", "https://APP.DAYNOMY.TEST/news?q=foo%2Fbar#detail"] {
    expect(release, url, true, true); expect(release, url, false, true)
}
for url in ["https://images.example.org/photo.webp", "https://platform.x.com/widgets.js", "https://www.threads.com/embed.js", "https://www.youtube.com/embed/test", "https://example.org:444/asset", "https://app.daynomy.test:444/image", "https://sub.app.daynomy.test/image"] {
    expect(release, url, false, true); expect(release, url, true, false)
}
for url in ["http://example.org/image", "http://app.daynomy.test/image", "http://127.0.0.1:18082/", "file:///etc/passwd", "javascript:alert(1)", "data:image/png;base64,AAAA", "intent://evil", "content://picker/image", "https://user:pass@example.org/a", "https://app.daynomy.test@evil.test/a", "https://example.org:0/a", "https://example.org:65536/a", "https://example.org:abc/a", "https://example.org\\evil/a", "//example.org/a", "https://exa mple.org/a", "garbage", "https://", ""] {
    expect(release, url, false, false); expect(release, url, true, false)
}
let debug = FullResourcePolicy(trustedOrigin: "http://127.0.0.1:18082", debug: true)
expect(debug, "http://127.0.0.1:18082/news", true, true)
expect(debug, "http://127.0.0.1:18082/assets/app.js", false, true)
expect(debug, "http://127.0.0.1:18083/image", false, false)
expect(debug, "http://192.168.0.5:18082/image", false, false)
expect(debug, "https://images.example.org/image", false, true)
expect(debug, "https://images.example.org/image", true, false)
for mime in ["image/png", "image/jpeg", "image/webp", "image/gif"] { count += 1; precondition(FullResourcePolicy.acceptsImage(scheme: "content", mime: mime)) }
let rejected: [(String?,String?)] = [(nil,"image/png"),("file","image/png"),("http","image/png"),("data","image/png"),("content",nil),("content",""),("content","text/plain"),("content","application/octet-stream"),("content","image/")]
for (scheme,mime) in rejected { count += 1; precondition(!FullResourcePolicy.acceptsImage(scheme: scheme, mime: mime)) }
print("Full Swift resource/image policy: \(count) assertions passed; no WKWebView runtime claim")
