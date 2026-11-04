package org.daynomy.market

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

/** Independent follow-up regressions discovered in source review after the initial green. */
class Android30SafetyRegressionTest {
    @Test fun mutation503RetryAfterZeroIsReturnedWithoutAutomaticReplay() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setHeader("Content-Type","application/json").setHeader("Set-Cookie","XSRF-TOKEN=fixture; Path=/").setBody("""{"headerName":"X-XSRF-TOKEN","token":"fixture"}"""))
            server.enqueue(MockResponse().setResponseCode(503).setHeader("Retry-After","0").setHeader("Content-Type","application/json").setBody("""{"code":"SERVICE_UNAVAILABLE","message":"temporary"}"""))
            server.enqueue(MockResponse().setResponseCode(201).setBody("""{"transactionId":999}"""))
            server.start()
            val transport=SessionHttpTransport(server.url("/").toString())
            val error=expectFailure<ApiException> { transport.request("POST","/api/portfolio/transactions","""{"assetId":1,"quantity":1}""") }
            assertEquals(503,error.status); assertEquals("SERVICE_UNAVAILABLE",error.code)
            assertEquals("CSRF bootstrap and one mutation only",2,server.requestCount)
            assertEquals("/api/auth/csrf",server.takeRequest().path)
            assertEquals("/api/portfolio/transactions",server.takeRequest().path)
        }
    }

    @Test fun unknownAccountRoleIsRejectedRatherThanAcceptedAsMemberProfile() = runBlocking {
        val transport=object:SessionTransport {
            override suspend fun get(pathAndQuery:String)="""{"id":7,"email":"synthetic@example.invalid","name":null,"nickname":"회원","role":"GUEST"}"""
            override suspend fun request(method:String,path:String,jsonBody:String?)=get(path)
        }
        expectFailure<ResponseFormatException> { AccountClient(transport).me() }
        Unit
    }
}
