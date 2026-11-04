package org.daynomy.market

import java.math.BigDecimal
import org.junit.Assert.assertTrue

internal const val SEARCH_ROW = """{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"}"""
internal const val PRICE_ROW = """{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-10-23","closePrice":71000.1250,"currency":"KRW"}"""
internal fun stock(id: Long = 1) = Stock(id, "CODE$id", "Stock $id", Category.STOCK, Market.KOSPI, Currency.KRW)
internal fun price(id: Long = 1, amount: String = "71000.1250", date: String = "2026-10-23") =
    StockPrice(id, "CODE$id", "Stock $id", date, BigDecimal(amount), Currency.KRW)
internal class RecordingTransport(var body: String) : HttpTransport {
    val paths = mutableListOf<String>()
    var failure: Throwable? = null
    override suspend fun get(pathAndQuery: String): String {
        paths += pathAndQuery
        failure?.let { throw it }
        return body
    }
}
internal suspend inline fun <reified T : Throwable> expectFailure(crossinline action: suspend () -> Unit): T {
    val failure = try { action(); null } catch (failure: Throwable) { failure }
    assertTrue("Expected ${T::class.java.simpleName}, got ${failure?.javaClass?.simpleName ?: "success"}", failure is T)
    return failure as T
}
