# 매도 Picker 접근성 조회 개정

root의 첫 표준폰 NextUI 7개 실행은 4개 통과·3개 실패다. 실패는 pending spinner 확인, guest buy/edit/sell/delete, guest oversell이며 뒤의 두 검사는 같은 `openTrade` helper에서 매도 유형을 선택하기 전에 멈췄다. 첫 4개 통과를 나머지 기능 검증으로 확대하지 않는다.

실제 `.local/next-ui-attachments/5C17CD46-2881-4E60-8C17-249BF2C0A4B4.txt`의 같은 거래 editor accessibility hierarchy에서 다음을 확인했다.

- line236: `Button`의 label은 `유형, 매수`다.
- line237: 하위 `StaticText`의 label은 `매수`다.
- line238: 별도 `StaticText`의 label은 `유형`이다.

원래 `app.buttons["유형"]`는 실제 버튼을 찾지 못했다. 관련 실제 AX 구간은 `picker-accessibility-excerpt.txt`에 보존했다. 이 근거로 현재 Next 소스의 해당 query만 label이 정확히 `유형` 또는 `유형, 매수`인 Button으로 개정했다. OR의 첫 값은 기존 환경의 원래 조회를 유지하고 두 번째 값은 관측된 iOS 27 AX label이다. 임의 다른 버튼을 허용하는 contains query로 확대하지 않았다.

매도 메뉴 선택·수량·단가·oversell 오류·sheet 보존·기존 원장 결과 단언은 그대로다. 원본 Next 전체는 `DaynomyNextUITests.original.swift`, 수정 diff는 `picker-query-revision.diff`, 원본/AX/diff/새 소스 해시는 `picker-revision.sha256`에 보존했다. `next-original.sha256`은 개정 전 baseline 시점의 경로/해시이며 현재 Next 경로는 의도적으로 변경됐다. 원본 fixture는 계속 불변이다.

Xcode Swift frontend parse는 통과했다. root는 개정 후 기존 UI3과 실패 관련3을 재빌드·실행하며, 이미 통과한 Next4는 같은 앱 소스이므로 불필요하게 반복하지 않는다. 실제 재실행 결과는 root의 SDK/UI 결과 부록에서 판단한다. 이 문서는 재실행 성공을 선행 주장하지 않는다.
