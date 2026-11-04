# 빈 단가 XCUITest assertion 개정

root가 표준 iPhone 17 / iOS Simulator 27.0에서 실행한 원본 UI 3개 중 탭 진입과 종목 선택·종가·변경은 통과했고 `testManualDeletionRemainsEmptyAfterLateQuote`의 마지막 assertion만 실패했다. 본 역할은 Simulator를 제어하지 않고 기존 `.local/baseline-phone-ui.xcresult`의 결과·활동과 root가 export한 attachment를 읽었다.

## 실제 관측

- 원본 Swift의 SHA256: `413d7063bf4ed310cc54dbb57c2ca839e590d1874d3832c098f763ee1589d907`. `DaynomyIOSUITests.original.swift`에 그대로 보존했다.
- 원본 마지막 비교는 `price.value == ""`이며 xcresult의 실제 값은 `Optional("단가")`였다. 77 입력, 두 번 삭제, 종가 기준일 존재 확인 후 발생했다. 해당 구간은 `manual-deletion-failure.log`다. 공개 사본의 개인 절대경로는 `<worktree>`로 치환했으며 원시 원문은 로컬 전용 `.local/manual-deletion-failure-original.log`에 보존했다. 치환 후 해시를 다시 기록했다.
- root export manifest의 테스트 ID는 `DaynomyIOSUITests/testManualDeletionRemainsEmptyAfterLateQuote()`이고 녹화 attachment는 `89D6D31E-7F52-441A-AFDB-F7CFCD0A3B7A.mp4`다. 이 녹화 길이 19.598333초의 끝 0.3초 전 프레임을 ffmpeg로 추출해 `empty-price-at-failure.png`로 보존하고 직접 확인했다. 단가 입력에는 옅은 placeholder `단가`만 보이며 77과 123.4500은 보이지 않는다. 전체 hierarchy attachment는 이 export에 없었다.
- 제품 소스 `MarketView.swift`의 `TextField("단가", ...)`와도 placeholder가 일치한다. 이 관측은 빈 TextField를 XCUITest가 placeholder 문자열로 읽은 플랫폼 차이와 부합한다.

## 최소 개정과 범위

실제 현재 `clients/ios/UITests/DaynomyIOSUITests.swift`의 마지막 assertion만 개정했다. `placeholderValue == "단가"`를 요구하고 `value == ""` 또는 `value == placeholderValue`만 수용한다. nil·77·123.4500·임의 문자열·다른 placeholder는 수용하지 않는다. 77 입력→삭제→늦은 종가 기준일 대기 순서와 timeout은 그대로다. `assertion-revision.diff`에 개정 diff, `revision.sha256`에 원본·화면·실패·diff·현재 테스트 해시를 기록했다.

Xcode Swift frontend parse는 통과했다. 개정 후 UI 실행과 최종 build는 root가 수행한다. 이 기록만으로 개정 검사의 플랫폼 통과를 주장하지 않는다. Duo의 tab 조회와 pending-search fixture는 수정하지 않았다.

화면 추출 명령:

```sh
ffmpeg -v error -sseof -0.3 -i .local/baseline-phone-attachments/89D6D31E-7F52-441A-AFDB-F7CFCD0A3B7A.mp4 -frames:v 1 experiments/ios-sdk-verification/test-author/ui-baseline/empty-price-at-failure.png
```
