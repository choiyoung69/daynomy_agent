package com.daynomy.webview

import java.net.URI
import java.util.Locale

enum class NavigationDecision { INTERNAL, EXTERNAL, BLOCK }

/** Pure URL trust boundary: no Android classes or string-prefix origin comparisons. */
class NavigationPolicy(trustedOrigin: String, debug: Boolean) {
    private data class Origin(val scheme: String, val host: String, val port: Int)
    private val trusted: Origin
    init {
        val uri = parse(trustedOrigin)
        require(uri != null && (uri.rawPath.isNullOrEmpty() || uri.rawPath == "/") && uri.rawQuery == null && uri.rawFragment == null) { "Configure one origin without a path" }
        trusted = origin(uri) ?: throw IllegalArgumentException("Invalid trusted origin")
        require(trusted.scheme == "https" || (debug && trusted.scheme == "http" && trusted.host in LOCAL_HOSTS)) { "HTTPS is required outside local debug" }
    }
    fun decide(url: String, userActivated: Boolean): NavigationDecision {
        val uri = parse(url) ?: return NavigationDecision.BLOCK
        val candidate = origin(uri) ?: return NavigationDecision.BLOCK
        if (candidate == trusted) return NavigationDecision.INTERNAL
        return if (candidate.scheme == "https" && userActivated) NavigationDecision.EXTERNAL else NavigationDecision.BLOCK
    }
    private fun origin(uri: URI): Origin? {
        val scheme = uri.scheme?.lowercase(Locale.ROOT) ?: return null
        if (scheme != "https" && scheme != "http") return null
        val host = uri.host?.lowercase(Locale.ROOT)?.removePrefix("[")?.removeSuffix("]") ?: return null
        if (host.isEmpty() || uri.rawUserInfo != null || uri.rawAuthority?.contains('@') == true || host.endsWith('.')) return null
        val port = if (uri.port == -1) { if (scheme == "https") 443 else 80 } else uri.port
        if (port !in 1..65535) return null
        return Origin(scheme, host, port)
    }
    private fun parse(url: String): URI? {
        if (url.isEmpty() || url.any { it <= ' ' || it == '\\' || it == '\u007f' }) return null
        return try { URI(url).takeIf { it.isAbsolute && !it.isOpaque } } catch (_: Exception) { null }
    }
    companion object { private val LOCAL_HOSTS = setOf("localhost", "127.0.0.1", "10.0.2.2", "::1") }
}
