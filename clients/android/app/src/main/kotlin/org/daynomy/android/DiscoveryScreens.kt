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
    var query by rememberSaveable { mutableStateOf(state.searchQuery.orEmpty()) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    fun search() {
        focus.clearFocus(force = true)
        keyboard?.hide()
        controller.submitSearch(query)
    }
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
        } else {
            Text("경제 소식", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            Text("발행된 뉴스를 분야별로 살펴보세요.", style = MaterialTheme.typography.bodyLarge)
            OutlinedTextField(query, { query = it }, label = { Text("뉴스 검색어") },
                singleLine = true, isError = state.searchError != null,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { search() }),
                modifier = Modifier.fillMaxWidth().testTag("news-query"))
            state.searchError?.let { DiscoveryError(it, "news-query-error") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button({ search() }, Modifier.heightIn(min = 48.dp).testTag("news-search")) { Text("검색") }
                if (state.searchQuery != null || query.isNotEmpty()) {
                    TextButton({ query = ""; controller.clearSearch() }, Modifier.heightIn(min = 48.dp).testTag("news-search-clear")) { Text("검색 해제") }
                }
            }
            state.searchQuery?.let {
                Text("검색 중: $it", Modifier.testTag("news-active-query").semantics { liveRegion = LiveRegionMode.Polite })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NewsSearchSort.entries.forEach { sort ->
                        FilterChip(state.sort == sort, { controller.selectSort(sort) },
                            label = { Text(if (sort == NewsSearchSort.LATEST) "최신순" else "관련도순") },
                            modifier = Modifier.heightIn(min = 48.dp).testTag("news-sort-${sort.name}"))
                    }
                }
            }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
                    if (result.value.items.isEmpty()) Text(if (state.searchQuery == null) "발행된 뉴스가 없습니다." else "검색 결과가 없습니다.", Modifier.testTag("news-empty"))
                    result.value.items.forEach { news ->
                        OutlinedCard(onClick = { controller.openDetail(news.id) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("news-item-${news.id}")) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(news.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                Text(newsLabel(news.category), style = MaterialTheme.typography.bodyMedium)
                                news.publishedAt?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
