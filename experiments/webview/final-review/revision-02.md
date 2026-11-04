# Independent fix verification — revision 02

## 1. Scope / evidence

2026-10-28. Same independent final reviewer as round 01; implementation and frozen tests were read only. This pass verifies the two reported findings and the resulting stock search → latest stored close → manual unit-price pilot. It does not approve login, transaction saving, deployment, the whole service, or iOS execution.

Read the changed `market.ts:27` and `app.ts:23`, all independent round02 suite logs/results, Android/desktop runtime JSON and the runtime inspection source, Android host-check JSON/source, final integrity manifest, and the separate documentation rediff. The implementation role's report is not treated as an acceptance test. Independently recomputed every revision02 implementation-manifest hash: all match. Of the 17 implementation/config files hashed by this reviewer in round01, exactly market.ts and app.ts changed. The frozen manifest remains SHA256 `dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9`; all 13 frozen files match. Current source/dist/evidence hashes are in `revision-02-hashes.json`.

Actual independent evidence: TypeScript/unit 29/29, Kotlin/Swift policy 2/2, HTTP and actual Chromium DOM 2/2; all round02 suite commands exit 0. The verifier's real-server runs record desktop Chromium156 and Android13/WebView109 on emulator-5564 using the local web18082 → Rust18091 setup. Both record KR quote 71000.125/date 2026-10-23, US193.4/USD, and exact empty manual deletion after reactivation. Android also records exact `0001.2300000000000000001` preservation after Home/resume and rotation, and actual keyboard shown. These are bounded synthetic local fixtures, not production-market or authenticated-session evidence.

Visually inspected these files under `verification/screenshots/`: `round02-desktop-quote-full.png`, `round02-android-quote.png`, `round02-android-keyboard-device.png`, `round02-android-landscape.png`, `round02-desktop-mobile-full.png`, and `round02-android-missing-price.png`. Also inspected, but rejected as full-page evidence, `round02-android-quote-full.png`: it repeats the top search section twice and omits the price panel. The valid Android quote viewport provides the required price/date evidence instead; no product defect is inferred from the capture artifact. Landscape capture shows only the scrolled lower area, so rotation's exact value is established by runtime JSON, not by a full landscape composition claim.

The existing code-led white/purple-blue utility world remains the visual authority. No approved generated comp exists. Impeccable launcher/detector was unavailable as already recorded; no detector findings, clean detector result or injected overlay are claimed. This reviewer launched no browser/device/DB checks and no further agents.

## 2. Strengths

- Binding the default fetch receiver fixes the platform-specific failure while preserving dependency injection and the controller's cancellation/manual-input contracts. The unchanged real-browser test now completes the core flow.
- Desktop quote capture has a clear search/price split, readable stock identity and raw date, and explicit limited-scope notice. Android quote viewport displays the same data in a coherent single column.
- The native Android keyboard capture shows the full manual string in a visible, focused price field above the keyboard, with the native toolbar and OS surfaces present. The 390px desktop mobile error capture shows readable wrapping, manual-entry guidance and the retry action without horizontal clipping.
- Runtime metrics report viewport/scroll widths equal at 1365, 412 and 390px and measured active controls at least 48px high. Six reviewed CSS/computed text-color pairs calculate at 5.00:1–17.66:1 contrast (`revision-02-contrast.json`). Semantic labels, status regions, focus styling and textContent insertion from the original source review remain intact. This is not a screen-reader certification.
- Actual Android supplementary checks keep six rejected navigation targets at the trusted origin; the JS marker remains unset, a synthetic cookie survives background/resume and is removed, and native Back restores internal history. An external HTTPS activation dispatches to Chrome's first-run activity while WebView remains at its trusted origin. That demonstrates dispatch, not successful external destination loading.

## 3. Material findings with file / line / evidence

| Prior finding | Revision02 status | Evidence |
| --- | --- | --- |
| P1 unbound browser fetch, `web/src/market.ts:27–29` | **Resolved** | Default is now `globalThis.fetch.bind(globalThis)`; frozen HTTP/Chromium DOM both pass; actual Android and desktop searches reach quote values shown in JSON/captures. |
| P3 mobile directional copy, `web/src/app.ts:23` | **Resolved** | Copy is now “검색창에서 종목을 찾아보세요.” Android/desktop initial runtime DOM records the neutral wording; mobile single-column remains unchanged. |

No new blocking product defect was identified within this bounded fix review. Two evidence limitations must remain explicit:

1. `round02-android-quote-full.png` is invalid full-page composition evidence. Use the valid `round02-android-quote.png` plus native keyboard capture; preserve the bad capture as a capture limitation.
2. `verification/runtime-inspect.mjs` initially waits for `직접 입력` to identify missing-price completion, but the loading message also contains that text. Consequently `desktop-runtime.json.missingPrice` records loading/retry:false even though later screenshot and layout data show the final error/retry UI. Android's JSON has the settled error. The original runtime script never clicks retry. These original artifacts prove error presentation, but do not by themselves prove an actual retry request. **Evidence gap now closed:** the separate recovery verifier produced `verification/recovery/desktop-retry.json` and `android-retry.json`. This reviewer read both JSON files and the exact `recovery/retry.mjs`: each waits for settled error + visible retry + cleared date, clicks the real retry control, observes request count 1→2 and two HTTP404 responses, then verifies the settled error/retry/date state again. The premature original observation remains unchanged as historical evidence.

## 4. Disposition

**Both original findings are resolved. Accept the corrected core web/Android pilot behavior and inspected visual states within the recorded environment.** No design rebuild or additional polish is warranted. Retain round01 failed runs and the corrected round02 evidence separately.

Acceptance is scoped: actual explicit-retry execution is now verified by the separate strict recovery evidence, rather than inferred from the original generic runtime status `passed`. iOS remains source/pure-policy only: no full Xcode app build, WKWebView run, keyboard/device or rendering approval. Android API26 minimum-version execution, renderer-process termination recovery, TalkBack/VoiceOver and comprehensive release HTTPS deployment remain outside the demonstrated results. No whole-platform or deployment ship approval is given.

## 5. Fix verification requirements

- Completed for the reported product fixes: final source + rebuilt ESM, immutable frozen tests, real Chromium DOM, actual Android/Rust flow and valid desktop/Android quote captures.
- **Completed:** strict settled-error and explicit retry checks on desktop and actual Android. Both record one new price request, two HTTP404 responses in total and a visible manual-entry/error/retry state with cleared date. The early original observation remains preserved.
- Use only the valid Android quote viewport for price/date visual evidence; a new full-page capture is unnecessary for this scoped verdict. Landscape visual coverage is limited to the captured lower section.
- Keep final evidence hashes and scope aligned in the coordinator's report. Treat later iOS/Xcode/device validation and broader Android/accessibility checks as separate work.

Final supplemental evidence: recovery/integrity.json records unchanged frozen13, revision02 web9, host22, KB21, context and APK hashes, all matching. Both restored-state JSON files record KR71000.125/date2026-10-23 and empty script-visible cookie storage. The coordinator reported a verifier model-capacity interruption; earlier cleanup left the retry environment disconnected. The recovery desktop first attempt also selected an extension target before the runner selected an actual page. These are retained execution/diagnostic incidents, not product defects or changes to frozen criteria. No implementation changes were needed after revision02.

**Final verdict: original P1/P3 resolved; scoped web/Android pilot accepted for the recorded local fixture flow, including explicit retry. iOS build/device remains unverified.**
