# WebView revision02 implementation

Independent lifecycle RED/freeze was verified before edits: four actual failures, no skip. The prior 216-file source hashes all matched and were preserved in baseline-source-hashes.json; only useWebViewForeground.ts and App.tsx changed.

The hook now combines document visibility/pagehide/pageshow state AND the native host boolean daynomy:active state. Strings/objects are ignored. Duplicate booleans return the identical state object; an inactive document cannot be resumed by host true alone. React draft owners remain mounted. Existing editor effect cleanup aborts readonly search/price/rate requests, then reissues reads when foreground becomes true; no write request is started by the hook. Manual price and quantity are covered by the fixed test. App now counts a direct investment-calendar visit as a service visit.

KB rules applied: packages/webview/state-and-navigation and async-and-cancellation (separate state ownership from readonly request lifetime); shared/ui-state-navigation (preserve drafts and manual input, abort stale reads); shared/transactions-concurrency TX03/TX04 (never replay mutations or equate read cancellation with transaction rollback); auth-and-storage (same-document nonprivileged lifecycle event, no token bridge).

commands.json records actual commands and exits. Fixed native lifecycle 4/4, original UI plus previous implementation lifecycle 385/385, production build including typecheck all exit 0. Existing JSDOM scrollTo/navigation notices and the original large chunk build warning remain. Frozen initial/query/lifecycle criteria were not changed. Actual server/API/DB and native SDK/UI results remain the separate verifier/coordinator responsibility.

Source and dist are stable for independent re-verification. delta.diff compares the two changed source files to the preserved baseline. source-hashes.json freezes all prior 216 delivered files at the new revision. Earlier manifests/reports were not overwritten.
