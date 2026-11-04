package org.daynomy.market

import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.Call
import okhttp3.EventListener
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.*

/** Real loopback sockets, not a mocked transport or interceptor. No Rust/DB claim. */
class OkHttpTransportContractTest {
    private lateinit var server: MockWebServer
    private val clients = mutableListOf<OkHttpClient>()
    @Before fun startServer() { server = MockWebServer(); server.start() }
    @After fun stopServer() {
        server.shutdown()
        clients.forEach { it.connectionPool.evictAll(); it.dispatcher.executorService.shutdownNow() }
    }
    private fun client(listener: EventListener = EventListener.NONE): OkHttpClient =
        OkHttpClient.Builder().retryOnConnectionFailure(false).readTimeout(3, TimeUnit.SECONDS)
            .eventListener(listener).build().also { clients += it }
    private fun transport(client: OkHttpClient = client()) = OkHttpTransport(server.url("/").toString(), client)

    @Test fun realGetPreservesPathUtf8QueryAndResponseBodyWithoutAuthentication() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody("{\"stocks\":[]}"))
        val body = transport().get("/api/stocks?q=%EC%82%BC%EC%84%B1%20%26%20ETF&country=US")
        val request = server.takeRequest(3, TimeUnit.SECONDS)!!
        assertEquals("GET", request.method)
        assertEquals("/api/stocks", request.requestUrl!!.encodedPath)
        assertEquals("삼성 & ETF", request.requestUrl!!.queryParameter("q"))
        assertEquals("US", request.requestUrl!!.queryParameter("country"))
        assertEquals(0L, request.bodySize)
        assertNull(request.getHeader("Authorization"))
        assertNull(request.getHeader("Cookie"))
        assertEquals("{\"stocks\":[]}", body)
        assertEquals(1, server.requestCount)
    }
    @Test fun business404RetainsStatusAndStringCode() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(404).setBody("""{"code":"STOCK_PRICE_NOT_FOUND","message":"주식·ETF 종가를 찾을 수 없습니다."}"""))
        val failure = expectFailure<ApiException> { transport().get("/api/stocks/1/price") }
        assertEquals(404, failure.status)
        assertEquals("STOCK_PRICE_NOT_FOUND", failure.code)
        assertEquals(1, server.requestCount)
    }
    @Test fun malformedHtmlEmptyAndNonStringErrorBodiesRemainHttpFailures() = runBlocking {
        val http = transport()
        for (body in listOf("<html>Bad gateway</html>", "", "null", "[]", "{", "{\"code\":123,\"message\":true}")) {
            server.enqueue(MockResponse().setResponseCode(500).setBody(body))
            val failure = expectFailure<ApiException> { http.get("/api/stocks?q=A") }
            assertEquals(500, failure.status)
            assertNull(failure.code)
        }
        assertEquals(6, server.requestCount)
    }
    @Test fun successfulInvalidJsonAnd204ReachDecoderAndBecomeFormatFailures() = runBlocking {
        val api = StockSearchClient(transport())
        server.enqueue(MockResponse().setResponseCode(200).setBody("bad-json"))
        expectFailure<ResponseFormatException> { api.search("x", Country.KR) }
        server.enqueue(MockResponse().setResponseCode(204))
        expectFailure<ResponseFormatException> { api.search("x", Country.KR) }
        assertEquals(2, server.requestCount)
    }
    @Test fun socketFailureRemainsIOExceptionAndDoesNotBecomeEmptySuccess() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))
        expectFailure<IOException> { transport().get("/api/stocks?q=x") }
        Unit
    }
    @Test fun coroutineCancellationCancelsUnderlyingOkHttpCall() = runBlocking {
        val cancelled = CountDownLatch(1)
        val http = transport(client(object : EventListener() {
            override fun canceled(call: Call) { cancelled.countDown() }
        }))
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val request = async(start = CoroutineStart.UNDISPATCHED) { http.get("/api/stocks?q=slow") }
        assertNotNull("The request must actually reach the socket", server.takeRequest(3, TimeUnit.SECONDS))
        withTimeout(3000) { request.cancelAndJoin() }
        assertTrue(request.isCancelled)
        assertTrue("Coroutine cancellation must call Call.cancel", cancelled.await(2, TimeUnit.SECONDS))
        assertEquals(1, server.requestCount)
    }
    @Test fun bothApiClientsUseActualHttpAdapter() = runBlocking {
        server.enqueue(MockResponse().setBody("{\"stocks\":[$SEARCH_ROW]}"))
        server.enqueue(MockResponse().setBody(PRICE_ROW))
        val http = transport()
        val stock = StockSearchClient(http).search("삼성", Country.KR).single()
        val quote = StockPriceClient(http).latest(stock.assetId)
        assertEquals("71000.1250", quote.closePrice.toPlainString())
        assertEquals("2026-10-23", quote.baseDate)
        assertEquals("/api/stocks", server.takeRequest(3, TimeUnit.SECONDS)!!.requestUrl!!.encodedPath)
        assertEquals("/api/stocks/1/price", server.takeRequest(3, TimeUnit.SECONDS)!!.path)
    }
}
