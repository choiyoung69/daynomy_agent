# Flutter iOS 독립 검증 재개

현재 후속 상태: Xcode27.1에서 실제 simulator build03 종료0. 제품/고정 테스트 수정 없이
`Runner.app`를 생성했다. SDK와 일치하는 iOS27.1 runtime24A94232 설치를 기다리며
실제 화면·5탭 검증은 아직 성공하지 않았다. 아래 설치 전 차단 기록은 과거 이력이다.

2026-10-28 KST, 검증 역할 `/root/flutter_xcode_verification`.
사용자가 Xcode 설치 후 실제 검증을 요청해 Flutter iOS 빌드·시뮬레이터 실행을 다시 시도했다.
제품·고정 테스트는 수정하지 않았다. `clients/ios/`의 별도 Swift 작업도 변경하지 않았다.

## 최초 시도 당시 판정 (설치 전)

**환경 차단. iOS 빌드·설치·화면 실행을 성공으로 세지 않는다.**
이 검증 시점의 `/Applications`와 사용자 Applications·Downloads·Volumes 최상위에는 Xcode
bundle 후보가 없었다. Spotlight의 Xcode bundle identifier 및 파일명 검색도 결과가 없었다.
이 관찰은 사용자 설치 의도를 부정하는 것이 아니며, 다른 경로/진행 중 설치는 사용자 답으로 확인한다.

| 직접 검사 | 결과 |
| --- | --- |
| `python3 scripts/check.py preflight` | 종료0, 원본 29/29 해시 일치; 동작 검증 아님 |
| `xcode-select -p` | `/Library/Developer/CommandLineTools` |
| 기본 `xcodebuild -version` | 종료1, 전체 Xcode가 필요하다는 오류 |
| 기본 `xcrun --find simctl` | 종료72, simctl 도구 없음 |
| 프로세스 한정 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -version` | 종료1, 지정 경로 없음 |
| 같은 환경의 `xcrun simctl list runtimes` | 종료1, 지정 경로 없음 |
| Flutter simulator debug build | 종료1, 같은 xcrun 경로 오류. 앱 컴파일 전 실패 |
| `flutter doctor -v` | Xcode incomplete; doctor 종료코드0은 환경 정상 판정이 아님 |
| Info.plist·AppFrameworkInfo.plist·project.pbxproj lint | 3/3 통과. 정적 문법 검사만 의미 |

빌드 명령은 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer bash ../../scripts/flutter.sh
build ios --simulator --debug --no-pub --dart-define=API_BASE_URL=http://127.0.0.1:18087`이다.
실제 원시 로그는 `experiments/flutter/ios-verification-20261028/ios-build-01.log`에 있다.
존재하지 않는 경로 지정의 실패와 제품 결함을 구별한다. 기존 CLTools만으로 iOS 검증을 대체하지 않았다.

## 근거와 변경 보존

`README.md`, AGENTS 시작 기록, 피드백 명세, 기존 Flutter 독립 검증 기록·클라이언트 안내와
Flutter 계약·인증·디자인·테스트 작성 기록을 읽었다. iOS SPM 설정, plugin 등록,
URL scheme `org.daynomy.app`, deployment target17.4를 정적으로 확인했다.
SPM을 사용하는 프로젝트이므로 doctor의 CocoaPods 미설치 경고만으로 플러그인 결함을 확정하지 않는다.
시뮬레이터·DB·개발 서버를 생성하지 않았으며 전역 xcode-select·라이선스·first launch를 변경하지 않았다.

72개 제품/플랫폼/고정·보강 테스트/명세 경로의 실행 전후 SHA-256은
`experiments/flutter/ios-verification-20261028/source-before.json`과 `source-after.json`이다.
현재 비교에서 변경은 없다. `environment.json`에는 직접 도구 검색 결과,
`flutter-doctor-01.log`에는 Flutter 진단을 보존했다. Doctor의 adb 소켓/네트워크 오류는
sandbox 진단 한계이며 iOS 앱 결함으로 세지 않는다.

조정자가 별도로 재실행하는 238개 회귀 테스트와 이 iOS 플랫폼 검증은 구별한다.
조정자의 첫 회귀 실행은 없는 DEVELOPER_DIR 선택으로 test host 준비 전 실패했고,
기본 CLTools 환경으로 두 번째 회귀를 수행한다. 해당 결과는 조정자 기록을 따른다.

## 이어서 수행할 검증

사용자가 전체 Xcode의 실제 설치 경로/완료 상태를 알려주면 그 경로를 프로세스 환경에만 지정해
Xcode 버전·iOS SDK·시뮬레이터 runtime을 확인한다. 설치되어 있으면 새 전용 UDID를 생성해
실제 simulator build → install → launch → 5개 탭 → 합성 Rust fixture 검색·종가·포트폴리오·뉴스·
캘린더·피드백을 검증한다. 기존 다른 기기/DB/Swift 프로젝트는 조작하지 않는다.
실 Google·실 AI·실기기 인증은 별도 범위이며 여전히 미검증이다.

## 후속 환경 관찰과 회귀 결과

19:03:50KST의 두 번째 범위 제한 재탐색에서 `/Applications/Xcode.appdownload`가 새로 발견됐다.
이 placeholder 후보의 mtime은19:02:54KST이며 `Contents`와 Icon 항목만 있고
`Contents/Developer/usr/bin/xcodebuild`는 없다. 이 관찰을 전체 Xcode 설치 완료로 세지 않는다.
최초 탐색 때 후보가 없었다는 결과도 그 시점의 근거로 보존한다. 탐색 범위·읽기 불가 경로는
`scoped-search-02.json`, 후보 metadata는 `download-candidate-02.json`에 있다.

조정자 `.local/flutter-xcode-regression-03/result.json` 재실행은 실제 **238/238**,
analyzer 종료0(4.49초), release Web 종료0(16.84초), 테스트28.24초이며
`criteria_and_sources_unchanged=true`다. 이 호스트 회귀 성공은 iOS 빌드 성공과 구별한다.
첫 회귀 -01은 없는 DEVELOPER_DIR 지정, -02는 sandbox loopback test-server socket
Operation not permitted로 테스트 로딩 전에 실패했다. 필요한 loopback 권한으로 -03에서
성공했으며 통과를 위해 제품·기준을 수정하지 않았다. 이 실패 이력도 성공으로 덮어쓰지 않는다.

## 이번 검증의 최종 판정

19:09:16KST 마지막 읽기 확인에서도 `/Applications/Xcode.app`와 그 안의 xcodebuild가 없었고
`/Applications/Xcode.appdownload`만 있었다. 관찰은
`experiments/flutter/ios-verification-20261028/environment-observations.jsonl`에 보존했다.
**설치 중간 bundle 관찰, 전체 Xcode 및 iOS SDK 사용 불가; 정확한 설치 완료 여부는 미확정**이다.
따라서 제품 컴파일·시뮬레이터 생성·설치·런칭·5탭 화면 검증은 이번에 수행하지 못했다.
사용자의 설치 완료 진술과 현재 도구에서 발견한 경로를 동일 사실로 단정하지 않는다.
추가 설치·권한 변경·새 DB 검사 없이 관찰을 종료했다. 실제 Xcode.app 경로가 확인되면 재개한다.

별도 조정자 회귀 -03 원시 result를 `coordinator-regression-03.json`에 보존했다.
238개 테스트·분석·Web 빌드가 모두 성공했고, 기존 independent03과도 제품/고정·보강 기준은 같다.
iOS 검사 자체의 원시 result는 `result.json`이며 status는 `blocked_xcode_unavailable`이다.
마지막에도72개 경로의 전후 해시는 모두 같았다. 이 역할에서 변경한 것은 지정 검증 산출물과
이 보고서뿐이다. 새 앱 결함을 확인한 것은 아니며, iOS 완료 승인은 보류한다.

## Xcode 설치 후 재개 02

사용자가 Xcode를 열었다고 알려 재개했다. 19:13KST에 `/Applications/Xcode.app`가 존재하고
프로세스 한정 DEVELOPER_DIR에서 **Xcode27.1 build27A9275** 버전 확인이 성공했다.
다만 SDK 목록과 simctl runtime/device 확인은 모두 종료69이며
`You have not agreed to the Xcode license agreements`를 반환했다.
이 시점은 이전의 전체앱 부재와 다른 초기설정 차단이다. 라이선스 자동동의나 sudo를
수행하지 않았으며 사용자의 Xcode 첫실행 검토/동의 완료를 기다린다.
`resume-02/environment-01.json`에 원시결과, `source-before.json`에72개 기준 해시를 보존했다.
이전 검사와 제품/기준 차이는 없다. 아직 새 simulator·빌드·DB검사를 시작하지 않았다.

## 재개 02 실제 빌드와 runtime 조사

사용자 라이선스 동의 답변 뒤 정상 도구 권한에서 SDK 조회·firstlaunch 상태 조회가 종료0이었다.
기본 sandbox에서는 여전히 license69를 반환했으므로 그 후속 오류는 권한 진단 혼선으로 구별한다.
`xcodebuild -runFirstLaunch`는 도움말상 약관 동의도 포함해 자동 실행하지 않았다.
CoreSimulator 도구는 사용자 첫실행 준비가 진행된 뒤 사용 가능해졌다.

실제 simulator build 결과:

1. build01: Xcode 컴파일 진입 뒤 objective_c9.6.2 native hook의 빈 SDK경로로 실패했다.
   hooks_runner1.5.0은 DEVELOPER_DIR를 제거하나 PATH는 보존한다. 동일 hook을 Xcode경로를
   명시한 환경에서 단독 실행하면 clang native asset 컴파일이 성공했다.
2. 검증용 local PATH xcrun wrapper가 DEVELOPER_DIR만 설정한 뒤 실제 `/usr/bin/xcrun`을
   exec하도록 했다. 제품/의존성 소스나 전역 xcode-select는 변경하지 않았다.
   build02는 native hook을 통과했으나 plugin module 누락으로 실패했다.
3. Xcode가 없던 시점의 생성 메타데이터는 iOS SPM false, generated package dependencies=[]였다.
   같은 고정 의존성으로 `pub get --offline` 종료0 후 SPM이 true/정상 dependencies로 재생성됐다.
   **build03 종료0, 실제 Xcode build17.1초**, `build/ios/iphonesimulator/Runner.app` 생성.
   Bundle org.daynomy.app, iPhoneSimulator, 최소17.4와 arm64/x86_64 binary를 확인했다.

`build03-manifest.json`은 앱63개 파일 해시와 입력 변경을 보존한다. 입력72개 중 변경된 것은
빌드 생성물 `Generated.xcconfig`와 `flutter_export_environment.sh` 두 개뿐이며 제품lib/플랫폼
프로젝트 설정·고정/보강 테스트·pubspec/lock·명세는 변하지 않았다.

첫 `xcodebuild -downloadPlatform iOS -architectureVariant arm64`가27.1 build24A94425를
내려받았다. available=true가 일시 관찰되어 전용 iPhoneDuo UDID
5352DDB4-AE3F-43E5-A7FC-C477BBAB3228을 만들고 boot/install/launch까지 실행했다.
launchPID는 확인됐지만 screenshot01/02는 검정이며 실제UI 성공으로 세지 않는다.
primary화면 캡처는 프레임을 받지 못해 해당 본인 캡처 명령만 중단했다.

다운로드 도구가 추가27.0(8.05GB) 다운로드를 시작해 필수27.1이 준비된 것으로 판단하고 본인
session만 Ctrl-C로 중단했다(exit70, Download was cancelled). 뒤이어 runtime profile을 찾을 수
없고 기기는 unavailable/shutdown이 됐다. 처음에는 취소 rollback을 의심했지만 공식
`simctl runtime list`에는24A94425 이미지가 **Ready 상태로 계속 남아있었다**.
`runtime match list`의 설치SDK27.1 default/chosen build는 **24A94232**였다.
따라서 이미지 삭제/rollback은 확정하지 않으며 SDK System-match 불일치가 직접 확인된 근거다.

이후 `-downloadPlatform iOS -buildVersion 27.1 -architectureVariant arm64`가 요구 build24A94232를
명시 선택해 설치 중이다. 이번에는 명령 종료0과 안정된 runtime availability 뒤에만 실행을 재개한다.
기존 이미지·다른기기 삭제나 전역 runtime override는 하지 않았다. 이전 launch/검정캡처,
Flutter run의 device-not-found 실패를 그대로 보존했다. GUI Simulator app도 현재 설치경로에서
찾지 못해 독립 작성자의 shadow integration 하네스를 준비했다. pubget와 하네스 analyze 종료0은
실제 iOS UI 성공과 구별한다. 하네스는9개 checkpoint를 포함한1개 시나리오이며238개 기존검사와
단순 합산하지 않는다. 실 production main/lib/transport를 사용하고 shadow에만 SDK계측 의존성을 더한다.
