---
title: webview — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E04", "E37", "E57", "F01", "F03", "DX04", "DX09"]
---

# 타입·null·JSON 디코딩

## 웹 JSON과 호스트 메시지의 경계를 각각 검증한다

기존 API 응답은 TypeScript guard로 검증하고(F01/F03), 호스트 브리지는 별도 버전/메서드/payload 스키마를 갖는다.
브리지 메시지가 앱 내부에서 왔다고 가정하지 않는다. 출처 검사는 JSON 안의 origin 문자열로 대체할 수 없다(E57/E37).

## 실패하는 변환

```typescript
const message = JSON.parse(raw) as any;
native[message.method](message.payload); // 임의 메서드 호출 경계가 된다.
```

## 실행한 최소 프로토콜

```typescript
type Envelope = { v: 1; id: string; method: 'close'; payload: Record<string, never> };
function decodeBridge(value: unknown): Envelope {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('MESSAGE_TYPE');
  const input = value as Record<string, unknown>;
  if (input.v !== 1 || typeof input.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(input.id) || input.method !== 'close') {
    throw new Error('MESSAGE_SCHEMA');
  }
  if (!input.payload || typeof input.payload !== 'object' || Array.isArray(input.payload) || Object.keys(input.payload).length !== 0) {
    throw new Error('PAYLOAD_SCHEMA');
  }
  return { v: 1, id: input.id, method: 'close', payload: {} };
}
```

이 예제는 close 한 가지 동작만 허용하며 payload도 빈 객체만 허용한다. 실제 서비스에 메서드를 추가할 때는
기능별 권한/출처/필드 스키마/응답/오류를 각각 정의한다. 이 프로토콜이 기존 DAYNOMY 구현이라는 뜻은 아니다.

| 메시지 | 결과 |
| --- | --- |
| v1·유효 id·close·빈 payload | 허용 |
| v2 또는 eval 등 알 수 없는 method | 거절 |
| 잘못된 id·배열/root null | 거절 |
| close에 임의 code payload | 거절 |

네이티브도 같은 의미를 독립 검증해야 하며 웹 guard만 신뢰하지 않는다.

## 경계 사례와 확인 범위

실행: TS 메시지 decode의 정상 close·unknown method·version·payload 거절. Android/WK 네이티브 메시지 수신 통합과 왕복은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
