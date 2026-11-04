# Flutter 독립 구현 역할 기록

2026-10-28 KST. 역할 `/root/flutter_implementation`은 고정 테스트 작성 역할의 red 실행 이후
두 번째 역할로 구현했다. 별도 검증 역할의 최종 판정을 대체하지 않는다. 기존 Android/WebView/
지식베이스 미커밋 작업과 `reference/`를 수정하지 않았다. 추가 서브에이전트는 만들지 않았다.

## 근거와 변경

`AGENTS.md` 시작 문서·과거 구현/비교/자동화 기록, `spec/flutter/{test-contract,native-auth,design}.md`,
고정 테스트와 `knowledge/contracts/stock-search-price.json`, `.local/flutter-knowledge/context.md`의
공통 4개·Flutter 6개·서비스 8개 문서를 읽었다. 원본 frontend의 stocks/portfolio/calendar/news/
search/stock-content/people API·타입, backend의 포트폴리오 입력 DTO·분석 이력·캘린더 Controller·
뉴스 검색 DTO·관련자료 DTO를 직접 대조했다. preflight 자체 재실행에서 원본 29/29 해시가 일치했다.

- L01/L02: exact JSON 재귀 파서·BigInt 정수 검사로 ID 안전 범위와 금액 원문을 보존한다.
  중복 키와 비유한 숫자·잘못된 중첩 DTO/enum을 거절한다. 계산은 서버 응답을 사용한다.
- L03/L04: 누락/null을 필드별 검사하고 거래일·종가 날짜를 문자열로 유지한다.
  원본처럼 decoder의 종가 날짜 달력 유효성·양수 가격을 임의 강화하지 않는다.
- C01–C05: HTTP code/message 보존, CSRF headerName/token 확인, GET 401 single flight와 한 번 재시도,
  모든 쓰기의 자동 재전송 금지, timeout/크기 제한, 실제 abort와 화면 세대 검사를 연결했다.
- auth/storage: 외부 UA PKCE·고정 callback, 메모리 cookie jar와 same-origin web 어댑터,
  세션 상실/계정 정리 때 활성 전송 취소와 회원 캐시 삭제, 재시작 시 재인증 정책을 적용했다.
- UI: ui-ux-pro-max를 읽고 금융 앱의 5탭·시스템 한국어 글꼴·8px 간격·실패/빈 상태·최소 48dp 버튼·
  SafeArea·좁은/넓은 탐색·어두운 테마·스크롤 폼·상태 Semantics를 적용했다.
  검색어/수량/가격은 탭 이탈 후 복원하고 이전 전송은 취소한다.

`clients/flutter/lib/`는 모델/정확 JSON·API·저장소·검색 상태·native auth·플랫폼 전송·위젯으로 나눈다.
5탭은 실제 사용자 endpoint 34개와 연결한다. 게스트 보유 CRUD/평가/AI, 회원 거래/보유 CRUD·
성과/거래 이력/AI 이력, 뉴스/통합검색/출처/인물, 월/최대12개월 범위 캘린더, 회원/피드백을 구현했다.
Rust는 기존 OIDC에 서명 모바일 state를 추가하고 별도 1회 코드 교환을 트랜잭션으로 구현한다.
새 migration은 기존 003 번호를 피한 `004_mobile_auth_codes.sql`이다.

직접 Flutter 의존성은 flutter SDK, crypto 3.0.7, flutter_web_auth_2 5.1.0,
url_launcher 6.3.2, web 1.1.1이다. Rust 직접 의존성을 추가하지 않았다.
자체 crate의 forbid(unsafe_code)를 보존했다. 네이티브 플러그인의 내부 unsafe 부재를 의미하지 않는다.

## 자체 실행과 실패/수정

테스트/spec/인수 기준은 수정하지 않았다. 아래 로그는 로컬 자체 실행이며 root가 고정 기준 해시와
최종 후보 소스 해시를 별도로 확인한다. `/tmp` 로그는 비밀 요청 내용을 기록하지 않는다.

| 실행 | 결과 | 근거/수정 |
|---|---|---|
| `python3 scripts/check.py preflight` | 종료 0, 원본 29/29 | `/tmp/daynomy-flutter-preflight.log`, DB 동작 검증 아님 |
| `cargo fmt`, `cargo check --locked --offline` | 종료 0 | 기존 crate/서버 컴파일, HTTP/DB는 root 직렬 검사 대기 |
| 첫 Flutter test | 컴파일 실패 | 선언 화살표·괄호·currency 필드 이름 충돌 수정 |
| 다음 Flutter test | 환경 실패 | sandbox의 loopback 테스트 소켓 거절, 승인된 소켓 허용 실행으로 전환 |
| 실제 Flutter test 04 | 204 통과/3 실패 | deterministic state entropy 길이 분리, calendar ALL scope 유지, 거래 dialog submit의 스크롤/hit 영역 수정 |
| 실제 Flutter test 05 | 종료 0, 207/207 | `/tmp/daynomy-flutter-test-05.log` |
| 실제 Flutter test 06 | 종료 0, 207/207 | 세션 취소/원화 표기/범위 캘린더 등 후 `/tmp/daynomy-flutter-test-06.log` |
| 첫 analyzer | 환경 실패 | `.dartServer` 읽기전용 홈 경로, 소스에서 `ANALYZER_STATE_LOCATION_OVERRIDE` 확인해 `.local/`로 격리 |
| analyzer 02/03/04 | 종료 0, No issues found | `/tmp/daynomy-flutter-analyze-0{2,3,4}.log` |
| Web release build 01 | 컴파일 실패 | external JS interop tear-off를 명시 closure로 수정 |
| Web release build 02 | 종료 0 | `/tmp/daynomy-flutter-web-build-02.log`, wasm dry run도 성공 |
| Android debug build 01 | 버전 검사 실패 | Flutter3.47 최소 Gradle8.14/AGP8.11.1/KGP2.2.20 확인. 검사 skip 금지 유지 |
| Android debug build 02 | 종료 0, APK 생성 | `/tmp/daynomy-flutter-android-build-02.log`, 212.4초. Gradle8.14.3/AGP8.13.0/Kotlin2.2.20. 향후9.x권고 warning 남음 |

Android 설정은 stable auth 5.1.0의 AGP9 미지원 README와 Flutter 로컬 최소 버전 코드를 함께 읽고
선택했다. Android compile/target36·min24, iOS deployment17.4, 고정 URL scheme/activity·taskAffinity,
외부 UA와 debug의 명시 loopback HTTP 예외를 설정했다. SDK/NDK는 root가 전용 `.local/`에 준비했다.

## 남은 독립 검증과 한계

root가 공용 DB 잠금 안에서 기존 미구현 red와 최신 Rust 네이티브 인증 HTTP/DB green·기존 회귀를
실행한다. 다른 채팅의 DB 프로세스를 중단하거나 직접 우회 서버를 띄우지 않았다.
실 Google 계정 인증/실기기, iOS 빌드(Xcode 부재), 실제 AI 제공자 응답·전체 접근성 실기기 검증은
미확인이다. 고정 fake transport와 widget 테스트를 실제 DB/외부 제공자 성공으로 확대하지 않는다.

root 원본 대조에서 USD guest의 참고 종가와 KRW 평균 매입가 입력 분리 회귀를 독립 테스트 역할에
추가 배정했다. 그 추가 red 확인 후 해당 수정을 반영하고 새 최종 검사 결과를 이어 기록한다.


## 최종 자체 검사와 인계

추가 독립 통화 계약의 실제 red 실행 후 `holding-average-krw`를 추가했다. 미국 게스트는 USD 참고
종가와 KRW 원가를 분리하고, KRW 입력이 없으면 보유를 추가하지 않는다. 평균 원가 행도 항상 KRW다.
추가 테스트 SHA-256은 `9a7c7cd3be47239c3e7479f833b8af127380a1e16f32f1f683ea909d5943c111`로 유지했다.

- `flutter test test review_test --reporter expanded`: 종료 0, **210/210**. `/tmp/daynomy-flutter-test-07.log`.
- `flutter analyze`: 종료 0, **No issues found**. `/tmp/daynomy-flutter-analyze-final.log`.
- `flutter build web --release`: 종료 0. `/tmp/daynomy-flutter-web-build-final.log`.
  wasm dry run 성공. CupertinoIcons 미사용 글꼴 경고는 남아 있으나 MaterialIcons는 정상 포함됐다.
- `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:18081`: 종료 0, 11.5초.
  `/tmp/daynomy-flutter-android-build-final.log`. 결과 `clients/flutter/build/app/outputs/flutter-apk/app-debug.apk`.
  이 APK는 로컬 개발 서버 주소를 사용한다. 운영 배포/서명 완료가 아니다.

아래는 인계 시 코드·직접 의존성 파일의 SHA-256 목록이다. 전체 플랫폼/검사 기준과 최종 검증 소스 해시는
조정자의 별도 checker가 관리한다. 독립 검토에 따라 수정하면 새 해시와 결과를 이어 기록해야 한다.

```text
app/migrations/004_mobile_auth_codes.sql 9e6363d71340a4e58fec6dc165b15f44c76eb6424878c43be3bc951ac13488c8
app/src/main.rs 6b8637836f7ba463a410fc44944760805d0fca9bcb0c3d6300c8eb1f9887c605
app/src/service_auth.rs ca50065e928882961f8cd932c404e61aee6bc38df0ab9637f52cfc0e3cd331f7
clients/flutter/lib/daynomy.dart 2994385d808adca3a0dea90c5fbca625b8c32259dba8e2473732770a7ce8d669
clients/flutter/lib/main.dart 113c649655d6d6874a143cc429675e719d2604cec91d4a0842a0fcca95461ef4
clients/flutter/lib/src/api.dart 15139f9be6f906e68d52860cffecd08e192774ef71da0e6482478a0894de9a16
clients/flutter/lib/src/app.dart 133122982bf88a3b1e826b0350dafbbf050875353d3a20dc282703820742b6ba
clients/flutter/lib/src/exact_json.dart 2b934e84b1b259011557efcbb924f94df5ee46328cd0dc2f9524279452d8d251
clients/flutter/lib/src/native_auth.dart aff61300a9d3e851f3bbe4e36f17bc7579e1ed2dc85dc4960e5aba48fbcc3385
clients/flutter/lib/src/repository.dart 1cbeb298e7bb7298850db3dfedbcaae2693979cdeb2dfb239794853df75cd44b
clients/flutter/lib/src/search.dart b1230b1630af1630ea0e435c67bb4c83500e95abb9fd65eb31957bd3de174162
clients/flutter/lib/src/transport.dart 2e1090ec7f2a28c084e28a53dbfdf23dc9bb6da16a2fb26cab0b0e7182c76ec4
clients/flutter/lib/src/transport_native.dart c814d661b617c1c32fd0d9838807857858bb585388a13536020d67c452856dc9
clients/flutter/lib/src/transport_web.dart 5a417ba8aa20cdfee66b81b6f40c76d57c812c7aa8b7ab7344d48ea249ab1ef8
clients/flutter/pubspec.lock 78ec894b60a655c0bf60e8d1a29f180fc2b2f7991d755a7f6dcfeac013a7057d
clients/flutter/pubspec.yaml f5e6f170091017b2089e58f5b40b239b330b8857fbab833d89b91e8c2694b589
aggregate 5e316aae989e96f0632d068abb42bc8f40a19e50590233efea62db59f27b1d44
```

인계 직전 Rust 추가 자체 확인: `cargo clippy --locked --offline -- -D warnings` 종료 0,
`cargo test --locked --offline` 종료 0, 29 통과/0 실패/0 ignored다.
로그는 `/tmp/daynomy-flutter-rust-clippy.log`, `/tmp/daynomy-flutter-rust-tests.log`다.
이 검사는 공유 DB를 쓰지 않으며 독립 HTTP/DB 검증을 대체하지 않는다.

## 독립 리뷰의 수명 결함 두 건 수정

별도 검증 역할이 제품 결함 두 건의 실제 red를 작성한 뒤 구현 역할을 재개했다.
기준 `test/`, `review_test/`, `verification_test/`, `spec/`는 수정하지 않았다.
원본 red 로그는 `experiments/flutter/review/lifecycle-02.log`, `lifecycle-03.log`에 보존돼 있다.

1. 게스트 AI의 계산 응답을 기다리다 탭을 이탈해도 늦은 응답 뒤 AI POST를 새로 시작했다.
   `app.dart`의 포트폴리오 계산/AI에 조회 토큰과 별도의 화면 작업 토큰·세대를 두고 dispose에서
   취소한다. 계산 결과는 공유 상태를 다시 읽지 않고 해당 요청 결과를 사용하며, 각 await 뒤와
   다음 AI POST 직전에 mounted·세대·취소·현재 보유 snapshot 일치를 확인한다.
2. 로그아웃/탈퇴 완료를 자식 페이지의 mounted 조건으로 막아 다른 탭으로 이동하면 부모의 회원
   상태가 남았다. 성공한 세션 종료 콜백을 페이지 수명과 분리하고, 부모가 자신의 mounted를 확인한다.
   자식의 화면 setState만 자식 mounted 조건을 유지한다. 거래 쓰기의 자동 재시도 정책은 바꾸지 않았다.

첫 재검사는 AI 회귀를 통과했지만 검증자가 추가한 로그아웃 회귀를 실패했다
(`/tmp/daynomy-flutter-lifecycle-fix-test.log`). 두 번째 수정 후
`flutter test test review_test verification_test --reporter expanded`는 종료 0,
**223/223** 통과했다(`/tmp/daynomy-flutter-lifecycle-fix-test-02.log`, 실제 HTTP timeout 포함 25초).
`flutter analyze`는 종료 0, No issues found(`/tmp/daynomy-flutter-lifecycle-fix-analyze-02.log`).
최종 Web/APK 재빌드 로그는 `/tmp/daynomy-flutter-lifecycle-fix-web-02.log`,
`/tmp/daynomy-flutter-lifecycle-fix-apk-02.log`에 남긴다.

이번 제품 수정은 `clients/flutter/lib/src/app.dart`만이며 SHA-256은
`8cc228a21c5c4ddaf023cc899536efdb0a064ccf47b910974b5a8f038bce6172`다.
이전 인계 표의 해당 파일 해시는 과거 후보로 보존하고, 새 후보의 독립 재확인은 조정자가 배정한다.

최종 재빌드도 두 명령 모두 종료 0이다: Web release 31.1초, Android debug APK 20.9초.
정확한 시간은 각 원본 로그의 Flutter 출력값을 기준으로 하며, iOS/실 Google 검증의 한계는 그대로다.

## 독립 실서버 검증의 내부 뉴스 URL 계약 수정

별도 검증자가 Web+실제 Rust의 정상 200 혼합 종목 자료에서 내부 뉴스 상대 URL 때문에 전체 목록이
형식 오류가 되는 결함을 발견했다. 앞서 수동 AssetContentRequest의 절대 URL 제약만 읽고,
자동 `AssetContent.createInternalNews`가 `/news/{id}`를 생성하는 경로를 놓쳤다.
원본 frontend stock-content/api.ts:26–35는 `new URL(value, 'https://daynomy.local')`로
상대 URL을 수용하고, trim 후 `//` 및 비 HTTP(S) scheme을 거절한다. 원본 UI는 INTERNAL_NEWS를
별도 뉴스 링크로 표시한다. 이 근거를 직접 대조한 뒤 추가 독립 테스트 actual red까지 제품 수정을 보류했다.

추가 기준은 `review_test/internal_news_contract_test.dart`이며 SHA-256은
`c35acd74985aa0326a70a1e047d057c1e365c5da492cf87e296cceebda6cce61`이다.
root가 보존한 `.local/flutter-internal-news-red-01`은 8 통과/7 실패, 종료 1이다.
해당 파일과 기존 test/spec/review_test/verification_test는 구현 역할이 수정하지 않았다.

제품 수정은 `lib/src/repository.dart`, `lib/src/app.dart` 두 파일이다.
종목 자료 decoder의 URL 검사는 원본의 HTTP(S)/안전한 상대 URL 경계를 유지한다.
유효한 canonical INTERNAL_NEWS `/news/<positive-safe-id>`는 기존 앱 뉴스 상세를 연다.
외부 절대 HTTP(S) 출처는 기존 런처를 사용한다. 잘못된 내부 ID·미지원 상대 경로는 DTO 목록을
숨기지 않고 안내만 표시하며, 잘못된 뉴스 API나 외부 런처 호출을 시작하지 않는다.

최종 자체 실행은 모두 종료 0이다.

| 명령 | 결과 | 로그 |
|---|---|---|
| `flutter test test review_test verification_test --reporter expanded` | **238/238**, 실제 HTTP timeout 포함 25초 | `/tmp/daynomy-flutter-internal-news-test.log` |
| `flutter analyze` | No issues found, 4.3초 | `/tmp/daynomy-flutter-internal-news-analyze.log` |
| `flutter build web --release` | build/web 생성, 16.1초 | `/tmp/daynomy-flutter-internal-news-web.log` |
| `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:18081` | debug APK 생성, 8.7초 | `/tmp/daynomy-flutter-internal-news-apk.log` |

인계 소스 SHA-256:

```text
clients/flutter/lib/src/app.dart 56bc7484e381eb925aca768d184620a07caf1d9ade92e3a240d05a38173b1b9f
clients/flutter/lib/src/repository.dart b2c68d747994a3a82a3536fa76c5972610da2c5c06b6fc4b53059e509fffa4c0
```

추가 실제 Web+Rust 연결 재확인과 독립 최종 판정은 조정자/검증 역할이 수행한다.
