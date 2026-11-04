package org.daynomy.market

import java.io.IOException
import java.math.BigDecimal
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ExchangeControllerContractTest {
    @Test fun activationAndBlankDateHaveNoSpuriousRequestAndPreserveRawDate() = runTest {
        val source = ExchangeFake()
        val controller = ExchangeController(source, this)
        assertEquals(ExchangeUiState(), controller.state.value)
        controller.updateDate(" 2026-02-30 "); runCurrent()
        assertTrue(source.calls.isEmpty())
        controller.setActive(true); runCurrent()
        assertEquals(listOf(" 2026-02-30 "), source.calls)
        assertEquals(" 2026-02-30 ", controller.state.value.date)
        assertEquals(LoadState.Ready(exchangeQuote()), controller.state.value.quote)
        controller.setActive(true); runCurrent(); assertEquals(1, source.calls.size)
        controller.updateDate(" \t "); runCurrent()
        assertEquals(" \t ", controller.state.value.date)
        assertEquals(LoadState.Idle, controller.state.value.quote)
        controller.retry(); runCurrent(); assertEquals(1, source.calls.size)
        controller.close()
    }

    @Test fun loadingThenFailureThenExplicitRetryIsNotEmptySuccessOrAutomaticRetry() = runTest {
        val gate = CompletableDeferred<Unit>()
        val source = ExchangeFake().apply { answer = { gate.await(); throw IOException("secret-response-body") } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("2026-10-25"); runCurrent()
        assertEquals(LoadState.Loading, controller.state.value.quote)
        gate.complete(Unit); runCurrent()
        val failed = controller.state.value.quote as LoadState.Failed
        assertTrue(failed.message.isNotBlank())
        assertFalse(failed.message.contains("secret-response-body"))
        assertEquals(1, source.calls.size)
        source.answer = { exchangeQuote() }
        controller.retry(); runCurrent()
        assertEquals(listOf("2026-10-25", "2026-10-25"), source.calls)
        assertEquals(LoadState.Ready(exchangeQuote()), controller.state.value.quote)
        controller.close()
    }

    @Test fun newDateWinsOverNonCooperativeOlderSuccess() = runTest {
        val old = CompletableDeferred<ExchangeRate>()
        val source = ExchangeFake().apply { answer = { date -> if (date == "old") withContext(NonCancellable) { old.await() } else exchangeQuote("new", "1500") } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("old"); runCurrent()
        controller.updateDate("new"); runCurrent()
        old.complete(exchangeQuote("old", "1000")); runCurrent()
        assertEquals("new", controller.state.value.date)
        assertEquals(LoadState.Ready(exchangeQuote("new", "1500")), controller.state.value.quote)
        controller.close()
    }

    @Test fun oldFailureCannotClearNewQuote() = runTest {
        val old = CompletableDeferred<Unit>()
        val source = ExchangeFake().apply { answer = { date ->
            if (date == "old") { withContext(NonCancellable) { old.await() }; throw IOException("old failure") }
            exchangeQuote("new")
        } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("old"); runCurrent()
        controller.updateDate("new"); runCurrent()
        old.complete(Unit); runCurrent()
        assertEquals(LoadState.Ready(exchangeQuote("new")), controller.state.value.quote)
        controller.close()
    }

    @Test fun deactivationCancelsJobAndReactivationLoadsCurrentDateOnce() = runTest {
        var cleaned = false
        val source = ExchangeFake().apply { answer = { try { awaitCancellation() } finally { cleaned = true } } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("2026-10-25"); runCurrent()
        controller.setActive(false); runCurrent()
        assertTrue(cleaned)
        assertEquals(LoadState.Idle, controller.state.value.quote)
        source.answer = { exchangeQuote() }
        controller.setActive(true); controller.setActive(true); runCurrent()
        assertEquals(2, source.calls.size)
        assertEquals(LoadState.Ready(exchangeQuote()), controller.state.value.quote)
        controller.close()
    }

    @Test fun cancellationIsIdleInsteadOfFailure() = runTest {
        val source = ExchangeFake().apply { answer = { throw CancellationException("cancel") } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("date"); runCurrent()
        assertEquals(LoadState.Idle, controller.state.value.quote)
        controller.close()
    }

    @Test fun closeIsTerminalAndLateSuccessCannotRepopulateState() = runTest {
        val old = CompletableDeferred<ExchangeRate>()
        val source = ExchangeFake().apply { answer = { withContext(NonCancellable) { old.await() } } }
        val controller = ExchangeController(source, this)
        controller.setActive(true); controller.updateDate("old"); runCurrent()
        controller.close(); val closed = controller.state.value
        controller.updateDate("new"); controller.retry(); controller.setActive(true); controller.close()
        old.complete(exchangeQuote()); runCurrent()
        assertEquals(closed, controller.state.value)
        assertEquals(LoadState.Idle, controller.state.value.quote)
        assertEquals(listOf("old"), source.calls)
    }
}

private fun exchangeQuote(date: String = "2026-10-23", rate: String = "1423.123456") = ExchangeRate(date, BigDecimal(rate))
private class ExchangeFake : ExchangeRateSource {
    val calls = mutableListOf<String>()
    var answer: suspend (String) -> ExchangeRate = { exchangeQuote() }
    override suspend fun quote(date: String): ExchangeRate { calls += date; return answer(date) }
}
