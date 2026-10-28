---
title: android-kotlin — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["B04", "F01", "W02", "G11", "E23", "DX01", "DX09"]
---

# 날짜·시간대·Unicode

## 날짜 전용 값과 시각을 분리한다

종가 baseDate는 달력 날짜다. 서버의 LocalDate와 맞추려면 시간대를 갖는 시각으로 무조건 바꾸지 않는다(B04).
거래 입력은 달력 유효성과 서울 기준 미래 여부를 검사하지만, 현행 종가 응답 검사는 문자열 타입까지만 확인한다(F01/W02).

## 실패하는 변환

```kotlin
// 장치의 자정 시각으로 만든 후 UTC로 바꾸면 원래 거래일을 잃을 수 있다.
val calendarDate = inputAsInstant.atZone(deviceZone).toLocalDate()
// Kotlin trim()을 Java strip()과 동일하다고 간주하는 것도 잘못이다.
```

## 적용 코드

```kotlin
val tradeDate = LocalDate.parse("2024-02-29")
check(tradeDate.toString() == "2024-02-29")
check(runCatching { LocalDate.parse("2026-02-30") }.isFailure)
check("😀".length == 2) // UTF-16 코드 단위
check("\u00a0삼성\u00a0".trim().length == 2)
```

Kotlin/JVM도 Java String을 사용하지만 기본 trim의 공백 판정은 Java strip과 다를 수 있다.
실행에서 NBSP를 Kotlin trim은 제거했고 Java strip은 남겼다(G11). 공통 검색의 길이 단위와 공백 정책을 보존한다.
사용자가 보는 글자 수, UTF-16 단위 수, Unicode scalar 수, UTF-8 바이트 수는 서로 다른 기준이다.
정규화나 대소문자 변환을 추가하면 기존 검색·중복 판정이 달라질 수 있다.

## 경계 사례와 확인 범위

실행: 잘못된 LocalDate 거절, emoji 길이, Kotlin NBSP trim. 오늘의 서울 경계와 실제 DB 검색 결과는 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
