package org.daynomy.market

import java.math.BigDecimal
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * Actual Kotlin -> OkHttp -> Rust -> isolated PostgreSQL acceptance.
 * Authored AFTER the initial feature implementations; this is not part of the
 * original 49 test-first criteria. The coordinator owns server/DB lifecycle.
 * The required environment variable must address the seeded pilot server.
 * Missing configuration fails setup rather than skipping or using canned data.
 */
class RustBackendAcceptanceTest {
    private lateinit var search: StockSearchClient
    private lateinit var prices: StockPriceClient

    @Before fun requireConfiguredBackend() {
        val baseUrl = System.getenv("ANDROID_PILOT_BASE_URL")
        require(!baseUrl.isNullOrBlank()) { "ANDROID_PILOT_BASE_URL is required for actual Rust/DB acceptance; no default or skip" }
        val transport = OkHttpTransport(baseUrl)
        search = StockSearchClient(transport)
        prices = StockPriceClient(transport)
    }

    @Test fun koreanSearchSelectsListedStockAndLoadsLatestStoredDecimalQuote() = runBlocking {
        val found = search.search("삼성", Country.KR)
        assertEquals("Delisted matching stock must not appear", listOf(910001L), found.map { it.assetId })
        val selected = found.single()
        assertEquals("005930", selected.assetCode)
        assertEquals("삼성전자", selected.name)
        assertEquals(Category.STOCK, selected.category)
        assertEquals(Market.KOSPI, selected.market)
        assertEquals(Currency.KRW, selected.currency)
        val quote = prices.latest(selected.assetId)
        assertEquals(selected.assetId, quote.assetId)
        assertEquals(selected.assetCode, quote.assetCode)
        assertEquals(selected.name, quote.name)
        assertEquals("2026-10-23", quote.baseDate)
        assertEquals("Latest base_date, not older price or binary-rounded decimal", 0, BigDecimal("71000.1250").compareTo(quote.closePrice))
        assertEquals(Currency.KRW, quote.currency)
    }

    @Test fun countryQuerySeparatesUsStockAndPreservesUsdQuote() = runBlocking {
        assertTrue(search.search("AAPL", Country.KR).isEmpty())
        val selected = search.search("AAPL", Country.US).single()
        assertEquals(910002L, selected.assetId)
        assertEquals("AAPL.US", selected.assetCode)
        assertEquals("Apple", selected.name)
        assertEquals(Market.NASDAQ, selected.market)
        assertEquals(Currency.USD, selected.currency)
        val quote = prices.latest(selected.assetId)
        assertEquals("2026-10-22", quote.baseDate)
        assertEquals(0, BigDecimal("193.4000").compareTo(quote.closePrice))
        assertEquals(Currency.USD, quote.currency)
    }

    @Test fun listedEtfIsIncludedByRealSearch() = runBlocking {
        val result = search.search("KODEX", Country.KR)
        assertEquals(listOf(910004L), result.map { it.assetId })
        assertEquals(Category.ETF, result.single().category)
        assertEquals(Market.KOSPI, result.single().market)
        assertEquals(Currency.KRW, result.single().currency)
    }

    @Test fun knownStockWithoutPriceReturnsBusiness404ThroughActualAdapter() = runBlocking {
        val selected = search.search("NOPRICE", Country.KR).single()
        assertEquals(910003L, selected.assetId)
        val failure = apiFailure { prices.latest(selected.assetId) }
        assertEquals(404, failure.status)
        assertEquals("STOCK_PRICE_NOT_FOUND", failure.code)
    }

    @Test fun realSearchEnforcesTwentyRowLimitWithoutDelistedResults() = runBlocking {
        val result = search.search("LIMIT", Country.KR)
        assertEquals(20, result.size)
        assertEquals(20, result.map { it.assetId }.distinct().size)
        assertEquals((0..19).map { "LIMIT${it.toString().padStart(2, '0')}" }, result.map { it.assetCode })
        assertTrue(result.all { it.category == Category.STOCK && it.market == Market.KOSPI && it.currency == Currency.KRW })
        assertTrue(search.search("숨김", Country.KR).isEmpty())
    }

    @Test fun noMatchingRowsIsAnEmptySuccessFromRealBackend() = runBlocking {
        assertEquals(emptyList<Stock>(), search.search("NO_MATCH_ANDROID_PILOT_8bf47d", Country.KR))
    }

    @Test fun invalidQueryIsServer400NotEmptySuccessOrClientFormatFailure() = runBlocking {
        for (query in listOf("", "%%%")) {
            val failure = apiFailure { search.search(query, Country.KR) }
            assertEquals(400, failure.status)
            assertEquals("INVALID_REQUEST", failure.code)
        }
    }

    private suspend fun apiFailure(action: suspend () -> Any): ApiException {
        val caught = try { action(); null } catch (failure: Throwable) { failure }
        assertTrue("Expected HTTP ApiException, got ${caught?.javaClass?.simpleName ?: "success"}", caught is ApiException)
        return caught as ApiException
    }
}
