package org.daynomy.android

import android.os.Bundle
import android.content.Intent
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.List
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Search
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import org.daynomy.market.*

class MainActivity : ComponentActivity() {
    private var authCallback by mutableStateOf<String?>(null)
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        authCallback = intent.dataString
        setIntent(Intent(intent).setData(null))
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        authCallback = intent.dataString
        intent.data = null
        // The emulator alias is debug-only; release never accepts Intent-controlled endpoints.
        val baseUrl = if (BuildConfig.DEBUG) intent.getStringExtra("base_url") ?: "http://10.0.2.2:18109/"
                      else "https://api.example.invalid/"
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF334155), secondary = Color(0xFF047857),
                background = Color(0xFFF8FAFC), surface = Color.White, onSurface = Color(0xFF0F172A))) {
                val model: MarketViewModel = viewModel(factory = viewModelFactory {
                    initializer { MarketViewModel(createSavedStateHandle(), baseUrl) }
                })
                val discovery: DiscoveryViewModel = viewModel(factory = viewModelFactory {
                    initializer { DiscoveryViewModel(baseUrl) }
                })
                val core: CoreViewModel = viewModel(factory = viewModelFactory { initializer { CoreViewModel(baseUrl) } })
                val guest: GuestPortfolioViewModel = viewModel(factory = viewModelFactory { initializer { GuestPortfolioViewModel(baseUrl) } })
                val feedback: FeedbackViewModel = viewModel(factory = viewModelFactory { initializer { FeedbackViewModel(baseUrl) } })
                var feedbackOpen by rememberSaveable { mutableStateOf(false) }
                var tab by rememberSaveable { mutableStateOf("portfolio") }
                val screenState = rememberSaveableStateHolder()
                var exchangeReturn by rememberSaveable { mutableStateOf("portfolio") }
                val focus = LocalFocusManager.current
                val keyboard = LocalSoftwareKeyboardController.current
                LaunchedEffect(authCallback) {
                    authCallback?.let { callback -> authCallback = null; tab = "account"; core.completeLogin(callback) }
                }
                val owner = LocalLifecycleOwner.current
                DisposableEffect(owner, model, discovery, tab) {
                    fun activate(started: Boolean) {
                        model.controller.setActive(started && tab == "market")
                        discovery.news.setActive(started && tab == "news")
                        discovery.todayNews.setActive(started && tab == "news")
                        discovery.exchange.setActive(started && tab == "exchange")
                    }
                    val observer = LifecycleEventObserver { _, event ->
                        if (event == Lifecycle.Event.ON_START) activate(true)
                        if (event == Lifecycle.Event.ON_STOP) activate(false)
                    }
                    owner.lifecycle.addObserver(observer)
                    activate(owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED))
                    onDispose { owner.lifecycle.removeObserver(observer); activate(false) }
                }
                if (feedbackOpen) FeedbackDialog(feedback.controller) { feedbackOpen = false }
                val state by model.controller.state.collectAsStateWithLifecycle()
                val news by discovery.news.state.collectAsStateWithLifecycle()
                val todayNews by discovery.todayNews.state.collectAsStateWithLifecycle()
                val exchange by discovery.exchange.state.collectAsStateWithLifecycle()
                BackHandler(tab == "news" && news.selectedId != null) { discovery.news.closeDetail() }
                BackHandler(tab == "market") {
                    if (state.selected != null) model.controller.clearSelection()
                    else { focus.clearFocus(); keyboard?.hide(); tab = "portfolio" }
                }
                BackHandler(tab == "exchange") { tab = exchangeReturn }
                fun openExchange(date: String) {
                    exchangeReturn = tab
                    discovery.exchange.updateDate(date)
                    focus.clearFocus(); keyboard?.hide(); tab = "exchange"
                }
                MaterialTheme(colorScheme = PortfolioStyle.colors, typography = PortfolioStyle.typography) {
                    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding()) {
                        Box(Modifier.weight(1f)) {
                            screenState.SaveableStateProvider(tab) {
                            when (tab) {
                                "news" -> NewsScreen(news, discovery.news, todayNews, discovery.todayNews, baseUrl)
                                "exchange" -> Column {
                                    TextButton({ tab = exchangeReturn }, Modifier.heightIn(min = 48.dp).testTag("exchange-back")) { Text("이전 화면으로") }
                                    ExchangeScreen(exchange, discovery.exchange)
                                }
                                "account" -> AccountScreen(core, onFeedback = { feedbackOpen = true }) {
                                    try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(core.loginUrl()))) }
                                    catch (_: Exception) { core.showMessage("로그인 브라우저를 열지 못했습니다. 다시 시도해 주세요.") }
                                }
                                "portfolio" -> if (core.portfolioRequiresLogin && core.profile == null) {
                                    GuestPortfolioScreen(guest, onAccount = { tab = "account" })
                                } else PortfolioScreen(core, onAccount = { tab = "account" },
                                    onStockSearch = { tab = "market" }, onExchange = { openExchange(it) })
                                else -> MarketScreen(state, model.controller, onBack = { tab = "portfolio" },
                                    onExchange = { openExchange((state.price as? LoadState.Ready)?.value?.baseDate ?: java.time.LocalDate.now().toString()) })
                            }
                        }
                        }
                        NavigationBar(containerColor = Color.White, tonalElevation = 0.dp,
                            modifier = Modifier.heightIn(min = if (LocalDensity.current.fontScale > 1.3f) 104.dp else 72.dp).testTag("bottom-navigation")) {
                            listOf("portfolio" to "포트폴리오", "news" to "이슈", "account" to "내 계정").forEach { (key, title) ->
                                val active = tab == key || ((tab == "market" || tab == "exchange") && key == "portfolio")
                                NavigationBarItem(selected = active,
                                    onClick = { focus.clearFocus(); keyboard?.hide(); tab = key },
                                    icon = { Icon(when(key) { "portfolio" -> Icons.Outlined.Home; "news" -> Icons.Outlined.List; else -> Icons.Outlined.Person }, contentDescription = null) },
                                    label = { Text(title, modifier = Modifier.widthIn(max = 96.dp), maxLines = 2, textAlign = TextAlign.Center,
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = if (active) FontWeight.Bold else FontWeight.Medium) },
                                    colors = NavigationBarItemDefaults.colors(indicatorColor = Color.Transparent,
                                        selectedIconColor = PortfolioStyle.blue, selectedTextColor = PortfolioStyle.blue,
                                        unselectedIconColor = PortfolioStyle.muted, unselectedTextColor = PortfolioStyle.muted),
                                    modifier = Modifier.testTag("tab-$key"))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MarketScreen(state: MarketUiState, controller: MarketController, onBack: () -> Unit, onExchange: () -> Unit) {
    val keyboard = LocalSoftwareKeyboardController.current
    val selected = state.selected
    val focus = LocalFocusManager.current
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            TextButton(onBack, Modifier.heightIn(min = 48.dp).testTag("market-back")) { Text("포트폴리오로") }
            AppPageTitle("종목 찾기")
            OutlinedTextField(state.query, {
                if (state.selected != null) controller.clearSelection()
                controller.updateQuery(it)
            }, label = { Text("종목명 또는 코드") }, leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                singleLine = true, shape = PortfolioStyle.panel,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { keyboard?.hide(); focus.clearFocus() }),
                modifier = Modifier.fillMaxWidth().testTag("query"))
            if (state.country == Country.US || selected?.currency?.name == "USD") {
                OutlinedButton(onExchange, shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("market-exchange")) { Text("미국 종목 참고 환율 · USD/KRW") }
                Text("저장된 환율과 실제 기준일을 확인하세요. 실시간 환율이 아닙니다.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
            }
            if (selected == null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Country.entries.forEach { country ->
                        FilterChip(state.country == country, { controller.updateCountry(country) },
                            label = { Text(if (country == Country.KR) "국내" else "미국") },
                            modifier = Modifier.heightIn(min = 48.dp).testTag("country-${country.name}"))
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CategoryFilter.entries.forEach { filter ->
                        FilterChip(state.filter == filter, { controller.updateFilter(filter) },
                            label = { Text(when (filter) { CategoryFilter.ALL -> "전체"; CategoryFilter.STOCK -> "주식"; CategoryFilter.ETF -> "ETF" }) },
                            modifier = Modifier.heightIn(min = 48.dp).testTag("filter-${filter.name}"))
                    }
                }
                when (val result = state.search) {
                    LoadState.Idle -> Text("국내·미국 주식과 ETF를 검색할 수 있어요.")
                    LoadState.Loading -> {
                        LinearProgressIndicator(Modifier.fillMaxWidth().testTag("search-loading"))
                        Text("종목을 찾고 있어요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    }
                    is LoadState.Failed -> {
                        ErrorMessage(result.message, "search-error")
                        OutlinedButton(controller::retrySearch, Modifier.heightIn(min = 48.dp)) { Text("다시 검색") }
                    }
                    is LoadState.Ready -> {
                        val visible = result.value.filter { state.filter == CategoryFilter.ALL || it.category.name == state.filter.name }
                        if (visible.isEmpty()) Text("검색 결과가 없습니다. 종목명이나 코드를 확인해 주세요.")
                        visible.forEach { stock ->
                            OutlinedCard(onClick = { keyboard?.hide(); controller.select(stock) },
                                border = BorderStroke(1.dp, Color(0xFFE2E8F0)), modifier = Modifier.fillMaxWidth().testTag("stock-${stock.assetId}")) {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(stock.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    Text("${stock.assetCode} · ${stock.market} · ${stock.category}", style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                }
            } else {
                Text(selected.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text("${selected.assetCode} · ${selected.market} · ${selected.currency}")
                TextButton(controller::clearSelection, Modifier.heightIn(min = 48.dp).testTag("clear-selection")) { Text("종목 변경") }
                when (val quote = state.price) {
                    LoadState.Idle -> Unit
                    LoadState.Loading -> {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text("최근 종가를 확인하고 있어요.")
                    }
                    is LoadState.Failed -> {
                        ErrorMessage(quote.message, "price-error")
                        OutlinedButton(controller::retryPrice, Modifier.heightIn(min = 48.dp)) { Text("종가 다시 조회") }
                    }
                    is LoadState.Ready -> {
                        Text("최근 종가 ${quote.value.closePrice.stripTrailingZeros().toPlainString()} ${quote.value.currency}",
                            style = MaterialTheme.typography.titleMedium)
                        Text("기준일 ${quote.value.baseDate}", modifier = Modifier.testTag("price-date"))
                    }
                }
                OutlinedTextField(state.unitPrice, controller::editUnitPrice, label = { Text("거래 단가 (${selected.currency})") },
                    supportingText = { Text("직접 입력한 값은 조회 결과가 덮어쓰지 않아요.") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth().testTag("unit-price"))
                Text("이 화면에서는 조회와 단가 입력까지만 할 수 있어요.", style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun ErrorMessage(message: String, tag: String) {
    Text(message, color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag(tag).semantics { liveRegion = LiveRegionMode.Polite })
}
