---
title: ios-swift — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "E43", "F03", "R02", "W05", "DX03", "DX09"]
---

# 오류·자원·트랜잭션 경계

## Error와 서버 상태를 일대일로 단순 치환하지 않는다

URLSession 전송 오류, HTTP 4xx/5xx, DecodingError, 업무 code, 취소를 구분한다(E43).
200 응답의 잘못된 JSON을 성공으로 표시하지 않는다. 204는 빈 본문 계약을 따른다(F03).

## 실패하는 변환

```swift
catch { try await api.createTransaction(request) }
// 서버가 이미 커밋했을 수 있다. 응답 유실을 미적용으로 판단한다.
```

## 적용 예

```swift
enum Submission {
    case sending
    case confirmed(transactionID: Int64)
    case rejected(code: String)
    case outcomeUnknown
}
```

오류 status/code와 입력 필드 오류를 별도로 저장한다. 원문 응답 전체나 토큰을 로그로 남기지 않는다.
서버 결과를 못 확인한 변경 요청은 확인 경로/중복 방지 계약에 따라 처리하고 비멱등 자동 재시도를 넣지 않는다(E19).

```swift
func withResource<T>(_ resource: Resource, body: () throws -> T) rethrows -> T {
    defer { resource.close() }
    return try body()
}
```

Resource는 앱이 정의할 자원 인터페이스 예다. defer 정리는 메모리/자원 책임이며 서버 DB 롤백을 보장하지 않는다(R02).

## 경계 사례와 확인 범위

HTTP 실패·잘못된 성공 본문·취소·커밋 후 응답 유실을 별개 사례로 확인해야 한다. 이 문서의 Resource/거래 인터페이스는 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
