# Independent iOS verification preparation

Role: third verifier, distinct from test author and implementer. 2026-10-28. Writes confined to `experiments/ios-native/verification/`.

## Environment blocker

`environment.json` records actual command exits and bounded alternate installation search. Active developer directory is `/Library/Developer/CommandLineTools`; Swift is 6.3.3 targeting arm64 macOS 26. `xcodebuild -version` exits 1 because full Xcode is required. `xcrun` cannot find iphoneos, iphonesimulator, or simctl. Spotlight Xcode bundle search finds none. Depth-four searches of /Applications, ~/Applications, /Library/Developer, ~/Library/Developer, /opt, /Volumes, ~/Downloads and ~/develop find no Xcode app or iOS SDK (only unrelated Homebrew Xcode.md). This is a bounded search, not a proof over every file on the machine.

KB consulted first: `knowledge/wiki/platforms/ios.md`, `shared/build-validation.md`, and iOS Swift package documents. They already distinguish host Swift examples from iOS builds. Actual gap: installation prerequisite. Apple [Xcode command-line tool reference](https://developer.apple.com/documentation/xcode/xcode-command-line-tool-reference) states its tools require Xcode and the app selected as developer directory. Apple [simulator runtime installation](https://help.apple.com/xcode/mac/current/en.lproj/deva7379ae35.html) describes downloading required runtimes in Xcode. Consequently full Xcode with iOS platform SDK and chosen simulator runtime must be installed/configured before project scheme/destination build or UI runtime can be certified. No tools installed; no developer directory changed.

`python3 scripts/check.py preflight`: actual exit 0, original snapshot 29/29 matches. No DB/server/behavior verified by that command.

## Independent original comparison

Directly read original frontend `features/stocks/api.ts`, `types.ts`, `PortfolioTransactionEditor.tsx`, and backend `StockPriceService.java`. Core expectations:

- Search GET encodes q; KR country omitted, US explicit. Whole stocks array validation. JS safe positive integer IDs; category STOCK/ETF and known markets.
- Original market validator uses String coercion, so strict string-only native policy is a documented difference. Original currency is unvalidated and nullish fallback uses case-sensitive `.US`; fallback for malformed currency is native defensive policy.
- Original price decoder checks finite number and date string. It allows zero/negative and arbitrary calendar text; UI rejects nonpositive prices. Original web first sets date even for nonpositive price; native hiding invalid quote date is a policy difference.
- Original price is a JS Number, while native lexical decimal spelling preservation is deliberate precision improvement. Exact lexical safe-ID validation is stricter than web Number rounding and needs separate labeling. Malformed JSON must fail regardless of custom lexical parser.
- Original search delay is 250 ms after JS trim; both cancel and latest-generation protection must cover success, failure and loading completion.
- Original unit-price change sets dirty even when deleting to empty. Price auto-fill needs both empty current input and no edit. Stock change resets edit/input/date.
- Native deactivate/activate and draft restoration are explicit pilot lifecycle policies, not proof of identical original navigation semantics.
- Backend `findFirstByAssetIdOrderByBaseDateDesc` selects the latest stored row; absent price is business 404. No current market feed claim.

## Acceptance checklist for candidate

1. Frozen test SHA matches before and after run; actual green tests, no skipped cases; compiling red evidence predates implementation.
2. Custom parser: invalid grammar, booleans/strings/null, escaped quotes, duplicate/nested keys, huge exponent, long decimal, safe-ID exactness and integral exponents. Never allow arbitrary token matching outside JSON structure.
3. State: obsolete success/error/loading suppression, cancel propagation, dirty deletion, stock change, deactivate and restore; MainActor ownership. No unjustified unchecked Sendable.
4. Screen: each input/state binds to core, model state changes are observable, selected date/price/error/manual field mapped, lifecycle passes through deactivate/activate; safe-area/keyboard/VoiceOver and background behavior require actual iOS runtime.
5. Host core tests and live loopback HTTP marked macOS only. Own loopback server checks Unicode query, exact decimal, business/generic errors, malformed JSON, and server-observed TCP disconnect on task cancellation.
6. Coordinated fixture: production URLSession adapter -> production StockAPI -> actual Rust HTTP -> disposable synthetic PostgreSQL. Check KR/US, unlisted exclusion, empty, server limit, newest stored date, precise price and missing price. Root alone starts/stops fixture under shared DB lock.
7. Record implementation/core/host test/harness/Rust binary/source identities and unresolved limitations. iOS build/UI runtime remain blocked until SDK/runtime exist.
