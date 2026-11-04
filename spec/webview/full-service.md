# DAYNOMY WebView 전체 웹 화면 확장

2026-10-28 사용자 요청: 검색 파일럿에 한정하지 않고 빠르게 WebView 코드를 구현한다. Android native/iOS native/React Native/Flutter/WebView는 각각 별도 구현 방식이며 이 대화는 WebView 버전을 담당한다. 다른 대화의 clients/android, clients/ios, clients/flutter 및 app/ 수정은 건드리지 않는다.

## 구현 전략

reference/2026-DAYNOMY-dev/frontend는 읽기 전용 근거다. 원본 .env·자격 증명·운영 데이터·서버는 사용하지 않는다. src/public/index.html/package.json/package-lock.json/TypeScript 설정 및 비리그 원본 테스트를 clients/webview/fullweb/로 명시적 복사하고 복사 전후 파일 해시를 기록한다. 원본 React/TypeScript UI를 재사용해 화면·업무 규칙을 보존하고, 모바일 safe-area/입력/스크롤 및 WebView host lifecycle을 연결한다. 기존 pilot 및 frozen-tests는 그대로 보존한다.

리그와 F14 이메일 알림·배포는 기존 서비스 범위 밖이다. 리그 메뉴/라우트/로그인 유도 등 현재 백엔드에서 동작하지 않는 노출은 제거하거나 명확한 미지원 경로로 처리한다. 리그 자료 import가 비리그 컴포넌트에 필요한 경우 재사용 범위/비활성 여부를 기록한다. 포트폴리오·뉴스/상세/검색·종목 자료·인물·로그인·마이페이지·피드백·관리자 콘텐츠와 자산 동기화·서비스 안내 화면을 연결한다. 관리자 UI는 서버 권한 검사를 유지하며 화면에서 권한을 위조하지 않는다. 로그인은 기존 서버 쿠키/CSRF/refresh 계약을 유지하고 실제 Google와 로컬 제공자 검증은 구분한다. 네이티브 외부 OAuth user-agent·콜백·쿠키 공유는 호스트별 실제 검증 전 완료라고 하지 않는다.

## 제공 및 보안

신규 clients/webview/scripts/serve-full.mjs CLI: --port 18082 --api-origin http://127.0.0.1:18081 --dist <optional absolute directory>. 기본 dist는 clients/webview/fullweb/dist. 127.0.0.1 bind, 고정 loopback API origin만 허용한다. /api/ 요청은 GET/POST/PUT/PATCH/DELETE/OPTIONS와 본문·쿠키·CSRF헤더·상태·여러Set-Cookie를 보존해 스트리밍 프록시한다. /oauth2/ 및 /login/oauth2/의 서버 redirect도 보존하며 임의 외부 proxy 금지. 원문 본문/쿠키/토큰을 로그에 남기지 않는다.

빌드된 정적 assets/public 파일은 dist 내부만 제공, 경로 탈출·.env/.git/소스 노출·임의 URL·잘못된 percent·encoded slash/backslash·NUL 거절. 알려진 UI 경로의 GET/HEAD HTML 탐색만 index.html fallback, 없는 asset/API는 원상태404. HTML/JS/CSS/MIME 및 보안헤더, no-store 적용. POST 본문을 조용히 버리거나 성공으로 위장하지 않는다. backend unavailable은502.

Android/iOS 기존 WebView host는 같은 origin18082를 사용해 전체 앱을 띄운다. 기존 native policy frozen13 기준을 수정하지 않는다. host 변경이 실제 필요하면 별도 테스트 기준을 먼저 작성한다. 브리지 특권/HttpOnly 토큰 추출/SSL 우회/임의 URL 허용 없음. fullweb은 기존 디자인을 보존한다. 원본 모니터링/분석 SDK는 credential 없는 검증 환경에서 외부 호출하지 않도록 구성하고 production 실자격 증명을 복사하지 않는다.

## 지식베이스와 검증 역할

knowledge/wiki/projects/daynomy/service-catalog.md와 기능별 auth-session/account/portfolio-ledger/portfolio-calculation/portfolio-analysis/investment-calendar/news/content-search/content-people/feedback/administration/stocks-exchange, shared auth-storage/error-retry-cancel/ui-state-navigation/testing-migration 및 WebView 패키지를 읽고 규칙→적용 파일 매핑을 기록한다. source hash check를 먼저 수행한다. 기존 플랫폼 READY는 stock-search-price에 한정되므로 전체 기능 준비 완료로 재사용하지 않는다. 전체 확장 구현에 필요한 버전/계약/명세를 여기 고정하고 전달 자료 manifest를 별도로 생성한다.

테스트 작성 서브에이전트가 먼저 spec+원본에서 serve-full 계약과 화면 smoke/경계 테스트를 작성하고 실제 red와 SHA256을 고정한다. 구현 서브에이전트는 고정 테스트를 바꾸지 않고 전체 웹 복사·연결 및 서버를 구현한다. 별도 검증자가 실제 빌드·고정 검사·브라우저·가능한 Android WebView와 Rust/임시DB 요청을 실행한다. 처음에는 비리그 UI 전체 라우트 및 비회원 포트폴리오 편집/원장, 뉴스/검색, 피드백 쓰기, 세션/권한 경계를 우선한다. 원본 테스트를 실행했다고 실제 Google/S3/AI/운영검증을 주장하지 않는다. 코드 구현/화면 로딩/실제 서버 기능/외부 제공자/iOS 실행은 구분한다.
