---
title: rust-backend — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["Q08", "P02", "P03", "F01", "E39", "DX05", "DX09"]
---

# 타입·null·JSON 디코딩

## serde_json Value도 업무 스키마 검증이 필요하다

Value의 null·누락·숫자 타입과 업무 제약을 구분한다. 인덱스 접근은 누락을 Null처럼 보이게 할 수 있으므로
존재 구분에는 get을 사용한다. typed DTO를 쓰더라도 Option의 누락/null 의미와 default 정책을 검토한다.

## 실패하는 변환

```rust
let id = value["assetId"].as_f64().unwrap() as u64;
// 소수 절삭·범위·정밀도 손실·panic을 허용한다.
```

## 실행한 경계 검사

```rust
fn checked_id(value: &Value) -> Result<u64, &'static str> {
    let id = value.as_u64().ok_or("ID_TYPE")?;
    if !(1..=9_007_199_254_740_991).contains(&id) { return Err("ID_RANGE"); }
    Ok(id)
}
```

arbitrary_precision 기능으로 숫자를 보존해도 as_f64에서 정밀도를 잃을 수 있다(Q08).
서버의 더 큰 정수 저장 능력과 기존 웹의 안전 정수 계약을 구분한다.

| 입력 | 기대 |
| --- | --- |
| null과 키 없음 | get 결과의 Some(Null)/None 구분 |
| 숫자 1 | 허용 |
| 문자열 "1" | 거절 |
| 공통 안전 정수 한도 밖 | 거절 |

피드백의 문자열 전용 content·중복 키 거절 정책을 다른 API 전체에 자동 확대하지 않는다(P02/P03).

## 경계 사례와 확인 범위

실행: 누락/null·안전 ID·큰 ID/문자열 ID 거절. 모든 DTO/중복 키/HTTP validation 실행은 이 예제에 포함되지 않는다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
