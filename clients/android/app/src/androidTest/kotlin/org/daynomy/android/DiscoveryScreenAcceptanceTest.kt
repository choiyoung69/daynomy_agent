package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
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
class DiscoveryScreenAcceptanceTest {
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
                    "/api/news" -> {
                        val page = request.requestUrl?.queryParameter("page")?.toInt() ?: 1
                        val id = if (page == 2) 1 else 2
                        json("""{"items":[{"id":$id,"title":"화면 뉴스 $id","category":"STOCK","imageUrl":null,"publishedAt":"2026-10-23T00:00:00Z"}],"page":$page,"size":6,"totalPages":2,"totalElements":7,"hasNext":${page == 1}}""")
                    }
                    "/api/news/1", "/api/news/2" -> {
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

    @Test fun newsCategoryPaginationDetailAndBackUseNativeScreenAndKeepSelectedPage() {
        launch().use {
            awaitTag("tab-news"); compose.onNodeWithTag("tab-news").performClick()
            awaitTag("news-item-2")
            compose.onNodeWithTag("category-STOCK").performClick()
            compose.waitUntil(8000) { requests.any { it.requestUrl?.queryParameter("category") == "STOCK" } }
            awaitTag("news-item-2"); compose.onNodeWithTag("news-next").performClick()
            awaitTag("news-item-1"); compose.onNodeWithTag("news-item-1").performClick()
            awaitTag("news-detail"); compose.onNodeWithText("첫 상세 문단").assertIsDisplayed()
            compose.onNodeWithText("둘째 상세 문단").assertIsDisplayed()
            compose.onNodeWithTag("news-back").performClick()
            awaitTag("news-item-1"); compose.onNodeWithTag("news-item-1").assertIsDisplayed()
            assertTrue(requests.any { it.path == "/api/news/1" })
            assertTrue(requests.any { it.requestUrl?.queryParameter("page") == "2" && it.requestUrl?.queryParameter("category") == "STOCK" })
        }
    }

    @Test fun exchangeShowsActualFallbackDateAndExactRateAndSurvivesRecreation() {
        launch().use { scenario ->
            awaitTag("tab-exchange"); compose.onNodeWithTag("tab-exchange").performClick()
            awaitTag("exchange-date"); compose.onNodeWithTag("exchange-date").performTextReplacement("2026-10-25")
            assertFalse(requests.any { it.requestUrl?.encodedPath == "/api/exchange-rates/usd-krw" })
            compose.onNodeWithTag("exchange-load").performClick()
            awaitTag("exchange-value")
            compose.onNodeWithTag("exchange-value").assertTextContains("1423.123456", substring = true)
            compose.onNodeWithTag("exchange-value").assertTextContains("2026-10-23", substring = true)
            assertEquals("2026-10-25", requests.last { it.requestUrl?.encodedPath == "/api/exchange-rates/usd-krw" }.requestUrl!!.queryParameter("date"))
            scenario.recreate(); awaitTag("exchange-value")
            compose.onNodeWithTag("exchange-value").assertTextContains("1423.123456", substring = true)
        }
    }

    @Test fun exchangeErrorDoesNotBecomeAQuoteAndExplicitRetryRecovers() {
        exchangeFails = true
        launch().use {
            awaitTag("tab-exchange"); compose.onNodeWithTag("tab-exchange").performClick()
            awaitTag("exchange-date"); compose.onNodeWithTag("exchange-date").performTextReplacement("2026-10-25")
            compose.onNodeWithTag("exchange-load").performClick(); awaitTag("exchange-error")
            compose.onNodeWithTag("exchange-error").assertIsDisplayed()
            compose.onNodeWithTag("exchange-value").assertDoesNotExist()
            compose.onNodeWithText("private-provider-body").assertDoesNotExist()
            assertEquals(1, requests.count { it.requestUrl?.encodedPath == "/api/exchange-rates/usd-krw" })
            exchangeFails = false
            compose.onNodeWithTag("exchange-retry").performClick(); awaitTag("exchange-value")
            compose.onNodeWithTag("exchange-value").assertTextContains("1423.123456", substring = true)
            assertEquals(2, requests.count { it.requestUrl?.encodedPath == "/api/exchange-rates/usd-krw" })
        }
    }
}
