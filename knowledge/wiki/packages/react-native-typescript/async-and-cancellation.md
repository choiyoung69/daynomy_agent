---
title: react-native-typescript — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E30", "E14", "F04", "DX04", "DX09"]
---

# 비동기·취소·요청 경쟁

## Promise는 취소 프로토콜이 아니다

AbortSignal과 Fetch를 연결하고 타이머·이전 요청·늦은 반영을 정리한다.
Promise.race 또는 시간 제한 표시가 원래 작업을 중단하지는 않는다. 아래는 어댑터 wiring과 race의 실행 예다.

## 실패하는 변환

```typescript
await Promise.race([fetch(url), timeout()]);
// timeout 승리만으로 fetch가 중단됐다고 판단
```

## 적용 코드

```typescript
const controller = new AbortController(); let adapterCancelled = false;
controller.signal.addEventListener('abort', () => { adapterCancelled = true; }, { once: true });
controller.abort();
test('abort_adapter_wiring', controller.signal.aborted && adapterCancelled);
let complete!: () => void; let originalCompleted = false;
const original = new Promise<void>(resolve => { complete = resolve; }).then(() => { originalCompleted = true; });
await Promise.race([original, Promise.resolve('timeout')]);
complete(); await original;
test('race_does_not_cancel_original', originalCompleted);
```

실제 어댑터는 fetch(url, {signal})처럼 취소 신호를 HTTP에 전달해야 한다.
예제는 signal의 취소 이벤트를 가짜 어댑터에 연결했으며 실제 RN HTTP 취소까지 검증하지 않았다.
React effect cleanup은 요청을 취소하거나 결과를 무시하는 처리를 짝짓는다(E30).
finally에서도 이전 요청이 loading을 지우지 못하게 세대를 확인한다.

## 경계 사례와 확인 범위

실행: AbortSignal wiring, race 후 원래 Promise 계속 완료. RN의 실제 요청·쿠키·redirect·abort 예외 모양은 버전별 통합 검사 대상이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
