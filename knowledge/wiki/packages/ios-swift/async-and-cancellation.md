---
title: ios-swift — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E13", "E56", "E43", "F04", "DX03", "DX09"]
---

# 비동기·취소·요청 경쟁

## Task 취소와 actor 직렬성만으로 응답 역전을 해결하지 않는다

Swift Task 취소는 협력적이고, actor 메서드도 await로 중단된 사이 다른 작업이 상태를 바꿀 수 있다(E13/E56).
await 전에 고른 종목이 응답 도착 때도 선택돼 있다고 가정하지 않는다.

## 실패하는 변환

```swift
let response = try await api.search(query)
self.results = response // 이미 새 검색이 시작됐을 수 있다.
```

## 적용 코드

```swift
actor Gate {
    private var generation = 0
    private var alive = true
    private(set) var result: String?
    func begin() -> Int { generation += 1; return generation }
    func accept(_ token: Int, _ value: String) -> Bool {
        guard alive && token == generation else { return false }
        result = value
        return true
    }
    func dispose() { alive = false; generation += 1 }
}
```

Task 소유자가 요청을 취소하고 응답·오류·로딩 반영 모두에서 세대를 확인한다.
CancellationError를 일반 오류 알림이나 자동 재전송으로 바꾸지 않는다.

```swift
let work = Task { try await Task.sleep(for: .seconds(600)) }
work.cancel()
do { try await work.value }
catch is CancellationError { /* 취소 상태: 사용자 실패 알림과 분리 */ }
```

Task.sleep의 취소 관찰과 URLSession 실제 요청 취소·쿠키·delegate 동작은 다른 검사다(E43).

## 경계 사례와 확인 범위

실행: actor Gate의 최신 세대·이탈 후 무시와 Task.sleep 취소. iOS URLSession/SwiftUI 통합 취소는 미실행이다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
