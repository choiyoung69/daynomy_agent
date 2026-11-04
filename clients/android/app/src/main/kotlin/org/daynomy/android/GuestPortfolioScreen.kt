package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import org.daynomy.market.*
import java.text.NumberFormat
import java.util.Locale

@Composable
fun GuestPortfolioScreen(model: GuestPortfolioViewModel, onAccount: () -> Unit) {
    val state by model.portfolio.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()
    MaterialTheme(colorScheme = PortfolioStyle.colors) {
        Column(Modifier.fillMaxSize().imePadding().verticalScroll(scroll).padding(20.dp)
            .testTag("guest-portfolio"), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("내 포트폴리오", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
                modifier = Modifier.semantics { heading() })
            Surface(color = PortfolioStyle.soft, shape = PortfolioStyle.panel) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("로그인 없이 포트폴리오 체험", fontWeight = FontWeight.SemiBold)
                    Text("종목·수량·원화 평균 매수가를 담아 최근 저장 종가로 평가해 보세요.")
                    Text("이 앱을 실행하는 동안만 임시 보관됩니다. 앱 프로세스가 종료되면 사라집니다.", color = PortfolioStyle.muted)
                    TextButton(onAccount, Modifier.heightIn(min = 48.dp).testTag("guest-account")) { Text("계정에 저장하려면 로그인") }
                }
            }
            Text("종목 담기", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Country.entries.forEach { country -> FilterChip(model.country == country, { model.changeCountry(country) },
                    label = { Text(if (country == Country.KR) "국내" else "미국") }, modifier = Modifier.heightIn(min = 48.dp)) }
            }
            OutlinedTextField(model.query, model::search, label = { Text("종목명 또는 코드") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().testTag("guest-query"))
            if (model.searching) LinearProgressIndicator(Modifier.fillMaxWidth())
            model.searchError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
            model.results.forEach { stock ->
                TextButton({ focus.clearFocus(); model.choose(stock) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-stock-${stock.assetId}")) {
                    Text("${stock.name} · ${stock.assetCode}")
                }
            }
            if (!model.searching && model.query.isNotBlank() && model.selected == null && model.results.isEmpty() && model.searchError == null)
                Text("검색 결과가 없습니다.", color = PortfolioStyle.muted)
            model.selected?.let { stock ->
                Text(stock.name, fontWeight = FontWeight.SemiBold)
                OutlinedTextField(model.quantity, { model.quantity = it }, label = { Text("보유 수량") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth().testTag("guest-quantity"))
                OutlinedTextField(model.average, { model.average = it }, label = { Text("원화 평균 매수가") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth().testTag("guest-average"))
                Button({ focus.clearFocus(); model.save() }, shape = PortfolioStyle.pill,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("guest-save")) {
                    Text(if (state.holdings.any { it.stock.assetId == stock.assetId }) "임시 보유 수정" else "임시 포트폴리오에 담기")
                }
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
                modifier = Modifier.testTag("guest-error").semantics { liveRegion = LiveRegionMode.Polite }) }
            state.notice?.let { Text(it, color = PortfolioStyle.muted, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
            HorizontalDivider(color = PortfolioStyle.line)
            Text("임시 보유 ${state.holdings.size}개 / 최대 50개", style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("guest-holdings-count"))
            if (state.holdings.isEmpty()) Text("아직 담은 종목이 없습니다.", color = PortfolioStyle.muted)
            state.holdings.forEach { row ->
                Surface(color = PortfolioStyle.soft, shape = PortfolioStyle.panel) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(row.stock.name, fontWeight = FontWeight.SemiBold)
                        Text("${row.quantity}주 · 원화 평균 매수가 ${guestMoney(row.average.toPlainString())}")
                        Row {
                            TextButton({ focus.clearFocus(); model.choose(row.stock); scope.launch { scroll.animateScrollTo(0) } }, Modifier.heightIn(min = 48.dp).testTag("guest-edit-${row.stock.assetId}")) { Text("수정") }
                            TextButton({ model.portfolio.remove(row.stock.assetId) }, Modifier.heightIn(min = 48.dp).testTag("guest-remove-${row.stock.assetId}")) { Text("제거") }
                        }
                    }
                }
            }
            Button({ focus.clearFocus(); model.portfolio.evaluate() }, enabled = state.holdings.isNotEmpty() && !state.evaluating,
                shape = PortfolioStyle.pill, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("guest-evaluate")) { Text(if (state.evaluating) "평가 중…" else "평가하기") }
            if (state.evaluating) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.evaluation?.let { evaluation ->
                Column(Modifier.testTag("guest-evaluation").semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("평가 결과", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
                    val status = evaluation["pricingStatus"]?.jsonPrimitive?.content
                    Text(when (status) { "PARTIAL" -> "일부 종목의 가격·환율이 없어 전체 손익을 계산할 수 없습니다."; "MIXED_DATES" -> "종목별 가격 기준일이 다릅니다."; else -> "최근 저장 종가 기준 평가입니다." })
                    Text("매입금액 ${guestMoney(evaluation["totalPurchaseAmount"]?.jsonPrimitive?.contentOrNull)}")
                    Text("${if (status == "PARTIAL") "평가 가능 종목 금액" else "평가금액"} ${guestMoney(evaluation["totalEvaluationAmount"]?.jsonPrimitive?.contentOrNull)}")
                    Text("평가손익 ${guestMoney(evaluation["totalProfitLoss"]?.jsonPrimitive?.contentOrNull)}", fontWeight = FontWeight.SemiBold)
                    evaluation["holdings"]?.jsonArray?.forEach { item ->
                        val row = item.jsonObject
                        Text("${row["name"]?.jsonPrimitive?.content.orEmpty()} · 기준일 ${row["baseDate"]?.jsonPrimitive?.contentOrNull ?: "가격 없음"}", color = PortfolioStyle.muted)
                    }
                }
            }
        }
    }
}

private fun guestMoney(raw: String?): String = raw?.toBigDecimalOrNull()?.let {
    NumberFormat.getNumberInstance(Locale.KOREA).apply { maximumFractionDigits = 2 }.format(it) + "원"
} ?: "평가 불가"
