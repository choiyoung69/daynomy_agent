package org.daynomy.market

import java.math.BigDecimal
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

class StockPriceClient(private val transport: HttpTransport) : StockPriceSource {
    override suspend fun latest(assetId: Long): StockPrice {
        require(assetId in 1..MAX_SAFE_PRICE_ASSET_ID) { "종목 ID가 올바르지 않습니다." }
        // Keep transport/API/cancellation failures outside the payload decoder.
        val body = transport.get("/api/stocks/$assetId/price")
        return decodePrice(body)
    }
}

private const val MAX_SAFE_PRICE_ASSET_ID = 9_007_199_254_740_991L
private val PRICE_JSON_NUMBER = Regex("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

private fun invalidPriceResponse(): Nothing =
    throw ResponseFormatException("최근 종가 응답 형식이 올바르지 않습니다.")

private fun decodePrice(body: String): StockPrice {
    val element = try {
        Json.parseToJsonElement(body)
    } catch (_: SerializationException) {
        invalidPriceResponse()
    }
    val row = element as? JsonObject ?: invalidPriceResponse()
    val idDecimal = priceNumber(row, "assetId")
    val id = try {
        idDecimal.longValueExact()
    } catch (_: ArithmeticException) {
        invalidPriceResponse()
    }
    if (id !in 1..MAX_SAFE_PRICE_ASSET_ID) invalidPriceResponse()

    val assetCode = priceString(row, "assetCode")
    val name = priceString(row, "name")
    val baseDate = priceString(row, "baseDate")
    val closePrice = priceNumber(row, "closePrice")
    // Match the web finite-number boundary without using Double for money.
    if (!closePrice.toDouble().isFinite()) invalidPriceResponse()
    val currencyValue = (row["currency"] as? JsonPrimitive)
        ?.takeIf { it.isString }?.content
    val currency = when (currencyValue) {
        "KRW" -> Currency.KRW
        "USD" -> Currency.USD
        else -> if (assetCode.endsWith(".US")) Currency.USD else Currency.KRW
    }
    return StockPrice(id, assetCode, name, baseDate, closePrice, currency)
}

private fun priceString(row: JsonObject, key: String): String {
    val value = row[key] as? JsonPrimitive ?: invalidPriceResponse()
    if (!value.isString) invalidPriceResponse()
    return value.content
}

private fun priceNumber(row: JsonObject, key: String): BigDecimal {
    val value = row[key] as? JsonPrimitive ?: invalidPriceResponse()
    if (value.isString || !PRICE_JSON_NUMBER.matches(value.content)) invalidPriceResponse()
    return try {
        BigDecimal(value.content)
    } catch (_: NumberFormatException) {
        invalidPriceResponse()
    }
}
