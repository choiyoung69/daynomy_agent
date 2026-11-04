package com.daynomy.webview

import java.net.URI
import java.net.URLDecoder
import java.security.MessageDigest
import java.util.Base64
import java.util.Locale

data class AuthLaunch(val authorizationURL: String) {
    override fun toString() = "AuthLaunch(redacted)"
}
data class AuthExchange(val exchangeURL: String, val code: String, val codeVerifier: String, val requestId: String) {
    override fun toString() = "AuthExchange(redacted)"
}
data class AuthCookiePlan(val originURL: String, val reloadURL: String, val setCookieHeaders: List<String>) {
    override fun toString() = "AuthCookiePlan(redacted)"
}

/** Pure policy; secrets exist only for one pending native handshake, never in JS/storage. */
class NativeAuthSession(trustedOrigin: String, private val debug: Boolean) {
    private data class Origin(val scheme: String, val host: String, val port: Int)
    private data class Pending(val state: String, val verifier: String, val began: Long, val id: String,
                               val received: Long? = null)
    private val configured = parse(trustedOrigin)?.takeIf {
        it.rawPath.isNullOrEmpty() && it.rawQuery == null && it.rawFragment == null
    }?.let { uri -> origin(uri)?.takeIf { it.scheme == "https" || (debug && it.scheme == "http" && it.host in LOCAL) } }
    private val originURL = trustedOrigin
    private var pending: Pending? = null
    private var generation = 0L
    val isPending: Boolean get() = pending != null

    fun begin(navigationURL: String, sourceDocumentURL: String, httpMethod: String, isMainFrame: Boolean,
              userActivated: Boolean, state: String, verifier: String, nowMillis: Long): AuthLaunch? {
        if (configured == null || pending != null || nowMillis < 0 || !isMainFrame || !userActivated || httpMethod != "GET" ||
            !exact(navigationURL, "/api/auth/google") || parse(sourceDocumentURL)?.let { origin(it) } != configured ||
            !safe(state, 32, 128) || verifier.length !in 43..128 || !verifier.all { it in UNRESERVED }) return null
        generation += 1
        pending = Pending(state, verifier, nowMillis, generation.toString())
        val challenge = Base64.getUrlEncoder().withoutPadding().encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)))
        return AuthLaunch("$originURL/api/auth/mobile/start?code_challenge=$challenge&state=$state&code_challenge_method=S256")
    }

    fun receive(callbackURL: String, nowMillis: Long): AuthExchange? {
        val current = pending ?: return null
        if (!alive(current, nowMillis)) { cancel(); return null }
        if (current.received != null) return null
        val uri = parse(callbackURL) ?: return null
        if (uri.scheme != "org.daynomy.app" || uri.host != "auth" || uri.rawAuthority != "auth" ||
            uri.rawPath != "/callback" || uri.rawFragment != null) return null
        val query = decodeQuery(uri.rawQuery ?: return null) ?: return null
        if (query.size != 2 || !constantEqual(query["state"] ?: return null, current.state)) return null
        if (query.keys == setOf("error", "state") && query["error"] == "oauth_failed") { cancel(); return null }
        if (query.keys != setOf("code", "state")) return null
        val code = query["code"]?.takeIf { safe(it, 32, 128) } ?: return null
        pending = current.copy(received = nowMillis)
        return AuthExchange("$originURL/api/auth/mobile/exchange", code, current.verifier, current.id)
    }

    fun complete(requestId: String, status: Int, responseURL: String, setCookieHeaders: List<String>, nowMillis: Long): AuthCookiePlan? {
        val current = pending ?: return null
        val received = current.received ?: return null
        if (requestId != current.id) return null
        pending = null
        if (!alive(current, nowMillis) || nowMillis < received || nowMillis - received >= 60_000 || status != 204 ||
            !exact(responseURL, "/api/auth/mobile/exchange") || !cookiesValid(setCookieHeaders)) return null
        return AuthCookiePlan(originURL, "$originURL/", setCookieHeaders.toList())
    }
    fun cancel() { pending = null }

    private fun alive(current: Pending, time: Long) = time >= current.began && time - current.began < 600_000
    private fun exact(text: String, path: String): Boolean = parse(text)?.let {
        origin(it) == configured && it.rawPath == path && it.rawQuery == null && it.rawFragment == null
    } == true
    private fun cookiesValid(headers: List<String>): Boolean {
        if (headers.size != 2 || configured == null) return false
        val names = mutableSetOf<String>()
        return headers.all { header ->
            if (header.isEmpty() || header.length > 16_384 || header.any { it.code < 32 || it.code == 127 }) return@all false
            val parts = header.split(';').map { it.trim() }
            val initial = parts.first().split('=', limit = 2)
            if (initial.size != 2 || initial[0] !in setOf("access_token", "refresh_token") || !names.add(initial[0]) ||
                initial[1].isEmpty() || !initial[1].all { c -> c.code == 0x21 || c.code in 0x23..0x2B || c.code in 0x2D..0x3A || c.code in 0x3C..0x5B || c.code in 0x5D..0x7E }) return@all false
            val attributes = mutableMapOf<String, String?>()
            for (part in parts.drop(1)) {
                val pair = part.split('=', limit = 2)
                val name = pair[0].lowercase(Locale.ROOT)
                if (name !in setOf("path", "max-age", "httponly", "samesite", "secure", "domain") || attributes.containsKey(name)) return@all false
                attributes[name] = pair.getOrNull(1)
            }
            val path = if (initial[0] == "access_token") "/" else "/api/auth"
            val age = attributes["max-age"]
            attributes["path"] == path && attributes.containsKey("httponly") && attributes["httponly"] == null &&
                attributes["samesite"]?.lowercase(Locale.ROOT) == "lax" && age != null && age.all { it in '0'..'9' } && (age.toLongOrNull() ?: 0) > 0 &&
                (!attributes.containsKey("secure") || attributes["secure"] == null) &&
                ((debug && configured.scheme == "http") || attributes.containsKey("secure")) &&
                (!attributes.containsKey("domain") || attributes["domain"]?.lowercase(Locale.ROOT) == configured.host)
        } && names == setOf("access_token", "refresh_token")
    }
    private fun decodeQuery(raw: String): Map<String, String>? { return try {
        val result = mutableMapOf<String, String>()
        for (part in raw.split('&')) {
            val pair = part.split('=', limit = 2)
            if (pair.size != 2) return null
            val key = URLDecoder.decode(pair[0], "UTF-8")
            val value = URLDecoder.decode(pair[1], "UTF-8")
            if (key !in setOf("state", "code", "error") || result.put(key, value) != null) return null
        }
        result
    } catch (_: Exception) { null } }
    private fun constantEqual(a: String, b: String): Boolean = MessageDigest.isEqual(a.toByteArray(Charsets.UTF_8), b.toByteArray(Charsets.UTF_8))
    private fun safe(value: String, min: Int, max: Int) = value.length in min..max && value.all { it in URLSAFE }
    private fun parse(text: String): URI? {
        if (text.isEmpty() || text.any { it <= ' ' || it == '\\' || it == '\u007f' }) return null
        return runCatching { URI(text).takeIf { it.isAbsolute && !it.isOpaque && it.rawUserInfo == null && it.rawAuthority?.contains('%') != true && it.rawAuthority?.contains('@') != true } }.getOrNull()
    }
    private fun origin(uri: URI): Origin? {
        val scheme = uri.scheme?.lowercase(Locale.ROOT) ?: return null
        if (scheme !in setOf("http", "https")) return null
        val host = uri.host?.lowercase(Locale.ROOT)?.removePrefix("[")?.removeSuffix("]") ?: return null
        val port = if (uri.port == -1) if (scheme == "https") 443 else 80 else uri.port
        if (host.isEmpty() || host.endsWith('.') || port !in 1..65535) return null
        return Origin(scheme, host, port)
    }
    companion object {
        private const val URLSAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        private const val UNRESERVED = URLSAFE + ".~"
        private val LOCAL = setOf("localhost", "127.0.0.1", "10.0.2.2", "::1")
    }
}
