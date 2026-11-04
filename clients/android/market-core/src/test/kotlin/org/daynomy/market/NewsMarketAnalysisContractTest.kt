package org.daynomy.market

import java.io.IOException
import kotlin.coroutines.Continuation
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

/** Expected fields and absence code follow MarketAnalysisResponse/MarketAnalysisService,
 * and service_acceptance.py market-fields/market-unavailable, not generated analysis. */
@OptIn(ExperimentalCoroutinesApi::class)
class NewsMarketAnalysisContractTest {
    @Test fun endpointPreservesOriginalFieldsAndAllowsUnknownFields() = runTest {
        val transport = RecordingTransport("""{"risk":"  위험 😀\n변동  ","watchPoint":"\t후속 지표\t","future":{"extra":true}}""")
        assertEquals(NewsMarketAnalysis("  위험 😀\n변동  ", "\t후속 지표\t"), NewsClient(transport).marketAnalysis(42))
        assertEquals(listOf("/api/news/42/market-analysis"), transport.paths)
    }

    @Test fun rejectsMissingNullWrongTypesAndJavaBlankFields() = runTest {
        val invalid = mutableListOf("", "{", "null", "[]", "{}")
        for (field in listOf("risk", "watchPoint")) {
            val other = if (field == "risk") "watchPoint" else "risk"
            invalid += """{"$other":"valid"}"""
            for (value in listOf("null", "1", "false", "[]", "{}", "\"\"", "\" \\t\\r\\n\"", "\"\\u001c\\u001d\\u001e\\u001f\"", "\"\\u2003\"")) {
                invalid += """{"$field":$value,"$other":"valid"}"""
            }
        }
        for (body in invalid) expectFailure<ResponseFormatException> {
            NewsClient(RecordingTransport(body)).marketAnalysis(42)
        }
    }

    @Test fun nonBreakingSpacesAreNotJavaBlankAndArePreserved() = runTest {
        // Java Character.isWhitespace excludes these, whereas Kotlin isBlank includes them.
        for (space in listOf("\u00a0", "\u2007", "\u202f")) {
            val body = """{"risk":"$space","watchPoint":"$space"}"""
            assertEquals(NewsMarketAnalysis(space, space), NewsClient(RecordingTransport(body)).marketAnalysis(1))
        }
    }

    @Test fun onlyExactNotFoundStatusAndCodeBecomeAbsentWithoutRetry() = runTest {
        val absent = RecordingTransport("invalid").apply {
            failure = ApiException(404, "MARKET_ANALYSIS_NOT_FOUND", "private")
        }
        assertNull(NewsClient(absent).marketAnalysis(42))
        assertEquals(listOf("/api/news/42/market-analysis"), absent.paths)
        for (failure in listOf(
            ApiException(404, "NEWS_NOT_FOUND", "private"),
            ApiException(404, "market_analysis_not_found", "private"),
            ApiException(401, "MARKET_ANALYSIS_NOT_FOUND", "private"),
            ApiException(503, "MARKET_ANALYSIS_NOT_FOUND", "private"),
            IOException("offline"), CancellationException("cancelled")
        )) {
            val transport = RecordingTransport("invalid").apply { this.failure = failure }
            assertSame(failure, expectFailure<Exception> { NewsClient(transport).marketAnalysis(42) })
            assertEquals(listOf("/api/news/42/market-analysis"), transport.paths)
        }
    }

    @Test fun existingNewsSourcesKeepDefaultUnsupportedBehavior() = runTest {
        val source = object : NewsSource {
            override suspend fun list(category: NewsCategory?, page: Int, size: Int) = analysisPage()
            override suspend fun detail(newsId: Long) = analysisDetail(newsId)
        }
        expectFailure<UnsupportedOperationException> { source.marketAnalysis(1) }
        assertEquals(LoadState.Idle, NewsUiState().analysis)
    }

    @Test fun analysisFailureKeepsDetailAndKeywordsAndExplicitRetryRecovers() = runTest {
        val source = AnalysisSource().apply { answer = { throw IOException("private-body") } }
        val controller = NewsController(source, this)
        try {
            controller.setActive(true); controller.openDetail(1); runCurrent()
            val detail = controller.state.value.detail
            val keywords = controller.state.value.keywords
            assertTrue(detail is LoadState.Ready); assertTrue(keywords is LoadState.Ready)
            assertTrue(controller.state.value.analysis is LoadState.Failed)
            assertFalse((controller.state.value.analysis as LoadState.Failed).message.contains("private-body"))
            assertEquals(listOf(1L), source.calls)
            source.answer = { sampleAnalysis() }; controller.retryAnalysis(); runCurrent()
            assertEquals(LoadState.Ready(sampleAnalysis()), controller.state.value.analysis)
            assertEquals(detail, controller.state.value.detail); assertEquals(keywords, controller.state.value.keywords)
            assertEquals(1, source.detailCalls); assertEquals(1, source.keywordCalls)
            source.answer = { null }; controller.retryAnalysis(); runCurrent()
            assertEquals(LoadState.Ready<NewsMarketAnalysis?>(null), controller.state.value.analysis)
            assertEquals(listOf(1L, 1L, 1L), source.calls)
        } finally { controller.close() }
    }

    @Test fun detailAndKeywordFailuresDoNotHideAnalysis() = runTest {
        val source = AnalysisSource().apply { detailFailure = IOException("detail"); keywordFailure = IOException("keywords") }
        val controller = NewsController(source, this)
        try {
            controller.setActive(true); controller.openDetail(1); runCurrent()
            assertTrue(controller.state.value.detail is LoadState.Failed)
            assertTrue(controller.state.value.keywords is LoadState.Failed)
            assertEquals(LoadState.Ready(sampleAnalysis()), controller.state.value.analysis)
        } finally { controller.close() }
    }

    @Test fun inactiveDoesNotFetchAndDeactivationCancelsThenReactivationFetchesAgain() = runTest {
        var cancelled = false
        val source = AnalysisSource().apply { answer = { try { awaitCancellation() } finally { cancelled = true } } }
        val controller = NewsController(source, this)
        try {
            controller.openDetail(1); controller.retryAnalysis(); runCurrent()
            assertTrue(source.calls.isEmpty()); assertEquals(LoadState.Idle, controller.state.value.analysis)
            controller.setActive(true); runCurrent()
            assertEquals(LoadState.Loading, controller.state.value.analysis)
            controller.setActive(false); runCurrent()
            assertTrue(cancelled); assertEquals(LoadState.Idle, controller.state.value.analysis)
            controller.retryAnalysis(); runCurrent(); assertEquals(listOf(1L), source.calls)
            source.answer = { sampleAnalysis() }; controller.setActive(true); runCurrent()
            assertEquals(listOf(1L, 1L), source.calls)
            assertEquals(LoadState.Ready(sampleAnalysis()), controller.state.value.analysis)
        } finally { controller.close() }
    }

    @Test fun sourceCancellationNeverBecomesReadyNullOrFailure() = runTest {
        val source = AnalysisSource().apply { answer = { throw CancellationException("cancelled") } }
        val controller = NewsController(source, this)
        try {
            controller.setActive(true); controller.openDetail(1); runCurrent()
            assertEquals(LoadState.Idle, controller.state.value.analysis)
            assertTrue(controller.state.value.detail is LoadState.Ready)
            assertEquals(listOf(1L), source.calls)
        } finally { controller.close() }
    }

    @Test fun lateSuccessAndFailureCannotCrossAnySelectionOrLifecycleBoundary() = runTest {
        for (boundary in listOf("detail", "back", "mode", "category", "page", "inactive", "close", "retry")) {
            for (fails in listOf(false, true)) {
                lateinit var pending: Continuation<NewsMarketAnalysis?>
                var resumed = false
                lateinit var pendingJob: Job
                val source = AnalysisSource().apply {
                    answer = {
                        pendingJob = currentCoroutineContext()[Job]!!
                        suspendCoroutine { pending = it }
                    }
                }
                val controller = NewsController(source, this)
                try {
                    controller.setActive(true); controller.openDetail(1); runCurrent()
                    assertEquals(LoadState.Loading, controller.state.value.analysis)
                    source.answer = { NewsMarketAnalysis("new risk", "new watch") }
                    when (boundary) {
                        "detail" -> controller.openDetail(2)
                        "back" -> controller.closeDetail()
                        "mode" -> controller.selectToday(true)
                        "category" -> controller.selectCategory(NewsCategory.ECONOMY)
                        "page" -> controller.selectPage(2)
                        "inactive" -> controller.setActive(false)
                        "close" -> controller.close()
                        "retry" -> controller.retryAnalysis()
                    }
                    runCurrent()
                    assertTrue("$boundary must cancel pending analysis", pendingJob.isCancelled)
                    val expected = controller.state.value.analysis
                    if (boundary == "detail" || boundary == "retry") {
                        assertEquals(LoadState.Ready(NewsMarketAnalysis("new risk", "new watch")), expected)
                    } else assertEquals(LoadState.Idle, expected)
                    resumed = true
                    if (fails) pending.resumeWithException(IOException("late-private-body")) else pending.resume(sampleAnalysis())
                    runCurrent()
                    assertEquals("$boundary / failure=$fails", expected, controller.state.value.analysis)
                    if (boundary == "detail") assertEquals(2L, controller.state.value.selectedId)
                    if (boundary in listOf("back", "mode", "category", "page")) {
                        assertNull(controller.state.value.selectedId)
                        controller.retryAnalysis(); runCurrent(); assertEquals(listOf(1L), source.calls)
                    }
                    if (boundary == "close") {
                        controller.retryAnalysis(); controller.openDetail(3); controller.setActive(true); runCurrent()
                        assertEquals(listOf(1L), source.calls)
                    }
                } finally {
                    if (!resumed) pending.resume(null)
                    controller.close(); runCurrent()
                }
            }
        }
    }
}

private fun sampleAnalysis() = NewsMarketAnalysis("위험", "확인 지표")
private fun analysisPage() = NewsPage(emptyList(), 1, 6, 0, 0, false)
private fun analysisDetail(id: Long) = NewsDetail(id, "제목", NewsCategory.STOCK, "2026-11-04", listOf("본문"), null, null, emptyList())
private class AnalysisSource : NewsSource {
    val calls = mutableListOf<Long>()
    var detailCalls = 0
    var keywordCalls = 0
    var detailFailure: Exception? = null
    var keywordFailure: Exception? = null
    var answer: suspend (Long) -> NewsMarketAnalysis? = { sampleAnalysis() }
    override suspend fun marketAnalysis(newsId: Long): NewsMarketAnalysis? { calls += newsId; return answer(newsId) }
    override suspend fun list(category: NewsCategory?, page: Int, size: Int) = analysisPage()
    override suspend fun today() = analysisPage()
    override suspend fun detail(newsId: Long): NewsDetail { detailCalls++; detailFailure?.let { throw it }; return analysisDetail(newsId) }
    override suspend fun keywords(newsId: Long): List<NewsKeyword> {
        keywordCalls++; keywordFailure?.let { throw it }
        return listOf(NewsKeyword(NewsKeywordCategory.POLICY, "금리", listOf("뜻", "맥락", "확인"), "뜻", "맥락", "확인"))
    }
}
