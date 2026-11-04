# Native WebView OAuth independent verification plan

Verifier role is separate from the new frozen-test author and native implementer. Only this verification directory may be written. Backend, WebView source and all old/new frozen tests remain read-only.

## Before execution

- Await root GREENLIGHT after author records actual missing-source RED and immutable test hashes.
- Independently verify the frozen files, NativeAuthSession and host source/APK hashes.
- Run the actual Kotlin and Swift frozen suites, preserving command outputs and exits. Run Android compilation and the existing host-policy suite for regression. Swift pure execution/parsing is not an iOS SDK build.
- Confirm root-owned emulator5576 and loopback18082/18091 fixture; never select or stop another device/DB.

## Android full round trip

1. Install the delivered debug APK configured for127.0.0.1:18082, reverse that port, and start the real Activity.
2. Attach WebView CDP with `noDefaults:true` for the installed older engine. Clear only this isolated app's authentication if needed; no feedback submissions or unrelated user-browser changes.
3. Visit the real `/login?returnTo=%2Fmypage`, press the original Google link with a real interaction and verify the external system browser is launched while WebView remains on trusted content.
4. Attach external Chrome CDP if available. Read the local provider `/authorize` query in memory, validate issuer fixture/redirect URI and register synthetic authorization through the existing local mock control. Do not save code/state/nonce/verifier/cookies or full authorization URLs.
5. Navigate that same external browser to the real backend callback. Verify the server produces `org.daynomy.app://auth/callback` and the OS routes it to this app. If Chrome refuses automatic scheme dispatch and explicit ADB delivery is necessary, report browser-to-app dispatch as partial and do not claim the full OS redirect path.
6. Observe actual native exchange and WebView membership through real `/api/users/me`200 and protected MyPage UI. Inspect only redacted cookie properties through native/CDP cookies, confirming HttpOnly while `document.cookie` does not expose access/refresh names.
7. Exercise nickname PATCH200, USER/admin boundary and logout204 followed by protected-route denial. This is an actual Rust+privateDB/local signed OIDC flow, not real Google.
8. Re-deliver the same callback and mismatched/wrong-path callbacks without saving payloads; confirm no new authenticated state after logout and no native crash. Distinguish pure-state-machine security tests from runtime checks.

## Evidence and limits

Save numeric HTTP statuses, step names, selected device/engine version, source/APK hashes, command exits and settled screenshots only. Catch assertion errors with a fixed step/name rather than printing Playwright URL call logs or raw request data. Keep initial harness failures and clearly name adaptations. Android evidence does not approve iOS runtime, real Google, broad member/admin features or production deployment.
