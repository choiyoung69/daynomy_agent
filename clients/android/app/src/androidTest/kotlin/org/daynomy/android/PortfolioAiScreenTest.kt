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
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith

/** F06 member UI acceptance. All narratives, holdings, scores and evidence are synthetic fixtures. */
@RunWith(AndroidJUnit4::class)
class PortfolioAiScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    @Volatile private var signedIn = true
    @Volatile private var emptyHoldings = false
    @Volatile private var getStatus = 200
    @Volatile private var saved = wrapper()
    @Volatile private var refreshStatus = 200
    @Volatile private var refreshBody = wrapper()
    @Volatile private var disconnectRefresh = false
    @Volatile private var malformedRefresh = false
    @Volatile private var readGate: CountDownLatch? = null
    @Volatile private var refreshGate: CountDownLatch? = null
    private fun json(body: String, status: Int = 200) = MockResponse().setResponseCode(status)
        .setHeader("Content-Type", "application/json").setBody(body)
    @Before fun fixture() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/auth/csrf" -> json("""{"headerName":"X-XSRF-TOKEN","parameterName":"_csrf","token":"synthetic-ai-csrf"}""")
                        .addHeader("Set-Cookie", "XSRF-TOKEN=synthetic-ai-csrf; Path=/")
                    "/api/auth/refresh" -> json("""{"code":"INVALID_REFRESH_TOKEN","message":"로그인이 필요합니다"}""", 401)
                    "/api/auth/logout" -> { signedIn = false; MockResponse().setResponseCode(204) }
                    "/api/users/me" -> if (signedIn) json("""{"id":37,"email":"ai-fixture@example.invalid","name":null,"nickname":"AI검증회원","role":"USER"}""")
                        else json(error("UNAUTHORIZED"), 401)
                    "/api/portfolio" -> if (!signedIn) json(error("UNAUTHORIZED"), 401) else json("""{"holdings":[${if (emptyHoldings) "" else """{"assetId":77,"assetCode":"TEST77","name":"합성자산","quantity":3,"averagePurchasePrice":300,"currency":"KRW","market":"KOSPI"},{"assetId":78,"assetCode":"TEST78","name":"합성보조자산","quantity":1,"averagePurchasePrice":300,"currency":"KRW","market":"KOSPI"}"""}],"totalRealizedProfitLoss":0}""")
                    "/api/portfolio/histories" -> json("[]")
                    ROOT -> if (request.method == "GET") {
                        val response = if (!signedIn) json(error("UNAUTHORIZED"), 401) else json(saved, getStatus)
                        readGate?.await(15, TimeUnit.SECONDS)
                        response
                    } else json(wrapper())
                    "$ROOT/refresh" -> when {
                        disconnectRefresh -> MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)
                        malformedRefresh -> json("{broken-json")
                        refreshStatus != 200 -> json(error(if (refreshStatus == 409) "ANALYSIS_IN_PROGRESS" else "UNAVAILABLE"), refreshStatus)
                        else -> {
                            val response = json(refreshBody)
                            refreshGate?.await(15, TimeUnit.SECONDS)
                            response
                        }
                    }
                    "$ROOT/history" -> json("""[{"analysisId":91,"previousAnalysisId":90,"analyzedAt":"2026-11-04T02:03:04Z","changeReason":"EVIDENCE_UPDATED","analysis":${analysis()}}]""")
                    else -> json("[]")
                }
            }
        }
        server.start()
    }
    @After fun shutdown() { readGate?.countDown(); refreshGate?.countDown(); server.shutdown() }
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun await(tag: String) { compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun awaitSummary(text: String = SUMMARY) {
        compose.waitUntil(10_000) { compose.onAllNodesWithText(text, substring = true).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun openAi() { await("ai-toggle"); click("ai-toggle") }
    private fun posts() = requests.count { it.method == "POST" && it.requestUrl?.encodedPath?.startsWith(ROOT) == true }
    private fun reads() = requests.count { it.method == "GET" && it.requestUrl?.encodedPath == ROOT }
    private fun awaitIdleAction(tag: String) {
        compose.waitUntil(10_000) { compose.onAllNodes(hasTestTag(tag) and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun capture(name: String) {
        compose.onNodeWithTag("ai-status").performScrollTo()
        val viewport = compose.onNode(hasScrollAction() and hasAnyDescendant(hasTestTag("ai-status")))
        val offset = compose.onNodeWithTag("ai-status").fetchSemanticsNode().boundsInRoot.top -
            viewport.fetchSemanticsNode().boundsInRoot.top
        viewport.performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, offset) }
        compose.waitForIdle()
        val instrumentation = androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.waitForIdle(500, 5_000)
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        java.io.FileOutputStream(java.io.File(instrumentation.targetContext.getExternalFilesDir(null), "$name.png")).use {
            bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap.recycle()
    }

    @Test fun savedGetDoesNotGenerateAndManualActionsUseCanonicalEndpoints() {
        launch().use {
            openAi(); awaitSummary()
            compose.onNodeWithTag("ai-result").assertTextContains(SUMMARY, substring = true)
            compose.onNodeWithTag("ai-score").assertTextContains("37.5", substring = true)
            compose.onNodeWithTag("ai-donut").assertExists()
            compose.onNodeWithTag("ai-coverage").assertExists()
            compose.onNodeWithTag("ai-impacts").assertExists()
            compose.onAllNodesWithText("합성 근거 문서", substring = true).assertCountEquals(0)
            click("ai-sources-toggle")
            compose.onNodeWithTag("ai-sources").assertExists()
            assertTrue(compose.onAllNodesWithText("합성 근거 문서", substring = true).fetchSemanticsNodes().isNotEmpty())
            click("ai-sources-toggle")
            assertEquals(0, posts())
            capture("ai-ready")
            click("ai-generate"); awaitIdleAction("ai-generate")
            assertEquals(1, requests.count { it.method == "POST" && it.requestUrl?.encodedPath == ROOT })
            click("ai-refresh"); awaitIdleAction("ai-refresh")
            assertEquals(1, requests.count { it.method == "POST" && it.requestUrl?.encodedPath == "$ROOT/refresh" })
            click("ai-history"); await("ai-history-list")
            assertEquals(1, requests.count { it.requestUrl?.encodedPath == "$ROOT/history" })
            assertTrue(requests.none { it.requestUrl?.encodedPath == "/api/portfolio/analysis" || it.requestUrl?.encodedPath?.startsWith("/api/v2/") == true })
            assertTrue(requests.none { it.requestUrl?.encodedPath == "/api/portfolio/calculate" })
        }
    }

    @Test fun partialNullScoreIsJudgmentDeferredAndNeverFabricatedZero() {
        saved = wrapper(body = analysis(partial = true))
        launch().use {
            openAi(); awaitSummary(PARTIAL_SUMMARY)
            compose.onNodeWithTag("ai-score").assertTextContains("판단 보류", substring = true)
            compose.onNodeWithTag("ai-score").assert(hasText("0점", substring = true).not())
            compose.onNodeWithTag("ai-coverage").assertExists()
            click("ai-asset-1")
            assertTrue(compose.onAllNodesWithText("판단에 필요한 근거를 확인하지 못했어요.", substring = true).fetchSemanticsNodes().isNotEmpty())
            click("ai-overall"); awaitSummary(PARTIAL_SUMMARY)
            assertEquals(0, posts())
            capture("ai-partial")
        }
    }

    @Test fun donutAssetSelectionChangesDetailAndOverallRestoresSummaryWithoutRequests() {
        launch().use {
            openAi(); awaitSummary()
            compose.onNodeWithTag("ai-donut").assertExists()
            val initialReads = reads()
            click("ai-asset-0")
            compose.onNodeWithText("합성 수요가 증가했어요.").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("변화를 지켜봐야 해요.").assertExists()
            capture("ai-selected")
            compose.onAllNodesWithText(SUMMARY, substring = true).assertCountEquals(0)
            click("ai-sources-toggle")
            compose.onNodeWithText("합성 근거 문서", substring = true).assertExists()
            compose.onAllNodesWithText("합성 보조 근거 문서", substring = true).assertCountEquals(0)
            click("ai-sources-toggle")
            click("ai-overall"); awaitSummary()
            compose.onNodeWithTag("ai-result").assertTextContains(SUMMARY, substring = true)
            compose.onNodeWithTag("ai-score").assertTextContains("37.5", substring = true)
            compose.onAllNodesWithText("합성 근거 문서", substring = true).assertCountEquals(0)
            click("ai-sources-toggle")
            assertTrue(compose.onAllNodesWithText("합성 근거 문서", substring = true).fetchSemanticsNodes().isNotEmpty())
            compose.onNodeWithText("합성 보조 근거 문서", substring = true).assertExists()
            compose.onNodeWithText("Synthetic demand changed.", substring = true).assertExists()
            click("ai-sources-toggle")
            compose.onAllNodesWithText("합성 근거 문서", substring = true).assertCountEquals(0)
            compose.onAllNodesWithText("합성 보조 근거 문서", substring = true).assertCountEquals(0)
            assertEquals(initialReads, reads())
            assertEquals(0, posts())
        }
    }

    @Test fun refresh503PreservesEarlierSuccessfulAnalysis() {
        refreshStatus = 503
        launch().use {
            openAi(); awaitSummary(); click("ai-refresh")
            awaitIdleAction("ai-refresh")
            compose.onNodeWithTag("ai-result").assertTextContains(SUMMARY, substring = true)
            assertEquals(1, posts())
        }
    }

    @Test fun unknownRefreshBlocksAnotherPostUntilExplicitGetConfirmsState() {
        disconnectRefresh = true
        launch().use {
            openAi(); awaitSummary(); click("ai-refresh")
            compose.waitUntil(10_000) { compose.onAllNodes(hasTestTag("ai-reload") and isEnabled()).fetchSemanticsNodes().isNotEmpty() && posts() == 1 }
            compose.onNodeWithTag("ai-generate").assertIsNotEnabled()
            compose.onNodeWithTag("ai-refresh").assertIsNotEnabled()
            compose.onNodeWithTag("ai-result").assertTextContains(SUMMARY, substring = true)
            val before = reads(); disconnectRefresh = false
            click("ai-reload")
            compose.waitUntil(10_000) { reads() > before }
            awaitIdleAction("ai-refresh")
            assertEquals(1, posts())
        }
    }

    @Test fun malformedRefreshAndConflictRequireReadBeforeFurtherPost() {
        malformedRefresh = true
        launch().use {
            openAi(); awaitSummary(); click("ai-refresh")
            compose.waitUntil(10_000) { compose.onAllNodes(hasTestTag("ai-generate") and isNotEnabled()).fetchSemanticsNodes().isNotEmpty() && posts() == 1 }
            compose.onNodeWithTag("ai-refresh").assertIsNotEnabled()
            awaitIdleAction("ai-reload")
            malformedRefresh = false; saved = wrapper(status = "PROCESSING")
            click("ai-reload"); awaitIdleAction("ai-reload")
            compose.onNodeWithTag("ai-generate").assertIsNotEnabled()
            compose.onNodeWithTag("ai-refresh").assertIsNotEnabled()
            saved = wrapper(); click("ai-reload"); awaitIdleAction("ai-refresh")
            refreshStatus = 409; click("ai-refresh")
            awaitIdleAction("ai-reload")
            compose.onNodeWithTag("ai-generate").assertIsNotEnabled()
            compose.onNodeWithTag("ai-refresh").assertIsNotEnabled()
            assertEquals(2, posts())
            click("ai-reload"); awaitIdleAction("ai-refresh")
            assertEquals(2, posts())
        }
    }

    @Test fun readErrorsAreNotEmptyOrAReadyResultAnd401RoutesToAccount() {
        getStatus = 503; saved = error("UNAVAILABLE")
        launch().use {
            openAi(); awaitIdleAction("ai-reload")
            compose.onNodeWithTag("ai-result").assertDoesNotExist()
            assertEquals(0, posts())
            getStatus = 401; saved = error("UNAUTHORIZED")
            signedIn = false
            click("ai-reload"); await("ai-login")
            compose.onNodeWithTag("ai-result").assertDoesNotExist()
            click("ai-login"); await("account-login")
        }
    }

    @Test fun emptyHoldingsDisableGenerationEvenWhenSavedAnalysisIsEmpty() {
        emptyHoldings = true; saved = wrapper(status = "EMPTY", body = null)
        launch().use {
            openAi(); await("ai-status")
            compose.onNodeWithTag("ai-generate").assertIsNotEnabled()
            compose.onNodeWithTag("ai-result").assertDoesNotExist()
            assertEquals(0, posts())
        }
    }

    @Test fun logoutDuringDelayedSavedGetPreventsLateMemberAnalysisFromReappearing() {
        readGate = CountDownLatch(1)
        launch().use {
            openAi()
            compose.waitUntil(10_000) { reads() == 1 }
            compose.onNodeWithTag("tab-account").performClick(); await("account-profile")
            click("account-logout"); await("account-login")
            readGate!!.countDown()
            compose.onNodeWithTag("tab-portfolio").performClick(); await("portfolio-login")
            compose.onNodeWithTag("ai-result").assertDoesNotExist()
            compose.onAllNodesWithText(SUMMARY, substring = true).assertCountEquals(0)
            assertEquals(0, posts())
        }
    }

    @Test fun accountRead401ClearsReadyAnalysisAndHistoryBeforeLateRefreshCanReturn() {
        launch().use { scenario ->
            openAi(); awaitSummary()
            click("ai-history"); await("ai-history-list")
            refreshGate = CountDownLatch(1)
            click("ai-refresh")
            compose.waitUntil(10_000) {
                requests.any { it.method == "POST" && it.requestUrl?.encodedPath == "$ROOT/refresh" }
            }
            signedIn = false
            compose.onNodeWithTag("tab-account").performClick(); await("account-login")
            compose.onNodeWithTag("account-login").assertIsEnabled()
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            fun assertExpiredState() {
                scenario.onActivity { activity ->
                    val core = androidx.lifecycle.ViewModelProvider(activity)[CoreViewModel::class.java]
                    val ai = core.portfolioAi.state.value
                    assertNull(core.profile)
                    assertTrue(core.accountRequiresLogin)
                    assertNull(ai.saved)
                    assertNull(ai.history)
                    assertTrue(ai.loginRequired)
                    assertFalse(ai.submitting)
                    assertFalse(ai.loading)
                }
            }
            // Inspect the shared ViewModel while still on Account, before any portfolio GET.
            assertExpiredState()
            refreshGate!!.countDown()
            compose.waitForIdle()
            androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().uiAutomation.waitForIdle(500, 5_000)
            assertExpiredState()
            assertEquals(1, requests.count { it.method == "POST" && it.requestUrl?.encodedPath == "$ROOT/refresh" })
            assertEquals(0, requests.count { it.requestUrl?.encodedPath == "/api/auth/logout" })
        }
    }

    companion object {
        private const val ROOT = "/api/users/me/portfolio/analysis"
        private const val SUMMARY = "합성 검증 결과예요. 반도체 수요의 영향을 확인해야 해요."
        private const val PARTIAL_SUMMARY = "합성 부분 분석이에요. 근거가 없는 종목은 판단을 보류해요."
        private const val SOURCE = """{"title":"합성 근거 문서","url":"https://example.invalid/synthetic-evidence","publishedOn":"2026-11-03","occurredOn":null,"excerpt":"합성 자료에서 수요 변화를 확인했어요.","factQuote":"Synthetic demand changed."}"""
        private const val AUX_SOURCE = """{"title":"합성 보조 근거 문서","url":"https://example.invalid/synthetic-secondary-evidence","publishedOn":"2026-11-02","occurredOn":null,"excerpt":"합성 보조 자료의 변화를 확인했어요.","factQuote":"Synthetic secondary evidence changed."}"""
        private fun error(code: String) = """{"code":"$code","message":"synthetic AI fixture failure"}"""
        private fun analysis(partial: Boolean = false): String {
            val first = """{"assetName":"합성자산","weight":75,"direction":"POSITIVE","impactLevel":"MEDIUM","issueSummary":"합성 수요가 증가했어요.","expectedReaction":"수요의 영향을 확인할 수 있어요.","outlook":"변화를 지켜봐야 해요.","reason":"비중을 함께 확인해야 해요.","evidenceSentence":"합성 자료에서 수요 변화를 확인했어요.","sources":[$SOURCE],"rank":1,"evidenceStatus":"SUPPORTED"}"""
            val second = if (partial) """{"assetName":"합성보조자산","weight":25,"direction":null,"impactLevel":null,"issueSummary":"판단에 필요한 근거를 확인하지 못했어요.","expectedReaction":"","outlook":"","reason":"판단에 필요한 근거를 확인하지 못했어요.","evidenceSentence":"판단에 필요한 근거를 확인하지 못했어요.","sources":[],"rank":2,"evidenceStatus":"INSUFFICIENT"}"""
                else """{"assetName":"합성보조자산","weight":25,"direction":"NEGATIVE","impactLevel":"LOW","issueSummary":"합성 변화를 확인했어요.","expectedReaction":"추가 확인이 필요해요.","outlook":"자료를 지켜봐야 해요.","reason":"영향이 제한적이에요.","evidenceSentence":"합성 보조 자료의 변화를 확인했어요.","sources":[$AUX_SOURCE],"rank":2,"evidenceStatus":"SUPPORTED"}"""
            return """{"totalAssetCount":2,"analyzedAssetCount":${if (partial) 1 else 2},"selectedAssetCount":2,"overallDirection":${if (partial) "null" else "\"POSITIVE\""},"overallScore":${if (partial) "null" else "37.5"},"positiveImpactScore":45,"negativeImpactScore":${if (partial) 0 else 7.5},"analyzedAt":"2026-11-04T02:03:04Z","overallImpact":"${if (partial) PARTIAL_SUMMARY else SUMMARY}","impacts":[$first,$second],"sources":[$SOURCE${if (partial) "" else ",$AUX_SOURCE"}],"excludedAssets":[],"analyzedWeight":${if (partial) 75 else 100},"coverage":"${if (partial) "PARTIAL" else "COMPLETE"}"}"""
        }
        private fun wrapper(status: String = "READY", body: String? = analysis()) = """{"status":"$status","lastCheckOutcome":${if (body == null) "null" else "\"UPDATED\""},"analysisId":${if (body == null) "null" else "91"},"matchesCurrentPortfolio":${status != "PORTFOLIO_CHANGED" && body != null},"lastSucceededAt":${if (body == null) "null" else "\"2026-11-04T02:03:04Z\""},"lastFailedAt":null,"failureCode":null,"changeReason":null,"analysis":${body ?: "null"}}"""
    }
}
