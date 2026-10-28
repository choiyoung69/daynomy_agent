# Native session contract, independently checked

Observed 2026-10-28T09:32Z. Direct source hashes are in `auth-contract-hashes.json`. Source-backed, not real Google/device-login proof.

- External browser start: GET `/api/auth/mobile/start?code_challenge=...&state=...`. Challenge is SHA256(verifier), unpadded base64url exactly43 chars. App state32–128 chars letters/digits/`-_`. Verifier43–128 letters/digits/`-._~`, memory only.
- Success fixed callback: `org.daynomy.app://auth/callback?code=...&state=...`. Error callback: same fixed location, `error=oauth_failed&state=...`, only when server signed OAuth state verifies. Client must check scheme/host/path and matching app state; callback URLs contain no access/refresh tokens.
- Exchange: POST `/api/auth/mobile/exchange`, Content-Type application/json, body `{code,codeVerifier}`. Success204 no body. Set-Cookie access_token Path=/ and refresh_token Path=/api/auth, HttpOnly, SameSite=Lax, Secure unless local config false. Origin/path/expiry-aware ephemeral URLSession cookie storage required; browser cookies aren't automatically app cookies.
- Code is60s, hashed in DB, consumed once inside transaction with PKCE and ACTIVE-member verification. Malformed fields400, expired/replay/wrong verifier401, wrong MIME415. No login redirect parameter; fixed callback is server controlled.
- GET `/api/auth/csrf` yields `{headerName:"X-XSRF-TOKEN",parameterName:"_csrf",token:...}` and XSRF-TOKEN cookie Path=/. POST refresh/logout, PATCH/DELETE profile and public calculate/calendar/feedback require same cookie plus token header. Mobile exchange is exemption; unauthenticated guest analysis has its separate existing exception.
- GET `/api/users/me`: id,email,name(nullable),nickname,role. PATCH same endpoint `{nickname}`. DELETE same endpoint deletes current membership. POST `/api/auth/refresh` rotates cookies; POST `/api/auth/logout` clears cookies. Never assume access alone can refresh without refresh-path cookie and CSRF.
- Existing OAuth config must supply actual client credentials/server redirect `/login/oauth2/code/google`; no native client ID invented. Full Xcode/runtime absent; ASWebAuthenticationSession syntax/UI and real callback scheme are unverified until native build.

Source excerpts inspected: service_auth.rs mobile_start/mobile_exchange/mobile_failure, cookie_header/profile/handle; main.rs private_request CSRF exemptions and handle csrf response; csrf.rs token matching. Backend unchanged by verifier.
