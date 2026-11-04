# Independent query and upload-preview regression — 2026-10-28

Additional criteria; the initial five frozen files and their original absent-implementation RED remain untouched. This new suite precedes the server correction.

Source defect: serve-full.mjs validatedPath currently checks `%2f` and `%5c` over all of req.url before separating pathname/query. Source contracts require security checks on path separators while preserving query bytes. Original frontend src/features/pages/components/LoginPage.tsx reads `returnTo` from searchParams (line 34); src/App.tsx AuthenticatedRoute/AdminRoute encode the same-origin path with encodeURIComponent. Thus /login?returnTo=%2Fmypage is a required direct/reload URL. SearchPage.tsx uses URLSearchParams; a slash in a query keyword is data. stocks API query and OAuth scope URI query are also data. These tests use synthetic local HTTP upstream and temporary dist only; no real OAuth/network/provider credential is used.

Four positive RED cases: login encoded returnTo, search encoded keyword, fixed upstream stock query byte preservation, OAuth callback encoded scope preservation without following its 302. A negative case independently keeps encoded slash/backslash and dot traversal pathname denial. Changing query handling must not weaken pathname validation or turn the server into a variable upstream proxy.

Original src/features/admin/AdminNewsFormPage.tsx lines 166–175 uses URL.createObjectURL(image) and revokeObjectURL for the selected uploaded image preview. Its img preview requires CSP img-src blob:; original src/features/admin/AdminNewsFormPage.tsx is the source reason to assert the image policy. The header assertion checks this necessary capability; actual browser image decode/display remains separately verified. It does not broaden script-src or arbitrary navigation.

Command: node --test clients/webview/full-tests/query-regression.test.mjs. Node builtin runner, no npm/browser dependency. All fixtures synthetic; no body/cookie/token is printed.

Actual initial sandbox run could not listen on loopback (EPERM); it was not counted as functional RED. Re-execution with approved local-network sandbox escalation reproduced four query failures (400 instead of 200/302) and missing blob image policy, while encoded-path denial passed. TAP totals include parent failure: pass 1, fail 6; five actual failing subtests; skip 0.
