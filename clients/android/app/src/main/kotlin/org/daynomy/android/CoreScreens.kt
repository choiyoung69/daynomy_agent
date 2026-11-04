package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.*
import org.daynomy.market.Country

@Composable
fun AccountScreen(model: CoreViewModel, onFeedback: () -> Unit = {}, onExchange: () -> Unit = {}, onLogin: () -> Unit) {
    val focus = LocalFocusManager.current
    val profile = model.profile
    var nickname by remember(profile?.id, profile?.nickname) { mutableStateOf(profile?.nickname.orEmpty()) }
    var withdraw by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.loadAccount() }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        CoreHeading("내 계정")
        TextButton(onExchange, Modifier.heightIn(min = 48.dp).testTag("tab-exchange")) { Text("환율 조회") }
        OutlinedButton(onFeedback, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-feedback")) { Text("의견 보내기") }
        CoreMessage(model.message)
        if (model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (profile == null) {
            Text("로그인하면 보유자산과 거래 내역을 계정에 저장할 수 있어요.")
            Button(onLogin, enabled = !model.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-login")) { Text("Google로 로그인") }
        } else {
            Text("${profile.nickname} · ${profile.email}", Modifier.testTag("account-profile"), style = MaterialTheme.typography.titleMedium)
            CoreField(nickname, { nickname = it }, "닉네임", "account-nickname", enabled = !model.busy)
            Text("앞뒤 공백을 제외하고 20자 이내로 입력하세요.", style = MaterialTheme.typography.bodySmall)
            Button({ focus.clearFocus(); model.rename(nickname) }, enabled = !model.busy && nickname.isNotBlank() && nickname.trim().length <= 20,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-save")) { Text("닉네임 저장") }
            OutlinedButton({ focus.clearFocus(); model.logout() }, enabled = !model.busy,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-logout")) { Text("로그아웃") }
            TextButton({ withdraw = true }, enabled = !model.busy, modifier = Modifier.heightIn(min = 48.dp).testTag("account-delete")) { Text("회원 탈퇴") }
        }
    }
    if (withdraw) AlertDialog(onDismissRequest = { withdraw = false }, title = { Text("회원 탈퇴") },
        text = { Text("탈퇴하면 이 계정으로 더 이상 로그인할 수 없습니다. 계속할까요?") },
        confirmButton = { TextButton({ withdraw = false; focus.clearFocus(); model.logout(true) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("탈퇴하기") } },
        dismissButton = { TextButton({ withdraw = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("취소") } })
}

@Composable internal fun CoreHeading(title: String) { Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineSmall) }
@Composable internal fun CoreMessage(message: String?) { if (message != null) Text(message, Modifier.testTag("core-message").semantics { liveRegion = LiveRegionMode.Polite }) }
@Composable internal fun CoreField(value: String, change: (String) -> Unit, label: String, tag: String,
    keyboard: KeyboardType = KeyboardType.Text, enabled: Boolean = true) {
    val focus = LocalFocusManager.current
    OutlinedTextField(value, change, label = { Text(label) }, enabled = enabled, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard, imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { focus.clearFocus() }), modifier = Modifier.fillMaxWidth().testTag(tag))
}
@Composable internal fun PointSummary(row: JsonObject) {
    fun amount(key: String) = row[key]?.takeUnless { it == JsonNull }?.jsonPrimitive?.content ?: "확인 불가"
    if (row.text("baseDate").isNotBlank()) Text("기준일 ${row.text("baseDate")}", style = MaterialTheme.typography.bodySmall)
    Text("매입 ${amount("totalPurchaseAmount")}원 · 평가 ${amount("totalEvaluationAmount")}원")
    Text("손익 ${amount("totalProfitLoss")}원 · 수익률 ${amount("totalReturnRate")}%")
}
