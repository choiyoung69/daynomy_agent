---
title: react-native-typescript — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E22", "W02", "F01", "G11", "DX04", "DX09"]
---

# 날짜·시간대·Unicode

## Date·locale·Unicode 기본값을 변환 규칙으로 숨기지 않는다

표준 날짜 전용 문자열은 UTC로 읽는 JS 규칙이 있다(E22). 현지 표시로 바꾸면 다른 달력 날짜가 될 수 있다.
거래 입력은 서울 오늘과 올바른 달력 날짜를 검사하고, 종가 API는 현재 String 타입까지만 검사한다(W02/F01).

## 실패하는 변환

```typescript
const baseDateLabel = new Date(api.baseDate).toLocaleDateString();
// 날짜 전용 기준일을 장치 시간대로 변환한다.
```

## 적용 코드

```typescript
const baseDateText = api.baseDate; // 날짜 전용 값의 의미를 유지
const utf16Length = '😀'.length;   // 2
const scalarCount = Array.from('😀').length; // 1
const equalRaw = String('e\u0301') === String('é'); // false
```

길이 단위·trim·정규화·대소문자 정책을 서버와 대조한다. TextInput의 길이 제한만으로 서버 정책을
완전히 검증했다고 하지 않는다. grapheme 단위 자르기는 별도 Unicode 처리 요구다.

Intl/locale/시간대 지원은 선택한 RN 엔진·OS 버전에 따라 확인한다. Node의 시간대 예제를 RN 호환 결과로 재사용하지 않는다.

## 경계 사례와 확인 범위

실행: UTF-16/scalar 길이·분해 문자열 비교, 기존 Node 시간대 이동 예제. RN 엔진 Intl·서울 자정·DST·기기 locale은 별도다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
