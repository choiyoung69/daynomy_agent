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
class Android30CoreScreenTest {
    @get:Rule val compose=createEmptyComposeRule()
    private lateinit var server:MockWebServer
    private val requests=CopyOnWriteArrayList<RecordedRequest>()
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
                    "/api/portfolio" -> json("""{"holdings":[],"totalRealizedProfitLoss":0}""")
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
    private fun awaitTag(tag:String) { compose.waitUntil(10000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() } }
    private fun fill(tag:String,value:String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }

    @Test fun actualAccountProfileNicknamePatchAndLogoutClearMemberUi() {
        launch().use {
            awaitTag("tab-account"); compose.onNodeWithTag("tab-account").performClick(); awaitTag("account-profile")
            compose.onNodeWithTag("account-profile").assertTextContains("초기회원",substring=true)
            fill("account-nickname","변경회원"); compose.onNodeWithTag("account-save").performScrollTo().performClick()
            compose.waitUntil(10000) { requests.any { it.requestUrl?.encodedPath=="/api/users/me" && it.method=="PATCH" } }
            compose.waitUntil(10000) { compose.onAllNodes(hasTestTag("account-profile") and hasText("변경회원",substring=true)).fetchSemanticsNodes().isNotEmpty() }
            compose.onNodeWithTag("account-logout").performScrollTo().performClick(); awaitTag("account-login")
            compose.onNodeWithTag("account-profile").assertDoesNotExist()
            val write=requests.single { it.method=="PATCH" && it.requestUrl?.encodedPath=="/api/users/me" }
            assertTrue(write.body.clone().readUtf8().contains("변경회원")); assertEquals("fixture-csrf",write.getHeader("X-XSRF-TOKEN"))
            assertTrue(write.getHeader("Cookie").orEmpty().contains("XSRF-TOKEN=fixture-csrf"))
            assertEquals(1,requests.count { it.requestUrl?.encodedPath=="/api/auth/logout" })
        }
    }

    @Test fun lostTradeResponseShowsUnknownOutcomeAndDoesNotResubmitOrClaimSuccess() {
        launch().use {
            awaitTag("tab-portfolio"); compose.onNodeWithTag("tab-portfolio").performClick(); awaitTag("transaction-asset")
            fill("transaction-asset","삼성전자"); awaitTag("transaction-stock-1"); compose.onNodeWithTag("transaction-stock-1").performScrollTo().performClick()
            fill("transaction-quantity","2"); fill("transaction-price","10.0001"); fill("transaction-date","2026-10-23")
            compose.onNodeWithTag("transaction-type-BUY").performScrollTo().performClick()
            compose.onNodeWithTag("transaction-submit").performScrollTo().performClick(); awaitTag("transaction-unknown")
            compose.onNodeWithTag("transaction-unknown").performScrollTo().assertIsDisplayed()
            compose.waitForIdle()
            val writes=requests.filter { it.requestUrl?.encodedPath=="/api/portfolio/transactions" }
            assertEquals(1,writes.size); assertEquals("fixture-csrf",writes.single().getHeader("X-XSRF-TOKEN"))
            val body=writes.single().body.clone().readUtf8(); assertTrue(body.contains("10.0001")); assertTrue(body.contains("BUY"))
            compose.onNodeWithTag("transaction-pending").assertDoesNotExist()
        }
    }
}
