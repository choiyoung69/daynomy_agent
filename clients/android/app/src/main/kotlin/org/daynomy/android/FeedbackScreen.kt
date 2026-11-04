package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import org.daynomy.market.*

class FeedbackViewModel(baseUrl: String) : ViewModel() {
    private val client = OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).followRedirects(false).build()
    private val transport = SessionHttpTransport(baseUrl, client)
    val controller = FeedbackController(FeedbackClient(transport), viewModelScope)
    override fun onCleared() {
        controller.close(); transport.close()
        client.dispatcher.cancelAll(); client.connectionPool.evictAll(); client.dispatcher.executorService.shutdown()
    }
}

@Composable
fun FeedbackDialog(controller: FeedbackController, onClose: () -> Unit) {
    val state by controller.state.collectAsStateWithLifecycle()
    val invalid = feedbackContentError(state.content)
    AlertDialog(onDismissRequest = { if (!state.isSubmitting) onClose() },
        title = { Text("의견 보내기") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 400.dp).imePadding()
                .verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("로그인 없이 서비스에 대한 의견을 보낼 수 있어요.")
                if (state.sent) {
                    Text("의견을 접수했어요. 감사합니다.", Modifier.testTag("feedback-success")
                        .semantics { liveRegion = LiveRegionMode.Polite })
                } else {
                    OutlinedTextField(state.content, controller::editContent, label = { Text("의견") },
                        minLines = 4, enabled = !state.isSubmitting && !state.outcomeUnknown,
                        isError = state.error != null || (state.content.isNotEmpty() && invalid != null),
                        supportingText = { Text("${state.content.length}/1000 · 이모지는 2자로 계산될 수 있어요.") },
                        modifier = Modifier.fillMaxWidth().testTag("feedback-content"))
                    val error = state.error ?: invalid?.takeIf { state.content.isNotEmpty() }
                    if (error != null) Text(error, color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.testTag("feedback-error").semantics { liveRegion = LiveRegionMode.Polite })
                    if (state.isSubmitting) {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text("의견을 보내고 있어요.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    }
                }
            }
        },
        confirmButton = {
            if (state.sent || state.outcomeUnknown) {
                TextButton(controller::reset, Modifier.heightIn(min = 48.dp).testTag("feedback-new")) { Text("새 의견 작성") }
            } else {
                Button(controller::submit, enabled = !state.isSubmitting && invalid == null,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("feedback-send")) { Text("보내기") }
            }
        },
        dismissButton = {
            TextButton(onClose, enabled = !state.isSubmitting,
                modifier = Modifier.heightIn(min = 48.dp).testTag("feedback-close")) { Text("닫기") }
        })
}
