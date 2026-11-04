# Native WebView authentication implementation handoff

Role: implementation, after independent missing-source RED and root GREENLIGHT. This is not independent runtime approval.

## Change

Added Foundation/JVM `NativeAuthSession` implementations for the existing Rust mobile start/exchange contract. The state machine validates trusted login source/origin/path/frame/gesture, cryptographic-state/verifier shape, S256, exact callback/query/state, pending generations, both lifetimes, exact response endpoint/status204 and both HttpOnly cookie headers. Invalid callbacks preserve the legitimate pending flow; matching provider failure/cancellation clears it. Raw secrets stay in native memory and return-model descriptions are redacted.

Android intercepts the existing trusted login anchor, opens the OS browser, receives the exact callback through singleTask/onNewIntent, makes a redirect-disabled JSON exchange and awaits CookieManager writes before trusted reload. iOS uses a retained ASWebAuthenticationSession with ephemeral browsing requested, redirect-disabled ephemeral URLSession and WKHTTPCookieStore installation/readback. Foundation's combined duplicate Set-Cookie representation is normalized only at a following session-cookie boundary before strict validation; raw cookie attributes are not weakened.

Native cancellation remains available while page interaction is locked during authentication. Android browser-back without a callback leaves explicit native cancel/retry available. State is not serialized across process death. Whole-auth and code-exchange lifetimes are distinct. Neither WebView receives a native privilege bridge, injected JS token, custom bearer token scheme or SSL bypass. Existing pure main-document NavigationPolicy files remain byte-identical to pilot copies.

Readonly review found two host integration races during implementation: local cookie state did not serialize a destroyed host's late rollback with a new host, and iOS navigation callbacks do not observe SPA logout actions. Both were addressed before handoff: process-wide owner leases cover installation/rollback and block new login/initial page load until cleanup finishes; native-auth page interaction is locked, with native retry/back/cancel preserved. Cancellation changes generation, old network/cookie callbacks cannot reload, and rollback deletes only the two session-cookie names with their exact path/domain attributes. No remove-all-cookies or guest-storage clearing is used.

## Execution

See `commands.json` and preserved command output:

- First and delivered frozen native-auth runs:2/2 tests, Kotlin211 and Swift211 assertions, exit0, no skip. This is pure host-language behavior, not OS/HTTP execution.
- Existing full-host resource/image/no-bridge policy:3/3, exit0.
- First Android attempt failed before compilation because sandbox blocked Gradle's local daemon socket. `android-first.log` is preserved. Offline escalated build succeeded; intermediate and delivered builds also exit0. Delivered APK is built with debug origin `http://127.0.0.1:18082`.
- Delivered Swift `-frontend -parse`:exit0; project/Debug/Release plist lint:3 OK. This is not UIKit/WebKit/AuthenticationServices SDK compilation.
- New frozen manifest6 files unchanged. Old main-document policies unchanged. Earlier host and test manifests were not rewritten.

Handoff manifest: `source-hashes.json`,26 files, aggregate SHA256 `fb2e3d2c3d54cb2fa7c16410b11d7fcfbe9aa8244bf7c31fe72fbc2f4e55bf05`. APK SHA256 `2bc9bdf08d9905c1672fd31b76bb512ef0a282abccc5a824cce2dfc479f3b07e`.

No backend, original reference, fullweb216 behavior source, other client or test source was modified by this role. FULL-HOSTS documentation is part of this new manifest; its earlier version remains in earlier evidence.

## Verification boundary

The separate verifier must exercise actual Android login anchor→external browser→local OIDC/Rust→callback→cookie exchange→authenticated WebView and logout, plus invalid/replayed callback and cancellation/recreation/late-write behavior. This implementer did not run those device tests. Real Google, provider deployment and iOS SDK/runtime remain unverified. Shared Android callback-scheme handlers may present an OS chooser; PKCE/state prevents cross-app acceptance, while routing choice still needs deployment/platform verification. Complete native/service approval cannot follow from these pure tests and APK build.

Knowledge read: native-auth spec, backend mobile endpoints, auth-session, shared auth-storage, platform WebView and WebView auth-and-storage. Additional API gaps checked against [Apple's web authentication guide](https://developer.apple.com/documentation/authenticationservices/authenticating-a-user-through-a-web-service) and [Android CookieManager](https://developer.android.com/reference/android/webkit/CookieManager). These support API choices; they do not certify unavailable iOS runtime behavior.
