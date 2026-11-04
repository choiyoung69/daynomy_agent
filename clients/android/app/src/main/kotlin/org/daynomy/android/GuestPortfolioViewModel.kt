package org.daynomy.android

import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import org.daynomy.market.*

class GuestPortfolioViewModel(baseUrl: String) : ViewModel() {
    // Separate cookie jar: a guest evaluation cannot read or mutate member holdings.
    private val transport = SessionHttpTransport(baseUrl)
    val portfolio = GuestPortfolioController(transport, viewModelScope)
    var query by mutableStateOf(""); private set
    var country by mutableStateOf(Country.KR); private set
    var results by mutableStateOf<List<Stock>>(emptyList()); private set
    var selected by mutableStateOf<Stock?>(null); private set
    var searching by mutableStateOf(false); private set
    var searchError by mutableStateOf<String?>(null); private set
    var quantity by mutableStateOf("")
    var average by mutableStateOf("")
    private var generation = 0L
    private var searchJob: Job? = null

    fun search(value: String) {
        query = value; selected = null; results = emptyList(); searchError = null
        val owner = ++generation; searchJob?.cancel(); searching = value.isNotBlank()
        if (value.isBlank()) return
        val requestedCountry = country
        searchJob = viewModelScope.launch {
            try {
                delay(250)
                val rows = StockSearchClient(transport).search(value, requestedCountry)
                if (owner == generation) results = rows
            } catch (failure: CancellationException) { throw failure }
            catch (_: Exception) { if (owner == generation) searchError = "종목을 검색하지 못했어요. 다시 입력해 주세요." }
            finally { if (owner == generation) searching = false }
        }
    }
    fun changeCountry(value: Country) { country = value; search(query) }
    fun choose(stock: Stock) {
        generation++; searchJob?.cancel(); searching = false; results = emptyList(); searchError = null
        selected = stock; query = stock.name
        val old = portfolio.state.value.holdings.find { it.stock.assetId == stock.assetId }
        quantity = old?.quantity?.toString().orEmpty(); average = old?.average?.toPlainString().orEmpty()
    }
    fun save() { selected?.let { portfolio.save(it, quantity, average) } }
    override fun onCleared() { transport.close() }
}
