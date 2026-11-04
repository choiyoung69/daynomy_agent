package org.daynomy.market

import kotlin.coroutines.Continuation
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.advanceTimeBy
import org.junit.Assert.*
import org.junit.Test

/** This fake intentionally ignores Job cancellation, to expose missing generation guards. */
private class Pending<T>(val job: Job, private val continuation: Continuation<T>) {
    fun succeed(value: T) = continuation.resume(value)
    fun fail(failure: Throwable) = continuation.resumeWithException(failure)
}
private class ControlledSources : StockSearchSource, StockPriceSource {
    data class SearchCall(val query: String, val country: Country, val pending: Pending<List<Stock>>)
    data class PriceCall(val id: Long, val pending: Pending<StockPrice>)
    val searches = mutableListOf<SearchCall>()
    val prices = mutableListOf<PriceCall>()
    override suspend fun search(keyword: String, country: Country): List<Stock> {
        val job = currentCoroutineContext()[Job]!!
        return suspendCoroutine { searches += SearchCall(keyword, country, Pending(job, it)) }
    }
    override suspend fun latest(assetId: Long): StockPrice {
        val job = currentCoroutineContext()[Job]!!
        return suspendCoroutine { prices += PriceCall(assetId, Pending(job, it)) }
    }
}
@OptIn(ExperimentalCoroutinesApi::class)
class MarketControllerContractTest {
    @Test fun debounceWaits250msAndCancelsEarlierTimer() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(249); runCurrent()
        assertTrue(source.searches.isEmpty())
        controller.updateQuery("B"); runCurrent(); advanceTimeBy(249); runCurrent()
        assertTrue(source.searches.isEmpty())
        advanceTimeBy(1); runCurrent()
        assertEquals("B", source.searches.single().query)
        source.searches.single().pending.succeed(listOf(stock(2))); runCurrent()
        assertEquals(LoadState.Ready(listOf(stock(2))), controller.state.value.search)
        controller.close()
    }
    @Test fun javascriptWhitespaceIsTrimmedButNelAndRawInputArePreserved() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        for ((raw, expected) in listOf(" \u00a0\ufeff삼성\ufeff\u00a0 " to "삼성", "\u0085삼성\u0085" to "\u0085삼성\u0085")) {
            controller.updateQuery(raw); runCurrent(); advanceTimeBy(250); runCurrent()
            assertEquals(raw, controller.state.value.query)
            assertEquals(expected, source.searches.last().query)
            source.searches.last().pending.succeed(emptyList()); runCurrent()
        }
        controller.close()
    }
    @Test fun blankInputInvalidatesInflightSearchAndClearsStatus() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        val old = source.searches.single().pending
        controller.updateQuery(" \ufeff\u00a0 "); runCurrent()
        assertTrue(old.job.isCancelled)
        assertEquals(LoadState.Idle, controller.state.value.search)
        old.succeed(listOf(stock())); runCurrent(); advanceTimeBy(1000); runCurrent()
        assertEquals(1, source.searches.size)
        assertEquals(LoadState.Idle, controller.state.value.search)
        controller.close()
    }
    @Test fun staleSearchSuccessCannotOverwriteNewerResults() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        controller.updateQuery("B"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertTrue(source.searches[0].pending.job.isCancelled)
        source.searches[1].pending.succeed(listOf(stock(2))); runCurrent()
        source.searches[0].pending.succeed(listOf(stock(1))); runCurrent()
        assertEquals(LoadState.Ready(listOf(stock(2))), controller.state.value.search)
        controller.close()
    }
    @Test fun staleSearchErrorAndFinallyCannotEndCurrentLoading() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        controller.updateQuery("B"); runCurrent(); advanceTimeBy(250); runCurrent()
        source.searches[0].pending.fail(ApiException(500, null, "stale")); runCurrent()
        assertEquals(LoadState.Loading, controller.state.value.search)
        source.searches[1].pending.succeed(emptyList()); runCurrent()
        assertEquals(LoadState.Ready(emptyList<Stock>()), controller.state.value.search)
        controller.close()
    }
    @Test fun countryChangeCancelsPreviousSearchAndRetriesSameTrimmedInput() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery(" AAPL "); runCurrent(); advanceTimeBy(250); runCurrent()
        controller.updateCountry(Country.US); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(Country.US, controller.state.value.country)
        assertEquals(" AAPL ", controller.state.value.query)
        assertEquals("AAPL", source.searches.last().query)
        assertEquals(Country.US, source.searches.last().country)
        assertTrue(source.searches.first().pending.job.isCancelled)
        source.searches.last().pending.succeed(listOf(stock(2))); runCurrent()
        source.searches.first().pending.fail(IllegalStateException("old")); runCurrent()
        assertEquals(LoadState.Ready(listOf(stock(2))), controller.state.value.search)
        controller.close()
    }
    @Test fun selectingStockSuppressesSearchAndStartsPriceImmediately() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        val search = source.searches.single().pending
        controller.select(stock(2)); runCurrent()
        assertTrue(search.job.isCancelled)
        assertEquals(2L, source.prices.single().id)
        assertEquals(LoadState.Loading, controller.state.value.price)
        assertEquals(LoadState.Idle, controller.state.value.search)
        controller.updateQuery("ignored while selected"); runCurrent(); advanceTimeBy(500); runCurrent()
        assertEquals(1, source.searches.size)
        search.succeed(listOf(stock(1))); source.prices.single().pending.succeed(price(2)); runCurrent()
        assertEquals(stock(2), controller.state.value.selected)
        assertEquals(LoadState.Idle, controller.state.value.search)
        controller.close()
    }
    @Test fun filterChangesDoNotTriggerAnotherServerRequest() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        val all = listOf(stock(1), stock(2).copy(category = Category.ETF), stock(3))
        source.searches.single().pending.succeed(all); runCurrent()
        controller.updateFilter(CategoryFilter.ETF); runCurrent(); advanceTimeBy(500); runCurrent()
        assertEquals(CategoryFilter.ETF, controller.state.value.filter)
        assertEquals(LoadState.Ready(all), controller.state.value.search)
        assertEquals(1, source.searches.size)
        controller.updateFilter(CategoryFilter.ALL); runCurrent()
        assertEquals(LoadState.Ready(all), controller.state.value.search)
        assertEquals(1, source.searches.size)
        controller.close()
    }
    @Test fun explicitRetryRecoversSearchWithoutAutomaticLoop() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(250); runCurrent()
        source.searches.single().pending.fail(ApiException(400, "INVALID_REQUEST", "bad")); runCurrent()
        assertTrue(controller.state.value.search is LoadState.Failed)
        advanceTimeBy(2000); runCurrent(); assertEquals(1, source.searches.size)
        controller.retrySearch(); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(2, source.searches.size)
        assertEquals("A", source.searches.last().query)
        source.searches.last().pending.succeed(emptyList()); runCurrent()
        assertEquals(LoadState.Ready(emptyList<Stock>()), controller.state.value.search)
        controller.close()
    }
    @Test fun positivePriceFillsPlainDecimalAndPreservesDateWithoutRequiringResponseIdMatch() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock(1)); runCurrent()
        source.prices.single().pending.succeed(price(2, "1.25e2", "2026-02-30")); runCurrent()
        assertEquals("125", controller.state.value.unitPrice)
        assertFalse(controller.state.value.priceEdited)
        assertEquals(LoadState.Ready(price(2, "1.25e2", "2026-02-30")), controller.state.value.price)
        controller.close()
    }
    @Test fun userEnteredAndClearedAndZeroPriceSurviveLateQuote() = runTest {
        for (entered in listOf("123.4000", "", "0")) {
            val source = ControlledSources(); val controller = MarketController(source, source, this)
            controller.select(stock()); runCurrent()
            controller.editUnitPrice("123.4000")
            controller.editUnitPrice(entered)
            source.prices.single().pending.succeed(price()); runCurrent()
            assertEquals(entered, controller.state.value.unitPrice)
            assertTrue(controller.state.value.priceEdited)
            assertTrue(controller.state.value.price is LoadState.Ready)
            controller.close()
        }
    }
    @Test fun restoredNonemptyUneditedPriceIsNotOverwritten() = runTest {
        val source = ControlledSources()
        val controller = MarketController(source, source, this, MarketDraft(selected = stock(), unitPrice = "7.5000", priceEdited = false))
        controller.setActive(true); runCurrent()
        assertEquals(1, source.prices.size)
        source.prices.single().pending.succeed(price()); runCurrent()
        assertEquals("7.5000", controller.state.value.unitPrice)
        controller.close()
    }
    @Test fun nonpositiveQuoteFailsAtUiLayerWithoutAutofillOrVisibleQuoteDate() = runTest {
        for (amount in listOf("0", "-1")) {
            val source = ControlledSources(); val controller = MarketController(source, source, this)
            controller.select(stock()); runCurrent()
            source.prices.single().pending.succeed(price(amount = amount)); runCurrent()
            assertTrue(controller.state.value.price is LoadState.Failed)
            assertEquals("", controller.state.value.unitPrice)
            controller.editUnitPrice("77"); assertEquals("77", controller.state.value.unitPrice)
            controller.close()
        }
    }
    @Test fun priceFailureSupportsManualEntryAndExplicitRetryPreservesIt() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent()
        source.prices.single().pending.fail(ApiException(404, "STOCK_PRICE_NOT_FOUND", "missing")); runCurrent()
        assertTrue(controller.state.value.price is LoadState.Failed)
        assertEquals(stock(), controller.state.value.selected)
        controller.editUnitPrice("42.0000")
        controller.retryPrice(); runCurrent()
        assertEquals(2, source.prices.size)
        source.prices.last().pending.succeed(price()); runCurrent()
        assertEquals("42.0000", controller.state.value.unitPrice)
        assertTrue(controller.state.value.priceEdited)
        assertTrue(controller.state.value.price is LoadState.Ready)
        controller.close()
    }
    @Test fun newSelectionResetsOnlyPriceDraftAndRejectsOldSuccess() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock(1)); runCurrent(); controller.editUnitPrice("88")
        controller.select(stock(2)); runCurrent()
        assertTrue(source.prices.first().pending.job.isCancelled)
        assertEquals("", controller.state.value.unitPrice)
        assertFalse(controller.state.value.priceEdited)
        source.prices.last().pending.succeed(price(2, "193400.0000")); runCurrent()
        source.prices.first().pending.succeed(price(1)); runCurrent()
        assertEquals("193400", controller.state.value.unitPrice)
        assertEquals(LoadState.Ready(price(2, "193400.0000")), controller.state.value.price)
        controller.close()
    }
    @Test fun stalePriceFailureAndFinallyCannotEndNewPriceLoading() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock(1)); runCurrent()
        controller.select(stock(2)); runCurrent()
        source.prices.first().pending.fail(ApiException(500, null, "old")); runCurrent()
        assertEquals(LoadState.Loading, controller.state.value.price)
        source.prices.last().pending.succeed(price(2)); runCurrent()
        assertEquals(stock(2), controller.state.value.selected)
        assertTrue(controller.state.value.price is LoadState.Ready)
        controller.close()
    }
    @Test fun clearSelectionInvalidatesOldPriceAndResetsDraft() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent(); controller.editUnitPrice("99")
        controller.clearSelection(); runCurrent()
        assertTrue(source.prices.single().pending.job.isCancelled)
        source.prices.single().pending.succeed(price()); runCurrent()
        assertNull(controller.state.value.selected)
        assertEquals("", controller.state.value.unitPrice)
        assertFalse(controller.state.value.priceEdited)
        assertEquals(LoadState.Idle, controller.state.value.price)
        controller.close()
    }
    @Test fun countryChangeClearsSelectionAndPriceDraft() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent(); controller.editUnitPrice("99")
        controller.updateCountry(Country.US); runCurrent()
        assertTrue(source.prices.single().pending.job.isCancelled)
        source.prices.single().pending.fail(IllegalStateException("stale")); runCurrent()
        assertNull(controller.state.value.selected)
        assertEquals(Country.US, controller.state.value.country)
        assertEquals("", controller.state.value.unitPrice)
        assertFalse(controller.state.value.priceEdited)
        assertEquals(LoadState.Idle, controller.state.value.price)
        controller.close()
    }
    @Test fun inactiveCancelsAndPreservesDraftThenActiveReissuesSuitablePrice() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent(); controller.editUnitPrice("12.3000")
        controller.setActive(false); runCurrent()
        assertTrue(source.prices.single().pending.job.isCancelled)
        val inactive = controller.state.value
        source.prices.single().pending.fail(IllegalStateException("late")); runCurrent()
        assertEquals(inactive, controller.state.value)
        assertEquals("12.3000", inactive.unitPrice)
        assertTrue(inactive.priceEdited)
        assertEquals(stock(), inactive.selected)
        controller.setActive(true); runCurrent()
        assertEquals(2, source.prices.size)
        source.prices.last().pending.succeed(price()); runCurrent()
        assertEquals("12.3000", controller.state.value.unitPrice)
        controller.close()
    }
    @Test fun inactiveSearchDoesNotRestartUntilActive() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.updateQuery("A"); runCurrent(); advanceTimeBy(100); runCurrent()
        controller.setActive(false); advanceTimeBy(500); runCurrent()
        assertTrue(source.searches.isEmpty())
        assertEquals("A", controller.state.value.query)
        controller.setActive(true); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals("A", source.searches.single().query)
        source.searches.single().pending.succeed(emptyList()); runCurrent()
        controller.close()
    }
    @Test fun cancellationExceptionIsNotUserVisibleFailure() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent()
        source.prices.single().pending.fail(CancellationException("cancel")); runCurrent()
        assertFalse(controller.state.value.price is LoadState.Failed)
        controller.close()
    }
    @Test fun closeIsTerminalAndLateCallbacksCannotMutateClosedState() = runTest {
        val source = ControlledSources(); val controller = MarketController(source, source, this)
        controller.select(stock()); runCurrent(); controller.editUnitPrice("55")
        controller.close(); runCurrent()
        assertTrue(source.prices.single().pending.job.isCancelled)
        val closed = controller.state.value
        source.prices.single().pending.succeed(price()); runCurrent()
        controller.setActive(true); controller.updateQuery("B"); controller.select(stock(2)); controller.editUnitPrice("66"); controller.retryPrice(); controller.retrySearch(); runCurrent(); advanceTimeBy(500); runCurrent()
        assertEquals(closed, controller.state.value)
        assertEquals(1, source.prices.size)
        assertTrue(source.searches.isEmpty())
    }
}
