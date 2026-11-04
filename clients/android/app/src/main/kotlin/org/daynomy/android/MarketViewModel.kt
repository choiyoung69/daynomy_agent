package org.daynomy.android

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import okhttp3.OkHttpClient
import org.daynomy.market.*

class MarketViewModel(private val saved: SavedStateHandle, baseUrl: String) : ViewModel() {
    private val client = OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).followRedirects(false).build()
    private val transport = OkHttpTransport(baseUrl, client)
    val controller = MarketController(StockSearchClient(transport), StockPriceClient(transport), viewModelScope, restore())
    init {
        controller.state.onEach { state ->
            saved["query"] = state.query; saved["country"] = state.country.name; saved["filter"] = state.filter.name
            saved["unitPrice"] = state.unitPrice; saved["priceEdited"] = state.priceEdited
            val s = state.selected
            saved["assetId"] = s?.assetId; saved["assetCode"] = s?.assetCode; saved["name"] = s?.name
            saved["category"] = s?.category?.name; saved["market"] = s?.market?.name; saved["currency"] = s?.currency?.name
        }.launchIn(viewModelScope)
    }
    private fun restore(): MarketDraft {
        val selected = runCatching {
            val id = saved.get<Long>("assetId") ?: return@runCatching null
            Stock(id, requireNotNull(saved["assetCode"]), requireNotNull(saved["name"]),
                Category.valueOf(requireNotNull(saved["category"])), Market.valueOf(requireNotNull(saved["market"])),
                Currency.valueOf(requireNotNull(saved["currency"])))
        }.getOrNull()
        return MarketDraft(saved["query"] ?: "", runCatching { Country.valueOf(saved["country"] ?: "KR") }.getOrDefault(Country.KR),
            selected, saved["unitPrice"] ?: "", saved["priceEdited"] ?: false,
            runCatching { CategoryFilter.valueOf(saved["filter"] ?: "ALL") }.getOrDefault(CategoryFilter.ALL))
    }
    override fun onCleared() {
        controller.close(); client.dispatcher.cancelAll(); client.connectionPool.evictAll(); client.dispatcher.executorService.shutdown()
    }
}
