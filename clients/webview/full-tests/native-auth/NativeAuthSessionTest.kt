package com.daynomy.webview

import java.net.URI
import java.net.URLDecoder

private const val ORIGIN = "https://app.example.invalid"
private const val STATE = "sssssssssssssssssssssssssssssssssssssssssss"
private const val VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
private const val CODE = "ccccccccccccccccccccccccccccccccccccccccccc"
private const val START = 1_000_000L
private var assertions = 0
private fun expect(value: Boolean, label: String) { assertions++; check(value) { label } }
private fun fresh(origin: String = ORIGIN, debug: Boolean = false) = NativeAuthSession(origin, debug)
private fun begin(s: NativeAuthSession, url: String = "$ORIGIN/api/auth/google", source: String = "$ORIGIN/login?returnTo=%2F", method: String = "GET", main: Boolean = true, user: Boolean = true, state: String = STATE, verifier: String = VERIFIER, time: Long = START) =
    s.begin(url, source, method, main, user, state, verifier, time)
private fun callback(state: String = STATE, code: String = CODE) = "org.daynomy.app://auth/callback?code=$code&state=$state"
private fun cookies(secure: Boolean = true) = listOf(
    "access_token=fixture.access; Path=/; Max-Age=1800; HttpOnly; SameSite=Lax" + if (secure) "; Secure" else "",
    "refresh_token=fixture.refresh; Path=/api/auth; Max-Age=1209600; HttpOnly; SameSite=Lax" + if (secure) "; Secure" else ""
)
private fun exchange(s: NativeAuthSession): AuthExchange {
    expect(begin(s) != null, "exchange setup begins")
    return checkNotNull(s.receive(callback(), START + 1)) { "exchange setup callback" }
}
private fun query(url: String): Map<String, String> = URI(url).rawQuery.split('&').associate {
    val pair = it.split('=', limit = 2); URLDecoder.decode(pair[0], "UTF-8") to URLDecoder.decode(pair.getOrElse(1) { "" }, "UTF-8")
}

fun main() {
    val s = fresh()
    val launch = checkNotNull(begin(s)) { "trusted clicked login must launch" }
    val uri = URI(launch.authorizationURL)
    val params = query(launch.authorizationURL)
    expect(uri.scheme == "https" && uri.host == "app.example.invalid" && uri.rawPath == "/api/auth/mobile/start", "authorization exact origin/path")
    expect(params["code_challenge"] == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", "RFC7636 S256 vector")
    expect(params["state"] == STATE, "state preserved")
    expect(params.keys.all { it in setOf("state", "code_challenge", "code_challenge_method") }, "no unexpected authorization field")
    expect(uri.rawQuery.split('&').size == params.size, "authorization query contains no duplicate fields")
    expect(params["code_challenge_method"] == null || params["code_challenge_method"] == "S256", "challenge method S256 if present")
    expect(!launch.authorizationURL.contains(VERIFIER), "verifier absent from browser URL")
    expect(begin(s) == null, "duplicate begin cannot replace pending state")
    val received = checkNotNull(s.receive(callback(), START + 1)) { "valid callback" }
    expect(received.exchangeURL == "$ORIGIN/api/auth/mobile/exchange", "exchange URL exact")
    expect(received.code == CODE && received.codeVerifier == VERIFIER, "native exchange payload retained")
    expect(received.requestId.isNotEmpty(), "exchange ID nonempty")
    expect(s.receive(callback(), START + 2) == null, "callback single use")
    val plan = checkNotNull(s.complete(received.requestId, 204, received.exchangeURL, cookies(), START + 2)) { "valid cookie completion" }
    expect(plan.originURL == ORIGIN && plan.reloadURL == "$ORIGIN/", "cookie target and reload exact origin")
    expect(plan.setCookieHeaders == cookies(), "raw cookie security attributes preserved")
    expect(s.complete(received.requestId, 204, received.exchangeURL, cookies(), START + 3) == null, "completion single use")

    for (origin in listOf("http://app.example.invalid", "https://app.example.invalid/", "https://app.example.invalid/path", "https://user@app.example.invalid", "https://app.example.invalid?x=1", "https://app.example.invalid#x", "javascript:alert(1)", "https://app.example.invalid:99999")) {
        expect(begin(fresh(origin)) == null, "invalid configured origin rejected")
    }
    for (origin in listOf("http://127.0.0.1:18082", "http://localhost:18082", "http://10.0.2.2:18082")) {
        expect(begin(fresh(origin, true), "$origin/api/auth/google", "$origin/login") != null, "debug local HTTP allowed")
        expect(begin(fresh(origin, false), "$origin/api/auth/google", "$origin/login") == null, "release local HTTP denied")
    }
    expect(begin(fresh("http://192.168.1.2:18082", true), "http://192.168.1.2:18082/api/auth/google", "http://192.168.1.2:18082/login") == null, "debug LAN HTTP denied")
    for (url in listOf("https://evil.invalid/api/auth/google", "http://app.example.invalid/api/auth/google", "https://app.example.invalid.evil.invalid/api/auth/google", "https://user@app.example.invalid/api/auth/google", "$ORIGIN:444/api/auth/google", "$ORIGIN/api/auth/google/", "$ORIGIN/api/auth/%67oogle", "$ORIGIN/api/auth/google?x=1", "$ORIGIN/api/auth/google#x")) {
        expect(begin(fresh(), url) == null, "navigation boundary rejected")
    }
    for (source in listOf("https://evil.invalid/login", "https://app.example.invalid.evil.invalid/", "https://user@app.example.invalid/login", "data:text/html,login", "")) {
        expect(begin(fresh(), source = source) == null, "untrusted source document rejected")
    }
    expect(begin(fresh(), method = "POST") == null, "nonGET login rejected")
    expect(begin(fresh(), main = false) == null, "subframe login rejected")
    expect(begin(fresh(), user = false) == null, "unactivated navigation rejected")
    for (state in listOf("s".repeat(31), "s".repeat(129), "s".repeat(32) + "+", "한".repeat(32))) expect(begin(fresh(), state = state) == null, "invalid state rejected")
    for (v in listOf("v".repeat(42), "v".repeat(129), "v".repeat(42) + "+", "한".repeat(43))) expect(begin(fresh(), verifier = v) == null, "invalid verifier rejected")
    expect(begin(fresh(), time = -1) == null, "negative clock rejected")

    val badCallbacks = listOf(
        "https://auth/callback?code=$CODE&state=$STATE", "org.daynomy.app://evil/callback?code=$CODE&state=$STATE",
        "org.daynomy.app://user@auth/callback?code=$CODE&state=$STATE", "org.daynomy.app://auth:443/callback?code=$CODE&state=$STATE",
        "org.daynomy.app://auth/callback/?code=$CODE&state=$STATE", "org.daynomy.app://auth/%63allback?code=$CODE&state=$STATE",
        callback() + "#fragment", callback() + "&extra=1", callback() + "&state=$STATE", callback() + "&%73tate=$STATE",
        callback() + "&code=$CODE", callback() + "&error=oauth_failed", callback(state = "x".repeat(43)),
        callback(code = "c".repeat(31)), callback(code = "c".repeat(129)), callback(code = ""), callback(code = "c".repeat(32) + "+"),
        callback(code = "%ZZ"), callback(code = "%"), callback(code = "%2563".repeat(43)), callback(code = "%00" + CODE),
        "org.daynomy.app://auth/callback?code=$CODE", "org.daynomy.app://auth/callback?state=$STATE",
        "org.daynomy.app://auth/callback?error=unknown&state=$STATE"
    )
    for (bad in badCallbacks) {
        val test = fresh(); begin(test)
        expect(test.receive(bad, START + 1) == null, "malformed callback rejected")
        expect(test.receive(callback(), START + 2) != null, "malformed callback preserves legitimate pending request")
    }
    val percent = fresh(); begin(percent)
    expect(percent.receive(callback(code = "%63".repeat(43)), START + 1)?.code == CODE, "callback percent decoded exactly once")
    for (time in listOf(START - 1, START + 600_000, START + 600_001)) {
        val test = fresh(); begin(test)
        expect(test.receive(callback(), time) == null, "expired or reversed callback clock rejected")
        expect(test.receive(callback(), START + 1) == null, "expired pending state cleared")
    }
    val atBoundary = fresh(); begin(atBoundary)
    expect(atBoundary.receive(callback(), START + 599_999) != null, "callback just before TTL accepted")
    val failure = fresh(); begin(failure)
    expect(failure.receive("org.daynomy.app://auth/callback?error=oauth_failed&state=$STATE", START + 1) == null, "matched provider failure produces no exchange")
    expect(failure.receive(callback(), START + 2) == null, "matched provider failure consumes pending state")
    expect(begin(failure, time = START + 3) != null, "new auth possible after matched failure")
    val cancelled = fresh(); begin(cancelled); cancelled.cancel()
    expect(cancelled.receive(callback(), START + 1) == null, "cancel blocks callback")
    val cancelledExchange = fresh(); val pending = exchange(cancelledExchange); cancelledExchange.cancel()
    expect(cancelledExchange.complete(pending.requestId, 204, pending.exchangeURL, cookies(), START + 2) == null, "cancel blocks late network completion")
    val restarted = fresh(); val old = exchange(restarted); restarted.cancel(); val newer = exchange(restarted)
    expect(old.requestId != newer.requestId, "new handshake has a distinct exchange generation")
    expect(restarted.complete(old.requestId, 204, old.exchangeURL, cookies(), START + 2) == null, "cancelled generation cannot complete replacement")
    expect(restarted.complete(newer.requestId, 204, newer.exchangeURL, cookies(), START + 3) != null, "replacement still completes")

    for (url in listOf("https://evil.invalid/api/auth/mobile/exchange", "$ORIGIN/api/auth/mobile/exchange/", "$ORIGIN/api/auth/mobile/exchange?x=1", "$ORIGIN/api/auth/mobile/exchange#x", "$ORIGIN/api/auth/mobile/%65xchange", "$ORIGIN:444/api/auth/mobile/exchange")) {
        val test = fresh(); val e = exchange(test)
        expect(test.complete(e.requestId, 204, url, cookies(), START + 2) == null, "redirected or different response URL rejected")
    }
    for (status in listOf(200, 201, 302, 400, 401, 500)) {
        val test = fresh(); val e = exchange(test)
        expect(test.complete(e.requestId, status, e.exchangeURL, cookies(), START + 2) == null, "only exchange204 installs cookies")
    }
    val stale = fresh(); val current = exchange(stale)
    expect(stale.complete(current.requestId + "-stale", 204, current.exchangeURL, cookies(), START + 2) == null, "stale completion ID rejected")
    expect(stale.complete(current.requestId, 204, current.exchangeURL, cookies(), START + 3) != null, "stale response cannot consume current exchange")
    for (time in listOf(START, START + 60_001, START + 600_000)) {
        val test = fresh(); val e = exchange(test)
        expect(test.complete(e.requestId, 204, e.exchangeURL, cookies(), time) == null, "completion clock/lifetime boundary rejected")
    }
    val beforeExpiry = fresh(); val before = exchange(beforeExpiry)
    expect(beforeExpiry.complete(before.requestId, 204, before.exchangeURL, cookies(), START + 60_000) != null, "completion just before exchangeTTL accepted")
    val overall = fresh(); begin(overall); val late = checkNotNull(overall.receive(callback(), START + 599_999))
    expect(overall.complete(late.requestId, 204, late.exchangeURL, cookies(), START + 600_000) == null, "overall auth TTL also limits exchange")

    val valid = cookies()
    val badCookieSets = listOf(
        emptyList(), listOf(valid[0]), listOf(valid[1]), valid + valid[0], valid.reversed() + "other=x; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=10",
        listOf(valid[0].replace("HttpOnly; ", ""), valid[1]), listOf(valid[0], valid[1].replace("; Secure", "")),
        listOf(valid[0].replace("Path=/;", "Path=/api/auth;"), valid[1]), listOf(valid[0], valid[1].replace("Path=/api/auth;", "Path=/;")),
        listOf(valid[0].replace("SameSite=Lax", "SameSite=None"), valid[1]), listOf(valid[0].replace("Max-Age=1800", "Max-Age=0"), valid[1]),
        listOf(valid[0].replace("Max-Age=1800", "Max-Age=-1"), valid[1]), listOf(valid[0].replace("Max-Age=1800", "Max-Age=oops"), valid[1]),
        listOf(valid[0] + "; Domain=evil.invalid", valid[1]), listOf(valid[0] + "; Domain=example.invalid", valid[1]), listOf(valid[0] + "; Domain=sub.app.example.invalid", valid[1]),
        listOf(valid[0] + "; Path=/", valid[1]), listOf(valid[0] + "; HttpOnly", valid[1]), listOf(valid[0] + "; Secure", valid[1]),
        listOf(valid[0] + "\r\nX-Leak: fixture", valid[1]), listOf(valid[0].replace("fixture.access", "a,b"), valid[1]),
        listOf(valid[0].replace("fixture.access", ""), valid[1]), listOf(valid[0] + ", " + valid[1])
    )
    for (headers in badCookieSets) {
        val test = fresh(); val e = exchange(test)
        expect(test.complete(e.requestId, 204, e.exchangeURL, headers, START + 2) == null, "invalid cookie set never partially installs")
    }
    val exactDomain = fresh(); val d = exchange(exactDomain)
    expect(exactDomain.complete(d.requestId, 204, d.exchangeURL, valid.map { "$it; Domain=app.example.invalid" }, START + 2) != null, "exact host domain accepted")
    val case = fresh(); val c = exchange(case)
    expect(case.complete(c.requestId, 204, c.exchangeURL, valid.map { it.replace("HttpOnly", "httponly").replace("SameSite=Lax", "samesite=lax").replace("Path=", "path=").replace("Max-Age=", "max-age=").replace("Secure", "secure") }, START + 2) != null, "cookie attribute names case insensitive")
    val debug = fresh("http://127.0.0.1:18082", true)
    expect(begin(debug, "http://127.0.0.1:18082/api/auth/google", "http://127.0.0.1:18082/login") != null, "debug setup")
    val de = checkNotNull(debug.receive(callback(), START + 1))
    expect(debug.complete(de.requestId, 204, de.exchangeURL, cookies(false), START + 2) != null, "debug local cookie may omit Secure while retaining HttpOnly")
    println("NativeAuthSession Kotlin: $assertions assertions passed")
}
