---
title: Swift 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E07", "E13", "E26", "E42", "E43", "Q08", "F01", "B04"]
---

# Swift 언어 패키지

iOS 앱과 WKWebView 호스트에 필요한 언어 지식이다. SwiftUI 수명과 화면 구성은 iOS 패키지에서 다룬다.

## 데이터와 직렬화

- ID는 Int64로 디코딩하고 공통 안전 정수 범위를 따로 검사한다. macOS Foundation 예제에서는
  큰 ID를 Int64로 보존했지만 기존 웹보다 API 허용 범위를 넓힌다는 뜻은 아니다(Q08/F01).
- Codable/JSONDecoder는 모델 디코딩 도구다(E42). 필수 필드·추가 필드·enum·통화에 관한 업무 검증까지
  자동 보장하지 않는다. 합성 Optional은 관찰 예제에서 누락/null을 모두 nil로 처리했다(Q08).
  구별이 필요한 수정 요청에는 keyed container의 존재 확인과 null 검사를 사용하는 어댑터를 둔다.
- 가격은 Decimal 기반 처리를 기본 제안으로 삼는다. Double로 먼저 변환한 뒤 Decimal로 바꿔
  정밀도가 회복된다고 가정하지 않는다. JSONDecoder가 선택한 Foundation 버전에서 십진 값을
  어떻게 읽는지는 별도로 검사한다. 기존 예제의 Decimal 검사는 문자열 연산까지의 증거다.
- baseDate는 String 또는 검증된 날짜 전용 모델로 유지한다. Date는 시각이므로 표시 시간대에 따라
  날짜가 바뀌는 문제를 피해야 한다. 서버 계약을 강화하는 달력 검증은 별도 결정으로 남긴다.
- String.count와 UTF-16 길이는 다르며 canonically equivalent 문자열은 같을 수 있다(E26/Q08).
  서버의 길이·중복 정책을 Swift 기본 비교만으로 재현했다고 판단하지 않는다.

## 비동기와 오류

- Task 취소는 협력적이다(E13). 새 검색의 Task와 이전 응답의 반영 권한을 함께 관리한다.
  await 전후에 보유한 UI 상태가 같다고 가정하지 않는다. 요청 세대 번호·선택 종목을 다시 확인한다.
- 네트워크 기본 후보는 URLSession이며 HTTPURLResponse의 상태와 Data 디코딩을 구분한다(E43).
  전송 성공과 HTTP 4xx/5xx, JSON 오류, 업무 실패, 취소를 각각 공통 오류에 연결한다.
- UI 상태 갱신의 actor 격리를 명시한다. Task를 화면 밖에서 생성했다면 소유자와 취소 시점을 정한다.
  완료한 거래의 서버 결과를 화면 이탈 때문에 실패한 거래로 바꾸지 않는다.

## 모듈 경계

Codable DTO, 순수 입력 규칙, API 프로토콜, URLSession 어댑터, UI 모델을 분리한다.
공유 모델을 참조형으로 만들 때 변경 소유자를 명확히 하고, 병렬 Task 사이 값 전달과 Sendable 제약은
선택한 Swift 언어 모드에서 컴파일해 확인한다. Swift 버전과 Xcode/SDK/지원 OS를 각각 기록한다.

## 필수 검사

Optional의 누락/null·정수·Decimal 디코딩·날짜 보존·문자열·Task 취소·UI 격리 경고를 검사한다.
Q08은 macOS Swift 예제이며 iOS 빌드·URLSession 취소·쿠키 검증 결과가 아니다.
[iOS 패키지](../platforms/ios.md), [공통 데이터](../shared/data-semantics.md), [패키지 구성](../shared/package-map.md).

## 상세 패키지

[iOS + Swift의 주제별 문서](../packages/ios-swift/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.
