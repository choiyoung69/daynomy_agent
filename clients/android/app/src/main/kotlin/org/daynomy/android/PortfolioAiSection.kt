package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.platform.LocalDensity
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
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
            Text("AI 분석", fontSize = 24.sp, fontWeight = FontWeight.Bold)
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
                    saved.analysis?.let {
                        if (!saved.matchesCurrentPortfolio || state.portfolioChanged || saved.status in setOf("FAILED", "PROCESSING") || state.message != null) {
                            Text("이전 성공 분석 · 현재 상태와 구분해 확인하세요.", color = PortfolioStyle.muted)
                        }

                    }
                }
                val idle = !state.loading && !state.submitting
                val allowPost = idle && canGenerate && saved != null && !state.outcomeUnknown && saved.status != "PROCESSING"
                Button({ controller.generate(true) }, enabled = allowPost && saved?.analysis != null, shape = PortfolioStyle.pill,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xff0a0a0a)),
                    modifier = Modifier.heightIn(min = 48.dp).testTag("ai-refresh")) { Text("새 소식 확인") }
                if (!canGenerate) Text("보유 종목을 등록하고 거래 상태를 확인하면 분석을 요청할 수 있어요.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                if (state.outcomeUnknown) Text("요청이 처리됐을 수 있습니다. 다시 분석하기 전에 저장 상태를 조회하세요.", color = PortfolioStyle.muted)
                saved?.analysis?.let { AiResult(it) }
                OutlinedButton({ controller.generate() }, enabled = allowPost, shape = PortfolioStyle.pill,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("ai-generate")) { Text("현재 포트폴리오 분석") }
                TextButton(controller::load, enabled = idle, modifier = Modifier.heightIn(min = 48.dp).testTag("ai-reload")) { Text("저장 상태 다시 조회") }
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
    var selectedName by rememberSaveable(result.analyzedAt, result.overallImpact) { mutableStateOf<String?>(null) }
    var sourcesOpen by rememberSaveable(selectedName, result.analyzedAt) { mutableStateOf(false) }
    val impacts = result.impacts.sortedBy { it.rank }
    val selected = impacts.find { it.assetName == selectedName }
    val direction = selected?.direction ?: if (selected == null) result.overallDirection else null
    val color = impactColor(direction)
    val sources = if (selected == null) result.sources else selected.sources
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val wide = maxWidth >= 600.dp && fontScale < 1.5f
        val overview: @Composable () -> Unit = {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("자산별 영향", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Box(Modifier.size(if (wide || fontScale > 1.3f) 220.dp else 172.dp).testTag("ai-donut")
                        .semantics { contentDescription = if (selected == null) "전체 포트폴리오, ${directionLabel(direction)}" else "${selected.assetName}, 보유 비중 ${selected.weight}% , ${directionLabel(direction)}" }, contentAlignment = Alignment.Center) {
                        Canvas(Modifier.fillMaxSize()) {
                            val stroke = size.minDimension * .16f
                            val inset = stroke / 2
                            val arcSize = Size(size.width - stroke, size.height - stroke)
                            if (selected == null) drawArc(color, -90f, 360f, false, Offset(inset, inset), arcSize, style = Stroke(stroke))
                            else {
                                drawArc(Color(0xffe8eef8), -90f, 360f, false, Offset(inset, inset), arcSize, style = Stroke(stroke))
                                // A partial response is not normalized to 100%; omitted holdings remain inactive.
                                var start = -90f
                                impacts.forEach { impact ->
                                    val sweep = impact.weight.toFloat().coerceIn(0f, 100f) * 3.6f
                                    if (impact.assetName == selected.assetName) drawArc(color, start, sweep.coerceAtMost((270f - start).coerceAtLeast(0f)), false,
                                        Offset(inset, inset), arcSize, style = Stroke(stroke))
                                    start += sweep
                                }
                            }
                        }
                        Column(Modifier.width(104.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            TextButton({ selectedName = null }, contentPadding = PaddingValues(0.dp), modifier = Modifier.heightIn(min = 48.dp)) {
                                Text(if (selected == null) (if (fontScale > 1.3f) "전체" else "전체 포트폴리오") else "${selected.weight.stripTrailingZeros().toPlainString()}%", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = PortfolioStyle.ink)
                            }
                            Text(if (selected == null) "전체 분석" else "보유 비중", fontSize = 12.sp, color = PortfolioStyle.muted)
                        }
                    }
                }
                Column(Modifier.testTag("ai-impacts")) {
                    AiSelectionRow("전체 포트폴리오", result.overallScore?.stripTrailingZeros()?.toPlainString()?.plus("점") ?: "판단 보류", result.overallDirection, selected == null, "ai-overall") { selectedName = null }
                    impacts.forEachIndexed { index, impact ->
                        AiSelectionRow(impact.assetName, if (impact.direction == null) "근거 부족" else "TOP ${impact.rank}", impact.direction,
                            selected?.assetName == impact.assetName, "ai-asset-$index", selected == null || selected.assetName == impact.assetName) { selectedName = impact.assetName }
                    }
                }
                Text("색상과 영향 표시는 자산에 예상되는 영향 방향입니다.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
            }
        }
        val detail: @Composable () -> Unit = {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(if (selected == null) "전체 포트폴리오 예상 영향" else if (selected.direction == null) "보유 종목 · 근거 부족" else "포트폴리오 영향 TOP ${selected.rank} / ${result.analyzedAssetCount}", color = color, fontWeight = FontWeight.SemiBold)
                Text(selected?.assetName ?: "전체 포트폴리오", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Surface(color = color.copy(alpha = .09f), shape = RoundedCornerShape(24.dp)) {
                    Text(directionLabel(direction), Modifier.padding(horizontal = 14.dp, vertical = 8.dp), color = color, fontWeight = FontWeight.SemiBold)
                }
                if (selected == null) Text("영향 점수 ${result.overallScore?.stripTrailingZeros()?.toPlainString()?.let { if (result.overallScore!!.signum() > 0) "+$it" else it }?.plus("점") ?: "판단 보류"}", Modifier.testTag("ai-score"), fontWeight = FontWeight.Bold)
                else Text("영향 수준 ${when (selected.impactLevel) { "HIGH" -> "높음"; "MEDIUM" -> "보통"; "LOW" -> "낮음"; else -> "판단 보류" }}", color = PortfolioStyle.muted)
                if (selected == null) Text(result.overallImpact, Modifier.testTag("ai-result"), fontSize = 16.sp, lineHeight = 26.sp)
                else {
                    val paragraphs = if (selected.direction == null) listOf("판단에 필요한 근거를 확인하지 못했어요.") else listOf(selected.issueSummary, selected.expectedReaction, selected.outlook)
                    paragraphs.filter { it.isNotBlank() }.distinct().forEach { Text(it, Modifier.testTag("ai-asset-detail"), fontSize = 16.sp, lineHeight = 26.sp) }
                }
                result.analyzedAt?.let { Text(analysisTime(it), color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall) }
                Text(when (result.coverage) { "COMPLETE" -> "전체 종목 분석"; "PARTIAL" -> "일부 종목 분석"; "INSUFFICIENT" -> "분석 근거 부족"; else -> "분석 범위 정보 없음" } +
                    " · ${result.analyzedAssetCount}/${result.totalAssetCount}종목" + (result.analyzedWeight?.let { " · 분석 비중 ${it.stripTrailingZeros().toPlainString()}%" } ?: ""),
                    Modifier.testTag("ai-coverage"), color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                Column(Modifier.testTag("ai-sources")) {
                    TextButton({ sourcesOpen = !sourcesOpen }, modifier = Modifier.heightIn(min = 48.dp).testTag("ai-sources-toggle")
                        .semantics { stateDescription = if (sourcesOpen) "펼쳐짐" else "접힘" }) {
                        Text("분석 출처 모두 보기  ${if (sourcesOpen) "−" else "+"}", fontWeight = FontWeight.Bold)
                    }
                    if (sourcesOpen) {
                        if (sources.isEmpty()) Text("제공된 근거 출처가 없습니다.", color = PortfolioStyle.muted)
                        sources.distinctBy { it.url }.forEach { SourceLink(it) }
                    }
                }
            }
        }
        if (wide) Row(horizontalArrangement = Arrangement.spacedBy(32.dp)) {
            Box(Modifier.weight(.38f)) { overview() }
            Box(Modifier.weight(.62f)) { detail() }
        } else Column(verticalArrangement = Arrangement.spacedBy(24.dp)) {
            overview()
            HorizontalDivider(color = PortfolioStyle.line)
            detail()
        }
    }
}

@Composable
private fun AiSelectionRow(label: String, suffix: String?, direction: String?, selected: Boolean, tag: String, active: Boolean = true, onClick: () -> Unit) {
    val color = impactColor(direction)
    Row(Modifier.fillMaxWidth().background(if (selected) color.copy(alpha = .07f) else Color.Transparent, RoundedCornerShape(12.dp))
        .selectable(selected, role = Role.RadioButton, onClick = onClick).heightIn(min = 48.dp).testTag(tag).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Canvas(Modifier.size(9.dp)) { drawCircle(if (active) color else Color(0xffe8eef8)) }
        Text(label, Modifier.weight(1f), color = if (selected) color else PortfolioStyle.ink, fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal)
        suffix?.let { Text(it, color = color, style = MaterialTheme.typography.labelMedium) }
    }
}
private fun impactColor(direction: String?): Color = when (direction) {
    "POSITIVE" -> Color(0xffef464d)
    "NEGATIVE" -> Color(0xff3e83d7)
    else -> Color(0xff667085)
}
private fun analysisTime(value: String): String = try {
    OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("yyyy.MM.dd HH:mm")) + " 분석 기준"
} catch (_: Exception) { "분석 기준 $value" }

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
