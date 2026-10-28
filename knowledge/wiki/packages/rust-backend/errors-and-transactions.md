---
title: rust-backend — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["R02", "E19", "E27", "E28", "E39", "DX05", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 명시적 SQL 트랜잭션은 모든 오류 경로에서 닫아야 한다

현재 거래 코드는 BEGIN 이후 mutate 결과에 따라 COMMIT/ROLLBACK을 호출한다(R02).
`?`나 Task 취소만으로 이 코드에 존재하지 않는 자동 rollback을 가정하지 않는다.

## 실패하는 변환

```rust
db.batch_execute("BEGIN").await?;
write_ledger(db).await?; // 오류 시 아래 COMMIT과 별도 ROLLBACK을 모두 건너뛸 수 있음
// 이 코드는 설명용 실패 패턴이며 현재 구현을 그대로 옮긴 것이 아님
```

## 실행한 제어 흐름 모델

```rust
fn simulate_transaction(fail: bool) -> Vec<&'static str> {
    let mut events = vec!["BEGIN", "WRITE"];
    let outcome: Result<(), ()> = if fail { Err(()) } else { Ok(()) };
    match outcome { Ok(()) => events.push("COMMIT"), Err(()) => events.push("ROLLBACK") }
    events
}
```

이 함수는 event log를 사용하는 가짜 제어 흐름이다. 실제 SQL의 원자성/격리/실패 정리를 검증한 것이 아니다.
COMMIT 응답 유실은 실제 적용 여부가 불명확할 수 있으며 서버 오류 응답만으로 미적용을 확신하지 않는다(E19).
Read Committed 일반 SELECT·FOR UPDATE·잠금 순서와 모든 변경 경로를 대조한다(E28).
업무 오류·파싱 오류·내부 DB 오류를 status/code에 연결하며 SQL/쿠키/본문을 그대로 로그로 내보내지 않는다.

## 경계 사례와 확인 범위

실행: 가짜 오류 경로 ROLLBACK/성공 경로 COMMIT 이벤트. 실제 HTTP/DB·충돌·데드락·취소·연결 풀 정리는 별도 검사다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
