package org.daynomy.market

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test

/** Integration boundaries added when the existing search controller gained today's dashboard. */
@OptIn(ExperimentalCoroutinesApi::class)
class NewsDashboardSearchIntegrationTest {
    @Test fun dashboardTodayAndIssueSearchKeepIndependentStateAcrossReentry() = runTest {
        val source = CombinedNewsSource()
        val dashboard = NewsController(source, this)
        val issues = NewsController(source, this)
        try {
            dashboard.selectToday(true); dashboard.setActive(true); runCurrent()
            dashboard.setActive(false)
            issues.selectCategory(NewsCategory.ETF)
            issues.submitSearch("금리"); issues.selectSort(NewsSearchSort.RELEVANCE)
            issues.setActive(true); runCurrent(); issues.selectPage(2); runCurrent()
            val searchState = issues.state.value
            issues.setActive(false); dashboard.setActive(true); runCurrent()
            assertTrue(dashboard.state.value.todayOnly)
            assertNull(dashboard.state.value.searchQuery)
            assertEquals(9L, (dashboard.state.value.list as LoadState.Ready).value.items.single().id)
            assertEquals("금리", issues.state.value.searchQuery)
            assertEquals(NewsCategory.ETF, issues.state.value.category)
            assertEquals(2, issues.state.value.page)
            assertEquals(NewsSearchSort.RELEVANCE, issues.state.value.sort)
            dashboard.setActive(false); issues.setActive(true); runCurrent()
            assertEquals(searchState.searchQuery, issues.state.value.searchQuery)
            assertEquals("search:금리:ETF:2:6:RELEVANCE", source.calls.last())
            assertFalse(issues.state.value.todayOnly)
            assertEquals(2, source.calls.count { it == "today" })
        } finally { dashboard.close(); issues.close() }
    }

    @Test fun submittingSearchFromTodayRejectsLateTodayResponseAndReentersSearch() = runTest {
        val gate = CompletableDeferred<NewsPage>()
        val source = CombinedNewsSource().apply {
            todayAnswer = { withContext(NonCancellable) { gate.await() } }
        }
        val controller = NewsController(source, this)
        try {
            controller.selectToday(true); controller.setActive(true); runCurrent()
            controller.submitSearch("본문검색"); runCurrent()
            gate.complete(combinedPage(9)); runCurrent()
            assertFalse(controller.state.value.todayOnly)
            assertEquals("본문검색", controller.state.value.searchQuery)
            assertEquals(42L, (controller.state.value.list as LoadState.Ready).value.items.single().id)
            controller.setActive(false); controller.setActive(true); runCurrent()
            assertEquals("search:본문검색:null:1:6:LATEST", source.calls.last())
            assertEquals(1, source.calls.count { it == "today" })
            controller.clearSearch(); runCurrent()
            assertFalse(controller.state.value.todayOnly)
            assertNull(controller.state.value.searchQuery)
            assertEquals("list:null:1:6", source.calls.last())
        } finally { gate.complete(combinedPage(9)); controller.close() }
    }
}

private fun combinedPage(id: Long) =
    NewsPage(listOf(NewsListItem(id, "본문에만 검색어 포함", NewsCategory.STOCK, null, null)), 1, 6, 1, 1, false)
private class CombinedNewsSource : NewsSource {
    val calls = mutableListOf<String>()
    var todayAnswer: suspend () -> NewsPage = { combinedPage(9) }
    override suspend fun today(): NewsPage { calls += "today"; return todayAnswer() }
    override suspend fun search(query: String, category: NewsCategory?, page: Int, size: Int, sort: NewsSearchSort): NewsPage {
        calls += "search:$query:$category:$page:$size:$sort"
        return combinedPage(42)
    }
    override suspend fun list(category: NewsCategory?, page: Int, size: Int): NewsPage {
        calls += "list:$category:$page:$size"
        return combinedPage(1)
    }
    override suspend fun detail(newsId: Long) =
        NewsDetail(newsId, "detail", NewsCategory.STOCK, "date", listOf("body"), null, null, emptyList())
}
