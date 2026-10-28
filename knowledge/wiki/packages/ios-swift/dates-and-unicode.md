---
title: ios-swift — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E26", "B04", "E22", "W02", "DX03", "DX09"]
---

# 날짜·시간대·Unicode

## 날짜를 Date로 표현할지 먼저 의미를 정한다

Date는 시각이며 날짜 전용 baseDate와 의미가 다르다. YYYY-MM-DD를 임의 현지 자정으로 만든 후 시간대 변환하면
다른 날짜가 될 수 있다(B04/E22). 원본 거래 입력과 종가 응답의 검증 층도 다르다.

## 실패하는 변환

```swift
let displayed = DateFormatter.localizedString(from: timestamp, dateStyle: .short, timeStyle: .none)
// 원래 달력 날짜를 유지해야 하는 baseDate에 timestamp 변환을 강제하면 안 된다.
```

## 적용 예

```swift
struct CalendarDate: Equatable {
    let isoText: String
    // 거래 입력에서만 문법·달력·서울 오늘 조건을 검증하는 생성자를 둔다.
    // 종가 응답의 현재 String 계약을 조용히 강화하지 않는다.
}
let text = "😀"
assert(text.count == 1)
assert(text.utf16.count == 2)
assert("e\u{301}" == "é")
```

Swift 문자열 동등성은 canonical equivalence를 고려하므로 서버/JS의 단순 비교와 다를 수 있다(E26).
서버가 UTF-16 길이를 제한하면 String.count 대신 그 단위에 맞는 검사를 사용한다.
DateFormatter의 locale/calendar/timeZone을 시스템 기본에 맡기지 않고 목적별로 고정한다.

## 경계 사례와 확인 범위

실행: emoji의 Character/UTF-16 길이와 분해/합성 문자열 동등성. 날짜 전용 모델·자정·DST·서버 비교는 앱 날짜 어댑터에서 추가 실행해야 한다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
