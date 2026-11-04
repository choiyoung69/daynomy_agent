package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import org.daynomy.market.Country

@Composable
fun AccountScreen(model: CoreViewModel, onFeedback: () -> Unit = {}, onLogin: () -> Unit) {
    val focus = LocalFocusManager.current
    val profile = model.profile
    var nickname by remember(profile?.id, profile?.nickname) { mutableStateOf(profile?.nickname.orEmpty()) }
    var withdraw by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.loadAccount() }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        CoreHeading("내 계정")
        OutlinedButton(onFeedback, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-feedback")) { Text("의견 보내기") }
        CoreMessage(model.message)
        if (model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (profile == null) {
            Text("로그인하면 보유자산과 거래 내역을 계정에 저장할 수 있어요.")
            Button(onLogin, enabled = !model.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-login")) { Text("Google로 로그인") }
        } else {
            Text("${profile.nickname} · ${profile.email}", Modifier.testTag("account-profile"), style = MaterialTheme.typography.titleMedium)
            CoreField(nickname, { nickname = it }, "닉네임", "account-nickname", enabled = !model.busy)
            Text("앞뒤 공백을 제외하고 20자 이내로 입력하세요.", style = MaterialTheme.typography.bodySmall)
            Button({ focus.clearFocus(); model.rename(nickname) }, enabled = !model.busy && nickname.isNotBlank() && nickname.trim().length <= 20,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-save")) { Text("닉네임 저장") }
            OutlinedButton({ focus.clearFocus(); model.logout() }, enabled = !model.busy,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-logout")) { Text("로그아웃") }
            TextButton({ withdraw = true }, enabled = !model.busy, modifier = Modifier.heightIn(min = 48.dp).testTag("account-delete")) { Text("회원 탈퇴") }
        }
    }
    if (withdraw) AlertDialog(onDismissRequest = { withdraw = false }, title = { Text("회원 탈퇴") },
        text = { Text("탈퇴하면 이 계정으로 더 이상 로그인할 수 없습니다. 계속할까요?") },
        confirmButton = { TextButton({ withdraw = false; focus.clearFocus(); model.logout(true) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("탈퇴하기") } },
        dismissButton = { TextButton({ withdraw = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("취소") } })
}

@Composable
fun PortfolioScreen(model: CoreViewModel) {
    val focus = LocalFocusManager.current
    var removal by remember { mutableStateOf<Pair<String, Long>?>(null) }
    var adjustment by remember { mutableStateOf<JsonObject?>(null) }
    var adjustQuantity by remember { mutableStateOf("") }
    var adjustAverage by remember { mutableStateOf("") }
    val canWrite = !model.busy && !model.unknown
    LaunchedEffect(Unit) { model.refreshPortfolio() }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        CoreHeading("내 포트폴리오")
        CoreMessage(model.message)
        if (model.unknown) {
            Text("처리 결과 확인 필요", Modifier.testTag("transaction-unknown").semantics { liveRegion = LiveRegionMode.Assertive },
                style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
            Text("같은 거래를 다시 보내지 마세요. 내역을 새로 조회해 거래가 반영됐는지 확인하세요.")
        }
        OutlinedButton({ focus.clearFocus(); model.refreshPortfolio() }, enabled = !model.busy && !model.loading,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("portfolio-refresh")) { Text(if (model.loading) "내역 조회 중…" else "보유자산·거래 내역 새로 조회") }
        if (model.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        CoreHeading(if (model.editId == null) "거래 등록" else "거래 수정")
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
        HorizontalDivider()
        CoreHeading("보유자산")
        if (model.portfolioLoaded && model.holdings.isEmpty()) Text("보유자산이 없습니다. 거래를 등록하거나 내역을 새로 조회하세요.")
        model.holdings.forEach { element ->
            val row = element as? JsonObject ?: return@forEach
            val id = row["assetId"]?.jsonPrimitive?.longOrNull ?: return@forEach
            Text(row.text("name").ifBlank { row.text("assetCode") }, style = MaterialTheme.typography.titleMedium)
            Text("${row.text("quantity")}주 · 평균 매수가 ${row.text("averagePurchasePrice")}원")
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton({ adjustment = row; adjustQuantity = row.text("quantity"); adjustAverage = row.text("averagePurchasePrice") }, enabled = canWrite,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("holding-edit-$id")) { Text("수량·평균가 조정") }
                TextButton({ removal = "holding" to id }, enabled = canWrite, modifier = Modifier.heightIn(min = 48.dp).testTag("holding-delete-$id")) { Text("제거") }
            }
        }
        HorizontalDivider()
        CoreHeading("거래 내역·수익률")
        CoreField(model.from, { model.from = it }, "조회 시작일 (YYYY-MM-DD)", "portfolio-from", enabled = !model.busy)
        CoreField(model.to, { model.to = it }, "조회 종료일 (YYYY-MM-DD)", "portfolio-to", enabled = !model.busy)
        OutlinedButton({ focus.clearFocus(); model.loadPerformance() }, enabled = !model.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("portfolio-performance")) { Text("기간 수익률 조회") }
        model.performance?.let { result ->
            Text(if (result.text("status") == "INSUFFICIENT_DATA") "수익률을 계산할 자료가 충분하지 않습니다." else "기간별 수익률")
            (result["points"] as? JsonArray).orEmpty().forEach { point -> (point as? JsonObject)?.let { PointSummary(it) } }
            (result["currentPoint"] as? JsonObject)?.let { PointSummary(it) }
        }
        if (model.portfolioLoaded && model.history.isEmpty()) Text("조회 기간에 거래·조정 내역이 없습니다.")
        model.history.forEach { element ->
            val row = element as? JsonObject ?: return@forEach
            val id = row["historyId"]?.jsonPrimitive?.longOrNull ?: return@forEach
            val kind = row.text("changeType")
            val title = when (kind) { "BUY" -> "매수"; "SELL" -> "매도"; "ADJUSTED" -> "보유 조정"; "REMOVED" -> "보유 제거"; else -> "보유 등록" }
            Text("${row.text("effectiveDate")} · $title · ${row.text("name")}", style = MaterialTheme.typography.titleSmall)
            if (kind == "BUY" || kind == "SELL") {
                Text("${row.text("transactionQuantity")}주 · 단가 ${row.text("unitPrice")} ${row.text("currency")}")
                Text("수수료 ${row.text("fee")} · 세금 ${row.text("tax")}", style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton({ focus.clearFocus(); model.edit(row) }, enabled = canWrite, modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-edit-$id")) { Text("거래 수정") }
                    TextButton({ removal = "transaction" to id }, enabled = canWrite, modifier = Modifier.heightIn(min = 48.dp).testTag("transaction-delete-$id")) { Text("거래 삭제") }
                }
            } else Text("${row.text("quantity")}주 · 평균 매수가 ${row.text("averagePurchasePrice")}원")
        }
        HorizontalDivider()
        CoreHeading("현재 평가")
        Text("저장된 보유자산의 최근 종가로 계산합니다. 평가 조회는 새 거래를 저장하지 않습니다.")
        OutlinedButton({ focus.clearFocus(); model.evaluate() }, enabled = !model.busy && model.holdings.isNotEmpty(), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("portfolio-evaluate")) { Text("최근 종가로 평가 조회") }
        model.evaluation?.let { result ->
            Text(when (result.text("pricingStatus")) { "PARTIAL" -> "일부 종목의 가격을 확인하지 못했습니다."; "MIXED_DATES" -> "종목별 가격 기준일이 다릅니다."; else -> "최근 종가 기준 평가" })
            PointSummary(result)
        }
    }
    removal?.let { (kind, id) ->
        AlertDialog(onDismissRequest = { removal = null }, title = { Text(if (kind == "transaction") "거래 삭제" else "보유자산 제거") },
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

@Composable private fun CoreHeading(title: String) { Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineSmall) }
@Composable private fun CoreMessage(message: String?) { if (message != null) Text(message, Modifier.testTag("core-message").semantics { liveRegion = LiveRegionMode.Polite }) }
@Composable private fun CoreField(value: String, change: (String) -> Unit, label: String, tag: String,
    keyboard: KeyboardType = KeyboardType.Text, enabled: Boolean = true) {
    val focus = LocalFocusManager.current
    OutlinedTextField(value, change, label = { Text(label) }, enabled = enabled, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard, imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { focus.clearFocus() }), modifier = Modifier.fillMaxWidth().testTag(tag))
}
@Composable private fun PointSummary(row: JsonObject) {
    fun amount(key: String) = row[key]?.takeUnless { it == JsonNull }?.jsonPrimitive?.content ?: "확인 불가"
    if (row.text("baseDate").isNotBlank()) Text("기준일 ${row.text("baseDate")}", style = MaterialTheme.typography.bodySmall)
    Text("매입 ${amount("totalPurchaseAmount")}원 · 평가 ${amount("totalEvaluationAmount")}원")
    Text("손익 ${amount("totalProfitLoss")}원 · 수익률 ${amount("totalReturnRate")}%")
}
