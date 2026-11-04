package org.daynomy.market

import java.math.BigDecimal
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.json.*

data class GuestHolding(val stock: Stock, val quantity: Long, val average: BigDecimal)
data class GuestPortfolioState(
    val holdings: List<GuestHolding> = emptyList(),
    val evaluating: Boolean = false,
    val evaluation: JsonObject? = null,
    val error: String? = null,
    val notice: String? = null,
)

/** An activity-session draft, never an authenticated portfolio or a server-side ledger. */
class GuestPortfolioController(transport: SessionTransport, private val scope: CoroutineScope) {
    private val client = PortfolioClient(transport)
    private val mutable = MutableStateFlow(GuestPortfolioState())
    val state: StateFlow<GuestPortfolioState> = mutable.asStateFlow()
    private var revision = 0L
    private var evaluationJob: Job? = null

    fun save(stock: Stock, quantity: String, average: String) {
        val count = quantity.toLongOrNull()?.takeIf { it in 1..9_007_199_254_740_991L }
        val price = average.takeIf { it.matches(Regex("[0-9]{1,15}(\\.[0-9]{1,2})?")) }?.toBigDecimalOrNull()
        val error = when {
            stock.assetId <= 0 -> "종목을 다시 선택해 주세요."
            count == null -> "수량은 양의 정수로 입력하세요."
            price == null || price < BigDecimal("0.01") -> "원화 평균 매수가는 0.01 이상, 정수 15자리·소수 2자리까지 입력하세요."
            state.value.holdings.size >= 50 && state.value.holdings.none { it.stock.assetId == stock.assetId } -> "최대 50개 종목까지 담을 수 있습니다."
            else -> null
        }
        if (error != null) { mutable.update { it.copy(error = error) }; return }
        invalidate()
        val next = GuestHolding(stock, count!!, price!!)
        mutable.update { old -> old.copy(holdings = if (old.holdings.any { it.stock.assetId == stock.assetId })
            old.holdings.map { if (it.stock.assetId == stock.assetId) next else it } else old.holdings + next,
            error = null, notice = "임시 포트폴리오에 반영했어요.") }
    }

    fun remove(assetId: Long) {
        invalidate()
        mutable.update { it.copy(holdings = it.holdings.filterNot { row -> row.stock.assetId == assetId }, error = null, notice = "임시 보유에서 제거했어요.") }
    }

    private fun invalidate() {
        revision++; evaluationJob?.cancel()
        mutable.update { it.copy(evaluating = false, evaluation = null) }
    }

    fun evaluate() {
        if (state.value.evaluating) return
        val snapshot = state.value.holdings
        if (snapshot.isEmpty()) { mutable.update { it.copy(error = "평가할 종목을 먼저 담아 주세요.") }; return }
        val owner = revision
        val body = buildJsonObject { put("holdings", JsonArray(snapshot.map { row -> buildJsonObject {
            put("assetId", row.stock.assetId); put("quantity", row.quantity); put("averagePurchasePrice", JsonPrimitive(row.average))
        } })) }
        mutable.update { it.copy(evaluating = true, evaluation = null, error = null, notice = null) }
        evaluationJob = scope.launch {
            try {
                val result = client.calculate(body)
                val status = result["pricingStatus"]?.jsonPrimitive?.content
                if (status !in setOf("COMPLETE", "MIXED_DATES", "PARTIAL") || result["holdings"] !is JsonArray)
                    throw ResponseFormatException("Invalid public evaluation")
                for (key in listOf("totalPurchaseAmount", "totalEvaluationAmount", "totalProfitLoss")) {
                    val value = result[key]
                    if (value != null && value !is JsonNull && (value !is JsonPrimitive || value.isString || value.content.toBigDecimalOrNull() == null))
                        throw ResponseFormatException("Invalid public amount")
                }
                if (result["holdings"]!!.jsonArray.any { value ->
                    value !is JsonObject || (value["name"] as? JsonPrimitive)?.isString != true ||
                        (value["baseDate"] != null && value["baseDate"] !is JsonNull && (value["baseDate"] as? JsonPrimitive)?.isString != true)
                }) throw ResponseFormatException("Invalid public holding")
                if (owner == revision) mutable.update { it.copy(evaluation = result) }
            } catch (failure: CancellationException) { throw failure }
            catch (_: Exception) { if (owner == revision) mutable.update { it.copy(error = "평가를 불러오지 못했어요. 종목은 보관되어 있으니 다시 평가해 주세요.") } }
            finally { if (owner == revision) mutable.update { it.copy(evaluating = false) } }
        }
    }
}
