package org.daynomy.market

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

class OkHttpTransport(
    baseUrl: String,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(15, TimeUnit.SECONDS).retryOnConnectionFailure(false).followRedirects(false).build(),
) : HttpTransport {
    private val base = baseUrl.toHttpUrl().also {
        require(it.username.isEmpty() && it.password.isEmpty()) { "API URL must not contain credentials" }
        require(it.encodedPath == "/" && it.query == null && it.fragment == null) { "Use an API origin URL" }
    }

    override suspend fun get(pathAndQuery: String): String {
        require(pathAndQuery.startsWith("/api/") && !pathAndQuery.contains('#')) { "Expected an API path" }
        val url = requireNotNull(base.resolve(pathAndQuery))
        val call = client.newCall(Request.Builder().url(url).header("Accept", "application/json").get().build())
        return suspendCancellableCoroutine { continuation ->
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (continuation.isActive) continuation.resumeWithException(e)
                }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        response.use {
                            val body = it.body?.string().orEmpty()
                            if (!continuation.isActive) return
                            if (it.isSuccessful) continuation.resume(body)
                            else continuation.resumeWithException(httpFailure(it.code, body))
                        }
                    } catch (failure: IOException) {
                        if (continuation.isActive) continuation.resumeWithException(failure)
                    }
                }
            })
        }
    }

    private fun httpFailure(status: Int, body: String): ApiException {
        val error = try { Json.parseToJsonElement(body) as? JsonObject } catch (_: IllegalArgumentException) { null }
        fun string(key: String): String? = (error?.get(key) as? JsonPrimitive)?.takeIf { it.isString }?.content
        return ApiException(status, string("code"), string("message") ?: "HTTP $status")
    }
}
