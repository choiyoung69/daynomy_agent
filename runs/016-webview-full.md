# WebView 전체 비리그 화면 확장

현재 결과: 전체 비리그 웹·로컬 제공 서버·Android/iOS 호스트와 네이티브 OAuth 연결 소스를 구현했다. 웹 빌드/고정 검사, 실제 Rust/임시DB 대표 흐름, 실제 Android의 선택한 기능과 통제된 로컬 인증 왕복을 검증했다. 자동HTTP302→OS앱전환·실제Google·iOS SDK실행·전체회원/관리자/외부제공자 범위는 미검증이며 서비스/네이티브 전체 완료 판정은 아니다. 아래 최초 검증과 OAuth 후속의 실패/결과를 구분한다.

사용자가 파일럿 범위 축소를 지적해 기존 웹 전체 화면을 재사용하도록 확장했다. 다섯 구현 방식 중 이 대화는 WebView만 담당하고 다른 native/Flutter 작업은 보존한다. 계약 spec/webview/full-service.md.

테스트 작성 fullweb_tests → 웹 구현 fullweb_porter / 서버 구현 fullweb_server 병렬 → 별도 fullweb_verifier 순서다. 구현 전 red와 experiments/webview/full/frozen-tests.json을 고정했다. 이전 파일럿 코드·기준·실패는 보존한다. 원본 .env·운영 데이터·원본 서버는 사용하지 않는다.

처음 preflight29/29 exit0, knowledge check110/110 exit0. 원본 package/lock만 먼저 복사한 후 npm ci --ignore-scripts --prefer-offline --no-audit --no-fund --prefix clients/webview/fullweb:228packages/exit0. 소스 복사는 red 이후 구현자가 시작했다. 고정된 의존성 설치와 앱 동작 완료는 구분한다.

## 수정과 독립 검사 진행

- 서버 path 검사가 query의 %2F까지 막는 결함을 fresh 리뷰와 별도 검증자가 발견했다. 테스트 작성자가 returnTo/검색/OAuth scope의 실제 실패와 blob 이미지 CSP 누락을 새 기준에 고정한 뒤 서버 구현자가 수정했다. 기존 기준은 유지했다.
- 전체 웹이 호스트의 daynomy:active 신호를 받지 않는 결함도 새 독립 회귀4개 실패로 고정하고 웹 구현자가 수정했다. 표준 pagehide/pageshow 검사와 호스트 신호 검사를 구분했다.
- 단순 파일럿 호스트를 변경하지 않고 android-full/ios-full을 별도로 추가했다. 외부 HTTPS 리소스, 사용자 이미지 선택, 신뢰한 문서의 확인 대화상자를 지원한다. 주 문서 탐색 정책은 원문 그대로 유지하며 특권 브리지/카메라/SSL 우회는 없다.
- 새로운 Kotlin/Swift 정책은 각각77개 assertion, 고정 검사3개를 구현 전 missing-source 실패 후 실행했다. iOS는 소스 문법/정책/프로젝트 검사만이며 Xcode 앱 실행은 미검증이다.
- 외부 Google OAuth 사용자 에이전트에서 앱 복귀·세션 연결까지의 네이티브 handoff는 end-to-end로 구현되지 않았다. 웹 로그인 UI 및 기존 서버 쿠키/CSRF 코드 재사용과 구분한다.
- 다른 채팅의 공유DB 검증 잠금 때문에 실제 API 준비가 지연됐다. 사용자는 조율 메시지 전송을 거절했으며 다른 채팅에 메시지를 보내지 않았다. 대기 중 독립 빌드·합성 API 브라우저·새 호스트 검사를 진행했다. 이후 root 전용 API18091/임시DB가 준비돼 feedback 기준0행을 확인하고 별도 검증자의 실제 저장/인증 검사를 허용했다.
- 기존 두 에뮬레이터5560/5564를 보존했다. 기존 AVD read-only 동시 실행 실패와 avdmanager 부재를 기록하고, 설치된 시스템 이미지와 검증된 하드웨어 설정만 사용한 새 AVD를 .local/webview-full-avd에 구성해 전용5576에서 실행한다. 기존 userdata를 복사하거나 초기화하지 않았다.

## 독립 검증 결과

WebView의 전체 비리그 화면 코드와 로컬 제공 서버, Android/iOS 전체 호스트 소스를 구현했다. 전체 플랫폼·외부 제공자 완료 판정은 아니다. 테스트 작성 → 구현 → 별도 실행 검증과 읽기 전용 리뷰를 분리했다. 상세 실행 출력과 실패 원본은 `experiments/webview/full/verification/`, 리뷰는 `experiments/webview/full/review/`에 보존한다.

| 범위 | 실제 검사와 결과 | 한계 |
| --- | --- | --- |
| 전체 웹 | 원본 단위35/35, UI385/385(원본384+구현자 lifecycle1), 독립 production build/typecheck exit0, dist16파일 일치 | 리그 혼합 원본 테스트는 원문 보존·실행 제외; 해당 비리그 assertion까지 모두 검증했다고 하지 않음 |
| 로컬 제공 서버 | 별도 서버 계약·query·symlink·abort 검사19/19 | loopback 실험 서버, 배포 완료 아님 |
| 호스트 생명주기 | 별도 고정 회귀4/4 및 실제 Chrome boolean event/입력 유지/조회 재개 | 변경 요청 자동 재실행 없음; 프로세스 종료 뒤 초안 복구 보장 아님 |
| 화면 탐색 | 동결 모바일 smoke와 20라우트 desktop/mobile 검사 | 초기 API502 화면 검사는 실제 데이터 검사와 별도 보존 |
| Android 실제 WebView | 새 Android13/WebView109에서 전체 앱 실행, HOME/복귀 시 수동 단가 유지·재조회, 비회원 거래 재로딩, 시스템 image picker·390744byte PNG 읽기·blob preview, 확인 대화상자 | 기기 동작 검사는 합성 API; Rust/DB 결과로 합산하지 않음 |
| 호스트 정책 | 고정3검사, Kotlin/Swift 각각77 assertion | Swift 정책·문법·plist/project 검사만; iOS SDK 빌드/실행 없음 |
| 실제 Rust API 비회원 흐름 | 종목 검색·BUY 추가·reload·수량3 수정·삭제 통과 | 비회원 원장은 원래 sessionStorage이며 DB 저장 주장 아님 |
| 실제 피드백 DB | UI POST204와 완료 화면, 전용 DB0→1행 확인 | 정확1회 제출; 실험용 임시DB |
| 실제 웹 인증 | 로컬 서명 OIDC callback→HttpOnly 쿠키 세션, 닉네임 PATCH200, USER 관리자 경계, logout204→보호화면 재진입401 통과 | 합성 authorization/로컬 제공자이며 실제 Google·네이티브 OAuth handoff 아님 |

전용 Rust fixture는 `.local/webview-full-backend-01/`, API18091, 프록시18082로 실행했다. 운영 데이터·원본 환경파일 없이 ephemeral OIDC와 discovery용 합성 데이터를 사용했다. `runtime/backend-provenance.json`에서 실제 실행 binary 해시와 fixture build 결과, 스냅샷 이후 backend 소스 변경이 없음을 대조했다. 본 작업은 Rust 소스를 수정하지 않았다.

검증 harness 실패도 보존한다. 초기 onboarding overlay가 click을 가린 문제, 새 VM Google Play FontsProvider 종료로 앱이 OS에 의해 종료된 시도, 구형 WebView CDP 연결 옵션, 로컬 provider authorize404/redirect 대기, 로그아웃 도착 경로를 원본 `/news` 대신 `/`로 기대한 실패를 각각 수정·재실행했다. 피드백 재전송으로 성공을 만들지 않았다. Chrome 실행 파일 경로를 verification-only preload로 지정했으며 동결 browser smoke 원문은 바꾸지 않았다. 최종 ADB viewport 캡처로 초기 로딩/긴 페이지 캡처의 반복 현상을 구분했다.

## 고정 근거와 남은 범위

- KB 전체14개 context `--require-ready` 통과, 입력36문서/context/spec 해시를 별도 manifest로 고정했다. 최종 로컬 source check110/110, 원본 preflight29/29 exit0. 외부63 pinned 출처는 live 재조회하지 않았다.
- 원본 frontend212파일의 복사 전후 해시, 현재 웹216파일 해시를 대조했다. 최종 웹 revision02 aggregate SHA256 `4848c4190a3264f32f67381ddffeb3e135dda6fc20e2f757bf9fe6f381aeb16b`, 서버 SHA256 `7baa7a35a5ac0af3ecbe03fb66b344fcd30b86aa8711ce2bfdb390b658215806`.
- Android 전체 호스트 APK SHA256 `db7b753f460b20c1b63676b6b3b53728e28eb359678b416cb6832d2109c9c4e3`. 호스트24파일 및 문서만 수정한 별도 revision을 보존하며 코드23파일/APK는 동일하다. 기존 pilot/frozen 기준을 덮어쓰지 않았다.
- 네 개 frozen manifest의17파일은 구현자가 변경하지 않았다. 최초 RED와 query/blob/lifecycle 보강의 RED·최종 결과를 함께 보존한다. 루트 README 정리 및 fullweb `.gitignore`는 실행 소스216파일 밖의 안내/생성물 제외 파일이다.
- **미구현:** 외부 인증 사용자 에이전트에서 앱 callback 및 WebView 세션 연결까지의 네이티브 OAuth handoff. 브라우저 로컬 로그인 성공으로 이 경계를 승인하지 않는다.
- **미검증:** iOS SDK 빌드/실행, 실제 Google·S3 업로드·AI·소셜 embed 제공자, 운영 통합, 모든 관리자/회원 기능의 실제 DB end-to-end. 리그/F14/배포는 제외 범위다.
- 본 대화의 결과는 WebView 버전이다. 별도 Android native/iOS native/React Native/Flutter 구현의 완료를 뜻하지 않는다.

최종 KB 회귀19개 중 `test_missing_service_context_fails_coverage`가 먼저 플랫폼 scope 유효성 검사에 걸려 실패했다(exit1). 현재 Android/WebView 승인 기능에 account가 들어간 상태에서 합성 fixture가 account만 삭제했기 때문이다. 별도 테스트 작성 역할이 해당 메서드의 합성 승인 범위만 기존 기능으로 고정했고, 실제 KB metadata/coverage 검사와 누락 assertion을 유지했다. 수정 후19/19 exit0이며 원래 실패 출력·변경근거는 `verification/kb-regression/`에 보존했다.

## 네이티브 OAuth 후속 보완 진행

위 결과와 `review/final-review.md`는 전체 웹 로컬 미리보기의 첫 검증 단계다. 로그인 범위에 남은 native handoff 미구현을 그대로 완료로 두지 않고 보완한다. 기존 Rust 모바일 start/exchange 계약을 읽기 전용으로 사용하고 backend는 수정하지 않는다. 별도 테스트 작성 역할이 신규 `spec/webview/native-auth.md`와 Kotlin/Swift 순수 정책·상태기계 검사를 먼저 RED로 고정하고, 호스트 구현 역할→별도 검증 순서로 진행한다. 이전24파일/17고정검사/APK 해시는 첫 단계 스냅샷으로 보존한다. 실제 Google와 iOS SDK 실행 한계는 별도다.

사용자가 직접 테스트 방법을 물어본 시점에 기존18082/18091 모두 connection refused임을 실제 loopback에서 확인했다. 새 수동 환경을 띄워 화면·종목검색·최근종가·뉴스200을 확인하고 `clients/webview/TESTING.md`에 단계와 자동 검사 명령을 정리했다. 초기 `.local/webview-manual-20261028-02`의 공유DB fixture는 stop파일로 종료(exit0/임시DB정리)하고, 다른 검증을 막지 않는 `.local/webview-manual-private-20261028-01` 전용PG55449/API18091로 전환했다. root 소유 launcher에 새output/빈 privateDBport 검사 옵션을 추가했고 phase1 launcher 복사본을 native-auth/runtime에 보존했다. 공통 fixture/백엔드 소스는 수정하지 않았다. proxy18082는 유지하며 전용DB 전환 후에도200을 재확인했다. 수동 Google로그인/AI실제제공자는 이 환경의 성공 대상으로 안내하지 않았다.

native-auth 테스트 작성 역할이 새 Kotlin/Swift 실행 검사2개를 실제 missing-source RED(exit1/skip0)로 고정했다. nil ABI stub으로 테스트 자체가 컴파일되는지만 별도 확인했고 이를 기능 성공으로 세지 않는다. 신규6파일 frozen manifest SHA256 `144fac2d952c9ed8674b85a69a8ebbfa4846481654cc89fa0dce7ded0b2f0f81`. 구현은 이 고정 후 다른 역할에 넘겼다. 기존17고정파일/백엔드/웹 구현은 수정하지 않았다. 사용자에게 안내한 서버 명령도 root가 재실행해17/17 exit0을 확인했다. 전용5576 에뮬레이터의 phase1 APK를 다시 열었고, 이는 native-auth 연결 완료 APK로 안내하지 않았다.

후속 구현 전달: NativeAuthSession Kotlin/Swift와 실제 OS 브라우저·callback·native exchange·HttpOnly 쿠키 저장 연결을 추가했다. 신규26파일 aggregate SHA256 `fb2e3d2c3d54cb2fa7c16410b11d7fcfbe9aa8244bf7c31fe72fbc2f4e55bf05`, APK SHA256 `2bc9bdf08d9905c1672fd31b76bb512ef0a282abccc5a824cce2dfc479f3b07e`. 순수2검사 각각211조건, 기존호스트정책3검사, Androidofflinebuild, Swiftparse/plutil exit0. 최초 Android빌드는 sandbox socket권한 실패 후 승인된 실행으로 성공한 기록을 유지한다. 읽기전용 리뷰가 process-global 쿠키 저장소와 Activity-local rollback의 경합, SPA logout와 late cookie설치의 경합을 지적해 process-global 설치lease/정리완료까지새begin차단/인증중WebView입력잠금/명시native취소를 추가했다. 테스트·웹216파일·Rust는 변경하지 않았다. 리뷰는26파일/APK/고정6파일/input5해시를 독립 확인했다. 실제기기승인은 별도다.

전용5576 visible실행 초기 Chrome 전환에서 shell/UI dump가 멈췄다. root소유기기만 정리해 headless로 다시 부팅했고 Chrome 초기화/외부CDP/adb reverse를 준비했다. 이 실패는 앱 정상로그인의 증거로 처리하지 않는다. 사용자 직접 기능 확인은 API와 함께 계속 동작하는 브라우저18082로 안내했다.

후속 독립 Android 인증 검증은 exit0이다. 원본 로그인 링크→외부Chrome, 미완료 브라우저에서 돌아온 뒤 native취소/재시도→새로그인, 실제Rustcallback302, 잘못된state의intent로me401유지, 서버발급URI를Chrome링크로열어nativeexchange/OSHttpOnly쿠키저장→실제WebView회원화면200, 닉네임PATCH200, USER관리자차단, logout204, 이전callback재전달후미인증을 확인했다. OS 쿠키속성과 JS 비노출도 검사했다. **전달 한계:** Chrome context 쿠키를 공유하는 APIRequestContext로 실제 callback302를 받고, 같은Chrome페이지의 사용자행동 링크로 발급앱URI를 열었다. native입구부터 회원까지 실제왕복이지만 자동HTTP302→OS dispatch 전체의 증거로 세지 않는다. 실제Google와 iOS는 계속 미검증이다.

검증 harness실패1~4는 보존했다. 이전Chrome탭/foreground선택경합과 고정email충돌가능성을 분리하고 합성sub/email을 유일하게 만들었다. WebView109에서 BrowserContext.request의쿠키CDP기능지원차이는 실제페이지fetch와페이지Network.getCookies의속성관측으로 교체했다. 요청/쿠키/코드/state/verifier 원문은 기록하지 않는다. 강제로쿠키저장중Activity재생성을일으킨동시실행증거는 없고, 해당경합방어는 소스리뷰/고정순수검사와 구분한다. 독립해시는 웹216/호스트26/기존고정17/추가고정6/APK모두 일치한다.

수동 테스트용 API18091/웹18082는 사용자 요청에 따라 유지한다. 전용privatePG55449를 사용해 공유검증잠금을 점유하지 않으며, 이 세션 시작 전 공유fixture는 정상종료했다. 재실행·종료 방법과 한계는 `clients/webview/TESTING.md`에 있다. 전용Android/CDP검증 자원은 별도 정리하며 다른 채팅 자원은 건드리지 않는다. 런타임출처는 `native-auth/runtime/backend-provenance.json`의 실제binary/고정candidate소스일치로 확인했다.

최종 독립리뷰 시각은2026-10-28 20:10:57 KST(`native-auth/review/final-acceptance.json`)다. 소스26/APK/새고정6/input5 해시 불일치0, 실제결과/하네스/독립순수검사의 해시도 고정했다. 판정은 `accepted-source-and-controlled-android-scope`이며 자동302앱전환·실제Google/운영·iOS SDK·강제쿠키저장/재생성교차실행을 승인한 것이 아니다. 사용자 테스트 안내 전18082의화면/종목/뉴스200을 재확인했다. 비용·모델사용량은 측정하지 않아 추정하지 않았다.
