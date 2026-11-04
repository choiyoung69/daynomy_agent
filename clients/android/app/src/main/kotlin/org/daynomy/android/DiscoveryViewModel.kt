package org.daynomy.android

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import org.daynomy.market.ExchangeController
import org.daynomy.market.ExchangeRateClient
import org.daynomy.market.NewsClient
import org.daynomy.market.NewsController
import org.daynomy.market.OkHttpTransport

class DiscoveryViewModel(baseUrl: String) : ViewModel() {
    private val client = OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).followRedirects(false).build()
    private val transport = OkHttpTransport(baseUrl, client)
    val news = NewsController(NewsClient(transport), viewModelScope)
    val exchange = ExchangeController(ExchangeRateClient(transport), viewModelScope)
    override fun onCleared() {
        news.close(); exchange.close()
        client.dispatcher.cancelAll(); client.connectionPool.evictAll(); client.dispatcher.executorService.shutdown()
    }
}
