# Flutter 독립 검증 기록

2026-10-28 KST. 세 번째 역할 `/root/flutter_verification`. 제품·고정 v1 기준·원본을 읽기 전용으로
검토하고 별도 `clients/flutter/verification_test/` 및 `experiments/flutter/review/`만 추가했다.
제품 수정은 별도 구현 역할이 수행했다. root가 전체 완료 판정을 담당한다.

## 기준과 직접 대조

AGENTS 시작 문서와 Flutter test-contract/native-auth/design, 선택 KB 18개를 읽었다.
자체 `python3 scripts/check.py preflight` 종료 0, 원본 29/29 해시 일치다.
선택 KB 18/18과 합친 context 해시를 다시 확인했다. 원본 TS의 portfolio API/DTO,
calendar API, news list/search, stock-content API, 공통 client를 직접 대조했다.
검색/종가·34개 사용자 endpoint·금액/ID/취소/세션·UI 연결 및 Rust 모바일 OAuth 소스를 검토했다.
근거 해시는 `experiments/flutter/review/independent-manifest-01.json`에 보존한다.

- USD 최근 종가·거래 단가와 KRW 평균 원가를 구별한다. 독립 통화 보강 3개는 고정 SHA
  `9a7c7cd3be47239c3e7479f833b8af127380a1e16f32f1f683ea909d5943c111`를 유지했다.
- API GET 401 한 번 재시도/single flight, 변경 요청의 CSRF·자동 재전송 금지,
  native HttpOnly 메모리 jar·동일 origin·경로/secure/만료, 실제 전송 abort/세션 epoch를 대조했다.
- 회원 거래/보유 CRUD·성과/이력/분석, 게스트 계산/AI, 뉴스/검색/콘텐츠/인물,
  월/기간 캘린더, 프로필/닉네임/탈퇴/로그아웃/피드백이 실제 repository에 연결된다.
- native callback/PKCE·Android activity·iOS URL scheme/SPM 설정을 읽었다.
  설정 정적 대조는 실제 Google/iOS 실행 성공을 뜻하지 않는다.

## 실제 검사와 대표 결함 주입

| 실행 | 결과 | 증거 |
| --- | --- | --- |
| `flutter_check.py --phase verify --baseline .local/flutter-red-01/result.json --output .local/flutter-independent-01` | 종료 0: analyzer/210 tests/release Web, 입력 해시 불변 | `.local/flutter-independent-01/{result.json,*.log}` |
| `flutter test verification_test --reporter expanded` | 종료 0: 초기 독립 11/11 | `experiments/flutter/review/independent-tests-01.log` |
| lifecycle 보강 02 | 종료 1: 5 통과/게스트 AI 수명 1 실패 | `experiments/flutter/review/lifecycle-02.log` |
| lifecycle 보강 03 | 종료 1: 5 통과/수명 2 실패 | `experiments/flutter/review/lifecycle-03.log` |
| `flutter_check.py … --output .local/flutter-independent-02` | 종료 0: analyzer/223 tests/release Web, 입력 해시 불변 | `.local/flutter-independent-02/{result.json,*.log}` |
| 격리 복사본 JSON duplicate 허용 mutation | 종료 1, 의도한 1개 실패·47 통과 | `mutation-02-duplicate-json-key.log` |
| 격리 복사본 쓰기401 refresh mutation | 종료 1, POST/PATCH/DELETE 3개 실패·26 통과 | `mutation-02-retry-write-on-401.log` |

독립 13개는 native loopback HTTP 6개와 반응형/수명 위젯 7개다. 실제 `HttpServer`로
HttpOnly cookie·Path/Domain/Secure 격리·clearSession, 지연 헤더와 스트림 중 cancel,
세션 종료 후 늦은 Set-Cookie, redirect 미추적·외부 origin 거절·4MiB 초과,
실제 25초 timeout을 확인했다. 위젯은 375×812, 글씨 2배/다크, 812×375 가로,
1280×800/글씨 2배와 5탭·늦은 검색 완료를 검사한다. 완전한 스크린리더 실기기 검사는 아니다.
UI 검토에는 `ui-ux-pro-max`의 Flutter 큰 글씨/반응형 규칙과 앱 체크리스트를 사용했다.

검사 준비 중 로그 폴더 누락/프로젝트 cwd 오류 두 번을 교정했다. 첫 mutation 실행은
복사본의 package_graph.json 누락으로 테스트 전 도구 실패였다. `mutation-*.log`와
`mutations.json`을 그대로 보존하며 결함 탐지로 세지 않았다. 생성 파일을 보완한
두 번째 복사본에서 실제 테스트 실패를 확인했다. 제품 lib와 고정 test 해시 불변이다.

## 발견·수정·추가 기준

1. P2: 게스트 AI 계산 대기 중 탭을 떠나면 폐기된 화면이 늦은 계산 완료 후
   새 `/api/portfolio/analysis` POST를 시작했다. 폐기 후 계산 상태 저장도 생략돼 빈 assets를 보냈다.
   독립 red를 보존하고 구현자가 계산/AI 취소 token·세대·입력 snapshot·각 await 뒤 생존 검사를 추가했다.
2. P2: 로그아웃 대기 중 탭을 떠나면 204 뒤 `mounted` 검사로 전역 세션 정리가 생략돼
   부모 profile/닉네임이 회원으로 남았다. 탈퇴도 같은 분기였다. 독립 red 뒤 구현자가
   성공한 세션 종료 처리를 페이지 수명과 분리했다. checker02에서 두 회귀 모두 green이다.
3. P2 (실제 Web에서 추가 발견): `/api/assets/910001/contents`는 INTERNAL_NEWS의
   `/news/910001` 상대 URL과 정상 YouTube URL을 함께 반환한다. 원본 `stock-content/api.ts`는
   상대 내부 URL을 허용하지만 Flutter는 절대 HTTP만 허용하는 safeUrl 검사로 전체 DTO를 거절했다.
   UI의 관련 자료 전체가 형식 오류가 됐다. 원본 해석·기준 보강이므로 root에 근거를 보내
   첫 테스트 작성 역할에 추가 red 배정을 요청했다. 근거는
   `related-content-actual-01.json`/`related-content-evidence-01.json`이다.
   이 항목 해결 전 전체 승인은 보류한다.

## 서버 실제 HTTP/DB와 브라우저

root가 공유 DB 잠금 안에서 실행한 `.local/flutter-auth-green-02`의 원시 결과를 읽었다.
모바일 인증 23 + 기존 OIDC 13 + core 80 = **116/116**, 실패 0이다.
현재 app 후보와 검사한 전체 소스 79/79 해시가 일치한다. core에는 실제 거래 추가/수정/삭제,
보유 수정/삭제·원장 replay/rollback·동시 매도·회원 격리·USD·성과/닉네임/탈퇴가 포함된다.
모바일은 PKCE·해시 저장·single-use/expiry/concurrency·활성 회원·CSRF 예외 한정·기존웹회귀다.
이는 로컬 RSA/JWKS fixture이며 실 Google 계정 로그인으로 표현하지 않는다.
root 실행 증거는 `experiments/flutter/evidence/backend-green-v1.json`에 있다.
검증 역할은 별도 DB 검사를 중복 실행하거나 다른 fixture/프로세스를 중단하지 않았다.

root의 전용 실제 Rust/DB fixture `.local/flutter-backend-preview-01`(18081)이 serving이고
같은 DB에서 필수 `check.py verify` 종료 0임을 result와 로그에서 확인했다.
검증 역할의 Web preview는 18300→18081 same-origin proxy다. CUA로 release Web을 실제 실행했다.

- Harness 검색→Alpha 선택→최근 저장 종가 120.2500 KRW/2020-01-03→수동 평균가 100.00/2주 추가.
  게스트 서버 계산은 매입 200.00, 평가 240.50, 손익 40.50, 수익률 20.25를 표시했다.
- 뉴스 목록/상세의 본문·출처·키워드·시장분석, 뉴스 검색/통합 콘텐츠, 주요 인물/게시물을 확인했다.
- 2026-10의 합성 CPI 일정 및 과거 반응 표본 0/미확인 수익률을 확인했다.
- 공개 피드백을 실제 CSRF 흐름으로 전송해 성공 문구와 입력 비움을 확인했다.
  내용/쿠키/토큰은 실행 기록에 저장하지 않는다.
- 실제 회원 브라우저 로그인/회원 UI CRUD는 이 브라우저 검증에서 수행하지 않았다.
  고정 widget 경로 검사와 서버 실제 CRUD 증거를 구분한다.

화면은 `experiments/flutter/review/web-live-{guest-calculation,news-detail,people,calendar,feedback-success}.png`다.
초기 오프라인 XHR 502/재시도는 `web-offline-search-error.png`에 보존했다.

## Android와 미확인 범위

전용 emulator-5560(Android13,1080×1920,density420≈411dp)에 APK를 설치·실행하고
초기 오프라인 5탭 탐색/실패·재시도 화면과 접근성 계층을 수집했다.
`experiments/flutter/review/android-offline-*.{png,xml}`이 증거다.
이후 CUA inventory에는 headless emulator 창이 노출되지 않았다. root가 같은 전용 기기에서
수정 APK의 실제 HTTP UI를 별도 보완한다. 서로 다른 기기/adbserver를 종료하지 않았다.
초기 APK 해시는 `f8dfd2c5acbeb19f575bc78499286024fd3049f06ad113017681ffc933f578b7`다.
checker02 시점 수정 APK는 `e59accf84d5e2fd4c118e32c5f186c1135f9d4d3eb312a739b7c20ce45bfb40a`,
app.dart는 `8cc228a21c5c4ddaf023cc899536efdb0a064ccf47b910974b5a8f038bce6172`다.
이후 수정 시 이 해시를 최종 후보 해시로 재사용하지 않는다.

Xcode/iOS SDK 부재로 iOS 빌드·화면·실기기 미확인. 실 Google·외부 인증세션의 플랫폼
callback 완주·실제 AI 제공자 응답·Web XHR 취소의 동적 지연 재현·완전한 실기기 접근성은 미확인이다.
현재 source/test 실행 성공 범위와 운영 배포·실서비스 인증은 구별한다.

## 원본 URL 보강 인계 (후속)

첫 테스트 작성 역할이 기존 v1을 보존하고 `review_test/internal_news_contract_test.dart` 15개를 추가했다.
SHA `c35acd74985aa0326a70a1e047d057c1e365c5da492cf87e296cceebda6cce61`다.
원본은 내부 뉴스 링크를 같은 사이트 새 탭으로 열었다. Flutter 앱 내부 detail navigation은 이식 방식이다.
다른 상대 URL까지 decoder에서 거절하는 강화안을 채택하지 않고 원본 허용 경계와 실행 경계를 분리했다.
root가 구현 전 실제 red 8 통과/7 실패를 `.local/flutter-internal-news-red-01`에 보존한 뒤
다른 구현자에게 수정을 넘겼다. 수정 코드는 상대 URL 수용·정확한 `/news/<양의 safe ID>`만
앱 상세로 연결·HTTP(S) 외부 링크·미지원 상대 경로 안내로 나눈다.

추가 실제 Web 검사에서 게스트 보유 수정(3주·평균105.50 KRW)과 확인 후 삭제/빈 상태도 확인했다.
`web-live-guest-edited.png`와 `web-live-375-guest-empty.png`가 증거다.
필수 피드백 인수 raw report에는 46개 실제 HTTP/DB 검사, 종료0/complete=true가 기록돼 있다.
위 수동 재시작/장애 검사는 이 46개 자동 인수 검사와 구별한다.

## 최종 독립 판정

최종 `flutter_check.py --phase verify --baseline .local/flutter-red-01/result.json
--output .local/flutter-independent-03`는 종료 0이다. analyzer 4.86초, 전체 **238/238**
(기존207 + 통화3 + 검증역할13 + 첫 작성자의 내부뉴스15) 27.69초, release Web 15.36초다.
고정 v1 기준 및 보강 기준·후보 소스의 실행 전후 일치를 확인했다.
`experiments/flutter/review/independent-manifest-final.json`에 final checker·37개 소스,
4개 보강파일, 플랫폼/제품/검사/APK 106개 경로의 해시를 보존했다.

- 최종 app.dart: `56bc7484e381eb925aca768d184620a07caf1d9ade92e3a240d05a38173b1b9f`
- 최종 repository.dart: `b2c68d747994a3a82a3536fa76c5972610da2c5c06b6fc4b53059e509fffa4c0`
- 최종 APK: `e5c17878246238ef3e457465811a2cce5bdf14b6ecc60f00e32307cdec8299cf`

최종 release Web을 다시 열어 실제 관련자료 혼합 목록이 표시되고, INTERNAL_NEWS 클릭이
외부 창 없이 같은 앱의 실제 뉴스 본문/키워드/시장분석으로 이동하는 것을 확인했다.
뒤로가기는 선택 종목·입력·스크롤 위치를 복원했다.
`web-final-related-content.png`와 `web-final-internal-news-detail.png`가 증거다.
발견한 3개 P2는 모두 독립 red 후 별도 구현·green·실제 화면 재검증까지 해결됐다.

root가 같은 소유 fixture/공유 DB 잠금 안에서 수행한 수동 피드백 4개도 직접 결과 파일로 확인했다:
재시작 뒤 행 보존, 저장 장애 때 500/삽입 없음, statement 오류 뒤 복구, probe 입력의 로그 미노출.
근거는 `.local/flutter-feedback-lifecycle-01/result.json`과
`experiments/flutter/evidence/feedback-lifecycle-v1.json`이다. root는 브라우저에서 제출한
/profile 피드백 행 1개도 본문을 노출하지 않고 확인했다. 과거 실행을 새 성공으로 바꾸지 않았다.

**판정: 검토한 로컬 구현·검증 범위는 승인 가능.** 실 Google 계정·실기기 외부 인증 callback,
iOS 빌드/화면, 실 AI 제공자와 운영 배포의 완료는 승인하지 않는다. 회원 전체 UI CRUD E2E는
실행하지 않았으므로 widget 경로 검사와 실제 서버 HTTP/DB의 결합 증거임을 계속 표시한다.
Android 마지막 새 APK/실서버 화면 보완은 root의 별도 실행 기록을 따른다.

검증 역할이 직접 만든 Web 탭을 닫고 18300 preview만 프로세스 신원 확인 후 종료했다.
root 소유 18081 fixture·DB·emulator-5560은 이 역할이 종료하지 않았다.
