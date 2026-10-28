# Independent native iOS expanded verification

Disposition: **host core and listed real HTTP paths verified; full iOS app is not approved as complete**.

- 51 canonical test methods translated by the frozen standalone runner: 51 unique methods executed, 0 failures. All original and added freeze hashes match; original UI test hash checked against its explicit v1 archive, revised UI against v2 manifest. Runner semantic audit in frozen-runner-review.json. This is not a successful `swift test` runtime run.
- 34 actual URLSession → Rust → isolated PostgreSQL assertions passed, covering filled public feeds, FX, guest calculate/calendar, feedback persistence, synthetic PKCE/member cookies, transaction replay, refresh/logout, and admin feedback/people/multipart-news mutations. One feedback create then admin delete returns row count to baseline. Original feedback-only run also recorded exact +1 row.
- Independent deterministic races first failed, then passed after client generation/session invalidation fixes. Actual loopback URLSession late-refresh response after logout leaves zero auth cookies and rejects stale request. Both passing and failing evidence retained.
- Two additional portfolio currency precedence checks pass. Final copied core source hashes match live source; backend copied binary and all startup source hashes match after run.

Own isolated PG port55561 and Rust18096 were stopped cleanly. Shared cluster and existing shared fixture were untouched. No bodies, cookies, tokens, or DB URLs were logged.

An independent verifier expectation initially required404 after news deletion. Original News.java176 and AdminNewsService263 specify soft deletion; assertion was corrected to DELETED and failed attempt retained. Production/test-author files were not changed by verifier.

Remaining gates: full Xcode/iOS SDK typing and build, Simulator/device execution, native UI tests and real OAuth browser callback are unavailable. Canonical Testing framework runtime is missing lib_TestingInterop.dylib. External AI/image/provider/market jobs and all-screen functional equivalence were not exercised. Multipart optional image bytes are covered by host wire assertions; real Rust multipart verification used JSON request part without provider upload. Static SwiftUI source review and route catalog must not be described as full frontend runtime verification.
