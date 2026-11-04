package org.daynomy.android

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
class GuestPortfolioScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<Pair<String, String>>()
    private fun json(body: String, status: Int = 200) = MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)
    @Before fun setup() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                requests += request.method.orEmpty() to path
                return when (path) {
                    "/api/portfolio", "/api/users/me", "/api/auth/refresh" -> json("""{"code":"UNAUTHORIZED","message":"로그인이 필요합니다."}""",401)
                    "/api/auth/csrf" -> json("""{"headerName":"X-XSRF-TOKEN","token":"guest-csrf"}""").addHeader("Set-Cookie","XSRF-TOKEN=guest-csrf; Path=/")
                    "/api/stocks" -> json("""{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"}]}""")
                    "/api/portfolio/calculate" -> json("""{"pricingStatus":"COMPLETE","totalPurchaseAmount":400000,"totalEvaluationAmount":444000,"totalProfitLoss":44000,"holdings":[{"assetId":1,"name":"삼성전자","baseDate":"2026-11-03"}]}""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
    }
    @After fun teardown() { server.shutdown() }
    @Test fun guestCanAddEvaluateRotateEditAndRemoveWithoutMemberWrites() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), MainActivity::class.java)
            .putExtra("base_url",server.url("/").toString())
        ActivityScenario.launch<MainActivity>(intent).use { scenario ->
            compose.waitUntil(15_000) { compose.onAllNodesWithTag("guest-portfolio").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("guest-query").performScrollTo().performTextInput("005930")
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("guest-stock-1").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("guest-stock-1").performScrollTo().performClick()
            compose.onNodeWithTag("guest-quantity").performScrollTo().performTextInput("2")
            compose.onNodeWithTag("guest-average").performScrollTo().performTextInput("200000")
            compose.onNodeWithTag("guest-save").performScrollTo().performClick()
            compose.onNodeWithTag("guest-evaluate").performScrollTo().performClick()
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("guest-evaluation").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithText("평가금액 444,000원").performScrollTo().assertIsDisplayed()
            scenario.recreate(); compose.waitForIdle()
            compose.onNodeWithTag("guest-evaluation").assertExists()
            compose.onNodeWithTag("guest-edit-1").performScrollTo().performClick()
            compose.onNodeWithTag("guest-quantity").performScrollTo().performTextClearance()
            compose.onNodeWithTag("guest-quantity").performTextInput("3")
            compose.onNodeWithTag("guest-save").performScrollTo().performClick()
            compose.onNodeWithTag("guest-evaluation").assertDoesNotExist()
            compose.onNodeWithTag("guest-remove-1").performScrollTo().performClick()
            compose.onNodeWithText("아직 담은 종목이 없습니다.").performScrollTo().assertIsDisplayed()
            assertTrue(requests.any { it == ("POST" to "/api/portfolio/calculate") })
            assertFalse(requests.any { it.first != "GET" && it.second.startsWith("/api/portfolio") && it.second != "/api/portfolio/calculate" })
        }
    }
}
