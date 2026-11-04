# Web implementation revision 02

2026-10-28. Root authorized correction after independent verifier found a real browser defect. The first revision and its failed runtime evidence remain unchanged; this is a new implementation revision, not a replacement of the first result.

## Trigger and correction

The independent verifier reproduced `Failed to execute 'fetch' on 'Window': Illegal invocation` with default `MarketApi().search` in Android WebView 109 and desktop Chrome 156. `experiments/webview/verification/fetch-receiver-diagnostic.json` records the default rejection and bound-fetch success. The native fetch had been stored as an object property and invoked with the MarketApi receiver. Node mock contract tests did not expose this browser receiver requirement; the frozen browser DOM test failed on the actual product defect.

`market.ts` now defaults to `globalThis.fetch.bind(globalThis)`, preserving the browser global receiver. Injected mock fetchers and the public API remain unchanged. `app.ts` empty-state copy says “검색창” instead of the desktop-specific “왼쪽 검색창”. `DESIGN.md` now states the actual primary 8px input/filter/button radius alongside 7px country segments, 10px group and 4px result rows.

KB mapping: webview modules-and-testing and shared testing-migration distinguish pure language/mocks from browser/host execution. This defect demonstrates that boundary. Existing S01/S04/S07/S09 API data semantics, credentials/signal contract and cancellation/manual-input policies are unchanged. No spec, test, configuration, source KB or original reference files were edited.

## Evidence

- `before-source-hashes.json`: changed files immediately before this revision. `revision-01-source-hashes.json`: preserved nine-file original implementation hash record. `source-hashes.json`: all nine current source/document hashes after correction.
- `npm --prefix clients/webview/web test`: exit 0; build and 29/29 tests pass. Raw output `unit.log`, command result `unit-result.json`.
- `node --test clients/webview/tests/http-browser.test.mjs` with authorized escalation: exit 0; 2/2 pass, including actual HTTP and actual Chrome DOM search → select → quote → exact input/deletion → local filters → page/native lifecycle. Raw output `http-browser.log`, command result `http-browser-result.json`.
- All 13 frozen test/config/evidence hashes rechecked unchanged before and after this correction.

The implementation role's successful browser run is self-verification. Independent Android WebView revalidation and final acceptance remain with the verifier/coordinator. No verifier-owned server or fixture was stopped or changed. iOS WKWebView execution remains a separately blocked item where full Xcode is unavailable.
