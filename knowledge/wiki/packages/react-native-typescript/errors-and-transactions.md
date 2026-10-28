---
title: react-native-typescript — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "F03", "W05", "R02", "DX04", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 성공 status와 안전한 재시도는 다른 판단이다

Fetch 전송 실패, HTTP 오류, 잘못된 JSON, 업무 code, 취소, 거래 결과 미확정을 구별한다(F03/W05).
서버 트랜잭션과 RN의 로컬 상태 변경은 하나의 원자적 작업이 아니다.

## 실패하는 변환

```typescript
try { await createTrade(input); }
catch { await createTrade(input); } // 응답 유실 후 중복 생성 가능
```

## 적용 모델

```typescript
type Submit =
  | { kind: 'sending' }
  | { kind: 'confirmed'; transactionId: number }
  | { kind: 'rejected'; code: string }
  | { kind: 'outcome-unknown' };
```

성공 응답의 transactionId·holding·실현손익도 검사한다. 응답을 못 확인하면 재조회/중복 방지 계약으로 회복하며
비멱등 자동 재전송 조건은 HTTP 원칙과 API 계약을 따른다(E19).

```typescript
try { await send(); }
finally {
  if (token === currentToken) setLoading(false);
}
```

finally는 자원/화면 정리이며 서버 롤백 증거가 아니다. 로그에 입력 본문·쿠키·토큰을 남기지 않는다.

## 경계 사례와 확인 범위

실제 HTTP/DB 없이 오류 모델만 제시했다. 응답 유실·동시 클릭·잘못된 성공 본문·다른 회원 격리는 통합 사례로 검증해야 한다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
