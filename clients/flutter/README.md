# DAYNOMY Flutter 사용자 앱

기존 `knowledge/`와 원본 API를 바탕으로 검색·포트폴리오·뉴스·캘린더·내 정보를 구현한다.
관리자·리그·이메일 알림·배포는 범위 밖이다. 게스트 초안은 앱 메모리에서만 유지하고,
회원 원장은 Rust 서버를 조회한다. 앱 재시작 시 네이티브 로그인도 다시 필요하다.

## 실행

프로젝트 루트의 `python3 scripts/flutter_setup.py --check`로 설치된 SDK를 확인한다.
이 작업의 SDK는 Flutter 3.47.8 / Dart 3.13.7이다. `scripts/flutter.sh`는 pub·Gradle·분석기
캐시를 저장소의 `.local/`에 분리하고 전용 Android SDK가 있으면 자동으로 사용한다.

```sh
cd clients/flutter
bash ../../scripts/flutter.sh pub get
bash ../../scripts/flutter.sh analyze
bash ../../scripts/flutter.sh test test review_test verification_test
bash ../../scripts/flutter.sh build web --release
```

Web은 API와 **동일 origin**에서 제공한다. 별도 포트에서 개발할 때는 루트의
`scripts/flutter_preview.py`로 `build/web`과 loopback Rust API를 같은 origin으로 제공한다.
브라우저의 HttpOnly 세션 쿠키를 사용하고 로그인 버튼은 기존 `/api/auth/google`로 이동한다.
브라우저 로그인을 위한 서버의 성공 redirect도 이 앱 origin으로 설정한다.

Android emulator의 개발 서버 주소는 `http://10.0.2.2:18081`이다.

```sh
bash ../../scripts/flutter.sh run --dart-define=API_BASE_URL=http://10.0.2.2:18081
bash ../../scripts/flutter.sh build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:18081
```

실기기는 `adb reverse tcp:18081 tcp:18081` 후 `http://127.0.0.1:18081`을 사용하거나 HTTPS
개발 서버를 지정한다. 임의 LAN/공개 HTTP origin은 거절한다. Android debug에서만
localhost·127.0.0.1·10.0.2.2의 HTTP를 허용하며 release 기본은 HTTPS다.
네이티브에서 `API_BASE_URL`을 생략하면 실제 서버를 임의 추측하지 않는다.

Android는 API 24+, compile/target 36이다. 안정판 `flutter_web_auth_2` 5.1.0의 AGP 9 미지원 때문에
Gradle 8.14.3 / AGP 8.13.0 / Kotlin 2.2.20을 고정했다. Flutter 3.47의 최소 지원 버전 검사를
통과하며, 차후 9.x 업그레이드 권고는 남아 있다. 검사를 건너뛰는 플래그를 사용하지 않는다.
iOS는 보수적으로 17.4+를 지정했으며 Xcode에서 `ios/Runner.xcworkspace`를 열어 서명·기기를
설정해야 한다. 이번 환경에는 Xcode가 없어 iOS 빌드와 실기기 인증을 확인하지 못했다.

## 사용자 흐름

- 검색: KR/US 시장, 주식/ETF 필터, 250ms debounce, 이전 실제 전송 취소, 최근 저장 종가·통화·날짜,
  수동 입력 보존, 종목별 관련 자료를 제공한다.
- 게스트: 보유 추가·수정·삭제, 서버 평가 계산·부분 종가 표시, 서버 계산의 비중에 기반한 AI 체험을 제공한다.
  평균 매입가는 모든 시장에서 **KRW**다. 미국 종목은 USD 참고 종가와 별도로 초기 빈 KRW 평균가를
  명시 입력해야 추가할 수 있다. 거래 단가와 최근 종가는 종목 통화를 사용한다.
- 회원: 선택 종목의 매수/매도·거래 수정/삭제·보유 수정/삭제를 서버에 기록하고 원장을 다시 조회한다.
  거래일은 날짜 문자열이고 서울 기준 미래 거래일을 거절한다. 단가 4자리, 비용 2자리, 환율 6자리다.
  기간별 거래 이력·스냅샷 성과·저장 AI 분석과 갱신/분석 이력을 확인할 수 있다.
- 뉴스: 페이지·분류·오늘 뉴스, 뉴스 검색과 출처별 콘텐츠 검색, 본문·키워드·시장 분석·원문 출처,
  주요 인물의 게시물, 종목 자료를 연결한다. 보조 분석 404가 뉴스 본문을 숨기지 않는다.
- 캘린더: 회원/게스트 보유 기반 월 조회와 최대 12개월 범위의 모든 월 조회, 일정·출처·발표값·영향·
  과거 반응 표본을 표시한다. 데이터 부족을 0 수익률로 바꾸지 않는다.
- 내 정보: 외부 브라우저 Google 로그인, 회원 닉네임 수정·로그아웃·탈퇴, 공개 피드백을 제공한다.

작은 화면은 하단 탐색, 넓은 화면은 탐색 rail이다. SafeArea·스크롤 가능한 폼·시스템 글꼴·
밝은/어두운 테마·상태 안내·실패 후 입력 보존을 사용한다. 전송 실패를 빈 데이터로 숨기지 않는다.
거래 쓰기는 자동 재전송하지 않으며 처리 여부가 불명확하면 목록 재조회로 확인한다.

## 네이티브 인증과 저장

`main.dart`는 실제 플랫폼 전송에 `NativeAuthCoordinator`와 `MemoryCookieJar`를 연결한다.
Android Auth Tab / iOS ASWebAuthenticationSession에서 서버의 Google OAuth를 시작한다.
서명 state에 결합한 S256 PKCE·별도 앱 state, 60초·1회용 코드, 고정
`org.daynomy.app://auth/callback`을 검증한 뒤 `/api/auth/mobile/exchange`에서 HttpOnly 쿠키를 받는다.
코드·토큰을 로그나 일반 설정·URL에 저장하지 않는다. Android callback activity와 iOS URL scheme은
소스에 설정돼 있다. 외부 브라우저에 앱 access/refresh 쿠키를 발급하지 않는다.

native `dart:io` 어댑터는 origin/경로/Secure/만료를 지키는 메모리 jar를 사용한다.
web `XMLHttpRequest`는 동일 origin 브라우저 쿠키를 사용한다. 양쪽 모두 timeout·크기 제한·
실제 abort·세션 세대 검사를 연결한다. 로그아웃/탈퇴 전 기존 전송을 취소하고 서버 로그아웃의
쿠키 삭제가 끝나면 회원 캐시와 메모리 쿠키를 정리한다. 브라우저 HttpOnly 쿠키는 JS가 직접 삭제하지 않는다.

직접 의존성은 Flutter SDK(위젯), crypto 3.0.7(SHA-256), flutter_web_auth_2 5.1.0(외부 인증 세션),
url_launcher 6.3.2(검증한 HTTP/HTTPS 출처 링크), web 1.1.1(브라우저 전송)이다.
`pubspec.lock`과 Android 빌드 버전을 함께 보존한다.

## 검증의 범위

별도 테스트 작성 → 구현 → 독립 검증 역할로 진행했다. 최종 독립 실행에서 단위/위젯·실제 native HTTP
테스트 238개, analyzer, release Web 빌드가 통과했다. Android debug APK 빌드·전용 에뮬레이터의
실제 Rust 서버 검색/종목 선택과 입력 위젯 계층의 종가도 확인했다. 서버 HTTP/DB는 모바일 인증 23개·기존 OIDC 13개·
회원/공개 core 80개가 통과했고, 기존 피드백 인수 46개와 재시작/저장장애 검사도 확인했다.
최종 해시와 독립 판정은 `../../runs/012-flutter-verification.md`, 전체 실행 기록은
`../../runs/012-flutter-app.md`를 본다. 실제 Google 계정 인증·플랫폼 callback 완주,
iOS 빌드·실기기, 실제 AI 제공자 응답, 회원 전체 UI CRUD E2E는 미검증이다.

고정 계약은 `../../spec/flutter/test-contract.md`, 인증은 `../../spec/flutter/native-auth.md`이며,
Rust 실행/설정은 `../../app/README.md`, 구현자 기록은 `../../runs/012-flutter-implementation.md`를 본다.

## 검증용 로컬 데이터로 열기

기존 서버 설정 없이 공개 기능을 확인하려면 저장소 루트에서 아래처럼 전용 fixture를 시작한다.
전용 DB에 합성 종목·뉴스·캘린더를 넣으며 다른 검사의 공용 DB 잠금이 풀릴 때까지 기다린다.
실제 Google·AI 제공자를 설정하는 명령은 아니다.

```sh
python3 scripts/flutter_backend_fixture.py --output .local/flutter-preview-new --port 18081
python3 scripts/flutter_preview.py --port 18300 --api http://127.0.0.1:18081
```

두 명령은 별도 터미널에서 실행한다. Web 빌드가 있어야 하며
`http://127.0.0.1:18300`에서 같은 origin으로 API를 사용한다.
Android 에뮬레이터 빌드는 `--dart-define=API_BASE_URL=http://10.0.2.2:18081`을 사용한다.
fixture 터미널에서 Ctrl-C를 누르거나 해당 출력 폴더에 `stop` 파일을 만들면
자신이 생성한 DB와 서버를 정리한다. 출력 폴더는 매 실행 새 경로를 사용한다.
