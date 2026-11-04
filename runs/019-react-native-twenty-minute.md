# 019 — React Native 20분 이식

- 요청: 기존과 같은 독립 테스트 작성 → 구현 → 독립 검증 방식, 구현 제한20분.
- 시작: 2026-10-28 19:15:33 KST / 10:15:33 UTC.
- 제한: 19:35:33 KST / 10:35:33 UTC.
- 구현: `clients/react-native/`, 계약 `spec/react-native/`, 배정 `agents/react-native.json`.
- 역할은 실제 desktop subagent 세 개와 조정자다. 역할 JSON은 실행기가 아니다.
  모델/추론 수준은 현 대화 설정을 상속했다. 과거 iOS 역할 모델을 새 호출의 실제 값으로 주장하지 않는다.
- 원본·Rust 서버·기존 iOS/Android/Flutter/WebView 변경을 보존했다. 배포·커밋 없음.

## 구현과 범위

Expo58.0.20 / React19.3.0 / React Native0.88.0 / TypeScript6.0.2 / Node22.23.1.
npm registry/Expo 공식 SDK 자료와 `expo install` 호환 결과에 따라 설치했고 잠금 파일을 생성했다.
외부 의존성은 React/RN/Expo 런타임, Expo crypto(PKCE 난수·SHA256), 외부 인증 브라우저,
AsyncStorage(게스트 거래), safe-area-context(시스템 영역), vector-icons, status-bar,
웹 확인용 react-dom/react-native-web, 개발용 TypeScript/타입 선언이다.

- 종목: 국내/미국·주식/ETF·검색·최근 종가·수동단가 보존·거래일환율.
- 게스트: 기기 거래 저장·매수/매도·수정/삭제·십진 원장·과거 초과매도 거절·평가/손익.
- 회원: PKCE 브라우저 로그인 연결·내정보·닉네임·로그아웃·탈퇴·거래 등록·이력·
  현재 보유 메타데이터가 있는 거래 수정·BUY/SELL 거래 삭제·평가·추이·분석 조회.
- 뉴스/탐색: 허용 카테고리·1부터 시작하는페이지·상세·키워드·시장분석·뉴스/콘텐츠검색·종목자료·인물.
- 캘린더: 월이동·전체/내종목·게스트/회원·출처.
- 관리자: 뉴스 multipart 초안등록/수정/발행/거절/삭제, 피드백 상태/삭제.
  인물/후보는 조회화면이다. 실제 관리자 쓰기는 별도 검증 표를 따른다.

보유 직접 조정/삭제·opening/adjustment 원장·게스트 추이·회원 분석 폴링/이력 전용화면·
관리자 이미지·연결종목편집·인물/게시물/후보 쓰기·수집/동기화 UI·정밀차트/영상·정책/투어는 남았다.
전체 원본기능/기기검증 완료가 아니다. [상세범위](../spec/react-native/coverage.md).

## 독립 테스트와 실패 보존

1. `rn_tests`는 원본/KB/명세를 읽고 빈 core stub에27개 계약을 실행했다.
   10:17:51 UTC에21개실패/6개예외검사통과, exit1. rejection-only6개 통과는 구현 성공 증거가 아니다.
2. tests/core.test.ts SHA256
   `346c27cc3aa445f355293fbcffd87723c21d7828452af06a2748a4790be37d92` 고정 후 구현을 인계했다.
   원본테스트는 이후 변경하지 않았다. 실제 RED·stub hash는 `experiments/react-native/test-author/`.
3. `rn_core`가 API/디코더/정확한 원장/선택상태/인증/저장소를 구현해 고정27개 통과했다.
4. `rn_verifier`는 별도10개 회귀에서 저장 동시 add 소실·clear 후 부활을 실제로 발견했다.
   구현자가 직렬 큐 내부에서 현재 상태를 계산하도록 수정해 재실행10개가 통과했다.
   손상된 저장값 자동삭제는 원문보존으로 수정했다.
   이 저장소 클래스 검사는 App 자체 AsyncStorage 경로 검사가 아님을 분리한다.
5. `rn_tests`의 실제 브라우저 실행에서 native fetch를 객체 메서드로 호출하면
   `Illegal invocation`이 나는 결함을 발견했다. root가 수신자를 제거해 수정했다.
   fake transport의27개가 놓친 실제 런타임 결함이다.
6. 독립 원본대조로 뉴스0페이지/잘못된카테고리·회원요청필드·지원하지않는거래조회경로·
   분석비중누락·서버전환profile경쟁을 발견해 수정했다. 초기실패는 덮어쓰지 않는다.

## 실제 검사와 경계

- preflight29/29 원본해시일치, exit0. 기능검사 성공을 의미하지 않는다.
- `npm run typecheck`: exit0.
- `npm test`: 고정계약27/27, skip0, exit0.
- 독립regressions:10/10, skip0. 실제 HTTP와 다른 host 검사다.
- 독립실제 Rust + 별도 PostgreSQL: 공개조회·404·뉴스null·CSRF·피드백·계산·
  합성PKCE교환·회원조회·거래등록재조회·닉네임·관리자403·로그아웃15/15.
  DB효과4개: 피드백정확히1행·회원보유2주·BUY원장1행·로그아웃후refresh0행.
  Node cookie adapter를 주입했으며 RN OS 쿠키 검증이 아니다.
- `npx expo export --platform all`: web/Android/iOS Metro 번들 생성 성공, exit0.
  native 설치/APK/iOS 앱실행을 의미하지 않는다.
- Android: 격리복사본 prebuild성공. assembleDebug는180초 cap timeout,
  Gradle9.4.1 준비/플러그인컴파일까지 진행. APK성공 주장 없음.
  생성debug manifest는 local cleartext 허용, release는 HTTPS 사용.
- iOS: full Xcode존재하지만 사용 가능한 Simulator runtime목록이 비어 있다.
  실제 iOS 앱 빌드·시뮬레이터/기기실행 미검증.
- `git diff --check`(이번 tracked문서): exit0. 원본/백엔드 회귀 전체검사는 이번에 다시 실행하지 않았다.

호스트 제한 실패도 보존했다: sandbox PG 공유메모리거절, 긴Unix socket경로, localhost HTTP차단,
Expo bind/브라우저 버전 불일치. 권한승인된 전용로컬 실행·짧은tmp socket·설치된Chrome로 해결했다.
최초 registry조회 제한은 npm 네트워크승인 후 해결했다. 루트에서 npm실행한경로오류2회는
클라이언트경로로 고쳤고 오생성한 빈 루트잠금파일을 제거했다.
UI합성fixture CORS실패는 exact origin+credentials허용으로 수정한 테스트환경오류로 구분한다.

## 남은 검증

실제 Google 계정 로그인/OS쿠키 유지·공유·로그아웃, 앱프로세스 종료/재실행,
native 키보드·back gesture·screen reader·최대 Dynamic Type·다크모드·태블릿,
관리자 실제권한 CRUD·외부AI·미디어 제공자, 모든 DTO의 의미 검증은 남았다.
현재 UI는 light-theme다. 외부브라우저 callback을 쓰는 로그인은 Expo Go 대신 개발빌드가 필요하다.
쓰기401 자동재전송금지는 기존 Flutter 모바일안전정책을 따르며 원본웹과 차이를 명시했다.
민감값/실제사용자정보/토큰/쿠키/DB접속문자열을 기록하지 않는다. 모르는 비용/사용량은 추정하지 않는다.

원시증거는 `experiments/react-native/{test-author,verification,ui-verification,coordination}/`.
큰native/build/DB/cache산출물은 `.gitignore`로제외한다. 실행법은
[클라이언트README](../clients/react-native/README.md).

## 최종 통합 확인

- 최종 구현 준비: 19:32:21 KST / 10:32:21 UTC, 시작 후16분48초. 검증 종료시각은 별도 기록한다.
- 독립 브라우저 UI는 실제 Expo Web+설치된 Chrome을375×812/812×375에서 실행했다.
  합성 HTTP fixture이며 Rust HTTP15개와 구분한다. 수동단가 지연응답 보존, 게스트매수,
  modal닫힘, 보유2주, browser reload 저장복원, 거래내역, null뉴스/상세, 탐색, 일정빈상태,
  설정, 가로overflow까지12개통과. JS pageerror0·예상401을제외한consoleerror0.
  실제 프로세스종료/AsyncStorage OS동작을 browser reload로 대체해서 완료라 하지 않는다.
- 관리자 UI의실제saveNews함수를추출/Node cookie adapter로실행:6개중5개성공.
  초안multipart등록201·수정200·연결종목보존·삭제·피드백상태변경을확인했다.
  발행은Rust의외부AI provider설정없음으로500실패를보존했다. 발행성공·모든관리자CRUD완료아님.
- 원본10개뉴스분류와현재Rust필터지원3개의차이를확인해화면은전체/주식/ETF/부동산만노출한다.
  응답디코더의원본10개허용은보존했다. 해당백엔드확장은남은작업이다.
- 최종코드·패키지잠금·테스트해시는 `experiments/react-native/coordination/source-manifest.json`.
  UI검사해시는 `ui-verification/source-hashes.json`, 독립검사해시는 `verification/`에보존한다.

- 최종 UI 재검증: 19:33:02 KST / 10:33:02 UTC, 12/12통과·exit0.
  최종소스9개+고정테스트해시가현재파일과일치한다. Expo검증서버는종료했다.
- 관리자반복로그인회귀는기존유효세션이남으므로전체refresh0행조건이틀렸음을발견했다.
  최초HTTP15실행의0행결과는보존하되추가관리자흐름에서는로그아웃전후2→1로
  해당세션정확히1개제거를독립확인했다. 검증오류와수정근거는원문증거를보존한다.

- 최종 검증·기록 종료: 2026-10-28T10:34:27.918543+00:00 UTC, 시작 후18분54초(20분 제한 이내).
  독립최종소스해시/화면해시/고정테스트일치를조정자가재확인했다.
  독립실험Rust/DB는10:33:57 UTC정상종료, Expo화면검증서버도종료.
  결과요약은 `experiments/react-native/coordination/final-result.json`.
