package com.daynomy.webview

import android.app.AlertDialog
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.View
import android.view.WindowInsets
import android.webkit.ValueCallback
import android.webkit.JsResult
import android.webkit.CookieManager
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.window.OnBackInvokedCallback
import java.io.ByteArrayInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import java.util.Base64
import java.util.concurrent.Executors
import java.util.concurrent.Future
import org.json.JSONObject

/** CookieManager is process-wide; a destroyed Activity must finish rollback before another can log in. */
private object NativeAuthCookieTransaction {
    private var owner: Any? = null
    @Synchronized fun busy() = owner != null
    @Synchronized fun acquire(candidate: Any): Boolean { if (owner != null) return false; owner = candidate; return true }
    @Synchronized fun release(candidate: Any) { if (owner === candidate) owner = null }
}

/** Host owns navigation/lifecycle only; all stock/price state stays in the web controller. */
class MainActivity : Activity() {
    private lateinit var root: LinearLayout
    private lateinit var errorPanel: LinearLayout
    private lateinit var errorText: TextView
    private var web: WebView? = null
    private var policy: NavigationPolicy? = null
    private var resourcesPolicy: FullResourcePolicy? = null
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var pickerRequest = 2000
    private var pickerMultiple = false
    private var dialog: AlertDialog? = null
    private var dialogResult: JsResult? = null
    private var active = false
    private var mainFrameFailed = false
    private var modernBack: OnBackInvokedCallback? = null
    private var authSession: NativeAuthSession? = null
    private val authHandler = Handler(Looper.getMainLooper())
    private val authWorker = Executors.newSingleThreadExecutor()
    private var authFuture: Future<*>? = null
    @Volatile private var authConnection: HttpURLConnection? = null
    private var authGeneration = 0L
    private var authPending = false
    private var cookieInstalling = false
    private var cookieRollback = false
    private var cookieOwner: Any? = null
    private var authCancelButton: Button? = null
    private val authTimeout = Runnable { cancelAuth(); showError("로그인 시간이 만료됐습니다. 다시 시도해 주세요.") }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.WHITE) }
        root.setOnApplyWindowInsetsListener { view, insets ->
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.ime())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else {
                @Suppress("DEPRECATION")
                view.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop, insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            }
            insets
        }
        setContentView(root)
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            modernBack = OnBackInvokedCallback { goBack() }.also {
                onBackInvokedDispatcher.registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, it)
            }
        }
        val toolbar = LinearLayout(this)
        toolbar.addView(Button(this).apply { text = "뒤로"; minHeight = dp(48); setOnClickListener { goBack() } })
        toolbar.addView(TextView(this).apply { text = "DAYNOMY · WebView"; textSize = 16f; gravity = android.view.Gravity.CENTER }, LinearLayout.LayoutParams(0, dp(52), 1f))
        authCancelButton = Button(this).apply { text = "로그인 취소"; visibility = View.GONE; setOnClickListener { cancelAuth(); showError("로그인을 취소했습니다. 다시 시도할 수 있습니다.") } }
        toolbar.addView(authCancelButton)
        root.addView(toolbar)
        errorPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(16), dp(20), dp(16)); visibility = View.GONE }
        errorText = TextView(this).apply { textSize = 16f; accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE }
        errorPanel.addView(errorText)
        errorPanel.addView(Button(this).apply { text = "다시 시도"; minHeight = dp(48); setOnClickListener { retry() } })
        root.addView(errorPanel)
        policy = runCatching { NavigationPolicy(BuildConfig.WEB_ORIGIN, BuildConfig.DEBUG) }.getOrNull()
        if (policy == null) { showError("앱의 HTTPS 웹 주소를 설정해야 합니다."); return }
        resourcesPolicy = FullResourcePolicy(BuildConfig.WEB_ORIGIN, BuildConfig.DEBUG)
        authSession = NativeAuthSession(BuildConfig.WEB_ORIGIN, BuildConfig.DEBUG)
        createWebView()
        if (NativeAuthCookieTransaction.busy()) { showError("이전 로그인 정리를 마친 뒤 다시 시도를 눌러 주세요."); return }
        // Navigation history may be restored after process recreation. Unsaved form persistence is not promised.
        if (savedInstanceState == null || web?.restoreState(savedInstanceState) == null) loadHome()
        // Cold/process-death callbacks have no pending native state and cannot establish a session.
        consumeAuthIntent(intent)
    }

    private fun createWebView() {
        val view = WebView(this)
        web = view
        view.setOnTouchListener { _, _ -> authPending || cookieInstalling }
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            safeBrowsingEnabled = true
            mediaPlaybackRequiresUserGesture = true
        }
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(view, false)
        view.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                fileCallback?.onReceiveValue(null); fileCallback = null
                if (policy?.decide(view.url ?: "", false) != NavigationDecision.INTERNAL ||
                    params.mode !in listOf(FileChooserParams.MODE_OPEN, FileChooserParams.MODE_OPEN_MULTIPLE)) {
                    callback.onReceiveValue(null); return true
                }
                pickerMultiple = params.mode == FileChooserParams.MODE_OPEN_MULTIPLE
                fileCallback = callback
                // Unique request IDs prevent a replaced picker's late response reaching the new callback.
                pickerRequest = if (pickerRequest >= 60000) 2000 else pickerRequest + 1
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "image/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, pickerMultiple)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                try { startActivityForResult(intent, pickerRequest) }
                catch (_: Exception) { fileCallback = null; callback.onReceiveValue(null) }
                return true
            }
            override fun onJsAlert(view: WebView, url: String, message: String, result: JsResult): Boolean =
                showWebDialog(url, message, result, false)
            override fun onJsConfirm(view: WebView, url: String, message: String, result: JsResult): Boolean =
                showWebDialog(url, message, result, true)
        }
        view.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return resourcesPolicy?.allows(request.url.toString(), false) != true
                if (startNativeAuth(view, request)) return true
                return when (policy?.decide(request.url.toString(), request.hasGesture())) {
                    NavigationDecision.INTERNAL -> false
                    NavigationDecision.EXTERNAL -> {
                        if (request.isForMainFrame) runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url).addCategory(Intent.CATEGORY_BROWSABLE)) }
                        true
                    }
                    else -> true
                }
            }
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (policy?.decide(request.url.toString(), false) == NavigationDecision.INTERNAL &&
                    ((request.method == "POST" && request.url.path == "/api/auth/logout") ||
                     (request.method == "DELETE" && request.url.path == "/api/users/me"))) {
                    authHandler.post { cancelAuth() }
                }
                if (resourcesPolicy?.allows(request.url.toString(), request.isForMainFrame) == true) return null
                return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0)))
            }
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                if (authPending || cookieInstalling) cancelAuth()
                cancelDialog()
                fileCallback?.onReceiveValue(null); fileCallback = null
                mainFrameFailed = false
            }
            override fun onPageFinished(view: WebView, url: String?) {
                if (!mainFrameFailed) errorPanel.visibility = View.GONE
                setWebActive(active)
            }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) { mainFrameFailed = true; showError("페이지를 불러오지 못했습니다. 연결을 확인하고 다시 시도해 주세요.") }
            }
            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, response: WebResourceResponse) {
                if (request.isForMainFrame) { mainFrameFailed = true; showError("페이지 응답에 문제가 있습니다. 다시 시도해 주세요.") }
            }
            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
                mainFrameFailed = true
                showError("안전한 연결을 확인할 수 없습니다.")
            }
            override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                cancelAuth()
                cancelDialog()
                fileCallback?.onReceiveValue(null); fileCallback = null
                root.removeView(view); view.destroy(); web = null
                showError("웹 화면이 종료되었습니다. 다시 시도해 주세요. 저장하지 않은 입력은 복원되지 않을 수 있습니다.")
                return true
            }
        }
        root.addView(view, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
    }
    private fun cancelDialog() {
        val result = dialogResult; dialogResult = null
        dialog?.dismiss(); dialog = null
        result?.cancel()
    }
    private fun showWebDialog(url: String, message: String, result: JsResult, confirm: Boolean): Boolean {
        cancelDialog()
        if (policy?.decide(url, false) != NavigationDecision.INTERNAL || isFinishing || isDestroyed) {
            result.cancel(); return true
        }
        dialogResult = result
        fun complete(accepted: Boolean) {
            val pending = dialogResult; dialogResult = null
            dialog = null
            if (accepted) pending?.confirm() else pending?.cancel()
        }
        val builder = AlertDialog.Builder(this).setTitle("DAYNOMY").setMessage(message)
            .setPositiveButton("확인") { _, _ -> complete(true) }
            .setOnCancelListener { complete(false) }
        if (confirm) builder.setNegativeButton("취소") { _, _ -> complete(false) }
        dialog = builder.create().also { it.show() }
        return true
    }
    @Deprecated("Platform activity result supported without third-party runtime dependencies")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != pickerRequest) return
        val callback = fileCallback ?: return
        fileCallback = null
        val selected = mutableListOf<Uri>()
        if (resultCode == RESULT_OK && data != null) {
            data.clipData?.let { clip -> for (i in 0 until clip.itemCount) selected.add(clip.getItemAt(i).uri) }
            if (selected.isEmpty()) data.data?.let { selected.add(it) }
        }
        val allowed = selected.isNotEmpty() && (pickerMultiple || selected.size == 1) && selected.all { uri ->
            FullResourcePolicy.acceptsImage(uri.scheme, runCatching { contentResolver.getType(uri) }.getOrNull()) &&
                runCatching { contentResolver.openAssetFileDescriptor(uri, "r")?.use { true } ?: false }.getOrDefault(false)
        }
        callback.onReceiveValue(if (allowed) selected.distinct().toTypedArray() else null)
    }
    private fun loadHome() {
        if (NativeAuthCookieTransaction.busy()) { showError("로그인 정리를 마친 뒤 다시 시도를 눌러 주세요."); return }
        web?.loadUrl(BuildConfig.WEB_ORIGIN + "/")
    }
    private fun retry() {
        cancelAuth()
        if (NativeAuthCookieTransaction.busy()) { showError("로그인 정리를 마친 뒤 다시 시도를 눌러 주세요."); return }
        if (policy == null) return
        if (web == null) { createWebView(); loadHome() } else if (web?.url == null) loadHome() else web?.reload()
    }
    private fun showError(message: String) { errorText.text = message; errorPanel.visibility = View.VISIBLE }
    private fun setWebActive(value: Boolean) {
        web?.evaluateJavascript("window.dispatchEvent(new CustomEvent('daynomy:active',{detail:$value}));", null)
    }
    override fun onResume() { super.onResume(); active = true; web?.onResume(); setWebActive(true) }
    override fun onPause() { active = false; setWebActive(false); web?.onPause(); CookieManager.getInstance().flush(); super.onPause() }
    override fun onSaveInstanceState(outState: Bundle) { web?.saveState(outState); super.onSaveInstanceState(outState) }
    @Deprecated("Compatible with API 26 history handling")
    override fun onBackPressed() { goBack() }
    private fun goBack() { cancelAuth(); if (NativeAuthCookieTransaction.busy()) { showError("로그인 정리를 기다려 주세요."); return }; val view = web; if (view != null && view.canGoBack()) view.goBack() else finish() }
    private fun randomAuthValue(): String = Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(32).also { SecureRandom().nextBytes(it) })
    private fun startNativeAuth(view: WebView, request: WebResourceRequest): Boolean {
        if (request.url.path != "/api/auth/google" || policy?.decide(request.url.toString(), false) != NavigationDecision.INTERNAL) return false
        // Never let an ineligible login navigation fall through to embedded OAuth.
        if (authPending || cookieInstalling || NativeAuthCookieTransaction.busy()) { showError("로그인이 진행 중입니다. 잠시 후 다시 시도해 주세요."); return true }
        val launch = authSession?.begin(request.url.toString(), view.url ?: "", request.method, request.isForMainFrame,
            request.hasGesture(), randomAuthValue(), randomAuthValue(), SystemClock.elapsedRealtime())
        if (launch == null) { showError("로그인 버튼을 눌러 다시 시작해 주세요."); return true }
        authGeneration += 1
        authPending = true
        authCancelButton?.visibility = View.VISIBLE
        view.isEnabled = false
        authHandler.postDelayed(authTimeout, 600_000)
        showError("외부 브라우저에서 로그인해 주세요. 취소한 경우 다시 시도를 눌러 주세요.")
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(launch.authorizationURL)).addCategory(Intent.CATEGORY_BROWSABLE)) }
        catch (_: Exception) { cancelAuth(); showError("로그인 브라우저를 열지 못했습니다.") }
        return true
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); consumeAuthIntent(intent) }
    private fun consumeAuthIntent(receivedIntent: Intent?) {
        val callback = receivedIntent?.dataString ?: return
        receivedIntent.data = null
        val exchange = authSession?.receive(callback, SystemClock.elapsedRealtime())
        if (exchange == null) {
            if (authSession?.isPending != true) cancelAuth()
            showError("로그인을 완료하지 못했습니다. 다시 시도해 주세요."); return
        }
        val current = authGeneration
        authFuture = authWorker.submit {
            var connection: HttpURLConnection? = null
            try {
                connection = URL(exchange.exchangeURL).openConnection() as HttpURLConnection
                authConnection = connection
                connection.instanceFollowRedirects = false
                connection.useCaches = false
                connection.connectTimeout = 15_000
                connection.readTimeout = 15_000
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                val body = JSONObject().put("code", exchange.code).put("codeVerifier", exchange.codeVerifier).toString().toByteArray(Charsets.UTF_8)
                connection.setFixedLengthStreamingMode(body.size)
                connection.outputStream.use { it.write(body) }
                val status = connection.responseCode
                val responseURL = connection.url.toString()
                val cookies = connection.headerFields.entries.filter { it.key?.equals("Set-Cookie", true) == true }.flatMap { it.value }
                runCatching { (if (status < 400) connection.inputStream else connection.errorStream)?.close() }
                authHandler.post {
                    if (current != authGeneration || isFinishing || isDestroyed) return@post
                    val plan = authSession?.complete(exchange.requestId, status, responseURL, cookies, SystemClock.elapsedRealtime())
                    if (plan == null) { cancelAuth(); showError("로그인 세션을 연결하지 못했습니다. 다시 시도해 주세요.") }
                    else installAuthCookies(plan, current)
                }
            } catch (_: Exception) {
                authHandler.post { if (current == authGeneration && !isDestroyed) { cancelAuth(); showError("로그인 연결에 실패했습니다. 다시 시도해 주세요.") } }
            } finally { connection?.disconnect(); if (authConnection === connection) authConnection = null }
        }
    }
    private fun installAuthCookies(plan: AuthCookiePlan, current: Long) {
        val owner = Any()
        if (!NativeAuthCookieTransaction.acquire(owner)) { cancelAuth(); showError("로그인 저장을 마칠 때까지 잠시 기다려 주세요."); return }
        cookieOwner = owner
        cookieInstalling = true
        cookieRollback = false
        val manager = CookieManager.getInstance()
        fun next(index: Int) {
            if (current != authGeneration || isFinishing || isDestroyed) { rollbackAuthCookies(plan); return }
            if (index == plan.setCookieHeaders.size) {
                cookieInstalling = false
                NativeAuthCookieTransaction.release(owner); cookieOwner = null
                authPending = false
                authCancelButton?.visibility = View.GONE
                web?.isEnabled = true
                authHandler.removeCallbacks(authTimeout)
                manager.flush()
                web?.loadUrl(plan.reloadURL)
                return
            }
            manager.setCookie(plan.originURL, plan.setCookieHeaders[index]) { accepted ->
                if (!accepted || current != authGeneration || isFinishing || isDestroyed) {
                    if (current == authGeneration) cancelAuth()
                    rollbackAuthCookies(plan)
                    if (!isDestroyed) showError("로그인 쿠키를 저장하지 못했습니다. 다시 시도해 주세요.")
                } else next(index + 1)
            }
        }
        next(0)
    }
    private fun rollbackAuthCookies(plan: AuthCookiePlan) {
        if (cookieRollback) return
        cookieRollback = true
        val manager = CookieManager.getInstance()
        val deletions = plan.setCookieHeaders.map { header ->
            val pieces = header.split(';').map { it.trim() }
            val name = pieces.first().substringBefore('=')
            val attributes = pieces.drop(1).filter { it.startsWith("Path=", true) || it.startsWith("Domain=", true) || it.equals("Secure", true) }
            "$name=; Max-Age=0; HttpOnly; SameSite=Lax; " + attributes.joinToString("; ")
        }
        fun clear(index: Int) {
            if (index == deletions.size) {
                manager.flush(); cookieInstalling = false; cookieRollback = false
                cookieOwner?.let { NativeAuthCookieTransaction.release(it) }; cookieOwner = null
                web?.isEnabled = true
                return
            }
            manager.setCookie(plan.originURL, deletions[index]) { clear(index + 1) }
        }
        clear(0)
    }
    private fun cancelAuth() {
        authGeneration += 1
        authPending = false
        authCancelButton?.visibility = View.GONE
        authSession?.cancel()
        authHandler.removeCallbacks(authTimeout)
        authFuture?.cancel(true); authFuture = null
        authConnection?.disconnect(); authConnection = null
        if (!cookieInstalling) web?.isEnabled = true
        // A queued cookie callback observes the new generation, then rolls back before another begin.
    }
    override fun onDestroy() {
        cancelAuth()
        authWorker.shutdownNow()
        fileCallback?.onReceiveValue(null); fileCallback = null
        cancelDialog()
        if (android.os.Build.VERSION.SDK_INT >= 33) modernBack?.let { onBackInvokedDispatcher.unregisterOnBackInvokedCallback(it) }
        web?.let { root.removeView(it); it.stopLoading(); it.destroy() }; web = null; super.onDestroy() }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
