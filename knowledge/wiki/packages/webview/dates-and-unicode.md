---
title: webview — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E22", "E26", "G11", "B04", "DX04", "DX09"]
---

# 날짜·시간대·Unicode

## 웹과 호스트가 다른 날짜/문자열 의미를 가질 수 있다

웹 baseDate를 호스트 Date/Instant로 바꾸고 다시 웹에 넘기는 과정에서 날짜가 이동할 수 있다(B04/E22).
문자열 길이·동등성도 JS UTF-16, Swift Character/canonical equality, Kotlin의 문자열 처리 사이에서 다르다.

## 실패하는 변환

```typescript
postToHost({ baseDate: new Date(api.baseDate).toISOString() });
// 달력 날짜를 시각 계약으로 변환한다.
```

## 적용 메시지 예

```json
{"v":1,"id":"price_1","method":"showPriceDate","payload":{"calendarDate":"2026-10-28"}}
```

이 메시지는 날짜 의미 설명용 제안이며 현재 실행한 close-only 프로토콜에는 포함되지 않는다.
새 method를 허용하려면 양쪽 allowlist와 payload 검사를 추가하고 별도 fixture를 만든다.

| 값 | 확인한 언어 의미 |
| --- | --- |
| 😀 | JS/Kotlin UTF-16 길이 2, Swift Character 1 |
| e+결합 악센트 / é | Swift 동등 가능, JS 단순 비교는 다름 |
| NBSP 양쪽 삼성 | Kotlin trim/Rust trim과 Java strip의 차이 있음 |

경로·검색·닉네임·브리지 id를 표시 문자열과 동일한 정규화 규칙으로 일괄 처리하지 않는다.

## 경계 사례와 확인 범위

언어별 작은 문자열/시간대 예제는 실행했다. 브리지 날짜 method와 실제 OS 표시 왕복은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
