package org.daynomy.market

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/** Additive review regression: authored after implementation, before the query-reset fix. */
@OptIn(ExperimentalCoroutinesApi::class)
class MarketControllerRegressionTest {
    @Test fun changingStockRetainsSearchTextAndReissuesSearchWhileResettingOnlyPriceDraft() = runTest {
        val calls = mutableListOf<Pair<String, Country>>()
        val search = object : StockSearchSource {
            override suspend fun search(keyword: String, country: Country): List<Stock> {
                calls += keyword to country
                return listOf(stock())
            }
        }
        val prices = object : StockPriceSource {
            override suspend fun latest(assetId: Long): StockPrice = price(assetId)
        }
        val controller = MarketController(search, prices, this)
        try {
            controller.updateQuery("  삼성  ")
            runCurrent(); advanceTimeBy(250); runCurrent()
            assertEquals(listOf("삼성" to Country.KR), calls)
            controller.select(stock()); runCurrent()
            controller.editUnitPrice("77.0000")
            controller.clearSelection(); runCurrent()
            assertEquals("Original change-stock action preserves entered search text", "  삼성  ", controller.state.value.query)
            assertNull(controller.state.value.selected)
            assertEquals("", controller.state.value.unitPrice)
            assertFalse(controller.state.value.priceEdited)
            assertEquals(LoadState.Idle, controller.state.value.price)
            assertEquals(LoadState.Loading, controller.state.value.search)
            advanceTimeBy(249); runCurrent(); assertEquals(1, calls.size)
            advanceTimeBy(1); runCurrent()
            assertEquals(listOf("삼성" to Country.KR, "삼성" to Country.KR), calls)
            assertEquals(LoadState.Ready(listOf(stock())), controller.state.value.search)
        } finally { controller.close() }
    }

    @Test fun searchRejectsBigDecimalTokensThatAreNotJsonNumbers() = runTest {
        for (token in listOf("+1", "01", "1.", ".1", "1e+")) {
            val row = SEARCH_ROW.replace("\"assetId\":1", "\"assetId\":$token")
            expectFailure<ResponseFormatException> {
                StockSearchClient(RecordingTransport("{\"stocks\":[$row]}")).search("x", Country.KR)
            }
        }
    }

    @Test fun priceRejectsNonJsonNumericGrammarInBothIdAndPrice() = runTest {
        for (token in listOf("+1", "01", "1.", ".1", "1e+")) {
            for (body in listOf(PRICE_ROW.replace("\"assetId\":1", "\"assetId\":$token"), PRICE_ROW.replace("71000.1250", token))) {
                expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(body)).latest(1) }
            }
        }
    }
}
