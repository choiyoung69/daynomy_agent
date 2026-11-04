# DAYNOMY WebView

직접 실행·수동 확인·Android 설치·자동 검사는 [TESTING.md](TESTING.md)를 따른다.

전체 비리그 React·TypeScript 웹 화면은 `fullweb/`, Android WebView 호스트는 `android-full/`, iOS WKWebView 호스트는 `ios-full/`에 있다. 별도 Android/iOS 네이티브 앱과 구분한다.

## 전체 화면 실행

```sh
npm --prefix clients/webview/fullweb ci --ignore-scripts
npm --prefix clients/webview/fullweb run build
node clients/webview/scripts/serve-full.mjs --port 18082 --api-origin http://127.0.0.1:18081
```

API 주소는 실제 실행 중인 실험용 Rust 백엔드에 맞춘다. 원본 서버나 운영 DB·자격 증명은 사용하지 않는다. 전체 화면/변경 범위는 [FULLWEB.md](FULLWEB.md), 서버는 [FULL-SERVER.md](FULL-SERVER.md), APK·iOS 실행은 [FULL-HOSTS.md](FULL-HOSTS.md)를 따른다.

브라우저의 로컬 OIDC 인증·닉네임·로그아웃과 실제 피드백 DB 저장은 검증했다. Android WebView의 앱 복귀·이미지 선택은 합성 API 기기 검사로 구분한다. 후속으로 외부 인증 브라우저 → 앱 callback → PKCE 코드 교환 → HttpOnly 쿠키 저장의 네이티브 OAuth handoff를 구현했다. 새 정책 검사는 Kotlin/Swift 각각211개 조건을 통과했다. 실제 Android에서도 로컬 OIDC/Rust 서버가 발행한 앱 URI를 같은 Chrome의 링크로 전달해 회원 화면·닉네임·로그아웃·잘못된 state 및 replay 거절을 검증했다. Chrome context 쿠키로 callback302를 APIRequestContext에서 받은 뒤 링크를 눌렀으므로, 자동 HTTP302→OS 앱 전환 전체를 검증한 것은 아니다. iOS SDK 빌드·기기 실행과 실제 Google/S3/AI 제공자 연동도 미검증이며 네이티브 앱 전체 완료를 뜻하지 않는다.

테스트 작성 → 웹/서버/호스트 구현 → 독립 검증과 수정 기록은 [전체 확장 실행 기록](../../runs/016-webview-full.md)에 있다. 리그·F14 이메일·배포는 제외한다.

## 이전 검색 파일럿

이전 `web/`, `android/`, `ios/`, `scripts/serve.mjs`와 고정 검사는 보존한다. 이전 실행법은 [PILOT.md](PILOT.md), 기록은 [run013](../../runs/013-webview.md)이다. 전체 앱 실행에는 위 fullweb/serve-full을 사용한다.
