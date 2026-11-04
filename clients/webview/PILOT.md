# DAYNOMY WebView validation pilot

종목 검색 → 최근 저장 종가 조회 → 수동 거래 단가 입력을 Android/iOS 공통 웹 화면에서 실행한다. 로그인·거래 저장은 포함하지 않는다. 명세는 `../../spec/webview/README.md`, 호스트 실행법은 `HOSTS.md`를 따른다.

## 웹 실행

저장소 루트에서:

```sh
npm --prefix clients/webview/web run build
node clients/webview/scripts/serve.mjs --port 18082 --api-origin http://127.0.0.1:18081
```

웹 주소는 http://127.0.0.1:18082, Android 에뮬레이터는 http://10.0.2.2:18082 다. Rust 실험 백엔드를 별도 준비해야 한다. 서버는 정적 HTML/CSS/compiled ESM과 `/api/` GET/HEAD만 제공하며 고정된 loopback API origin으로 프록시한다. 서버는 127.0.0.1에만 bind하고 에뮬레이터의 host loopback alias로 접속한다. 이 서버는 로컬 검증용이다. cookie는 같은 origin 요청에서 backend로 전달하며 로그에 출력하지 않는다. 응답 cache는 비활성화한다.

## 검사

```sh
npm --prefix clients/webview/web test
node --test clients/webview/tests/http-browser.test.mjs
node --test clients/webview/tests/host-policy.test.mjs
```

테스트 작성자가 구현 전 실행해 실패를 확인한 기준과 설정은 `experiments/webview/frozen-tests.json`에 SHA256으로 고정했다. 구현자는 테스트와 설정을 수정하지 않는다. 웹 단위/Chromium DOM/호스트 순수 정책/실제 WebView 기기 실행은 각각 별도 근거다. iOS WKWebView의 빌드·실행에는 full Xcode가 필요하다.

## 데이터와 수명

API decoder는 원본 stocks API의 일곱 market과 safe integer/finite price 검사를 보존한다. currency는 원본처럼 nullish fallback만 적용하고 알 수 없는 통화는 단가 label에 표시하지 않는다. 날짜 문자열은 변환하지 않는다. 단가 직접 입력과 삭제는 숫자로 파싱하지 않는다. 재조회 결과도 수정한 입력을 덮지 않는다.

이전 검색/선택의 응답은 AbortSignal과 요청 세대로 무효화한다. pagehide/visibilitychange, host의 `daynomy:active` boolean 이벤트로 요청을 중단하고 foreground 복귀 시 현재 조회만 한 번 재개한다. 초안은 현재 JS 메모리에만 보존된다. 프로세스 종료/새로고침 후 수동 단가의 영구 복원은 제공하지 않는다. 특권 JavaScript bridge와 토큰 저장은 없다.
