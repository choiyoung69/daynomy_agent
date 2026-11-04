package org.daynomy.android

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.outlined.KeyboardArrowLeft
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Search
import androidx.compose.ui.input.key.*
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
fun NewsScreen(state: NewsUiState, controller: NewsController, today: NewsUiState, todayController: NewsController, imageBaseUrl: String) {
    var query by rememberSaveable { mutableStateOf(state.searchQuery.orEmpty()) }
    var todayArticleId by rememberSaveable { mutableStateOf<Long?>(null) }
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
            TodayNewsCarousel(today.list, imageBaseUrl, todayArticleId, { todayArticleId = it }, todayController::retryList, controller::openDetail)
            Text("전체 이슈", fontSize = 18.sp, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            OutlinedTextField(query, { query = it }, label = { Text("이슈 검색") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                singleLine = true, isError = state.searchError != null, shape = PortfolioStyle.panel,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { search() }),
                modifier = Modifier.fillMaxWidth().onPreviewKeyEvent { event ->
                    if (event.key == Key.Enter || event.key == Key.NumPadEnter) {
                        if (event.type == KeyEventType.KeyUp) search()
                        true
                    } else false
                }.testTag("news-query"))
            state.searchError?.let { DiscoveryError(it, "news-query-error") }
            if (state.searchQuery != null || query.isNotEmpty()) {
                TextButton({ query = ""; controller.clearSearch() }, Modifier.heightIn(min = 48.dp).testTag("news-search-clear")) { Text("검색 해제") }
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
private fun TodayNewsCarousel(result: LoadState<NewsPage>, imageBaseUrl: String, selectedId: Long?, select: (Long) -> Unit, retry: () -> Unit, open: (Long) -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("news-today-summary"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("오늘 뉴스", fontSize = 21.sp, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
        Text("최신 발행 소식 · 좌우로 넘겨보세요", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
        when (result) {
            LoadState.Idle, LoadState.Loading -> DiscoveryLoading("오늘 뉴스를 불러오고 있어요.")
            is LoadState.Failed -> {
                DiscoveryError("오늘 뉴스를 불러오지 못했습니다.", "news-today-error")
                OutlinedButton(retry, shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("news-today-retry")) { Text("다시 조회") }
            }
            is LoadState.Ready -> {
                val articles = result.value.items.take(9)
                if (articles.isEmpty()) Text("오늘 발행된 뉴스가 없습니다.", Modifier.testTag("news-today-empty"))
                else {
                    val pager = rememberPagerState(initialPage = articles.indexOfFirst { it.id == selectedId }.coerceAtLeast(0), pageCount = { articles.size })
                    val scope = rememberCoroutineScope()
                    LaunchedEffect(pager, articles) {
                        snapshotFlow { pager.settledPage }.collect { index -> articles.getOrNull(index)?.let { select(it.id) } }
                    }
                    HorizontalPager(state = pager, pageSpacing = 12.dp, key = { articles[it].id },
                        modifier = Modifier.fillMaxWidth().testTag("news-today-pager")) { page ->
                        val news = articles[page]
                        Box(Modifier.fillMaxWidth().heightIn(min = if (LocalDensity.current.fontScale > 1.3f) 380.dp else 280.dp)
                            .clip(PortfolioStyle.panel).background(PortfolioStyle.ink)
                            .clickable(onClickLabel = "오늘 기사 읽기", role = androidx.compose.ui.semantics.Role.Button) { select(news.id); open(news.id) }
                            .testTag("news-today-${news.id}")) {
                            StoryPhoto(news.imageUrl, imageBaseUrl, news.id, Modifier.matchParentSize())
                            Box(Modifier.matchParentSize().background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = .10f), Color.Black.copy(alpha = .45f), Color.Black.copy(alpha = .94f)))))
                            Column(Modifier.fillMaxWidth().align(Alignment.BottomStart).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text("오늘 뉴스 %02d".format(page + 1), color = Color(0xFFB8D5FF), style = MaterialTheme.typography.labelLarge)
                                Text(news.title, color = Color.White, fontSize = 22.sp, lineHeight = 31.sp, fontWeight = FontWeight.Bold)
                                Text(listOfNotNull(newsLabel(news.category), news.publishedAt?.take(10)).joinToString(" · "),
                                    color = Color.White.copy(alpha = .90f), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                        IconButton({ scope.launch { pager.scrollToPage(pager.currentPage - 1) } }, enabled = pager.currentPage > 0,
                            modifier = Modifier.size(48.dp).testTag("news-today-previous")) { Icon(Icons.Outlined.KeyboardArrowLeft, contentDescription = "이전 뉴스") }
                        Text("${pager.currentPage + 1} / ${articles.size}", Modifier.testTag("news-today-position"), color = PortfolioStyle.muted,
                            style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
                        IconButton({ scope.launch { pager.scrollToPage(pager.currentPage + 1) } }, enabled = pager.currentPage < articles.lastIndex,
                            modifier = Modifier.size(48.dp).testTag("news-today-next")) { Icon(Icons.Outlined.KeyboardArrowRight, contentDescription = "다음 뉴스") }
                    }
                }
            }
        }
    }
}

@Composable
private fun StoryPhoto(rawUrl: String?, baseUrl: String, id: Long, modifier: Modifier) {
    val url = remember(rawUrl, baseUrl) { rawUrl?.takeIf { it.isNotBlank() }?.let { baseUrl.toHttpUrlOrNull()?.resolve(it)?.toString() } }
    var state by remember(rawUrl, url) { mutableStateOf(if (rawUrl.isNullOrBlank()) "이미지 없음" else if (url == null) "이미지를 불러오지 못했습니다" else "이미지 불러오는 중") }
    Box(modifier.semantics { stateDescription = state }.testTag("news-today-image-$id")) {
        if (url != null) AsyncImage(model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize(),
            onLoading = { state = "이미지 불러오는 중" }, onSuccess = { state = "이미지 로드 완료" }, onError = { state = "이미지를 불러오지 못했습니다" })
        if (state != "이미지 로드 완료") Text(state, Modifier.align(Alignment.TopEnd).padding(16.dp), color = Color.White.copy(alpha = .85f), style = MaterialTheme.typography.labelSmall)
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
