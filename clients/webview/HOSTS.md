# DAYNOMY WebView 호스트

공통 웹은 `web/`에서 제공한다. Android와 iOS 호스트는 네이티브로 종목/금액을 처리하지 않고 웹의 상태 모델을 사용한다. 로그인·OAuth·파일 선택·특권 JavaScript 브리지는 없다.

## 주소와 정책

- 개발 웹 origin은 Android emulator `http://10.0.2.2:18082`, iOS simulator `http://127.0.0.1:18082`다. 웹 `/api/` 프록시의 Rust 기본 대상은 별도 웹 서버 설정 `http://127.0.0.1:18081`이다. 호스트가 API 포트로 직접 접속하지 않는다.
- release는 설정된 단일 HTTPS origin만 내부로 연다. 미설정은 화면에 설정 오류를 표시한다. Android `-PwebOrigin=https://...`, iOS `DAYNOMY_WEB_ORIGIN=https://...` build setting으로 지정한다. 경로·query·fragment 없는 origin을 사용한다.
- scheme/host/effective port를 비교하며 userinfo·제어문자·역슬래시·불명 scheme을 거절한다. 외부 HTTPS는 주 프레임에서 사용자가 누른 링크만 OS 브라우저로 연다. 다른 포트·하위도메인도 내부로 취급하지 않는다.
- debug HTTP는 `127.0.0.1`, `localhost`, `10.0.2.2`, `::1` 중 설정한 한 origin만 허용한다. Android network security config와 iOS debug ATS는 release와 분리한다. iOS `NSAllowsLocalNetworking`은 ATS의 로컬 전송 예외이며 정확한 origin 제한은 정책/delegate/content rules에서 추가 적용한다. [Apple 공식 설명](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking).
- Android는 외부 origin subresource를 거절한다. WK는 document를 navigation delegate로 검사하고, script/fetch/image 등 다른 resource는 exact-origin content rule로 제한한다. 이 WK 규칙의 기기 실행은 미검증이다.
- SSL 오류 우회·혼합 콘텐츠·외부 popup·토큰 추출은 없다. 쿠키는 엔진 기본 저장소에서만 관리한다. 쿠키 세션 동작 검증은 별도다.

## 수명과 UI

Android는 시스템 bar/IME inset, iOS는 safe area/keyboard layout guide를 적용한다. Android API33 이상은 OnBackInvokedDispatcher, 이전 버전은 back callback에서 웹 history 우선 처리한다. iOS는 뒤로 버튼과 history 제스처를 제공한다.

Android orientation/screenSize configuration 변경은 같은 Activity/WebView를 유지한다. iOS 회전은 같은 controller/WebView를 재배치한다. background/foreground 때 웹에 `daynomy:active` CustomEvent(detail boolean)를 전달하며 웹은 이를 `MarketController.setActive`에 연결한다. 페이지 로드 완료 시 현재 active 상태도 전달한다.

메인 페이지 오류·HTTP 실패·렌더 프로세스 종료는 한국어 오류와 명시적 재시도를 제공한다. Android 프로세스 재생성은 WebView navigation state 복원을 시도한다. 프로세스 종료 후 수동 단가 초안의 영구 복원은 보장하지 않는다. 호스트 프로그램은 일반 오류 메시지만 표시하며 응답·쿠키·토큰을 로그에 남기지 않는다.

## 빌드

Android: min26 / compile35 / target35, AGP8.9.2, Kotlin2.1.20, Gradle8.11.1, JDK21. Android framework WebView/Activity와 Kotlin stdlib 외 추가 런타임 라이브러리는 없다. 기존 native Android 앱과 applicationId가 다르다.

```sh
# SDK 경로는 로컬 환경에 맞춰 local.properties 또는 ANDROID_HOME으로 지정한다.
JAVA_HOME=/Users/seoyeong/Library/Java/JavaVirtualMachines/ms-21.0.12/Contents/Home \
GRADLE_USER_HOME="$PWD/.local/android-gradle" \
.local/android-tools/gradle-8.11.1/bin/gradle -p clients/webview/android --offline --no-daemon :app:assembleDebug
node --test clients/webview/tests/host-policy.test.mjs
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`. 재현 가능한 wrapper도 제공하며 기존 로컬 캐시에 맞춰 위 명령으로 빌드했다. shared cache는 삭제하지 않는다.

iOS: iOS15.0 이상, UIKit/WKWebView/Foundation, Swift5 language mode. 실제 Xcode가 설치된 Mac에서:

```sh
xcodebuild -project clients/webview/ios/DaynomyWebView.xcodeproj \
  -scheme DaynomyWebView -configuration Debug -sdk iphonesimulator \
  CODE_SIGNING_ALLOWED=NO build
```

현재 개발 호스트는 Xcode/iOS SDK/simulator가 없다. Swift 정책 실행·문법 파싱·plist/pbxproj lint는 iOS 앱 빌드/실행을 대체하지 않는다.

## 지식베이스 적용

| 지식베이스 근거 | 호스트 적용 |
| --- | --- |
| `platforms/webview.md` W01/W02 및 파일럿 결정 | Android/WK 별도 호스트·OS별 검증 분리·HTTP debug origin |
| `packages/webview/state-and-navigation.md` | 내부 웹 history, 외부 브라우저, 회전 초안 유지, 프로세스 종료 재시도 |
| `packages/webview/auth-and-storage.md` E57/E37/E47 | 브리지 미노출, 엔진 cookie store만 사용, 로그인/OAuth 범위 제외 |
| `packages/webview/async-and-cancellation.md` | native lifecycle 이벤트를 웹 controller 수명과 연결 |
| `packages/webview/numbers-and-money.md` 및 dates/types | 금액·날짜를 native로 왕복 변환하지 않고 웹 모델에 유지 |
| `shared/testing-migration.md`, `packages/webview/modules-and-testing.md` | 고정 독립 정책 테스트와 APK/기기/iOS 실행 근거를 구분 |

입력 묶음과 해시: `experiments/webview/knowledge/manifest.json`. 구현자가 테스트/기준을 변경하지 않았다. 실제 실행 명령/종료 코드/미검증 사항과 소스 해시는 `experiments/webview/implementation/hosts/`에 남긴다. 독립 검증자의 별도 결과가 최종 인수 근거다.
