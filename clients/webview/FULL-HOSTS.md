# DAYNOMY full WebView hosts

`android-full/` and `ios-full/` display `fullweb/` served by `scripts/serve-full.mjs`. They reuse the React application; they are distinct from native Android/iOS apps and from the preserved WebView pilot hosts. The copied `NavigationPolicy` files are byte-identical to the pilot versions.

Main documents remain restricted to one configured scheme/host/effective port. User-activated external HTTPS links open in the OS browser. Android subframe requests and iOS frame delegates permit valid external HTTPS content; HTTPS assets are now allowed for news images and social embeds. Browser CSP restricts script hosts and API connections, and same-origin isolation remains active. There is no privileged JavaScript bridge, token extraction, TLS bypass, mixed-content grant or camera permission. External providers may still block embeds or require cookies; these integrations need actual provider testing.

Android file inputs use the system `ACTION_OPEN_DOCUMENT` picker, `CATEGORY_OPENABLE`, and `image/*`. The user chooses the document. Returned URIs must use `content`, resolve to an image MIME type and be readable. Cancel, replacement, navigation, renderer termination and Activity destruction complete pending callbacks with cancellation. Multiple files are accepted only when the input requested multiple mode. The web form retains its JPEG/PNG/WebP and size validation. No arbitrary filesystem paths or capture intents are used. Standard JS alert/confirm dialogs accept only callbacks with a trusted origin; cancellation and lifecycle cleanup complete each result once.

iOS keeps WKWebView's OS-provided file input UI. Trusted mainframe alert/confirm callbacks use UIKit dialogs; external frame dialogs are cancelled. Content rules allow external HTTPS resources and exact configured debug HTTP. Blob previews created by the trusted web origin and data image resources remain web-owned images under the page CSP. Main documents are checked independently. iOS content-rule compilation, file selection and all UI behavior remain unverified until an Xcode/iOS SDK host is available.

## Build and development

Android uses API26 minimum, compile/target35, AGP8.9.2, Gradle8.11.1, Kotlin2.1.20 and JDK21. Application ID `com.daynomy.webview.full` preserves the separately installed pilot. Framework Activity/WebView and Kotlin stdlib are the runtime dependencies.

```sh
JAVA_HOME=/Users/seoyeong/Library/Java/JavaVirtualMachines/ms-21.0.12/Contents/Home \
GRADLE_USER_HOME="$PWD/.local/android-gradle" \
.local/android-tools/gradle-8.11.1/bin/gradle -p clients/webview/android-full \
  --offline --no-daemon -PdebugWebOrigin=http://127.0.0.1:18082 :app:assembleDebug
```

APK: `android-full/app/build/outputs/apk/debug/app-debug.apk`. The override above uses `adb reverse tcp:18082 tcp:18082` on the verifier-selected device. The full web server proxies to the separate Rust fixture backend, normally port18091 for validation. Configure backend CORS to the actual page origin `http://127.0.0.1:18082`. The default Android origin remains `http://10.0.2.2:18082`, requiring matching backend CORS if used. Debug allows only the configured loopback/emulator origin; production requires `-PwebOrigin=https://...` and rejects cleartext.

iOS minimum is15, Swift5, UIKit/WebKit/Foundation. Bundle identifier is `com.daynomy.webview.full`; Debug uses `http://127.0.0.1:18082`, Release requires `DAYNOMY_WEB_ORIGIN` set to a single HTTPS origin.

```sh
xcodebuild -project clients/webview/ios-full/DaynomyWebView.xcodeproj \
  -scheme DaynomyWebView -configuration Debug -sdk iphonesimulator \
  CODE_SIGNING_ALLOWED=NO build
node --test clients/webview/full-tests/full-host-policy.test.mjs
```

The current host has no Xcode/iOS SDK. Swift host policy execution and syntax parsing do not establish iOS build or screen success. WKWebView content-rule compilation and UI execution remain unverified.

## Native OAuth handoff addition

The original trusted `/api/auth/google` link is intercepted only for a main-frame GET from the trusted top document and a user gesture. The hosts generate cryptographic random state/verifier, open the existing server `/api/auth/mobile/start` in an external authentication user agent, validate the fixed `org.daynomy.app://auth/callback` URI and state, and exchange its one-use code with PKCE S256. Android uses an OS browser and exact callback intent-filter with `singleTask`/`onNewIntent`; iOS retains an `ASWebAuthenticationSession` with ephemeral browsing requested. This does not put the provider login inside WebView.

The native exchange disables HTTP redirects and accepts only the exact configured exchange endpoint, status204 and both correctly scoped HttpOnly session cookies. The server's raw security attributes are validated before CookieManager/WKHTTPCookieStore installation; no cookie/code/verifier is injected into JavaScript or logged. All cookie writes are awaited before trusted `/` reload. Foundation's combined Set-Cookie representation is split only at a following session-cookie boundary, then validated without dropping security attributes. The existing web cookie/CSRF/refresh flow remains responsible for later API requests and logout.

The pure session has a ten-minute total handshake lifetime and sixty-second exchange lifetime after the callback is accepted; the backend code separately expires sixty seconds after issuance. State and PKCE are native memory only; cold/process-death callbacks cannot restore a session. A process-wide cookie transaction lease serializes installation/rollback across recreated hosts. Cancellation invalidates late network responses, rolls back only the two exact session cookie names/paths after an in-flight write finishes, and prevents reload/new authentication until cleanup completes. Other cookies and guest storage are not cleared. Web interaction is locked during native authentication, while native cancel/retry remains available. Returning from the Android browser without a callback allows explicit native cancellation; backgrounding alone does not cancel the external login.

The backend callback scheme is shared with other DAYNOMY clients. On Android, installing several clients that handle it can produce an OS chooser; PKCE/state prevent accepting another app's session, but automatic routing to this host is not promised. The iOS system authentication session receives its own callback. Real Google/provider deployment must configure the server's HTTPS callback and the app's HTTPS origin; the local OIDC fixture is not real Google.

This source addition replaces the earlier absent-handoff boundary. At implementation handoff, frozen pure tests execute211 assertions each in Kotlin/Swift and the Android APK builds. Actual Android browser→Rust/OIDC→callback→WebView membership is a separate verifier task. iOS SDK compilation/runtime, real Google and production cookie/provider behavior remain unverified. Do not call the entire native application complete based on the pure tests or Swift parsing.

The additional contract and frozen RED are `spec/webview/native-auth.md` and `experiments/webview/full/native-auth/tests/`; implementation snapshots are in `experiments/webview/full/native-auth/implementation/`. Existing earlier host/test manifests are preserved.

## Evidence and knowledge mapping

The 36 source documents in `experiments/webview/full/knowledge/manifest.json` were read and their SHA256 values matched before implementation. `scripts/check.py preflight` matched29/29 original snapshot files. The existing package's pilot-only readiness does not certify the full app.

| Knowledge rule | Host application |
| --- | --- |
| WebView auth-and-storage, shared auth-storage | No JS token copying; external authentication and validated server Set-Cookie install; external frames have no native privilege |
| state-and-navigation, shared ui-state-navigation | Exact mainframe policy, browser external links, safe-area/IME/back/history, lifecycle cleanup and user retry |
| async-and-cancellation | Pending picker/dialog callbacks complete once; navigation and destruction cancel old callbacks |
| types/numbers/dates/collections | Domain values remain in original web models and are not transformed by hosts |
| news, content-people, administration | HTTPS images/embeds, user-mediated image picker and trusted confirmation dialogs |
| shared testing-migration, modules-and-testing | Frozen independent policy tests, Android APK and actual platform/runtime verification are separate evidence |

`experiments/webview/full/frozen-full-host-policy-tests.json` records missing implementation RED before root GREENLIGHT. New host source hashes, command outcomes and limitations are in `experiments/webview/full/implementation/hosts/`. The independent verifier owns device/runtime acceptance. No deployment or Google/S3/AI production validation is claimed.

Additional official API checks filled the file-selection and content-rule gaps: [Android WebChromeClient](https://developer.android.com/reference/android/webkit/WebChromeClient) documents chooser callback and URI validation responsibility; [WebKit content blocker format](https://webkit.org/blog/3476/content-blockers-first-look/) documents the restricted regex subset. WK rules enumerate port ranges without counted quantifiers or alternation; actual iOS compilation remains pending.

For the native authentication addition, [Apple's web authentication guide](https://developer.apple.com/documentation/authenticationservices/authenticating-a-user-through-a-web-service) supports a retained system session, presentation anchor and ephemeral browsing request. [Android CookieManager](https://developer.android.com/reference/android/webkit/CookieManager) specifies asynchronous cookie completion; the host waits for each callback. These API references do not establish runtime success on the unavailable iOS SDK.
