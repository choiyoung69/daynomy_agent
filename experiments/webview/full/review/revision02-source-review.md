# Full WebView revision02 independent source re-review

## Scope/evidence

Reviewed server revision02, web revision02 and new android-full/ios-full source against the earlier source review. No application/backend/test changes, builds, browser or device execution by this reviewer. Independently recalculated 216 web hashes, 24 host hashes and all 17 frozen artifact hashes across four manifests; all match at this pass. Server SHA256 is `7baa7a35a5ac0af3ecbe03fb66b344fcd30b86aa8711ce2bfdb390b658215806`. Both new NavigationPolicy copies are byte-identical to the pilot source. See `provenance-revision02.json`.

Reviewed independent verifier's server 19/19, lifecycle 4/4, inherited UI 385/385, build and native-lifecycle-browser evidence. Real Chrome synthetic stock results establish boolean-event handling, draft/manual-value preservation, guest storage and no mutation replay, not actual Rust DB or provider behavior. Kotlin/Swift pure policy checks and Android APK evidence establish narrower boundaries than native UI tests. Actual Android full-host screenshots/results are pending at this pass; iOS SDK is unavailable.

## Strengths

- R1 repaired: encoded separator checking now applies only to pathname; opaque query values preserve returnTo, encoded search separators and URL-valued OAuth scopes. Path traversal restrictions remain.
- R2 repaired: the hook combines document activity AND boolean native host activity; duplicate state does not retrigger reads, invalid payloads are ignored, and listeners are removed. Calendar deep-link service-start tracking is also corrected.
- Local image blob previews explicitly permitted by CSP; scripts/connect destinations remain restricted.
- New full hosts separate HTTPS subresources/subframes from exact-origin main documents. The restrictive pilot hosts/tests are preserved separately. No privileged bridge, TLS bypass or blanket file access is introduced.
- Android image selection is OS-mediated with content URI, image MIME and readability checks; callbacks cancel on navigation/replacement/process loss/destruction. Trusted JS confirmation dialogs now have completion cleanup. iOS uses ordinary WebKit input UI and main-frame-checked confirmation dialogs.

## Material findings

No further confirmed source defect in the R1/R2 fixes at this pass. Earlier source findings are resolved for the tested local web contract.

**Remaining implementation boundary — native OAuth is not complete.** `fullweb/src/features/pages/components/LoginPage.tsx:74` starts the original same-origin `/api/auth/google` flow. Android full host's `MainActivity.kt:127` and iOS full host's `WebViewController.swift:151` only hand external HTTPS navigation to the OS browser when treated as user activated. Provider redirects do not implement an external authentication session. Android's manifest has only a launcher intent; iOS AppDelegate has only launch handling. Neither host implements the external OAuth callback/session handoff required to return authenticated state to its WebView. This must be described as unimplemented end-to-end, not merely a missing real-account test. It blocks claiming complete logged-in native functionality even if a browser/local OIDC fixture later passes.

External images/embeds and Android chooser are now source-supported in the new hosts; they no longer have the deterministic blanket denial identified in the pilot review. Actual provider rendering/cookies/file selection still need platform verification. iOS content-rule compilation and UIKit/WebKit API compatibility remain unverified because host Swift parsing and pure policy tests do not compile/run the iOS target.

## Disposition

Source-approved for the repaired local full-web serving/lifecycle contract and conditional full-host runtime verification. This is not approval of all service behavior or complete native applications. Preserve the original white/blue UI; no cosmetic rewrite is requested. Final runtime-scoped verdict awaits current Android and fixture evidence.

## Required fix verification

- Preserve frozen artifacts and initial failures. Record documentation-only hash changes separately if OAuth wording is corrected.
- Final report must name native external OAuth user-agent/callback/session handoff as unimplemented; actual Google/S3/AI/social integrations and iOS runtime as unverified.
- Review current full-host Android screenshot/runtime results, including actual pause/resume and picker/dialog/resource behavior where available. Synthetic responses and backend 502 states remain explicitly labeled.
- Actual Rust/DB/OIDC tests remain pending while the shared fixture lock is unavailable. Do not replace them with frontend mocks or reuse unrelated backend completion as client acceptance.
