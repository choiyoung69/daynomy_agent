# iOS SDK 후속 독립 소스 리뷰

기준: `892151432ee774a735f04de731c6379717585b01`. 기존 `experiments/ios-next-verification/review.md`의 F1–F7과 현재 최종 소스 차이를 대조했다. 검토 역할은 앱·기존 테스트·KB를 수정하거나 SDK/Simulator/상태 검사를 중복 실행하지 않았다. 이 기록만 작성했다.

## 판정

검토한 수정에서 새 수정 필수 결함을 발견하지 않았다. F1–F7의 소스 원인은 모두 해소됐다. 이 판정과 후속 SDK 빌드·고유 UI10개 증분 통과는 모든 native 인수 항목 완료를 뜻하지 않는다. 최초 소스 리뷰 이후 도착한 실행 증거와 후속 검사 개정 검토는 아래 부록에 구분했다.

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
| `clients/ios/DaynomyIOS.xcodeproj/project.pbxproj` | `205e096e48fd1beb75d174281d15188dde373cc92dece12286df9f4fadb93551` |

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

### Debug architecture 설정

후속 실제 destination의 `xcodebuild test`에서 `.local/revised-ui.log`에 DaynomyCore의 x86_64 undefined symbol 링크 실패가 발생했다. root는 package object가 arm64로 갱신되는 반면 앱이 arm64+x86_64를 링크하는 불일치를 확인했다. 이전 generic build 성공은 이전 object 상태에서의 결과이며 이 재실행 실패를 지우지 않는다.

현재 프로젝트 diff를 독립 검토했다. project Debug `XCBuildConfiguration`에 `ONLY_ACTIVE_ARCH = YES` 한 항목을 추가하고 앱/UI target이 이를 상속한다. 특정 architecture 제외나 `ARCHS` 강제 지정은 없고 Release 설정도 바꾸지 않는다. 실제 실행 destination의 active architecture에 앱·테스트 빌드를 맞추는 수정으로 범위가 적절하다. 이 변경은 Intel Simulator 빌드 통과 증거는 아니다.

프로젝트 SHA256은 이전 SDK 성공 시점 `7ff88922420e14fc1cc742dca7de8243b5737abc3a463daf609f36d37cba5dba`에서 현재 `205e096e48fd1beb75d174281d15188dde373cc92dece12286df9f4fadb93551`로 바뀌었다. 위 현재 소스 표도 갱신했다. 앱 Swift5개는 `verified-source.sha256` 직접 재대조로 모두 불변임을 확인했다. `.local/revised-ui-active-arch.log`의 이후 빌드/UI 성공 여부는 최종 실행 결과에서 별도 판정한다.

### ActivityIndicator·실현손익 조회 개정

실제 `.local/revised-ui-attachments/0242583C-AAA3-4FE2-9CE5-A2CEAB74308A.txt:221`에서 label `검색 중`, value1인 ActivityIndicator를 직접 확인했다. `.local/revised-ui-attachments/E8DEB146-0694-4FF1-BEC1-9FACFD9CE178.txt:76`의 StaticText label은 `실현손익, 80 원`이다. 보존된 두 영상 frame도 직접 열어 검색어 `삼성` 아래 spinner와 검색 중 문구, 실현손익80원·보유10주·평균110원을 확인했다. `activity-profit-revision.sha256`의 직전 Picker-stage 원문·frame2개·AX2개·diff·현재 소스 7항목을 직접 대조해 모두 일치했다.

이번 변경은 Next 두 query만 수정한다. spinner의 존재→전체삭제→동일 indicator 부재→빈 검색어/이전 결과 부재 순서와 timeout은 유지하고 실제 AX type인 `.activityIndicator`와 정확한 `검색 중` label/identifier를 조회한다. 손익은 정확한 combined label `실현손익, 80 원`을 요구해 `(150 - 110) * 2 = 80` 기대값을 유지한다. 이후 매도/매수 삭제 및 빈 보유·거래 단언도 불변이다. 실제 표시 타입/묶인 접근성 label에 맞춘 수정이며 인수 기준 약화로 판단하지 않는다.

현재 Next 소스 SHA256은 `6e8e3ffac065a054e78ef19d6ba7c02bdb27277cbb7ab6a9d377f0ab69145bcf`다. 이전 단계 해시는 보존된 stage 원문의 식별로 유지한다. `.local/final-generic-build.log`의 `TEST BUILD SUCCEEDED`도 직접 확인했다. 이 generic SDK 성공과 남은 두 UI 사례의 실제 통과 여부는 구분하며, 이 부록 작성 시 두 UI 최종 결과는 미수령이다.

### 거래 삭제 제스처 개정

마지막 두 UI 중 검색 spinner는 통과했다는 root 통지를 받았다. 거래 CRUD는 손익80원까지 도달한 뒤 삭제 버튼 조회에서 실패했다. `.local/final-two-attachments/83408F8C-0DD9-47FE-9426-0C23B616B59E.txt:119,141`을 직접 읽어 매도 row frame y779~860.3, TabBar y791~874를 확인했다. row 중앙819.65는 탭바 범위다. 보존된 실패 frame도 직접 열어 거래 행이 탭바 뒤에 가려지고 삭제 버튼·확인창이 없는 것을 확인했다. `delete-row-revision.sha256` 5항목(직전 원문·frame·AX·diff·현재 Next 소스)을 직접 대조해 전부 일치했다.

수정은 `deleteRow` helper에 한정된다. 최대7회 스크롤 후 row 전체가 navigation bar와 tab bar 사이에 있는지 더 강하게 단언하고, row 내부 x90%→45%의 부분 drag로 실제 삭제 action을 노출한다. 삭제 버튼 존재 대기→명시적 `삭제`→`거래 삭제` 확인→해당 행 부재 순서는 유지한다. 매도 삭제 후12주 평균110원, 매수 삭제 후 빈 보유·빈 거래 인수도 그대로다. 조회/제스처 좌표를 실제 표시된 row에 맞춘 변경이며 오류 무시·조건부 skip·기대값 완화가 없어 인수 기준 약화로 판단하지 않는다.

현재 Next 소스 SHA256은 `da6dfeb61f1da886f8133206ac94a6903619009ba7d4921b141c30aa4710cd21`다. 앞 단계 현재 소스 해시는 보존 stage 식별이다. 앱·프로젝트 소스는 변경하지 않았다. 실제 마지막 거래 삭제와 빈 원장 완료는 root의 최종 UI1 결과가 도착하기 전까지 통과로 처리하지 않는다.

## 최종 실행 증거 확정

`results.json`과 실제 로컬 로그 메타를 읽기 전용으로 대조했다. 기록된 11개 실행 모두 로그 SHA256·build/test 성공 marker가 일치하고, 각 testcase의 이름·pass/fail·소요초가 로그와 일치했다. 전체 실행에서 testcase별 가장 최근 결과를 계산한 합집합이 JSON의 고유 UI10개 목록과 정확히 일치하며 모두 pass다. 이는 한 번의 UI10개 전체 실행이 아니다. 이미 통과한 메서드는 유지하고 실패와 개정 영향을 받은 검사만 재실행한 증분 합집합이다. 앞선 실패와 그 원문·단계별 소스는 기록에서 제거하지 않았다.

마지막 `.local/final-ledger-ui.log`는 거래 매수→수정→매도→삭제 흐름 1개,92.376초,0실패 및 `TEST SUCCEEDED`를 직접 확인했다. 앞 단계 `.local/final-two-ui.log`의 spinner21.442초 pass와 거래 삭제 전 실패도 분리되어 있다. canonical Swift log의 51tests/9suites pass 및 `.local/final-generic-build.log`의 SDK `TEST BUILD SUCCEEDED`도 직접 확인했다. host 상태/정적 연결·SDK 빌드·Simulator UI를 서로 대신 세지 않았다.

최종 `final-source.sha256` 41파일을 직접 대조해 전부 일치했고, manifest 자체 SHA256 `d790625aa0f88c0f9aef567ff6fc9d012641a6b823cda835c835d5289dddd3f3`와 파일 수41도 결과 JSON과 일치했다. 검토한 `results.json` SHA256은 `56f2b7cd04feac69d8f1b01f378c3393440e70da7b930fe7abb8e4855fa310a5`다. `.local/final-knowledge-check.log`의 local source111/111 PASS도 읽었다. KB 준비/해시 검사를 실제 앱 동작 증명으로 해석하지 않는다.

확정 범위는 Xcode27.1·Swift6 모드·iOS17 최소 target의 SDK 빌드, 합성 fixture의 iPhone17/iOS27.0에서 고유 UI10개 최신 증분 통과, 연결된 host 회귀 및 현재 소스 리뷰다. 실제 Google 로그인/callback, 계정전환의 렌더 프레임 격리, 실제 Rust/DB·외부 AI/S3/social/provider, 포괄적 접근성·tablet/dark/rotation·Duo sidebar, Release/device 서명·배포는 여전히 미검증이다. 전체 시간·토큰 절감을 측정하거나 추정하지 않았다. 이 독립 검토 역할은 실행 재수행이나 앱·기존 테스트·KB 수정 없이 증거와 최종 source만 대조했다.
