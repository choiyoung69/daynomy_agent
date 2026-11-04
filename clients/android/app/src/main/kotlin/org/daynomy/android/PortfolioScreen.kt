package org.daynomy.android

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import org.daynomy.market.Country
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

/** Tokens extracted from reference frontend index.css + portfolioLedger.css; scoped to this screen. */
internal object PortfolioStyle {
    val ink = Color(0xFF171821)
    val muted = Color(0xFF52647F)
    val line = Color(0xFFE4E7EF)
    val blue = Color(0xFF326BD5)
    val soft = Color(0xFFF1F3F7)
    val pill = RoundedCornerShape(999.dp)
    val panel = RoundedCornerShape(14.dp)
    val colors = lightColorScheme(primary = Color(0xFF0A0A0A), onPrimary = Color.White,
        secondary = blue, onSecondary = Color.White, secondaryContainer = Color(0xFFEDF3FC), onSecondaryContainer = blue, background = Color.White, surface = Color.White,
        onSurface = ink, onSurfaceVariant = muted, surfaceVariant = soft, outline = line, outlineVariant = line,
        error = Color(0xFFB42318))
}

@Composable
fun PortfolioScreen(model: CoreViewModel, onAccount: () -> Unit = {}) {
    MaterialTheme(colorScheme = PortfolioStyle.colors) {
        var editorOpen by rememberSaveable { mutableStateOf(false) }
        var historyTab by rememberSaveable { mutableStateOf(false) }
        var amountsHidden by rememberSaveable { mutableStateOf(false) }
        var analysisOpen by rememberSaveable { mutableStateOf(true) }
        var removal by remember { mutableStateOf<Pair<String, Long>?>(null) }
        var adjustment by remember { mutableStateOf<JsonObject?>(null) }
        var adjustQuantity by remember { mutableStateOf("") }
        var adjustAverage by remember { mutableStateOf("") }
        val focus = LocalFocusManager.current
        val dashboardScroll = rememberScrollState()
        val editorScroll = rememberScrollState()
        LaunchedEffect(editorOpen) { if (editorOpen) editorScroll.scrollTo(0) }
        val canWrite = !model.busy && !model.unknown && !model.portfolioRequiresLogin
        LaunchedEffect(Unit) { model.refreshPortfolio() }
        BackHandler(editorOpen) { if (!model.busy) { focus.clearFocus(); editorOpen = false } }
        fun openTrade() { if (model.editId != null) model.cancelEdit(); editorOpen = true }

        Surface(Modifier.fillMaxSize(), color = Color.White) {
            BoxWithConstraints(Modifier.fillMaxSize()) {
                val gutter = if (maxWidth <= 600.dp) 36.dp else (16 + (maxWidth.value * .08f).coerceIn(32f, 128f)).dp
                Column(Modifier.fillMaxSize().imePadding().verticalScroll(if (editorOpen) editorScroll else dashboardScroll)
                    .padding(horizontal = gutter, vertical = 28.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
                    if (editorOpen) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            SectionTitle(if (model.editId == null) "거래 기록" else "거래 수정")
                            TextButton({ focus.clearFocus(); editorOpen = false }, enabled = !model.busy,
                                modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-close")) { Text("닫기") }
                        }
                        Text("매수와 매도를 기록하고 자산의 흐름을 확인하세요.", color = PortfolioStyle.muted)
                        PortfolioNotice(model)
                        PortfolioTransactionForm(model)
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("내 포트폴리오", Modifier.semantics { heading() },
                                style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                            Text(if (model.portfolioRequiresLogin) "로그인하면 계정의 자산과 거래 내역을 확인할 수 있어요."
                                else "계정에 저장한 보유 자산과 거래 기록을 확인하세요.",
                                color = PortfolioStyle.blue, style = MaterialTheme.typography.bodyMedium)
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton({ focus.clearFocus(); model.refreshPortfolio() },
                                enabled = !model.busy && !model.loading, shape = PortfolioStyle.pill,
                                modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("portfolio-refresh")) {
                                Text("새로고침")
                            }
                            Button({ openTrade() }, enabled = canWrite && model.portfolioLoaded, shape = PortfolioStyle.pill,
                                modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("transaction-open")) {
                                Text("거래 기록")
                            }
                        }
                        PortfolioNotice(model)
                        if (model.loading) {
                            LinearProgressIndicator(Modifier.fillMaxWidth())
                            Text("보유 자산과 거래 내역을 불러오고 있어요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                        }
                        if (model.portfolioRequiresLogin) {
                            PortfolioPanel {
                                SectionTitle("로그인이 필요해요")
                                Text("Android는 아직 비회원 자산의 임시 저장을 지원하지 않습니다.", color = PortfolioStyle.muted)
                                Button(onAccount, shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-login")) {
                                    Text("계정에서 로그인")
                                }
                            }
                        }
                        PortfolioSummary(model, amountsHidden, { amountsHidden = !amountsHidden })
                        HorizontalDivider(color = PortfolioStyle.line)
                        TextButton({ analysisOpen = !analysisOpen }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .testTag("portfolio-analysis-toggle").semantics { stateDescription = if (analysisOpen) "펼쳐짐" else "접힘" }) {
                            Text(if (analysisOpen) "자산 분석 접기" else "자산 분석 펼치기", Modifier.weight(1f), fontWeight = FontWeight.Bold)
                        }
                        if (analysisOpen) PortfolioAnalysis(model, amountsHidden)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            FilterChip(!historyTab, { historyTab = false }, label = { Text("보유 자산 ${if (model.portfolioLoaded) model.holdings.size else "—"}") },
                                modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-holdings-tab"))
                            FilterChip(historyTab, { historyTab = true }, label = { Text("거래 내역") },
                                modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-history-tab"))
                        }
                        if (historyTab) {
                            SectionTitle("거래 내역")
                            CoreField(model.from, { model.from = it }, "조회 시작일 (YYYY-MM-DD)", "portfolio-from", enabled = !model.busy)
                            CoreField(model.to, { model.to = it }, "조회 종료일 (YYYY-MM-DD)", "portfolio-to", enabled = !model.busy)
                            OutlinedButton({ focus.clearFocus(); model.refreshPortfolio() }, enabled = !model.busy && !model.loading,
                                modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-history-refresh")) { Text("이 기간의 내역 조회") }
                            if (model.portfolioLoaded && model.history.isEmpty()) Text("조회 기간에 거래·조정 내역이 없습니다.", color = PortfolioStyle.muted)
                            model.history.forEach { element ->
                                val row = element as? JsonObject ?: return@forEach
                                val id = row["historyId"]?.jsonPrimitive?.longOrNull ?: return@forEach
                                val kind = row.text("changeType")
                                val title = when (kind) { "BUY" -> "매수"; "SELL" -> "매도"; "ADJUSTED" -> "보유 조정"; "REMOVED" -> "보유 제거"; else -> "보유 등록" }
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("${row.text("effectiveDate")} · $title · ${row.text("name")}", fontWeight = FontWeight.SemiBold)
                                    if (kind == "BUY" || kind == "SELL") {
                                        Text("${row.text("transactionQuantity")}주 · 단가 ${displayNumber(row.text("unitPrice"), amountsHidden)} ${row.text("currency")}")
                                        Text("수수료 ${displayNumber(row.text("fee"), amountsHidden)} · 세금 ${displayNumber(row.text("tax"), amountsHidden)}", color = PortfolioStyle.muted)
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            OutlinedButton({ focus.clearFocus(); model.edit(row); editorOpen = true }, enabled = canWrite,
                                                modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-edit-$id")) { Text("거래 수정") }
                                            TextButton({ removal = "transaction" to id }, enabled = canWrite,
                                                modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-delete-$id")) { Text("거래 삭제") }
                                        }
                                    } else Text("${row.text("quantity")}주 · 평균 매수가 ${displayNumber(row.text("averagePurchasePrice"), amountsHidden)}원")
                                    HorizontalDivider(color = PortfolioStyle.line)
                                }
                            }
                        } else {
                            if (model.portfolioLoaded && model.holdings.isEmpty()) {
                                Column(Modifier.fillMaxWidth().padding(vertical = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Text("보유 중인 자산이 없어요", fontWeight = FontWeight.SemiBold)
                                    Text("매수·매도를 기록하고 보유 자산의 평가금액을 확인해 보세요.", color = PortfolioStyle.muted)
                                    OutlinedButton({ openTrade() }, enabled = canWrite, shape = PortfolioStyle.pill,
                                        modifier = Modifier.heightIn(min = 48.dp)) { Text("거래 기록하기") }
                                }
                            }
                            model.holdings.forEach { element ->
                                val row = element as? JsonObject ?: return@forEach
                                val id = row["assetId"]?.jsonPrimitive?.longOrNull ?: return@forEach
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text(row.text("name").ifBlank { row.text("assetCode") }, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    Text("${row.text("quantity")}주 · 평균 매수가 ${displayNumber(row.text("averagePurchasePrice"), amountsHidden)}원", color = PortfolioStyle.muted)
                                    Column {
                                        TextButton({ adjustment = row; adjustQuantity = row.text("quantity"); adjustAverage = row.text("averagePurchasePrice") }, enabled = canWrite,
                                            modifier = Modifier.heightIn(min = 48.dp).testTag("holding-edit-$id")) { Text("수량·평균가 조정") }
                                        TextButton({ removal = "holding" to id }, enabled = canWrite,
                                            modifier = Modifier.heightIn(min = 48.dp).testTag("holding-delete-$id")) { Text("제거") }
                                    }
                                    HorizontalDivider(color = PortfolioStyle.line)
                                }
                            }
                        }
                        HorizontalDivider(color = PortfolioStyle.line)
                        SectionTitle("보유 자산 소식")
                        Text("관련 소식 연결은 준비 중입니다.", color = PortfolioStyle.muted)
                        Text("발행된 뉴스는 하단 이슈 메뉴에서 볼 수 있어요.", style = MaterialTheme.typography.bodyMedium, color = PortfolioStyle.muted)
                    }
                }
            }
        }
        removal?.let { (kind, id) ->
            AlertDialog(onDismissRequest = { if (!model.busy) removal = null }, title = { Text(if (kind == "transaction") "거래 삭제" else "보유자산 제거") },
                text = { Text(if (kind == "transaction") "이 거래를 삭제하고 보유 수량을 다시 계산합니다. 계속할까요?" else "보유자산을 제거하고 변경 이력을 남깁니다. 계속할까요?") },
                confirmButton = { TextButton({ removal = null; focus.clearFocus(); if (kind == "transaction") model.deleteTransaction(id) else model.removeHolding(id) }, enabled = canWrite, modifier = Modifier.heightIn(min = 48.dp)) { Text("삭제하기") } },
                dismissButton = { TextButton({ removal = null }, modifier = Modifier.heightIn(min = 48.dp)) { Text("취소") } })
        }
        adjustment?.let { row ->
            AlertDialog(onDismissRequest = { adjustment = null }, title = { Text("보유 수량·평균가 조정") },
                text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("평균 매수가는 원화 기준입니다.")
                    CoreField(adjustQuantity, { adjustQuantity = it }, "보유 수량", "holding-quantity", KeyboardType.Number)
                    CoreField(adjustAverage, { adjustAverage = it }, "원화 평균 매수가", "holding-average", KeyboardType.Decimal)
                } },
                confirmButton = { TextButton({ model.adjustHolding(row["assetId"]!!.jsonPrimitive.long, adjustQuantity, adjustAverage); adjustment = null }, enabled = canWrite, modifier = Modifier.heightIn(min = 48.dp)) { Text("조정 저장") } },
                dismissButton = { TextButton({ adjustment = null }, modifier = Modifier.heightIn(min = 48.dp)) { Text("취소") } })
        }
    }
}

@Composable private fun PortfolioNotice(model: CoreViewModel) {
    if (model.unknown) {
        Text("처리 결과 확인 필요", Modifier.testTag("transaction-unknown").semantics { liveRegion = LiveRegionMode.Assertive }, color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Bold)
        Text("같은 거래를 다시 보내지 마세요. 내역을 새로 조회해 거래가 반영됐는지 확인하세요.")
    }
    CoreMessage(model.message)
}

@Composable private fun PortfolioSummary(model: CoreViewModel, hidden: Boolean, toggle: () -> Unit) {
    val empty = model.portfolioLoaded && model.holdings.isEmpty()
    fun value(key: String) = when { !model.portfolioLoaded -> "—"; empty -> displayNumber("0", hidden) + "원"; model.evaluation == null -> "평가 조회 필요"; else -> displayWon(model.evaluation?.text(key), hidden) }
    Column(Modifier.fillMaxWidth().testTag("portfolio-summary"), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("전체 자산 평가금액", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodyMedium)
            TextButton(toggle, modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-summary-toggle").semantics { stateDescription = if (hidden) "금액 숨겨짐" else "금액 표시됨" }) {
                Text(if (hidden) "금액 보기" else "금액 숨기기")
            }
        }
        Text(value("totalEvaluationAmount"), Modifier.testTag("portfolio-summary-amount"), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("최근 거래일 손익 ${displayNumber(model.evaluation?.text("dailyProfitLoss"), hidden)}", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodyMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("보유자산 매입금액", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                Text(value("totalPurchaseAmount"), fontWeight = FontWeight.SemiBold)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("평가손익", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                Text(value("totalProfitLoss"), fontWeight = FontWeight.SemiBold)
            }
        }
        Text("누적 실현손익", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
        Text(if (model.portfolioLoaded) displayNumber(model.totalRealizedProfitLoss, hidden) + "원" else "—", fontWeight = FontWeight.SemiBold)
        Text(when (model.evaluation?.text("pricingStatus")) {
            "PARTIAL" -> "일부 종목의 가격을 확인하지 못했습니다. 미평가 금액은 —로 표시합니다."
            "MIXED_DATES" -> "종목별 가격 기준일이 다릅니다."
            else -> if (empty) "매수·매도 거래를 기록해 시작하세요." else "최근 저장 종가 기준입니다. 평가 조회는 거래를 저장하지 않습니다."
        }, color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
        model.evaluation?.text("baseDate")?.takeUnless { it.isBlank() || it == "null" }?.let { Text("종가 기준일 $it", color = PortfolioStyle.muted) }
    }
}

@Composable private fun PortfolioAnalysis(model: CoreViewModel, hidden: Boolean) {
    var periodOpen by rememberSaveable { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        PortfolioPanel {
            SectionTitle("자산 추이")
            Text("저장된 수익률을 조회합니다. 그래프 시각화는 준비 중입니다.", color = PortfolioStyle.muted)
            TextButton({ periodOpen = !periodOpen }, modifier = Modifier.heightIn(min = 48.dp)
                .semantics { stateDescription = if (periodOpen) "펼쳐짐" else "접힘" }) { Text("조회 기간 변경") }
            if (periodOpen) {
                CoreField(model.from, { model.from = it }, "조회 시작일 (YYYY-MM-DD)", "performance-from", enabled = !model.busy)
                CoreField(model.to, { model.to = it }, "조회 종료일 (YYYY-MM-DD)", "performance-to", enabled = !model.busy)
            }
            Text("${model.from} ~ ${model.to}", style = MaterialTheme.typography.bodySmall, color = PortfolioStyle.muted)
            OutlinedButton(model::loadPerformance, enabled = !model.busy && model.portfolioLoaded,
                modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-performance")) { Text("기간 수익률 조회") }
            model.performance?.let { result ->
                Text(if (result.text("status") == "INSUFFICIENT_DATA") "수익률을 계산할 자료가 충분하지 않습니다." else "기간별 수익률")
                (result["points"] as? JsonArray).orEmpty().forEach { point -> (point as? JsonObject)?.let { PortfolioPoint(it, hidden) } }
                (result["currentPoint"] as? JsonObject)?.let { PortfolioPoint(it, hidden) }
            }
        }
        PortfolioPanel {
            SectionTitle("자산 구성")
            when {
                !model.portfolioLoaded -> Text("보유 자산 조회 후 확인할 수 있어요.", color = PortfolioStyle.muted)
                model.holdings.isEmpty() -> Text("표시할 자산이 없습니다", color = PortfolioStyle.muted)
                else -> Text("보유 자산 ${model.holdings.size}개 · 최근 종가로 평가를 조회하세요.", color = PortfolioStyle.muted)
            }
            OutlinedButton(model::evaluate, enabled = !model.busy && !model.loading && model.portfolioLoaded && model.holdings.isNotEmpty(),
                modifier = Modifier.heightIn(min = 48.dp).testTag("portfolio-evaluate")) { Text("최근 종가로 평가 조회") }
            (model.evaluation?.get("holdings") as? JsonArray).orEmpty().forEach { holding ->
                (holding as? JsonObject)?.let { row -> Text("${row.text("name")} · 비중 ${displayNumber(row.text("weight"), hidden)}%") }
            }
            Text("평가 조회는 거래를 저장하지 않습니다.", style = MaterialTheme.typography.bodySmall, color = PortfolioStyle.muted)
        }
    }
}

@Composable private fun PortfolioPoint(row: JsonObject, hidden: Boolean) {
    if (row.text("baseDate").isNotBlank()) Text("기준일 ${row.text("baseDate")}")
    Text("매입 ${displayNumber(row.text("totalPurchaseAmount"), hidden)}원 · 평가 ${displayNumber(row.text("totalEvaluationAmount"), hidden)}원")
    Text("손익 ${displayNumber(row.text("totalProfitLoss"), hidden)}원 · 수익률 ${displayNumber(row.text("totalReturnRate"), hidden)}%")
}
@Composable private fun PortfolioPanel(content: @Composable ColumnScope.() -> Unit) {
    Surface(Modifier.fillMaxWidth(), shape = PortfolioStyle.panel, border = BorderStroke(1.dp, PortfolioStyle.line), color = Color.White) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp), content = content)
    }
}
@Composable private fun SectionTitle(text: String) {
    Text(text, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
}
private fun displayWon(raw: String?, hidden: Boolean): String {
    val number = displayNumber(raw, hidden)
    return if (number == "—") number else "${number}원"
}
private fun displayNumber(raw: String?, hidden: Boolean): String {
    if (hidden) return "••••••"
    val amount = raw?.takeUnless { it.isBlank() || it == "null" }?.toBigDecimalOrNull() ?: return "—"
    return DecimalFormat("#,##0.############################", DecimalFormatSymbols(Locale.KOREA)).format(amount)
}

@Composable private fun PortfolioTransactionForm(model: CoreViewModel) {
    val focus = LocalFocusManager.current
    val canWrite = !model.busy && !model.unknown && !model.portfolioRequiresLogin
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        CoreField(model.query, model::search, "종목명 또는 종목코드 검색", "transaction-asset", enabled = canWrite && model.editId == null)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Country.entries.forEach { country ->
                FilterChip(model.country == country, { model.searchCountry(country) }, label = { Text(if (country == Country.KR) "국내" else "미국") },
                    enabled = canWrite && model.editId == null, modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-country-${country.name}"))
            }
        }
        if (model.searchBusy) Text("종목을 찾고 있어요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        model.searchResults.forEach { stock ->
            OutlinedButton({ focus.clearFocus(); model.select(stock) }, enabled = canWrite,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("transaction-stock-${stock.assetId}")) { Text("${stock.name} · ${stock.assetCode}") }
        }
        model.selection?.let { Text("선택 종목: ${it.name} · ${it.code} (${it.currency})", Modifier.testTag("transaction-selected")) }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            listOf("BUY" to "매수", "SELL" to "매도").forEach { (type, title) ->
                FilterChip(model.type == type, { model.type = type }, label = { Text(title) }, enabled = canWrite && model.editId == null,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-type-$type"))
            }
        }
        CoreField(model.quantity, { model.quantity = it }, "수량", "transaction-quantity", KeyboardType.Number, canWrite)
        CoreField(model.price, { model.price = it }, "거래 단가", "transaction-price", KeyboardType.Decimal, canWrite)
        CoreField(model.tradeDate, { model.tradeDate = it }, "거래일 (YYYY-MM-DD)", "transaction-date", enabled = canWrite)
        CoreField(model.fee, { model.fee = it }, "수수료", "transaction-fee", KeyboardType.Decimal, canWrite)
        CoreField(model.tax, { model.tax = it }, "세금", "transaction-tax", KeyboardType.Decimal, canWrite)
        if (model.selection?.currency == "USD") {
            CoreField(model.exchangeRate, { model.exchangeRate = it }, "거래 환율 (USD → KRW)", "transaction-rate", KeyboardType.Decimal, canWrite)
            Text("미국 종목 거래에는 해당 거래일의 환율이 필요합니다.", style = MaterialTheme.typography.bodySmall)
        }
        if (model.busy) {
            LinearProgressIndicator(Modifier.fillMaxWidth().testTag("transaction-pending"))
            Text("처리 중입니다. 잠시 기다려 주세요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        }
        Button({ focus.clearFocus(); model.submit() }, enabled = canWrite,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("transaction-submit")) { Text(if (model.editId == null) "거래 등록" else "거래 수정 저장") }
        if (model.editId != null) OutlinedButton({ model.cancelEdit() }, enabled = !model.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("수정 취소") }
    }
}
