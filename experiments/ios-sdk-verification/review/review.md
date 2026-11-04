# iOS SDK 후속 독립 소스 리뷰

기준: `892151432ee774a735f04de731c6379717585b01`. 기존 `experiments/ios-next-verification/review.md`의 F1–F7과 현재 최종 소스 차이를 대조했다. 검토 역할은 앱·기존 테스트·KB를 수정하거나 SDK/Simulator/상태 검사를 중복 실행하지 않았다. 이 기록만 작성했다.

## 판정

검토한 수정에서 새 수정 필수 결함을 발견하지 않았다. F1–F7의 소스 원인은 모두 해소됐다. 이 판정은 아래 해시의 소스·host 회귀 증거에 한정되며 모든 native 인수 항목 완료를 뜻하지 않는다. 최종 SDK 빌드와 Simulator 결과는 이 기록 작성 시 root로부터 아직 수령하지 않았다.

| 항목 | 현재 근거 | 판단 |
| --- | --- | --- |
| F1 뉴스 검색 DTO | `DiscoveryView.swift:48`이 `NewsPresentation.items`에 실제 뉴스 검색 여부를 전달한다. helper는 검색 `content`와 일반 목록 `items`를 구분한다. 원본 `search/dto/NewsSearchResponse.java`의 `content`와 Rust 응답을 대조했다. | 소스 해결; 기존 presentation 10회귀 로그 확인 |
| F2 계정·분석 수명 | `AppShell.swift:12`에서 금융 탭 전체 identity를 로그인 상태·회원 ID에 묶어 navigation과 State 수명을 폐기한다. 분석은 계정 변경 시 결과·이력을 초기화하고 응답·오류·loading에 account/generation을 적용한다. saved GET과 POST도 각 세대를 소유해 늦은 EMPTY가 새 READY를 지우지 않는다. History는 조회/이탈 시 자료를 비우고 account/generation으로 양쪽 응답을 방어한다. | 소스 해결; 실제 렌더 프레임/계정전환 UI는 별도 |
| F3 보유·평가 혼합 | `PortfolioView.swift:69,84`에서 검증된 새 보유를 반영하는 같은 MainActor 구간에 이전 calculation을 지운다. 이후 histories 또는 calculate 실패도 이전 평가를 되살리지 않는다. | 소스 해결; 회원 histories 실패와 기존 calculate 실패 회귀 로그 확인 |
| F4 관리자 category | `AdminView.swift:473`이 작성 전용 `adminCategoryCodes`를 사용한다. 원본 `news/domain/Category.java`와 Rust validator의 STOCK/ETF/REAL_ESTATE 3값과 일치한다. | 기존 수정 유지 확인 |
| F5 내부 뉴스 navigation | `DiscoveryView.swift:87`이 contents record ID 대신 URL에서 추출한 news ID로 상세를 연다. 공용 parser는 canonical `/news/{positive Int64}`만 허용한다. 원본 `content/domain/AssetContent.java`의 `"/news/" + news.getId()`와 일치한다. | 소스 해결; route 16회귀 로그 확인 |
| F6 검색 idle·응답 경쟁 | 새 검색은 이전 matches를 즉시 지우고 빈 검색/선택 분기는 spinner를 idle로 만든다. country/query/selected ID가 task 수명에 포함되며 결과·오류·defer는 generation을 확인한다. select/이탈도 이전 검색을 무효화한다. | 소스 해결; 취소 없이 응답을 뒤집는 회귀 확인 |
| F7 게스트 명시 삭제 | removing 분기는 quantity/average를 파싱하지 않고 0/removed 이벤트를 만든다. 원장을 복제한 뒤 성공 때만 교체하므로 거래 보존과 원자적 replay 정책을 유지한다. | 소스 해결; 빈 값/잘못된 값과 거래 보존 회귀 로그 확인 |

원본 추가 조회는 이 worktree에 없는 파일만 저장소 root의 `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/`에서 읽었다. `SavedPortfolioAnalysisResponse.empty()`는 `analysis:null`이고 FAILED/PROCESSING은 이전 분석 object를 포함할 수 있다. 현재 코드는 EMPTY/null을 지우되 서버가 준 이전 object는 유지하며, 같은 계정의 transport 실패는 기존 결과를 보존한다. KB는 지정된 ios-swift 상태/취소와 프로젝트 portfolio-ledger/analysis/calculation만 참고했다.

## 검사 증거 대조

새 runner는 실제 production 메서드와 State 선언을 추출한다. SwiftUI wrapper·private만 제거하며 메서드를 다시 구현하지 않는 것을 확인했다. HTTP/Market actor가 응답 순서를 직접 통제해 uncancelled ABA·이전 계정 오류·동일 계정 GET/POST 순서를 검사한다.

- 독립 역할이 남긴 GREEN 로그를 읽었다: 새 async 상태 17/17, 기존 고정 Swift 본문 13/13, route 16/16, 기존 presentation 10/10, source wiring 9/9, identity 연결 1/1.
- 이 리뷰 역할은 `frozen.sha256` 9항목, `verified-source.sha256` 5항목, `green-evidence.sha256` 8항목을 직접 대조해 전부 일치를 확인했다. 상태 검사는 재실행하지 않았다.
- identity/wiring은 정적 연결 확인이다. 실제 SwiftUI lifecycle나 이전 계정 데이터가 한 프레임도 보이지 않았다는 실행 증거로 세지 않는다. host transport는 실제 iOS URLSession·로그인·Rust/DB 비교 증거가 아니다.
- 최종 SDK/Simulator 결과: 미수령. root 실행과 해당 소스 해시 연결 후 별도 기록을 따른다. baseline SDK build 성공 통지는 최종 변경 SDK 검증으로 대체하지 않았다.

## 남은 native 인수 경계

SDK·UI 결과에서 구별할 핵심은 계정 전환 중 비활성 금융 navigation 폐기, 지연/실패 응답 뒤 A 자료 재노출 없음, 새 보유 뒤 평가 실패 표시, 검색 진행 중 전체삭제·국가전환·선택, 편집값이 빈 게스트 명시 삭제, 뉴스 검색·자료의 정확한 news ID 진입이다. 실제 Google 인증 완료, PhotosPicker 취소/연속선택, Dynamic Type/VoiceOver/가로 화면·차트 경계는 이 host/소스 리뷰로 검증됐다고 쓰지 않는다. 기존 리뷰의 수동 인수 항목은 유지한다.

## 검토 소스 SHA256

| 파일 | SHA256 |
| --- | --- |
| `clients/ios/DaynomyIOS/AppShell.swift` | `9f3d02eb5d21a1e55c7dea09d91d38283517b56dc0a498094a0e95792e02bf8b` |
| `clients/ios/DaynomyIOS/CalendarAnalysisView.swift` | `a1ccda86a9c1173f862cdf67f9e6e142598f6bf85da3c6a6b692e9a42c29ea31` |
| `clients/ios/DaynomyIOS/PortfolioView.swift` | `fd626d763d9734ac8e8d76f1275d6afa30d8699eb91a8e6c840fc6c5f0043c76` |
| `clients/ios/DaynomyIOS/DiscoveryView.swift` | `510c257fced02d7fa87bfda81534e7a22f0edbba58d135f5906c87a0f1657c2a` |
| `clients/ios/DaynomyIOS/AdminView.swift` | `4350d78b4e701fe939934b8a0daab8b979aee57e44a9c94879897a1713b83857` |
| `clients/ios/Sources/DaynomyCore/NewsPresentation.swift` | `dd51a20c1c2dec18d57d5abdccaea7279a3bc43a0012a5b0851742cca3166762` |
| `clients/ios/DaynomyIOS.xcodeproj/project.pbxproj` | `7ff88922420e14fc1cc742dca7de8243b5737abc3a463daf609f36d37cba5dba` |

## 후속 검토 — SDK 및 UI 검사 조건

root의 최종 build-for-testing 로그 `.local/final-build.log` 끝에서 `TEST BUILD SUCCEEDED`를 직접 읽었다. 이 시점 production `verified-source.sha256` 5항목도 다시 대조해 전부 일치를 확인했다. 이는 SDK 타입 검사 증거이며 이후 UI 인수 결과와 구분한다.

`test-author/ui-baseline/`의 보존 원본·실패 로그·diff·현재 UI 테스트 해시 5항목을 직접 대조했다. 추출한 실패 시점 화면 `empty-price-at-failure.png`도 직접 열어 회색 `단가` placeholder만 보이며 77과 지연 종가가 표시되지 않음을 확인했다. 원본 검사는 마지막 값 비교에서 `Optional("단가") != Optional("")`로 실패했다.

`clients/ios/UITests/DaynomyIOSUITests.swift`의 assertion 개정은 인수 기준 약화로 판단하지 않는다. 77 입력→두 번 삭제→종가 기준일 대기 순서와 timeout은 유지한다. 마지막 접근성 값 해석만 `placeholderValue == "단가"`를 요구하면서 빈 문자열 또는 그 placeholder로 한정한다. nil·77·123.4500·임의 문자열·다른 placeholder는 계속 거부한다. 통제된 입력 경로에는 숫자77과 삭제만 있어 placeholder와 실제 입력을 혼동할 여지도 이 검사에서는 없다. 개정 파일 SHA256: `823b5ea9cc21c5c3d24d9e35fbedcf512d23a74c8a7c8969868b42906e3f9815`. 개정 후 UI 성공 여부는 root 최종 결과로 판정한다.

새 `experiments/ios-sdk-verification/ui_fixture.py`는 기존 fixture를 import한 뒤 `Handler(original.Handler)`를 상속하며 `/api/stocks` GET에만 기본 3초 지연을 추가하고 `super().do_GET()`로 원래 응답을 제공한다. POST·CSRF·피드백 검증·calculate·종가 지연은 override하지 않는다. loopback 주소와 ThreadingHTTPServer를 유지한다. 기존 `experiments/ios-next-verification/test-author/ui_fixture.py`의 git diff가 없음을 확인했다. 원본 SHA256은 `f429a5a3b73b853dbd17c5fb6dea3377a3d1fb8c73898fc01e9009808d29aa94`, wrapper는 `9281f2d8e81114f80bbde6b800828e935383ac4fff04288496ee57edddffd1af`다.

이는 실제 spinner가 존재하는 pending 상태라는 기존 UI 시나리오의 전제를 갖추는 변경이다. 즉시 응답 fixture에서 spinner 존재 assertion이 실패한 결과는 제품 검색 spinner 결함 재현으로 세지 않는다. 독립 테스트 역할의 `delayed-fixture-smoke.log`에서 2.9초 이상 지연·원본 응답·인증/CSRF/피드백/calculate 유지 PASS를 읽었고 smoke 코드를 검토했다. 리뷰 역할은 실행하지 않았다. fixture는 여전히 합성 응답이며 실제 서버/DB 증거가 아니다. 다른 Next UI 실패 및 나머지 UI 결과는 이 부록 작성 시 미수령이며 성공으로 처리하지 않는다.

### 매도 Picker query 개정

실제 export attachment `.local/next-ui-attachments/5C17CD46-2881-4E60-8C17-249BF2C0A4B4.txt:236`을 직접 읽었다. 거래 editor의 실제 Button label은 `유형, 매수`이며 `유형`은 별도 StaticText다. 따라서 이전 `app.buttons["유형"]` 조회 실패와 일치한다. `picker-revision.sha256`의 보존 Next 원본·AX excerpt·diff·현재 Next 소스 4항목을 직접 대조해 모두 일치했다.

변경은 `openTrade`의 매도 분기에서 Button label을 정확히 `유형` 또는 `유형, 매수`로 조회하는 한 곳뿐이다. 임의 contains 조회로 확대하지 않고 기존 label과 관측된 현재 label만 허용한다. 그다음 매도 메뉴 선택, 수량·단가 입력, 저장·보유·실현손익·원장 삭제·oversell 오류 및 기존 보유 보존 단언은 그대로다. 인수 기준 약화로 판단하지 않는다. 현재 Next 소스 SHA256은 `c2abb7f73ffe8d457c1e52a78983293f632430d8871e6a139b55c6d9bdc790a8`다. 이 query 개정이 실패했던 뒤쪽 거래 흐름을 통과시켰는지는 실제 재실행 결과로 별도 판단한다.

또한 `test-author/delayed-fixture.sha256`의 wrapper·smoke 코드·smoke 로그 3항목을 추가 대조해 모두 일치를 확인했다. 이 리뷰 역할은 앱·검사·fixture 수정이나 재실행을 수행하지 않았다.
