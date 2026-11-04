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
class NewsSearchControllerTest {
    @Test fun submitCategorySortAndClearResetPageAndDetailWhileBackPreservesSearch() = runTest {
        val source = SearchFake(); val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.selectPage(2); runCurrent()
        controller.openDetail(2); runCurrent(); controller.submitSearch(" Fed fed "); runCurrent()
        assertEquals(" Fed fed ", controller.state.value.searchQuery); assertEquals(1, controller.state.value.page)
        assertNull(controller.state.value.selectedId); assertEquals(LoadState.Idle, controller.state.value.detail)
        assertEquals(SearchCall(" Fed fed ", null, 1, NewsSearchSort.LATEST), source.searches.last())
        controller.selectPage(2); runCurrent(); controller.openDetail(2); runCurrent(); controller.closeDetail()
        assertEquals(2, controller.state.value.page); assertEquals(" Fed fed ", controller.state.value.searchQuery)
        controller.selectCategory(NewsCategory.ETF); runCurrent()
        assertEquals(SearchCall(" Fed fed ", NewsCategory.ETF, 1, NewsSearchSort.LATEST), source.searches.last())
        controller.selectPage(2); runCurrent(); controller.selectSort(NewsSearchSort.RELEVANCE); runCurrent()
        assertEquals(SearchCall(" Fed fed ", NewsCategory.ETF, 1, NewsSearchSort.RELEVANCE), source.searches.last())
        controller.clearSearch(); runCurrent()
        assertNull(controller.state.value.searchQuery); assertNull(controller.state.value.searchError)
        assertEquals(NewsCategory.ETF to 1, source.lists.last()); assertEquals(1, controller.state.value.page)
        controller.close()
    }

    @Test fun invalidSubmitDoesNotReplaceValidQueryOrMakeRequestAndValidSubmitClearsError() = runTest {
        val source = SearchFake(); val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.submitSearch("금리"); runCurrent()
        val count = source.searches.size
        for (query in listOf("", "  ", "%_!", "a".repeat(101), "a\nb")) {
            controller.submitSearch(query); runCurrent()
            assertEquals("금리", controller.state.value.searchQuery); assertNotNull(controller.state.value.searchError)
            assertEquals(count, source.searches.size)
        }
        controller.submitSearch("ETF"); runCurrent()
        assertNull(controller.state.value.searchError); assertEquals("ETF", controller.state.value.searchQuery)
        controller.close()
    }

    @Test fun lateListAndOlderSearchSuccessCannotOverwriteNewestSearch() = runTest {
        val listGate = CompletableDeferred<NewsPage>(); val searchGate = CompletableDeferred<NewsPage>()
        val source = SearchFake().apply {
            listAnswer = { _, _ -> withContext(NonCancellable) { listGate.await() } }
            searchAnswer = { call -> if (call.query == "old") withContext(NonCancellable) { searchGate.await() } else searchPage(id = 30) }
        }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.submitSearch("old"); runCurrent()
        controller.submitSearch("new"); runCurrent()
        listGate.complete(searchPage(id = 10)); searchGate.complete(searchPage(id = 20)); runCurrent()
        assertEquals("new", controller.state.value.searchQuery)
        assertEquals(30L, (controller.state.value.list as LoadState.Ready).value.items.single().id)
        controller.close()
    }

    @Test fun clearSearchDiscardsLateFailureAndReturnsToNormalList() = runTest {
        val gate = CompletableDeferred<Unit>()
        val source = SearchFake().apply { searchAnswer = { withContext(NonCancellable) { gate.await() }; throw IOException("private-late") } }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.submitSearch("old"); runCurrent()
        controller.clearSearch(); runCurrent(); gate.complete(Unit); runCurrent()
        assertNull(controller.state.value.searchQuery); assertTrue(controller.state.value.list is LoadState.Ready)
        controller.close()
    }

    @Test fun errorsRemainSafeAndExplicitRetryRetainsAllSearchConditionsAndEmptySuccess() = runTest {
        val source = SearchFake().apply { searchAnswer = { throw IOException("private-server-body") } }
        val controller = NewsController(source, this)
        controller.setActive(true); runCurrent(); controller.selectCategory(NewsCategory.STOCK); runCurrent()
        controller.submitSearch("금리"); runCurrent(); controller.selectSort(NewsSearchSort.RELEVANCE); runCurrent()
        controller.selectPage(2); runCurrent()
        assertFalse((controller.state.value.list as LoadState.Failed).message.contains("private-server-body"))
        val count = source.searches.size; runCurrent(); assertEquals(count, source.searches.size)
        source.searchAnswer = { call -> searchPage(call.page).copy(items = emptyList(), totalPages = 0, totalElements = 0, hasNext = false) }
        controller.retryList(); runCurrent()
        assertEquals(count + 1, source.searches.size)
        assertEquals(SearchCall("금리", NewsCategory.STOCK, 2, NewsSearchSort.RELEVANCE), source.searches.last())
        assertTrue((controller.state.value.list as LoadState.Ready).value.items.isEmpty())
        controller.close()
    }

    @Test fun inactiveSearchWaitsForActivationCancellationCleansUpAndCloseIsTerminal() = runTest {
        var cancelled = false
        val source = SearchFake().apply { searchAnswer = { try { awaitCancellation() } finally { cancelled = true } } }
        val controller = NewsController(source, this)
        controller.submitSearch("금리"); runCurrent(); assertTrue(source.searches.isEmpty())
        controller.setActive(true); runCurrent(); controller.setActive(false); runCurrent()
        assertTrue(cancelled); assertEquals(LoadState.Idle, controller.state.value.list)
        source.searchAnswer = { searchPage(it.page) }
        controller.setActive(true); runCurrent(); assertEquals("금리", source.searches.last().query)
        controller.close(); val closed = controller.state.value; val count = source.searches.size
        controller.submitSearch("new"); controller.clearSearch(); controller.selectSort(NewsSearchSort.RELEVANCE)
        controller.setActive(true); controller.retryList(); runCurrent()
        assertEquals(closed, controller.state.value); assertEquals(count, source.searches.size)
    }
}

private data class SearchCall(val query: String, val category: NewsCategory?, val page: Int, val sort: NewsSearchSort)
private fun searchPage(page: Int = 1, id: Long = 2) = NewsPage(listOf(NewsListItem(id, "News $id", NewsCategory.STOCK, null, null)), page, 6, 3, 13, page < 3)
private class SearchFake : NewsSource {
    val searches = mutableListOf<SearchCall>(); val lists = mutableListOf<Pair<NewsCategory?, Int>>()
    var searchAnswer: suspend (SearchCall) -> NewsPage = { searchPage(it.page) }
    var listAnswer: suspend (NewsCategory?, Int) -> NewsPage = { _, page -> searchPage(page) }
    override suspend fun list(category: NewsCategory?, page: Int, size: Int): NewsPage {
        lists += category to page; return listAnswer(category, page)
    }
    override suspend fun detail(newsId: Long) = NewsDetail(newsId, "News $newsId", NewsCategory.STOCK, "2026-10-23T00:00:00Z", listOf("Body"), null, null, emptyList())
    override suspend fun search(query: String, category: NewsCategory?, page: Int, size: Int, sort: NewsSearchSort): NewsPage {
        assertEquals(6, size)
        val call = SearchCall(query, category, page, sort); searches += call; return searchAnswer(call)
    }
}
