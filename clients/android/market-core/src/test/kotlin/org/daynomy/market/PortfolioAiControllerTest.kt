package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class PortfolioAiControllerTest {
    @Test fun loginRequiredResetBlocksAllReadsAndWritesUntilAuthenticatedReset() = runTest {
        val transport = AiTestTransport()
        val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
        try {
            controller.load(); runCurrent()
            assertNotNull(controller.state.value.saved)
            transport.calls.clear()
            controller.reset(true)
            val loggedOut = controller.state.value
            controller.load(); controller.loadHistory(); controller.generate(); controller.generate(true)
            runCurrent()
            assertTrue(transport.calls.isEmpty())
            assertEquals(loggedOut, controller.state.value)
            assertNull(controller.state.value.saved)
            controller.reset(false); controller.load(); runCurrent()
            assertEquals(listOf(AiTestCall("GET", "/api/users/me/portfolio/analysis", null)), transport.calls)
            assertFalse(controller.state.value.loginRequired)
            assertNotNull(controller.state.value.saved)
        } finally { controller.close() }
    }

    @Test fun readsNeverGenerateAndDuplicateSubmissionIsBlockedWhilePending() = runTest {
        val gate = CompletableDeferred<String>(); val transport = AiTestTransport()
        val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
        try {
            controller.load(); runCurrent()
            assertEquals(listOf("GET"), transport.calls.map { it.method })
            transport.answer = { if (it.method == "POST") gate.await() else "[]" }
            controller.generate(); controller.generate(true); runCurrent()
            assertTrue(controller.state.value.submitting)
            assertEquals(1, transport.calls.count { it.method == "POST" })
            gate.complete(AI_TEST_SAVED); runCurrent()
            assertFalse(controller.state.value.submitting); assertNotNull(controller.state.value.saved)
            controller.loadHistory(); runCurrent()
            assertEquals(1, transport.calls.count { it.method == "POST" })
        } finally { gate.complete(AI_TEST_SAVED); controller.close() }
    }

    @Test fun uncertainPostPreservesResultAndBlocksAnotherPostUntilSuccessfulSavedRead() = runTest {
        for (failure in listOf<Throwable>(IOException("private-transport"), ResponseFormatException("private-json"), ApiException(409, "PROCESSING", "private-server"))) {
            val transport = AiTestTransport(); val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
            try {
                controller.load(); runCurrent(); val previous = controller.state.value.saved
                transport.answer = { throw failure }
                controller.generate(); runCurrent()
                assertEquals(previous, controller.state.value.saved)
                assertTrue(controller.state.value.outcomeUnknown)
                assertFalse(controller.state.value.submitting)
                assertFalse(controller.state.value.message.orEmpty().contains("private-"))
                val posts = transport.calls.count { it.method == "POST" }
                controller.generate(true); runCurrent()
                assertEquals(posts, transport.calls.count { it.method == "POST" })
                controller.load(); runCurrent()
                assertTrue(controller.state.value.outcomeUnknown)
                transport.answer = { AI_TEST_SAVED }
                controller.load(); runCurrent()
                assertFalse(controller.state.value.outcomeUnknown)
                controller.generate(true); runCurrent()
                assertEquals(posts + 1, transport.calls.count { it.method == "POST" })
            } finally { controller.close() }
        }
    }

    @Test fun historyFailurePreservesCurrentAnalysisAndUsesSeparateSafeError() = runTest {
        val transport = AiTestTransport(); val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
        try {
            controller.load(); runCurrent(); val previous = controller.state.value.saved
            transport.answer = { throw IOException("private-history") }
            controller.loadHistory(); runCurrent()
            assertEquals(previous, controller.state.value.saved)
            assertFalse(controller.state.value.historyLoading)
            assertNotNull(controller.state.value.historyError)
            assertFalse(controller.state.value.historyError.orEmpty().contains("private-history"))
            assertFalse(controller.state.value.outcomeUnknown)
        } finally { controller.close() }
    }

    @Test fun historyStartedBeforeGenerationCannotRestoreStaleHistoryAfterSuccess() = runTest {
        val gate = CompletableDeferred<String>(); val transport = AiTestTransport()
        val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
        try {
            controller.load(); runCurrent()
            transport.answer = { call ->
                if (call.path.endsWith("/history")) withContext(NonCancellable) { gate.await() }
                else AI_TEST_SAVED
            }
            controller.loadHistory(); runCurrent()
            controller.generate(); runCurrent()
            assertNull(controller.state.value.history)
            gate.complete("[]"); runCurrent()
            assertNull(controller.state.value.history)
            assertFalse(controller.state.value.historyLoading)
        } finally { gate.complete("[]"); controller.close() }
    }

    @Test fun resetAndPortfolioInvalidationDiscardLateReadsAndMutations() = runTest {
        for (mutation in listOf(false, true)) {
            val gate = CompletableDeferred<String>(); val transport = AiTestTransport()
            val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
            try {
                controller.load(); runCurrent()
                transport.answer = { withContext(NonCancellable) { gate.await() } }
                if (mutation) controller.generate() else controller.load()
                runCurrent(); controller.reset(true)
                val resetState = controller.state.value
                gate.complete(AI_TEST_SAVED); runCurrent()
                assertEquals(resetState, controller.state.value)
                assertTrue(controller.state.value.loginRequired); assertNull(controller.state.value.saved)
            } finally { gate.complete(AI_TEST_SAVED); controller.close() }
        }
        val gate = CompletableDeferred<String>(); val transport = AiTestTransport()
        val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this)
        try {
            controller.load(); runCurrent()
            transport.answer = { withContext(NonCancellable) { gate.await() } }
            controller.generate(); runCurrent(); controller.invalidatePortfolio()
            val invalidated = controller.state.value
            gate.complete(AI_TEST_SAVED); runCurrent()
            assertEquals(invalidated, controller.state.value)
            assertTrue(controller.state.value.portfolioChanged)
        } finally { gate.complete(AI_TEST_SAVED); controller.close() }
    }

    @Test fun unauthorizedClearsSensitiveResultsAndNotifiesOnceAndCloseIsTerminal() = runTest {
        val transport = AiTestTransport(); var unauthorized = 0
        val controller = PortfolioAiController(PortfolioAnalysisClient(transport), this) { unauthorized++ }
        try {
            controller.load(); runCurrent()
            transport.answer = { throw ApiException(401, "UNAUTHORIZED", "private-auth") }
            controller.generate(); runCurrent()
            assertNull(controller.state.value.saved); assertNull(controller.state.value.history)
            assertTrue(controller.state.value.loginRequired); assertEquals(1, unauthorized)
            controller.close(); val closed = controller.state.value; val count = transport.calls.size
            controller.load(); controller.generate(); controller.loadHistory(); runCurrent()
            assertEquals(count, transport.calls.size); assertEquals(closed, controller.state.value)
        } finally { controller.close() }
    }
}
