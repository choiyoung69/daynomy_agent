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
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
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
                val feedback: FeedbackViewModel = viewModel(factory = viewModelFactory { initializer { FeedbackViewModel(baseUrl) } })
                var feedbackOpen by rememberSaveable { mutableStateOf(false) }
                var tab by rememberSaveable { mutableStateOf("market") }
                LaunchedEffect(authCallback) {
                    authCallback?.let { callback -> authCallback = null; tab = "account"; core.completeLogin(callback) }
                }
                val owner = LocalLifecycleOwner.current
                DisposableEffect(owner, model, discovery, tab) {
                    fun activate(started: Boolean) {
                        model.controller.setActive(started && tab == "market")
                        discovery.news.setActive(started && tab == "news")
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
                val exchange by discovery.exchange.state.collectAsStateWithLifecycle()
                BackHandler(tab == "news" && news.selectedId != null) { discovery.news.closeDetail() }
                Column(Modifier.fillMaxSize().safeDrawingPadding()) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("market" to "종목", "news" to "뉴스", "exchange" to "환율", "portfolio" to "자산", "account" to "계정").forEach { (key, title) ->
                            FilterChip(tab == key, { tab = key }, label = { Text(title) },
                                modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("tab-$key"))
                        }
                    }
                    Box(Modifier.weight(1f)) {
                        when (tab) {
                            "news" -> NewsScreen(news, discovery.news)
                            "exchange" -> ExchangeScreen(exchange, discovery.exchange)
                            "account" -> AccountScreen(core, onFeedback = { feedbackOpen = true }) {
                                try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(core.loginUrl()))) }
                                catch (_: Exception) { core.showMessage("로그인 브라우저를 열지 못했습니다. 다시 시도해 주세요.") }
                            }
                            "portfolio" -> PortfolioScreen(core)
                            else -> MarketScreen(state, model.controller)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MarketScreen(state: MarketUiState, controller: MarketController) {
    val keyboard = LocalSoftwareKeyboardController.current
    val selected = state.selected
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("종목과 가격", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold,
                modifier = Modifier.semantics { heading() })
            if (selected == null) {
                OutlinedTextField(state.query, controller::updateQuery, label = { Text("종목 검색") },
                    placeholder = { Text("종목명 또는 종목코드") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
                    modifier = Modifier.fillMaxWidth().testTag("query"))
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
