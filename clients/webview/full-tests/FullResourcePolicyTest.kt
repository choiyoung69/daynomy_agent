package com.daynomy.webview

private var count = 0
private fun expect(policy: FullResourcePolicy, url: String, main: Boolean, expected: Boolean) {
    count++
    check(policy.allows(url, main) == expected) { "Resource policy mismatch for $url main=$main expected=$expected" }
}
fun main() {
    val release = FullResourcePolicy("https://app.daynomy.test", false)
    for (url in listOf("https://app.daynomy.test", "https://app.daynomy.test:443/assets/app.js", "https://APP.DAYNOMY.TEST/news?q=foo%2Fbar#detail")) {
        expect(release, url, true, true); expect(release, url, false, true)
    }
    for (url in listOf("https://images.example.org/photo.webp", "https://platform.x.com/widgets.js", "https://www.threads.com/embed.js", "https://www.youtube.com/embed/test", "https://example.org:444/asset", "https://app.daynomy.test:444/image", "https://sub.app.daynomy.test/image")) {
        expect(release, url, false, true); expect(release, url, true, false)
    }
    for (url in listOf("http://example.org/image", "http://app.daynomy.test/image", "http://127.0.0.1:18082/", "file:///etc/passwd", "javascript:alert(1)", "data:image/png;base64,AAAA", "intent://evil", "content://picker/image", "https://user:pass@example.org/a", "https://app.daynomy.test@evil.test/a", "https://example.org:0/a", "https://example.org:65536/a", "https://example.org:abc/a", "https://example.org\\evil/a", "//example.org/a", "https://exa mple.org/a", "garbage", "https://", "")) {
        expect(release, url, false, false); expect(release, url, true, false)
    }
    val debug = FullResourcePolicy("http://10.0.2.2:18082", true)
    expect(debug, "http://10.0.2.2:18082/news", true, true)
    expect(debug, "http://10.0.2.2:18082/assets/app.js", false, true)
    expect(debug, "http://10.0.2.2:18083/image", false, false)
    expect(debug, "http://192.168.0.5:18082/image", false, false)
    expect(debug, "https://images.example.org/image", false, true)
    expect(debug, "https://images.example.org/image", true, false)
    for (mime in listOf("image/png", "image/jpeg", "image/webp", "image/gif")) { count++; check(FullResourcePolicy.acceptsImage("content", mime)) }
    for ((scheme, mime) in listOf(null to "image/png", "file" to "image/png", "http" to "image/png", "data" to "image/png", "content" to null, "content" to "", "content" to "text/plain", "content" to "application/octet-stream", "content" to "image/")) { count++; check(!FullResourcePolicy.acceptsImage(scheme, mime)) }
    println("Full Android resource/image policy: $count assertions passed; no WebView runtime claim")
}
