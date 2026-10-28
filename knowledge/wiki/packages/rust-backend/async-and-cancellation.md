---
title: rust-backend — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E58", "R02", "E27", "E28", "DX05", "DX09"]
---

# 비동기·취소·요청 경쟁

## abort는 비동기 중단과 업무 롤백의 동의어가 아니다

Tokio JoinHandle.abort의 취소와 join 결과를 확인한다(E58). blocking 작업·외부 시스템·이미 커밋한 변경까지
모두 취소된다고 가정하지 않는다. 요청을 처리하는 future가 drop되는 시점의 자원/DB 상태를 조사한다.

## 실패하는 변환

```rust
handle.abort();
// 그래서 DB도 반드시 롤백됐다고 보고 성공/실패를 확정
```

## 실행한 취소 예

```rust
let work = tokio::spawn(async {
    tokio::time::sleep(std::time::Duration::from_secs(600)).await;
});
work.abort();
assert!(work.await.unwrap_err().is_cancelled());
```

이 결과는 sleep future의 취소이며 DB commit·HTTP 클라이언트·spawn_blocking의 보장은 아니다.
락 보유 범위와 await 지점을 명시하고, 외부 환율 준비를 DB 잠금 전 수행하는 현재 거래 구조와 대조한다(R02).
동일 자원 작업의 세대·캐시·재사용 상태도 actor/Mutex와 별도로 업무 규칙으로 관리한다.

## 경계 사례와 확인 범위

실행: async sleep task의 abort/join 취소. DB 연결 단절·COMMIT 유실·blocking 작업 중단은 미실행이다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
