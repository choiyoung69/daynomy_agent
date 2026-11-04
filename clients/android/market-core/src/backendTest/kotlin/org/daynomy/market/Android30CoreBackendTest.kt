package org.daynomy.market

import java.math.BigDecimal
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.*
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.junit.Assert.*
import org.junit.Test

/** Real existing Rust HTTP/disposable DB. No environment means failure, never skip. */
class Android30CoreBackendTest {
    private fun required(key:String)=System.getenv(key)?.takeIf { it.isNotBlank() } ?: error("Required disposable backend fixture variable: $key")
    private fun obj(raw:String)=Json.parseToJsonElement(raw).jsonObject
    private suspend fun failure(action:suspend ()->Unit):ApiException {
        val error=try { action(); null } catch (e:Throwable) { e }; assertTrue("Expected API failure",error is ApiException); return error as ApiException
    }

    @Test fun realRustAnonymousAccountAndLedgerRejectWithoutFabricatedEmptyState()=runBlocking {
        val session=SessionHttpTransport(required("ANDROID_PILOT_BASE_URL"))
        assertEquals(401,failure { AccountClient(session).me() }.status)
        assertEquals(401,failure { PortfolioClient(session).holdings() }.status)
    }

    @Test fun realRustRequiresCsrfForPublicCalculateAndAcceptsSessionBootstrap()=runBlocking {
        val base=required("ANDROID_PILOT_BASE_URL").trimEnd('/')
        val raw=OkHttpClient.Builder().retryOnConnectionFailure(false).build()
        raw.newCall(Request.Builder().url("$base/api/portfolio/calculate").post("{\"holdings\":[]}".toRequestBody("application/json".toMediaType())).build()).execute().use { assertEquals(403,it.code) }
        val asset=required("ANDROID30_ASSET_ID").toLong()
        val result=PortfolioClient(SessionHttpTransport("$base/")).calculate(obj("""{"holdings":[{"assetId":$asset,"quantity":1,"averagePurchasePrice":10}]}"""))
        assertTrue(result.isNotEmpty())
    }

    @Test fun realRustPkceMemberAccountBuySellHistoryOversellRollbackUpdateAndDelete()=runBlocking {
        val session=SessionHttpTransport(required("ANDROID_PILOT_BASE_URL"))
        val credentials=buildJsonObject { put("code",required("ANDROID30_LOGIN_CODE")); put("codeVerifier",required("ANDROID30_LOGIN_VERIFIER")) }
        session.request("POST","/api/auth/mobile/exchange",credentials.toString())
        val account=AccountClient(session); val original=account.me()
        assertTrue(original.id>0); assertTrue(original.nickname.isNotBlank())
        val renamed=account.updateNickname("Android검증회원"); assertEquals("Android검증회원",renamed.nickname)
        val portfolio=PortfolioClient(session); assertTrue(portfolio.holdings().getValue("holdings").jsonArray.isEmpty())
        val asset=required("ANDROID30_ASSET_ID").toLong()
        fun transaction(type:String,quantity:Int,price:String)=obj("""{"assetId":$asset,"type":"$type","quantity":$quantity,"unitPrice":$price,"fee":0,"tax":0,"tradeDate":"2026-10-23"}""")
        val buy=portfolio.createTransaction(transaction("BUY",3,"10.0001")); val buyId=buy.getValue("transactionId").jsonPrimitive.long
        assertEquals(3L,buy.getValue("holding").jsonObject.getValue("quantity").jsonPrimitive.long)
        val sold=portfolio.createTransaction(transaction("SELL",1,"12.0001")); val sellId=sold.getValue("transactionId").jsonPrimitive.long
        assertEquals(2L,sold.getValue("holding").jsonObject.getValue("quantity").jsonPrimitive.long)
        val before=portfolio.holdings()
        val oversell=failure { portfolio.createTransaction(transaction("SELL",99,"12")) }; assertEquals(400,oversell.status)
        assertEquals(before,portfolio.holdings())
        val history=portfolio.histories("2026-10-01","2026-10-28"); assertEquals(2,history.size)
        assertTrue(history.all { it.jsonObject.containsKey("historyId") }); assertEquals(setOf("BUY","SELL"),history.map { it.jsonObject.getValue("changeType").jsonPrimitive.content }.toSet())
        portfolio.updateTransaction(buyId,transaction("BUY",3,"11.0001"))
        portfolio.deleteTransaction(sellId); portfolio.deleteTransaction(buyId)
        assertTrue(portfolio.holdings().getValue("holdings").jsonArray.isEmpty())
        assertTrue(portfolio.histories("2026-10-01","2026-10-28").isEmpty())
        account.logout(); assertEquals(401,failure { account.me() }.status)
    }
}
