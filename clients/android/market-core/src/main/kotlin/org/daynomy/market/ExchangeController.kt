package org.daynomy.market

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Events and state mutations belong to one UI dispatcher. */
class ExchangeController(private val source: ExchangeRateSource, private val scope: CoroutineScope) : AutoCloseable {
    private val mutableState = MutableStateFlow(ExchangeUiState())
    val state: StateFlow<ExchangeUiState> = mutableState.asStateFlow()
    private var active = false
    private var closed = false
    private var generation = 0L
    private var job: Job? = null

    fun updateDate(date: String) {
        if (closed || state.value.date == date) return
        mutableState.update { it.copy(date = date) }
        load()
    }
    fun retry() { if (!closed) load() }
    fun setActive(active: Boolean) {
        if (closed || this.active == active) return
        this.active = active
        if (active) load() else {
            invalidate()
            mutableState.update { it.copy(quote = LoadState.Idle) }
        }
    }
    override fun close() {
        if (closed) return
        closed = true
        active = false
        invalidate()
        mutableState.update { it.copy(quote = LoadState.Idle) }
    }
    private fun invalidate() { generation++; job?.cancel(); job = null }
    private fun current(token: Long) = !closed && active && token == generation
    private fun load() {
        invalidate()
        val date = state.value.date
        if (!active || date.isBlank()) {
            mutableState.update { it.copy(quote = LoadState.Idle) }
            return
        }
        val token = generation
        mutableState.update { it.copy(quote = LoadState.Loading) }
        job = scope.launch {
            try {
                val quote = source.quote(date)
                if (current(token)) mutableState.update { it.copy(quote = LoadState.Ready(quote)) }
            } catch (cancelled: CancellationException) {
                if (current(token)) mutableState.update { it.copy(quote = LoadState.Idle) }
                throw cancelled
            } catch (_: Exception) {
                if (current(token)) mutableState.update { it.copy(quote = LoadState.Failed("환율을 불러오지 못했습니다.")) }
            }
        }
    }
}
