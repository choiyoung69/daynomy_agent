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
import okhttp3.mockwebserver.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Shell acceptance journeys use synthetic account and article data only. */
@RunWith(AndroidJUnit4::class)
class ShellDesignScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var signedIn = true
    @Volatile private var accountFails = false
    @Volatile private var newsFails = false
    @Volatile private var rejectNickname = false
    @Volatile private var nickname = "디자인검증회원"
    private fun json(body: String, status: Int = 200) = MockResponse()
        .setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)
    private fun profile() = json("""{"id":17,"email":"shell@example.invalid","name":null,"nickname":"$nickname","role":"USER"}""")
    private fun page(id: Int, current: Int = 1) = """{"items":[{"id":$id,"title":"검증용 경제 소식 $id","category":"STOCK","imageUrl":null,"publishedAt":"2026-11-04T00:00:00Z"}],"page":$current,"size":6,"totalPages":2,"totalElements":7,"hasNext":${current == 1}}"""

    @Before fun fixture() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/auth/csrf" -> json("""{"headerName":"X-XSRF-TOKEN","parameterName":"_csrf","token":"synthetic-shell-csrf"}""")
                        .addHeader("Set-Cookie", "XSRF-TOKEN=synthetic-shell-csrf; Path=/")
                    "/api/auth/refresh" -> json("""{"code":"INVALID_REFRESH_TOKEN","message":"로그인이 필요합니다"}""", 401)
                    "/api/auth/logout" -> { signedIn = false; MockResponse().setResponseCode(204) }
                    "/api/users/me" -> when {
                        accountFails -> json("""{"code":"UNAVAILABLE","message":"private account diagnostic"}""", 503)
                        !signedIn -> json("""{"code":"UNAUTHORIZED","message":"로그인이 필요합니다"}""", 401)
                        request.method == "PATCH" && rejectNickname -> json("""{"code":"UNAUTHORIZED","message":"synthetic expired session"}""", 401)
                        request.method == "PATCH" -> { nickname = "변경검증회원"; profile() }
                        else -> profile()
                    }
                    "/api/portfolio" -> json("""{"holdings":[],"totalRealizedProfitLoss":0}""")
                    "/api/portfolio/histories" -> json("[]")
                    "/api/stocks" -> json("""{"stocks":[{"assetId":88,"assetCode":"AAPL","name":"검증용 미국종목","category":"STOCK","market":"NASDAQ","currency":"USD"}]}""")
                    "/api/news" -> if (newsFails) json("""{"code":"UNAVAILABLE","message":"private news diagnostic"}""", 503)
                        else { val current = request.requestUrl?.queryParameter("page")?.toInt() ?: 1; json(page(if (current == 2) 72 else 71, current)) }
                    "/api/news/today" -> json(page(73))
                    "/api/news/71", "/api/news/72", "/api/news/73" -> {
                        val id = request.requestUrl!!.encodedPath.substringAfterLast('/')
                        json("""{"id":$id,"title":"검증용 경제 소식 $id","category":"STOCK","publishedAt":"2026-11-04T00:00:00Z","content":"독립 검증 본문입니다.","sources":[{"name":"합성 출처","url":"https://example.invalid/news"}]}""")
                    }
                    else -> json("[]")
                }
            }
        }
        server.start()
    }
    @After fun shutdown() { server.shutdown() }
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun await(tag: String) { compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun tab(name: String) { await("tab-$name"); compose.onNodeWithTag("tab-$name").performClick() }
    private fun assertShell() {
        compose.onNodeWithTag("query").assertDoesNotExist()
        compose.onNodeWithTag("bottom-navigation").assertIsDisplayed()
        listOf("portfolio", "news", "account").forEach { compose.onNodeWithTag("tab-$it").assertIsDisplayed() }
        compose.onNodeWithTag("tab-market").assertDoesNotExist()
    }
    private fun capture(name: String, contentTag: String) {
        compose.onNode(hasScrollAction() and hasAnyDescendant(hasTestTag(contentTag)))
            .performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, -100_000f) }
        compose.waitForIdle()
        val instrumentation = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        java.io.FileOutputStream(java.io.File(instrumentation.targetContext.getExternalFilesDir(null), "$name.png")).use {
            bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap.recycle()
    }

    @Test fun newsRetainsModesCategoryPagingDetailAndShell() {
        launch().use {
            tab("news"); await("news-item-71"); assertShell()
            capture("shell-news", "news-item-71")
            compose.onNodeWithTag("category-STOCK").performScrollTo().performClick()
            compose.waitUntil(10_000) { requests.any { it.requestUrl?.queryParameter("category") == "STOCK" } }
            await("news-item-71")
            compose.onNodeWithTag("news-next").performScrollTo().performClick(); await("news-item-72")
            compose.onNodeWithTag("news-item-72").performScrollTo().performClick(); await("news-detail")
            compose.onNodeWithText("독립 검증 본문입니다.").performScrollTo().assertIsDisplayed()
            assertShell()
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-72")
            await("news-today-73")
            compose.onNodeWithTag("news-today-73").performScrollTo().performClick(); await("news-detail")
            compose.onNodeWithTag("news-back").performScrollTo().performClick(); await("news-item-72")
            compose.onNodeWithTag("news-mode-all").assertDoesNotExist()
            compose.onNodeWithTag("news-mode-today").assertDoesNotExist()
            assertTrue(requests.any { it.requestUrl?.encodedPath == "/api/news/today" })
        }
    }

    @Test fun memberAccountPreservesRenameMenusAndLogout() {
        launch().use {
            await("portfolio-summary")
            compose.onNodeWithTag("portfolio-refresh").assertDoesNotExist()
            tab("account"); await("account-profile"); assertShell()
            compose.onNodeWithTag("account-profile").assertTextContains("디자인검증회원", substring = true)
            capture("shell-account", "account-profile")
            compose.onNodeWithTag("account-feedback").assertExists()
            compose.onNodeWithTag("tab-exchange").assertDoesNotExist()
            compose.onNodeWithTag("account-delete").assertExists()
            compose.onNodeWithTag("account-nickname").performScrollTo().performTextReplacement("변경검증회원")
            compose.onNodeWithTag("account-save").performScrollTo().performClick()
            compose.waitUntil(10_000) {
                compose.onAllNodes(hasTestTag("account-profile") and hasText("변경검증회원", substring = true)).fetchSemanticsNodes().isNotEmpty()
            }
            assertEquals(1, requests.count { it.method == "PATCH" && it.requestUrl?.encodedPath == "/api/users/me" })
            compose.onNodeWithTag("account-logout").performScrollTo().performClick(); await("account-login")
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            assertEquals(1, requests.count { it.requestUrl?.encodedPath == "/api/auth/logout" })
        }
    }

    @Test fun guestAccountKeepsFeedbackWithoutMemberOrExchangeActions() {
        signedIn = false
        launch().use {
            tab("account"); await("account-login"); assertShell()
            capture("shell-account-guest", "account-login")
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            compose.onNodeWithTag("account-save").assertDoesNotExist()
            compose.onNodeWithTag("account-delete").assertDoesNotExist()
            compose.onNodeWithTag("tab-exchange").assertDoesNotExist()
            compose.onNodeWithTag("account-feedback").performScrollTo().performClick(); await("feedback-content")
            compose.onNodeWithTag("feedback-close").performClick()
            compose.onNodeWithTag("account-login").assertExists()
        }
    }

    @Test fun nicknameUnauthorizedResponseLeavesLoginActionEnabled() {
        launch().use {
            tab("account"); await("account-profile")
            rejectNickname = true
            compose.onNodeWithTag("account-nickname").performScrollTo().performTextReplacement("변경검증회원")
            compose.onNodeWithTag("account-save").performScrollTo().performClick()
            await("account-login")
            compose.onNodeWithTag("account-login").performScrollTo().assertIsEnabled()
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            compose.onNodeWithTag("account-save").assertDoesNotExist()
            assertTrue(requests.any { it.method == "PATCH" && it.requestUrl?.encodedPath == "/api/users/me" })
        }
    }

    @Test fun contextualStockSearchAndUsdExchangeReturnKeepTradeDraft() {
        launch().use {
            tab("account"); await("account-profile")
            compose.onNodeWithTag("query").assertDoesNotExist()
            compose.onNodeWithTag("tab-exchange").assertDoesNotExist()
            tab("portfolio"); await("portfolio-stock-search")
            compose.onNodeWithTag("portfolio-stock-search").performScrollTo().performClick(); await("query")
            compose.onNodeWithTag("market-exchange").assertDoesNotExist()
            compose.onNodeWithTag("country-US").performScrollTo().performClick()
            compose.onNodeWithTag("query").performTextReplacement("AAPL")
            await("stock-88")
            compose.onNodeWithTag("market-exchange").performScrollTo().performClick(); await("exchange-date")
            compose.onNodeWithTag("query").assertDoesNotExist()
            compose.onNodeWithTag("exchange-back").performClick(); await("query")
            compose.onNodeWithTag("query").assertTextContains("AAPL")
            tab("portfolio"); await("transaction-open")
            compose.onNodeWithTag("transaction-open").performScrollTo().performClick(); await("transaction-asset")
            compose.onNodeWithTag("transaction-country-US").performScrollTo().performClick()
            compose.onNodeWithTag("transaction-asset").performScrollTo().performTextReplacement("AAPL")
            await("transaction-stock-88")
            compose.onNodeWithTag("transaction-stock-88").performScrollTo().performClick()
            compose.onNodeWithTag("transaction-quantity").performScrollTo().performTextReplacement("3")
            compose.onNodeWithTag("transaction-price").performScrollTo().performTextReplacement("217.45")
            compose.onNodeWithTag("transaction-date").performScrollTo().performTextReplacement("2026-10-23")
            compose.onNodeWithTag("transaction-rate").performScrollTo().performTextReplacement("1423.123456")
            compose.onNodeWithTag("transaction-exchange").performScrollTo().performClick(); await("exchange-date")
            compose.waitUntil(10_000) {
                compose.onAllNodes(hasTestTag("exchange-date") and hasText("2026-10-23", substring = true)).fetchSemanticsNodes().isNotEmpty() &&
                    requests.any { it.requestUrl?.encodedPath == "/api/exchange-rates/usd-krw" && it.requestUrl?.queryParameter("date") == "2026-10-23" }
            }
            compose.onNodeWithTag("exchange-date").assertTextContains("2026-10-23")
            compose.onNodeWithTag("exchange-back").performClick(); await("transaction-asset")
            compose.onNodeWithTag("transaction-quantity").assertTextContains("3")
            compose.onNodeWithTag("transaction-price").assertTextContains("217.45")
            compose.onNodeWithTag("transaction-rate").assertTextContains("1423.123456")
            compose.onNodeWithTag("transaction-date").assertTextContains("2026-10-23")
            compose.onNodeWithTag("transaction-selected").assertTextContains("AAPL", substring = true)
            assertTrue(requests.none { it.requestUrl?.encodedPath == "/api/portfolio/transactions" })
        }
    }

    @Test fun loginStartAndInvalidCallbackKeepLocalLoginRetryAvailable() {
        val instrumentation = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        val store = androidx.lifecycle.ViewModelStore()
        val baseUrl = server.url("/").toString()
        lateinit var model: CoreViewModel
        try {
            instrumentation.runOnMainSync {
                model = CoreViewModel(baseUrl)
                store.put("login-retry", model)
                model.loginUrl() // Exercise state only; never launch an external browser.
                assertTrue(model.accountRequiresLogin)
                assertFalse(model.busy)
                model.completeLogin("org.daynomy.app://auth/callback?state=invalid&code=invalid")
            }
            compose.waitUntil(10_000) { !model.busy && model.message == "로그인하지 못했습니다. 다시 시작해 주세요." }
            instrumentation.runOnMainSync {
                assertTrue(model.accountRequiresLogin)
                assertFalse(model.busy)
                assertNull(model.profile)
                model.loginUrl()
                assertTrue(model.accountRequiresLogin)
            }
            assertTrue(requests.none { it.requestUrl?.encodedPath?.startsWith("/api/auth/mobile/") == true })
        } finally {
            instrumentation.runOnMainSync { store.clear() }
        }
    }

    @Test fun errorsRemainErrorsAndNewsRetryRecoversWithoutFakeContent() {
        accountFails = true; newsFails = true
        launch().use {
            tab("account")
            compose.waitUntil(10_000) { compose.onAllNodesWithText("회원 정보를 확인하지 못했습니다.").fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            compose.onNodeWithTag("account-login").assertDoesNotExist()
            compose.onNodeWithText("private account diagnostic").assertDoesNotExist()
            assertShell()
            accountFails = false
            compose.onNodeWithTag("account-retry").performScrollTo().performClick(); await("account-profile")
            compose.onNodeWithTag("account-profile").assertTextContains("디자인검증회원", substring = true)
            tab("news"); await("news-error")
            compose.onNodeWithTag("news-empty").assertDoesNotExist()
            compose.onNodeWithTag("news-item-71").assertDoesNotExist()
            compose.onNodeWithText("private news diagnostic").assertDoesNotExist()
            newsFails = false
            compose.onNodeWithTag("news-retry").performScrollTo().performClick(); await("news-item-71")
            assertShell()
        }
    }
}
