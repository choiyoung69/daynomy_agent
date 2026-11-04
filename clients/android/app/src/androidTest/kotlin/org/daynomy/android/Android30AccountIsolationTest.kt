package org.daynomy.android

import android.os.SystemClock
import androidx.lifecycle.viewModelScope
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.cancel
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.daynomy.market.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Native main-thread state boundary; browser launch and real Google account are unnecessary. */
@RunWith(AndroidJUnit4::class)
class Android30AccountIsolationTest {
    @Test fun startingAnotherNativeLoginClearsPreviousAccountPortfolioAndDrafts() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        fun main(action:()->Unit)=instrumentation.runOnMainSync(action)
        fun await(condition:()->Boolean) {
            val end=SystemClock.elapsedRealtime()+8000
            while(SystemClock.elapsedRealtime()<end) {
                val ready=AtomicBoolean(false); main { ready.set(condition()) }
                if(ready.get()) return
                SystemClock.sleep(20)
            }
            fail("Account/portfolio fixture did not finish before isolation assertion")
        }
        fun json(body:String)=MockResponse().setHeader("Content-Type","application/json").setBody(body)
        MockWebServer().use { server ->
            server.dispatcher=object:Dispatcher() {
                override fun dispatch(request:RecordedRequest):MockResponse=when(request.requestUrl?.encodedPath) {
                    "/api/users/me" -> json("""{"id":7,"email":"account-a@example.invalid","name":null,"nickname":"A회원","role":"USER"}""")
                    "/api/portfolio" -> json("""{"holdings":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW","quantity":2,"averagePurchasePrice":10.01,"averagePurchasePriceCurrency":"KRW"}],"totalRealizedProfitLoss":0}""")
                    "/api/portfolio/histories" -> json("""[{"historyId":9,"assetId":1,"assetCode":"005930","name":"삼성전자","currency":"KRW","changeType":"BUY","quantity":2,"averagePurchasePrice":10.01,"effectiveDate":"2026-10-23","transactionQuantity":2,"unitPrice":10.01,"fee":0,"tax":0,"exchangeRate":null}]""")
                    else -> MockResponse().setResponseCode(404)
                }
            }; server.start()
            val baseUrl=server.url("/").toString()
            lateinit var vm:CoreViewModel
            main { vm=CoreViewModel(baseUrl); vm.loadAccount(); vm.refreshPortfolio() }
            try {
                await { vm.profile?.id==7L && vm.portfolioLoaded && !vm.loading && vm.holdings.isNotEmpty() && vm.history.isNotEmpty() }
                main {
                    vm.select(Stock(1,"005930","삼성전자",Category.STOCK,Market.KOSPI,Currency.KRW))
                    vm.quantity="2"; vm.price="10.01"
                    val url=vm.loginUrl()
                    assertTrue(url.contains("/api/auth/mobile/start?"))
                    assertNull("Previous member must disappear when another login starts",vm.profile)
                    assertTrue("Previous holdings must be removed",vm.holdings.isEmpty())
                    assertTrue("Previous history must be removed",vm.history.isEmpty())
                    assertFalse(vm.portfolioLoaded); assertNull(vm.selection)
                    assertEquals("",vm.quantity); assertEquals("",vm.price); assertFalse(vm.loading)
                }
            } finally { main { vm.viewModelScope.cancel() } }
        }
    }
}
