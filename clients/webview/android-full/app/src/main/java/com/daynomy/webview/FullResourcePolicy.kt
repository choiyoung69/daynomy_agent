package com.daynomy.webview

/** Separate document trust from HTTPS assets; CSP and SOP still apply in the engine. */
class FullResourcePolicy(trustedOrigin: String, debug: Boolean) {
    private val navigation = NavigationPolicy(trustedOrigin, debug)
    fun allows(url: String, isMainFrame: Boolean): Boolean {
        val decision = navigation.decide(url, !isMainFrame)
        return decision == NavigationDecision.INTERNAL || (!isMainFrame && decision == NavigationDecision.EXTERNAL)
    }
    companion object {
        fun acceptsImage(scheme: String?, mime: String?): Boolean =
            scheme == "content" && mime != null && Regex("image/[a-zA-Z0-9.+-]+").matches(mime)
    }
}
