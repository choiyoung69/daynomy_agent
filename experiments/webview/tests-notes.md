# WebView 독립 테스트 작성 기록 — 2026-10-28

역할은 테스트 작성 전용이다. 구현 파일·기존 Android 파일·지식베이스는 변경하지 않았다. 부모 조정자가 승인한 별도 작업 `scripts/test_knowledge.py`의 KB regression fixture 보강은 아래에 구분한다.

## 기준과 인터페이스

- `spec/webview/README.md`, `knowledge/wiki/projects/daynomy/stock-search-price.md`, WebView platform 및 types-and-json/async-and-cancellation/state-and-navigation/errors-and-transactions/modules-and-testing 패키지를 읽었다.
- 원본 `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts`, `types.ts`, `features/portfolio/components/PortfolioTransactionEditor.tsx`를 직접 대조했다.
- market.ts 인터페이스는 명세 기준. 호스트 정책은 부모가 승인한 NavigationPolicy 계약 사용. Kotlin package `com.daynomy.webview`, NavigationDecision INTERNAL/EXTERNAL/BLOCK; Swift NavigationDecision internalPage/externalBrowser/block.
- HTTP: `node clients/webview/scripts/serve.mjs --port <port> --api-origin http://127.0.0.1:<port>`; root HTML, `/dist/market.js`, `/api/` 프록시. 독립 fixture 서버는 임시 포트·합성 종목·합성 쿠키만 사용한다.
- 실제 DOM 테스트는 설치된 Chrome headless+CDP를 구동한다. search input의 accessible label, ETF/전체 버튼, 종목 버튼, 단가 label, 상태/날짜/로그인 안내, text 렌더링, lifecycle을 실제 DOM에서 검사한다. 가짜 DOM이나 소스 문자열 비교가 아니다.

## 원본의 미묘한 의미와 pilot 결정

- isStockMarket는 `String(value)`로 검사하므로 toString으로 KOSPI가 되는 값도 원본처럼 허용한다. currency는 응답 guard에서 검사하지 않고 `??` fallback만 적용한다. `.US` 대소문자는 원본 그대로다.
- API는 안전 양의 ID, 유한 number, 문자열 날짜를 검사한다. 날짜 문법·양수 가격은 API decoder가 검사하지 않는다.
- 편집기는 양수 가격만 자동 입력하고 수동 삭제도 dirty이다. 비양수 실패 시 날짜 null은 이번 pilot 명세가 명시한 동작이다. 원본은 날짜를 먼저 설정하고 비양수 오류를 발생시키므로 이 부분은 원본과 완전히 동일하다는 주장을 하지 않는다.
- 검색은 JS trim/250ms(단위 테스트에서는 짧은 주입값)/취소/로컬 유형 필터다. 테스트 mock API는 AbortSignal을 무시한 이전 성공·실패를 의도적으로 완료하여 stale finally까지 검증한다.
- 공개 pilot은 인증 갱신을 하지 않는다는 명세에 따라 401에서도 숨은 refresh/retry가 없어야 한다. 원본 공통 request의 refresh 동작을 복제한 것으로 보고하지 않는다.

## 실제 red와 고정

Node v22.23.1. TypeScript compiler 경로 `.local/knowledge-sdks/typescript/package/bin/tsc` 확인.

1. `node --check`로 market.test.mjs, host-policy.test.mjs, http-browser.test.mjs 각각 exit 0.
2. `npm run build` (clients/webview/web): exit 2, TS18003 구현 src 부재.
3. `npm run test:contracts`: exit 1, dist/market.js ERR_MODULE_NOT_FOUND.
4. `node --test clients/webview/tests/host-policy.test.mjs`: exit 1, Android/Swift 정책 소스 부재로 2 실패.
5. `node --test clients/webview/tests/http-browser.test.mjs`: exit 1, 서버 구현 부재로 HTTP/Chrome DOM 2 실패.

구현 부재 red이며 테스트 JavaScript 문법 오류가 아니다. 구현 stub은 만들지 않았다. 상세 출력/실행 인자/종료코드는 `clients/webview/tests/red/`에 보존했다. 테스트/설정/red 기록 13 파일 SHA256을 `experiments/webview/frozen-tests.json`에 고정했다. 이 manifest 자체의 고정 시점 SHA256은 `dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9`다. 구현자에게 완료와 불변 범위를 통지한 뒤 구현을 시작하도록 했다.

## 검증의 한계

- Kotlin/Swift harness는 실제 구현 정책 함수를 컴파일하여 실행하나 WebView/WKWebView UI 실행 증거는 아니다.
- Chrome DOM 검사는 Android/iOS 기기 UI·키보드·cookie store·회전/프로세스 종료 복원을 대체하지 않는다.
- HTTP fixture 검사는 Rust/DB 실행 증거가 아니다. 독립 검증 역할이 실제 Rust/로컬 DB 및 가능한 호스트 build/device를 별도 수행해야 한다.
- 이 기록 시점에는 구현 후 테스트·실제 WebView 검증을 실행하지 않았다. 후속 검증 결과는 별도 기록한다.

## 별도 KB regression 요청

부모 조정자가 `scripts/test_knowledge.py` 쓰기 범위를 추가 승인했다. metadata가 새 `spec/webview/README.md` 링크를 참조하므로 격리 fixture에 해당 subtree를 복사한다. 준비됨 기대값은 stock-search-price의 Android와 WebView만 허용하고, 다른 기능 auth-session은 두 플랫폼 모두 scope guard로 차단되는지 검사한다. 이는 테스트 기준 약화가 아니라 지식 준비 범위와 링크 fixture를 현재 승인 계약에 맞춘 것이다. 기존 Android 파일은 변경하지 않았다.

KB regression 실제 실행: `python3 -m unittest discover -s scripts -p 'test_knowledge*.py'` exit 0, 29 tests, 6.751s. 이 실행은 WebView 구현 검증과 별개다.
