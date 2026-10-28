---
title: ios-swift — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E42", "F01", "F02", "DX03", "DX09"]
---

# 타입·null·JSON 디코딩

## Optional은 부분 수정의 3상태 모델이 아니다

합성 Decodable의 Optional은 누락/null을 모두 nil로 읽는 사례가 있다. 원본 웹의 optional 필드나
서버의 PATCH 의미가 유지/삭제/값 설정을 구분하면 별도 존재 모델이 필요하다(E42/F01).

## 실패하는 변환

```swift
struct Patch: Decodable { let currency: String? }
// {}와 {"currency":null}을 구별하지 못한다.
```

## 적용 코드

```swift
enum Field: Equatable { case missing, null, value(String) }
struct CurrencyPatch: Decodable {
    let currency: Field
    enum Keys: String, CodingKey { case currency }
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: Keys.self)
        if !container.contains(.currency) { currency = .missing }
        else if try container.decodeNil(forKey: .currency) { currency = .null }
        else { currency = .value(try container.decode(String.self, forKey: .currency)) }
    }
}
struct OptionalCurrency: Decodable { let currency: String? }
struct Money: Decodable { let amount: Decimal }
func decode<T: Decodable>(_ type: T.Type, _ text: String) throws -> T {
    try JSONDecoder().decode(type, from: Data(text.utf8))
}
```

필수 ID는 Int64로 디코딩한 뒤 1...9007199254740991 범위를 확인한다. 네이티브가 더 큰 정수를
읽는다고 기존 웹의 허용 계약을 넓히지 않는다. enum의 알 수 없는 rawValue를 기본 케이스로 바꾸는 정책도 명시한다.
Codable 모델을 만들었다고 status·업무 제약·통화 허용값까지 자동 검증되는 것은 아니다.

## 경계 사례와 확인 범위

실행: 합성 Optional 누락/null, 존재 모델의 missing/null/value, Decimal JSON 표본. 모든 API 필드와 iOS 네트워크 디코딩 검증은 별도다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
