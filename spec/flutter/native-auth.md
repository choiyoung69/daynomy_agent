# Flutter 네이티브 인증 확장 계약

2026-10-28 사용자 승인: 전체 사용자 앱과 네이티브 회원 로그인을 위한 서버 확장.
기존 웹 OAuth·쿠키·CSRF 계약을 보존하며, 아래 경로만 추가한다.
테스트 작성 → 별도 구현 → 별도 검증 순서를 지킨다.

## 외부 브라우저와 일회용 코드

1. 앱이 암호학적 난수로 RFC 7636 verifier(43–128자의 영문/숫자/`-._~`)와
   state(32–128자의 영문/숫자/`-_`)를 생성한다. verifier는 앱 메모리에만 둔다.
2. 외부 user-agent로 `GET /api/auth/mobile/start?code_challenge=...&state=...`를 연다.
   challenge는 SHA-256(verifier)의 padding 없는 base64url(43자)이다.
   서버는 이 값들을 기존 서명된 OAuth state에 결합하고 기존 Google OIDC 검증을 사용한다.
3. Google 검증 성공 시 DB에 코드 해시·회원 ID·challenge·만료를 보관한다.
   코드 유효기간은 60초이며 단 한 번 교환할 수 있다. 콜백은 고정
   `org.daynomy.app://auth/callback?code=...&state=...`다.
   요청이 제공한 redirect 주소는 사용하지 않는다. access/refresh 토큰을 URL에 넣지 않는다.
4. 앱은 callback scheme/host/path와 state가 일치하는지 확인하고
   `POST /api/auth/mobile/exchange`에 `{code,codeVerifier}`를 전송한다.
   서버는 PKCE·유효기간·재사용·회원 ACTIVE 상태를 검증한 뒤 기존 access/refresh 쿠키를 발급한다.
   성공은 본문 없는 204다. 이 경로는 브라우저 쿠키에 의존하지 않는 PKCE 교환이므로
   이 경로에 한해서 CSRF 예외다. 다른 쓰기 경로의 CSRF 검증은 유지한다.

잘못된 필드/시작 파라미터는 400, 잘못된·만료·재사용 코드/검증자는 401로 처리한다.
동시 교환은 정확히 한 요청만 성공해야 한다. 탈퇴한 회원은 발급할 수 없다.
중간 실패가 refresh 토큰 발급이나 코드 소비의 부분 저장을 남기지 않도록 트랜잭션으로 처리한다.
서명된 모바일 state를 확인할 수 있는 OAuth 오류는 같은 고정 콜백에 error와 state만 전달한다.
검증되지 않은 state로 커스텀 URL에 redirect하지 않는다.

## 앱 저장과 플랫폼

Android/iOS는 외부 인증 세션 플러그인을 사용한다. Google 로그인을 내장 WebView로 대체하지 않는다.
네이티브 HTTP 쿠키는 origin/경로/Secure/만료를 지키는 메모리 jar에 두며, 앱 종료 시 소멸한다.
이 선택은 영구 로그인 구현을 의미하지 않는다. 브라우저 세션과 앱 세션을 동일시하지 않는다.
웹은 기존 같은 origin의 Google redirect와 브라우저 HttpOnly 쿠키를 사용한다.
일반 설정/로그/실행 증거에 코드·verifier·쿠키·토큰·실제 사용자 정보를 남기지 않는다.
API는 HTTPS를 기본으로 하고, 개발 중 loopback/Android emulator의 명시적 로컬 주소만 HTTP를 허용한다.

## 검증 범위

공식 Google 환경과 실제 기기 인증은 자격 증명과 기기 준비에 따라 따로 보고한다.
로컬 RSA/JWKS 제공자의 HTTP/DB 성공을 실제 Google 계정 로그인 성공으로 표현하지 않는다.
기존 서버 동작 및 피드백 회귀를 함께 확인하고, 테스트·후보 소스 해시를 기록한다.
