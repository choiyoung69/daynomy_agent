package org.daynomy.market

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Events and state mutations belong to one UI dispatcher, not arbitrary concurrent threads. */
class MarketController(
    private val searchSource: StockSearchSource,
    private val priceSource: StockPriceSource,
    private val scope: CoroutineScope,
    initial: MarketDraft = MarketDraft(),
    private val debounceMillis: Long = 250,
) : AutoCloseable {
    private val mutableState = MutableStateFlow(MarketUiState(
        query = initial.query, country = initial.country, selected = initial.selected,
        unitPrice = initial.unitPrice, priceEdited = initial.priceEdited, filter = initial.filter,
    ))
    val state: StateFlow<MarketUiState> = mutableState.asStateFlow()
    private var searchJob: Job? = null
    private var priceJob: Job? = null
    private var searchGeneration = 0L
    private var priceGeneration = 0L
    private var active = true
    private var activationHandled = false
    private var closed = false

    fun updateQuery(query: String) {
        if (closed || state.value.query == query) return
        mutableState.update { it.copy(query = query) }
        search()
    }
    fun updateCountry(country: Country) {
        if (closed || state.value.country == country) return
        invalidatePrice()
        mutableState.update { it.copy(country = country, selected = null, price = LoadState.Idle, unitPrice = "", priceEdited = false) }
        search()
    }
    fun updateFilter(filter: CategoryFilter) {
        if (!closed) mutableState.update { it.copy(filter = filter) }
    }
    fun select(stock: Stock) {
        if (closed) return
        invalidateSearch()
        invalidatePrice()
        mutableState.update { it.copy(selected = stock, search = LoadState.Idle, price = LoadState.Idle, unitPrice = "", priceEdited = false) }
        price()
    }
    fun clearSelection() {
        if (closed) return
        invalidatePrice()
        mutableState.update { it.copy(selected = null, price = LoadState.Idle, unitPrice = "", priceEdited = false) }
        search()
    }
    fun editUnitPrice(value: String) {
        if (!closed) mutableState.update { it.copy(unitPrice = value, priceEdited = true) }
    }
    fun retrySearch() { if (!closed) search() }
    fun retryPrice() { if (!closed) price() }

    fun setActive(active: Boolean) {
        if (closed) return
        if (!active) {
            this.active = false
            activationHandled = false
            invalidateSearch(); invalidatePrice()
            mutableState.update { it.copy(search = LoadState.Idle, price = LoadState.Idle) }
        } else if (!this.active || !activationHandled) {
            this.active = true
            activationHandled = true
            if (state.value.selected != null) price() else search()
        }
    }
    override fun close() {
        if (closed) return
        closed = true; active = false
        invalidateSearch(); invalidatePrice()
        mutableState.update { it.copy(search = LoadState.Idle, price = LoadState.Idle) }
    }
    private fun invalidateSearch() { searchGeneration++; searchJob?.cancel(); searchJob = null }
    private fun invalidatePrice() { priceGeneration++; priceJob?.cancel(); priceJob = null }
    private fun currentSearch(token: Long) = !closed && active && token == searchGeneration && state.value.selected == null
    private fun currentPrice(token: Long, id: Long) = !closed && active && token == priceGeneration && state.value.selected?.assetId == id

    private fun search() {
        invalidateSearch()
        val snapshot = state.value
        val keyword = webTrim(snapshot.query)
        if (!active || snapshot.selected != null || keyword.isEmpty()) {
            mutableState.update { it.copy(search = LoadState.Idle) }
            return
        }
        val token = searchGeneration
        mutableState.update { it.copy(search = LoadState.Loading) }
        searchJob = scope.launch {
            try {
                delay(debounceMillis)
                val values = searchSource.search(keyword, snapshot.country)
                if (currentSearch(token)) mutableState.update { it.copy(search = LoadState.Ready(values.toList())) }
            } catch (cancelled: CancellationException) {
                if (currentSearch(token)) mutableState.update { it.copy(search = LoadState.Idle) }
                throw cancelled
            } catch (_: Exception) {
                if (currentSearch(token)) mutableState.update { it.copy(search = LoadState.Failed("검색 결과를 불러오지 못했어요.")) }
            }
        }
    }
    private fun price() {
        invalidatePrice()
        val stock = state.value.selected
        if (!active || stock == null) {
            mutableState.update { it.copy(price = LoadState.Idle) }
            return
        }
        val token = priceGeneration
        mutableState.update { it.copy(price = LoadState.Loading) }
        priceJob = scope.launch {
            try {
                val quote = priceSource.latest(stock.assetId)
                if (currentPrice(token, stock.assetId)) {
                    if (quote.closePrice.signum() <= 0) throw IllegalArgumentException("Nonpositive price")
                    mutableState.update {
                        it.copy(price = LoadState.Ready(quote), unitPrice =
                            if (it.priceEdited || it.unitPrice.isNotEmpty()) it.unitPrice
                            else quote.closePrice.stripTrailingZeros().toPlainString())
                    }
                }
            } catch (cancelled: CancellationException) {
                if (currentPrice(token, stock.assetId)) mutableState.update { it.copy(price = LoadState.Idle) }
                throw cancelled
            } catch (_: Exception) {
                if (currentPrice(token, stock.assetId)) mutableState.update { it.copy(price = LoadState.Failed("최근 종가를 불러오지 못했습니다. 거래 단가를 직접 입력해 주세요.")) }
            }
        }
    }
}

/** ECMAScript trim code points: preserve NEL; trim BOM explicitly. */
private fun webTrim(value: String) = value.trim { ch ->
    ch in '\u0009'..'\u000d' || ch == '\u0020' || ch == '\u00a0' || ch == '\u1680' ||
        ch in '\u2000'..'\u200a' || ch in '\u2028'..'\u2029' || ch == '\u202f' ||
        ch == '\u205f' || ch == '\u3000' || ch == '\ufeff'
}
