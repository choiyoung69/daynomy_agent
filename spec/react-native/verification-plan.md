# React Native verification boundaries

2026-10-28, independent test-author plan. The application is a separate client under `clients/react-native/`. Existing iOS/Android/Flutter/WebView clients, backend and original reference remain preserved.

## Evidence levels

| Check | What passing establishes | What it does not establish |
| --- | --- | --- |
| Frozen Node core tests | Deterministic transport/state/ledger/decoder behavior for the fixed 27 examples | Hermes behavior, cookie persistence, screen interaction |
| TypeScript compiler | Cross-module and JSX type compatibility for installed declarations | Native dependency registration and SDK build |
| Expo/Metro bundle | JavaScript/native module resolution and bundle generation for selected platform | Successful iOS/Android native app install |
| Synthetic HTTP fixture | Client request/response behavior against explicitly synthetic data | Actual Rust DB or provider behavior |
| Rust HTTP/DB integration | Named fixture behavior against real local server and DB when actually executed | Native HTTP cookie storage or OAuth user interaction |
| Android/iOS app build | SDK compilation/linkage for named OS/toolchain | Real keyboard, accessibility, lifecycle, OAuth behavior |
| Emulator/device scenarios | Observed flow in named device/runtime | Unexecuted other platform behavior |

Do not upgrade Node/Metro/typecheck evidence into native completion. Record commands, exit codes, timestamps, toolchain versions and source hashes for the checked candidate. Test author SHA is in `experiments/react-native/test-author/frozen.json`; rejection-only tests passing on stub were explicitly recorded rather than misreported as pre-implementation success.

## Native acceptance scenarios still requiring actual execution

1. Open portfolio, select KR/US stock, search Korean and ampersand/plus queries. Empty results, failure, retry and loading states differ. Search debounce follows original 250ms policy. Delay A response behind B; only B changes list/loading/error.
2. Select stock, start saved-close query, manually type a price, complete query. Manual input survives and base date is shown unchanged. Switch selection while price pending; old result cannot overwrite new stock. API finite zero remains a decoder-valid value but cannot autofill a positive trade price.
3. Add KRW buy with fees, sell part, edit/delete earlier trade that causes later oversell. Reject invalid change atomically, preserve previous ledger. Confirm no hidden rounding/precision loss in high-value and USD transactions. Confirm actual application wires the tested core rather than duplicate UI math.
4. Restart app and navigate tabs. Guest lifetime must follow the documented policy. Do not silently claim sessionStorage semantics for persistent native storage. Account data is cleared/segregated on logout and account change.
5. Bootstrap CSRF, send feedback, profile update, transaction mutation. Cookies are carried by the real OS networking stack. Missing/invalid CSRF fails without writing. Surface mutation 401 without automatic replay; explicit manual retry requires fresh state.
6. Concurrent authenticated reads produce one shared refresh, failed refresh stops, and logout while refresh is pending cannot restore old session. These races exceed the first fixed 27 examples and require independent extension/inspection.
7. OAuth opens the external user agent, uses cryptographic verifier/state + S256, rejects foreign/malformed callback and wrong state, exchanges only approved code once, and clears pending state after cancel/error/success. Never log verifier/code/cookies/request bodies.
8. Native bottom tabs and Android back/iOS gesture return to expected destination. Modal closes without accidental save; keyboard does not cover actions. Dynamic text, VoiceOver/TalkBack names, touch targets, contrast and safe areas work on each OS.
9. News nullable thumbnail/date renders without literal null, preserves all text/sections/source links, and handles page/category changes. External URL schemes are allowlisted; untrusted link does not execute script.
10. Member calendar/analysis/admin actions use source DTOs and current auth/CSRF. Mere endpoint listing or generic JSON form is not full feature interaction parity. Provider AI/image/social jobs are only verified when corresponding external integration actually ran.

Excluded by inherited scope: league, F14 calendar email notifications and deployment. Marketing/terms/privacy, exact chart layout/media embeds and app-store release requirements are not automatically complete.
