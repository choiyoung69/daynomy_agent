---
title: ios-swift — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E42", "P02", "W02", "B04", "DX03", "DX09"]
---

# 숫자·금액·반올림

## Decimal도 입력 경로와 반올림 정책을 명시해야 한다

Double에서 이미 잃은 정밀도를 Decimal 생성으로 복구할 수 없다. 원시 JSON을 바로 Decodable Decimal로 읽는
대상 버전의 동작과 지수/자릿수 한도를 검사해야 한다. 기존 예제는 제한된 표본의 근거다(E42).

## 실패하는 변환

```swift
let inherited = Decimal(0.1 + 0.2)
// 먼저 수행한 Double 연산의 오차를 없애는 수단이 아니다.
```

## 적용 코드

```swift
let exact = Decimal(string: "0.1")! + Decimal(string: "0.2")!
var input = Decimal(string: "1.005")!
var rounded = Decimal()
NSDecimalRound(&rounded, &input, 2, .plain)
// 예제의 강제 언래핑은 고정 리터럴에만 사용. 사용자 입력에는 guard/오류 처리.
```

거래 단가·비용·환율은 자릿수와 최소값이 다르므로 입력 즉시 같은 scale로 바꾸지 않는다(P02/W02).
화면에 쓰는 locale 포맷과 JSON 전송 숫자는 별개다. 금액이 숫자 JSON인 API를 문자열 API로 바꿀 때는 서버 계약 변경이 필요하다.

| 입력/상황 | 검사 |
| --- | --- |
| amount:0.1 JSON | 현재 Foundation에서 Decimal 0.1 읽기 |
| 1.005 → 표시 scale2 | 양수 반올림 1.01 |
| 소수점 수량 | 정수 수량 거절 |
| 과도한 지수·정밀도 | 선택한 Foundation 버전에서 거절/보존 정책 확인 |

## 경계 사례와 확인 범위

현재 macOS Foundation의 JSON Decimal 표본 0.1과 문자열 1.005 반올림을 실행했다. 임의 precision 전체와 iOS SDK 동일 동작을 보장하지 않는다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
