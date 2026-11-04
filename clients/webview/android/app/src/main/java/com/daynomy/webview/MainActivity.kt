package com.daynomy.webview

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.view.View
import android.view.WindowInsets
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

/** Host owns navigation/lifecycle only; all stock/price state stays in the web controller. */
class MainActivity : Activity() {
    private lateinit var root: LinearLayout
    private lateinit var errorPanel: LinearLayout
    private lateinit var errorText: TextView
    private var web: WebView? = null
    private var policy: NavigationPolicy? = null
    private var active = false
    private var mainFrameFailed = false
    private var modernBack: OnBackInvokedCallback? = null

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
        root.addView(toolbar)
        errorPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(16), dp(20), dp(16)); visibility = View.GONE }
        errorText = TextView(this).apply { textSize = 16f; accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE }
        errorPanel.addView(errorText)
        errorPanel.addView(Button(this).apply { text = "다시 시도"; minHeight = dp(48); setOnClickListener { retry() } })
        root.addView(errorPanel)
        policy = runCatching { NavigationPolicy(BuildConfig.WEB_ORIGIN, BuildConfig.DEBUG) }.getOrNull()
        if (policy == null) { showError("앱의 HTTPS 웹 주소를 설정해야 합니다."); return }
        createWebView()
        // Navigation history may be restored after process recreation. Unsaved form persistence is not promised.
        if (savedInstanceState == null || web?.restoreState(savedInstanceState) == null) loadHome()
    }

    private fun createWebView() {
        val view = WebView(this)
        web = view
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
        view.webChromeClient = WebChromeClient() // No dialogs, file picker, permissions or popup grants.
        view.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                return when (policy?.decide(request.url.toString(), request.isForMainFrame && request.hasGesture())) {
                    NavigationDecision.INTERNAL -> false
                    NavigationDecision.EXTERNAL -> {
                        if (request.isForMainFrame) runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url).addCategory(Intent.CATEGORY_BROWSABLE)) }
                        true
                    }
                    else -> true
                }
            }
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (policy?.decide(request.url.toString(), false) == NavigationDecision.INTERNAL) return null
                return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0)))
            }
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
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
                root.removeView(view); view.destroy(); web = null
                showError("웹 화면이 종료되었습니다. 다시 시도해 주세요. 저장하지 않은 입력은 복원되지 않을 수 있습니다.")
                return true
            }
        }
        root.addView(view, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
    }
    private fun loadHome() { web?.loadUrl(BuildConfig.WEB_ORIGIN + "/") }
    private fun retry() {
        if (policy == null) return
        if (web == null) { createWebView(); loadHome() } else web?.reload()
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
    private fun goBack() { val view = web; if (view != null && view.canGoBack()) view.goBack() else finish() }
    override fun onDestroy() {
        if (android.os.Build.VERSION.SDK_INT >= 33) modernBack?.let { onBackInvokedDispatcher.unregisterOnBackInvokedCallback(it) }
        web?.let { root.removeView(it); it.stopLoading(); it.destroy() }; web = null; super.onDestroy() }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
