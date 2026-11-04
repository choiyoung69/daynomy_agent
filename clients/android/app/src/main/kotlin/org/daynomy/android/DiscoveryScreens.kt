package org.daynomy.android

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Search
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.sp
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
fun NewsScreen(state: NewsUiState, controller: NewsController, today: NewsUiState, todayController: NewsController) {
    var query by rememberSaveable { mutableStateOf(state.searchQuery.orEmpty()) }
    var todayExpanded by rememberSaveable { mutableStateOf(false) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    fun search() { focus.clearFocus(); keyboard?.hide(); controller.submitSearch(query) }
    AppPage {
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
                    Text(news.title, fontSize = 24.sp, lineHeight = 34.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.semantics { heading() })
                    Text("${newsLabel(news.category)} · ${news.publishedAt}", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodyMedium)
                    news.content.forEach { Text(it, fontSize = 16.sp, lineHeight = 27.sp) }
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
            AppPageTitle("이슈")
            TodayNewsDashboard(today.list, todayExpanded, { todayExpanded = !todayExpanded }, todayController::retryList, controller::openDetail)
            Text("전체 이슈", fontSize = 18.sp, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            OutlinedTextField(query, { query = it }, label = { Text("이슈 검색") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                singleLine = true, isError = state.searchError != null, shape = PortfolioStyle.panel,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { search() }),
                modifier = Modifier.fillMaxWidth().testTag("news-query"))
            state.searchError?.let { DiscoveryError(it, "news-query-error") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button({ search() }, shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("news-search")) { Text("검색") }
                if (state.searchQuery != null || query.isNotEmpty()) {
                    TextButton({ query = ""; controller.clearSearch() }, Modifier.heightIn(min = 48.dp).testTag("news-search-clear")) { Text("검색 해제") }
                }
            }
            state.searchQuery?.let {
                Text("검색 중: $it", Modifier.testTag("news-active-query").semantics { liveRegion = LiveRegionMode.Polite })
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
                        shape = PortfolioStyle.pill,
                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = PortfolioStyle.colors.secondaryContainer, selectedLabelColor = PortfolioStyle.blue),
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
                    if (result.value.items.isEmpty()) {
                        Column(Modifier.fillMaxWidth().padding(vertical = 32.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(if (state.searchQuery == null) "발행된 뉴스가 없습니다." else "검색 결과가 없습니다.", Modifier.testTag("news-empty"), fontWeight = FontWeight.SemiBold)
                            Text("새로 발행된 소식은 이곳에서 확인할 수 있어요.", color = PortfolioStyle.muted)
                        }
                    }
                    Column {
                        result.value.items.forEach { news ->
                            Column(Modifier.fillMaxWidth().clickable(onClickLabel = "기사 읽기") { controller.openDetail(news.id) }
                                .heightIn(min = 96.dp).padding(vertical = 20.dp).testTag("news-item-${news.id}"),
                                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text(listOfNotNull(newsLabel(news.category), news.publishedAt).joinToString(" · "),
                                    color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Text(news.title, Modifier.weight(1f), fontSize = 19.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold)
                                    Icon(Icons.Outlined.KeyboardArrowRight, contentDescription = null, tint = PortfolioStyle.muted)
                                }
                            }
                            HorizontalDivider(color = PortfolioStyle.line)
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
private fun TodayNewsDashboard(result: LoadState<NewsPage>, expanded: Boolean, toggle: () -> Unit, retry: () -> Unit, open: (Long) -> Unit) {
    Card(Modifier.fillMaxWidth().testTag("news-today-summary"), shape = PortfolioStyle.panel,
        colors = CardDefaults.cardColors(containerColor = PortfolioStyle.colors.secondaryContainer)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("오늘 뉴스", fontSize = 21.sp, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            Text("서버 날짜 기준 · 최신 발행 소식 최대 9건", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
            when (result) {
                LoadState.Idle, LoadState.Loading -> DiscoveryLoading("오늘 뉴스를 불러오고 있어요.")
                is LoadState.Failed -> {
                    DiscoveryError("오늘 뉴스를 불러오지 못했습니다.", "news-today-error")
                    OutlinedButton(retry, shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("news-today-retry")) { Text("다시 조회") }
                }
                is LoadState.Ready -> {
                    if (result.value.items.isEmpty()) Text("오늘 발행된 뉴스가 없습니다.", Modifier.testTag("news-today-empty"))
                    else {
                        Text("최신 ${result.value.items.size}건", color = PortfolioStyle.blue, style = MaterialTheme.typography.labelLarge)
                        result.value.items.take(if (expanded) 9 else 3).forEachIndexed { index, news ->
                            Column(Modifier.fillMaxWidth().clickable(onClickLabel = "오늘 기사 읽기", role = androidx.compose.ui.semantics.Role.Button) { open(news.id) }
                                .heightIn(min = 64.dp).padding(vertical = 8.dp).testTag("news-today-${news.id}"),
                                verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(newsLabel(news.category), color = PortfolioStyle.muted, style = MaterialTheme.typography.labelMedium)
                                Text(news.title, fontSize = if (index == 0) 19.sp else 16.sp, lineHeight = 26.sp,
                                    fontWeight = if (index == 0) FontWeight.Bold else FontWeight.Medium)
                            }
                            if (index < (if (expanded) result.value.items.size.coerceAtMost(9) else result.value.items.size.coerceAtMost(3)) - 1) HorizontalDivider(color = PortfolioStyle.line)
                        }
                        if (result.value.items.size > 3) TextButton(toggle, Modifier.heightIn(min = 48.dp).testTag("news-today-more")) {
                            Text(if (expanded) "접기" else "오늘 뉴스 더 보기")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ExchangeScreen(state: ExchangeUiState, controller: ExchangeController) {
    var date by rememberSaveable { mutableStateOf(state.date) }
    var boundDate by rememberSaveable { mutableStateOf(state.date) }
    LaunchedEffect(state.date) {
        if (boundDate != state.date) { date = state.date; boundDate = state.date }
    }
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
