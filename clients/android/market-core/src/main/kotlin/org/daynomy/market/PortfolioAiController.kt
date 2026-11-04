package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

/** One UI dispatcher owns this state. Reads never generate an analysis. */
class PortfolioAiController(private val client: PortfolioAnalysisClient, private val scope: CoroutineScope,
    private val onUnauthorized: () -> Unit = {}) : AutoCloseable {
    private val mutableState = MutableStateFlow(PortfolioAiUiState())
    val state: StateFlow<PortfolioAiUiState> = mutableState.asStateFlow()
    private var generation = 0L
    private var historyGeneration = 0L
    private var job: Job? = null
    private var historyJob: Job? = null
    private var closed = false
    fun load() = request(false, false)
    fun generate(refresh: Boolean = false) = request(true, refresh)
    private fun request(write: Boolean, refresh: Boolean) {
        val old = state.value
        if (closed || old.loading || old.submitting || old.loginRequired || write && (old.outcomeUnknown || old.saved?.status == "PROCESSING")) return
        if (write) {
            historyGeneration++; historyJob?.cancel()
            mutableState.update { it.copy(historyLoading = false) }
        }
        val token = ++generation
        mutableState.update { it.copy(loading = !write, submitting = write, message = null) }
        job = scope.launch {
            try {
                val result = if (write) client.generate(refresh) else client.saved()
                if (current(token)) mutableState.update { it.copy(saved = result, loading = false, submitting = false,
                    message = null, loginRequired = false, outcomeUnknown = false, portfolioChanged = false,
                    history = if (write) null else it.history, historyError = if (write) null else it.historyError) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if (current(token)) {
                    if (e is ApiException && e.status == 401) { reset(true); onUnauthorized() }
                    else {
                        val uncertain = write && (e is IOException || e is ResponseFormatException || e is ApiException && e.status == 409)
                        val text = when {
                            uncertain -> "분석 요청 결과를 확인하지 못했습니다. 상태를 다시 조회한 뒤 확인하세요."
                            e is ApiException && e.status == 403 -> "AI 분석 요청 권한을 확인해 주세요."
                            e is ApiException && e.status == 400 -> "보유 자산과 가격을 확인한 뒤 다시 시도해 주세요."
                            write -> "AI 분석을 완료하지 못했습니다. 이전 결과는 유지됩니다."
                            else -> "저장된 AI 분석을 불러오지 못했습니다."
                        }
                        mutableState.update { it.copy(loading = false, submitting = false,
                            outcomeUnknown = it.outcomeUnknown || uncertain, message = text) }
                    }
                }
            }
        }
    }
    fun loadHistory() {
        if (closed || state.value.historyLoading || state.value.loginRequired) return
        val token = ++historyGeneration
        mutableState.update { it.copy(historyLoading = true, historyError = null) }
        historyJob = scope.launch {
            try { val rows = client.history(); if (!closed && token == historyGeneration) mutableState.update { it.copy(history = rows, historyLoading = false, historyError = null) } }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if (!closed && token == historyGeneration) {
                    if (e is ApiException && e.status == 401) { reset(true); onUnauthorized() }
                    else mutableState.update { it.copy(historyLoading = false, historyError = "분석 이력을 불러오지 못했습니다.") }
                }
            }
        }
    }
    fun invalidatePortfolio() {
        if (closed) return
        val pending = state.value.submitting
        generation++; historyGeneration++; job?.cancel(); historyJob?.cancel()
        mutableState.update { it.copy(loading = false, submitting = false, historyLoading = false, history = null,
            portfolioChanged = true, outcomeUnknown = it.outcomeUnknown || pending,
            message = "보유 자산의 분석 상태를 다시 확인해 주세요.") }
    }
    fun reset(loginRequired: Boolean = false) {
        generation++; historyGeneration++; job?.cancel(); historyJob?.cancel()
        mutableState.value = PortfolioAiUiState(loginRequired = loginRequired)
    }
    private fun current(token: Long) = !closed && generation == token
    override fun close() { reset(); closed = true }
}
