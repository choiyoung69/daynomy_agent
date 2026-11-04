package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import okhttp3.mockwebserver.*
import java.util.concurrent.CopyOnWriteArrayList
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith

/** Today's dashboard and explicit news search remain separate from stock discovery. */
@RunWith(AndroidJUnit4::class)
class TodayNewsScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var todayFails = false
    @Volatile private var todayEmpty = false
    @Volatile private var searchFails = false
    @Volatile private var searchEmpty = false
    private fun json(body: String, status: Int = 200) = MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)
    private fun item(id: Int) = """{"id":$id,"title":"뉴스 $id","category":"STOCK","imageUrl":null,"publishedAt":"2026-11-04T00:00:00Z"}"""
    private fun page(items: String, size: Int = 6) = """{"items":[$items],"page":1,"size":$size,"totalPages":${if (items.isEmpty()) 0 else 1},"totalElements":${items.count { it == '}' }},"hasNext":false}"""
    @Before fun setup() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/portfolio" -> json("""{"holdings":[],"totalRealizedProfitLoss":0}""")
                    "/api/portfolio/histories" -> json("[]")
                    "/api/news" -> json(page(item(1)))
                    "/api/news/today" -> if (todayFails) json("""{"message":"private today diagnostic"}""", 503)
                        else json(page(if (todayEmpty) "" else (42..45).joinToString(",") { item(it) }, 9))
                    "/api/search/news" -> if (searchFails) json("""{"message":"private search diagnostic"}""", 503)
                        else json("""{"content":[${if (searchEmpty) "" else item(81)}],"page":1,"size":6,"totalElements":${if (searchEmpty) 0 else 1},"totalPages":${if (searchEmpty) 0 else 1}}""")
                    "/api/news/42", "/api/news/81" -> {
                        val id = request.requestUrl!!.encodedPath.substringAfterLast('/')
                        json("""{"id":$id,"title":"뉴스 $id","category":"STOCK","publishedAt":"2026-11-04T00:00:00Z","content":"독립 뉴스 본문","sources":[]}""")
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
    }
    @After fun stop() { server.shutdown() }
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun await(tag: String) { compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun openNews() { await("tab-news"); compose.onNodeWithTag("tab-news").performClick() }
    private fun search(query: String) {
        compose.onNodeWithTag("news-query").performScrollTo().performTextReplacement(query)
        compose.onNodeWithTag("news-search").performScrollTo().performClick()
    }
    private fun capture(name: String, showSearch: Boolean = false) {
        compose.onNode(hasScrollAction() and hasAnyDescendant(hasTestTag("news-query")))
            .performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, -100_000f) }
        if (showSearch) compose.onNodeWithTag("news-item-81").performScrollTo().assertIsDisplayed()
        compose.waitForIdle()
        val instrumentation = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.waitForIdle(500, 5_000)
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        java.io.FileOutputStream(java.io.File(instrumentation.targetContext.getExternalFilesDir(null), "$name.png")).use {
            bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap.recycle()
    }
    @Test fun dashboardPreviewExpandsAndDetailBackRotationKeepListAndSearchIndependent() {
        launch().use { scenario ->
            openNews(); await("news-today-42"); await("news-item-1")
            compose.onNodeWithTag("news-today-summary").assertExists()
            compose.onNodeWithTag("news-today-45").assertDoesNotExist()
            capture("context-dashboard")
            compose.onNodeWithTag("news-today-more").performScrollTo().performClick()
            compose.onNodeWithTag("news-today-45").assertExists()
            compose.onNodeWithTag("news-today-42").performScrollTo().performClick(); await("news-detail")
            compose.onNodeWithText("독립 뉴스 본문").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-1")
            scenario.recreate(); await("news-today-42"); await("news-item-1")
            compose.onNodeWithTag("news-mode-today").assertDoesNotExist()
            compose.onNodeWithTag("query").assertDoesNotExist()
            assertFalse(requests.any { it.requestUrl?.encodedPath == "/api/search/news" })
            search("반도체 & ETF"); await("news-item-81")
            capture("context-search", showSearch = true)
            compose.onNodeWithTag("news-today-42").assertExists()
            val request = requests.last { it.requestUrl?.encodedPath == "/api/search/news" }
            assertEquals("반도체 & ETF", request.requestUrl!!.queryParameter("q"))
            assertEquals("LATEST", request.requestUrl!!.queryParameter("sort"))
            assertFalse(requests.any { it.requestUrl?.encodedPath == "/api/stocks" })
            compose.onNodeWithTag("news-item-81").performScrollTo().performClick(); await("news-detail")
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-81")
        }
    }
    @Test fun dashboardFailureAndEmptyRecoveryDoNotReplaceNewsSearchResults() {
        todayFails = true
        launch().use {
            openNews(); await("news-today-retry"); await("news-item-1")
            search("합성 뉴스"); await("news-item-81")
            compose.onNodeWithTag("news-today-retry").assertExists()
            compose.onNodeWithText("private today diagnostic").assertDoesNotExist()
            todayFails = false; todayEmpty = true
            compose.onNodeWithTag("news-today-retry").performScrollTo().performClick()
            compose.waitUntil(10_000) { compose.onAllNodesWithText("오늘 발행된 뉴스가 없습니다.").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("news-item-81").assertExists()
            assertEquals(2, requests.count { it.requestUrl?.encodedPath == "/api/news/today" })
        }
    }
    @Test fun searchFailureAndEmptyRecoveryDoNotReplaceTodayDashboard() {
        searchFails = true
        launch().use {
            openNews(); await("news-today-42"); await("news-item-1")
            search("오류 검증"); await("news-error")
            compose.onNodeWithTag("news-today-42").assertExists()
            compose.onNodeWithTag("news-item-1").assertDoesNotExist()
            compose.onNodeWithText("private search diagnostic").assertDoesNotExist()
            searchFails = false; searchEmpty = true
            compose.onNodeWithTag("news-retry").performScrollTo().performClick(); await("news-empty")
            compose.onNodeWithTag("news-today-42").assertExists()
            compose.onNodeWithTag("news-item-81").assertDoesNotExist()
            assertEquals(2, requests.count { it.requestUrl?.encodedPath == "/api/search/news" })
            assertFalse(requests.any { it.requestUrl?.encodedPath == "/api/stocks" })
        }
    }
}
