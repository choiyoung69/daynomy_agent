# iOS SDK 후속 독립 상태 회귀

기준 커밋: `892151432ee774a735f04de731c6379717585b01`. 기존 고정 검사·앱 구현은 이 역할에서 수정하지 않았다. 모든 명령은 저장소 루트에서 실행했고 Xcode compiler 명령에는 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`를 지정했다. Swift Observation macro 실행은 sandbox subprocess 제한 때문에 escalation이 필요했다. 최초 sandbox compiler 오류는 제품 결함 RED로 세지 않았다.

| 검사 | 수정 전 | 수정 후 | 범위 |
| --- | --- | --- | --- |
| 기존 `run_state_contract.py`의 13-check Swift 본문 | 7 실패 | 13 통과 | F2 EMPTY/FAILED null, F3 평가 실패, F6 idle spinner, F7 빈 수량 삭제 |
| 새 `run_async_state_contract.py` | 17 중 12 실패 | 17 통과 | F2 계정·동일 계정 응답 경쟁, F3 member holdings 이후 histories 실패, F6 stale matches/ABA/선택 후 늦은 응답, F7 잘못된 수량 삭제·거래 보존 |
| 새 `run_news_route_contract.py` | 16 중 8 실패 | 16 통과 | F5 canonical `/news/{id}`와 잘못된 내부 뉴스 URL 경계 |
| 기존 `run_presentation_contract.py` | 10 통과 | 변경 없음 | F1 content/items, F4 작성 category3개 |
| 기존 `check_source_wiring.py` | 9 통과 | 9 통과 | helper 실제 연결·history 최소 account wiring |
| 새 `check_financial_identity.py` | 기준선에 연결 없음 | 1 통과 | AppShell 금융 navigation 수명과 로그인/user ID 연결 |

새 비동기 검사의 마지막 GET EMPTY → POST READY 사례는 기준선에서도 통과한다. 기준선의 null 무시 결함이 그 사례를 가리므로, 이 단일 사례를 수정 전 race 재현으로 주장하지 않는다. EMPTY 제거 검사와 함께 유지하는 후속 회귀다.

## 실행

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 experiments/ios-sdk-verification/test-author/run_async_state_contract.py --revision 892151432ee774a735f04de731c6379717585b01
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 experiments/ios-sdk-verification/test-author/run_async_state_contract.py
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 experiments/ios-sdk-verification/test-author/run_async_state_contract.py --baseline
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 experiments/ios-sdk-verification/test-author/run_news_route_contract.py
python3 experiments/ios-next-verification/test-author/check_source_wiring.py
python3 experiments/ios-sdk-verification/test-author/check_financial_identity.py
shasum -a 256 -c experiments/ios-sdk-verification/test-author/frozen.sha256
shasum -a 256 -c experiments/ios-sdk-verification/test-author/verified-source.sha256
```

기존 runner의 SearchProbe는 `searchGeneration` 등의 새 저장 프로퍼티를 선언하지 않는다. 기존 파일을 수정하지 않고 새 runner가 production `@State` 선언과 메서드를 함께 추출한 뒤 `--baseline`으로 기존 `StateRegressionContract.swift` 원문을 실행한다. 선언의 SwiftUI wrapper·private 접근 제한만 제거하며, 시험 대상 메서드는 재구현하지 않는다. `--revision`은 view source만 지정 커밋에서 읽는다. 이번 작업에서 core 파일은 변경하지 않았다.

## 근거와 한계

- 계약: `spec/ios-native/{interfaces,clarifications,full-contract}.md`, KB `wiki/platforms/ios.md`와 `packages/ios-swift/{state-and-navigation,async-and-cancellation}.md`, 기존 F1–F7 리뷰.
- 기존 presentation/route 기대값은 서버 `service_discovery.rs`의 news search `content`, contents `sourceType/url` DTO 및 `service_admin_news.rs`의 작성 enum과 대조했다. 원본 내부 뉴스 URL `/news/{news.id}` 확인은 독립 리뷰 역할의 원본 대조와 연결한다.
- `baseline-state.log`, `async-state-red.log`, `news-route-red.log`는 수정 전 실제 실행 결과다. `baseline-source.sha256`은 당시 읽은 소스 식별이며 RED 재현 범위를 명시한다.
- `frozen.sha256`은 새 검사와 RED 로그를 고정한다. 마지막 대조에서 9개 모두 일치했다. `verified-source.sha256`은 GREEN 실행 때의 앱 소스를 고정한다.
- 합성 actor/HTTPTransport를 사용한 host 상태 검사이며 UI 프레임·실제 계정 로그인·Simulator·iOS URLSession·Rust/DB 실행 증거가 아니다. static identity도 이전 계정 데이터가 한 프레임도 표시되지 않았다는 증거가 아니다. Simulator는 root 역할이 독점하며 이 역할은 xcodebuild/UI 실행을 하지 않았다.

새 XCUITest 파일과 프로젝트 연결은 추가하지 않았다. 기존 UI fixture와 Next 테스트의 플랫폼 실행·fixture smoke는 root의 실행 범위다.
