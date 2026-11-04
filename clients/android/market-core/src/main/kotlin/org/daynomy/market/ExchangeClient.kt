package org.daynomy.market

import java.math.BigDecimal
import java.net.URLEncoder
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

class ExchangeRateClient(private val transport: HttpTransport) : ExchangeRateSource {
    override suspend fun quote(date: String): ExchangeRate {
        val body = transport.get("/api/exchange-rates/usd-krw?date=${URLEncoder.encode(date, "UTF-8")}")
        val row = try {
            Json.parseToJsonElement(body) as? JsonObject ?: invalidExchangeResponse()
        } catch (_: SerializationException) {
            invalidExchangeResponse()
        }
        val baseDate = row["baseDate"] as? JsonPrimitive ?: invalidExchangeResponse()
        if (!baseDate.isString) invalidExchangeResponse()
        val rawRate = row["rate"] as? JsonPrimitive ?: invalidExchangeResponse()
        if (rawRate.isString || !EXCHANGE_JSON_NUMBER.matches(rawRate.content)) invalidExchangeResponse()
        val rate = try {
            BigDecimal(rawRate.content)
        } catch (_: NumberFormatException) {
            invalidExchangeResponse()
        }
        // Preserve the numeric source while enforcing the web finite positive boundary.
        if (rate.signum() <= 0 || !rate.toDouble().isFinite() || rate.toDouble() <= 0.0) invalidExchangeResponse()
        return ExchangeRate(baseDate.content, rate)
    }
}

private val EXCHANGE_JSON_NUMBER = Regex("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
private fun invalidExchangeResponse(): Nothing = throw ResponseFormatException("환율 응답 형식이 올바르지 않습니다.")
