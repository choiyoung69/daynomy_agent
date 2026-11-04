package org.daynomy.market

import java.io.IOException
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
class DiscoveryControllerContractTest {
    @Test fun activationPaginationCategoryResetAndDetailBackPreserveExpectedSelection() = runTest {
        val source = DiscoveryFake()
        val controller = NewsController(source, this)
        assertEquals(NewsUiState(), controller.state.value)
        controller.selectPage(2); runCurrent(); assertTrue(source.lists.isEmpty())
        controller.setActive(true); controller.setActive(true); runCurrent()
        assertEquals(listOf(null to 2), source.lists)
        controller.openDetail(2); runCurrent()
        assertEquals(2L, controller.state.value.selectedId)
        assertEquals(LoadState.Ready(discoveryDetail(2)), controller.state.value.detail)
        val retained = controller.state.value.list
        controller.closeDetail(); runCurrent()
        assertNull(controller.state.value.selectedId); assertEquals(LoadState.Idle, controller.state.value.detail)
        assertEquals(retained, controller.state.value.list); assertEquals(2, controller.state.value.page)
        controller.selectCategory(NewsCategory.ETF); runCurrent()
        assertEquals(1, controller.state.value.page); assertEquals(NewsCategory.ETF, controller.state.value.category)
        assertEquals(NewsCategory.ETF to 1, source.lists.last())
        controller.selectPage(0); runCurrent(); assertEquals(NewsCategory.ETF to 0, source.lists.last())
        controller.close()
    }

    @Test fun latestCategoryAndDetailWinOverNonCooperativeOldSuccesses() = runTest {
        val listGate = CompletableDeferred<NewsPage>()
        val detailGate = CompletableDeferred<NewsDetail>()
        val source = DiscoveryFake().apply {
            listAnswer = { category, page -> if (category == null) withContext(NonCancellable) { listGate.await() } else discoveryNewsPage(page, 20) }
            detailAnswer = { id -> if (id == 1L) withContext(NonCancellable) { detailGate.await() } else discoveryDetail(id) }
        }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent()
        assertEquals(LoadState.Loading, controller.state.value.list)
        controller.selectCategory(NewsCategory.STOCK); runCurrent()
        controller.openDetail(1); runCurrent(); controller.openDetail(2); runCurrent()
        listGate.complete(discoveryNewsPage(1, 1)); detailGate.complete(discoveryDetail(1)); runCurrent()
        assertEquals(LoadState.Ready(discoveryNewsPage(1, 20)), controller.state.value.list)
        assertEquals(2L, controller.state.value.selectedId)
        assertEquals(LoadState.Ready(discoveryDetail(2)), controller.state.value.detail)
        controller.close()
    }

    @Test fun failuresAreDistinctFromEmptyReadyAndRetriesAreExplicit() = runTest {
        val source = DiscoveryFake().apply {
            listAnswer = { _, _ -> throw IOException("private-server-body") }
            detailAnswer = { throw ApiException(404, "NEWS_NOT_FOUND", "private-server-body") }
        }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent()
        assertFalse((controller.state.value.list as LoadState.Failed).message.contains("private-server-body"))
        assertEquals(1, source.lists.size)
        controller.retryDetail(); runCurrent(); assertTrue(source.details.isEmpty())
        controller.openDetail(99); runCurrent()
        assertFalse((controller.state.value.detail as LoadState.Failed).message.contains("private-server-body"))
        source.listAnswer = { _, page -> discoveryNewsPage(page).copy(items = emptyList(), totalPages = 0, totalElements = 0, hasNext = false) }
        source.detailAnswer = { discoveryDetail(it) }
        controller.retryList(); controller.retryDetail(); runCurrent()
        assertTrue((controller.state.value.list as LoadState.Ready).value.items.isEmpty())
        assertEquals(LoadState.Ready(discoveryDetail(99)), controller.state.value.detail)
        assertEquals(2, source.lists.size); assertEquals(listOf(99L, 99L), source.details)
        controller.load(); runCurrent(); assertEquals(3, source.lists.size)
        controller.close()
    }

    @Test fun deactivationCancelsBothRequestsAndReactivationReloadsCurrentSelection() = runTest {
        var listCleaned = false
        var detailCleaned = false
        val source = DiscoveryFake().apply {
            listAnswer = { _, _ -> try { awaitCancellation() } finally { listCleaned = true } }
            detailAnswer = { try { awaitCancellation() } finally { detailCleaned = true } }
        }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.openDetail(2); runCurrent()
        controller.setActive(false); runCurrent()
        assertTrue(listCleaned); assertTrue(detailCleaned)
        assertEquals(LoadState.Idle, controller.state.value.list); assertEquals(LoadState.Idle, controller.state.value.detail)
        source.listAnswer = { _, page -> discoveryNewsPage(page) }; source.detailAnswer = { discoveryDetail(it) }
        controller.setActive(true); controller.setActive(true); runCurrent()
        assertEquals(LoadState.Ready(discoveryDetail(2)), controller.state.value.detail)
        assertEquals(listOf(2L, 2L), source.details)
        controller.close()
    }

    @Test fun closingDetailAndControllerDiscardsLateFailureAndCloseIsTerminal() = runTest {
        val gate = CompletableDeferred<Unit>()
        val source = DiscoveryFake().apply { detailAnswer = { withContext(NonCancellable) { gate.await() }; throw IOException("late") } }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.openDetail(1); runCurrent()
        controller.closeDetail(); gate.complete(Unit); runCurrent()
        assertNull(controller.state.value.selectedId); assertEquals(LoadState.Idle, controller.state.value.detail)
        controller.close(); val closed = controller.state.value
        val calls = source.lists.size to source.details.size
        controller.setActive(true); controller.selectPage(2); controller.selectCategory(NewsCategory.ETF)
        controller.openDetail(2); controller.load(); controller.retryList(); controller.retryDetail(); controller.closeDetail(); controller.close(); runCurrent()
        assertEquals(closed, controller.state.value)
        assertEquals(calls, source.lists.size to source.details.size)
    }
}

private fun discoveryNewsPage(page: Int = 1, id: Long = 2) = NewsPage(listOf(NewsListItem(id, "News $id", NewsCategory.STOCK, null, null)), page, 6, 2, 7, true)
private fun discoveryDetail(id: Long) = NewsDetail(id, "News $id", NewsCategory.STOCK, "2026-10-23T00:00:00Z", listOf("Body $id"), null, null, emptyList())
private class DiscoveryFake : NewsSource {
    val lists = mutableListOf<Pair<NewsCategory?, Int>>()
    val details = mutableListOf<Long>()
    var listAnswer: suspend (NewsCategory?, Int) -> NewsPage = { _, page -> discoveryNewsPage(page) }
    var detailAnswer: suspend (Long) -> NewsDetail = { discoveryDetail(it) }
    override suspend fun list(category: NewsCategory?, page: Int, size: Int): NewsPage { assertEquals(6, size); lists += category to page; return listAnswer(category, page) }
    override suspend fun detail(newsId: Long): NewsDetail { details += newsId; return detailAnswer(newsId) }
}
