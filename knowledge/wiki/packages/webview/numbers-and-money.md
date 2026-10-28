---
title: webview — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["F01", "P02", "E23", "E42", "DX04", "DX09"]
---

# 숫자·금액·반올림

## 브리지로 숫자를 넘길 때도 손실 위치를 확인한다

JS number → JSON → Kotlin/Swift 숫자 변환은 정밀도를 되살리는 과정이 아니다.
웹의 Number.isSafeInteger 한도와 거래 금액 precision을 넘는 값은 protocol에서 표현/범위를 먼저 결정한다(F01/P02).

## 실패하는 변환

```typescript
native.postMessage(JSON.stringify({ id: Number('9007199254740993') }));
// 호스트 Long/Int64가 크더라도 JS가 이미 반올림한 ID를 복구하지 못한다.
```

## 적용 예

```typescript
function bridgeAssetId(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('ID_RANGE_OR_TYPE');
  }
  return value;
}
```

금액의 브리지 문자열 표현을 새로 정하더라도 서버 숫자 JSON과 같은 계약이라고 부르지 않는다.
호스트와 웹이 둘 다 계산을 맡으면 반올림/통화/환율 정책이 갈라질 수 있으므로 업무 계산의 소유자를 정한다.
예를 들어 웹이 화면 입력을 소유하고 호스트가 외부 링크/탐색만 맡으면 금액 브리지 자체를 줄일 수 있다.

| 검사 | 기대 |
| --- | --- |
| 안전 정수 한도 | JS와 호스트에 같은 한도 적용 |
| 잘못된 문자열 ID | 암묵 변환 없이 거절 |
| 소수 가격 | 원문·파싱·전송·표시 경로별 precision 확인 |
| 금액 protocol 변경 | 버전·양쪽 어댑터·서버 계약 영향 기록 |

## 경계 사례와 확인 범위

JS 안전 정수 예제는 실행했다. 호스트별 금액 JSON 왕복과 실제 브리지는 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
