# Android 30분 핵심 증분 계약

작성 기준: 2026-10-28. 사용자가 승인한 30분 범위에서 기존 Rust 서버와 연결하는
회원 인증·계정·포트폴리오 원장을 우선한다. 별도 테스트 작성 → 빈 구현 실패 확인·해시 고정 →
별도 구현 → 독립 검증을 따른다. 기존 플랫폼·서버를 수정하지 않는다.

## 먼저 읽은 로컬 근거

- `knowledge/wiki/projects/daynomy/{auth-session,account,portfolio-ledger,portfolio-calculation}.md`
- `knowledge/wiki/packages/android-kotlin/{auth-and-storage,types-and-json,numbers-and-money,errors-and-transactions,async-and-cancellation}.md`
- `spec/flutter/native-auth.md`, `app/src/service_auth.rs`, `app/src/service_portfolio.rs`, `app/src/main.rs`, `app/src/csrf.rs`
- 기존 Android transport·모델·JVM/HTTP/Compose 테스트. 웹 자료는 사용하지 않았다.

## 공유 Kotlin 경계

`SessionTransport : HttpTransport`는 `request(method: String, path: String, jsonBody: String? = null): String`을
제공한다. `SessionHttpTransport(baseUrl)`는 이 경계를 구현하고 `clearSession()`을 제공한다.
`NativeLogin(transport, baseUrl)`은 `begin(): String`, `suspend complete(callbackUrl: String)`을 제공한다.
`AccountClient(transport)`는 `me`, `updateNickname`, `logout`, `delete`를 제공한다.
프로필은 id/email/name(nullable)/nickname/role이다. 필수 ID는 JSON 정수이며 양수·웹 안전정수 범위를 지킨다.
`PortfolioClient(transport)`는 `holdings`, `createTransaction`, `updateTransaction`, `deleteTransaction`,
`histories(from,to)`, `performance(from,to)`, `calculate`를 제공한다. DTO를 성급하게 고정하지 않고
JSON 객체/배열을 사용하므로 통과한 테스트는 전체 DTO 의미 검증을 보증하지 않는다.
JSON 숫자의 원문은 유지하며 Double 왕복·통일된 2자리 반올림을 하지 않는다.

## 인증·오류

- 외부 브라우저만 사용한다. verifier는 메모리의 암호 난수 43–128자, challenge는 SHA256+base64url 무패딩이다.
  state는 별도 난수이며 callback `org.daynomy.app://auth/callback`의 scheme/host/path/state를 확인한다.
  중복 code/state와 재사용 callback은 교환하지 않는다. URL에 verifier·쿠키·토큰을 넣지 않는다.
- mobile/exchange만 CSRF 예외다. 다른 쓰기에는 `/api/auth/csrf`에서 받은 XSRF-TOKEN 쿠키와
  X-XSRF-TOKEN header를 함께 보낸다. origin/path/Secure/만료를 지키는 메모리 cookiejar를 사용한다.
  refresh_token의 `/api/auth` 경로를 존중한다.
- 동시 401은 단일 refresh를 공유하며 원 요청은 한 번만 재시도한다. 일반 네트워크 오류의 거래 재전송은 금지한다.
  로그아웃/탈퇴/clearSession 뒤 늦은 응답은 쿠키나 화면의 회원 데이터를 부활시키지 않는다.
- 서버 업무 오류의 status/code를 보존한다. 전송한 거래의 응답 유실은 결과 불명이며 실패 확정이나 성공으로 만들지 않는다.
  화면은 재조회 안내를 제공하고 중복 제출을 막는다. 기존 테스트 전체를 약화하지 않는다.
- HTTPS 기본이며 명시된 로컬 loopback/emulator 주소만 개발 HTTP를 허용한다. API origin 이탈 경로는 거절한다.

## 기존 Rust 원장

회원 경로는 `/api/portfolio`와 `/api/portfolio/{transactions,histories,performance}`를 사용한다.
생성은 assetId/type(BUY|SELL)/quantity/unitPrice/fee/tax/tradeDate 및 필요 exchangeRate를 전송한다.
PATCH는 원 거래의 assetId/type을 바꾸지 않는다. 생성·수정 결과는 transactionId/holding(nullable)/totalRealizedProfitLoss다.
histories는 envelope 없는 JSON 배열이며 historyId를 사용한다. 초과 매도는 서버 오류와 원장 불변을 확인한다.
수정·삭제 뒤 조회로 실제 효과를 확인한다. calculate는 공개지만 CSRF 검사가 있다.

## 증거와 완료 범위

- `Android30SessionContractTest`: CSRF·cookie 경로·singleflight·logout 세대·비재전송·origin 제한.
- `Android30CoreClientContractTest`: PKCE·callback·회원 모델·원문 소수·거래 경로·history 배열·응답 형태.
- `Android30CoreBackendTest`: 필수 환경이 없으면 실패하며 skip/메모리 대체를 하지 않는다.
  테스트용 코드와 verifier는 환경으로 주입하고 로그에 출력하지 않는다.
- Android 기기의 Compose 테스트는 JVM 검사를 대체하지 않는다. 실제 Google 계정 로그인은 로컬
  PKCE fixture/MockWebServer/가짜 공급자의 성공과 구별한다.
- 30분 내 검증되지 않은 UI/영속저장/Google 실계정/부가 기능은 완료로 세지 않는다.
