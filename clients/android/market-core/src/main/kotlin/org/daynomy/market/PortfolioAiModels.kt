package org.daynomy.market

import java.math.BigDecimal

data class PortfolioAiSource(val title: String, val url: String, val publishedOn: String?, val occurredOn: String?, val excerpt: String?, val factQuote: String?)
data class PortfolioAiImpact(val assetName: String, val weight: BigDecimal, val direction: String?, val impactLevel: String?,
    val issueSummary: String, val expectedReaction: String, val outlook: String, val reason: String,
    val evidenceSentence: String, val sources: List<PortfolioAiSource>, val rank: Int)
data class PortfolioAiAnalysis(val totalAssetCount: Int, val analyzedAssetCount: Int, val overallDirection: String?,
    val overallScore: BigDecimal?, val positiveImpactScore: BigDecimal, val negativeImpactScore: BigDecimal,
    val analyzedAt: String?, val overallImpact: String, val impacts: List<PortfolioAiImpact>, val sources: List<PortfolioAiSource>,
    val coverage: String?, val analyzedWeight: BigDecimal?)
data class SavedPortfolioAnalysis(val status: String, val lastCheckOutcome: String?, val analysisId: Long?,
    val matchesCurrentPortfolio: Boolean, val lastSucceededAt: String?, val lastFailedAt: String?, val failureCode: String?,
    val changeReason: String?, val analysis: PortfolioAiAnalysis?)
data class PortfolioAiHistory(val analysisId: Long, val previousAnalysisId: Long?, val analyzedAt: String,
    val changeReason: String?, val analysis: PortfolioAiAnalysis)
data class PortfolioAiUiState(val saved: SavedPortfolioAnalysis? = null, val loading: Boolean = false,
    val submitting: Boolean = false, val history: List<PortfolioAiHistory>? = null, val historyLoading: Boolean = false,
    val message: String? = null, val historyError: String? = null, val loginRequired: Boolean = false,
    val outcomeUnknown: Boolean = false, val portfolioChanged: Boolean = false)
