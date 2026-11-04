# Native WebView OAuth independent source review — initial findings

2026-10-28. Read-only review of production/spec/test/backend/KB files; this role writes only this review directory. No server, DB, emulator, source, or frozen test changes were made. Findings below describe the pre-handoff source and must be rechecked against the final implementation hashes.

## Provenance

The independently calculated frozen manifest SHA-256 is `144fac2d952c9ed8674b85a69a8ebbfa4846481654cc89fa0dce7ded0b2f0f81`. All six frozen files and all five recorded backend/KB read-input hashes match. The original LoginPage links to `/api/auth/google`; its post-login path is stored in sessionStorage before navigation. Rust mobile exchange uses PKCE, a row lock, active-member validation and one-use code deletion, returning HTTP 204 with two HttpOnly session cookies. Source inspection is not a new runtime backend test.

## Findings sent to implementer

1. **Cookie transaction ownership across host recreation.** CookieManager and the default WKWebsiteDataStore outlive an Activity/controller. Initial install/rollback flags were instance-local. A destroyed host's delayed rollback can therefore clear a new host's session cookies. The implementer accepted this source-race finding and plans a process-global lease with owner-checked release, blocking another authentication until rollback finishes. This finding was not reproduced on an OS by the reviewer.
2. **iOS logout during an exchange.** WKNavigationDelegate provisional navigation does not cover SPA transitions or fetch-based logout/account deletion. The initial iOS source lacks Android's logout request cancellation hook. A user action after the authentication browser dismisses can log out before a pending native exchange installs its cookies. Suggested native mitigation is to block underlying WebView interaction during the handshake/install transaction, retain an explicit cancel action, and unlock only on settled cancellation/failure/success/rollback. The implementer has been notified. Runtime iOS coverage remains unavailable.

## Reviewed boundaries so far

Pure Kotlin/Swift state machines validate exact login/exchange/callback origins and paths, callback state and S256 PKCE, two TTLs, one-use reception/completion, stale IDs and cancellation. Cookie validation requires the expected pair, expected paths, positive Max-Age, HttpOnly, SameSite=Lax and Secure outside loopback debug. The Android transport disables redirect following, uses library JSON serialization, and passes Set-Cookie headers directly into the native store. The iOS transport disables redirects and automatic URLSession cookie storage; header splitting and HTTPCookie/WK conversion still need final review and platform execution.

No approval or full-platform-complete claim is made by this initial review. Final source, frozen-suite results, actual Android evidence and explicit iOS/Google limits remain to be reviewed.

## Follow-up inspection

The implementer added process-global transaction leases with owner-checked release to both hosts, and disables underlying WebView interaction during authentication. This addresses the two identified source paths; Android runtime and iOS platform behavior still need separate verification.

A reviewer-owned standalone macOS Foundation check parsed a synthetic `access_token=synthetic; Path=/; Max-Age=1800; HttpOnly; SameSite=Lax; Secure` through `HTTPCookie.cookies`. Exit 0: the parsed properties included `SameSite`, its value was `lax`, and HttpOnly/Secure/path/domain were retained. No live token or network/DB/device was used. This establishes host Foundation conversion behavior only; it does not prove WKHTTPCookieStore or iOS execution. The temporary Swift module cache was removed after inspection.
