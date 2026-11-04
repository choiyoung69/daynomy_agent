package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

interface FeedbackSource { suspend fun submit(content: String, pagePath: String) }

private fun javaBlank(value: String) = value.isEmpty() || value.all { Character.isWhitespace(it) }
fun feedbackContentError(content: String): String? = when {
    content.length > 1000 -> "의견은 1,000자 이내로 입력해 주세요."
    javaBlank(content) -> "의견을 입력해 주세요."
    else -> null
}
private fun pagePathError(path: String): String? =
    if (path.length > 2048 || javaBlank(path)) "화면 경로를 확인해 주세요." else null

class FeedbackClient(private val transport: SessionTransport) : FeedbackSource {
    override suspend fun submit(content: String, pagePath: String) {
        require(feedbackContentError(content) == null) { "Invalid feedback content" }
        require(pagePathError(pagePath) == null) { "Invalid feedback pagePath" }
        val body = buildJsonObject { put("content", content); put("pagePath", pagePath) }
        transport.request("POST", "/api/feedback", body.toString())
    }
}

data class FeedbackUiState(val content: String = "", val isSubmitting: Boolean = false,
    val sent: Boolean = false, val error: String? = null, val outcomeUnknown: Boolean = false)

/** UI-dispatcher confined, like the other Android controllers. No automatic write retries. */
class FeedbackController(private val source: FeedbackSource, private val scope: CoroutineScope,
    private val pagePath: String = "/feedback") : AutoCloseable {
    private val mutable = MutableStateFlow(FeedbackUiState())
    val state = mutable.asStateFlow()
    private var job: Job? = null
    private var closed = false

    fun editContent(content: String) {
        if (closed || mutable.value.isSubmitting || mutable.value.outcomeUnknown) return
        mutable.value = mutable.value.copy(content = content, sent = false, error = null)
    }
    fun submit() {
        val before = mutable.value
        if (closed || before.isSubmitting || before.outcomeUnknown || before.sent) return
        val error = feedbackContentError(before.content) ?: pagePathError(pagePath)
        if (error != null) { mutable.value = before.copy(error = error); return }
        mutable.value = before.copy(isSubmitting = true, error = null)
        job = scope.launch {
            try {
                source.submit(before.content, pagePath)
                if (!closed) mutable.value = FeedbackUiState(sent = true)
            } catch (cancel: CancellationException) {
                throw cancel
            } catch (_: IOException) {
                if (!closed) mutable.value = before.copy(outcomeUnknown = true,
                    error = "전송 결과를 확인하지 못했어요. 이미 접수됐을 수 있으므로 같은 의견을 다시 보내지 마세요.")
            } catch (_: Exception) {
                if (!closed) mutable.value = before.copy(error = "의견을 보내지 못했어요. 잠시 후 다시 시도해 주세요.")
            } finally {
                if (!closed) mutable.value = mutable.value.copy(isSubmitting = false)
            }
        }
    }
    fun reset() {
        if (!closed && !mutable.value.isSubmitting) mutable.value = FeedbackUiState()
    }
    override fun close() {
        closed = true
        job?.cancel()
        mutable.value = mutable.value.copy(isSubmitting = false)
    }
}
