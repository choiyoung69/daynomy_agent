# WebView 독립 검증 계획

2026-10-28. 역할: 테스트·구현을 작성하지 않는 검증자. 테스트 작성 → 다른 구현자 → 독립 검증 순서를 따른다. 아래는 실행 전 계획이며 통과 보고가 아니다.

## 근거와 환경 사전 확인

- 계약: `spec/webview/README.md`, 지식베이스 기능 S01–S13, WebView 비동기·수명·인증·모듈 패키지.
- 원본: `frontend/src/features/stocks/api.ts`, `types.ts` 확인. market은 `String(value)`로 검사하며 currency는 검사하지 않는다. 날짜 문자열·유한한 숫자 가격을 API가 허용하고 양수 여부는 UI 책임이다.
- `python3 scripts/knowledge.py context --platform webview --feature stock-search-price --require-ready`: exit 2. 로컬 출처 해시 108/108은 통과했지만 플랫폼 버전/결정/주제 metadata가 아직 NOT READY다. spec에서 정한 버전을 metadata 준비 완료와 혼동하지 않는다.
- `node --version`: v22.23.1, exit 0. `java -version`: OpenJDK 21.0.12, exit 0.
- `xcodebuild -version`: exit 1. CommandLineTools만 선택되어 있고 Xcode가 없으므로 WKWebView 빌드·시뮬레이터 검증은 현재 불가하다.
- Android SDK `/Users/seoyeong/Library/Android/sdk`, Gradle `.local/android-tools/gradle-8.11.1`, 기존 캐시를 활용한다. `emulator -list-avds`: exit 0, Medium_Phone이 있으나 sandbox crashpad 권한 오류가 함께 관찰되어 실제 emulator 실행 가능성을 의미하지 않는다.

## 구현 완료 후 검사 순서

1. 테스트 작성자가 고정한 SHA256과 실제 테스트 파일을 대조한다. 구현·명세·호스트·런타임 소스 해시를 기록하고 검사 후 다시 확인한다. 코드·독립 테스트·기준을 수정하지 않는다.
2. 고정된 Node 계약 검사를 실행하여 명령·exit·통과/실패 수를 기록한다. decoder, 요청 URL/credentials/signal, debounce, 오래된 성공·실패·finally 무시, 수동 입력/삭제, 국가·선택 해제·수명 전환을 확인한다.
3. 별도 HTTP 서버에서 HTML/JS/CSS 및 `/api/` 프록시 응답을 직접 확인한다. 경로 탈출·신뢰하지 않은 프록시 목적지·에러 응답·쿠키 전달을 검토한다. 정적 검사를 화면 실행으로 표현하지 않는다.
4. root와 DB 자원을 조율한 뒤 disposable Rust fixture의 18091을 재사용하거나 새 fixture를 배정받는다. 이 fixture는 공유 DB lock을 유지하므로 실행 중 다른 DB gate를 실행하지 않는다. synthetic KR/US/가격 없음/ETF/비상장/20개 제한을 확인하고 화면에서 KR 최근 가격 71000.125 및 날짜 2026-10-23, US 193.4, 404의 수동 입력 안내를 검증한다.
5. Android debug APK를 실제 빌드한다. emulator 설치·실행과 WebView 엔진 버전을 기록한다. 검색→선택→자동 단가→수동 편집/삭제, 빠른 검색·국가 전환, background/복귀, 회전, 키보드·스크롤, 외부 탐색·뒤로 가기·오류 재시도를 확인한다. adb/가상화 권한 거절은 안전한 승인 경로를 시도한 후 결과를 기록한다.
6. Android/iOS origin 정책은 scheme/host/effective port와 userinfo/하위도메인/위장 hostname/file/javascript/data/intent/외부 팝업을 원본 코드와 대조한다. 브리지·SSL 우회·혼합 콘텐츠·release cleartext 허용 여부를 검토한다. host 정책 단위 실행이 실제 OS 탐색 검증을 대체하지 않는다.
7. iOS는 Xcode 부재를 명확히 기록한다. Swift 순수 정책 검사 가능 여부와 WKWebView build/device 한계를 분리한다.

## 증거와 완료 기준

검증 산출물은 `experiments/webview/verification/`에 둔다. 원시 로그에는 요청 본문·쿠키·토큰·DB 접속 문자열을 출력하지 않는다. 결과는 실행/정적 검토/미검증/환경 차단을 구분하고, 실패 항목은 root에 전달하여 다른 구현자가 수정하게 한다. 수정 이후에는 변경 소스 해시와 필요한 재검증 결과를 새 실행으로 남긴다. iOS 미검증 상태에서는 양쪽 WebView 전체 완료를 선언하지 않는다.
