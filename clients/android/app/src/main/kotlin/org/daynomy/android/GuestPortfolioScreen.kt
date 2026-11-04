package org.daynomy.android

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.serialization.json.*
import org.daynomy.market.*
import java.math.BigDecimal
import java.text.NumberFormat
import java.util.Locale

@Composable
fun GuestPortfolioScreen(model: GuestPortfolioViewModel, onAccount: () -> Unit) {
    val state by model.portfolio.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    var editorOpen by rememberSaveable { mutableStateOf(false) }
    var amountsHidden by rememberSaveable { mutableStateOf(false) }
    val dashboardScroll = rememberScrollState()
    val editorScroll = rememberScrollState()
    fun closeEditor() { focus.clearFocus(); keyboard?.hide(); editorOpen = false }
    fun openEditor() { focus.clearFocus(); keyboard?.hide(); editorOpen = true }
    LaunchedEffect(editorOpen) { if (editorOpen) editorScroll.scrollTo(0) }
    BackHandler(editorOpen) { closeEditor() }

    Surface(Modifier.fillMaxSize(), color = PortfolioStyle.colors.surface) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
            Column(Modifier.widthIn(max = 760.dp).fillMaxSize().imePadding()
                .verticalScroll(if (editorOpen) editorScroll else dashboardScroll).padding(20.dp)
                .testTag("guest-portfolio"), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                if (editorOpen) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("종목 담기", Modifier.weight(1f).semantics { heading() }, style = MaterialTheme.typography.headlineSmall)
                        TextButton({ closeEditor() }, Modifier.heightIn(min = 48.dp).testTag("guest-editor-close")) { Text("닫기") }
                    }
                    Text("종목·수량·원화 평균 매수가를 입력하세요.", color = PortfolioStyle.muted)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Country.entries.forEach { country -> FilterChip(model.country == country, { model.changeCountry(country) },
                            label = { Text(if (country == Country.KR) "국내" else "미국") }, modifier = Modifier.heightIn(min = 48.dp)) }
                    }
                    OutlinedTextField(model.query, model::search, label = { Text("종목명 또는 코드") }, singleLine = true,
                        shape = PortfolioStyle.panel, modifier = Modifier.fillMaxWidth().testTag("guest-query"))
                    if (model.searching) LinearProgressIndicator(Modifier.fillMaxWidth())
                    model.searchError?.let { GuestError(it) }
                    model.results.forEach { stock ->
                        TextButton({ focus.clearFocus(); keyboard?.hide(); model.choose(stock) },
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-stock-${stock.assetId}")) {
                            Text("${stock.name} · ${stock.assetCode}")
                        }
                    }
                    if (!model.searching && model.query.isNotBlank() && model.selected == null && model.results.isEmpty() && model.searchError == null)
                        Text("검색 결과가 없습니다.", color = PortfolioStyle.muted)
                    model.selected?.let { stock ->
                        Text(stock.name, style = MaterialTheme.typography.titleMedium)
                        OutlinedTextField(model.quantity, { model.quantity = it }, label = { Text("보유 수량") }, singleLine = true,
                            shape = PortfolioStyle.panel, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            modifier = Modifier.fillMaxWidth().testTag("guest-quantity"))
                        OutlinedTextField(model.average, { model.average = it }, label = { Text("원화 평균 매수가") }, singleLine = true,
                            shape = PortfolioStyle.panel, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.fillMaxWidth().testTag("guest-average"))
                        state.error?.let { GuestError(it) }
                        Button({
                            model.save()
                            if (model.portfolio.state.value.error == null) closeEditor()
                        }, shape = PortfolioStyle.pill,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-save")) {
                            Text(if (state.holdings.any { it.stock.assetId == stock.assetId }) "임시 보유 수정" else "임시 포트폴리오에 담기")
                        }
                    }
                } else {
                    val add: @Composable () -> Unit = {
                        Button({ openEditor() }, shape = PortfolioStyle.pill,
                            modifier = Modifier.heightIn(min = 48.dp).testTag("guest-editor-open")) { Text("종목 담기") }
                    }
                    if (LocalDensity.current.fontScale > 1.3f) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("내 포트폴리오", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.semantics { heading() })
                            add()
                        }
                    } else Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("내 포트폴리오", Modifier.weight(1f).semantics { heading() }, style = MaterialTheme.typography.headlineSmall)
                        add()
                    }
                    Text("로그인 없이 시작하세요. 임시 보유는 앱을 실행하는 동안만 유지됩니다.", color = PortfolioStyle.muted)
                    Column(Modifier.fillMaxWidth().testTag("guest-summary"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(if (state.evaluation?.get("pricingStatus")?.jsonPrimitive?.content == "PARTIAL") "평가 가능 종목 금액" else "총 평가금액",
                                Modifier.weight(1f), color = PortfolioStyle.muted)
                            TextButton({ amountsHidden = !amountsHidden }, Modifier.heightIn(min = 48.dp).testTag("guest-amount-toggle")) {
                                Text(if (amountsHidden) "금액 보기" else "금액 숨기기")
                            }
                        }
                        val amount = when {
                            amountsHidden -> "••••••"
                            state.holdings.isEmpty() -> "0원"
                            state.evaluation != null -> guestMoney(state.evaluation?.get("totalEvaluationAmount")?.jsonPrimitive?.contentOrNull)
                            else -> "평가 필요"
                        }
                        Text(amount, fontSize = 30.sp, fontWeight = FontWeight.Bold, lineHeight = 40.sp,
                            modifier = Modifier.testTag("guest-summary-amount"))
                        val purchase = state.holdings.fold(BigDecimal.ZERO) { total, row -> total + row.average.multiply(row.quantity.toBigDecimal()) }
                        Text("매입금액 ${if (amountsHidden) "••••••" else guestMoney(purchase.toPlainString())}", color = PortfolioStyle.muted)
                        if (state.holdings.isNotEmpty() && state.evaluation == null)
                            Text("평가하기를 눌러 최근 저장 종가를 확인하세요.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                    }
                    HorizontalDivider(color = PortfolioStyle.line)
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("보유 자산", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
                        Text("임시 보유 ${state.holdings.size}개 / 최대 50개", color = PortfolioStyle.muted,
                            style = MaterialTheme.typography.bodyMedium, modifier = Modifier.testTag("guest-holdings-count"))
                    }
                    state.notice?.let { Text(it, color = PortfolioStyle.muted, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                    state.error?.let { GuestError(it) }
                    if (state.holdings.isEmpty()) {
                        Column(Modifier.fillMaxWidth().padding(vertical = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("아직 담은 종목이 없습니다.", style = MaterialTheme.typography.titleMedium)
                            Text("종목을 담으면 보유 자산을 한눈에 볼 수 있어요.", color = PortfolioStyle.muted)
                        }
                    }
                    state.holdings.forEach { row ->
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(row.stock.name, style = MaterialTheme.typography.titleMedium)
                            Text("${row.stock.assetCode} · ${row.quantity}주", color = PortfolioStyle.muted)
                            Text("원화 평균 매수가 ${if (amountsHidden) "••••••" else guestMoney(row.average.toPlainString())}")
                            Row {
                                TextButton({ model.choose(row.stock); openEditor() }, Modifier.heightIn(min = 48.dp).testTag("guest-edit-${row.stock.assetId}")) { Text("수정") }
                                TextButton({ model.portfolio.remove(row.stock.assetId) }, Modifier.heightIn(min = 48.dp).testTag("guest-remove-${row.stock.assetId}")) { Text("제거") }
                            }
                            HorizontalDivider(color = PortfolioStyle.line)
                        }
                    }
                    if (state.holdings.isNotEmpty()) {
                        Button({ focus.clearFocus(); model.portfolio.evaluate() }, enabled = !state.evaluating, shape = PortfolioStyle.pill,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-evaluate")) { Text(if (state.evaluating) "평가 중…" else "평가하기") }
                    }
                    if (state.evaluating) LinearProgressIndicator(Modifier.fillMaxWidth())
                    state.evaluation?.let { evaluation ->
                        Column(Modifier.testTag("guest-evaluation").semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("평가 결과", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
                            val status = evaluation["pricingStatus"]?.jsonPrimitive?.content
                            Text(when (status) { "PARTIAL" -> "일부 종목의 가격·환율이 없어 전체 손익을 계산할 수 없습니다."; "MIXED_DATES" -> "종목별 가격 기준일이 다릅니다."; else -> "최근 저장 종가 기준 평가입니다." }, color = PortfolioStyle.muted)
                            Text("${if (status == "PARTIAL") "평가 가능 종목 금액" else "평가금액"} ${if (amountsHidden) "••••••" else guestMoney(evaluation["totalEvaluationAmount"]?.jsonPrimitive?.contentOrNull)}")
                            Text("평가손익 ${if (amountsHidden) "••••••" else guestMoney(evaluation["totalProfitLoss"]?.jsonPrimitive?.contentOrNull)}", fontWeight = FontWeight.SemiBold)
                            evaluation["holdings"]?.jsonArray?.forEach { item ->
                                val row = item.jsonObject
                                Text("${row["name"]?.jsonPrimitive?.content.orEmpty()} · 기준일 ${row["baseDate"]?.jsonPrimitive?.contentOrNull ?: "가격 없음"}", color = PortfolioStyle.muted)
                            }
                        }
                    }
                    TextButton(onAccount, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-account")) { Text("계정에 저장하려면 로그인") }
                    Text("앱 프로세스가 종료되면 임시 보유가 사라집니다. 회원 계정으로 자동 이동하지 않습니다.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun GuestError(message: String) {
    Text(message, color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("guest-error").semantics { liveRegion = LiveRegionMode.Polite })
}

private fun guestMoney(raw: String?): String = raw?.toBigDecimalOrNull()?.let {
    NumberFormat.getNumberInstance(Locale.KOREA).apply { maximumFractionDigits = 2 }.format(it) + "원"
} ?: "평가 불가"
