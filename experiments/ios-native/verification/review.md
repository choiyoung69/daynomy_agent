# Independent verifier disposition

2026-10-28. Third role, distinct from test author and implementer. **Accept the bounded macOS core/HTTP pilot evidence. Do not approve completed iOS application verification.** No unresolved blocking finding remains in the reviewed host core after the changes below. Xcode/iOS SDK, canonical Swift Testing runtime, simulator/UI and device accessibility verification remain unavailable.

## What actually passed

- Original frozen 22 test methods plus independently authored query regression 1: **23 methods, zero failures**, executed by the frozen standalone translation runner on macOS Swift 6.3.3. Original freeze remained unchanged. Canonical Swift Testing execution is blocked by missing `lib_TestingInterop.dylib`; this is not `swift test` success.
- Own compiled Swift executable uses **production URLSessionTransport and StockAPI**, real Python loopback TCP sockets: seven assertions pass for Unicode/literal-plus query, exact long decimal token, business/generic 404, invalid JSON number grammar, cancellation classification and subsecond cancellation. Python observed the request before cancellation and actual socket disconnect afterward. See `candidate-result.json`, `loopback.json`, `loopback.log`.
- Own numeric supplement: **14 assertions pass** (13 PASS lines; final combined line covers both decoder preservation and UI rejection). Integral exponent/leading-zero ID representations, exact fraction/range rejection, duplicate key final-value semantics, and `1e-400` lexical preservation with nonpositive UI rejection. See `numeric-edges.log`, `supplemental-result.json`.
- Same production URLSession binary -> **existing actual Rust HTTP server -> disposable synthetic PostgreSQL fixture**: seven assertions pass. KR/US search, unlisted exclusion, empty result, 20-result cap, latest stored KR date/price, US quote, missing-price business 404. See `rust-live.log`.
- Project and plist syntax passed; shared scheme names the UI test target. UI/source mapping independently inspected. This is source validation, not iOS typing or runtime acceptance.

## Defects and verification-history separation

1. Source review found that a valid exact integer ID expressed with many fractional leading zeros and a compensating exponent was incorrectly rejected by an arbitrary mantissa-length guard. Implementation normalizes leading zeros; own numeric supplement now verifies `0.0000000000000000000000000000000000000001e40 == 1`.
2. Actual loopback HTTP found a real contract regression the initial 22 tests did not catch: `URLComponents.queryItems` left `+` unescaped, so a form-query server decoded it as a space. `attempt03-loopback.json` records the corrupted request and failure. Implementation percent-encodes literal plus. A separate test author wrote `QueryEncodingRegressionTests.swift`, reproduced three failures on the exact prior implementation in an isolated copy, and froze the supplemental test independently. Final 23/0 and actual loopback pass. No old failure was relabeled success.
3. Root's original comparison required last-wins duplicate keys and JavaScript-like finite positive number checking in UI. Implementation now follows those checks while retaining original numeric spelling for display. Own supplement verifies both.
4. Verifier's first HTTP harness compilation failed because its helper lacked MainActor isolation; the verifier-only helper was corrected. Second attempt was blocked by sandbox socket.bind. Attempt logs are preserved separately. Approved local-loopback escalation enabled actual network verification. Neither failure was treated as production success.

## Source and baseline identity

- Original freeze SHA-256: `2c9192de3b8b16a6a83c1b97d81e75c6267a4c9e3be7bacb4e4fa4747a274cd2`.
- Supplemental freeze SHA-256: `e3fa391ff75f51c95d066bf9d97183d536c9f4960f97c87de74771d7145d0094`.
- Final `API.swift`: `d33b9b7c9e4cc21095f8765e66054201d965d683923cf020379c9f842414130d`.
- Final `MarketModel.swift`: `6aa1d0fe9c94f879d565768d7712111ac4533bebfa71641b0682e8174d26bf3c`.
- Actual live Swift executable: `e9e93d5e21f76e8bb4b5c29fe74e061cee670ff8295d19d3317394f118f2366b`.
- Serving Rust binary: `c6e271bda594bc80c29a5de6632e8ca77b6a3964b2e980f1189e4051543f0acd`.

`candidate-result.json` records every client file hash and checks the frozen original/supplemental files and original evidence before and after execution. Supplemental checks again bind to that candidate and verify unchanged client hashes. Final readback confirmed those client hashes unchanged.

The shared fixture was already running at `127.0.0.1:18091`, report `.local/android-next-backend-01/result.json`. The verifier did not start, stop, seed or alter DB resources; requests were GET only. Initial full application source hashes and binary matched. Before and after final Rust requests, startup manifest and on-disk binary matched, market/API code remained identical, and the current-tree mismatch was **app/README.md only**. `supplemental-result.json` records the complete startup source manifest and those differences. Evidence is bound to the serving binary/startup source, not an assertion that every contemporaneous working-tree file is identical. Fixture remained serving afterward.

Fixture limitation: existing seed inserts older date then newer date, so the returned maximum date is checked but this fixture alone does not distinguish a faulty last-inserted-row algorithm. Original Spring `findFirstByAssetIdOrderByBaseDateDesc` and Rust date ordering were also inspected. No concurrent fixture mutation was attempted.

## Independent semantic review

Original `api.ts`, `types.ts`, `PortfolioTransactionEditor.tsx` and backend price service were read directly after KB navigation. Search query/country, all-element array validation, safe positive IDs, category/market validation, date string preservation, finite price decoding and error classification align with the bounded contract. Strict market strings, malformed-currency fallback, exact-safe-ID lexical checks and price spelling preservation are documented native policies, not claimed byte-for-byte original behavior. No exchange/transaction/auth behavior is included.

Parser tokenization is structure-aware and rejects malformed grammar, validates strings with Foundation, retains numeric tokens without Double/Decimal round-trip, and handles nested fields independently. Double is used only for finite/positive checks, not for storing/displaying the token. State is MainActor plus Observable; cancellation and per-request generations guard stale success, failure and loading transitions. Dirty input includes deletion to empty; stock changes reset draft price state. Deactivate cancels requests while preserving draft, activate resumes, and restore invalidates old operations. No unjustified unchecked Sendable was found.

Frozen runner review is bounded to its current simple `@Test func` syntax: expectation Boolean checks, optional requirement throws, exact MarketError comparisons, and Issue.record failure counters retain failure semantics; every method is enumerated and count asserted. It serializes methods on MainActor, unlike general Swift Testing scheduling. This does not prove every possible macro transformation safe. Supplemental form decoder reproduces Rust `+`-to-space handling and tests original URLSearchParams semantics.

UI source connects search, country, category filter, selection, manual editing, stock change, retries, quote/date and lifecycle to the same core. Observable reference is held in State; onDisappear/background deactivate and active/appear activate. SwiftUI Form and labels are present, but source inspection cannot certify focus, VoiceOver, Dynamic Type, keyboard avoidance, rotation or visual correctness.

## Remaining blockers and runnable follow-up

`ios-build-blocked.json` records actual `xcodebuild -list` exit 1, iOS simulator build exit 1, and `xcrun simctl list devices available` exit 72. `environment.json` records CLI-only developer directory and the bounded search finding no full Xcode/SDK/simulator installation. Install/configure full Xcode with chosen iOS SDK/runtime, then query actual scheme/destinations and execute build plus the two UI tests. `ui_fixture.py` supplies the author's delayed quote fixture; it is synthetic HTTP and is not Rust/DB evidence.

Canonical Swift Testing runtime, iOS compile/typecheck, simulator or physical-device execution, actual lifecycle/keyboard/accessibility and both UI tests remain **unverified**. Host results do not close these gaps. Full backend regression was not rerun for this read-only client slice.
