package org.daynomy.market
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/** Existing --discovery synthetic DB fixture; no production data or mock fallback. */
class NewsSearchBackendTest {
    @Test fun actualSearchNormalizesAndFiltersPublishedNewsWithPaginationAndLiteralWildcards() = runBlocking {
        val base = System.getenv("ANDROID_PILOT_BASE_URL")
        require(!base.isNullOrBlank())
        val news = NewsClient(OkHttpTransport(base))
        assertEquals(listOf(920002L, 920001L, 920003L), news.search("  테스트   뉴스 뉴스 ").items.map { it.id })
        val first = news.search("테스트 뉴스", NewsCategory.STOCK, 1, 1, NewsSearchSort.RELEVANCE)
        assertEquals(listOf(920002L), first.items.map { it.id }); assertTrue(first.hasNext)
        assertEquals(2L, first.totalElements)
        assertEquals(listOf(920001L), news.search("테스트 뉴스", NewsCategory.STOCK, 2, 1).items.map { it.id })
        for (query in listOf("테스트 없는단어", "테스트 %", "테스트 _", "테스트 !")) {
            assertTrue(news.search(query).items.isEmpty())
        }
        assertEquals(920002L, news.detail(first.items.single().id).id)
    }
}
