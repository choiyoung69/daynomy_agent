package org.daynomy.market

import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import okhttp3.Call
import okhttp3.EventListener
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.Assert.*
import org.junit.Test

class TodayNewsClientContractTest {
    @Test fun preservesServerOrderDatesAndMetadataWithoutLocalFiltering() = runTest {
        val rows = listOf(todayRow(3, "2099-01-01T00:00:00Z"), todayRow(1, "1999-12-31T23:59:59Z"), todayRow(2))
        val transport = RecordingTransport(todayPage(rows.joinToString(",")))
        val result = NewsClient(transport).today()
        assertEquals(listOf("/api/news/today"), transport.paths)
        assertEquals(listOf(3L, 1L, 2L), result.items.map { it.id })
        assertEquals(listOf("2099-01-01T00:00:00Z", "1999-12-31T23:59:59Z", null), result.items.map { it.publishedAt })
        assertEquals("오늘 😀", result.items.first().title)
        assertNull(result.items.first().imageUrl)
        assertEquals(1, result.page); assertEquals(9, result.size)
        assertEquals(2, result.totalPages); assertEquals(12L, result.totalElements); assertTrue(result.hasNext)
    }

    @Test fun emptyTodayIsSuccessAndUnknownFieldsAreAllowed() = runTest {
        val body = """{"items":[],"page":1,"size":9,"totalPages":0,"totalElements":0,"hasNext":false,"future":{}}"""
        assertEquals(NewsPage(emptyList(), 1, 9, 0, 0, false), NewsClient(RecordingTransport(body)).today())
        val row = todayRow().dropLast(1) + ",\"future\":true}"
        assertEquals(1, NewsClient(RecordingTransport(todayPage(row))).today().items.size)
    }

    @Test fun rejectsMalformedEnvelopeAndEveryMissingOrNullMetadataField() = runTest {
        val valid = todayPage()
        val fields = listOf("\"items\":[${todayRow()}]", "\"page\":1", "\"size\":9", "\"totalPages\":2", "\"totalElements\":12", "\"hasNext\":true")
        val invalid = mutableListOf("", "{", "[]", "null", "{}")
        for (field in fields) {
            invalid += valid.replace(field, field.substringBefore(':') + ":null")
            invalid += valid.replace("$field,", "").replace(",$field", "")
        }
        invalid += valid.replace("\"items\":[${todayRow()}]", "\"items\":{}")
        invalid += valid.replace("\"page\":1", "\"page\":\"1\"")
        invalid += valid.replace("\"size\":9", "\"size\":9.5")
        invalid += valid.replace("\"totalPages\":2", "\"totalPages\":2147483648")
        invalid += valid.replace("\"totalElements\":12", "\"totalElements\":9223372036854775808")
        invalid += valid.replace("\"hasNext\":true", "\"hasNext\":\"true\"")
        for (body in invalid) expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(body)).today() }
    }

    @Test fun validatesEveryRowIncludingRequiredNullableFieldsAndExactSignedLongIds() = runTest {
        val row = todayRow()
        val invalid = listOf(
            row.replace("\"id\":2", "\"id\":\"2\""),
            row.replace("\"id\":2", "\"id\":2.5"),
            row.replace("\"id\":2", "\"id\":9223372036854775808"),
            row.replace("\"id\":2,", ""),
            row.replace("\"title\":\"오늘 😀\"", "\"title\":null"),
            row.replace("\"category\":\"STOCK\"", "\"category\":\"UNKNOWN\""),
            row.replace(",\"imageUrl\":null", ""),
            row.replace(",\"publishedAt\":null", ""),
            row.replace("\"imageUrl\":null", "\"imageUrl\":42"),
            row.replace("\"publishedAt\":null", "\"publishedAt\":false")
        )
        for (bad in invalid) expectFailure<ResponseFormatException> {
            NewsClient(RecordingTransport(todayPage("$row,$bad"))).today()
        }
        for (id in listOf(Long.MIN_VALUE, -1L, 0L, 9_007_199_254_740_992L, Long.MAX_VALUE)) {
            assertEquals(id, NewsClient(RecordingTransport(todayPage(todayRow(id)))).today().items.single().id)
        }
    }

    @Test fun httpTransportAndCancellationFailuresKeepIdentityAndDoNotRetry() = runTest {
        for (failure in listOf(ApiException(503, "UNAVAILABLE", "private"), IOException("offline"), CancellationException("cancelled"))) {
            val transport = RecordingTransport("not json").apply { this.failure = failure }
            assertSame(failure, expectFailure<Exception> { NewsClient(transport).today() })
            assertEquals(listOf("/api/news/today"), transport.paths)
        }
    }

    // Follows the existing OkHttpTransportContractTest loopback fixture.
    @Test fun actualGetHasNoQueryAndCancellationCancelsTheHttpCall() = runBlocking {
        val server = MockWebServer()
        val cancelled = CountDownLatch(1)
        val http = OkHttpClient.Builder().retryOnConnectionFailure(false)
            .eventListener(object : EventListener() {
                override fun canceled(call: Call) { cancelled.countDown() }
            }).build()
        server.start()
        try {
            val api = NewsClient(OkHttpTransport(server.url("/").toString(), http))
            server.enqueue(MockResponse().setBody(todayPage()))
            api.today()
            val first = server.takeRequest(3, TimeUnit.SECONDS)!!
            assertEquals("GET", first.method); assertEquals("/api/news/today", first.path)
            assertNull(first.requestUrl!!.query); assertEquals(0L, first.bodySize)
            server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
            val pending = async(start = CoroutineStart.UNDISPATCHED) { api.today() }
            assertEquals("/api/news/today", server.takeRequest(3, TimeUnit.SECONDS)!!.path)
            withTimeout(3000) { pending.cancelAndJoin() }
            assertTrue(pending.isCancelled); assertTrue(cancelled.await(2, TimeUnit.SECONDS))
            assertEquals(2, server.requestCount)
        } finally {
            server.shutdown()
            http.connectionPool.evictAll(); http.dispatcher.executorService.shutdownNow()
        }
    }
}

private fun todayRow(id: Long = 2, date: String? = null): String {
    val published = date?.let { "\"$it\"" } ?: "null"
    return """{"id":$id,"title":"오늘 😀","category":"STOCK","imageUrl":null,"publishedAt":$published}"""
}
private fun todayPage(items: String = todayRow()) =
    """{"items":[$items],"page":1,"size":9,"totalPages":2,"totalElements":12,"hasNext":true}"""
