# 012 — 지식베이스 기반 Flutter 사용자 앱

2026-10-28 진행 중. 현재 요청은 검색·포트폴리오·뉴스·캘린더·내 정보의 전체 사용자 앱이다.
추가로 네이티브 회원 로그인을 위한 서버 확장과 서로 다른 서브에이전트의
테스트 작성 → 구현 → 검증 순서를 사용자가 승인했다.

## 시작 근거

- 기존 미커밋 Android·knowledge 파일을 보존한다. Flutter 앱 위치는 `clients/flutter/`다.
- `python3 scripts/check.py preflight`: 종료 0, 원본 29/29 일치. 행동 검증을 의미하지 않는다.
- `python3 scripts/knowledge.py check`: 종료 0, 로컬 출처 108/108 일치.
- Flutter `context --require-ready`: 종료 2. 버전·HTTP·숫자·인증·빌드 결정이 남은 상태를 보존한다.
  앱 작업의 구체적 선택과 실제 검증은 이 실행에서 별도로 기록한다.
- 지식베이스 Flutter/Dart 묶음, 기능 계약, 원본 프론트/API와 현재 Rust 코드를 읽는다.
- SDK 공식 목록 경로를 잘못 사용한 세 요청은 404로 실패했다.
  공식 문서에서 `/flutter_infra_release/releases/` 경로를 확인해 목록 다운로드에 성공했다.
  공식 stable 목록: Flutter 3.47.8, Dart 3.13.7, macOS arm64.

## 역할과 완료 판정

1. `flutter_tests`: 원본 기반 계약·테스트 작성. 제품 구현 금지.
2. 이후 새 에이전트: 고정 테스트의 실패를 확인한 후 앱·네이티브 인증 서버 확장 구현.
3. 이후 다른 새 에이전트: 고정 테스트·실제 HTTP/DB·빌드·코드 리뷰로 검증.

조정자는 환경 준비·역할 연결·테스트와 소스 해시·실행 증거를 담당한다.
테스트 통과만으로 전체 기능·실제 Google 인증·양쪽 OS 동작 완료를 선언하지 않는다.
실제 명령·종료 코드·실패/수정·미검증 부분을 후속 기록에 추가한다.
비용과 속도 향상은 미측정이다. 기존 백엔드 결과를 이번 앱 검증으로 세지 않는다.

## 테스트 작성과 실제 초기 실패

- 첫 역할 `/root/flutter_tests`는 `clients/flutter/test/`의 테스트 6개와 support,
  34개 사용자 endpoint 계약, 기존 decoder fixture 21개, 게스트 계산·회원 거래 CRUD 위젯,
  PKCE·쿠키 격리와 `scripts/flutter_auth_acceptance.py`를 작성했다. 제품 구현은 작성하지 않았다.
- `.local/flutter-red-01/result.json`: `flutter test --reporter expanded` 종료 1,
  21.517초. `lib/daynomy.dart`가 없는 실제 컴파일 실패다. 기준 해시와 복사본을 보관했다.
  이 실패만으로 업무 결함을 탐지했다고 표현하지 않는다.
- 두 번째 역할 `/root/flutter_implementation`은 이 초기 실패와 기준 고정 이후 배정했다.
  고정 테스트·명세를 수정할 수 없으며 구현과 플랫폼 설정만 담당한다.
- `.local/flutter-auth-red-01/result.json`: 공용 검사 잠금 대기 후 기존 검사기가 Spring을
  시작하려다 종료했다. 기존 미리보기가 사용하는 18082 포트와 겹쳤다. 인수 검사는 실행되지
  않았으므로 성공한 red로 계산하지 않는다. 실패 실행과 원래 후보 소스를 보존했다.
- 검사 연결에 `service_gate.py --rust-only`를 추가해 Spring 비교가 필요 없는 인증 검사는
  Rust만 실행한다. 원본 비교 suite에는 이 옵션을 거절한다. 비정상 서버 종료 때도 DB 정리를
  계속하도록 cleanup을 수정했다. `.local/flutter-auth-red-02/`는 첫 실행의 미구현 후보를
  그대로 복사해 재검사한다. 다른 작업의 공용 잠금은 우회하지 않는다.
- 사용자는 다른 채팅에 조율 메시지를 보내는 대신 공용 DB 검사가 끝나기를 기다리도록 선택했다.

## 환경

- `python3 scripts/flutter_setup.py --check`: 종료 0. 공식 SDK SHA-256과 실제 Flutter 3.47.8,
  포함 Dart 3.13.7을 확인했다. 전역 SDK/PATH는 바꾸지 않았다.
- pub.dev 의존성은 프로젝트 전용 `.local/flutter-pub-cache`에 잠금 파일과 함께 준비했다.
- Android SDK36 r02와 NDK28.2.13676358은 공식 repository XML SHA-1을 대조해
  `.local/flutter-android-sdk`에 설치했다. 로컬 SHA-256도 `.local/flutter-setup/android-sdk.json`에
  기록했다. 기존 SDK 패키지는 읽기용 심볼릭 링크로 재사용하고 원본을 수정하지 않았다.
- Flutter 기본 설정과 Gradle cache는 `scripts/flutter.sh`로 `.local`에 격리한다.
- Xcode는 설치되지 않았고 Command Line Tools만 확인했다. iOS 실제 빌드 성공을 주장하지 않는다.
- 관련 지식 문서 18개를 `.local/flutter-knowledge/context.md`와 해시 manifest에 고정했다.
  이 자료 제공 기록 자체가 의미 적용이나 앱 검증 성공을 증명하지 않는다.

## 원본 대조에서 추가한 통화 회귀

기존 Flutter 207개가 통과한 뒤 원본을 다시 대조해 미국 종가 USD와 평균 매입가 KRW의
입력 경계 문제를 발견했다. 서버 `averagePurchasePriceCurrency`와 원본 보유 편집기는
원화 원가를 사용한다. 종목 통화 USD를 평균 원가 통화로 사용하면 계산에 잘못된 원가를 넘긴다.

첫 테스트 작성 역할에 별도 회귀를 재배정했고, 원본 DTO/SQL을 확인해
`clients/flutter/review_test/currency_contract_test.dart`의 3개 검사를 작성했다.
원래 고정한 12개 기준 파일은 수정하지 않았다. 추가 기준 해시는
`9a7c7cd3be47239c3e7479f833b8af127380a1e16f32f1f683ea909d5943c111`다.
`.local/flutter-currency-red-01/`에서 실제 종료 1, 1개 통과·2개 실패를 확인한 뒤
구현 담당에게 USD 참고 종가와 명시적 KRW 평균 매입가 입력을 분리하도록 요청했다.
추가 검증은 최초 207개와 이 3개를 함께 실행한다.

이 추가 실패의 실행 전 소스 해시와 로그를 보존했다. 최종 검사에서 입력 해시의
실행 전후 일치도 별도로 확인한다. 이전 실패를 수정 후 성공으로 덮어쓰지 않는다.


## 최종 구현과 독립 승인

검색·게스트/회원 포트폴리오·뉴스/콘텐츠/인물·캘린더·내 정보의 전체 사용자 앱과
Rust 모바일 로그인 확장(`004_mobile_auth_codes.sql`)을 구현했다. 네이티브 로그인은 외부 인증
세션, S256 PKCE, 고정 callback, 60초 1회용 코드와 기존 세션 쿠키를 연결한다.
전체 구현과 직접 의존성은 `clients/flutter/README.md`, `runs/012-flutter-implementation.md`에 있다.

사용자가 요청한 테스트 작성 → 다른 구현자 → 다른 검증자 순서를 지켰다. 기존 v1 고정 기준을
바꾸지 않고 보강 기준을 별도 추가했다. 검증 역할이 발견한 화면 폐기 뒤 게스트 AI POST와
로그아웃/탈퇴의 전역 세션 정리 누락은 독립 red 후 구현자가 고쳤다. 실제 Web에서 발견한
내부 뉴스 상대 URL 문제는 첫 테스트 작성자에게 돌려보내 15개 회귀를 작성했다.
`.local/flutter-internal-news-red-01`은 실제 8 통과/7 실패이며 구현 전 소스·기준 해시를 보존했다.
최종 수정 후 혼합 관련자료 → 내부 뉴스 상세 → 뒤로가기의 선택/입력/스크롤 복원도 확인했다.

| 최종 실제 실행 | 결과 |
| --- | --- |
| 독립 `.local/flutter-independent-03` | analyzer·238/238·release Web 모두 종료 0, 고정 기준/소스 불변 |
| 서버 `.local/flutter-auth-green-02` | 모바일 인증 23 + 기존 OIDC 13 + core 80 = 116/116 |
| 기존 `python3 scripts/check.py verify` | 종료 0, 실제 HTTP/DB 인수 46개 및 기존 Rust/Python 검사 |
| 피드백 lifecycle | 재시작 보존·저장 장애 500/미삽입·복구·로그 입력 미노출 4개 통과 |
| Android debug APK | 빌드·설치·실행 성공, 전용 Android13에서 실제 서버 검색·종목 선택 및 입력 위젯 계층의 저장 종가 120.2500 확인 |

서버 초기 red02는 미구현 후보에 실제 기존웹회귀 1 통과/모바일 22 실패였다.
잠금 대기와 Spring 포트 충돌로 검사하지 못한 red01/green01은 실패·대기 기록으로 유지한다.
검증 중 도구/준비 오류도 독립 기록에 남겼으며 제품 결함 탐지로 세지 않았다.
USD/KRW 원가와 내부 뉴스 보강 red 및 mutation 실패 증거 역시 수정 후 결과로 덮어쓰지 않았다.

독립 승인과 해시: `runs/012-flutter-verification.md`,
`experiments/flutter/review/independent-manifest-final.json`.
최종 APK SHA-256은 `e5c17878246238ef3e457465811a2cce5bdf14b6ecc60f00e32307cdec8299cf`다.
Android 최종 실서버 화면 보완은 조정자가 실행했으며 독립 검증자의 결과와 구분한다:
`experiments/flutter/review/android-coordinator-smoke.json` 및 `android-final-live-price.png`.
첫 UI hierarchy 캡처는 준비 전 실패해 재시도했고, 제품 실패로 세지 않았다.
최종 스크린샷에는 선택 종목·날짜·통화가 보이나 값 필드가 하단 탐색에 걸쳐 숫자는 잘린다.
120.2500은 실제 EditText 접근성 계층으로 확인한 값이며 스크린샷 육안 증거와 구분한다.

실 Google 계정·실기기 외부 callback·iOS 빌드/화면·실 AI 제공자·회원 전체 UI CRUD E2E·운영 배포는
미검증이다. 회원 기능은 고정 위젯 경로 검사와 실제 서버 HTTP/DB 검증의 결합 증거다.
Xcode 부재로 iOS 빌드는 수행하지 못했다. 로컬 통과를 운영 인증/배포 완료로 표현하지 않는다.

전용 fixture는 stop 파일로 종료했고 자기 DB 삭제가 성공했다. 전용 emulator-5560만 종료했다.
공용 PostgreSQL과 다른 채팅의 서버/기기는 중단하지 않았다. 기존 Android/지식베이스/iOS/WebView
미커밋 작업을 보존했으며 커밋/배포는 수행하지 않았다. 최종 합산 근거와 정리는
`experiments/flutter/evidence/final-verification.json`에 남긴다.

초기 Spring 포트 충돌 실행에서 남았을 가능성이 있는 `daynomy_2f22e50bc0_service_test`는
공용 잠금을 각각 45초/300초 기다려도 획득하지 못해 검사·삭제하지 않았다. 이 DB의 소유권을
확정한 것으로 표현하지 않는다. 다른 작업에 메시지를 보내거나 프로세스를 중단하지 않았다.
현재 성공 fixture DB와 green02 DB 삭제는 각각 종료 0이며 이 미확인 잔여 후보와 구별한다.
근거: `experiments/flutter/evidence/cleanup-first-auth-run.json`.
독립 최종 manifest 106개 중 README만 최종 수치/명령/미검증 안내로 갱신했으며 나머지 105개는
그대로다. 고정 기준과 제품 소스 53개 및 서버 snapshot 79개도 최종 해시가 일치한다.
