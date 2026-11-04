package org.daynomy.market

enum class NewsCategory { REAL_ESTATE, DEPOSIT_SAVINGS, STOCK, ECONOMY, ETF, BOND, PENSION, FOREIGN_EXCHANGE, VIRTUAL_ASSET, GOLD }
enum class NewsImageSourceType { NONE, AI_GENERATED, WIKIMEDIA, MANUAL }
data class NewsListItem(val id: Long, val title: String, val category: NewsCategory, val imageUrl: String?, val publishedAt: String?)
data class NewsPage(val items: List<NewsListItem>, val page: Int, val size: Int, val totalPages: Int, val totalElements: Long, val hasNext: Boolean)
data class NewsSourceLink(val name: String, val url: String)
data class NewsImageSource(val name: String, val url: String, val author: String, val license: String, val licenseUrl: String, val type: NewsImageSourceType)
data class NewsDetail(val id: Long, val title: String, val category: NewsCategory, val publishedAt: String, val content: List<String>, val imageUrl: String?, val imageSource: NewsImageSource?, val sources: List<NewsSourceLink>)
enum class NewsKeywordCategory { PERSON, POLICY, EVENT, TERM, TREND }
data class NewsKeyword(val category: NewsKeywordCategory, val keyword: String, val points: List<String>, val definition: String, val context: String, val watchPoint: String)
interface NewsSource {
    suspend fun keywords(newsId: Long): List<NewsKeyword> = throw UnsupportedOperationException("키워드 조회를 지원하지 않습니다.")
    suspend fun today(): NewsPage = throw UnsupportedOperationException("오늘 뉴스 조회를 지원하지 않습니다.")
    suspend fun list(category: NewsCategory? = null, page: Int = 1, size: Int = 6): NewsPage
    suspend fun detail(newsId: Long): NewsDetail
}
data class NewsUiState(val category: NewsCategory? = null, val page: Int = 1, val list: LoadState<NewsPage> = LoadState.Idle, val selectedId: Long? = null, val detail: LoadState<NewsDetail> = LoadState.Idle, val todayOnly: Boolean = false, val keywords: LoadState<List<NewsKeyword>> = LoadState.Idle)
