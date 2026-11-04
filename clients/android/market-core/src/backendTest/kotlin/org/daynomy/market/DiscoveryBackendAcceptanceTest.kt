package org.daynomy.market

import java.math.BigDecimal
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/** Actual HTTP/Rust/disposable DB. Coordinator must seed android_backend_fixture.py --discovery. */
class DiscoveryBackendAcceptanceTest {
    private lateinit var news: NewsClient
    private lateinit var exchange: ExchangeRateClient
    @Before fun requireConfiguredBackend() {
        val url = System.getenv("ANDROID_PILOT_BASE_URL")
        require(!url.isNullOrBlank()) { "ANDROID_PILOT_BASE_URL with --discovery fixture is required; no skip or canned fallback" }
        val transport = OkHttpTransport(url)
        news = NewsClient(transport); exchange = ExchangeRateClient(transport)
    }

    @Test fun realPaginationPublicationFilteringAndTieBreakFollowOriginalContract() = runBlocking {
        val all = news.list()
        assertEquals(listOf(920002L, 920001L, 920003L), all.items.map { it.id })
        assertEquals(3L, all.totalElements); assertEquals(1, all.totalPages); assertFalse(all.hasNext)
        val first = news.list(NewsCategory.STOCK, 1, 1)
        val second = news.list(NewsCategory.STOCK, 2, 1)
        assertEquals(listOf(920002L), first.items.map { it.id }); assertTrue(first.hasNext)
        assertEquals(2L, first.totalElements); assertEquals(2, first.totalPages)
        assertEquals(listOf(920001L), second.items.map { it.id }); assertFalse(second.hasNext)
        val empty = news.list(NewsCategory.REAL_ESTATE)
        assertTrue(empty.items.isEmpty()); assertEquals(0L, empty.totalElements)
        assertEquals(400, backendFailure { news.list(page = 0) }.status)
    }

    @Test fun actualDetailPreservesContentAttributionAndHidesDraftRejectedMissingRows() = runBlocking {
        val detail = news.detail(920002)
        assertEquals("테스트 뉴스 920002", detail.title)
        assertEquals(listOf("첫 문단", "둘째 문단"), detail.content)
        assertEquals(NewsCategory.STOCK, detail.category)
        assertNull(detail.imageUrl)
        assertEquals(NewsImageSourceType.NONE, detail.imageSource?.type)
        assertEquals(listOf(NewsSourceLink("합성 출처", "https://example.invalid/source")), detail.sources)
        for (id in listOf(920004L, 920005L, 999999L)) {
            val failure = backendFailure { news.detail(id) }
            assertEquals(404, failure.status); assertEquals("NEWS_NOT_FOUND", failure.code)
        }
    }

    @Test fun storedExchangeFallbackUsesActualBaseDateAndDecimalAndServerRejectsInvalidDate() = runBlocking {
        val result = exchange.quote("2026-10-25")
        assertEquals("2026-10-23", result.baseDate)
        assertEquals(0, BigDecimal("1423.123456").compareTo(result.rate))
        for (date in listOf("1999-12-31", "2026-02-30")) assertEquals(400, backendFailure { exchange.quote(date) }.status)
    }

    private suspend fun backendFailure(action: suspend () -> Any): ApiException {
        val failure = try { action(); null } catch (failure: Throwable) { failure }
        assertTrue("Expected actual HTTP ApiException, got ${failure?.javaClass?.simpleName ?: "success"}", failure is ApiException)
        return failure as ApiException
    }
}
