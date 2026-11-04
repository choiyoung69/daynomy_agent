# Full WebView local server

Build `clients/webview/fullweb` first, then run from the repository root:

```sh
node clients/webview/scripts/serve-full.mjs --port 18082 --api-origin http://127.0.0.1:18081
```

Optional `--dist /absolute/build/directory` supports isolated fixture builds. Node core modules only; binds 127.0.0.1. API origin accepts explicit loopback HTTP(S) only, without credentials, query or extra path. This is a local development server; TLS release hosting is not implemented here.

`/api/`, `/oauth2/` and `/login/oauth2/` stream requests and responses, preserving CRUD method, query, request bytes, Cookie, CSRF headers, upstream status, Location and separate Set-Cookie headers. It never follows OAuth redirects. Connection hop headers are removed, including nominated fields. Client disconnect cancels the upstream request; cancellation does not imply rollback of server mutations. No retry of mutations is performed. Inactivity timeout is 30 seconds; connection failures return 502.

Origin is forwarded unchanged. For the real local Rust fixture set `APP_CORS_ALLOWED_ORIGIN=http://127.0.0.1:18082` (or the actual frontend origin). The backend default localhost:5173 does not match this server. Cookie Secure/HttpOnly/SameSite/domain/path and CSRF policies remain backend-owned; this proxy neither rewrites them nor extracts tokens. Real Google authentication, external user-agent callback/cookie sharing and Android/iOS host sessions require separate verification.

Static files resolve inside the canonical dist root. Dot segments, encoded separators, malformed encoding, dotfiles, source files/maps, source directories and escapes through symlinks are rejected. Only known nonleague UI routes have HTML GET/HEAD navigation fallback. Missing assets and API errors never become SPA HTML. Responses use no-store, nosniff and CSP. Original React inline styling, HTTPS images/media/frames, and exact X/Threads embed script hosts are permitted; external-provider rendering and native host navigation policy compatibility are unverified.

Knowledge application: shared/auth-storage and webview/auth-and-storage → untouched cookies/CSRF/Origin and no privileged bridge; shared/error-retry-cancel and webview/async-and-cancellation → stream cancellation without mutation retry; shared/ui-state-navigation → explicit nonleague fallback route set; shared/testing-migration and webview/modules-and-testing → fixture HTTP evidence distinct from real backend/OS/provider validation. Original frontend src/api/client.ts supplies refresh/CSRF behavior; vite.config.ts supplies the three proxy prefixes. Original nginx broad SPA fallback is narrowed to the full-service security contract.

Frozen contract: `node --test clients/webview/full-tests/server-contract.test.mjs`. Loopback listening requires host execution when sandbox reports EPERM. Evidence and implementation hashes live in `experiments/webview/full/implementation/server/`.
