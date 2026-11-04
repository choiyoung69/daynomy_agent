# Native WebView OAuth frozen tests

Run from repository root:

```sh
node --test clients/webview/full-tests/native-auth/native-auth.test.mjs
```

The two tests compile and execute the production pure `NativeAuthSession` source with independent Kotlin and Swift cases. Android SDK, iOS SDK, DB and HTTP are not used by this runner. Installed local Kotlin/JDK and host `swiftc` are required. Actual OS browser/callback, HTTP redirect disabling, random generation, cookie-store installation completion, and authenticated WebView UI must be independently verified afterward.

The expected interface is fixed before implementation:

| Item | Kotlin | Swift |
| --- | --- | --- |
| Session | `NativeAuthSession(trustedOrigin: String, debug: Boolean)` | `NativeAuthSession(trustedOrigin: String, debug: Bool)` |
| Constructor | ordinary nonthrowing constructor; invalid configuration makes `begin` return null | ordinary nonfailable/nonthrowing initializer; invalid configuration makes `begin` return nil |
| `begin` arguments | navigationURL, sourceDocumentURL, httpMethod: String; isMainFrame, userActivated: Boolean; state, verifier: String; nowMillis: Long | identical named labels, String/Bool/Int64 |
| `receive` arguments | callbackURL: String, nowMillis: Long | identical named labels, String/Int64 |
| `complete` arguments | requestId: String, status: Int, responseURL: String, setCookieHeaders: List\<String\>, nowMillis: Long | identical named labels, String/Int/[String]/Int64 |
| Return models | nullable `AuthLaunch`, `AuthExchange`, `AuthCookiePlan` | optional `AuthLaunch`, `AuthExchange`, `AuthCookiePlan` |
| `AuthLaunch` | authorizationURL: String | authorizationURL: String |
| `AuthExchange` | exchangeURL, code, codeVerifier, requestId: String | same String properties |
| `AuthCookiePlan` | originURL, reloadURL: String; setCookieHeaders: List\<String\> | String/String/[String] |
| cancellation | `cancel()` invalidates pending generation | `cancel()` invalidates pending generation |

Kotlin production and test source use package `com.daynomy.webview`. Swift test uses top-level `main.swift`. No UIKit/WebKit is imported by the pure test. Mutable-session methods use reference semantics. The values in tests are public synthetic constants and never real login material.

Coverage includes exact login origin/path/source/GET/frame/gesture; RFC S256 challenge and no verifier in browser URL; single pending flow; strict callback URI/query/percent decoding/state; invalid callbacks preserving legitimate pending flow; matched provider failure; 600000ms total TTL; 60000ms accepted-code TTL; reverse clock; duplicate callback/completion; generation cancellation and stale response isolation; exact exchange response URL and status204; both session cookie names, paths, HttpOnly, SameSite=Lax, positive Max-Age, Secure in release, exact optional Domain, duplicate attributes, missing/extra cookies and CRLF rejection. Cookie headers must be preserved unchanged in the native-only installation plan. Case-insensitive cookie attribute parsing and debug loopback HTTP are positive cases.

The backend contract and KB were read first; the explicit S256 example was checked against [RFC7636 Appendix B](https://www.rfc-editor.org/rfc/rfc7636.txt). The app callback TTL and stricter response-cookie policy are from `spec/webview/native-auth.md` and current Rust mobile endpoints, not invented as Google provider behavior.

`experiments/webview/full/native-auth/tests/frozen-tests.json` fixes these files, the supplemental spec, and the initial actual missing-source RED log. `test-compilation.json` is only syntax/typecheck using a temporary ABI-only nil stub, never behavioral success. The first Swift compile overlapped a test-file edit and failed with "input file was modified during the build"; that failure was retained and a stable-file compile passed. No production source existed or was written by the test role.
