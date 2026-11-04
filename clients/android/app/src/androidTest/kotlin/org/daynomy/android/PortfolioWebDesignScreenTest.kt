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
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Native Compose journeys, independent of JVM tests. All account data is synthetic. */
@RunWith(AndroidJUnit4::class)
class PortfolioWebDesignScreenTest {
    @get:Rule val compose=createEmptyComposeRule()
    private lateinit var server:MockWebServer
    private val requests=CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var portfolioStatus=200
    @Volatile private var portfolioBody="""{"holdings":[],"totalRealizedProfitLoss":0}"""
    @Volatile private var loggedIn=true
    @Volatile private var nickname="초기회원"
    private fun json(body:String,status:Int=200)=MockResponse().setResponseCode(status).setHeader("Content-Type","application/json").setBody(body)
    private fun profile()=json("""{"id":7,"email":"synthetic@example.invalid","name":null,"nickname":"$nickname","role":"USER"}""")
    @Before fun fixture() {
        server=MockWebServer(); server.dispatcher=object:Dispatcher() {
            override fun dispatch(request:RecordedRequest):MockResponse {
                requests+=request
                return when(request.requestUrl?.encodedPath) {
                    "/api/auth/csrf" -> json("""{"headerName":"X-XSRF-TOKEN","parameterName":"_csrf","token":"fixture-csrf"}""").addHeader("Set-Cookie","XSRF-TOKEN=fixture-csrf; Path=/")
                    "/api/auth/refresh" -> json("""{"code":"INVALID_REFRESH_TOKEN","message":"로그인이 필요합니다"}""",401)
                    "/api/auth/logout" -> { loggedIn=false; MockResponse().setResponseCode(204) }
                    "/api/users/me" -> when {
                        !loggedIn -> json("""{"code":"UNAUTHORIZED","message":"로그인이 필요합니다"}""",401)
                        request.method=="PATCH" -> { nickname="변경회원"; profile() }
                        else -> profile()
                    }
                    "/api/stocks" -> json("""{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"}]}""")
                    "/api/portfolio" -> json(portfolioBody,portfolioStatus)
                    "/api/portfolio/calculate" -> json("""{"pricingStatus":"PARTIAL","totalPurchaseAmount":200,"totalEvaluationAmount":null,"totalProfitLoss":null,"dailyProfitLoss":null,"totalReturnRate":null,"baseDate":null}""")
                    "/api/portfolio/histories" -> json("[]")
                    "/api/portfolio/transactions" -> MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)
                    else -> json("[]")
                }
            }
        }; server.start()
    }
    @After fun shutdown() { server.shutdown() }
    private fun launch():ActivityScenario<MainActivity> {
        val context=ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context,MainActivity::class.java).putExtra("base_url",server.url("/").toString()))
    }
    private fun capture(name:String) {
        compose.waitForIdle()
        val instrumentation=androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        val image=instrumentation.uiAutomation.takeScreenshot()
        val file=java.io.File(instrumentation.targetContext.getExternalFilesDir(null),name+".png")
        java.io.FileOutputStream(file).use { image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it) }
        image.recycle()
    }
    private fun awaitTag(tag:String) { compose.waitUntil(10000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun fill(tag:String,value:String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }

    @Test fun dashboardUsesWebHierarchyAndOpensTradeExplicitly() {
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            awaitTag("portfolio-summary")
            compose.onNodeWithTag("transaction-asset").assertDoesNotExist()
            capture("portfolio-dashboard-empty")
            compose.onNodeWithText("보유 중인 자산이 없어요").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("portfolio-holdings-tab").performScrollTo().performClick()
            compose.onNodeWithTag("portfolio-history-tab").performScrollTo().performClick()
            compose.onNodeWithText("조회 기간에 거래·조정 내역이 없습니다.").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("transaction-open").performScrollTo().performClick()
            awaitTag("transaction-asset")
            compose.onNodeWithTag("transaction-close").assertIsDisplayed()
            capture("portfolio-trade-editor")
            compose.onNodeWithTag("transaction-close").performClick()
            compose.onNodeWithTag("transaction-asset").assertDoesNotExist()
        }
    }

    @Test fun summaryPrivacyDoesNotPretendUnavailableValuationIsZero() {
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            awaitTag("portfolio-summary")
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().performClick()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("••••••", substring=true)
            compose.onNodeWithTag("portfolio-summary-toggle").performClick()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("0원")
            compose.onNodeWithText("포트폴리오 AI 분석",substring=true).assertDoesNotExist()
        }
    }
    @Test fun failedReadIsNotAnEmptyOrZeroPortfolio() {
        portfolioStatus=503; portfolioBody="""{"code":"UNAVAILABLE","message":"synthetic error"}"""
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            compose.waitUntil(10000) { compose.onAllNodesWithText("보유자산·거래 내역을 확인하지 못했습니다.").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("portfolio-summary").assertDoesNotExist()
            compose.onNodeWithText("보유 중인 자산이 없어요").assertDoesNotExist()
            compose.onNodeWithTag("transaction-open").assertIsNotEnabled()
        }
    }

    @Test fun unauthorizedReadOffersRealAccountRouteInsteadOfGuestStorage() {
        portfolioStatus=401; portfolioBody="""{"code":"UNAUTHORIZED","message":"synthetic unauthorized"}"""
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            awaitTag("portfolio-login")
            compose.onNodeWithTag("portfolio-summary").assertDoesNotExist()
            compose.onNodeWithTag("portfolio-login").performScrollTo().performClick()
            awaitTag("account-profile")
        }
    }

    @Test fun partialValuationDoesNotInventACompleteTotal() {
        portfolioBody="""{"holdings":[{"assetId":1,"name":"삼성전자","quantity":2,"averagePurchasePrice":100}],"totalRealizedProfitLoss":0}"""
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            compose.waitUntil(10000) { compose.onAllNodesWithText("평가 조회 필요").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("portfolio-evaluate").performScrollTo().performClick()
            compose.waitUntil(10000) { compose.onAllNodesWithText("일부 종목의 가격을 확인하지 못했습니다. 미평가 금액은 —로 표시합니다.").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("portfolio-summary-amount").performScrollTo().assertTextContains("—")
            capture("portfolio-partial-valuation")
            assertEquals(1,requests.count { it.requestUrl?.encodedPath=="/api/portfolio/calculate" })
        }
    }
    @Test fun dashboardStateSurvivesRecreationAndBackClosesEditor() {
        launch().use { scenario ->
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            compose.waitUntil(10000) { compose.onAllNodesWithText("보유 중인 자산이 없어요").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().performClick()
            scenario.recreate(); awaitTag("portfolio-summary")
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("••••••",substring=true)
            compose.onNodeWithTag("transaction-open").performScrollTo().performClick(); awaitTag("transaction-asset")
            androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK); compose.waitForIdle()
            compose.onNodeWithTag("transaction-asset").assertDoesNotExist()
            compose.onNodeWithTag("portfolio-summary-amount").assertTextContains("••••••",substring=true)
        }
    }

    @Test fun landscapeKeepsSummaryAndTradeReachable() {
        launch().use { scenario ->
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick()
            scenario.onActivity { it.requestedOrientation=android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE }
            awaitTag("portfolio-summary")
            compose.onNodeWithTag("portfolio-summary-toggle").performScrollTo().assertIsDisplayed()
            capture("portfolio-landscape")
            compose.onNodeWithTag("transaction-open").performScrollTo().performClick(); awaitTag("transaction-asset")
            compose.onNodeWithTag("transaction-close").performScrollTo().performClick()
            scenario.onActivity { it.requestedOrientation=android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT }
        }
    }
    @Test fun threeBottomTabsAndPortfolioSearchEntryUseRealScreens() {
        launch().use {
            awaitTag("bottom-navigation")
            compose.onNodeWithTag("tab-portfolio").assertTextContains("포트폴리오",substring=true)
            compose.onNodeWithTag("tab-news").assertTextContains("이슈",substring=true)
            compose.onNodeWithTag("tab-account").assertTextContains("내 계정",substring=true)
            compose.onNodeWithTag("tab-market").assertDoesNotExist()
            compose.onNodeWithTag("query").assertDoesNotExist()
            compose.onNodeWithTag("portfolio-stock-search").performScrollTo().performClick()
            awaitTag("query")
            compose.onNodeWithTag("query").performTextReplacement("삼성전자")
            awaitTag("stock-1")
            compose.onNodeWithTag("stock-1").performScrollTo().performClick()
            compose.onNodeWithTag("clear-selection").assertExists()
            compose.onNodeWithTag("query").performTextReplacement("삼성")
            awaitTag("stock-1")
            compose.onNodeWithTag("tab-news").performClick()
            compose.onNodeWithTag("query").assertDoesNotExist()
            compose.onNodeWithTag("tab-account").performClick(); awaitTag("account-profile")
            capture("portfolio-bottom-navigation")
        }
    }
}
