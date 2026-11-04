package org.daynomy.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.KeyboardArrowRight
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
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
    var nickname by rememberSaveable(profile?.id, profile?.nickname) { mutableStateOf(profile?.nickname.orEmpty()) }
    var withdraw by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.loadAccount() }
    AppPage {
        AppPageTitle("내 계정")
        Text("프로필과 서비스 이용을 관리하세요.", color = PortfolioStyle.muted)
        CoreMessage(model.message)
        when {
            model.accountLoading -> {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("회원 정보를 불러오고 있어요.", Modifier.testTag("account-loading").semantics { liveRegion = LiveRegionMode.Polite })
            }
            model.accountError != null -> {
                OutlinedCard(Modifier.fillMaxWidth(), shape = PortfolioStyle.panel) {
                    Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("계정을 불러오지 못했어요", fontWeight = FontWeight.Bold)
                        Text(model.accountError!!, color = PortfolioStyle.muted)
                        OutlinedButton(model::loadAccount, shape = PortfolioStyle.pill,
                            modifier = Modifier.heightIn(min = 48.dp).testTag("account-retry")) { Text("다시 조회") }
                    }
                }
            }
            profile == null -> {
                Surface(color = PortfolioStyle.soft, shape = PortfolioStyle.panel) {
                    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        Icon(Icons.Outlined.Person, contentDescription = null, tint = PortfolioStyle.blue, modifier = Modifier.size(32.dp))
                        Text("내 자산을 한곳에서", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        Text("로그인하면 보유자산과 거래 내역을 계정에 저장할 수 있어요.", color = PortfolioStyle.muted)
                        Button(onLogin, enabled = !model.busy && model.accountRequiresLogin, shape = PortfolioStyle.pill,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-login")) { Text("Google로 로그인") }
                    }
                }
            }
            else -> Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Surface(shape = PortfolioStyle.pill, color = PortfolioStyle.soft) {
                        Icon(Icons.Outlined.Person, contentDescription = null, tint = PortfolioStyle.muted, modifier = Modifier.padding(14.dp).size(28.dp))
                    }
                    Text("${profile.nickname}\n${profile.email}", Modifier.weight(1f).testTag("account-profile"), style = MaterialTheme.typography.titleMedium)
                }
                HorizontalDivider(color = PortfolioStyle.line)
                Text("프로필", fontWeight = FontWeight.SemiBold, modifier = Modifier.semantics { heading() })
                CoreField(nickname, { nickname = it }, "닉네임", "account-nickname", enabled = !model.busy)
                Text("앞뒤 공백을 제외하고 20자 이내로 입력하세요.", color = PortfolioStyle.muted, style = MaterialTheme.typography.bodySmall)
                Button({ focus.clearFocus(); model.rename(nickname) }, enabled = !model.busy && nickname.isNotBlank() && nickname.trim().length <= 20,
                    shape = PortfolioStyle.pill, modifier = Modifier.heightIn(min = 48.dp).testTag("account-save")) { Text("닉네임 저장") }
            }
        }
        if (model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Column {
            Text("서비스", color = PortfolioStyle.muted, style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(bottom = 8.dp).semantics { heading() })
            AccountMenu("환율 조회", "날짜별 USD/KRW 환율 확인", "tab-exchange", onExchange)
            AccountMenu("의견 보내기", "이용 중 불편했던 점을 알려주세요", "account-feedback", onFeedback)
        }
        if (profile != null && !model.accountLoading && model.accountError == null) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("계정 관리", color = PortfolioStyle.muted, style = MaterialTheme.typography.labelLarge, modifier = Modifier.semantics { heading() })
                OutlinedButton({ focus.clearFocus(); model.logout() }, enabled = !model.busy, shape = PortfolioStyle.pill,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-logout")) { Text("로그아웃") }
                TextButton({ withdraw = true }, enabled = !model.busy, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                    modifier = Modifier.heightIn(min = 48.dp).testTag("account-delete")) { Text("회원 탈퇴") }
            }
        }
    }
    if (withdraw) AlertDialog(onDismissRequest = { withdraw = false }, title = { Text("회원 탈퇴") },
        text = { Text("탈퇴하면 이 계정으로 더 이상 로그인할 수 없습니다. 계속할까요?") },
        confirmButton = { TextButton({ withdraw = false; focus.clearFocus(); model.logout(true) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("탈퇴하기") } },
        dismissButton = { TextButton({ withdraw = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("취소") } })
}

@Composable
private fun AccountMenu(title: String, subtitle: String, tag: String, action: () -> Unit) {
    TextButton(action, modifier = Modifier.fillMaxWidth().heightIn(min = 72.dp).testTag(tag), shape = PortfolioStyle.panel,
        colors = ButtonDefaults.textButtonColors(contentColor = PortfolioStyle.ink), contentPadding = PaddingValues(vertical = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(subtitle, color = PortfolioStyle.muted, style = MaterialTheme.typography.bodyMedium)
            }
            Icon(Icons.Outlined.KeyboardArrowRight, contentDescription = null)
        }
    }
    HorizontalDivider(color = PortfolioStyle.line)
}

@Composable
internal fun AppPage(content: @Composable ColumnScope.() -> Unit) {
    Surface(Modifier.fillMaxSize(), color = PortfolioStyle.colors.surface) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val gutter = if (maxWidth <= 600.dp) 20.dp else (16 + (maxWidth.value * .08f).coerceIn(32f, 128f)).dp
            Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = gutter, vertical = 24.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp), content = content)
        }
    }
}

@Composable
internal fun AppPageTitle(title: String) {
    Text(title, Modifier.semantics { heading() }, fontSize = 22.sp, fontWeight = FontWeight.Bold)
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
