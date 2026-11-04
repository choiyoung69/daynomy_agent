package org.daynomy.market

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.test.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class GuestPortfolioControllerTest {
    private val stock = Stock(1, "005930", "삼성전자", Category.STOCK, Market.KOSPI, Currency.KRW)
    private class Transport : SessionTransport {
        val calls = mutableListOf<Triple<String, String, String?>>()
        var reply: suspend () -> String = { """{"pricingStatus":"COMPLETE","holdings":[],"totalPurchaseAmount":400000,"totalEvaluationAmount":444000,"totalProfitLoss":44000}""" }
        override suspend fun get(pathAndQuery: String): String = request("GET", pathAndQuery)
        override suspend fun request(method: String, path: String, jsonBody: String?): String {
            calls += Triple(method, path, jsonBody)
            return reply()
        }
    }

    @Test fun temporaryHoldingsAreUpdatedByAssetAndNeverWrittenToMemberEndpoints() = runTest {
        val transport = Transport(); val c = GuestPortfolioController(transport, this)
        c.save(stock, "2", "200000.00")
        c.save(stock, "3", "199999.99")
        assertEquals(1, c.state.value.holdings.size)
        assertEquals(3L, c.state.value.holdings.single().quantity)
        assertEquals("199999.99", c.state.value.holdings.single().average.toPlainString())
        assertTrue(transport.calls.isEmpty())
        c.remove(1); assertTrue(c.state.value.holdings.isEmpty())
    }

    @Test fun invalidQuantitiesAndMoneyNeverChangeThePortfolio() = runTest {
        val c = GuestPortfolioController(Transport(), this)
        for ((quantity, price) in listOf("0" to "1", "-1" to "1", "1.5" to "1", "1" to "0", "1" to "1.001", "1" to "1e3", "1" to "1000000000000000")) {
            c.save(stock, quantity, price)
            assertTrue(c.state.value.holdings.isEmpty()); assertNotNull(c.state.value.error)
        }
    }

    @Test fun evaluationUsesOnlyThePublicCalculateContract() = runTest {
        val t = Transport(); val c = GuestPortfolioController(t, this)
        c.save(stock, "2", "200000"); c.evaluate(); advanceUntilIdle()
        assertEquals(listOf("/api/portfolio/calculate"), t.calls.map { it.second })
        assertEquals("POST", t.calls.single().first)
        val row = Json.parseToJsonElement(t.calls.single().third!!).jsonObject["holdings"]!!.jsonArray.single().jsonObject
        assertEquals(setOf("assetId", "quantity", "averagePurchasePrice"), row.keys)
        assertEquals(2L, row["quantity"]!!.jsonPrimitive.long)
        assertEquals("COMPLETE", c.state.value.evaluation!!["pricingStatus"]!!.jsonPrimitive.content)
    }

    @Test fun editingInvalidatesAnInflightEvaluationWithoutLosingHoldings() = runTest {
        val gate = CompletableDeferred<String>(); val t = Transport(); t.reply = { withContext(NonCancellable) { gate.await() } }
        val c = GuestPortfolioController(t, this); c.save(stock, "2", "1"); c.evaluate(); runCurrent()
        c.save(stock, "3", "2"); gate.complete("""{"pricingStatus":"COMPLETE","holdings":[]}"""); advanceUntilIdle()
        assertNull(c.state.value.evaluation); assertEquals(3L, c.state.value.holdings.single().quantity)
    }

    @Test fun separateGuestSessionsNeverShareHoldingsAndFailuresKeepDrafts() = runTest {
        val t = Transport(); t.reply = { throw ApiException(503, "FAILED", "private provider details") }
        val first = GuestPortfolioController(t, this); first.save(stock, "2", "1"); first.evaluate(); advanceUntilIdle()
        assertEquals(1, first.state.value.holdings.size)
        assertFalse(first.state.value.error!!.contains("private"))
        assertTrue(GuestPortfolioController(Transport(), this).state.value.holdings.isEmpty())
    }

    @Test fun maximumFiftyAssetsAndEmptyEvaluationAreEnforcedBeforeNetwork() = runTest {
        val t = Transport(); val c = GuestPortfolioController(t, this)
        c.evaluate(); assertTrue(t.calls.isEmpty())
        for (id in 1L..51L) c.save(stock.copy(assetId=id), "1", "1")
        assertEquals(50, c.state.value.holdings.size); assertNotNull(c.state.value.error)
    }

    @Test fun partialPricingPreservesUnavailableOverallProfit() = runTest {
        val t = Transport(); t.reply = { """{"pricingStatus":"PARTIAL","holdings":[],"totalPurchaseAmount":2,"totalEvaluationAmount":null,"totalProfitLoss":null}""" }
        val c = GuestPortfolioController(t,this); c.save(stock,"2","1"); c.evaluate(); advanceUntilIdle()
        assertEquals(JsonNull,c.state.value.evaluation!!["totalProfitLoss"])
    }

    @Test fun malformedAmountsAndHoldingRowsCannotBecomeAReadyEvaluation() = runTest {
        for (response in listOf("""{"pricingStatus":"COMPLETE","holdings":[],"totalEvaluationAmount":{"unexpected":1}}""",
            """{"pricingStatus":"COMPLETE","holdings":[42]}""")) {
            val t = Transport(); t.reply = { response }
            val c = GuestPortfolioController(t,this); c.save(stock,"2","1"); c.evaluate(); advanceUntilIdle()
            assertNull(c.state.value.evaluation); assertNotNull(c.state.value.error)
        }
    }
}
