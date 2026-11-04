package org.daynomy.market

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Events and state mutations belong to one UI dispatcher. */
class NewsController(private val source: NewsSource, private val scope: CoroutineScope) : AutoCloseable {
    private val mutableState = MutableStateFlow(NewsUiState())
    val state: StateFlow<NewsUiState> = mutableState.asStateFlow()
    private var active = false
    private var closed = false
    private var listGeneration = 0L
    private var detailGeneration = 0L
    private var listJob: Job? = null
    private var detailJob: Job? = null

    fun load() { if (!closed) loadList() }
    fun selectCategory(category: NewsCategory?) {
        if (closed || state.value.category == category) return
        closeDetail()
        mutableState.update { it.copy(category = category, page = 1) }
        loadList()
    }
    fun selectPage(page: Int) {
        if (closed || state.value.page == page) return
        closeDetail()
        mutableState.update { it.copy(page = page) }
        loadList()
    }
    fun openDetail(id: Long) {
        if (closed) return
        mutableState.update { it.copy(selectedId = id) }
        loadDetail()
    }
    fun closeDetail() {
        if (closed) return
        invalidateDetail()
        mutableState.update { it.copy(selectedId = null, detail = LoadState.Idle) }
    }
    fun retryList() { if (!closed) loadList() }
    fun retryDetail() { if (!closed) loadDetail() }
    fun setActive(active: Boolean) {
        if (closed || this.active == active) return
        this.active = active
        if (active) { loadList(); loadDetail() }
        else {
            invalidateList(); invalidateDetail()
            mutableState.update { it.copy(list = LoadState.Idle, detail = LoadState.Idle) }
        }
    }
    override fun close() {
        if (closed) return
        closed = true; active = false
        invalidateList(); invalidateDetail()
        mutableState.update { it.copy(list = LoadState.Idle, detail = LoadState.Idle) }
    }
    private fun invalidateList() { listGeneration++; listJob?.cancel(); listJob = null }
    private fun invalidateDetail() { detailGeneration++; detailJob?.cancel(); detailJob = null }
    private fun currentList(token: Long) = !closed && active && token == listGeneration
    private fun currentDetail(token: Long) = !closed && active && token == detailGeneration
    private fun loadList() {
        invalidateList()
        if (!active) { mutableState.update { it.copy(list = LoadState.Idle) }; return }
        val token = listGeneration
        val snapshot = state.value
        mutableState.update { it.copy(list = LoadState.Loading) }
        listJob = scope.launch {
            try {
                val page = source.list(snapshot.category, snapshot.page, 6)
                if (currentList(token)) mutableState.update { it.copy(list = LoadState.Ready(page)) }
            } catch (cancelled: CancellationException) {
                if (currentList(token)) mutableState.update { it.copy(list = LoadState.Idle) }
                throw cancelled
            } catch (_: Exception) {
                if (currentList(token)) mutableState.update { it.copy(list = LoadState.Failed("뉴스 목록을 불러오지 못했습니다.")) }
            }
        }
    }
    private fun loadDetail() {
        invalidateDetail()
        val id = state.value.selectedId
        if (!active || id == null) { mutableState.update { it.copy(detail = LoadState.Idle) }; return }
        val token = detailGeneration
        mutableState.update { it.copy(detail = LoadState.Loading) }
        detailJob = scope.launch {
            try {
                val detail = source.detail(id)
                if (currentDetail(token)) mutableState.update { it.copy(detail = LoadState.Ready(detail)) }
            } catch (cancelled: CancellationException) {
                if (currentDetail(token)) mutableState.update { it.copy(detail = LoadState.Idle) }
                throw cancelled
            } catch (_: Exception) {
                if (currentDetail(token)) mutableState.update { it.copy(detail = LoadState.Failed("뉴스 상세를 불러오지 못했습니다.")) }
            }
        }
    }
}
