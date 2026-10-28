---
title: react-native-typescript — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["P02", "W02", "F01", "B04", "DX04", "DX09"]
---

# 숫자·금액·반올림

## number는 서버 BigDecimal과 같은 계산 모델이 아니다

JSON 파싱 단계, 계산 단계, 표시 단계를 나눈다. 서버의 소수 자릿수·HALF_UP을 JS toFixed나
Math.round의 기본 동작으로 일괄 대체하지 않는다(P02/W02). 표시 문자열을 다시 숫자로 읽는 왕복도 검토한다.

## 실패하는 변환

```typescript
const total = 0.1 + 0.2;
const id = Number('9007199254740993');
// total과 id가 원문의 십진수/정수 정밀도를 모두 보존한다고 가정
```

## 적용 계약 예

```typescript
type EditedAmount = { text: string; currency: 'KRW' | 'USD'; scale: 2 | 4 | 6 };
function validateQuantity(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('QUANTITY_RANGE');
  }
  return value;
}
```

금액 라이브러리/정수 스케일 모델을 선택하더라도 입력·API 숫자 직렬화·서버 numeric 경계의 precision을 검사한다.
원문을 number로 잃은 뒤 문자열로 바꾸는 것은 복구가 아니다. 외부 decimal 라이브러리는 현재 고정하지 않았다.
단가를 API에서 표시하는 요구와 게스트 원장/평가를 계산하는 요구는 서로 다르다.

| 사례 | 판정 |
| --- | --- |
| 0.1+0.2 | JS 이진 소수 차이 재현 |
| 단가 0/음수 | 현행 API의 finite 검사와 편집기의 양수 검사 분리 |
| 수량 1.5 | 정수 입력 거절 |
| 1 USD 환율 | 통화와 환율의 필수 조건 확인 |

## 경계 사례와 확인 범위

이진 소수 차이와 안전 정수는 실행했다. 전체 금액 어댑터·반올림 라이브러리·JSON/DB 왕복은 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
