package org.daynomy.market

import java.net.URLEncoder
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

private val SEARCH_JSON_NUMBER = Regex("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

class StockSearchClient(private val transport: HttpTransport) : StockSearchSource {
    override suspend fun search(keyword: String, country: Country): List<Stock> {
        val query = URLEncoder.encode(keyword, "UTF-8")
        val countryQuery = if (country == Country.US) "&country=US" else ""
        // Transport failures and cancellation retain their original identity.
        val body = transport.get("/api/stocks?q=$query$countryQuery")
        val root = try {
            Json.parseToJsonElement(body)
        } catch (_: SerializationException) {
            invalidResponse()
        }
        val envelope = root as? JsonObject ?: invalidResponse()
        val rows = envelope["stocks"] as? JsonArray ?: invalidResponse()
        return rows.map { decodeStock(it) }
    }

    private fun decodeStock(element: JsonElement): Stock {
        val row = element as? JsonObject ?: invalidResponse()
        val assetId = decodeId(row["assetId"])
        val assetCode = requiredString(row["assetCode"])
        val name = requiredString(row["name"])
        val categoryName = requiredString(row["category"])
        val category = Category.entries.firstOrNull { it.name == categoryName } ?: invalidResponse()
        val marketName = requiredString(row["market"])
        val market = Market.entries.firstOrNull { it.name == marketName } ?: invalidResponse()
        val currencyValue = row["currency"] as? JsonPrimitive
        val currencyName = currencyValue?.takeIf { it.isString }?.content
        val currency = Currency.entries.firstOrNull { it.name == currencyName }
            ?: if (assetCode.endsWith(".US")) Currency.USD else Currency.KRW
        return Stock(assetId, assetCode, name, category, market, currency)
    }

    private fun requiredString(value: JsonElement?): String {
        val primitive = value as? JsonPrimitive ?: invalidResponse()
        if (!primitive.isString) invalidResponse()
        return primitive.content
    }

    private fun decodeId(value: JsonElement?): Long {
        val primitive = value as? JsonPrimitive ?: invalidResponse()
        if (primitive.isString) invalidResponse()
        if (!SEARCH_JSON_NUMBER.matches(primitive.content)) invalidResponse()
        val decimal = primitive.content.toBigDecimalOrNull() ?: invalidResponse()
        // Exact decimal conversion accepts 1.0/1e0 without rounding unsafe values.
        val id = try {
            decimal.longValueExact()
        } catch (_: ArithmeticException) {
            invalidResponse()
        }
        if (id !in 1L..9_007_199_254_740_991L) invalidResponse()
        return id
    }

    private fun invalidResponse(): Nothing =
        throw ResponseFormatException("종목 검색 응답 형식이 올바르지 않습니다.")
}
