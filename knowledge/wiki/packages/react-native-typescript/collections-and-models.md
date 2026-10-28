---
title: react-native-typescript — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E54", "E21", "P02", "DX04", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## readonly와 spread는 깊은 불변성을 보장하지 않는다

readonly는 타입 검사에서의 쓰기를 제한하며 런타임 객체를 동결하지 않는다(E54).
React 상태를 복사했다는 이유로 내부 배열/객체까지 분리됐다고 가정하지 않는다.

## 실패하는 변환과 실제 관찰

```typescript
const mutable = [1]; const readOnly: readonly number[] = mutable; mutable.push(2);
test('readonly_is_alias', readOnly.length === 2);
const source = { rows: [{ quantity: 1 }] }; const copy = { ...source };
source.rows[0].quantity = 2;
test('spread_is_shallow', copy.rows[0].quantity === 2);
```

## 적용 예

```typescript
const next = {
  ...state,
  rows: state.rows.map(row => row.assetId === targetId
    ? { ...row, quantity: nextQuantity }
    : row),
};
```

변경한 경로만 새 값으로 만들고, 어떤 경로가 공유되는지 설명한다. 임의 객체의 JSON stringify/parse 왕복을
일반 깊은 복사로 쓰면 undefined·날짜·BigInt·특수 타입 의미가 바뀔 수 있다.
정렬은 원본 배열을 직접 sort하는지 확인하고, UI key는 서버 ID를 사용한다.

Map/Set 변환은 서버의 중복·정렬·첫 값 우선 정책과 일치해야 한다. 캘린더의 같은 자산 첫 수량 채택과
계산 API의 중복 거절은 다른 기능 규칙이다(P02).

## 경계 사례와 확인 범위

실행: readonly alias, spread shallow copy. React 렌더링·메모이제이션·RN 리스트 identity는 실제 컴포넌트에서 추가 검사한다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
