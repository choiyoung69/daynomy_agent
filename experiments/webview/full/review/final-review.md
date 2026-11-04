# Full WebView final scoped independent review

## Scope/evidence

This read-only review covers original-source import fidelity, full nonleague routes, server revision02, web revision02, and new full Android/iOS hosts. It follows the preserved initial `source-review.md` and `revision02-source-review.md`. Only review artifacts were written by this reviewer; application, backend, reference and frozen tests were not modified. Independent execution belongs to the separate verifier; this reviewer inspected its scripts, results and screenshots rather than rerunning browser/device/DB commands.

`provenance-final.json` independently checks all 17 frozen artifacts across four manifests, 216 revised web files and 24 delivered host files. The initial 212 imports were also independently matched to the reference and copy claims. Both new main-document NavigationPolicy copies match the pilot policies byte for byte. Documentation-only changes after delivery are recorded separately, including full-host OAuth limitation wording and the full-version primary README/PILOT archive. They do not invalidate the behavior-source checks.

Execution evidence reviewed:

- Independent production/typecheck build, 35 unit tests, 385 original/UI lifecycle tests, 4 new frozen native-signal tests, 19 server/regression/extra checks; separate Kotlin and Swift full-host policy tests. These test counts establish the exercised contracts, not all product features.
- `native-lifecycle-browser.json`: real Chrome/React with synthetic stock responses; boolean host activity, hidden-document conjunction, manual draft preservation, read restart, no mutation replay and guest session storage.
- `android-core.json`: actual Android13 WebView on dedicated emulator5576, synthetic API responses; route/guard smoke, actual Activity HOME/resume and guest BUY/reload persistence. `android-picker.json` confirms actual ACTION_OPEN_DOCUMENT, readable PNG bytes and decoded blob preview in the original admin form. No API mutation was asserted in that picker run.
- `guest-edit.json`: actual Rust stock search and browser guest BUY/edit/delete, including same-tab sessionStorage persistence. Guest trades remain browser-local by original design; these results are not member ledger DB CRUD.
- `auth-feedback-first.json` plus `feedback-db.json`: actual feedback POST204/success UI and disposable DB count0→1. `auth-feedback.json`: real Rust/browser login through an ephemeral locally signed OIDC fixture, protected MyPage, nickname PATCH200, USER/admin UI boundary and logout followed by denied protected-route reentry. This is not real Google or native OAuth.
- Earlier failures remain preserved. In particular, the logout harness initially waited for `/` although the original MyPage navigates to `/news`; the expectation was corrected from source and rerun, without changing application behavior.

Visual evidence inspected: original mobile portfolio/calendar error-state captures; browser member MyPage and feedback success; actual Android admin preview viewport. These retain the original white/blue/purple UI. The early Android portfolio capture was a loading state and the Android CDP full-page image repeated tiles, so neither is used as proof of a settled full page. The later ADB admin viewport confirms the selected image is visible. No broad visual redesign, pixel-parity approval, computed contrast audit, or unavailable detector pass is claimed.

## Strengths

The implementation extends the original application rather than substituting a small search pilot. Source provenance, nonleague route mapping and explicit F14 exclusion are recorded. Original auth/refresh/CSRF, account roles, guest/member storage distinctions and domain models remain intact.

The two material review defects were repaired after independently frozen failing regressions. Server path security now leaves encoded query values intact, including login returnTo and OAuth scope; pathname traversal controls remain. The foreground hook honors both document and existing native activity signals, cancels reads and preserves manual values without replaying writes. Calendar direct-entry bookkeeping and CSP blob preview support are corrected.

New full hosts add HTTPS resources, image selection and trusted confirmation dialogs separately from the preserved restrictive pilot. Exact main-document origin checks, ordinary browser isolation, TLS checking and no privileged JS bridge remain. Actual Android file input and pause/resume evidence supplements the pure policy tests. Real browser/Rust/DB feedback and session evidence now supplements frontend mocks.

## Material findings

**Resolved:** R1 query/path confusion and R2 missing host-activity integration are closed within the tested local full-web contract. No additional confirmed blocking source regression was found in the reviewed changes.

**Unimplemented boundary: native external OAuth session handoff.** `clients/webview/fullweb/src/features/pages/components/LoginPage.tsx:74` still launches the original same-origin web endpoint. Android `MainActivity.kt:127` and iOS `WebViewController.swift:151` only dispatch user-activated external navigation; neither host implements the complete external authentication user-agent→callback/deep link→WebView session handoff. The launcher-only Android manifest and launch-only iOS AppDelegate do not provide callback processing. A successful browser/local-OIDC test cannot close this gap. FULL-HOSTS now accurately calls this absent/unimplemented rather than merely unverified.

**Unverified breadth:** real Google, external AI/S3 and social-provider rendering, complete authenticated member portfolio CRUD, all administrator writes and synchronization, account withdrawal, broader network/race/accessibility cases and complete iOS behavior are not established by this evidence. New host resource/chooser source support is distinguishable from all-provider operation. iOS has no SDK build or runtime result; Swift policy execution/syntax parsing does not establish UIKit/WebKit compilation or content-rule validity.

## Disposition

**Approve the scoped local implementation for review/use as a full-web preview with the documented limitations.** The original nonleague web surface is imported and wired, the identified serving/lifecycle defects are fixed, tested core browser/Rust/DB flows work, and selected Android WebView operations run on an actual emulator. This is broader than the original search pilot.

**Do not mark the complete service or complete native WebView apps finished.** Native authenticated operation remains blocked by unimplemented OAuth handoff; iOS and listed provider/feature breadth remain unverified. No claim of production deployment or exhaustive original behavioral equivalence follows from copied source or inherited test totals.

## Required fix verification

For the reviewed local preview there is no remaining confirmed R1/R2 fix. Keep the frozen artifacts, earlier failures, final source hashes and evidence distinctions intact.

Before claiming complete native/member capability, implement and independently test external OAuth launch, callback/state/session transfer and logout with platform-appropriate browser/cookie boundaries; do not weaken exact-origin trust or extract HttpOnly tokens. Run an actual iOS SDK build and UI/content-rule/file-input checks. Verify remaining member/admin writes against the disposable DB and provider features against their appropriate fixtures/live integrations. Preserve the original visual world while addressing functional evidence gaps.
