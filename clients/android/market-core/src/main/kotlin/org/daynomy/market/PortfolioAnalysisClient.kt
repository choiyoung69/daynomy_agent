package org.daynomy.market

import kotlinx.serialization.json.*
import java.math.BigDecimal
import java.net.URI

/** Member F06 only. Reuses the owning session's CSRF, cookies and refresh boundary. */
class PortfolioAnalysisClient(private val transport: SessionTransport) {
    suspend fun saved(): SavedPortfolioAnalysis = saved(coreObject(transport.get(PATH)))
    suspend fun generate(refresh: Boolean = false): SavedPortfolioAnalysis =
        saved(coreObject(transport.request("POST", PATH + if (refresh) "/refresh" else "", null)))
    suspend fun history(): List<PortfolioAiHistory> {
        val rows = coreElement(transport.get("$PATH/history")) as? JsonArray ?: invalidCore()
        return rows.map { value ->
            val row = value as? JsonObject ?: invalidCore()
            PortfolioAiHistory(coreId(row["analysisId"]), nullableId(row, "previousAnalysisId"), coreText(row["analyzedAt"]),
                nullableText(row, "changeReason"), analysis(row["analysis"]))
        }
    }
    private fun saved(row: JsonObject): SavedPortfolioAnalysis = SavedPortfolioAnalysis(
        enumValue(row["status"], setOf("EMPTY", "READY", "PORTFOLIO_CHANGED", "PROCESSING", "RECHECK_REQUIRED", "FAILED")),
        nullableEnum(row, "lastCheckOutcome", setOf("UPDATED", "UNCHANGED", "UNCONFIRMED")), nullableId(row, "analysisId"),
        (row["matchesCurrentPortfolio"] as? JsonPrimitive)?.takeUnless { it.isString }?.booleanOrNull ?: invalidCore(),
        nullableText(row, "lastSucceededAt"), nullableText(row, "lastFailedAt"), nullableText(row, "failureCode"),
        nullableText(row, "changeReason"), if (required(row, "analysis") == JsonNull) null else analysis(row["analysis"]))
    private fun analysis(value: JsonElement?): PortfolioAiAnalysis {
        val r = value as? JsonObject ?: invalidCore()
        return PortfolioAiAnalysis(integer(r["totalAssetCount"]), integer(r["analyzedAssetCount"]),
            nullableEnum(r, "overallDirection", directions), nullableDecimal(r, "overallScore"),
            coreDecimal(r["positiveImpactScore"]), coreDecimal(r["negativeImpactScore"]), nullableText(r, "analyzedAt"),
            coreText(r["overallImpact"]), array(r["impacts"]).map(::impact), array(r["sources"]).map(::source),
            if (r.containsKey("coverage")) enumValue(r["coverage"], setOf("COMPLETE", "PARTIAL", "INSUFFICIENT")) else null,
            if (r.containsKey("analyzedWeight")) coreDecimal(r["analyzedWeight"]) else null)
    }
    private fun impact(value: JsonElement): PortfolioAiImpact {
        val r = value as? JsonObject ?: invalidCore()
        val direction = nullableEnum(r, "direction", directions)
        val level = nullableEnum(r, "impactLevel", setOf("HIGH", "MEDIUM", "LOW"))
        if ((direction == null) != (level == null)) invalidCore()
        return PortfolioAiImpact(coreText(r["assetName"]), coreDecimal(r["weight"]), direction, level,
            coreText(r["issueSummary"]), coreText(r["expectedReaction"]), coreText(r["outlook"]), coreText(r["reason"]),
            coreText(r["evidenceSentence"]), array(r["sources"]).map(::source), integer(r["rank"]))
    }
    private fun source(value: JsonElement): PortfolioAiSource {
        val r = value as? JsonObject ?: invalidCore()
        val url = coreText(r["url"])
        val uri = try { URI(url) } catch (_: Exception) { invalidCore() }
        if (uri.scheme?.lowercase() !in setOf("http", "https") || uri.host.isNullOrEmpty()) invalidCore()
        fun optional(key: String): String? = if (r[key] == null || r[key] == JsonNull) null else coreText(r[key])
        return PortfolioAiSource(coreText(r["title"]), url, optional("publishedOn"), optional("occurredOn"),
            if (r.containsKey("excerpt")) coreText(r["excerpt"]) else null, optional("factQuote"))
    }
    private fun integer(value: JsonElement?): Int = try { coreDecimal(value).intValueExact() } catch (_: ArithmeticException) { invalidCore() }
    private fun array(value: JsonElement?): JsonArray = value as? JsonArray ?: invalidCore()
    private fun required(r: JsonObject, key: String): JsonElement = r[key] ?: invalidCore()
    private fun nullableText(r: JsonObject, key: String): String? = required(r, key).let { if (it == JsonNull) null else coreText(it) }
    private fun nullableDecimal(r: JsonObject, key: String): BigDecimal? = required(r, key).let { if (it == JsonNull) null else coreDecimal(it) }
    private fun nullableId(r: JsonObject, key: String): Long? = required(r, key).let { if (it == JsonNull) null else coreId(it) }
    private fun enumValue(value: JsonElement?, allowed: Set<String>): String = coreText(value).also { if (it !in allowed) invalidCore() }
    private fun nullableEnum(r: JsonObject, key: String, allowed: Set<String>): String? = required(r, key).let { if (it == JsonNull) null else enumValue(it, allowed) }
    companion object {
        private const val PATH = "/api/users/me/portfolio/analysis"
        private val directions = setOf("POSITIVE", "NEGATIVE", "NEUTRAL")
    }
}
