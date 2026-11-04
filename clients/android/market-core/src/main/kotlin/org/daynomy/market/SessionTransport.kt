package org.daynomy.market

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.*
import okhttp3.*
import okio.BufferedSink
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/** Memory-only native session. Cookie matching uses OkHttp's RFC domain/path/Secure rules. */
class SessionHttpTransport(baseUrl: String, client: OkHttpClient = OkHttpClient()) : SessionTransport, AutoCloseable {
    private val base = checkedSessionOrigin(baseUrl)
    private val client = client.newBuilder().cookieJar(CookieJar.NO_COOKIES)
        .authenticator(Authenticator.NONE).proxyAuthenticator(Authenticator.NONE)
        .retryOnConnectionFailure(false).followRedirects(false).followSslRedirects(false)
        .callTimeout(15, TimeUnit.SECONDS).build()
    private val lock = Any()
    private val cookies = mutableListOf<Cookie>()
    private var epoch = 0L
    private var refreshVersion = 0L
    private var csrf: String? = null
    private val csrfMutex = Mutex()
    private val refreshMutex = Mutex()

    fun clearSession() = synchronized(lock) { epoch++; cookies.clear(); csrf = null; Unit }
    override fun close() { clearSession() }
    override suspend fun get(pathAndQuery: String): String = request("GET", pathAndQuery)

    override suspend fun request(method: String, path: String, jsonBody: String?): String {
        require(method in setOf("GET", "POST", "PATCH", "PUT", "DELETE")) { "Unsupported method" }
        checkedUrl(path)
        val initial = synchronized(lock) { epoch to refreshVersion }
        val write = method != "GET"
        val token = if (write && path != "/api/auth/mobile/exchange") ensureCsrf(initial.first) else null
        val ending = (method == "POST" && path == "/api/auth/logout") ||
            (method == "DELETE" && path == "/api/users/me")
        if (ending) {
            val saved = cookieHeader(checkedUrl(path))
            clearSession() // Pending responses must never restore this session, even if logout fails.
            return finish(send(method, path, jsonBody, token, initial.first, saved, true))
        }
        val response = send(method, path, jsonBody, token, initial.first)
        if (response.status != 401 || method != "GET" || path.startsWith("/api/auth/")) return finish(response)
        refreshMutex.withLock {
            requireCurrent(initial.first)
            val alreadyRefreshed = synchronized(lock) { refreshVersion != initial.second }
            if (!alreadyRefreshed) {
                try {
                    val csrfToken = ensureCsrf(initial.first)
                    finish(send("POST", "/api/auth/refresh", null, csrfToken, initial.first))
                    synchronized(lock) { if (epoch == initial.first) refreshVersion++ }
                } catch (failure: Exception) {
                    if (failure is kotlinx.coroutines.CancellationException) throw failure
                    clearSession()
                    throw failure
                }
            }
        }
        requireCurrent(initial.first)
        return finish(send(method, path, jsonBody, null, initial.first))
    }

    private suspend fun ensureCsrf(expected: Long): String = csrfMutex.withLock {
        requireCurrent(expected)
        synchronized(lock) {
            val cached = csrf
            if (cached != null && cookies.any { it.name == "XSRF-TOKEN" && it.value == cached && it.matches(base) && it.expiresAt > System.currentTimeMillis() }) cached
            else { csrf = null; null }
        }?.let { return@withLock it }
        val body = finish(send("GET", "/api/auth/csrf", null, null, expected))
        val row = try { Json.parseToJsonElement(body) as? JsonObject } catch (_: IllegalArgumentException) { null }
        val header = (row?.get("headerName") as? JsonPrimitive)?.takeIf { it.isString }?.content
        val token = (row?.get("token") as? JsonPrimitive)?.takeIf { it.isString }?.content
        if (header != "X-XSRF-TOKEN" || token.isNullOrEmpty()) throw ResponseFormatException("CSRF 응답 형식이 올바르지 않습니다.")
        synchronized(lock) {
            requireCurrent(expected)
            if (cookies.none { it.name == "XSRF-TOKEN" && it.value == token && it.matches(base) && it.expiresAt > System.currentTimeMillis() }) {
                throw ResponseFormatException("CSRF 쿠키가 없습니다.")
            }
            csrf = token
        }
        token
    }

    private fun requireCurrent(expected: Long) = synchronized(lock) {
        if (epoch != expected) throw ApiException(401, "SESSION_CHANGED", "세션이 변경되었습니다.")
    }
    private fun checkedUrl(path: String): HttpUrl {
        require(path.startsWith("/api/") && !path.contains('#') && !path.contains('\\')) { "Expected API path" }
        val url = requireNotNull(base.resolve(path))
        require(url.scheme == base.scheme && url.host == base.host && url.port == base.port && url.encodedPath.startsWith("/api/")) { "API origin escape" }
        require(path.substringBefore('?').split('/').none { it.equals("..", true) || it.equals("%2e%2e", true) || it.equals(".%2e", true) || it.equals("%2e.", true) }) { "API traversal" }
        return url
    }
    private fun cookieHeader(url: HttpUrl): String = synchronized(lock) {
        cookies.removeAll { it.expiresAt <= System.currentTimeMillis() }
        cookies.filter { it.matches(url) }.sortedByDescending { it.path.length }.joinToString("; ") { "${it.name}=${it.value}" }
    }
    private data class Reply(val status: Int, val body: String)
    private suspend fun send(method: String, path: String, body: String?, csrfToken: String?, expected: Long,
                             savedCookie: String? = null, allowStale: Boolean = false): Reply {
        val url = checkedUrl(path)
        if (!allowStale) requireCurrent(expected)
        val builder = Request.Builder().url(url).header("Accept", "application/json")
        val cookie = savedCookie ?: cookieHeader(url)
        if (cookie.isNotEmpty()) builder.header("Cookie", cookie)
        if (csrfToken != null) builder.header("X-XSRF-TOKEN", csrfToken)
        val requestBody = if (method == "GET") null else {
            val delegate = (body ?: "").toRequestBody("application/json; charset=utf-8".toMediaType())
            object : RequestBody() {
                override fun contentType() = delegate.contentType()
                override fun contentLength() = delegate.contentLength()
                override fun writeTo(sink: BufferedSink) = delegate.writeTo(sink)
                // OkHttp otherwise repeats HTTP 503 Retry-After:0 even when connection retries are off.
                override fun isOneShot() = true
            }
        }
        val call = client.newCall(builder.method(method, requestBody).build())
        return suspendCancellableCoroutine { continuation ->
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (continuation.isActive) continuation.resumeWithException(e)
                }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        response.use {
                            val reply = Reply(it.code, it.body?.string().orEmpty())
                            if (!continuation.isActive) return
                            synchronized(lock) {
                                if (epoch == expected) {
                                    for (cookie in Cookie.parseAll(url, it.headers)) {
                                        cookies.removeAll { old -> old.name == cookie.name && old.domain == cookie.domain && old.path == cookie.path }
                                        if (cookie.expiresAt > System.currentTimeMillis()) cookies.add(cookie)
                                    }
                                } else if (!allowStale) {
                                    throw ApiException(401, "SESSION_CHANGED", "세션이 변경되었습니다.")
                                }
                            }
                            if (continuation.isActive) continuation.resume(reply)
                        }
                    } catch (failure: Exception) {
                        if (continuation.isActive) continuation.resumeWithException(failure)
                    }
                }
            })
        }
    }
    private fun finish(reply: Reply): String {
        if (reply.status in 200..299) return reply.body
        val row = try { Json.parseToJsonElement(reply.body) as? JsonObject } catch (_: IllegalArgumentException) { null }
        fun text(key: String) = (row?.get(key) as? JsonPrimitive)?.takeIf { it.isString }?.content
        throw ApiException(reply.status, text("code"), text("message") ?: "HTTP ${reply.status}")
    }
}

internal fun checkedSessionOrigin(raw: String): HttpUrl = raw.toHttpUrl().also {
    require(it.username.isEmpty() && it.password.isEmpty() && it.encodedPath == "/" && it.query == null && it.fragment == null) { "Use API origin" }
    require(it.scheme == "https" || (it.scheme == "http" && it.host in setOf("localhost", "127.0.0.1", "::1", "10.0.2.2"))) { "HTTPS required" }
}
