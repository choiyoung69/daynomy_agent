# Full WebView independent review — initial source pass

## Scope/evidence

Reviewed the full-service contract, FULLWEB/FULL-SERVER, KB provenance and applicable shared/WebView auth, storage, cancellation and navigation rules, original-delta.diff, all newly introduced serving/lifecycle/style configuration, original auth/API and affected routes/components. Reviewed native host policy only for integration compatibility; no host modifications, browser/device/DB execution or builds by this reviewer. Source comparison/provenance is independently recalculated in `provenance-initial.json`: 212 original copied-file claims, 216 web handoff hashes, 2 server handoff hashes and all 5 frozen test artifacts match.

Independent verifier artifacts show build success, 35 unit tests, 385 UI tests, frozen server/browser checks and additional symlink/cancellation checks. These are another verifier's execution results, not reviewer reruns. Existing browser-inspect/screenshots contain backend-unavailable 502 states; inspected mobile portfolio and calendar screenshots preserve the original white/blue layout and present recovery controls. They do not prove populated pages or actual backend operations. Runtime screenshots/fixture evidence are pending.

## Strengths

- Narrow, traceable original-source delta; no active league route/menu/recalculation endpoint or F14 notification component/API imported. Two pure league analytics/type dependencies and inactive CSS are distinguishable from active feature exposure.
- Original cookie authentication, shared refresh and CSRF request layer retained. Admin UI guards preserve role checks; backend authorization remains required.
- Static server binds loopback, rejects external API origins, contains real paths/symlinks, distinguishes assets/API failures from SPA navigation and preserves multiple Set-Cookie headers. Proxy cancellation never asserts server rollback or replays mutations.
- Client build disables reference env loading, telemetry configuration and sourcemap upload. No copied `.env`/`.git` material found in imported project scope.
- Existing visual world retained rather than redesigning it. No detector result is claimed; detector launcher unavailable. Contrast, keyboard and native safe-area completeness are not established by these screenshots.

## Material findings

**R1 — P1: query values are treated as path separators, breaking valid login/OAuth/search URLs.** `clients/webview/scripts/serve-full.mjs:42` rejects `%2f`/`%5c` anywhere in the raw URL before line 43 splits off the query. The app itself produces `/login?returnTo=%2Fmypage`; a fresh request/reload gets 400. Encoded slash in a search term also gets 400. A normal OAuth callback containing URL-valued scope can be rejected before reaching the backend. `path-query-proof.json` executes the actual extracted validation function and demonstrates all three. Restrict traversal/encoded-separator checks to pathname; retain malformed raw URL checks without interpreting query values as filesystem segments. Keep the raw query intact for proxying.

**R2 — P2: full-client lifecycle hook does not consume the preserved hosts' activity event.** `clients/webview/fullweb/src/hooks/useWebViewForeground.ts:10` only subscribes to browser visibility/page events. Both hosts explicitly send `daynomy:active` false/true (Android `MainActivity.kt:129`, iOS `WebViewController.swift:116`). Consequently that host signal has no effect on full-client quote/search/rate cancellation. Browser/JSDOM pagehide coverage cannot establish pause behavior on either host. Connect the existing boolean notification with visibility state and test host false/true, malformed payload, draft preservation, read restart and no mutation replay. Treat the notification as lifecycle only, never authorization.

**Scope limitation with deterministic source evidence:** preserved Android `MainActivity.kt:103` blocks every cross-origin subresource, and iOS `WebViewController.swift:67` similarly restricts resource URLs and rejects subframe navigation. Original external news images and X/Threads/YouTube embeds cannot be represented as working full-host features. Android `MainActivity.kt:90` deliberately has no file chooser, so its imported admin image-upload control is unsupported. These are known host restrictions, beyond merely missing provider credentials. Do not weaken the frozen pilot policy ad hoc; either separately contract/test supported host capabilities or report them explicitly as unavailable.

**Needs browser check, not asserted as a confirmed bug:** server CSP `img-src` at `serve-full.mjs:29` lacks explicit `blob:` while `AdminNewsFormPage.tsx:172` creates blob previews for a selected image. Verify native/browser preview behavior under the served CSP before calling upload UI complete.

Minor navigation inconsistency: `App.tsx:193` omits the newly exposed `/investment-calendar` from service-start detection. A first guest deep-link to that screen followed by the portfolio header can return to onboarding. This is lower priority than R1/R2 and needs a focused navigation check.

## Disposition

Fix R1/R2 before approving the full WebView extension's local-serving/lifecycle claim. The import and browser route surface are substantially implemented, but the source import and inherited tests are not full behavioral validation. Do not claim production readiness, full native provider compatibility, real Google OAuth, AI/S3/embeds, native OAuth cookie sharing or iOS runtime completion. Final disposition awaits scoped backend/Android evidence and fix verification.

## Required fix verification

1. A different implementer repairs R1/R2. Preserve the five frozen files and original failed evidence; add focused tests separately.
2. Independently verify actual HTTP GET/HEAD `/login?returnTo=%2Fmypage`, proxy query containing encoded slash and OAuth-style URL-valued scope; encoded separators in pathname must still fail. Re-run fixed server tests.
3. Independently verify existing host `daynomy:active` false/true cancels/resumes only read effects, retains manual price/draft, and rejects malformed detail without changing auth. Include actual Android pause/resume if available; otherwise keep its runtime status unverified.
4. Review populated fixture screens/requests and Android screenshots separately from mocked/502 browser evidence. Image/file-selection/provider features and native OAuth need their own evidence or explicit unsupported status.
5. Refresh changed implementation hashes, verify frozen hashes remain stable, and preserve this initial review and reproducer rather than replacing them with a success-only history.
