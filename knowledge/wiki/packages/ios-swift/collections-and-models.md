---
title: ios-swift — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E52", "E61", "P02", "DX03", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## Array가 값 타입이어도 참조 요소는 공유된다

Swift struct/Array의 값 의미와 class 요소의 참조 의미를 구분한다(E52/E61).
Kotlin data class copy나 JS spread와 동일한 복사 규칙이라고 가정하지 않는다.

## 실패하는 변환

```swift
let rows = [ReferencePosition()]
let snapshot = rows
rows[0].quantity = 2
// snapshot[0].quantity도 2다.
```

## 적용 코드

```swift
struct Position { var quantity: Int }
final class ReferencePosition { var quantity = 1 }
```

```swift
var rows = [Position(quantity: 1)]
let snapshot = rows
rows[0].quantity = 2
assert(snapshot[0].quantity == 1)
```

값 모델을 선택해도 내부에 class/closure/reference storage가 있으면 그 수명을 따로 검토한다.
서버 ID를 안정적인 식별자로 쓰고 표시 이름·배열 위치를 identity로 쓰지 않는다.
Set/Dictionary로 변환할 때 순서·중복 첫 값/마지막 값·동률 정렬 정책을 유지한다.

## 경계 사례와 확인 범위

실행: struct 배열 복사 후 독립성, class 요소 배열의 공유. SwiftUI diff/Observation 영향은 UI에서 별도 검사한다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
