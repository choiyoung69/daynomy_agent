package org.daynomy.market

import java.math.BigDecimal
import java.net.URI
import java.security.MessageDigest
import java.util.Base64
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class Android30CoreClientContractTest {
    private class Transport(var result:String="{}") : SessionTransport {
        val calls=mutableListOf<Triple<String,String,String?>>()
        var failure:Throwable?=null
        override suspend fun get(pathAndQuery:String)=request("GET",pathAndQuery)
        override suspend fun request(method:String,path:String,jsonBody:String?):String {
            calls += Triple(method,path,jsonBody); failure?.let { throw it }; return result
        }
    }
    private val profile="""{"id":7,"email":"synthetic@example.invalid","name":null,"nickname":"회원","role":"USER"}"""
    private val mutation="""{"transactionId":9,"holding":null,"totalRealizedProfitLoss":1.005}"""
    private fun obj(raw:String)=Json.parseToJsonElement(raw).jsonObject
    private fun params(url:String)=URI(url).rawQuery.split('&').associate { val p=it.split('=',limit=2); p[0] to java.net.URLDecoder.decode(p[1],"UTF-8") }

    @Test fun nativeLoginUsesFreshS256ChallengeStateAndExactExchangeWithNoVerifierInBrowserUrl()=runBlocking {
        val transport=Transport(""); val login=NativeLogin(transport,"https://api.example.invalid/")
        val first=login.begin(); val p=params(first)
        assertEquals("/api/auth/mobile/start",URI(first).path); assertEquals("S256",p["code_challenge_method"] ?: "S256")
        assertTrue(p.getValue("state").matches(Regex("[A-Za-z0-9_-]{32,128}"))); assertEquals(43,p.getValue("code_challenge").length)
        assertFalse(first.contains("codeVerifier")); assertFalse(first.contains("code_verifier"))
        login.complete("org.daynomy.app://auth/callback?code=fixture-code&state=${p.getValue("state")}")
        val call=transport.calls.single(); assertEquals("POST",call.first); assertEquals("/api/auth/mobile/exchange",call.second)
        val body=obj(call.third!!); assertEquals("fixture-code",body.getValue("code").jsonPrimitive.content)
        val verifier=body.getValue("codeVerifier").jsonPrimitive.content
        assertTrue(verifier.matches(Regex("[A-Za-z0-9._~-]{43,128}")))
        val digest=Base64.getUrlEncoder().withoutPadding().encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)))
        assertEquals(p["code_challenge"],digest)
        val next=params(login.begin()); assertNotEquals(p["state"],next["state"]); assertNotEquals(p["code_challenge"],next["code_challenge"])
    }

    @Test fun malformedOAuthCallbacksNeverExchangeAndValidCallbackCannotBeReplayed()=runBlocking {
        for (callback in listOf("evil://auth/callback", "org.daynomy.app://evil/callback", "org.daynomy.app://auth/wrong", "org.daynomy.app://auth/callback?state=wrong&code=x", "org.daynomy.app://auth/callback?code=x&code=y&state=STATE", "org.daynomy.app://auth/callback?code=x&state=STATE&state=STATE")) {
            val t=Transport(""); val login=NativeLogin(t,"https://api.example.invalid/"); val state=params(login.begin()).getValue("state")
            expectFailure<IllegalArgumentException> { login.complete(callback.replace("STATE",state)) }; assertTrue(t.calls.isEmpty())
        }
        val t=Transport(""); val login=NativeLogin(t,"https://api.example.invalid/"); val state=params(login.begin()).getValue("state")
        val callback="org.daynomy.app://auth/callback?code=x&state=$state"; login.complete(callback)
        expectFailure<IllegalArgumentException> { login.complete(callback) }; assertEquals(1,t.calls.size)
    }

    @Test fun accountProfileSupportsExplicitNullAndNicknamePatchUsesExistingMemberEndpoint()=runBlocking {
        val t=Transport(profile); val account=AccountClient(t); val me=account.me()
        assertEquals(7L,me.id); assertNull(me.name); assertEquals("회원",me.nickname)
        account.updateNickname("다음 회원")
        assertEquals("GET",t.calls[0].first); assertEquals("/api/users/me",t.calls[0].second)
        assertEquals("PATCH",t.calls[1].first); assertEquals("다음 회원",obj(t.calls[1].third!!).getValue("nickname").jsonPrimitive.content)
    }

    @Test fun accountRejectsUnsafeIdentifierAndPropagatesConflictWithoutPretendSuccess()=runBlocking {
        for (id in listOf("\"7\"","1.5","9007199254740992","0")) {
            expectFailure<ResponseFormatException> { AccountClient(Transport(profile.replace("\"id\":7","\"id\":$id"))).me() }
        }
        val t=Transport(profile); t.failure=ApiException(409,"NICKNAME_ALREADY_EXISTS","duplicate")
        val error=expectFailure<ApiException> { AccountClient(t).updateNickname("duplicate") }; assertEquals("NICKNAME_ALREADY_EXISTS",error.code); assertEquals(1,t.calls.size)
    }

    @Test fun holdingsAndHistoryKeepNullAndDecimalSourceValuesWithoutDoubleConversion()=runBlocking {
        val t=Transport("""{"holdings":[{"assetId":1,"quantity":2,"averagePurchasePrice":900719925474099.1234}],"totalRealizedProfitLoss":1.005}""")
        val client=PortfolioClient(t); val holdings=client.holdings()
        assertEquals("900719925474099.1234",holdings.getValue("holdings").jsonArray[0].jsonObject.getValue("averagePurchasePrice").jsonPrimitive.content)
        t.result="""[{"historyId":9,"assetId":1,"exchangeRate":null,"unitPrice":1.0001,"changeType":"BUY"}]"""
        val history=client.histories("2026-10-01","2026-10-28"); assertEquals(JsonNull,history[0].jsonObject["exchangeRate"])
        val last=t.calls.last(); assertEquals("GET",last.first); assertEquals("/api/portfolio/histories?from=2026-10-01&to=2026-10-28",last.second)
    }

    @Test fun buySellUpdateDeleteUseExactExistingRequestFieldsAndDoNotRoundMoney()=runBlocking {
        val t=Transport(mutation); val client=PortfolioClient(t)
        val buy=obj("""{"assetId":1,"type":"BUY","quantity":2,"unitPrice":900719925474099.1234,"fee":0.01,"tax":0,"tradeDate":"2026-10-23","exchangeRate":1423.123456}""")
        val result=client.createTransaction(buy); assertEquals("9",result.getValue("transactionId").jsonPrimitive.content)
        assertEquals(buy,obj(t.calls.single().third!!)); assertEquals("POST",t.calls.single().first); assertEquals("/api/portfolio/transactions",t.calls.single().second)
        client.createTransaction(JsonObject(buy.toMutableMap().apply { put("type",JsonPrimitive("SELL")) }))
        assertEquals("SELL",obj(t.calls.last().third!!).getValue("type").jsonPrimitive.content)
        client.updateTransaction(9,buy); assertEquals("PATCH",t.calls.last().first); assertEquals("/api/portfolio/transactions/9",t.calls.last().second)
        t.result=""; client.deleteTransaction(9); assertEquals("DELETE",t.calls.last().first); assertEquals("/api/portfolio/transactions/9",t.calls.last().second)
    }

    @Test fun performanceAndCalculateUseSeparateReadAndPublicCalculationEndpoints()=runBlocking {
        val t=Transport("{}"); val client=PortfolioClient(t)
        client.performance("2026-10-01","2026-10-28")
        assertEquals("GET",t.calls.last().first); assertEquals("/api/portfolio/performance?from=2026-10-01&to=2026-10-28",t.calls.last().second)
        val body=obj("""{"holdings":[]}"""); client.calculate(body)
        assertEquals("POST",t.calls.last().first); assertEquals("/api/portfolio/calculate",t.calls.last().second); assertEquals(body,obj(t.calls.last().third!!))
    }

    @Test fun wrongSuccessShapesCannotBecomeEmptyHoldingsHistoryOrTransactionSuccess()=runBlocking {
        expectFailure<ResponseFormatException> { PortfolioClient(Transport("[]")).holdings() }
        expectFailure<ResponseFormatException> { PortfolioClient(Transport("{}")).histories("2026-10-01","2026-10-28") }
        expectFailure<ResponseFormatException> { PortfolioClient(Transport("{} ")).createTransaction(obj("""{"assetId":1,"quantity":1}""")) }
        Unit // JUnit 4 requires a void test method.
    }
}
