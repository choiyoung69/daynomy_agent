# Independent iOS pilot test author

Frozen contract/tests are listed with SHA256 in `frozen-tests.json`. API.swift and MarketModel.swift were throwing/no-op stubs at freeze; their hashes are separately recorded, not fixed implementation constraints. Test author did not implement behavior.

Baseline: iOS17+, Swift6 language mode, installed Apple Swift6.3.3 arm64 macOS. No Xcode/iOS SDK simulator execution. Core uses Foundation and no third-party package dependencies. Canonical tests use Apple Swift Testing; UI source uses XCTest, outside SwiftPM.

## Actual commands and outcomes

1. `swift test --package-path clients/ios --scratch-path /tmp/ios-author-build`: manifest/module cache permissions prevented compilation. `red-api.log` preserved; apparent SDK mismatch was downstream of inaccessible default Clang module cache.
2. Set CLANG_MODULE_CACHE_PATH and SWIFTPM_MODULECACHE_OVERRIDE to /tmp, --cache-path /tmp/ios-author-spm --disable-sandbox: compiled core; canonical test import Testing unresolved because CLT framework search path absent. `red-fixed-cache.log` preserved.
3. Added -Xswiftc -F /Library/Developer/CommandLineTools/Library/Developer/Frameworks and linker -F/-rpath: first found nested #require recursive macro compilation error; author split optional URL and URLComponents checks. `red-api-02.log` preserves failed test source attempt.
4. Same flags: build successful; SwiftPM runner loader failed because CLT Testing.framework depends on absent lib_TestingInterop.dylib. `red-behavior-01.log` preserves failure. This is not behavior red.
5. `python3 experiments/ios-native/test-author/run_host_tests.py`: canonical bodies transpiled only assertion syntax into a standalone swiftc executable; generated source in temporary folder. `red-host-01.log` 19 cases/29 failed assertions; `red-host-02.log` 20 cases/30 failed assertions.
6. Final same standalone command: `red-host-final.log`, 22 cases, 32 failed assertions, exit1, 3.447 seconds including compile+execution. This is actual compiling behavior red against no-op API/model. API positive tests throw invalidResponse; model tests report missing requests rather than hangs. All 22 function names enumerated and executed serially; no skips. Freeze follows this run.

Harness semantics: #expect boolean becomes evaluated Bool assertion; #expect(throws:) compares exact MarketError; #require nil throws; Issue.record increments failure counter. Every canonical @Test function is invoked; zero discovered cases fails; thrown unexpected errors fail; any assertion failure exits1. Independent verifier reviewed this translation. It does not exercise Swift Testing macro diagnostics/parallel scheduling and is not a claim `swift test` passed.

## Evidence-derived assertions

`frontend/src/features/stocks/api.ts`: search q encoding, country KR omission/US inclusion, required stocks array, positive safe IDs, STOCK/ETF and seven markets, price/date types. Native IDs use exact decimal-integrality rather than lossy JS parsing; lexical 1.0000000000000000001 is rejected defensively, while integral 1.0 and 1e0 are valid.

`frontend/src/features/stocks/types.ts`: currency nullish fallback and case-sensitive .US suffix. Native approved Android-aligned policy also falls back for malformed/unsupported currency; this is a deliberate defensive mapping, not exact original acceptance output.

`frontend/src/features/portfolio/components/PortfolioTransactionEditor.tsx`: trim/debounce/abort guards, manual input including deletion stays dirty, current input preserved, <=0 quote rejected by editor but accepted API decoder, category filter does not alter complete result set, change-stock draft reset. Native activate/deactivate/restore are explicitly selected lifecycle mappings, not claims original web executes iOS navigation.

Price lexical strings preserve JSON numeric precision beyond Decimal's capacity. No arithmetic or silent rounding performed in the contract. Base date remains arbitrary String as original decoder; no timezone/calendar conversion promised. Excluded: login, auth refresh, trading save, league, F14, deployment.

## UI test fixture boundary

`clients/ios/UITests/DaynomyIOSUITests.swift` contains 2 independent XCTest scenarios (search/select/quote/change-stock; pending-quote manual deletion). Requires external controlled fixture server: DAYNOMY_UI_BASE_URL defaults localhost18082, app receives DAYNOMY_API_BASE_URL. q=삼성 produces assetId1; quote123.4500/baseDate2026-10-24 delayed at least2s. Source not compiled or run here; implementer owns PBX target linkage. Actual fixture/backend/UI evidence belongs to separate verifier.
