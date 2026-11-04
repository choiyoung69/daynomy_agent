package com.daynomy.webview

private fun expect(policy: NavigationPolicy, url: String, user: Boolean, expected: NavigationDecision) {
    check(policy.decide(url, user) == expected) { "Navigation policy mismatch for $url activated=$user expected=$expected" }
}
fun main() {
    val release = NavigationPolicy("https://app.daynomy.test", false)
    for (url in listOf("https://app.daynomy.test", "https://app.daynomy.test:443/path?q=x#y", "https://APP.DAYNOMY.TEST/path")) {
        expect(release, url, false, NavigationDecision.INTERNAL)
    }
    for (url in listOf("https://example.org", "https://app.daynomy.test:444/a", "https://sub.app.daynomy.test")) {
        expect(release, url, false, NavigationDecision.BLOCK)
        expect(release, url, true, NavigationDecision.EXTERNAL)
    }
    for (url in listOf("https://user:password@app.daynomy.test", "https://app.daynomy.test@evil.test", "http://app.daynomy.test", "javascript:alert(1)", "data:text/html,attack", "file:///etc/passwd", "intent://evil", "//evil.test", "garbage")) {
        expect(release, url, false, NavigationDecision.BLOCK)
        expect(release, url, true, NavigationDecision.BLOCK)
    }
    val debug = NavigationPolicy("http://10.0.2.2:18082", true)
    expect(debug, "http://10.0.2.2:18082/", false, NavigationDecision.INTERNAL)
    expect(debug, "http://10.0.2.2:18083/", true, NavigationDecision.BLOCK)
    expect(debug, "http://192.168.0.5:18082/", true, NavigationDecision.BLOCK)
    check(runCatching { NavigationPolicy("http://10.0.2.2:18082", false) }.isFailure)
    check(runCatching { NavigationPolicy("http://example.org", true) }.isFailure)
    println("Android pure navigation policy assertions passed (no WebView runtime claim)")
}
