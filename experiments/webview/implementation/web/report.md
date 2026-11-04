# Web implementation handoff

2026-10-28. Implementation role only. Separate test writer froze the red baseline before writing began. Test/config/spec/knowledge/reference/native-existing sources were not changed. The root verifier must make the independent acceptance judgment.

## Baseline

`experiments/webview/frozen-tests.json` SHA256 `dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9`. All 13 pinned file hashes verified unchanged before writes and after self-checks. Knowledge context SHA256 `718834928fd2415c7c66d627395915f6b9904bc4fbbf74f6abfab595f1ec7f4b`, 21 selected documents from manifest; the context is preparation evidence, not runtime certification.

## KB → source mapping

| Rule/evidence | Implementation |
| --- | --- |
| Stock feature S01, S04, S07, S09; original `stocks/api.ts`, `types.ts` | `web/src/market.ts`: URLSearchParams, KR omission, seven markets using String(value), positive safe integer identity, finite price, raw date, unchecked/nullish currency semantics |
| S02/S03, webview async-and-cancellation, errors-and-transactions | `MarketController`: trim/debounce 250ms, AbortController and distinct request generations; stale success/error/finally cannot mutate state |
| S06/S08, numbers-and-money, dates-and-unicode | selection starts quote; only positive quote auto-fills; input/deletion sets dirty and retains exact string; failed/nonpositive quote clears date with manual-entry guidance; no Date parsing |
| state-and-navigation, shared ui-state-navigation | selected draft retained in JS memory on inactive; boolean native lifecycle event + pagehide/pageshow/visibility merged; repeated active value idempotent; foreground requery; permanent dispose |
| S13/auth-and-storage scope | fetch credentials include; public API has no automatic refresh or retry; server forwards cookies without logging; no token/privileged message bridge |
| modules-and-testing | business state TS independent of DOM; separate compilation/native hosts and immutable independent tests; runtime failures recorded separately |
| UI contract/original utility hierarchy | `app.ts` visible Korean labels, local type filtering, safe textContent for remote names, error recovery, raw date, login/save availability disclosure; `styles.css` original white/purple/blue palette, 48px controls, mobile safe-area/one-column layout |

## Commands and outcomes

1. `python3` SHA256 check of 13 frozen paths: exit 0 before edits.
2. `npm --prefix clients/webview/web test`: exit 0; TypeScript build succeeds, 29/29 contract tests pass, no skips.
3. `node --test clients/webview/tests/http-browser.test.mjs` in sandbox: exit 1; both tests hit `listen EPERM 127.0.0.1` before web execution.
4. Same fixed command with approved escalation: exit 1; HTTP static ESM/API query/cookie/error/path-boundary test passes, Chromium DOM test fails because Chrome DevTools endpoint does not appear within the fixed startup window. No DOM success claimed. Chrome version command: exit 0, Google Chrome 156.0.8078.48.
5. `node --check clients/webview/scripts/serve.mjs`: exit 0.
6. Frozen SHA256 check after edits: exit 0, 13/13 unchanged; source hashes recorded in adjacent `source-hashes.json`.

## Remaining independent verification

Actual Chromium screenshots/DOM and Android WebView runtime belong to the independent verifier; the implementation self-check did not run them successfully. Real Rust/DB fixture checks remain separate from the synthetic HTTP test. Native host compilation/policy and iOS WKWebView execution belong to the host implementer/verifier. Full Xcode is unavailable in this environment. There is no claim of complete WebView validation.

Root review narrowed the local development proxy to 127.0.0.1; Android emulator reaches the host loopback via 10.0.2.2. The proxy accepts only a fixed loopback backend origin and is documented for local validation only. It is not a deployment setup. Drafts are not durable across JS process termination or reload. Source hashes were refreshed after this root-review change. Root also relayed independent verifier evidence that Chrome DevTools could start using the fixed flags; the earlier single DOM failure is not treated as a permanent environment block.

Impeccable context launcher was unavailable in root preparation; direct source context, new-work/operate/craft-floor references were used. Existing world was extended without a new visual identity. No additional subagents were spawned by this role. Visual review/documentation artifacts are present; runtime screenshots still require the independent verifier.
