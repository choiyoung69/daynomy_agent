# WebView 테스트 우선 구현·독립 검증

현재 결과: **종목 검색·최근 종가·수동 단가의 웹/Android 로컬 파일럿 검증 통과. iOS 앱 빌드·기기 검증은 Xcode 부재로 미완료.**

[실행 안내](../clients/webview/README.md) · [호스트 안내](../clients/webview/HOSTS.md) · [독립 검증 보고서](../experiments/webview/verification/report.md) · [독립 결과 JSON](../experiments/webview/verification/result.json) · [최종 독립 리뷰](../experiments/webview/final-review/revision-02.md)

2026-10-28 사용자 요청: 지식베이스 활용. 독립 테스트 작성 서브에이전트 → 다른 구현 서브에이전트 → 다른 검증 서브에이전트.

착수 당시 상태: 테스트 작성 진행 중. 원본 preflight29/29 성공(exit0); knowledge check108/108 성공(exit0). 최초 WebView require-ready는 버전·정책 미결정으로 exit2. 파일럿 범위를 spec/webview/README.md에 결정한 뒤 준비 상태를 갱신했다. 앱 실행 통과는 아직 없음.

독립 역할: webview_tests / 후속 구현 역할 / webview_verifier. root는 계약·자료 준비·배정·증거 통합 담당. 역할 JSON은 자동 실행기가 아니다. 기존 미커밋 Android 및 지식 작업은 보존한다.

환경: Node22.23.1, 로컬 TS6.0.2. Xcode 부재로 xcodebuild -version exit1. 최초 adb는 sandbox socket 권한으로 exit1; 권한 해결 후 재확인 전까지 기기 부재로 단정하지 않는다.

범위·실행 계약: [WebView](../spec/webview/README.md). 테스트/구현/검증 증거는 experiments/webview/에 별도 기록한다. 전체 앱·거래 저장·로그인·운영 배포는 범위 밖.

## 독립 테스트 고정 및 병렬 구현 시작 — 2026-10-28T08:53:12.907590+00:00

- 독립 테스트 작성자 webview_tests가 구현 없는 상태에서 Node syntax검사 exit0, build exit2(TS18003 구현 없음), API/상태·host policy·HTTP/실제 Chromium 검사 exit1(필수 구현 파일 없음)을 기록했다. 아직 assertion을 통과시킨 green 결과는 없다.
- 기준 experiments/webview/frozen-tests.json SHA256 dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9, 고정 파일13개 현재 해시 일치. 구현자에게 기준 변경 금지를 전달했다.
- webview_implementer(웹)와 webview_hosts(Android/iOS)를 동시에 착수시켰다. 독립 검증자는 webview_verifier이며 자기 구현 검증으로 완료를 판정하지 않는다.
- KB require-ready는 21문서 선택 후 exit0; experiments/webview/knowledge/에 입력 문서 SHA256 보존. 준비 판정은 실행 통과가 아니다.
- root ADB 권한 요청 후 기기조회 exit0, emulator-5564 device. 기존 Android fixture18091는 다른 작업 소유이므로 중단·변경하지 않고 공개 synthetic조회만 재사용한다.
- KB 회귀 최초 실행29개 중16개 실패(exit1): 격리 fixture가 새 spec/webview 링크를 복사하지 않음. 테스트 작성자에게 fixture 보완과 파일럿 준비 경계 기대값 갱신을 요청했다. 테스트 의미를 약화하지 않는다.

## 지식베이스 회귀 보완 — 2026-10-28T08:54:40.008680+00:00

테스트 작성자가 isolated fixture에 새 spec/webview 문서를 복사하고, 기존 준비 판정은 Android 및 WebView의 stock-search-price만 허용하도록 기대를 갱신했다. 다른 기능 auth-session의 전달 차단도 두 플랫폼에서 확인한다. `python3 -m unittest discover -s scripts -p 'test_knowledge*.py'` 29개 PASS/exit0 (테스트 작성자 실행). 최초 실패를 성공으로 덮어쓰지 않는다.

## 독립 실제 실행에서 발견한 제품 결함 — 2026-10-28T09:02:16.604341+00:00

- 독립 verifier: TypeScript/계약29개, Kotlin·Swift 정책2개, 실제 HTTP1개 PASS. 실제 Chrome DOM의 검색결과 표시 검사 FAIL. Android APK 설치·실제 WebView109 화면 표시는 성공했으나 실제 검색은 같은 실패.
- CDP에서 실제 `new MarketApi().search`는 Window.fetch Illegal invocation으로 실패. default native fetch를 `this.fetcher(...)`로 호출하면 receiver가 MarketApi가 되는 구현 결함이다. `fetch.bind(globalThis)`를 주입하면 동일 검색이 성공했다. Node 모의 fetch는 receiver를 요구하지 않아 단위29개가 통과했다.
- 증거 experiments/webview/verification/fetch-receiver-diagnostic.json, android/desktop-runtime.json, http-browser.log와 초기 screenshots 보존. 환경 문제로 분류하지 않는다.
- root가 기존 구현 서브에이전트에게 native fetch receiver 수정·모바일 방향중립 안내·문서 corner token 정정을 요청했다. 기존 frozen tests는 변경하지 않고 새 revision-02 소스 해시와 실제 재검증을 요구한다.
- Android 구현자는 APK assembleDebug exit0·순수 정책2개 pass, iOS Swift syntax/plist/project lint pass를 보고했다. iOS Xcode 앱 빌드 exit1/기기 미검증을 유지한다.

## 수정 후 독립 실행 및 남은 증거 보강 — 2026-10-28T09:11:33.130607+00:00

- revision02: 기본 native fetch를 globalThis에 bind하고 모바일 '왼쪽' 안내를 방향중립으로 바꿨다. 이전 코드·실패·해시는 보존한다. 독립 재실행 unit29/29, Kotlin·Swift정책2/2, HTTP/actualChromiumDOM2/2 모두 exit0.
- 실제 Rust synthetic API와 Android13/WebView109·desktopChrome156 연결에서 KR71000.125/기준일2026-10-23, US193.4USD, exact manual string과 삭제, home/회전 유지, 키보드 표시,48px 조작/가로overflow없음을 독립 실행했다.
- fresh reviewer는 fetch/copy수정과 frozen13/소스해시 일치를 확인했다. Androidquote-full캡처는 header중복으로 무효이며 기존 validquote.png를 근거로 쓴다. landscape는 회전시 단가가독성을 입증하지 않으며 값유지 검사만 유효하다.
- verifier의 missingPrice 대기는 loading에도 있는 '직접 입력'을 조기에 매칭했다. Android settled404는 있었으나 실제 retryclick근거는 부족했다. 따라서 reviewer가 settlederror+retryvisible+새요청+404복귀 보강을 요구했다. 기존 진단/결과를 덮어쓰지 않는다.
- 보강 중 타작업 소유 공유emulator/fixture가 종료되어 adb없음/ECONNREFUSED발생. root가 별도 .local/webview-backend-01 임시Rust/DB를 새로 시작했고 READY18091, 소유session13254로 확인했다. source변경과 제품오류가 아니다.
- 기존 verifier턴은 Selected model is at capacity로 실패했다. 같은모델 자동재전송하지 않고 fresh webview_verifier_recovery(gpt-6-astra/high)를 배정했다. 초기 역할모델은 대화설정상속이며 정확ID미측정이다. 기존검증증거는 보존하고 남은보강/최종해시는 새검증자가 확인한다.

## 최종 인수 범위 — 2026-10-28T18:16:53.517185+09:00

테스트 작성자, 웹 구현자, 호스트 구현자, 실행 검증자, fresh 리뷰어를 구분했다. 구현 전 실패 기록과 고정 테스트 13개 파일, 지식베이스 입력 21개 문서를 보존했다. revision02 웹 9개 파일, 호스트 22개 파일, APK 및 실제 제공 ESM의 해시를 대조했다. 이 대화의 조정자가 배정했으며 역할 JSON은 무인 실행기가 아니다.

| 독립 검사 | 결과 |
| --- | --- |
| 웹 계약 | 29/29, exit 0 |
| Kotlin·Swift 순수 탐색 정책 | 2/2, exit 0 |
| HTTP 및 실제 Chromium DOM | 2/2, exit 0 |
| Android APK 재빌드 | exit 0 |
| 실제 Rust/임시 DB + Chrome156/Android13·WebView109 | 국내·미국 종가, 수동 입력·삭제, 앱 복귀·회전·키보드 확인 |
| 명시적 404 재시도 보강 | 두 환경에서 요청 1→2, 404 응답 두 개, 최종 오류 상태 확인 |
| 지식베이스 회귀 | 29개, exit 0 |
| 지식베이스 자료 검사 / 원본 preflight | 108/108 및 29/29, exit 0 |

국내 샘플은 71000.125·기준일 2026-10-23, 미국 샘플은 193.4 USD다. 사용자 수동 문자열과 삭제를 보존했고, 앱 복귀와 회전 뒤 입력 유지 및 키보드 표시를 확인했다. 별도 복구 검증자는 확정된 가격 오류·표시된 재시도 버튼·기준일 `조회 전`을 기다린 뒤 실제 클릭과 새 가격 요청, 404 응답, 최종 오류를 확인했다. 기존 검증 스크립트의 조기 판정은 보존하고 이 보강 증거로 보완했다. fresh 리뷰어는 기존 P1·P3를 해결된 것으로 판정하고 이 로컬 범위만 인수했다.

탐색 정책, JavaScript 오염 방지, 내부 history/back, 비민감 임시 쿠키 유지 후 제거를 확인했다. 외부 HTTPS는 Chrome FirstRun으로의 전달까지만 확인했으며 외부 페이지 렌더링은 확인하지 않았다. 쿠키 검사는 회원 로그인 검증이 아니다.

iOS는 순수 정책, Swift 문법, plist/project 형식만 검사했다. Xcode 앱 빌드·기기 실행은 미검증이다. Android 최소 API26·실기기·renderer 종료 복구·프로세스 종료 후 초안 영구 복원, TalkBack/VoiceOver, release HTTPS 배포는 미검증이다. 로그인·OAuth·거래 저장·전체 서비스·배포는 범위 밖이다. 백엔드 코드는 변경하지 않았고 기존 피드백 전체 `verify`를 이번 UI 검사로 대체하거나 재실행했다고 주장하지 않는다.

유효 캡처는 [실제 Android 종가](../experiments/webview/verification/screenshots/round02-android-quote.png), [데스크톱 종가](../experiments/webview/verification/screenshots/round02-desktop-quote-full.png), [모바일 오류 화면](../experiments/webview/verification/screenshots/round02-desktop-mobile-full.png)이다. 상단이 중복된 Android full-page 캡처는 제외했고 landscape 캡처의 가독성과 실행 JSON의 값 유지 근거를 구분했다.

웹 런타임에 추가 외부 패키지는 없다. TypeScript6.0.2는 빌드 도구이고 Node 내장 HTTP/HTTPS·파일 모듈로 로컬 서버를 제공한다. Android는 플랫폼 Activity/WebView를 사용하며 AGP/Gradle/Kotlin은 빌드 도구다. iOS는 UIKit/WebKit/Foundation을 사용한다. Rust 의존성은 변경하지 않았고 기존 app/README.md의 목록을 유지한다.

knowledge README/STATUS/목차/질문/이력과 packs의 runtime 설명에 한정된 결과를 연결했다. 고정 입력 21개 문서 원문과 테스트는 변경하지 않았다. 같은 범위의 순차 대조 실행이 없어 시간·비용 절감률을 추정하지 않는다.

검증 후 이 작업이 소유한 임시 Rust/DB, preview 서버, 재기동한 AVD를 정리했다. root fixture 세션13254는 exit 0이며 DB 정리 결과는 `.local/webview-backend-01/result.json`, 정리 요청과 ADB 종료 결과는 [cleanup](../experiments/webview/cleanup.json)에 보존한다. 기존 다른 작업의 파일과 원본은 보존했다. localhost 미리보기는 정리했으며 아래 명령으로 다시 실행한다.

### 로컬 재현

저장소 루트에서 터미널1에 전용 임시 DB/API를 시작한다. 아직 사용하지 않은 output 경로를 선택한다.

```sh
python3 scripts/android_backend_fixture.py --output .local/webview-replay-01
```

READY18091을 확인한 뒤 터미널2:

```sh
npm --prefix clients/webview/web run build
node clients/webview/scripts/serve.mjs --port 18082 --api-origin http://127.0.0.1:18091
```

브라우저는 http://127.0.0.1:18082, Android emulator는 http://10.0.2.2:18082를 사용한다. APK 위치와 빌드·설치, iOS 프로젝트는 위 호스트 안내를 따른다. 임시 fixture는 Ctrl-C로 종료하면 자원을 정리하며 원본 서비스나 운영 DB를 사용하지 않는다.
