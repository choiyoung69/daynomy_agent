package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CopyOnWriteArrayList
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Independent acceptance checks. Values deliberately differ from the approved design image. */
@RunWith(AndroidJUnit4::class)
class ApprovedPortfolioScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var readStatus = 200
    @Volatile private var calculationStatus = 200
    @Volatile private var signedIn = true
    @Volatile private var calculation = completeCalculation

    private fun json(body: String, status: Int = 200) = MockResponse()
        .setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)

    @Before fun fixture() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/auth/csrf" -> json("""{"headerName":"X-XSRF-TOKEN","parameterName":"_csrf","token":"synthetic-csrf"}""")
                        .addHeader("Set-Cookie", "XSRF-TOKEN=synthetic-csrf; Path=/")
                    "/api/auth/refresh" -> json("""{"code":"INVALID_REFRESH_TOKEN","message":"로그인이 필요합니다"}""", 401)
                    "/api/users/me" -> if (signedIn) json("""{"id":7,"email":"synthetic@example.invalid","name":null,"nickname":"검증회원","role":"USER"}""")
                        else json("""{"code":"UNAUTHORIZED","message":"synthetic session expired"}""", 401)
                    "/api/portfolio" -> if (readStatus == 200) json(savedPortfolio)
                        else json("""{"code":"${if (readStatus == 401) "UNAUTHORIZED" else "UNAVAILABLE"}","message":"synthetic read failure"}""", readStatus)
                    "/api/portfolio/histories" -> json("[]")
                    "/api/portfolio/calculate" -> json(calculation, calculationStatus)
                    "/api/stocks" -> json("""{"stocks":[]}""")
                    else -> json("[]")
                }
            }
        }
        server.start()
    }

    @After fun shutdown() { server.shutdown() }

    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java)
            .putExtra("base_url", server.url("/").toString()))
    }

    private fun awaitText(value: String) {
        compose.waitUntil(10_000) {
            compose.onAllNodesWithText(value, substring = true).fetchSemanticsNodes().isNotEmpty()
        }
    }

    private fun evaluate() {
        awaitText("검증용 보유종목")
        compose.onNodeWithTag("portfolio-evaluate").performScrollTo().performClick()
    }

    private fun captureNormalPortfolio() {
        compose.onNode(hasScrollAction() and hasAnyDescendant(hasTestTag("portfolio-summary")))
            .performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, -100_000f) }
        compose.waitForIdle()
        val instrumentation = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        val file = java.io.File(instrumentation.targetContext.getExternalFilesDir(null), "approved-normal.png")
        java.io.FileOutputStream(file).use {
            bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap.recycle()
    }

    @Test fun explicitEvaluationBindsServerAmountsAndPrivacyMasksThem() {
        launch().use {
            awaitText("검증용 보유종목")
            assertEquals(0, requests.count { it.requestUrl?.encodedPath == "/api/portfolio/calculate" })
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("평가 조회 필요", substring = true)
            evaluate()
            awaitText("987,654.32")
            compose.onNodeWithTag("portfolio-summary-amount").performScrollTo().assertTextContains("987,654.32", substring = true)
            compose.onNodeWithTag("portfolio-summary-profit").assertTextContains("-1,234.56", substring = true)
                .assertTextContains("-0.12%", substring = true)
            compose.onNodeWithText("988,888.88원", substring = true).assertExists()
            compose.onNodeWithText("2026-11-03", substring = true).assertExists()
            captureNormalPortfolio()
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().performClick()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("••••••", substring = true)
            compose.onNodeWithTag("portfolio-summary-profit").assertTextContains("••••••", substring = true)
            compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("-1,234.56", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("-0.12%", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("988,888.88", substring = true).assertCountEquals(0)
            compose.onNodeWithTag("portfolio-summary-toggle").performClick()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("987,654.32", substring = true)
            assertEquals(1, requests.count { it.requestUrl?.encodedPath == "/api/portfolio/calculate" })
            assertTrue(requests.none { it.requestUrl?.encodedPath == "/api/portfolio/transactions" })
        }
    }

    @Test fun partialEvaluationDoesNotInventTotalOrReturnRate() {
        calculation = """{"pricingStatus":"PARTIAL","totalPurchaseAmount":988888.88,"totalEvaluationAmount":null,"totalProfitLoss":null,"dailyProfitLoss":null,"totalReturnRate":null,"baseDate":null,"holdings":[]}"""
        launch().use {
            evaluate()
            awaitText("일부 종목의 가격을 확인하지 못했습니다")
            compose.onNodeWithTag("portfolio-summary-amount").performScrollTo().assertTextContains("—", substring = true)
            compose.onNodeWithTag("portfolio-summary-profit").assertTextContains("—", substring = true)
            compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("0%").assertCountEquals(0)
        }
    }

    @Test fun privacySurvivesBottomNavigationAndSubsequentEvaluation() {
        launch().use {
            evaluate()
            awaitText("987,654.32")
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().performClick()
            compose.onNodeWithTag("tab-news").performClick()
            compose.onNodeWithTag("tab-portfolio").performClick()
            awaitText("검증용 보유종목")
            // Returning refreshes holdings; evaluate the fresh holdings explicitly.
            compose.onNodeWithTag("portfolio-evaluate").performScrollTo().performClick()
            compose.waitUntil(10_000) {
                requests.count { it.requestUrl?.encodedPath == "/api/portfolio/calculate" } == 2 &&
                    compose.onAllNodesWithTag("portfolio-evaluate").fetchSemanticsNodes().isEmpty()
            }
            compose.onNodeWithTag("portfolio-summary-amount").performScrollTo()
                .assertTextContains("••••••", substring = true)
            compose.onNodeWithTag("portfolio-summary-profit").assertTextContains("••••••", substring = true)
            compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().performClick()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("987,654.32", substring = true)
        }
    }

    private fun failReevaluation(status: Int) {
        evaluate()
        awaitText("987,654.32")
        calculationStatus = status
        if (status == 401) signedIn = false
        calculation = """{"code":"${if (status == 401) "UNAUTHORIZED" else "UNAVAILABLE"}","message":"synthetic evaluation failure"}"""
        compose.onNodeWithTag("portfolio-analysis-toggle").performScrollTo().performClick()
        compose.onNodeWithTag("portfolio-reevaluate").performScrollTo().performClick()
    }

    @Test fun failedReevaluationDoesNotKeepAnEarlierNormalTotal() {
        launch().use {
            failReevaluation(503)
            awaitText("요청을 처리하지 못했습니다")
            compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("-1,234.56", substring = true).assertCountEquals(0)
            compose.onNodeWithTag("portfolio-summary-amount").performScrollTo()
                .assertTextContains("평가 조회 필요", substring = true)
        }
    }

    @Test fun expiredSessionDuringReevaluationRemovesPriorAccountData() {
        launch().use {
            failReevaluation(401)
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("portfolio-login").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("portfolio-summary").assertDoesNotExist()
            compose.onNodeWithText("검증용 보유종목", substring = true).assertDoesNotExist()
            compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("-1,234.56", substring = true).assertCountEquals(0)
            compose.onNodeWithTag("portfolio-login").performScrollTo().performClick()
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("account-login").fetchSemanticsNodes().isNotEmpty() }
        }
    }

    @Test fun unauthorizedReadHasNoSyntheticSummaryOrHoldingAndRoutesToAccount() {
        readStatus = 401
        launch().use {
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("portfolio-login").fetchSemanticsNodes().isNotEmpty() }
            assertUnavailableRead()
            compose.onNodeWithTag("portfolio-login").performScrollTo().performClick()
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("account-profile").fetchSemanticsNodes().isNotEmpty() }
        }
    }

    @Test fun unavailableReadIsNotRenderedAsNormalOrEmptyPortfolio() {
        readStatus = 503
        launch().use {
            awaitText("보유자산·거래 내역을 확인하지 못했습니다")
            assertUnavailableRead()
            compose.onNodeWithText("보유 중인 자산이 없어요").assertDoesNotExist()
        }
    }

    private fun assertUnavailableRead() {
        compose.onNodeWithTag("portfolio-summary").assertDoesNotExist()
        compose.onNodeWithTag("portfolio-summary-amount").assertDoesNotExist()
        compose.onNodeWithText("검증용 보유종목", substring = true).assertDoesNotExist()
        compose.onAllNodesWithText("987,654.32", substring = true).assertCountEquals(0)
        compose.onNodeWithTag("transaction-open").assertIsNotEnabled()
        assertEquals(0, requests.count { it.requestUrl?.encodedPath == "/api/portfolio/calculate" })
    }

    @Test fun approvedHierarchyKeepsSearchNavigationTabsAndExplicitTradeAvailable() {
        launch().use {
            awaitText("검증용 보유종목")
            compose.onNodeWithTag("query").assertIsDisplayed()
            val search = compose.onNodeWithTag("query").fetchSemanticsNode().boundsInRoot
            val navigation = compose.onNodeWithTag("bottom-navigation").fetchSemanticsNode().boundsInRoot
            assertTrue(navigation.top > search.bottom)
            compose.onNodeWithTag("tab-portfolio").assertTextContains("포트폴리오")
            compose.onNodeWithTag("tab-news").assertTextContains("이슈")
            compose.onNodeWithTag("tab-account").assertTextContains("내 계정")
            compose.onNodeWithTag("portfolio-history-tab").performScrollTo().performClick()
            awaitText("조회 기간에 거래·조정 내역이 없습니다")
            compose.onNodeWithTag("portfolio-holdings-tab").performScrollTo().performClick()
            compose.onNodeWithText("검증용 보유종목").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("transaction-open").performScrollTo().performClick()
            compose.onNodeWithTag("transaction-close").assertIsDisplayed().performClick()
            compose.onNodeWithTag("transaction-asset").assertDoesNotExist()
        }
    }

    companion object {
        private const val savedPortfolio = """{"holdings":[{"assetId":777,"assetCode":"TEST777","name":"검증용 보유종목","quantity":4,"averagePurchasePrice":247222.22,"currency":"KRW","market":"KOSPI"}],"totalRealizedProfitLoss":321.09}"""
        private const val completeCalculation = """{"pricingStatus":"COMPLETE","totalPurchaseAmount":988888.88,"totalEvaluationAmount":987654.32,"totalProfitLoss":-1234.56,"dailyProfitLoss":-456.78,"totalReturnRate":-0.12,"baseDate":"2026-11-03","holdings":[{"assetId":777,"name":"검증용 보유종목","quantity":4,"averagePurchasePrice":247222.22,"purchaseAmount":988888.88,"evaluationAmount":987654.32,"profitLoss":-1234.56,"returnRate":-0.12,"weight":100,"priceAvailable":true,"baseDate":"2026-11-03"}]}"""
    }
}
