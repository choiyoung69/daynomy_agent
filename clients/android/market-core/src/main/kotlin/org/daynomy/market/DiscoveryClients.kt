package org.daynomy.market

import java.math.BigDecimal
import java.net.URLEncoder
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

class NewsClient(private val transport: HttpTransport) : NewsSource {
    override suspend fun list(category: NewsCategory?, page: Int, size: Int): NewsPage {
        val path = "/api/news?page=$page&size=$size" + (category?.let { "&category=${it.name}" } ?: "")
        return decodePage(transport.get(path))
    }
    override suspend fun today(): NewsPage = decodePage(transport.get("/api/news/today"))
    private fun decodePage(body: String): NewsPage {
        val row = newsObject(body)
        val items = newsItems(row["items"])
        return NewsPage(items, newsInt(row["page"]), newsInt(row["size"]), newsInt(row["totalPages"]),
            newsLong(row["totalElements"]), newsBoolean(row["hasNext"]))
    }
    override suspend fun search(query: String, category: NewsCategory?, page: Int, size: Int, sort: NewsSearchSort): NewsPage {
        require(validNewsQuery(query)) { "검색어는 문자 또는 숫자를 포함해 100자 이내로 입력해 주세요." }
        require(page >= 1 && size in 1..100) { "검색 페이지가 올바르지 않습니다." }
        val path = "/api/search/news?q=${URLEncoder.encode(query, "UTF-8")}&page=$page&size=$size&sort=${sort.name}" +
            (category?.let { "&category=${it.name}" } ?: "")
        val row = newsObject(transport.get(path))
        val items = newsItems(row["content"])
        val responsePage = newsInt(row["page"])
        val responseSize = newsInt(row["size"])
        val totalPages = newsInt(row["totalPages"])
        val totalElements = newsLong(row["totalElements"])
        if (responsePage < 1 || responseSize < 1 || totalPages < 0 || totalElements < 0) invalidNewsResponse()
        return NewsPage(items, responsePage, responseSize, totalPages, totalElements, responsePage < totalPages)
    }
    override suspend fun detail(newsId: Long): NewsDetail {
        val row = newsObject(transport.get("/api/news/$newsId"))
        val content = when (val element = row["content"]) {
            is JsonArray -> element.map(::newsString)
            is JsonPrimitive -> newsString(element).split('\n').filter { it.isNotEmpty() }
            else -> invalidNewsResponse()
        }
        val imageSource = if (row.containsKey("imageSource")) {
            val source = newsObject(row["imageSource"])
            val type = newsString(source["type"])
            NewsImageSource(newsString(source["name"]), newsString(source["url"]), newsString(source["author"]),
                newsString(source["license"]), newsString(source["licenseUrl"]),
                NewsImageSourceType.entries.firstOrNull { it.name == type } ?: invalidNewsResponse())
        } else null
        val sources = newsArray(row["sources"]).map { element ->
            val source = newsObject(element)
            NewsSourceLink(newsString(source["name"]), newsString(source["url"]))
        }
        return NewsDetail(newsLong(row["id"]), newsString(row["title"]), newsCategory(row["category"]),
            newsString(row["publishedAt"]), content,
            if (row.containsKey("imageUrl")) newsNullableString(row["imageUrl"]) else null, imageSource, sources)
    }
}

private val NEWS_JSON_NUMBER = Regex("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
private fun invalidNewsResponse(): Nothing = throw ResponseFormatException("뉴스 API 응답 형식이 올바르지 않습니다.")
private fun newsObject(body: String): JsonObject {
    val element = try { Json.parseToJsonElement(body) } catch (_: SerializationException) { invalidNewsResponse() }
    return newsObject(element)
}
private fun newsObject(element: JsonElement?): JsonObject = element as? JsonObject ?: invalidNewsResponse()
private fun newsArray(element: JsonElement?): JsonArray = element as? JsonArray ?: invalidNewsResponse()
private fun newsString(element: JsonElement?): String {
    val value = element as? JsonPrimitive ?: invalidNewsResponse()
    if (!value.isString) invalidNewsResponse()
    return value.content
}
private fun newsNullableString(element: JsonElement?): String? = if (element === JsonNull) null else newsString(element)
private fun newsCategory(element: JsonElement?): NewsCategory {
    val name = newsString(element)
    return NewsCategory.entries.firstOrNull { it.name == name } ?: invalidNewsResponse()
}
private fun newsLong(element: JsonElement?): Long {
    val value = element as? JsonPrimitive ?: invalidNewsResponse()
    if (value.isString || !NEWS_JSON_NUMBER.matches(value.content)) invalidNewsResponse()
    return try { BigDecimal(value.content).longValueExact() }
    catch (_: NumberFormatException) { invalidNewsResponse() }
    catch (_: ArithmeticException) { invalidNewsResponse() }
}
private fun newsInt(element: JsonElement?): Int {
    val value = newsLong(element)
    if (value !in Int.MIN_VALUE..Int.MAX_VALUE) invalidNewsResponse()
    return value.toInt()
}
private fun newsBoolean(element: JsonElement?): Boolean {
    val value = element as? JsonPrimitive ?: invalidNewsResponse()
    if (value.isString) invalidNewsResponse()
    return when (value.content) { "true" -> true; "false" -> false; else -> invalidNewsResponse() }
}

private fun newsItems(element: JsonElement?): List<NewsListItem> = newsArray(element).map {
    val item = newsObject(it)
    NewsListItem(newsLong(item["id"]), newsString(item["title"]), newsCategory(item["category"]),
        newsNullableString(item["imageUrl"]), newsNullableString(item["publishedAt"]))
}
