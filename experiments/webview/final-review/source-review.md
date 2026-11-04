# Independent final review — round 01: FIX

## 1. Scope / evidence

Reviewed on 2026-10-28 by a separate final reviewer, read-only for implementation/tests. Scope: stock search → latest stored close → editable unit price, TypeScript web and Android/iOS host source. Authentication, transaction saving, deployment, and full service are excluded. Reviewed `spec/webview/README.md`, PRODUCT/DESIGN and sidecar, the frozen test manifest and test source, knowledge context and relevant WebView packages, original stocks API/types and PortfolioTransactionEditor, web/controller/server, Android policy/activity/config and iOS policy/controller/config.

Independently recomputed frozen manifest SHA256: `dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9`; all 13 pinned files match. Knowledge context matches SHA256 `718834928fd2415c7c66d627395915f6b9904bc4fbbf74f6abfab595f1ec7f4b`; all 21 document hashes match. These are provenance checks, not behavior verification.

The parent reports runtime verification in progress. The inspected `verification/suite-results.json` contains unit and host-policy exits 0 and HTTP/browser exit 1. Do not replace that failed result with an implementer success report. No reviewer browser/device/DB execution was launched, to preserve the runtime verifier's isolation. The reviewer then read `verification/round-01/{android,desktop}-runtime.json`, `fetch-receiver-diagnostic.json`, and diagnosis.md, and visually inspected `round-01/screenshots/android-search.png` and `desktop-search.png`. Android viewport is 412 CSS px and desktop 1365 CSS px; both reported scrollWidth equal to viewport width. The Android screenshot is web-content evidence, not a complete native keyboard/insets capture.

Impeccable craft-floor and Operate guidance were read against the committed white/purple-blue utility interface. The parent reported that the launcher has no installed engine and cache permission; no detector ran and there are no detector findings or overlay claims. This is a scoped final review, not a completed Impeccable dual-assessment critique command.

## 2. Strengths

- `market.ts:67–72,98–138`: separate request generations plus AbortSignals protect search/price from stale success, rejection and finally callbacks. Selection, country change, inactive and dispose invalidate relevant work.
- `market.ts:95,130–136`: manual input, including an empty deletion, marks dirty and survives a delayed quote; price remains a string, date stays an opaque API string, nonpositive price falls back to manual guidance. Decoder semantics match the original API source, including String(market) and nullish currency fallback.
- `app.ts:13–28,58–61,75–88`: Korean labels, explicit unimplemented login/save scope, status/retry controls and textContent for remote values. CSS provides 48px controls, focus indication, one-column layout and reduced-motion treatment. These remain source observations until rendered evidence arrives.
- Host source has no privileged bridge. Parsed scheme/host/effective-port policy, no userinfo, local-debug-only HTTP exceptions, Android file/content/mixed-content denial and SSL cancel, iOS native normal trust handling and fail-closed content-rule creation form a coherent narrow pilot boundary.

## 3. Material findings with file / line / evidence

**P1 — Bind the browser fetch receiver before using the default MarketApi.** `clients/webview/web/src/market.ts:27–29` stores the unbound browser `fetch` and invokes it as `this.fetcher(...)`, making the receiver a MarketApi instance. Real Android WebView109 and desktop Chromium156 cannot complete stock search; the visible result becomes the search error/retry state. The independent Android diagnostic records `TypeError: Failed to execute 'fetch' on 'Window': Illegal invocation` at compiled `MarketApi.request`, while the same API with bound fetch resolves the fixture asset ID. This agrees with the frozen Chromium DOM failure “Search results missing.” As a consequence, selection and latest-price entry cannot be reached in actual WebView. Bind the default browser fetch to globalThis or use a wrapper that invokes it with the browser global receiver, preserve injected test fetchers, rebuild ESM, and rerun the unchanged DOM and real-host flow. Node/arrow-function fakes do not exercise the browser receiver requirement.

Visual evidence supports keeping the current design direction: desktop has clear search/price columns, readable labels and restrained white/blue surfaces; Android has an orderly single column and large touch targets. The captured Android error is below the initial viewport and must be checked through scrolling after the functional fix. Neither selected-price nor keyboard/error-recovery screenshots are yet present, so those states are not visually approved.

P3 copy mismatch: `clients/webview/web/src/app.ts:23` says “왼쪽 검색창에서” although `clients/webview/web/styles.css:67` changes the layout to a vertical column at ≤720px. Mobile readers have no search field to the left. Replace the directional phrase with “검색창에서” (or responsive copy), then include the empty state in the final mobile capture. No behavior/test change is needed for this wording correction.

Unverified boundaries, not invented defects: iOS UIKit/WKWebView build/runtime, screen reader behavior, Android minimum-version runtime, real keyboard/insets/back/rotation/process loss/navigation policy enforcement and screenshots. Their status must follow actual independent evidence.

## 4. Disposition

**FIX / rebuild the web bundle, then recapture and verify.** The P1 fetch receiver defect blocks the pilot’s primary action. Source direction is consistent with the narrow pilot; the design does not need a new visual world. The initial failed logs and captures remain evidence. After the scoped correction, require new passing frozen-DOM and actual Android/backend evidence on matching source hashes before accepting the web/Android pilot. No rebuild of the established visual world is justified by source review. No full iOS approval: Swift CLI policy/syntax cannot certify a WKWebView app.

## 5. Fix verification requirements

1. Fix `market.ts:27–29`, preserve the frozen tests/spec, retain round-01 failed logs/captures, rebuild ESM, and record final source/dist hashes with passing frozen unit, HTTP/browser and actual Android/backend runs.
2. Supply desktop and mobile empty/search/selected/error captures plus actual Android WebView keyboard/manual deletion/lifecycle evidence. Screenshots must match the final implementation and test run.
3. Check the mobile copy correction if made; verify ≤720px readability, no horizontal overflow, 48px controls and visible keyboard focus against rendered evidence.
4. Separate Rust/DB HTTP, synthetic HTTP, Chromium DOM, Android runtime and iOS policy/build/device results. Mark unrun checks unverified and keep iOS build/device blocked unless Xcode evidence is produced.

Review boundary: this round ends with FIX, not ship. The parent will provide the corrected source hashes and independent follow-up evidence for a separate fix-verification pass.
