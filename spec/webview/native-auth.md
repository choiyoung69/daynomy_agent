# Full WebView 외부 OAuth 세션 연결 보완 계약

2026-10-28, 테스트 작성 역할이 backend/KB/원본을 읽고 고정한 추가 계약이다. 기존 full-service/pilot 명세와 고정 테스트는 수정하지 않는다. backend와 다른 클라이언트는 읽기 전용이다.

## 근거와 범위

- `app/src/service_auth.rs`의 `mobile_start`, `mobile_failure`, `mobile_exchange`, `oauth_callback` 및 `cookie_header`를 대조했다. 구현 시점 소스 해시는 테스트 manifest에 기록한다. backend의 최신 다른 변경을 본 역할이 작성했다는 의미는 아니다.
- `knowledge/wiki/projects/daynomy/auth-session.md`, `knowledge/wiki/shared/auth-storage.md`, `knowledge/wiki/platforms/webview.md`, `knowledge/wiki/packages/webview/auth-and-storage.md`를 읽었다. 외부 user-agent, state/PKCE, 쿠키 저장소 구분, JS 토큰 추출 금지, 실제 호스트 검증 구분을 적용한다.
- 원본 `reference/2026-DAYNOMY-dev/frontend/src/features/pages/components/LoginPage.tsx`의 `/api/auth/google` 로그인 링크를 네이티브 호스트에서 가로챈다. 기존 웹 쿠키/CSRF/refresh 방식은 유지한다.

## backend 현행 계약

1. `GET /api/auth/mobile/start?code_challenge=<S256>&state=<app-state>`는 challenge가 base64url 43자, state가 base64url 32~128자일 때 서버 OAuth를 시작한다. 서버 자체 state/nonce/verifier 및 600초 만료와 replay 방어는 별개다. 클라이언트는 `code_challenge_method=S256`을 추가해 의미를 명시할 수 있으나 서버는 현재 필수로 검사하지 않는다.
2. 성공 시 `org.daynomy.app://auth/callback?code=<one-use-code>&state=<app-state>`로 이동한다. 서버 code는 base64url 32~128자, 발급 후 60초 유효하며 DB에는 해시로 저장한다. 실패는 같은 callback의 `error=oauth_failed&state=...`이다.
3. `POST /api/auth/mobile/exchange`, `Content-Type: application/json`, body `{"code":...,"codeVerifier":...}`. verifier는 43~128자의 RFC7636 unreserved ASCII이다. 올바른 code/PKCE/활성회원이면 실제 서버는 204와 두 `Set-Cookie`를 반환한다. 틀린 PKCE/만료/replay는 401, 잘못된 입력은 400, content type 오류는 415다. 서버는 행 잠금 후 확인·삭제하여 동시 one-use를 보장한다.
4. 쿠키는 `access_token` Path `/`, `refresh_token` Path `/api/auth`, HttpOnly, SameSite=Lax, 양수 Max-Age다. 운영 Secure 설정을 유지한다. bearer 토큰 반환이나 JS 전달은 없다.

## 순수 정책과 상태기계 API

신규 소스는 Android `clients/webview/android-full/app/src/main/java/com/daynomy/webview/NativeAuthSession.kt`, Swift `clients/webview/ios-full/DaynomyWebView/NativeAuthSession.swift`다. 기존 NavigationPolicy는 수정하지 않는다. Foundation/JVM에서 독립 실행 가능해야 한다.

- `NativeAuthSession(trustedOrigin, debug)`는 HTTPS 단일 origin 또는 debug의 loopback HTTP만 허용한다. 경로/쿼리/fragment/userinfo를 가진 설정은 거절한다.
- `begin(navigationURL, sourceDocumentURL, httpMethod, isMainFrame, userActivated, state, verifier, nowMillis) -> AuthLaunch?`. Swift는 이 이름의 인자 label을 사용하며 Kotlin은 같은 순서다. 정확한 trusted `/api/auth/google` GET, trusted top document, 주프레임과 사용자 행동만 시작한다. query/fragment/encoded path/유사 경로/외부 origin은 거절한다. 진행 중 두 번째 begin은 거절한다. state/verifier 유효성 및 시각 범위를 검사하고 호스트가 제공한 cryptographic random 값만 저장한다. `authorizationURL`은 같은 origin의 `/api/auth/mobile/start`이며 S256 challenge와 state를 담는다. verifier를 URL에 넣지 않는다. 호스트는 Android SecureRandom, iOS SecRandomCopyBytes 등 OS 난수를 쓰며 고정값/UUID나 JS payload로 대체하지 않는다.
- `receive(callbackURL, nowMillis) -> AuthExchange?`. scheme `org.daynomy.app`, host `auth`, exact unencoded path `/callback`, userinfo/port/fragment 없음. query는 decode-once 뒤 중복/알 수 없는 key/잘못된 percent encoding/빈 값/비정상 문자/성공·실패 혼합을 거절한다. state를 constant-time 비교한다. 정상 code+state 또는 error=oauth_failed+state 두 항목만 허용한다. 잘못된/다른 state의 callback은 정상 진행 세션을 소모하지 않는다. 일치하는 error는 세션을 종료한다. begin 후 600,000ms 경계부터 만료되며 역행 시각도 거절하고 종료한다. 성공 code는 한 번만 exchange 계획으로 전환하며 같은 callback의 중복은 거절한다.
- `AuthExchange`는 `exchangeURL`, `code`, `codeVerifier`, `requestId`를 네이티브 호출자에게만 제공한다. exact trusted `/api/auth/mobile/exchange`로만 POST하며 HTTP redirect 자동 추적을 끈다. JSON은 라이브러리 인코더로 생성한다.
- `complete(requestId, status, responseURL, setCookieHeaders, nowMillis) -> AuthCookiePlan?`. 요청 ID가 현재 exchange와 일치하고 정확한 exchange URL 및 204, callback 수락 후 60,000ms 미만/전체 수명 안에서만 성공한다. 302/잘못된 origin/path/query/fragment와 stale ID는 쿠키를 설치하지 않는다. 쿠키는 access/refresh 각각 하나, 올바른 Path, HttpOnly, SameSite=Lax, 양수 Max-Age, release에서 Secure가 필요하다. Domain은 없거나 정확한 trusted host만 허용하며 하위/상위/다른 host를 거절한다. 중복 cookie/속성 및 CR/LF, 잘못된 쿠키는 거절한다. 둘 중 하나라도 빠지면 설치 계획 전체가 실패한다. 동일 완료는 한 번만 받아들인다.
- `AuthCookiePlan`의 `originURL`, `reloadURL`, `setCookieHeaders`는 네이티브 내부 전달용이다. URL은 trusted origin과 trusted `/`다. OS cookie store에 모든 Set-Cookie 속성을 보존하여 저장 완료를 기다린 후 `/`를 reload한다. JS/로그에 cookie/code/state/verifier 원문을 전달하지 않는다. 실패/취소/expired는 일반 로그인 실패 UI로 처리한다. `cancel()`은 pending 작업을 무효화해 늦은 callback/응답이 로그인 상태를 부활시키지 못하게 한다. 호스트의 비동기 cookie 설치/취소 경합도 별도로 방어한다.

## 호스트 연결 및 검증 경계

Android는 callback intent-filter의 exact scheme/host/path와 onCreate/onNewIntent를 연결하고 외부 브라우저를 사용한다. iOS는 URL scheme registration 및 openURL/scene callback 또는 시스템 authentication session을 연결한다. 앱의 다른 URL/기존 외부 링크 허용 범위를 넓히지 않는다. 한 번의 auth 흐름 동안만 native pending 상태를 보존하며 프로세스 종료 뒤 임의 복원하지 않는다.

Android CookieManager와 WKWebsiteDataStore.httpCookieStore는 웹 페이지 JS 브리지와 구분한다. HttpOnly를 JS로 읽거나 document.cookie/evaluateJavaScript로 로그인 토큰을 주입하지 않는다. 보안 속성을 제거하여 성공으로 만들지 않는다. sourceDocumentURL은 host가 관찰한 top document/frame 정보이며 메시지의 origin 문자열을 신뢰하지 않는다.

새 frozen Kotlin/Swift 검사는 동일한 callback·PKCE·시간·replay·cookie 정책을 실행한다. missing source의 실제 RED 후 구현을 넘긴다. 순수 검사 통과는 OS 브라우저→callback→HTTP→OS 쿠키→WebView 회원 상태 확인을 대체하지 않는다. Android 기기 및 로컬 OIDC/Rust DB 왕복은 별도 검증자가 실행한다. Xcode가 없는 호스트의 Swift 검사만으로 iOS 빌드·실행 완료라고 하지 않는다. 실제 Google 운영 로그인은 별도 미검증이다.
