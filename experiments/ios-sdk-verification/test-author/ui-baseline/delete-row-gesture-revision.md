# 거래 행 스와이프 위치 개정

root의 실패 관련2개 재실행에서 spinner 검사는 통과했다. 매수/수정/매도/삭제 검사는 손익80원·보유10주 평균110원까지 통과한 뒤 새로 도달한 삭제 제스처 단계에서 멈췄다. 이 시점 개별 UI 인수는 9개 통과·1개 미완료이며, 그 마지막 흐름의 삭제와 빈 원장 기대값을 통과로 세지 않는다.

## 실제 위치 근거

`.local/final-two-attachments/83408F8C-0DD9-47FE-9426-0C23B616B59E.txt`의 line119에서 매도 거래 Button frame은 `{{16.0, 779.0}, {370.0, 81.3}}`다. line141에서 TabBar frame은 `{{0.0, 791.0}, {402.0, 83.0}}`다. 행 중앙 y819.65가 탭바 안에 있다. 실제 구간은 `trade-row-swipe-accessibility-excerpt.txt`에 보존했다.

녹화 `1219C598-3D6B-4D3E-BFC8-AB0E9965BD75.mp4`의 끝 0.4초 전 프레임 `trade-row-swipe-failure.png`를 직접 확인했다. 거래 내역 header 아래 행이 탭바 뒤에 가려져 있고 삭제 버튼이나 삭제 확인 dialog는 없다. 전체 AX에도 삭제/거래삭제 dialog가 없다. 따라서 full-swipe가 삭제 확인을 자동으로 연 상태는 아니다. 기존 `reveal`의 `isHittable` 조건이 행을 부분 노출 상태에서 수용한 뒤 그 중앙을 swipe한 위치 문제가 관측 근거다. 이 실행만으로 제품의 swipeActions 자체가 고장났다고 단정할 근거는 없다.

## 개정

`deleteRow`만 변경했다. 행 전체 frame이 navigation bar 하단+8과 tab bar 상단-12 사이에 들어올 때까지 최대7회 방향에 맞게 스크롤하고, 그 조건을 명시적으로 단언한다. 가려지지 않은 행 안에서 x90%→45%의 partial drag로 삭제 action을 노출한 뒤 정확한 `삭제` 버튼 존재를 기다린다. 부분 제스처는 full-swipe의 자동 action 경로를 피하고 기존의 명시적 두 단계 확인을 유지한다.

그 뒤 기존 `거래 삭제` 확인, 해당 거래 행 부재, 매도 삭제 후12주 평균110원, 매수 삭제 후 빈 보유와 빈 거래 원장 기대값은 그대로다. 오류를 무시하거나 조건부 skip하지 않았다. 앱·fixture·지연은 변경하지 않았다.

직전 버전은 `DaynomyNextUITests.activity-profit-revision.swift`, 개정 diff는 `delete-row-gesture-revision.diff`, 관련 원문·frame·AX·diff·현재 Next 소스 SHA256은 `delete-row-revision.sha256`이다. 이전 단계 manifest의 현재 소스 경로는 후속 개정으로 달라졌으며 그때 소스를 별도 사본으로 보존했다.

Xcode Swift frontend parse는 통과했다. root가 마지막 미완료 UI1을 재빌드·실행한다. 실제 삭제와 빈 원장 완료 여부는 그 실행 결과로 판단하며 이 기록만으로 통과를 주장하지 않는다.
