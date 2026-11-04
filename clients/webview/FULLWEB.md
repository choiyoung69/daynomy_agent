# DAYNOMY 전체 WebView 클라이언트

기존 DAYNOMY React/TypeScript 화면을 `fullweb/`에 격리 복사했다. 새 UI를 다시 만든 것이 아니다. Android/iOS 기존 WebView 호스트가 사용하는 웹 origin은 그대로 `http://127.0.0.1:18082`이며 네이티브 특권 브리지는 추가하지 않는다.

```sh
npm --prefix clients/webview/fullweb ci --ignore-scripts
npm --prefix clients/webview/fullweb run build
node clients/webview/scripts/serve-full.mjs --port 18082 --api-origin http://127.0.0.1:18081
```

API는 별도로 실행 중인 실험용 Rust 서비스여야 한다. 프록시 구현/독립 검사 기록은 전체 실행 기록에서 확인한다. Vite 개발 모드도 loopback 18082와 같은 API 18081을 사용한다. 빌드 설정은 `.env`를 읽거나 환경변수 자격 증명을 클라이언트에 노출하지 않으며 Sentry 업로드를 실행하지 않는다. 원본 analytics/Sentry는 설정이 없으므로 비활성이다.

## 제공 화면

원본 포트폴리오·비회원 sessionStorage 거래 원장·계산·AI 분석·이력, 뉴스·키워드·시장 분석·통합 검색, 종목 콘텐츠·인물, 로그인·회원 닉네임·로그아웃·탈퇴, 피드백, 관리자 뉴스·인물·콘텐츠·피드백·종목 동기화, 서비스 안내를 재사용한다. UI 권한 가드와 원본 서버 쿠키/공유 refresh/CSRF 흐름을 유지한다. 실제 서버가 최종 권한을 결정한다.

원본에서 숨겨져 있던 투자 캘린더 컴포넌트를 `/investment-calendar`에 연결하고 헤더에 노출했다. 원본 `/portfolio/records`의 리그 이동은 `/` 포트폴리오 이동으로 변경했다. 리그 메뉴·라우트·소개·관리자 재집계 요청은 제거했다. `/league`, `/membership`, `/portfolio/publication`은 제공하지 않는다. F14 이메일 mock·UI·API는 가져오지 않았다. 일반 analytics 원본 테스트의 의존성인 순수 리그 telemetry sanitizer와 타입 파일 두 개만 보존하며 앱에서 해당 모듈을 호출하지 않는다.

원본 responsive CSS를 유지하고 viewport-fit/safe-area inset/dynamic viewport/모바일 입력 확대 방지를 보완했다. 거래 편집기의 읽기 검색·종가·환율 요청은 pagehide/visibilitychange에서 취소하고 pageshow/foreground에서 재조회한다. React 입력 초안과 수동 단가는 유지하며 변경 요청을 자동 재생하지 않는다. 프로세스 종료 뒤 입력 영구 복구를 보장하지 않는다.

## 근거와 검사

`experiments/webview/full/implementation/web/import-manifest.json`은 명시적으로 가져온 파일의 원본 SHA256와 복사 직후 SHA256, 제외 파일과 이유를 담는다. `original-delta.diff`는 복사본 변경을 원본에 대조하고 `source-hashes.json`은 검증 전달 시 파일 해시를 고정한다. 원본·기존 검색 파일럿·동결 인수 테스트·백엔드·다른 클라이언트는 수정하지 않았다.

KB에서 service-catalog와 기능별 문서, shared auth-storage/error-retry-cancel/ui-state-navigation/testing-migration 및 WebView 패키지를 읽었다. 규칙 적용은 다음과 같다.

| KB 규칙 | 적용 코드 |
| --- | --- |
| auth-session/account, auth-storage: 쿠키·CSRF·공유 refresh·서버 권한, 저장 수명 | 원본 `src/api/client.ts`, `src/auth/`, `features/pages/api.ts`, `account/MyPage.tsx`, `App.tsx` 재사용 |
| portfolio-ledger/calculation/analysis: 게스트/회원 구분, 저장·조회·수동 단가 | 원본 `features/portfolio/` 재사용, `PortfolioTransactionEditor.tsx` foreground 취소만 보완 |
| stocks-exchange, error-retry-cancel: 250ms·AbortSignal·늦은 응답·수동값 보존 | 원본 `features/stocks/`, editor effects + `hooks/useWebViewForeground.ts` |
| investment-calendar/news/content-search/content-people | 원본 각 feature API/컴포넌트와 App 라우트 연결 |
| feedback/administration: 공개 쓰기 CSRF·관리자 서버 검사 | 원본 `features/feedback/`, `features/admin/`; 제외 리그 recalc만 제거 |
| WebView/auth-and-storage: 동일 origin·특권 브리지 금지 | 동일 origin API 요청, 기존 호스트 보존; 서버 프록시는 별도 구현자 |
| ui-state-navigation/testing-migration | 기존 DOM/CSS·가드 보존, `webview.css`, lifecycle 회귀 검사; 웹/실서버/기기 결과 구분 |

`python3 scripts/check.py preflight`: 29/29 snapshot 일치, `python3 scripts/knowledge.py check`: 110/110 로컬 출처 일치. 외부 63개 pinned hash는 live 재조회하지 않았다. full-feature 준비 완료를 기존 stock-search-price READY로 대체하지 않았다.

구현자가 실행한 명령/실패:

- 초기 루트 `npm run typecheck`는 잘못된 작업 위치로 ENOENT; `npm --prefix clients/webview/fullweb`로 수정.
- 첫 typecheck는 원본 generic analytics 테스트의 순수 리그 모듈 의존성이 없어 실패; 해당 sanitizer/types 두 파일을 원본 그대로 추가해 해결.
- 첫 원본 unit 34/35: OAuth Vite proxy 계약 실패. loopback API/OAuth/callback proxy를 추가한 재실행은 35/35 통과.
- 원본 UI 39파일 384개 통과. JSDOM의 scrollTo/다른 문서 이동 미구현 메시지는 실제 브라우저 검증과 구분한다.
- production build/typecheck 통과. 원본 큰 JS chunk 경고는 유지한다.
- lifecycle 회귀 검사는 구현자가 추가한 검사이며 별도 동결 인수 테스트로 세지 않는다. 최종 결과는 `ui-final.log`에 기록한다.

리그/F14 전용 테스트 및 MyPage/Header/PortfolioAuth/adminStockSyncApi/AdminStockSyncPage의 혼합 리그 기대값 테스트는 원문 그대로 evidence `excluded-original-tests/`에 보존했다. 기준을 약화해 통과시키지 않았다. 그 혼합 파일의 비리그 기능 검증을 모두 실행했다고 주장하지 않는다. 허용 기능의 서버·브라우저 검증은 별도 검증자가 수행한다.

Google OAuth 화면과 로컬 provider fixture는 실제 Google 로그인 완료를 의미하지 않는다. 네이티브 외부 user-agent callback/쿠키 세션 공유, S3·AI·소셜 임베드·운영 데이터, iOS SDK 빌드·화면은 별도 미검증이다. 웹 빌드/단위 검사 결과만으로 전체 WebView 플랫폼 완료를 선언하지 않는다.

최종 구현자 검사: typecheck/build exit 0, 원본 unit 35/35, UI 40파일 385개(원본384 + 구현자 lifecycle1) exit 0. full KB 전달자료 context SHA256 `c8b40be656ddba97024beabd031a33b1084482819b86d2b2a5ab10c70664d821` 및 문서36개 해시를 확인했다. sync-jobs/transactions-concurrency 규칙은 원본 관리자 API/CSRF·항목별 오류·명시 재시도와 원장 저장 흐름을 보존하며 서버 원자성을 프론트 결과로 보증하지 않는다. React best-practices 검토는 effects cleanup/안정적 primitive 의존성/원본 label·권한 가드 보존을 확인했다.
