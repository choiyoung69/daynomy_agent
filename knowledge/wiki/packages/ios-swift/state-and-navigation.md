---
title: ios-swift — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E33", "E18", "F04", "DX03", "DX09"]
---

# UI 상태·탐색·수명

## 모델의 소유자와 view 작업 수명을 연결한다

SwiftUI 상태의 소유자를 모델에 두고 UI 변경의 actor 격리를 명시한다(E33).
Observation 지원 OS 조건과 task 오버로드의 SDK 조건을 확인한다. 현재 E18의 새 매개변수를 구형 SDK에 복사하지 않는다.

## 실패하는 변환

```swift
Task.detached {
    self.rows = try await api.search(query) // UI 격리·소유자·이탈 처리 누락
}
```

## 적용 예

```swift
@MainActor
final class SearchState {
    var query = ""
    var manualPrice = ""
    var priceEdited = false
    var generation = 0
    // 선택한 Observation/ObservableObject 방식과 view 소유 수명에 연결한다.
}
```

최신 결과의 반영 조건은 다음 순서로 정한다.
1. 요청 세대가 현재인가.
2. 요청한 assetId가 현재 선택인가.
3. 화면/모델 소유자가 살아 있는가.
4. 사용자가 단가를 수정했는가.

NavigationStack·sheet·back gesture·딥링크 복귀·백그라운드 복귀에서 보존할 초안과 재조회 조건을 정한다.
VoiceOver label·Dynamic Type·안전 영역·키보드 초점은 기기에서 검사한다.

## 경계 사례와 확인 범위

순수 actor Gate만 실행했다. @MainActor UI 모델 예시는 통합 설계 코드이며 SwiftUI 뷰·탐색·복원 테스트를 수행하지 않았다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
