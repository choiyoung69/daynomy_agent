# iOS 공통 UI 독립 인수 테스트

기준 소스 `e3c9616f`, 작업 브랜치 `codex/ios-common-ui`. `.local/common-uiux.md` 2·11·12절과 현재 사용자 구현 요청을 적용한다. 기존 고정 테스트는 수정하지 않았다. 테스트 작성 역할은 앱 소스·프로젝트 연결·Simulator·SDK 빌드를 수행하지 않는다.

- `DaynomyCommonUITests.swift`: 3탭과 포트폴리오 종목 조회, 최대9 사진 캐러셀과 44pt 이전/다음, 상세 복귀 선택 유지, Search/Enter 제출과 미제출 초안, 검색 해제·검색 장애와 오늘 상태 독립, 실제 로그인 진입·의견 API.
- `DaynomyCommonMarketRegressionUITests.swift`: 기존 `clients/ios/UITests/DaynomyIOSUITests.swift`의 2개 인수를 보존한다. 독립 종목 탭 진입만 포트폴리오 `portfolioMarket` 진입으로 개정한다.
- `DaynomyCommonNavigationRegressionUITests.swift`: 기존 `experiments/ios-next-verification/test-author/DaynomyNextUITests.swift`의 최신 deleteRow 제스처를 포함한 7개 인수를 보존한다. 탭 이름·검색 ID·계정 의견 시트 진입, 보유/거래 segment 전환만 최신 공통 탐색에 맞춘다. 입력·금액·매도 제한·원장 삭제·의견 성공/거절 기대값은 유지한다.

공통 접근성 계약: `portfolioMarket`, `portfolioLedgerPicker`(보유 자산/거래 내역), `todayNewsPrevious`, `todayNewsNext`, `todayNewsPosition`(1 / 9), `todayNewsArticle_<id>`, `newsQuery`, `clearNewsSearch`, 기존 `feedbackField`. 의견 시트 닫기는 `닫기`다. 이슈 탭은 `이슈`, 계정은 `내 계정`이다.

`ui_fixture.py`는 기존 SDK fixture Handler를 상속한다. today 기사171~181 총11건과 명시적 합성사진/사진없음/깨진URL만 추가한다. 앱에 샘플 데이터를 추가하지 않는다. 기존 기사71/검색72, 로그인401·CSRF·의견 거절·금액 계산·지연검색을 보존한다. `q=실패`는 검색503이다. 사진 응답 PNG chunk CRC를 확인했다. loopback 합성 응답은 실제 Rust/DB 증거가 아니다.

`baseline-red.log`는 `git show e3c9616f:<path>`로 고정한 구현 전 소스의 정적 RED 4건이다. 실제 UI 실패 실행으로 세지 않는다. `parse.log`는 Swift parser 성공(빈 출력), `fixture-smoke.log`는 임시 loopback fixture 검사 성공이다. 초기 sandbox bind 제한은 loopback만 허용한 재실행으로 해결했다. SDK/기기 실행·사진 렌더·VoiceOver·DynamicType·회전 후 유지 검사는 root가 별도로 수행해야 한다. 범용 하네스를 추가하지 않았다.

root 실행:

```sh
python3 experiments/ios-common-ui/test-author/ui_fixture.py --port 18097
```

root가 위 Swift 3파일을 Xcode UI target에 연결하고 기존 환경·Simulator에서 새 14인수를 실행한다. `DAYNOMY_UI_BASE_URL`로 fixture 주소를 지정할 수 있다. 테스트 작성자가 이 명령을 실행한 기록은 아니다.

사진 시각 대조용 테스트 데이터는 Android 승인 근거와 같은 JPEG를 재사용한다. 원본 provenance는 Android 작업공간 `docs/design/2026-11-04-web-reference/README.md:120`이며, 원본 웹 `reference/2026-DAYNOMY-dev/frontend/src/assets/news-home-banner.jpg` → AndroidTest asset → 여기 `assets/news-photo-fixture.jpg`로 복사했다. SHA256은 `0ac56a098fccb71b1496d92b10e2e8bef19776b522d86e5ad1ffc7914cd9b76a`다. 첫 기사만 상대 JPEG route로 연결하고 기존 합성 PNG route를 보존한다. 이 JPEG는 테스트 fixture 전용이며 앱 번들·제품 APK·기본 대체 사진에 포함하지 않는다.

실제 테스트 함수 수는 공통5 + Next 탐색 개정7 + Market 탐색 개정2 = **14개**다. 이전 15개/Next8개 표기는 함수 수를 잘못 센 기록이며 여기서 정정한다.

추가 인수(14개 기준 이후): `DaynomyCommonSelloutUITests.testFullSelloutRetainsCumulativeRealizedProfitAndLedger`는 매수2주×110원→전량매도2주×150원 후 보유0·누적 실현손익80원·매수/매도 원장 보존과 첫 거래 안내 부재를 검사한다. 기대값은 서비스 F05(`spec/service.md:147,155,162`) 및 원본 `PortfolioLedgerCalculator.java:53–65`의 proceeds 누적 후 quantity0 position 제거를 대조했다. Swift 원장도 누적값과 positions를 별도로 반환한다. 기존 부분매도/삭제 인수는 수정하지 않는다.

`DaynomyCommonVisualUITests`의 normal/accessibilityXXXL 2개는 각각 포트폴리오 첫 진입·이슈 첫 사진·계정 로그인 3화면을 `XCTAttachment.keepAlways`로 남긴다. accessibility 실행은 `-UIPreferredContentSizeCategoryName UICTContentSizeCategoryAccessibilityXXXL`을 사용한다. root가 iPad normal·phone dark/large 대상에서 선택 실행한다. 캡처 첨부는 자동 시각/VoiceOver 합격이 아니며 root의 실제 확인이 필요하다. 테스트 작성자는 Simulator를 실행하지 않았다.

최초14개 소스와 SHA 사본은 `ui-baseline-before-sellout-visual/`에 보존했다. 이후 검색 장애 인수는 임의 서버 문구를 UI 계약으로 고정한 단언을 제거하고 실제 실패 복구 버튼과 빈 성공 상태 부재·오늘 캐러셀 유지/전환을 검사하도록 보완했다. 기존 `friendlyServiceError`는 타입에 따라 문구를 변환하므로 검색503의 세부 문구는 인수 기준으로 삼지 않는다. fixture 응답/CSRF는 그대로다. 현재 총 함수 수는 기능15 + 시각2 = 17개다.

실행 직전 최종 보완: 검색 실패는 `newsSearchError` 오류 영역 존재·다시 시도·빈 성공 부재를 단언한다. 기존 부분매도 원장80원 단언 직후 `portfolio-populated-realized80` keepAlways 화면 첨부만 추가했다. 기준값/기존 삭제 단언은 바꾸지 않았다.

실UI 증거 `.local/common-phone-ui.log:1329`의 HoldingRemoval 실패는 삭제 완료 후 기존 거래가 남은 빈 보유에 첫 거래 안내를 기대한 문구 충돌이다. 해당 테스트의 정확 문구 한 곳만 `현재 보유 자산이 없어요.`로 개정하고 원본 매수 원장 존재 인수는 유지했다. 수정 전 소스는 `ui-baseline-holding-removal-caption/`에 보존했다. 거래 전체 삭제 시 첫 거래 안내 기준은 그대로다.

최종 범위 보완: 공통 명세14절의 포트폴리오 AI 단독 진입 인수 `testPortfolioAnalysisOpensWithoutCalendar`를 추가했다. guest 상태에서 `portfolioAnalysis` → `AI 포트폴리오 분석` 제목을 확인하고 투자 캘린더 section·이전/다음 달 버튼 부재를 검사한다. 생성 액션은 누르지 않는다. 변경 전 앱 source와 CommonUI 원문은 `ui-baseline-analysis-entry/`에 보존했고, 해당 시점 단독 진입/캘린더 guard 미구현을 정적 RED로 기록했다. fixture는 그대로다. 최종 기능16 + 시각2 = 18개이며 이번 명세 맞춤 이후 범위 확장은 없다.

실UI 검색 제출 인수 실패(`.local/common-phone-ui.log:2186`)의 전체 앱 Button 조회는 시스템 키보드 Search 키도 포함한다. 제품 본문은 DiscoveryView의 ScrollView 안에 있으므로 별도 검색 제출 버튼 부재 단언을 `app.scrollViews.buttons["검색"]`로 한정했다. 미제출 초안·Enter 이후 Search API 결과·검색 해제·오늘 선택 유지 기준은 그대로다. 수정 전 소스는 `ui-baseline-search-keyboard-scope/`에 보존했다. 캐러셀44pt 기준은 변경하지 않았다.

의견 시트 진입/전송 식별자 개정: `.local/related-ui.log:846` 실제 Sparse tree에서 계정 배경 진입과 시트 전송이 같은 `의견 보내기` label로 조회되어 중복 매칭됐다. 두 의견 인수의 진입은 `openFeedback`, 전송은 `sendFeedback`으로만 구분했다. 비활성·실제 CSRF 전송·성공 초기화·거절 후 초안/재전송 가능·계정 복귀 기준은 보존했다. 수정 전 두 소스는 `ui-baseline-feedback-identifiers/`다.
