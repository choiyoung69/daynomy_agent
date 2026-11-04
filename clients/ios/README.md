# DAYNOMY iOS

SwiftUI·iOS 17 이상·Swift 6 언어 모드의 네이티브 클라이언트다. 외부 Swift 패키지 없이 Foundation·Observation·CryptoKit과 iOS 시스템 프레임워크를 사용한다.

## 공통 탐색

하단은 **포트폴리오 · 이슈 · 내 계정** 세 탭이다. 종목 조회는 포트폴리오 안에서 열고, AI 분석은 요약 근처의 단독 진입을 사용한다. 캘린더·자료·관리자는 기존 보조 진입을 유지한다. 이슈의 오늘 뉴스 사진 캐러셀과 키보드 Search 제출 검색은 독립 상태다. [적용 계약](../../spec/ios-native/common-ui.md) · [실행·캡처 기록](../../experiments/ios-common-ui/README.md).

## 기능

- 포트폴리오: 게스트 매수/매도·수정/삭제·보유 조정/삭제, 정확한 십진수 원장 재계산, 회원 거래·보유 관리, 평가금액·손익·자산 추이·변경 이력.
- 종목: 국내/미국 검색·종류 필터·최근 저장 종가·수동 단가·환율·종목 관련 자료.
- 소식: 뉴스/오늘의 뉴스·카테고리·목록/상세·키워드·시장 분석·통합 검색·외부 자료·인물.
- 일정과 분석: 회원/게스트 월별 투자 캘린더·포트폴리오 분석·근거·회원 분석 갱신/이력.
- 계정: 외부 브라우저 Google 인증의 PKCE 코드 교환·쿠키 세션, 내 정보·닉네임·로그아웃·탈퇴·피드백.
- 관리자: 뉴스 목록/상세/등록/수정/발행/거절/삭제·이미지 선택/검색/생성 요청, 인물/게시물/후보 큐·종목 콘텐츠·피드백·동기화/백필 실행 화면.

리그·이메일 알림·배포는 제외한다. 웹 전용 소개/약관・개인정보 문구의 iOS 정책 확정, 마케팅 투어·미디어 내장 임베드·정밀한 차트/화면 재현은 남아 있다. 외부 미디어는 출처 링크로 열며 실제 제공자 로그인/AI/이미지/소셜 실행 검증은 별도다.

**2026-11-04 현재 Xcode 27.1·iOS Simulator SDK 27.1로 앱과 UI 테스트 타깃의 빌드가 통과했다.** 코어의 정식 Swift Testing 51개도 새 실행에서 통과했다. 화면·상태 회귀와 과거 HTTP/DB 근거의 범위는 [이번 검증 기록](../../experiments/ios-sdk-verification/README.md)에서 구분한다. 과거 CLT/Xcode 부재 기록을 현재 환경의 사실로 사용하지 않는다.

## 실행과 검사

기본 developer directory가 CLT일 수 있어 각 명령에 Xcode 경로를 지정한다. 전역 설정은 바꾸지 않는다.

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test --package-path clients/ios
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project clients/ios/DaynomyIOS.xcodeproj -scheme DaynomyIOS -destination 'generic/platform=iOS Simulator' -derivedDataPath .local/ios-derived CODE_SIGNING_ALLOWED=NO build-for-testing
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available
```

조회한 실제 Simulator destination으로 `test`를 실행한다. 과거4탭 UI 기준은 보존돼 있으며 현재3탭은 `DaynomyCommonUITests`, `DaynomyCommonMarketRegressionUITests`, `DaynomyCommonNavigationRegressionUITests`, `DaynomyCommonSelloutUITests`로 명시 개정했다. `-only-testing:DaynomyIOSUITests/<클래스>`로 현재 탐색 인수를 선택한다. 시각 캡처는 `DaynomyCommonVisualUITests`다. 합성 HTTP fixture는 아래처럼 시작한다. 이 서버의 결과는 실제 Rust/DB·OAuth·AI 제공자 검증과 구분한다.

```sh
python3 experiments/ios-next-verification/test-author/ui_fixture.py --port 18082
```

후속 UI 검사는 별도 터미널에서 검색 지연을 제어하는 기존 Handler 상속 fixture를 시작한다:

```sh
python3 experiments/ios-sdk-verification/ui_fixture.py --port 18097 --stock-delay 3
```

후속 UI 검사의 기본 포트는 18097이다. 기존 종목/탭 검사는 18082를 사용한다. `DAYNOMY_UI_BASE_URL`을 테스트 프로세스에 지정해 주소를 통일할 수도 있지만 검색 취소 인수에는 지연 fixture를 사용한다. 포트·기기 공유를 피하고 검사 후 자신이 시작한 서버만 종료한다.

과거 `experiments/ios-full/test-author/run_host_tests.py`는 CLT에 Swift Testing 라이브러리가 없을 때 고정 본문을 실행한 대체 러너다. 현재 Xcode 환경에서는 정식 `swift test`를 우선한다. 추출 상태 회귀도 SwiftUI 화면 인수와 구분한다.

반복 작업의 최소 입력·역할·검사 경로는 [프로젝트 iOS 스킬](../../.agents/skills/daynomy-ios/SKILL.md)에 있다. 기존 tracing hook 설정을 재사용하며 설정 존재를 수집 성공으로 해석하지 않는다.

## API와 인증 설정

`DaynomyIOS.xcodeproj`의 `DaynomyIOS` scheme은 같은 폴더의 `DaynomyCore` 패키지를 사용한다. Debug `DAYNOMY_API_URL` 기본값은 `http://127.0.0.1:18081`이다. 별도 로컬 Rust 서버를 [백엔드 안내](../../app/README.md)대로 준비한다. 앱이 서버·DB를 시작하지는 않는다. Debug 실행 환경 변수 `DAYNOMY_API_BASE_URL`은 명시적 루프백 주소만 덮어쓸 수 있다. Release는 HTTPS 주소를 빌드 설정에 지정해야 한다.

인증은 `org.daynomy.app://auth/callback`의 state/PKCE를 검증한 뒤 서버의 `/api/auth/mobile/exchange`로 코드를 단 한 번 교환한다. 브라우저 쿠키를 복사하거나 bearer 토큰을 URL/일반 설정에 저장하지 않는다. 시장 API와 서비스 API는 같은 ephemeral URLSession을 사용한다. CSRF·동시 401 갱신·로그아웃 세대/쿠키 정리를 공통 클라이언트가 처리한다. 실제 Google 공급자 설정과 iPhone 인증 복귀 검증은 별도로 필요하다.

게스트 기록과 앱 인증 쿠키는 현재 앱 세션 메모리에만 둔다. 앱 종료 뒤 복원이나 영구 로그인은 제공하지 않는다. 종가 원문은 문자열로 보존하고, 원장 계산은 입력 한도를 검증한 Decimal로 처리한다. 실시간 시세를 생성하거나 종가가 없는 자산을 임의 가격으로 평가하지 않는다.

현재 공통 UI 인수 fixture는 `python3 experiments/ios-common-ui/test-author/ui_fixture.py --port 18097`을 사용한다. Android와 같은 테스트 JPEG를 서버가 제공하며 제품 앱에는 포함하지 않는다. 이전 core/SDK 기록과 이번 UI 실행 범위는 각 검증 기록에서 구분한다.
