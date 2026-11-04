package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextReplacement
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CopyOnWriteArrayList
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Execute on Android: a JVM test result is not evidence for these screen journeys. */
@RunWith(AndroidJUnit4::class)
class NewsSearchScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var exchangeFails = false

    @Before fun server() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/search/news" -> json("""{"content":[{"id":42,"title":"금리 뉴스","category":"STOCK","imageUrl":null,"publishedAt":"2026-11-04T00:00:00Z"}],"page":1,"size":6,"totalElements":1,"totalPages":1}""")
                    "/api/news/today" -> json("""{"items":[],"page":1,"size":9,"totalPages":0,"totalElements":0,"hasNext":false}""")
                    "/api/news" -> {
                        val page = request.requestUrl?.queryParameter("page")?.toInt() ?: 1
                        val id = if (page == 2) 1 else 2
                        json("""{"items":[{"id":$id,"title":"화면 뉴스 $id","category":"STOCK","imageUrl":null,"publishedAt":"2026-10-23T00:00:00Z"}],"page":$page,"size":6,"totalPages":2,"totalElements":7,"hasNext":${page == 1}}""")
                    }
                    "/api/news/1", "/api/news/2", "/api/news/42" -> {
                        val id = request.requestUrl!!.encodedPath.substringAfterLast('/')
                        json("""{"id":$id,"title":"화면 뉴스 $id","category":"STOCK","publishedAt":"2026-10-23T00:00:00Z","content":"첫 상세 문단\n\n둘째 상세 문단","sources":[{"name":"테스트 출처","url":"https://example.invalid/source"}]}""")
                    }
                    "/api/exchange-rates/usd-krw" -> if (exchangeFails) json("""{"code":"EXCHANGE_RATE_UNAVAILABLE","message":"private-provider-body"}""").setResponseCode(503)
                        else json("""{"requestedDate":"2026-10-25","baseDate":"2026-10-23","rate":1423.123456,"baseCurrency":"USD","quoteCurrency":"KRW"}""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
    }
    @After fun stopServer() { server.shutdown() }
    private fun json(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun awaitTag(tag: String) { compose.waitUntil(8000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }

    @Test fun searchFiltersDetailClearAndRotationUseExistingNewsScreen() {
        launch().use { scenario ->
            awaitTag("tab-news"); compose.onNodeWithTag("tab-news").performClick()
            awaitTag("news-query")
            compose.onNodeWithTag("news-query").performScrollTo().performTextReplacement("금리 %_!")
            compose.onNodeWithTag("news-search").performScrollTo().performClick()
            awaitTag("news-item-42")
            compose.onNodeWithTag("news-sort-RELEVANCE").performScrollTo().performClick()
            compose.onNodeWithTag("category-STOCK").performScrollTo().performClick()
            compose.waitUntil(8000) { requests.any { it.requestUrl?.encodedPath == "/api/search/news" && it.requestUrl?.queryParameter("q") == "금리 %_!" && it.requestUrl?.queryParameter("category") == "STOCK" && it.requestUrl?.queryParameter("sort") == "RELEVANCE" } }
            awaitTag("news-item-42")
            scenario.recreate(); awaitTag("news-active-query")
            compose.onNodeWithTag("news-query").assertTextContains("금리 %_!")
            compose.onNodeWithTag("news-item-42").performScrollTo().performClick()
            awaitTag("news-detail")
            compose.onNodeWithTag("news-back").performScrollTo().performClick()
            awaitTag("news-item-42")
            compose.onNodeWithTag("news-query").performScrollTo().performTextReplacement("!!!")
            compose.onNodeWithTag("news-search").performScrollTo().performClick()
            awaitTag("news-query-error")
            assertFalse(requests.any { it.requestUrl?.queryParameter("q") == "!!!" })
            compose.onNodeWithTag("news-search-clear").performScrollTo().performClick()
            awaitTag("news-item-2")
        }
    }
}
