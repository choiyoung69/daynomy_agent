import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate
import kotlinx.coroutines.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*

// region json
@Serializable data class RequiredCurrency(val currency: String?)
@Serializable data class DefaultCurrency(val currency: String? = null)
fun checkedId(element: JsonElement): Long {
    val primitive = element as? JsonPrimitive ?: error("ID_TYPE")
    require(!primitive.isString) { "ID_TYPE" }
    val value = primitive.longOrNull ?: error("ID_INTEGER")
    require(value in 1..9_007_199_254_740_991L) { "ID_RANGE" }
    return value
}
// endregion json

// region collections
data class Basket(val symbols: MutableList<String>)
fun detachedBasket(source: Basket) = source.copy(symbols = source.symbols.toMutableList())
// endregion collections

// region bridge
fun trustedBridgeOrigin(originFromHost: String, isMainFrame: Boolean): Boolean =
    isMainFrame && originFromHost == "https://app.example.invalid"
// endregion bridge

// region state
class Gate {
    private var generation = 0
    private var alive = true
    var result: String? = null; private set
    fun begin(): Int = ++generation
    fun accept(id: Int, value: String): Boolean {
        if (!alive || id != generation) return false
        result = value
        return true
    }
    fun dispose() { alive = false; generation++ }
}
// endregion state

// region cancellation
suspend fun cancelledWorkCleansUp(): Boolean = coroutineScope {
    val started = CompletableDeferred<Unit>()
    var cleaned = false
    val job = launch {
        try { started.complete(Unit); awaitCancellation() }
        finally { cleaned = true }
    }
    started.await()
    job.cancelAndJoin()
    cleaned
}
// endregion cancellation

fun main() = runBlocking {
    val results = linkedMapOf<String, Boolean>()
    fun test(name: String, condition: Boolean) { check(condition) { name }; results[name] = condition }
    test("required_nullable_missing_rejected", runCatching { Json.decodeFromString<RequiredCurrency>("{}") }.isFailure)
    test("explicit_null_accepted", Json.decodeFromString<RequiredCurrency>("{\"currency\":null}").currency == null)
    test("nullable_default_handles_missing", Json.decodeFromString<DefaultCurrency>("{}").currency == null)
    test("implicit_null_changes_missing_policy", Json { explicitNulls = false }.decodeFromString<RequiredCurrency>("{}").currency == null)
    test("unknown_key_default_rejected", runCatching { Json.decodeFromString<DefaultCurrency>("{\"extra\":1}") }.isFailure)
    test("unknown_key_can_be_allowed", Json { ignoreUnknownKeys = true }.decodeFromString<DefaultCurrency>("{\"extra\":1}").currency == null)
    test("safe_id", checkedId(Json.parseToJsonElement("9007199254740991")) == 9_007_199_254_740_991L)
    test("large_id_rejected", runCatching { checkedId(Json.parseToJsonElement("9007199254740993")) }.isFailure)
    test("quoted_id_rejected", runCatching { checkedId(Json.parseToJsonElement("\"1\"")) }.isFailure)
    test("decimal_round_half_up", BigDecimal("1.005").setScale(2, RoundingMode.HALF_UP).toPlainString() == "1.01")
    test("decimal_sum", BigDecimal("0.1") + BigDecimal("0.2") == BigDecimal("0.3"))
    test("invalid_calendar_rejected", runCatching { LocalDate.parse("2026-02-30") }.isFailure)
    test("emoji_utf16_two", "😀".length == 2)
    test("kotlin_trim_nbsp", "\u00a0삼성\u00a0".trim().length == 2)
    val source = Basket(mutableListOf("A")); val shallow = source.copy(); val detached = detachedBasket(source)
    source.symbols.add("B")
    test("data_copy_is_shallow", shallow.symbols.size == 2)
    test("detached_list", detached.symbols.size == 1)
    val mutable = mutableListOf(1); val readOnly: List<Int> = mutable; mutable.add(2)
    test("read_only_is_not_immutable_snapshot", readOnly.size == 2)
    val gate = Gate(); val a = gate.begin(); val b = gate.begin()
    test("newest_result", gate.accept(b, "B"))
    test("old_result_ignored", !gate.accept(a, "A") && gate.result == "B")
    gate.dispose(); test("disposed_ignored", !gate.accept(b, "late"))
    test("cancel_finally", cancelledWorkCleansUp())
    test("run_catching_catches_cancellation", runCatching { throw CancellationException("synthetic") }.isFailure)
    test("bridge_trusted_origin", trustedBridgeOrigin("https://app.example.invalid", true))
    test("bridge_other_origin_rejected", !trustedBridgeOrigin("https://attacker.example.invalid", true))
    test("bridge_subframe_rejected", !trustedBridgeOrigin("https://app.example.invalid", false))
    println(Json.encodeToString(results))
}
