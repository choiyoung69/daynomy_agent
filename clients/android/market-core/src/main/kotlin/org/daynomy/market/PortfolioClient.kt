package org.daynomy.market

import java.math.BigDecimal
import java.net.URLEncoder
import java.time.LocalDate
import kotlinx.serialization.json.*

/** Raw JSON is deliberate: it preserves decimal lexemes and explicit null pricing fields. */
class PortfolioClient(private val transport: SessionTransport) {
    suspend fun holdings(): JsonObject = coreObject(transport.get("/api/portfolio")).also { row ->
        val holdings = row["holdings"] as? JsonArray ?: invalidCore()
        holdings.forEach { holding(it) }
        coreDecimal(row["totalRealizedProfitLoss"])
    }
    suspend fun createTransaction(body: JsonObject): JsonObject = mutation(transport.request("POST", "/api/portfolio/transactions", body.toString()))
    suspend fun updateTransaction(id: Long, body: JsonObject): JsonObject {
        // Asset and BUY/SELL are immutable; server edits only the original transaction's details.
        val patch = JsonObject(body.filterKeys { it != "assetId" && it != "type" })
        return mutation(transport.request("PATCH", "/api/portfolio/transactions/${checkedCoreId(id)}", patch.toString()))
    }
    suspend fun deleteTransaction(id: Long) {
        val result = transport.request("DELETE", "/api/portfolio/transactions/${checkedCoreId(id)}")
        // Some versions return a replay result; 204 has no JSON body.
        if (result.isNotBlank()) mutation(result)
    }
    suspend fun histories(from: String, to: String): JsonArray =
        (coreElement(transport.get("/api/portfolio/histories?${period(from, to)}")) as? JsonArray ?: invalidCore()).also { rows ->
            rows.forEach {
                val row = it as? JsonObject ?: invalidCore()
                coreId(row["historyId"]); coreId(row["assetId"])
                for (field in listOf("quantity", "averagePurchasePrice", "unitPrice", "fee", "tax", "exchangeRate")) {
                    row[field]?.takeUnless { it == JsonNull }?.let { value -> coreDecimal(value) }
                }
            }
        }
    suspend fun performance(from: String, to: String): JsonObject = coreObject(transport.get("/api/portfolio/performance?${period(from, to)}"))
    suspend fun calculate(body: JsonObject): JsonObject = coreObject(transport.request("POST", "/api/portfolio/calculate", body.toString()))
    suspend fun updateHolding(id: Long, quantity: Long, averagePurchasePrice: BigDecimal): JsonObject {
        checkedCoreId(quantity)
        require(averagePurchasePrice.signum() > 0) { "평균 매수가를 입력해주세요." }
        val body = buildJsonObject { put("quantity", quantity); put("averagePurchasePrice", JsonPrimitive(averagePurchasePrice)) }
        val row = coreObject(transport.request("PATCH", "/api/portfolio/holdings/${checkedCoreId(id)}", body.toString()))
        holding(row)
        return row
    }
    suspend fun deleteHolding(id: Long) { transport.request("DELETE", "/api/portfolio/holdings/${checkedCoreId(id)}") }
    private fun period(from: String, to: String): String {
        require(!LocalDate.parse(from).isAfter(LocalDate.parse(to))) { "조회 기간을 확인해주세요." }
        return "from=${URLEncoder.encode(from, "UTF-8")}&to=${URLEncoder.encode(to, "UTF-8")}"
    }
    private fun holding(value: JsonElement): JsonObject {
        val row = value as? JsonObject ?: invalidCore()
        coreId(row["assetId"]); coreId(row["quantity"])
        if (coreDecimal(row["averagePurchasePrice"]).signum() < 0) invalidCore()
        return row
    }
    private fun mutation(raw: String): JsonObject = coreObject(raw).also { row ->
        coreId(row["transactionId"])
        if (!row.containsKey("holding")) invalidCore()
        row["holding"]?.takeUnless { it == JsonNull }?.let { holding(it) }
        coreDecimal(row["totalRealizedProfitLoss"])
    }
}
