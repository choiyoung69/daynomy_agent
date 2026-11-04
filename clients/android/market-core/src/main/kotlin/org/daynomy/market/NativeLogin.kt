package org.daynomy.market

import java.net.URI
import java.net.URLDecoder
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** External browser PKCE bridge. Secrets exist only in this object's memory. */
class NativeLogin(private val transport: SessionTransport, baseUrl: String) {
    private val base = checkedSessionOrigin(baseUrl)
    private data class Pending(val state: String, val verifier: String)
    private var pending: Pending? = null
    private val random = SecureRandom()
    @Synchronized fun begin(): String {
        fun secret(): String = Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(32).also(random::nextBytes))
        val value = Pending(secret(), secret())
        pending = value
        val challenge = Base64.getUrlEncoder().withoutPadding().encodeToString(
            MessageDigest.getInstance("SHA-256").digest(value.verifier.toByteArray(Charsets.US_ASCII)))
        return base.newBuilder().encodedPath("/api/auth/mobile/start")
            .addQueryParameter("code_challenge", challenge).addQueryParameter("state", value.state).build().toString()
    }
    @Synchronized fun cancel() { pending = null }
    suspend fun complete(callbackUrl: String) {
        val uri = try { URI(callbackUrl) } catch (_: Exception) { throw IllegalArgumentException("잘못된 로그인 콜백입니다.") }
        require(uri.scheme == "org.daynomy.app" && uri.rawAuthority == "auth" && uri.rawPath == "/callback" && uri.rawFragment == null) { "잘못된 로그인 콜백입니다." }
        val params = mutableMapOf<String, String>()
        for (pair in (uri.rawQuery ?: "").split('&')) {
            val parts = pair.split('=', limit = 2)
            require(parts.size == 2) { "잘못된 로그인 콜백입니다." }
            val key = URLDecoder.decode(parts[0], "UTF-8")
            val value = URLDecoder.decode(parts[1], "UTF-8")
            require(params.put(key, value) == null) { "중복 로그인 파라미터입니다." }
        }
        val saved = synchronized(this) {
            val value = requireNotNull(pending) { "진행 중인 로그인이 없습니다." }
            require(MessageDigest.isEqual(value.state.toByteArray(Charsets.US_ASCII), params["state"].orEmpty().toByteArray(Charsets.US_ASCII))) { "로그인 상태가 일치하지 않습니다." }
            val code = params["code"]
            require((!code.isNullOrBlank() && params["error"] == null) || (!params["error"].isNullOrBlank() && code == null)) { "로그인 결과가 올바르지 않습니다." }
            pending = null // Every matching result is consumed before any network exchange.
            value
        }
        if (params["error"] != null) throw ApiException(401, "OAUTH_FAILED", "로그인을 완료하지 못했습니다.")
        val body = buildJsonObject { put("code", params.getValue("code")); put("codeVerifier", saved.verifier) }
        transport.request("POST", "/api/auth/mobile/exchange", body.toString())
    }
}
