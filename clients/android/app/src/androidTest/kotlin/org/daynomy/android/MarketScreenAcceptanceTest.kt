package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextReplacement
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
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

/** Device/emulator instrumented tests. JVM compilation cannot count as executing these. */
@RunWith(AndroidJUnit4::class)
class MarketScreenAcceptanceTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var server: MockWebServer
    private val requests = CopyOnWriteArrayList<RecordedRequest>()
    private var priceGate: CountDownLatch? = null
    private var priceMissing = false
    private val stocks = """{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"},{"assetId":2,"assetCode":"ETF.US","name":"ETF example","category":"ETF","market":"NASDAQ","currency":"USD"}]}"""
    @Before fun startServer() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return when (request.requestUrl?.encodedPath) {
                    "/api/stocks" -> MockResponse().setBody(stocks)
                    "/api/stocks/1/price" -> {
                        priceGate?.await(10, TimeUnit.SECONDS)
                        if (priceMissing) MockResponse().setResponseCode(404).setBody("""{"code":"STOCK_PRICE_NOT_FOUND","message":"주식·ETF 종가를 찾을 수 없습니다."}""")
                        else MockResponse().setBody("""{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-10-23","closePrice":71000.1250,"currency":"KRW"}""")
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
    }
    @After fun stopServer() { priceGate?.countDown(); server.shutdown() }
    private fun launch(): ActivityScenario<MainActivity> {
        val context = ApplicationProvider.getApplicationContext<Context>()
        return ActivityScenario.launch(Intent(context, MainActivity::class.java).putExtra("base_url", server.url("/").toString()))
    }
    private fun awaitTag(tag: String) {
        compose.waitUntil(8000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun assertUnitPrice(value: String) {
        compose.onNodeWithTag("unit-price").assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString(value)))
    }
    private fun searchAndSelect() {
        awaitTag("portfolio-stock-search")
        compose.onNodeWithTag("portfolio-stock-search").performScrollTo().performClick()
        awaitTag("query")
        compose.onNodeWithTag("query").performTextReplacement("삼성")
        awaitTag("stock-1")
        compose.onNodeWithTag("stock-1").performClick()
        awaitTag("unit-price")
    }
    @Test fun selectingStockDisplaysStoredDateAndAutofillsPlainDecimal() {
        launch().use {
            searchAndSelect()
            awaitTag("price-date")
            compose.onNodeWithTag("price-date").assertTextContains("2026-10-23", substring = true)
            assertUnitPrice("71000.125")
            assertTrue(requests.any { it.path == "/api/stocks/1/price" })
        }
    }
    @Test fun delayedQuoteCannotOverwriteManualInputAndRotationPreservesDirtyDraft() {
        priceGate = CountDownLatch(1)
        launch().use { scenario ->
            searchAndSelect()
            compose.waitUntil(8000) { requests.any { it.path == "/api/stocks/1/price" } }
            compose.onNodeWithTag("unit-price").performTextReplacement("123.4000")
            priceGate!!.countDown()
            awaitTag("price-date")
            assertUnitPrice("123.4000")
            scenario.recreate()
            awaitTag("unit-price")
            assertUnitPrice("123.4000")
            awaitTag("price-date")
            assertUnitPrice("123.4000")
            compose.onNodeWithTag("price-date").assertTextContains("2026-10-23", substring = true)
        }
    }
    @Test fun clearedManualInputRemainsEmptyWhenDelayedPriceArrives() {
        priceGate = CountDownLatch(1)
        launch().use {
            searchAndSelect()
            compose.onNodeWithTag("unit-price").performTextReplacement("99")
            compose.onNodeWithTag("unit-price").performTextReplacement("")
            priceGate!!.countDown()
            awaitTag("price-date")
            assertUnitPrice("")
        }
    }
    @Test fun missingQuoteShowsErrorAndStillAllowsManualInput() {
        priceMissing = true
        launch().use {
            searchAndSelect()
            awaitTag("price-error")
            compose.onNodeWithTag("price-error").assertIsDisplayed()
            compose.onNodeWithTag("price-date").assertDoesNotExist()
            compose.onNodeWithTag("unit-price").performTextReplacement("44.5")
            assertUnitPrice("44.5")
        }
    }
    @Test fun usSearchSendsCountryAndLocalCategoryFilterDoesNotRefetch() {
        launch().use {
            awaitTag("portfolio-stock-search")
            compose.onNodeWithTag("portfolio-stock-search").performScrollTo().performClick()
            awaitTag("query")
            compose.onNodeWithTag("query").performClick()
            awaitTag("country-US")
            compose.onNodeWithTag("country-US").performClick()
            compose.onNodeWithTag("query").performTextReplacement("AAPL & ETF")
            awaitTag("stock-1"); awaitTag("stock-2")
            val search = requests.last { it.requestUrl?.encodedPath == "/api/stocks" }
            assertEquals("US", search.requestUrl!!.queryParameter("country"))
            assertEquals("AAPL & ETF", search.requestUrl!!.queryParameter("q"))
            val before = requests.size
            compose.onNodeWithTag("filter-ETF").performClick()
            compose.onNodeWithTag("stock-1").assertDoesNotExist()
            compose.onNodeWithTag("stock-2").assertIsDisplayed()
            compose.onNodeWithTag("filter-ALL").performClick()
            compose.onNodeWithTag("stock-1").assertIsDisplayed()
            assertEquals(before, requests.size)
        }
    }
}
