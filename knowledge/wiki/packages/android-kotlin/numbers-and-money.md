---
title: android-kotlin — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E23", "E46", "E63", "P02", "W02", "DX01", "DX09"]
---

# 숫자·금액·반올림

## 금액은 입력·전송·계산·표시를 나눠 본다

JVM BigDecimal은 문자열에서 구성한다. 기존 종가 JSON은 숫자이며 문자열 JSON으로 일괄 변경하지 않는다.
JsonPrimitive의 숫자 여부와 null을 검사한 뒤 content를 십진 원문으로 처리하는 어댑터가 필요하다(E46/E63).

## 실패하는 변환

```kotlin
val inheritedError = BigDecimal(0.1 + 0.2) // 이진 소수의 근삿값을 받아 버린다.
val id = jsonDouble.toLong()              // 소수 ID의 절삭 또는 이미 잃은 정밀도를 허용한다.
```

## 적용 코드

```kotlin
val exact = BigDecimal("0.1") + BigDecimal("0.2")
check(exact == BigDecimal("0.3"))
val displayed = BigDecimal("1.005").setScale(2, RoundingMode.HALF_UP)
check(displayed.toPlainString() == "1.01")
```

이는 예제 금액의 반올림이다. DAYNOMY의 거래 단가는 소수 4자리, 비용은 2자리, 환율은 6자리 등
필드별 제약이 있으므로 모든 값을 입력 즉시 2자리로 만들지 않는다(P02/W02).
편집 중에는 문자열을 유지한다. locale 쉼표·통화 기호는 표시 계층에서 처리한다.

| 사례 | 기대 결과 |
| --- | --- |
| 1.005를 표시용 scale=2 HALF_UP | 1.01 |
| 수량 1.5 | 정수 검사 실패 |
| 단가 0 | 편집기와 API의 검사 층을 구분 |
| 큰 ID → Double → Long | 허용 경로로 사용하지 않음 |

## 경계 사례와 확인 범위

BigDecimal 합과 HALF_UP 양수 경계는 실행했다. JSON 숫자 원문의 모든 지수 표기·최대 precision·DB numeric 왕복은 별도 어댑터 검사 대상이다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
