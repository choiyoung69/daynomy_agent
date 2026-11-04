package org.daynomy.android

import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.io.IOException
import java.math.BigDecimal
import java.time.LocalDate
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import org.daynomy.market.*

data class TradeAsset(val id: Long, val code: String, val name: String, val currency: String)

/** Memory-only session and drafts. A lost mutation response requires explicit reconciliation. */
class CoreViewModel(baseUrl: String) : ViewModel() {
    private val session = SessionHttpTransport(baseUrl)
    private val account = AccountClient(session)
    private val portfolio = PortfolioClient(session)
    private val login = NativeLogin(session, baseUrl)
    private var epoch = 0L
    private var searchJob: Job? = null
    private var searchGeneration = 0L
    var profile by mutableStateOf<AccountProfile?>(null); private set
    var holdings by mutableStateOf(JsonArray(emptyList())); private set
    var history by mutableStateOf(JsonArray(emptyList())); private set
    var evaluation by mutableStateOf<JsonObject?>(null); private set
    var performance by mutableStateOf<JsonObject?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var busy by mutableStateOf(false); private set
    var loading by mutableStateOf(false); private set
    var portfolioError by mutableStateOf<String?>(null); private set
    var portfolioRequiresLogin by mutableStateOf(false); private set
    var totalRealizedProfitLoss by mutableStateOf("0"); private set
    var portfolioLoaded by mutableStateOf(false); private set
    var unknown by mutableStateOf(false); private set
    var searchResults by mutableStateOf<List<Stock>>(emptyList()); private set
    var searchBusy by mutableStateOf(false); private set
    var selection by mutableStateOf<TradeAsset?>(null); private set
    var query by mutableStateOf(""); private set
    var country by mutableStateOf(Country.KR); private set
    var editId by mutableStateOf<Long?>(null); private set
    var type by mutableStateOf("BUY")
    var quantity by mutableStateOf("")
    var price by mutableStateOf("")
    var tradeDate by mutableStateOf(LocalDate.now().toString())
    var fee by mutableStateOf("0")
    var tax by mutableStateOf("0")
    var exchangeRate by mutableStateOf("")
    var from by mutableStateOf(LocalDate.now().withDayOfYear(1).toString())
    var to by mutableStateOf(LocalDate.now().toString())
    fun showMessage(text: String) { message = text }
    fun loginUrl(): String {
        check(!busy) { "Another operation is pending" }
        epoch++; session.clearSession(); login.cancel()
        profile = null; holdings = JsonArray(emptyList()); history = JsonArray(emptyList())
        evaluation = null; performance = null; portfolioLoaded = false; portfolioError = null; portfolioRequiresLogin = false; totalRealizedProfitLoss = "0"; loading = false; unknown = false
        searchGeneration++; searchJob?.cancel(); searchBusy = false; searchResults = emptyList(); selection = null
        query = ""; editId = null; quantity = ""; price = ""; type = "BUY"; country = Country.KR
        tradeDate = LocalDate.now().toString(); fee = "0"; tax = "0"; exchangeRate = ""
        from = LocalDate.now().withDayOfYear(1).toString(); to = LocalDate.now().toString(); message = null
        return login.begin()
    }
    fun completeLogin(callback: String) {
        if (busy) return
        val generation = epoch; busy = true; message = null
        viewModelScope.launch {
            try { login.complete(callback); val p = account.me(); if (generation == epoch) { profile = p; message = "로그인했습니다." } }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (generation == epoch) message = "로그인하지 못했습니다. 다시 시작해 주세요." }
            finally { if (generation == epoch) busy = false }
        }
    }
    fun loadAccount() {
        val generation = epoch
        viewModelScope.launch {
            try { val p = account.me(); if (generation == epoch) profile = p }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { if (generation == epoch) { profile = null; message = if (e is ApiException && e.status == 401) "로그인이 필요합니다." else "회원 정보를 확인하지 못했습니다." } }
        }
    }
    fun rename(nickname: String) = mutate(false, "닉네임을 변경했습니다.") { profile = account.updateNickname(nickname) }
    fun logout(withdraw: Boolean = false) {
        if (busy) return
        epoch++; login.cancel(); busy = true; message = null
        profile = null; holdings = JsonArray(emptyList()); history = JsonArray(emptyList()); evaluation = null; performance = null
        selection = null; searchResults = emptyList(); query = ""; editId = null; unknown = false
        loading = false; searchBusy = false; searchGeneration++; searchJob?.cancel()
        portfolioLoaded = false; portfolioError = null; portfolioRequiresLogin = false; totalRealizedProfitLoss = "0"
        quantity = ""; price = ""; type = "BUY"; tradeDate = LocalDate.now().toString(); fee = "0"; tax = "0"; exchangeRate = ""; country = Country.KR
        viewModelScope.launch {
            try { if (withdraw) account.delete() else account.logout(); message = if (withdraw) "탈퇴했습니다." else "로그아웃했습니다." }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { message = "기기의 세션을 종료했습니다. 서버의 처리 결과는 다시 확인해 주세요." }
            finally { session.clearSession(); busy = false }
        }
    }
    fun search(query: String) {
        this.query = query; selection = null; searchResults = emptyList()
        val generation = ++searchGeneration; val owner = epoch; searchJob?.cancel()
        if (query.isBlank()) { searchBusy = false; return }
        searchBusy = true
        searchJob = viewModelScope.launch {
            try { delay(250); val rows = StockSearchClient(session).search(query, country); if (generation == searchGeneration && owner == epoch) searchResults = rows }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (generation == searchGeneration && owner == epoch) message = "종목 검색을 다시 시도해 주세요." }
            finally { if (generation == searchGeneration && owner == epoch) searchBusy = false }
        }
    }
    fun searchCountry(value: Country) { country = value; search(query) }
    fun select(stock: Stock) { searchGeneration++; searchJob?.cancel(); searchBusy = false; selection = TradeAsset(stock.assetId, stock.assetCode, stock.name, stock.currency.name); searchResults = emptyList() }
    fun refreshPortfolio() {
        if (loading) return
        val generation = epoch; loading = true; message = null; portfolioError = null
        evaluation = null; performance = null
        viewModelScope.launch {
            try {
                val saved = portfolio.holdings()
                val records = portfolio.histories(from, to)
                if (generation == epoch) { holdings = saved["holdings"]!!.jsonArray; history = records; totalRealizedProfitLoss = saved.text("totalRealizedProfitLoss"); unknown = false; portfolioLoaded = true; portfolioRequiresLogin = false }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if (generation == epoch) {
                    if (e is ApiException && e.code == "PORTFOLIO_NOT_FOUND") { holdings = JsonArray(emptyList()); history = JsonArray(emptyList()); portfolioLoaded = true; portfolioRequiresLogin = false; totalRealizedProfitLoss = "0"; unknown = false; message = "아직 보유자산이 없습니다. 첫 거래를 등록하세요." }
                    else {
                        portfolioRequiresLogin = e is ApiException && e.status == 401
                        portfolioError = if (portfolioRequiresLogin) "내 포트폴리오는 로그인 후 이용할 수 있습니다." else "보유자산·거래 내역을 확인하지 못했습니다."
                        message = portfolioError
                        if (portfolioRequiresLogin) {
                            holdings = JsonArray(emptyList()); history = JsonArray(emptyList()); portfolioLoaded = false
                            totalRealizedProfitLoss = "0"
                        }
                    }
                }
            } finally { if (generation == epoch) loading = false }
        }
    }
    fun edit(record: JsonObject) {
        searchGeneration++; searchJob?.cancel(); searchBusy = false; searchResults = emptyList(); query = record.text("name")
        selection = TradeAsset(record["assetId"]!!.jsonPrimitive.long, record.text("assetCode"), record.text("name"), record.text("currency").ifBlank { "KRW" })
        editId = record["historyId"]!!.jsonPrimitive.long; type = record.text("changeType")
        quantity = record.text("transactionQuantity"); price = record.text("unitPrice"); tradeDate = record.text("effectiveDate")
        fee = record.text("fee"); tax = record.text("tax"); exchangeRate = record.text("exchangeRate").takeUnless { it == "null" }.orEmpty()
        message = "거래 내용을 확인하고 수정해 주세요."
    }
    fun cancelEdit() { editId = null; quantity = ""; price = ""; fee = "0"; tax = "0"; message = null }
    fun submit() {
        if (busy || unknown) return
        val asset = selection ?: run { message = "먼저 종목을 검색해 선택하세요."; return }
        val count = quantity.toLongOrNull()?.takeIf { it > 0 } ?: run { message = "수량은 양의 정수로 입력하세요."; return }
        val unit = decimal(price)?.takeIf { it.signum() > 0 } ?: run { message = "단가를 확인하세요."; return }
        val costs = listOf(fee, tax).map { decimal(it)?.takeIf { n -> n.signum() >= 0 } }
        if (costs.any { it == null } || tradeDate.isBlank()) { message = "날짜와 수수료·세금을 확인하세요."; return }
        val body = buildJsonObject {
            put("assetId", asset.id); put("type", type); put("tradeDate", tradeDate); put("quantity", count)
            put("unitPrice", JsonPrimitive(unit)); put("fee", JsonPrimitive(costs[0]!!)); put("tax", JsonPrimitive(costs[1]!!))
            if (exchangeRate.isNotBlank()) put("exchangeRate", JsonPrimitive(decimal(exchangeRate) ?: run { message = "환율을 확인하세요."; return }))
        }
        val target = editId
        mutate(true, "거래가 저장됐습니다.") {
            if (target == null) portfolio.createTransaction(body) else portfolio.updateTransaction(target, body)
            editId = null; refreshPortfolio()
        }
    }
    fun deleteTransaction(id: Long) = mutate(true, "거래를 삭제했습니다.") { portfolio.deleteTransaction(id); refreshPortfolio() }
    fun removeHolding(id: Long) = mutate(true, "보유자산을 제거했습니다.") { portfolio.deleteHolding(id); refreshPortfolio() }
    fun adjustHolding(id: Long, quantity: String, average: String) {
        val count = quantity.toLongOrNull()?.takeIf { it > 0 }; val price = decimal(average)?.takeIf { it.signum() > 0 }
        if (count == null || price == null) { message = "보유 수량과 평균 매수가를 확인하세요."; return }
        mutate(true, "보유자산을 조정했습니다.") { portfolio.updateHolding(id, count, price); refreshPortfolio() }
    }
    fun evaluate() = mutate(false, "평가를 조회했습니다.") {
        val body = buildJsonObject { put("holdings", JsonArray(holdings.map { row ->
            val h = row.jsonObject; buildJsonObject { put("assetId", h["assetId"]!!); put("quantity", h["quantity"]!!); put("averagePurchasePrice", h["averagePurchasePrice"]!!) }
        })) }
        evaluation = portfolio.calculate(body)
    }
    fun loadPerformance() = mutate(false, "수익률을 조회했습니다.") { performance = portfolio.performance(from, to) }
    private fun mutate(transaction: Boolean, success: String, action: suspend () -> Unit) {
        if (busy || transaction && unknown) return
        val generation = epoch; busy = true; message = null
        viewModelScope.launch {
            try { action(); if (generation == epoch) message = success }
            catch (e: CancellationException) { if (transaction && generation == epoch) unknown = true; throw e }
            catch (e: Exception) {
                if (generation == epoch) {
                    unknown = transaction && (e is IOException || e is ResponseFormatException)
                    message = if (unknown) "거래 결과를 확인하지 못했습니다. 내역을 새로 조회한 뒤 확인하세요."
                    else if (e is ApiException) when (e.status) { 401 -> "로그인이 필요합니다."; 403 -> "요청 권한을 확인해 주세요."; 400 -> "날짜·수량·금액과 보유 수량을 확인하세요."; else -> "요청을 처리하지 못했습니다. 다시 조회해 주세요." }
                    else "입력값과 연결 상태를 확인해 주세요."
                }
            } finally { if (generation == epoch) busy = false }
        }
    }
    override fun onCleared() { epoch++; login.cancel(); searchJob?.cancel(); session.close() }
}
private fun decimal(text: String): BigDecimal? = try { text.takeIf { it.matches(Regex("[0-9]+(?:\\.[0-9]+)?")) }?.toBigDecimal() } catch (_: NumberFormatException) { null }
internal fun JsonObject.text(key: String): String = (get(key) as? JsonPrimitive)?.content.orEmpty()
