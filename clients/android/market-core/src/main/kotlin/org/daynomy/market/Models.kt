package org.daynomy.market

import java.math.BigDecimal

enum class Country { KR, US }
enum class Category { STOCK, ETF }
enum class CategoryFilter { ALL, STOCK, ETF }
enum class Market { KOSPI, KOSDAQ, NASDAQ, NYSE, NYSE_ARCA, NYSE_AMERICAN, BATS }
enum class Currency { KRW, USD }
data class Stock(val assetId: Long, val assetCode: String, val name: String, val category: Category, val market: Market, val currency: Currency)
data class StockPrice(val assetId: Long, val assetCode: String, val name: String, val baseDate: String, val closePrice: BigDecimal, val currency: Currency)
class ResponseFormatException(message: String) : IllegalArgumentException(message)
class ApiException(val status: Int, val code: String?, message: String) : Exception(message)
interface HttpTransport { suspend fun get(pathAndQuery: String): String }
interface StockSearchSource { suspend fun search(keyword: String, country: Country = Country.KR): List<Stock> }
interface StockPriceSource { suspend fun latest(assetId: Long): StockPrice }
sealed interface LoadState<out T> {
    data object Idle : LoadState<Nothing>
    data object Loading : LoadState<Nothing>
    data class Ready<T>(val value: T) : LoadState<T>
    data class Failed(val message: String) : LoadState<Nothing>
}
data class MarketDraft(val query: String = "", val country: Country = Country.KR, val selected: Stock? = null, val unitPrice: String = "", val priceEdited: Boolean = false, val filter: CategoryFilter = CategoryFilter.ALL)
data class MarketUiState(val query: String = "", val country: Country = Country.KR, val selected: Stock? = null, val search: LoadState<List<Stock>> = LoadState.Idle, val price: LoadState<StockPrice> = LoadState.Idle, val unitPrice: String = "", val priceEdited: Boolean = false, val filter: CategoryFilter = CategoryFilter.ALL)
