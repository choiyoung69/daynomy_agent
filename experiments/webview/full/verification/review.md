# Independent WebView review (2026-10-28)

Role: verifier, separate from frozen-test author and both implementations. No application/server/frozen-test/knowledge/backend/native source was modified.

- preflight: original29/29 snapshots match.
- Frozen5 files, handoff216 files, KB36 documents match their fixed SHA256 manifests. Original212 import source hashes match; copy-at-time claims agree with source; final12 adaptations match reviewed diff.
- Independently built a verification-owned copy. Production build+typecheck exit0 and all16 dist bytes match implementation dist exactly.
- Unit35/35 and UI40files385/385 pass; UI385 comprises384 imported tests plus1 implementation-authored lifecycle test. Excluded original mixed-league tests remain excluded and are not reported as fully covered nonleague tests.
- Independently reran fixed server contract:10 tests including parent/subtests, exit0. Additional symlink escape to outside-dist and hidden src target, client abort propagation pass.
- Fixed browser smoke passed in real system Chrome156 at390x844. Frozen file was unmodified. Verification preload resolves playwright from installed local dependency and adds system Chrome executablePath only. API responses synthetic; validates core headings, guest/member admin guard, no privileged data request, feedback dialog, error handling.
- Initial actual-origin20-route screenshot inspection: no unhandled page exceptions/no document-width overflow. API was still unavailable (fixture blocked on shared DB gate), so these screenshots verify error UI only; preserved as backend-unavailable evidence. No real function success claimed from this run.
- First guest click failed because original dismissible onboarding hint overlapped top transaction button. Harness now uses ordinary close-hint click; failure kept. No force click or app change.

Source review: league route/nav/auth prompts and admin recalc removed; pure telemetry/type dependencies retained without active league features. F14 email workflow not included. Server loopback bind/upstream allowlist, raw path validation, canonical dist containment, separate cookies, request/cancellation forwarding and no raw request logging verified. Auth/provider/CSRF remains original API behavior; admin gate checks role and backend remains authority. Env loading disabled, tracking credentials not exposed, no sourcemap upload. Mobile safe area and input sizing added. Foreground hook cancels readonly editor effects and preserves drafts; it does not queue mutations. Browser lifecycle test is separate from native lifecycle proof.

Outstanding: real Rust/DB UI and local signed OIDC execution await fixture readiness; actual Google and native browser-to-WebView cookie transfer unverified; external embeds constrained by unchanged native host allowlist; iOS SDK/runtime unavailable; Android full WebView execution requires ownership coordination. No full-platform completion approval from build/UI import alone.
