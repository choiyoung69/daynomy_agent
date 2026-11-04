package org.daynomy.market

import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import okhttp3.mockwebserver.*
import org.junit.Assert.*
import org.junit.Test

/** Auth/session contract: authored before implementation; fixture tokens are synthetic. */
class Android30SessionContractTest {
    private fun json(body: String, status: Int = 200) = MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)
    private fun csrf() = json("""{"headerName":"X-XSRF-TOKEN","parameterName":"_csrf","token":"fixture-csrf"}""").addHeader("Set-Cookie", "XSRF-TOKEN=fixture-csrf; Path=/; SameSite=Lax")

    @Test fun writesAcquireCsrfCookieAndMatchingHeaderBeforeSendingBody() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(csrf()); server.enqueue(json("""{"id":1}""")); server.start()
            val transport = SessionHttpTransport(server.url("/").toString())
            transport.request("PATCH", "/api/users/me", """{"nickname":"새이름"}""")
            assertEquals("/api/auth/csrf", server.takeRequest().path)
            val write = server.takeRequest(); assertEquals("PATCH", write.method)
            assertEquals("fixture-csrf", write.getHeader("X-XSRF-TOKEN"))
            assertTrue(write.getHeader("Cookie").orEmpty().contains("XSRF-TOKEN=fixture-csrf"))
            assertEquals("새이름", kotlinx.serialization.json.Json.parseToJsonElement(write.body.readUtf8()).let { (it as kotlinx.serialization.json.JsonObject)["nickname"].toString().trim('"') })
        }
    }

    @Test fun exchangeIsCsrfExemptAndRefreshCookieStaysOnAuthPath() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(204).addHeader("Set-Cookie", "access_token=access; Path=/; HttpOnly").addHeader("Set-Cookie", "refresh_token=refresh; Path=/api/auth; HttpOnly"))
            server.enqueue(json("{}")); server.enqueue(csrf()); server.enqueue(MockResponse().setResponseCode(204)); server.start()
            val transport = SessionHttpTransport(server.url("/").toString())
            transport.request("POST", "/api/auth/mobile/exchange", """{"code":"synthetic","codeVerifier":"synthetic"}""")
            transport.get("/api/users/me"); transport.request("POST", "/api/auth/logout")
            assertEquals("/api/auth/mobile/exchange", server.takeRequest().path)
            val me = server.takeRequest(); assertTrue(me.getHeader("Cookie").orEmpty().contains("access_token=access")); assertFalse(me.getHeader("Cookie").orEmpty().contains("refresh_token"))
            assertEquals("/api/auth/csrf", server.takeRequest().path)
            assertTrue(server.takeRequest().getHeader("Cookie").orEmpty().contains("refresh_token=refresh"))
        }
    }

    @Test fun concurrent401ShareOneRefreshAndEachReadRetriesOnlyOnce() = runBlocking {
        MockWebServer().use { server ->
            val requests = CopyOnWriteArrayList<RecordedRequest>(); val both = CountDownLatch(2)
            server.dispatcher = object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse {
                    requests += request
                    return when (request.path) {
                        "/api/auth/csrf" -> csrf()
                        "/api/auth/refresh" -> MockResponse().setResponseCode(204).addHeader("Set-Cookie", "access_token=fresh; Path=/")
                        else -> if (request.getHeader("Cookie").orEmpty().contains("access_token=fresh")) json("{}") else {
                            both.countDown(); check(both.await(3, TimeUnit.SECONDS)); json("""{"code":"INVALID_TOKEN"}""",401)
                        }
                    }
                }
            }; server.start(); val transport = SessionHttpTransport(server.url("/").toString())
            withContext(Dispatchers.Default) { listOf(async { transport.get("/api/users/me") }, async { transport.get("/api/portfolio") }).awaitAll() }
            assertEquals(1, requests.count { it.path == "/api/auth/refresh" })
            assertEquals(2, requests.count { it.path == "/api/users/me" }); assertEquals(2, requests.count { it.path == "/api/portfolio" })
        }
    }

    @Test fun clearingSessionWhileReadIsPendingDiscardsLateSetCookie() = runBlocking {
        MockWebServer().use { server ->
            val arrived = CountDownLatch(1); val release = CountDownLatch(1)
            server.dispatcher = object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse = if (request.path == "/api/late") {
                    arrived.countDown(); check(release.await(3, TimeUnit.SECONDS)); json("{}").addHeader("Set-Cookie", "access_token=late; Path=/")
                } else json("{}")
            }; server.start(); val transport = SessionHttpTransport(server.url("/").toString())
            val late = async(Dispatchers.Default) { runCatching { transport.get("/api/late") } }
            check(arrived.await(3, TimeUnit.SECONDS)); transport.clearSession(); release.countDown(); late.await()
            transport.get("/api/users/me"); server.takeRequest()
            assertFalse(server.takeRequest().getHeader("Cookie").orEmpty().contains("access_token=late"))
        }
    }

    @Test fun serverBusinessErrorsKeepStatusCodeAndNeverAutomaticallyReplayMutation() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(csrf()); server.enqueue(json("""{"code":"INSUFFICIENT_HOLDING_QUANTITY","message":"수량 부족"}""",400)); server.start()
            val transport = SessionHttpTransport(server.url("/").toString())
            val error = expectFailure<ApiException> { transport.request("POST", "/api/portfolio/transactions", "{}") }
            assertEquals(400,error.status); assertEquals("INSUFFICIENT_HOLDING_QUANTITY",error.code); assertEquals(2,server.requestCount)
        }
    }

    @Test fun lostMutationResponseIsNotAutomaticallyReplayed() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(csrf()); server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)); server.start()
            val transport = SessionHttpTransport(server.url("/").toString())
            expectFailure<java.io.IOException> { transport.request("POST", "/api/portfolio/transactions", "{}") }
            assertEquals(2,server.requestCount)
        }
    }

    @Test fun sessionTransportRejectsRemoteCleartextAndOriginEscape() = runBlocking {
        expectFailure<IllegalArgumentException> { SessionHttpTransport("http://example.com/") }
        MockWebServer().use { server -> server.start(); val transport = SessionHttpTransport(server.url("/").toString())
            for (path in listOf("//example.com/api/users/me", "https://example.com/api/users/me", "/api/../outside")) {
                expectFailure<IllegalArgumentException> { transport.get(path) }
            }; assertEquals(0,server.requestCount)
        }
    }
}
