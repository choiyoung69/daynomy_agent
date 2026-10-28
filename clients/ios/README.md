# DAYNOMY iOS

SwiftUI·iOS 17 이상·Swift 6 언어 모드의 네이티브 클라이언트다. 외부 Swift 패키지 없이 Foundation·Observation·CryptoKit과 iOS 시스템 프레임워크를 사용한다.

## 기능

- 포트폴리오: 게스트 매수/매도·수정/삭제·보유 조정/삭제, 정확한 십진수 원장 재계산, 회원 거래·보유 관리, 평가금액·손익·자산 추이·변경 이력.
- 종목: 국내/미국 검색·종류 필터·최근 저장 종가·수동 단가·환율·종목 관련 자료.
- 소식: 뉴스/오늘의 뉴스·카테고리·목록/상세·키워드·시장 분석·통합 검색·외부 자료·인물.
- 일정과 분석: 회원/게스트 월별 투자 캘린더·포트폴리오 분석·근거·회원 분석 갱신/이력.
- 계정: 외부 브라우저 Google 인증의 PKCE 코드 교환·쿠키 세션, 내 정보·닉네임·로그아웃·탈퇴·피드백.
- 관리자: 뉴스 목록/상세/등록/수정/발행/거절/삭제·이미지 선택/검색/생성 요청, 인물/게시물/후보 큐·종목 콘텐츠·피드백·동기화/백필 실행 화면.

리그·이메일 알림·배포는 제외한다. 웹 전용 소개/약관・개인정보 문구의 iOS 정책 확정, 마케팅 투어·미디어 내장 임베드·정밀한 차트/화면 재현은 남아 있다. 외부 미디어는 출처 링크로 열며 실제 제공자 로그인/AI/이미지/소셜 실행 검증은 별도다.

**현재 환경에는 full Xcode·iOS SDK가 없다.** 코어의 호스트·실제 HTTP 검사와 네이티브 화면 소스 작성/구문 검사를 iOS 앱 빌드·기기 실행 성공으로 보지 않는다. 검증한 범위와 미완료 항목은 [30분 확장 기록](../../runs/016-ios-full-thirty-minute.md)을 따른다.

## 실행과 검사

저장소 루트에서 현재 CLT 환경의 고정된 코어 테스트 본문을 실행한다:

```sh
python3 experiments/ios-full/test-author/run_host_tests.py
```

현재 CLT는 `lib_TestingInterop.dylib`가 없어 정식 `swift test` 런타임을 실행하지 못한다. 위 명령은 별도 작성자가 고정한 assertion 변환 러너다. 정상 Swift Testing 환경에서는 `swift test --package-path clients/ios`를 추가 실행한다. 과거 빈 구현 실패·고정 해시·추가 검사는 `experiments/ios-full/test-author/`, 독립 검증은 `experiments/ios-full/verification/`에 보존한다.

full Xcode를 준비한 호스트에서 프로젝트와 실제 Simulator destination을 조회한다:

```sh
xcodebuild -list -project clients/ios/DaynomyIOS.xcodeproj
xcrun simctl list devices available
xcodebuild -project clients/ios/DaynomyIOS.xcodeproj -scheme DaynomyIOS -showdestinations
xcodebuild -project clients/ios/DaynomyIOS.xcodeproj -scheme DaynomyIOS -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

그 뒤 조회한 실제 destination으로 `test`를 실행한다. 2개 종목 시나리오와 1개 전체 탭 XCUITest 소스가 같은 타깃에 연결돼 있다. 이 UI 검사는 현재 호스트에서 실행하지 않았다. 종목 UI 검사에 필요한 독립 합성 서버는 아래 명령으로 시작한다. Rust/DB 증거와 구별한다.

```sh
python3 experiments/ios-native/verification/ui_fixture.py
```

## API와 인증 설정

`DaynomyIOS.xcodeproj`의 `DaynomyIOS` scheme은 같은 폴더의 `DaynomyCore` 패키지를 사용한다. Debug `DAYNOMY_API_URL` 기본값은 `http://127.0.0.1:18081`이다. 별도 로컬 Rust 서버를 [백엔드 안내](../../app/README.md)대로 준비한다. 앱이 서버·DB를 시작하지는 않는다. Debug 실행 환경 변수 `DAYNOMY_API_BASE_URL`은 명시적 루프백 주소만 덮어쓸 수 있다. Release는 HTTPS 주소를 빌드 설정에 지정해야 한다.

인증은 `org.daynomy.app://auth/callback`의 state/PKCE를 검증한 뒤 서버의 `/api/auth/mobile/exchange`로 코드를 단 한 번 교환한다. 브라우저 쿠키를 복사하거나 bearer 토큰을 URL/일반 설정에 저장하지 않는다. 시장 API와 서비스 API는 같은 ephemeral URLSession을 사용한다. CSRF·동시 401 갱신·로그아웃 세대/쿠키 정리를 공통 클라이언트가 처리한다. 실제 Google 공급자 설정과 iPhone 인증 복귀 검증은 별도로 필요하다.

게스트 기록과 앱 인증 쿠키는 현재 앱 세션 메모리에만 둔다. 앱 종료 뒤 복원이나 영구 로그인은 제공하지 않는다. 종가 원문은 문자열로 보존하고, 원장 계산은 입력 한도를 검증한 Decimal로 처리한다. 실시간 시세를 생성하거나 종가가 없는 자산을 임의 가격으로 평가하지 않는다.
