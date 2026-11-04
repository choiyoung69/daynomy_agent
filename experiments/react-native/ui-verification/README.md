# Independent React Native UI verification

This evidence uses the real Expo web bundle and installed Google Chrome in headless mode at 375×812 and 812×375. It verifies React Native Web rendering and UI event wiring. It is **not Android/iOS native OS execution**.

`probe.mjs` first rendered the real app at `http://localhost:18139`. The dev server binds localhost IPv6; `127.0.0.1:18139` failed. The sandboxed initial Expo invocation did not reach a listener; running the local dev server with the approved execution permission started Metro. The installed Playwright package expected cached chromium1234 while only chromium1243 was cached, so the test explicitly uses installed Google Chrome. The development CLI also reports simctl help exit72; it did not run iOS Simulator.

`scenarios.mjs` explicitly intercepts API requests with synthetic route fixtures. This isolates UI event/state behavior from backend authentication/CORS and permits a controlled delayed price response. It never claims those fixture responses are Rust/DB evidence. The independent backend verifier owns actual Rust HTTP/DB checks.

## First actual failure

`results-first-failure.json`, `scenarios-first-failure.log`, `failure.png` preserve the failed first attempt. Opening the guest trade editor and searching rendered `Failed to execute 'fetch' on 'Window': Illegal invocation`. No request reached the route fixture. `ServiceClient.send` invoked the stored browser fetch with the ServiceClient as its receiver. This browser-specific defect was absent from the fake-transport Node tests. It was reported to the coordinator and implementer for source correction. Initial rendering also emitted `Unexpected text node: . A text node cannot be a child of a <View>` from string-valued `&&` expressions.

Reruns must preserve that first failure and record the checked source hashes. All generated UI files are confined to this directory. The fixed 27 contract tests are unchanged.

## Final execution

After the coordinator removed the fetch receiver and changed string-valued JSX conditions to booleans, the latest source was reloaded with an Expo dev-server restart. Two verifier-owned harness defects were preserved separately: wildcard CORS in the synthetic fixture with credentialed fetch, and a text selector that matched the modal and underlying page. The fixture now returns the exact localhost origin plus credentials permission, and the holding selector is scoped to `#root` outside the modal portal. An explicit hidden-save-button assertion confirms modal closure; a separate assertion confirms the actual two-share holding card. Modal/viewport animation settling precedes screenshots.

Final `scenarios.mjs` execution exited **0**: **12/12 checks passed**, uncaught JavaScript errors **0**, unexpected console errors **0**. Expected 401 resource messages from the intentionally unauthenticated fixture are retained separately as `expectedHttpErrors`; they are not application JavaScript errors. Checked source hashes in `source-hashes.json` match the current nine App/src files; the frozen contract test hash also remains unchanged.

Verified UI behavior:

- A delayed recent-close response preserves a manually entered 71000 price and displays the unchanged 2026-10-27 base date.
- Guest buy saves successfully, closes the trade modal, and shows the real main-page 삼성전자 holding with two shares and 71001.00 fee-inclusive average cost.
- Browser reload rehydrates the saved guest ledger. This is web AsyncStorage persistence evidence, not Android/iOS process-restart evidence.
- Trade history, news with nullable thumbnail/date, news detail, explore stock search, calendar empty state, and settings tab respond correctly.
- Portrait 375×812 and landscape 812×375 render without horizontal document overflow. Screenshots were opened and visually inspected after settling.

Final evidence: `results.json`, `scenarios.log`, `source-hashes.json`, `02-trade-manual-375.png`, `03-guest-holding-375.png`, `04-explore-landscape.png`. `01-initial-375.png` is the earlier initial-render image. Native Android/iOS build/device, OS cookies/OAuth, soft keyboard, screen reader and native process restart remain separate platform verification work. Admin authenticated mutations and external-provider jobs were not exercised by this UI scenario.

The final source revision (news category controls narrowed by the coordinator) was restarted and rechecked at 2026-10-28T10:33:02.011Z: all 12 checks passed, source/test hashes matched. The local Expo server was then stopped at the coordinator's request. It ran CI mode and was restarted whenever source changed.
