---
title: webview — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "E04", "E37", "E30", "DX04", "DX09"]
---

# 비동기·취소·요청 경쟁

## 페이지 이탈 후 브리지 응답과 네트워크 응답을 모두 다룬다

웹의 AbortController는 호스트 작업을 자동 취소하지 않는다. 호스트의 cancel도 이미 서버에 적용된 거래를
롤백하지 않는다(E19). 각 작업의 취소·응답 무시·결과 확인 프로토콜을 별도로 정한다.

## 실패하는 변환

```typescript
window.addEventListener('pagehide', () => controller.abort());
// 호스트가 진행하는 작업과 서버 거래도 취소됐다고 간주
```

## 적용 흐름 예

```text
요청: pageGeneration + requestId + method + validatedPayload
취소: cancel(requestId) 지원 여부를 method별로 선언
응답: 현재 pageGeneration이며 살아 있는 requestId만 반영
변경 결과 미확정: 조회/중복 방지 계약으로 확인
```

현재 실행한 TS Gate는 오래된 결과/폐기 후 반영을 막는 순수 모델이다.
브리지 cancel을 구현한다면 호스트가 어떤 작업을 실제 중단했는지 응답 의미를 정의하고 권한도 검사한다.
웹 타이머·message listener·pending map·호스트 delegate/handler 수명과 정리를 함께 검토한다.

Promise.race는 원래 작업을 취소하지 않는 관찰을 브리지 timeout에도 적용한다.

## 경계 사례와 확인 범위

실행: JS race 후 작업 완료·순수 Gate·취소 신호 wiring. 실제 host cancel과 페이지/프로세스 이탈 테스트는 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
