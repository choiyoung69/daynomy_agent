---
title: webview — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E21", "E54", "E04", "E11", "DX04", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## JSON 메시지는 메모리 객체 공유가 아니라 직렬화 경계다

웹의 객체를 호스트로 전송하면 별도의 값이 된다. 참조 identity·클래스 메서드·undefined 등은 유지되지 않는다(E21).
반대로 웹 내부 spread와 readonly는 얕은 복사/타입 제약일 뿐이다(E54).

## 실패하는 변환

```typescript
const pending = { id: 'x', payload: model };
postToHost(pending);
model.price = 2;
// 호스트가 같은 객체를 참조하며 자동으로 바뀔 것이라고 가정
```

## 적용 계약 예

```typescript
type MessageState = {
  id: string;
  version: 1;
  payloadSnapshot: string; // 검증한 값의 직렬화 결과
};
```

프로토콜의 요청/응답은 id로 연결하고, payload의 스냅샷 시점과 세대·시간 제한을 명시한다.
같은 id 재사용·페이지 재생성·네이티브 복구 후 오래된 응답은 거절한다.

복잡한 포트폴리오 상태 전체를 웹/호스트 양쪽에 복제하기 전에 기능의 소유자를 정한다.
가능하면 기존 웹이 모델/화면을 소유하고 호스트는 좁은 네이티브 기능만 맡는 구성을 먼저 검토한다.

## 경계 사례와 확인 범위

JS alias/shallow copy는 실행했다. 메시지 스냅샷·호스트 모델 복제·요청 id 재사용 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
