---
title: react-native-typescript — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E29", "E21", "F01", "F02", "F03", "DX04", "DX09"]
---

# 타입·null·JSON 디코딩

## TypeScript 선언과 응답의 실체는 별개다

서버에서 온 데이터는 unknown으로 받고 type guard로 필수 필드·숫자 범위·enum·null을 검증한다(E29).
`request<Row>()`의 제네릭이나 `as Row`는 런타임 JSON을 바꾸지 않는다(F03).

## 실패하는 변환

```typescript
const row = await response.json() as Row;
setPrice(row.closePrice); // 문자열/누락/Infinity 등 실제 타입 검사 없음
```

## 적용 코드

```typescript
function checkedId(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('ID_RANGE_OR_TYPE');
  }
  return value;
}
function fieldPresence(object: Record<string, unknown>, key: string): 'missing' | 'null' | 'value' {
  return !Object.hasOwn(object, key) ? 'missing' : object[key] === null ? 'null' : 'value';
}
```

존재 의미를 보존하는 PATCH 모델은 `{kind:'missing'}` / `{kind:'null'}` / `{kind:'value',value}` 같은
구분된 union으로 표현할 수 있다. undefined는 객체 JSON에서 생략되므로 의도치 않은 삭제/유지를 만들지 않는다(E21).

| JSON 입력 | 기존 계약과 검사 |
| --- | --- |
| assetId:"1" | 숫자형 ID 계약에서 거절 |
| assetId:9007199254740993 | 이미 반올림될 수 있으므로 안전 정수 거절 |
| currency 누락/null | 원본 fallback과 필드별 계약을 구분 |
| 추가 필드 | 허용 여부와 필수 필드 검사는 별도 |

204는 JSON을 읽지 않고 빈 응답으로 처리한다. 잘못된 성공 본문은 HTTP 오류와 다른 디코딩 실패다.

## 경계 사례와 확인 범위

실행: 안전 ID·따옴표 ID·누락/null·undefined 생략. 원본 웹 디코더의 23개 사례는 공통 계약이며 RN Fetch/엔진에서의 재실행은 별도다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
