package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.daynomy.market.*

@Composable
internal fun PortfolioAiSection(controller: PortfolioAiController, canGenerate: Boolean, onAccount: () -> Unit) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    val state by controller.state.collectAsStateWithLifecycle()
    LaunchedEffect(expanded) { if (expanded) controller.load() }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        OutlinedButton({ expanded = !expanded }, shape = PortfolioStyle.pill,
            modifier = Modifier.heightIn(min = 48.dp).testTag("ai-toggle").semantics { stateDescription = if (expanded) "펼쳐짐" else "접힘" }) {
            Text(if (expanded) "AI 포트폴리오 분석 접기" else "AI 포트폴리오 분석")
        }
        if (expanded) {
            Text("보유 종목의 이슈와 영향을 확인하세요.", color = PortfolioStyle.muted)
            if (state.loading || state.submitting) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(if (state.submitting) "AI 분석을 요청하고 있어요." else "저장된 분석을 불러오고 있어요.",
                    Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
            state.message?.let { Text(it, Modifier.testTag("ai-error").semantics { liveRegion = LiveRegionMode.Polite }, color = MaterialTheme.colorScheme.error) }
            if (state.loginRequired) {
                Text("AI 포트폴리오 분석은 로그인 후 이용할 수 있어요.")
                Button(onAccount, modifier = Modifier.heightIn(min = 48.dp).testTag("ai-login"), shape = PortfolioStyle.pill) { Text("내 계정에서 로그인") }
            } else {
                val saved = state.saved
                if (saved != null) {
                    Text(if (state.portfolioChanged) "현재 보유 자산과 일치 여부를 다시 확인해 주세요." else statusLabel(saved.status),
                        Modifier.testTag("ai-status").semantics { liveRegion = LiveRegionMode.Polite }, fontWeight = FontWeight.SemiBold)
                    saved.lastCheckOutcome?.let { outcome ->
                        Text(when (outcome) { "UNCHANGED" -> "같은 근거의 저장된 분석을 재사용했습니다."; "UNCONFIRMED" -> "최신 근거 확인이 필요합니다."; else -> "분석 결과가 갱신되었습니다." },
                            color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                    }
                    saved.analysis?.let { result ->
                        if (!saved.matchesCurrentPortfolio || state.portfolioChanged || saved.status in setOf("FAILED", "PROCESSING") || state.message != null) {
                            Text("이전 성공 분석 · 현재 상태와 구분해 확인하세요.", color = PortfolioStyle.muted)
                        }
                        AiResult(result)
                    }
                }
                val idle = !state.loading && !state.submitting
                val allowPost = idle && canGenerate && saved != null && !state.outcomeUnknown && saved.status != "PROCESSING"
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button({ controller.generate() }, enabled = allowPost, shape = PortfolioStyle.pill,
                        modifier = Modifier.heightIn(min = 48.dp).testTag("ai-generate")) { Text("현재 포트폴리오 분석") }
                    OutlinedButton({ controller.generate(true) }, enabled = allowPost && saved?.analysis != null, shape = PortfolioStyle.pill,
                        modifier = Modifier.heightIn(min = 48.dp).testTag("ai-refresh")) { Text("최신 근거 확인") }
                    TextButton(controller::load, enabled = idle, modifier = Modifier.heightIn(min = 48.dp).testTag("ai-reload")) { Text("저장 상태 다시 조회") }
                }
                if (!canGenerate) Text("보유 종목을 등록하고 거래 상태를 확인하면 분석을 요청할 수 있어요.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                if (state.outcomeUnknown) Text("요청이 처리됐을 수 있습니다. 다시 분석하기 전에 저장 상태를 조회하세요.", color = PortfolioStyle.muted)
                TextButton(controller::loadHistory, enabled = !state.historyLoading && !state.submitting,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("ai-history")) { Text("분석 이력 조회") }
                if (state.historyLoading) Text("분석 이력을 불러오고 있어요.")
                state.historyError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                state.history?.let { history ->
                    Column(Modifier.testTag("ai-history-list"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("최근 분석 이력", fontWeight = FontWeight.Bold)
                        if (history.isEmpty()) Text("저장된 분석 이력이 없습니다.", color = PortfolioStyle.muted)
                        history.forEach { row ->
                            HorizontalDivider(color = PortfolioStyle.line)
                            Text(row.analyzedAt, style = MaterialTheme.typography.bodySmall, color = PortfolioStyle.muted)
                            Text(row.analysis.overallImpact)
                            Text("종합 점수 ${row.analysis.overallScore?.stripTrailingZeros()?.toPlainString()?.plus("점") ?: "판단 보류"}")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AiResult(result: PortfolioAiAnalysis) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(result.overallImpact, Modifier.testTag("ai-result"), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        result.analyzedAt?.let { Text("분석 기준 $it", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall) }
        Text("종합 점수 ${result.overallScore?.stripTrailingZeros()?.toPlainString()?.plus("점") ?: "판단 보류"}", Modifier.testTag("ai-score"), fontWeight = FontWeight.Bold)
        Text(when (result.coverage) { "COMPLETE" -> "전체 종목 분석"; "PARTIAL" -> "일부 종목 분석"; "INSUFFICIENT" -> "분석 근거 부족"; else -> "분석 범위 정보 없음" } +
            " · ${result.analyzedAssetCount}/${result.totalAssetCount}종목" + (result.analyzedWeight?.let { " · 분석 비중 ${it.stripTrailingZeros().toPlainString()}%" } ?: ""),
            Modifier.testTag("ai-coverage"), color = PortfolioStyle.muted)
        Column(Modifier.testTag("ai-impacts"), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            result.impacts.forEach { impact ->
                HorizontalDivider(color = PortfolioStyle.line)
                Text("${impact.assetName} · ${impact.weight.stripTrailingZeros().toPlainString()}%", fontWeight = FontWeight.Bold)
                Text(directionLabel(impact.direction) + (impact.impactLevel?.let { " · 영향 ${when (it) { "HIGH" -> "높음"; "MEDIUM" -> "보통"; else -> "낮음" }}" } ?: ""), color = PortfolioStyle.muted)
                listOf(impact.issueSummary, impact.expectedReaction, impact.outlook, impact.reason, impact.evidenceSentence).filter { it.isNotBlank() }.distinct().forEach { Text(it) }
            }
        }
        val sources = (result.sources + result.impacts.flatMap { it.sources }).distinctBy { it.url }
        Column(Modifier.testTag("ai-sources"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("분석 근거", fontWeight = FontWeight.Bold)
            if (sources.isEmpty()) Text("제공된 근거 출처가 없습니다.", color = PortfolioStyle.muted)
            sources.forEach { source -> SourceLink(source) }
        }
    }
}

@Composable
private fun SourceLink(source: PortfolioAiSource) {
    val uri = LocalUriHandler.current
    var failed by remember { mutableStateOf(false) }
    TextButton({ try { uri.openUri(source.url); failed = false } catch (_: Exception) { failed = true } },
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(source.title) }
    source.publishedOn?.let { Text("발행일 $it", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall) }
    source.factQuote?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    if (failed) Text("출처 링크를 열지 못했습니다.", color = MaterialTheme.colorScheme.error)
}
private fun directionLabel(value: String?): String = when (value) { "POSITIVE" -> "긍정 영향"; "NEGATIVE" -> "부정 영향"; "NEUTRAL" -> "중립 영향"; else -> "근거 부족 · 판단 보류" }
private fun statusLabel(value: String): String = when (value) {
    "EMPTY" -> "저장된 AI 분석이 없습니다."
    "READY" -> "저장된 AI 분석"
    "PORTFOLIO_CHANGED" -> "보유 자산이 변경되어 재분석이 필요합니다."
    "PROCESSING" -> "AI 분석이 진행 중입니다. 상태를 다시 조회하세요."
    "RECHECK_REQUIRED" -> "최신 근거를 다시 확인해 주세요."
    else -> "최근 분석에 실패했습니다. 이전 결과를 확인하세요."
}
