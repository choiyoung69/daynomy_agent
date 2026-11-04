package org.daynomy.android

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import org.daynomy.market.*

@Composable
fun NewsScreen(state: NewsUiState, controller: NewsController) {
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("DAYNOMY", color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.labelLarge)
        if (state.selectedId != null) {
            TextButton(controller::closeDetail, Modifier.heightIn(min = 48.dp).testTag("news-back")) { Text("뉴스 목록으로") }
            when (val result = state.detail) {
                LoadState.Idle -> Text("뉴스 상세를 선택했어요.")
                LoadState.Loading -> DiscoveryLoading("뉴스를 불러오고 있어요.")
                is LoadState.Failed -> {
                    DiscoveryError(result.message, "news-detail-error")
                    OutlinedButton(controller::retryDetail, Modifier.heightIn(min = 48.dp).testTag("news-detail-retry")) { Text("상세 다시 조회") }
                }
                is LoadState.Ready -> Column(Modifier.testTag("news-detail"), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    val news = result.value
                    Text(news.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold,
                        modifier = Modifier.semantics { heading() })
                    Text("${newsLabel(news.category)} · ${news.publishedAt}", style = MaterialTheme.typography.bodyMedium)
                    news.content.forEach { Text(it, style = MaterialTheme.typography.bodyLarge) }
                    Text("뉴스 키워드", style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.semantics { heading() })
                    when (val keywords = state.keywords) {
                        LoadState.Idle -> Text("키워드 조회를 준비하고 있어요.")
                        LoadState.Loading -> DiscoveryLoading("키워드를 불러오고 있어요.")
                        is LoadState.Failed -> {
                            DiscoveryError(keywords.message, "news-keywords-error")
                            OutlinedButton(controller::retryKeywords,
                                Modifier.heightIn(min = 48.dp).testTag("news-keywords-retry")) { Text("키워드 다시 조회") }
                        }
                        is LoadState.Ready -> Column(Modifier.testTag("news-keywords"),
                            verticalArrangement = Arrangement.spacedBy(16.dp)) {
                            if (keywords.value.isEmpty()) Text("이 뉴스에 등록된 키워드가 없습니다.", Modifier.testTag("news-keywords-empty"))
                            keywords.value.forEach { keyword ->
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("${keyword.keyword} · ${keywordCategoryLabel(keyword.category)}", fontWeight = FontWeight.SemiBold)
                                    Text("뜻: ${keyword.definition}")
                                    Text("기사 속 의미: ${keyword.context}")
                                    Text("확인할 점: ${keyword.watchPoint}")
                                }
                            }
                        }
                    }
                    news.imageSource?.let { source ->
                        Text("이미지 출처: ${source.name} · ${source.author} · ${source.license}")
                        Text(source.url, style = MaterialTheme.typography.bodyMedium)
                        Text(source.licenseUrl, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (news.sources.isNotEmpty()) Text("출처", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
                    news.sources.forEach { source ->
                        Text(source.name, fontWeight = FontWeight.SemiBold)
                        Text(source.url, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            NewsMarketAnalysisSection(state.analysis, controller::retryAnalysis)
        } else {
            Text("경제 소식", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(!state.todayOnly, { controller.selectToday(false) }, label = { Text("전체 뉴스") },
                    modifier = Modifier.heightIn(min = 48.dp).testTag("news-mode-all"))
                FilterChip(state.todayOnly, { controller.selectToday(true) }, label = { Text("오늘 뉴스") },
                    modifier = Modifier.heightIn(min = 48.dp).testTag("news-mode-today"))
            }
            Text(if (state.todayOnly) "서버 날짜 기준으로 오늘 발행된 최신 뉴스 최대 9개를 보여줍니다." else "발행된 뉴스를 분야별로 살펴보세요.",
                style = MaterialTheme.typography.bodyLarge)
            if (!state.todayOnly) Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(null, NewsCategory.REAL_ESTATE, NewsCategory.STOCK, NewsCategory.ETF).forEach { category ->
                    FilterChip(state.category == category, { controller.selectCategory(category) }, label = { Text(newsLabel(category)) },
                        modifier = Modifier.heightIn(min = 48.dp).testTag("category-${category?.name ?: "ALL"}"))
                }
            }
            when (val result = state.list) {
                LoadState.Idle -> Text("뉴스를 확인해 주세요.")
                LoadState.Loading -> DiscoveryLoading("뉴스 목록을 불러오고 있어요.")
                is LoadState.Failed -> {
                    DiscoveryError(result.message, "news-error")
                    OutlinedButton(controller::retryList, Modifier.heightIn(min = 48.dp).testTag("news-retry")) { Text("목록 다시 조회") }
                }
                is LoadState.Ready -> {
                    if (result.value.items.isEmpty()) Text(if (state.todayOnly) "오늘 발행된 뉴스가 없습니다." else "발행된 뉴스가 없습니다.", Modifier.testTag("news-empty"))
                    result.value.items.forEach { news ->
                        OutlinedCard(onClick = { controller.openDetail(news.id) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("news-item-${news.id}")) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(news.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                Text(newsLabel(news.category), style = MaterialTheme.typography.bodyMedium)
                                news.publishedAt?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                            }
                        }
                    }
                    if (!state.todayOnly) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({ controller.selectPage(state.page - 1) }, enabled = state.page > 1,
                            modifier = Modifier.heightIn(min = 48.dp).testTag("news-previous")) { Text("이전") }
                        Text("${state.page} 페이지", Modifier.padding(vertical = 14.dp))
                        OutlinedButton({ controller.selectPage(state.page + 1) }, enabled = result.value.hasNext,
                            modifier = Modifier.heightIn(min = 48.dp).testTag("news-next")) { Text("다음") }
                    }
                }
            }
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
fun ExchangeScreen(state: ExchangeUiState, controller: ExchangeController) {
    var date by rememberSaveable { mutableStateOf(state.date) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    fun submit() {
        focus.clearFocus(force = true)
        keyboard?.hide()
        if (state.date == date) controller.retry() else controller.updateDate(date)
    }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("달러 환율", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
        OutlinedTextField(date, { date = it }, label = { Text("조회 날짜") }, placeholder = { Text("YYYY-MM-DD") },
            singleLine = true, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { submit() }), modifier = Modifier.fillMaxWidth().testTag("exchange-date"))
        Button({ submit() }, enabled = date.isNotBlank() && state.quote != LoadState.Loading,
            modifier = Modifier.heightIn(min = 48.dp).testTag("exchange-load")) { Text("환율 조회") }
        if (state.date.isNotEmpty()) Text("요청 날짜 ${state.date}")
        when (val quote = state.quote) {
            LoadState.Idle -> Text("날짜를 입력하고 환율을 조회해 주세요.")
            LoadState.Loading -> DiscoveryLoading("환율을 불러오고 있어요.")
            is LoadState.Failed -> {
                DiscoveryError(quote.message, "exchange-error")
                OutlinedButton(controller::retry, Modifier.heightIn(min = 48.dp).testTag("exchange-retry")) { Text("다시 조회") }
            }
            is LoadState.Ready -> Text("1 USD = ${quote.value.rate.toPlainString()} KRW\n실제 기준일 ${quote.value.baseDate}",
                style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("exchange-value"))
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun DiscoveryLoading(message: String) {
    LinearProgressIndicator(Modifier.fillMaxWidth())
    Text(message, Modifier.semantics { liveRegion = LiveRegionMode.Polite })
}
@Composable
private fun DiscoveryError(message: String, tag: String) {
    Text(message, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag(tag).semantics { liveRegion = LiveRegionMode.Polite })
}
private fun newsLabel(category: NewsCategory?): String = when (category) {
    null -> "전체"; NewsCategory.REAL_ESTATE -> "부동산"; NewsCategory.STOCK -> "주식"; NewsCategory.ETF -> "ETF"
    NewsCategory.DEPOSIT_SAVINGS -> "예금·적금"; NewsCategory.ECONOMY -> "경제지표"; NewsCategory.BOND -> "채권"
    NewsCategory.PENSION -> "연금"; NewsCategory.FOREIGN_EXCHANGE -> "외화·환율"; NewsCategory.VIRTUAL_ASSET -> "가상자산"; NewsCategory.GOLD -> "금"
}

private fun keywordCategoryLabel(category: NewsKeywordCategory): String = when (category) {
    NewsKeywordCategory.PERSON -> "인물"
    NewsKeywordCategory.POLICY -> "정책"
    NewsKeywordCategory.EVENT -> "사건"
    NewsKeywordCategory.TERM -> "용어"
    NewsKeywordCategory.TREND -> "흐름"
}

@Composable
private fun NewsMarketAnalysisSection(analysis: LoadState<NewsMarketAnalysis?>, retry: () -> Unit) {
    Text("시장 분석", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
    when (analysis) {
        LoadState.Idle -> Text("시장 분석 조회를 준비하고 있어요.")
        LoadState.Loading -> DiscoveryLoading("시장 분석을 불러오고 있어요.")
        is LoadState.Failed -> {
            DiscoveryError(analysis.message, "news-analysis-error")
            OutlinedButton(retry, Modifier.heightIn(min = 48.dp).testTag("news-analysis-retry")) { Text("시장 분석 다시 조회") }
        }
        is LoadState.Ready -> {
            val value = analysis.value
            if (value == null) Text("이 뉴스에 제공되는 시장 분석이 없습니다.", Modifier.testTag("news-analysis-empty"))
            else Column(Modifier.testTag("news-analysis"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("위험과 불확실성: ${value.risk}")
                Text("확인할 점: ${value.watchPoint}")
            }
        }
    }
}
