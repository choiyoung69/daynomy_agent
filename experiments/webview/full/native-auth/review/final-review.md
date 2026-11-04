# Independent native WebView OAuth review

## Current decision

**Accepted within the reviewed source and controlled Android execution scope.** No open blocking source finding remains in the 26-file handoff identified below. The independent Android run demonstrates external Chrome app-URI dispatch, native exchange, WebView cookies and protected member flows against real Rust/private DB with local signed OIDC. It does **not** demonstrate automatic HTTP302-to-app dispatch: the verifier obtained the real302 with Chrome-context cookies using APIRequestContext, then clicked its returned app URI in the same Chrome page. iOS execution, real Google, production deployment and forced cookie-write/recreation interleavings remain unverified. Source fixes are complete within this review; full platform validation is not.

## Reviewed handoff and independence

The reviewer did not author or modify production source, the contract, frozen tests, backend, or verification harness. The reviewer writes only `experiments/webview/full/native-auth/review/`. Shared servers, DB and devices were not touched by this role. Independent verification is a separate agent.

- Source manifest: `implementation/source-hashes.json`; manifest file SHA-256 `48b52c78e77104e988c5a6a6870b19b62282674d5f77e48d72069de4b3dec37f`.
- Manifest-reported aggregate: `fb2e3d2c3d54cb2fa7c16410b11d7fcfbe9aa8244bf7c31fe72fbc2f4e55bf05`.
- APK SHA-256: `2bc9bdf08d9905c1672fd31b76bb512ef0a282abccc5a824cce2dfc479f3b07e`.
- New frozen manifest SHA-256: `144fac2d952c9ed8674b85a69a8ebbfa4846481654cc89fa0dce7ded0b2f0f81`.

The reviewer independently recomputed all 26 source file hashes, APK hash, six frozen file hashes and five recorded backend/KB input hashes: no mismatches. See `final-source-check.json`. Independent verifier `handoff-hashes.json` also records matches for the preserved 216-file web implementation and 17 prior frozen files. The original Android/Swift NavigationPolicy files remain unchanged.

## Source conclusions

- The original trusted login link enters native auth only through main-frame, trusted top-document, user-activated GET checks. State/verifier use OS randomness. S256 challenge leaves the app; verifier stays in native memory until an exact-origin native JSON exchange.
- Both pure implementations validate callback URI, once-decoded unique query keys, constant-time state comparison, provider failure, 600000ms handshake and 60000ms accepted-code TTL, replay and stale completion IDs. Process death cannot reconstruct a pending handshake from an unsolicited callback.
- Native HTTP redirects are disabled. Only status204 at the exact exchange URL and the required valid cookie pair can create an installation plan. Cookie security attributes are validated and passed to native stores; no token-bearing JavaScript bridge or token injection was introduced. Existing lifecycle JavaScript contains only the public active/inactive flag.
- Android uses CookieManager completion callbacks; Swift waits for WK cookie completion and confirms stored names/domain/path/value/HttpOnly/Secure before reload. Native requests use isolated transport handling and library JSON encoding. iOS combined Set-Cookie fields are split only at known cookie boundaries and then validated.
- Initial cross-host rollback ownership and iOS SPA/logout interaction findings were communicated to the implementer and fixed before handoff: a process-global cookie owner lease prevents new auth/initial restoration during outstanding installation/rollback, and the underlying WebView interaction is disabled while auth is pending. Native cancel remains available. Cancel invalidates the generation; late install callbacks roll back before releasing ownership. This is source evidence, not a forced OS callback interleaving test.
- Android custom scheme routing may show an OS chooser when another DAYNOMY client handles the same scheme. State/PKCE protection and automatic OS route selection are distinct. Documentation discloses this boundary.

The reviewer additionally executed one standalone macOS Foundation conversion with synthetic cookie data (exit0): HttpOnly, Secure, path, domain and SameSite=lax were retained by HTTPCookie parsing. This does not establish iOS or WK cookie-store behavior.

## Evidence checked so far

The independent verifier's `pure.tap` runs the frozen production Kotlin/Swift suites: two tests, 211 assertions each, no skipped cases, exit0. Implementer build logs show the delivered Android assembleDebug passing; the initial Gradle daemon socket denial remains recorded separately. The existing full host policy suite passed 3/3. Swift syntax parsing/plist checks are explicitly not an iOS SDK compile.

The initial Android runtime attempt failed at provider callback/OS return and is preserved in `verification/android-auth-attempt1.json`/log. Further attempts retain harness failures separately. The final `verification/android-auth.json` reports passed; the reviewer read that result and the executed harness and viewed `android-login-after-logout.png`.

The accepted device result is emulator5576 / Android13 / Chrome109 with real Rust and the private DB, using an ephemeral signed local OIDC provider. The original login link opens external Chrome; native retry cancels an unfinished attempt and starts fresh. A wrong-state callback does not install authentication. The controlled Chrome app-URI link returns through Android OS routing; production native code exchanges the one-use code, and the WebView reaches member `GET /api/users/me`200 and protected MyPage. Cookie inspection records access `/` and refresh `/api/auth`, HttpOnly and SameSite=Lax; Secure=false is the explicitly configured local HTTP debug case. JavaScript cannot see the two token names. Nickname PATCH200, USER/admin UI boundary, logout204 followed by protected GET401, and old-callback replay remaining logged out passed. This does not add runtime server replay/parallel-exchange coverage beyond the reported cases.

The automatic HTTP302-to-app edge remains unverified because the successful harness uses `APIRequestContext` with the external Chrome context to obtain the real server302, then renders and clicks its app-URI link in Chrome. No successful ADB callback delivery is used as evidence for the positive login; explicit ADB delivery is used for wrong-state/replay negatives. The per-step result label must always be read with this delivery qualification.

## Limits

- No automatic browser HTTP302-to-app dispatch proof; the successful controlled delivery method is described above.
- No Xcode/iOS SDK build, iOS authentication session, WK cookie-store or iOS screen execution.
- No real Google or production provider/cookie/deployment validation.
- No forced runtime proof of every cancellation/store callback race; source mitigation and normal runtime evidence remain separate.
- This supplemental auth review does not certify all member/admin product features, other native clients, or omitted league/F14/deployment scope.

`FULL-HOSTS.md` accurately describes the implementation and these limits. Earlier run sections describing absent handoff are historical evidence; the current README/run summary is being updated by the coordinator to point to this bounded supplemental result.
