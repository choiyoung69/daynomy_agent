package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CopyOnWriteArrayList
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NewsMarketAnalysisScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var failing = false
    @Volatile private var absent = false

    @Before fun setup() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.path.orEmpty()) {
                    "/api/news?page=1&size=6" -> json("""{"items":[{"id":42,"title":"경제 뉴스","category":"STOCK","imageUrl":null,"publishedAt":null}],"page":1,"size":6,"totalPages":1,"totalElements":1,"hasNext":false}""")
                    "/api/news/42" -> json("""{"id":42,"title":"경제 상세","category":"STOCK","publishedAt":"2026-11-04","content":"상세 본문 유지","sources":[]}""")
                    "/api/news/42/keywords" -> json("""{"keywords":[{"category":"POLICY","keyword":"기준금리","points":["금리 뜻","기사 속 맥락","키워드 지표"],"definition":"금리 뜻","context":"기사 속 맥락","watchPoint":"키워드 지표"}]}""")
                    "/api/news/42/market-analysis" -> when {
                        failing -> json("""{"code":"UNAVAILABLE","message":"private-analysis-body"}""").setResponseCode(503)
                        absent -> json("""{"code":"MARKET_ANALYSIS_NOT_FOUND","message":"해당 뉴스의 시장 분석을 찾을 수 없습니다."}""").setResponseCode(404)
                        else -> json("""{"risk":"변동성 확대 😀","watchPoint":"후속 물가 지표"}""")
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
    }
    @After fun stop() { server.shutdown() }
    private fun json(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun await(tag: String) { compose.waitUntil(8000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun open() {
        await("tab-news"); compose.onNodeWithTag("tab-news").performClick()
        await("news-item-42"); compose.onNodeWithTag("news-item-42").performScrollTo().performClick()
        await("news-detail")
    }
    private fun analysisRequests() = requests.filter { it.path == "/api/news/42/market-analysis" }
    private fun assertArticleAndKeywords() {
        await("news-keywords")
        compose.onNodeWithText("상세 본문 유지").assertExists()
        compose.onNodeWithText("기준금리 · 정책").assertExists()
    }
    private fun assertSuccess() {
        await("news-analysis")
        compose.onNodeWithText("시장 분석").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("위험과 불확실성: 변동성 확대 😀").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("확인할 점: 후속 물가 지표").performScrollTo().assertIsDisplayed()
    }

    @Test fun successReloadsOnRotationAndClearsOnBack() {
        launch().use { scenario ->
            open(); assertSuccess(); assertArticleAndKeywords()
            assertEquals(1, analysisRequests().size)
            analysisRequests().single().let {
                assertEquals("GET", it.method); assertEquals(0L, it.bodySize)
                assertNull(it.getHeader("Authorization")); assertNull(it.requestUrl!!.query)
            }
            scenario.recreate(); assertSuccess()
            assertEquals(2, analysisRequests().size)
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-42")
            compose.onNodeWithTag("news-analysis").assertDoesNotExist()
            compose.onNodeWithTag("news-analysis-empty").assertDoesNotExist()
            compose.onNodeWithTag("news-analysis-error").assertDoesNotExist()
            assertEquals(2, analysisRequests().size)
            assertTrue(requests.all { it.method == "GET" })
        }
    }

    @Test fun failureKeepsArticleAndKeywordsAndExplicitRetryRecovers() {
        failing = true
        launch().use {
            open(); await("news-analysis-error"); assertArticleAndKeywords()
            compose.onNodeWithText("private-analysis-body").assertDoesNotExist()
            compose.onNodeWithTag("news-analysis-empty").assertDoesNotExist()
            assertEquals(1, analysisRequests().size)
            val detailCalls = requests.count { it.path == "/api/news/42" }
            val keywordCalls = requests.count { it.path == "/api/news/42/keywords" }
            failing = false
            compose.onNodeWithTag("news-analysis-retry").performScrollTo().performClick()
            assertSuccess(); assertArticleAndKeywords()
            compose.onNodeWithTag("news-analysis-error").assertDoesNotExist()
            assertEquals(2, analysisRequests().size)
            assertEquals(detailCalls, requests.count { it.path == "/api/news/42" })
            assertEquals(keywordCalls, requests.count { it.path == "/api/news/42/keywords" })
        }
    }

    @Test fun exactNotFoundShowsNormalAbsenceWithoutRetryAndKeepsOtherContent() {
        absent = true
        launch().use {
            open(); await("news-analysis-empty"); assertArticleAndKeywords()
            compose.onNodeWithTag("news-analysis-empty").performScrollTo()
                .assertTextEquals("이 뉴스에 제공되는 시장 분석이 없습니다.")
            compose.onNodeWithTag("news-analysis-error").assertDoesNotExist()
            compose.onNodeWithTag("news-analysis-retry").assertDoesNotExist()
            compose.onNodeWithTag("news-analysis").assertDoesNotExist()
            assertEquals(1, analysisRequests().size)
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-42")
            compose.onNodeWithTag("news-analysis-empty").assertDoesNotExist()
        }
    }
}
