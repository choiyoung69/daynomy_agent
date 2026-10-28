---
title: rust-backend — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E38", "E62", "R02", "DX05", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## Clone의 의미는 타입마다 다르다

Vec 값 복사와 Arc 복사는 다르다. Arc::clone은 같은 할당을 가리키며(E62), Clone 자체가
모든 내부 객체를 깊이 복제한다는 뜻은 아니다.

## 실패하는 가정

```rust
let snapshot = Arc::clone(&positions);
// 독립 원장 스냅샷으로 간주한 뒤 원본을 변경
```

## 실행한 차이

```rust
let mut original = vec![1];
let copy = original.clone();
original.push(2);
assert_eq!(copy.len(), 1);

let shared = Arc::new(Mutex::new(vec![1]));
let alias = Arc::clone(&shared);
shared.lock().unwrap().push(2);
assert_eq!(alias.lock().unwrap().len(), 2);
```

이 고정 예제의 unwrap은 테스트 조건 단순화다. 사용자 요청/DB 오류 처리에 그대로 복사하지 않는다.
Arc만으로 내부 변경이 안전해지는 것은 아니며 공유 변경은 Mutex 등 해당 모델의 동기화 정책이 필요하다(E62).
요청별 값과 프로세스 공유 캐시·DB 트랜잭션을 분리한다. 메모리 Mutex가 여러 서버 인스턴스의 DB 정합성을 대신하지 않는다.

## 경계 사례와 확인 범위

실행: Vec<i32> 복사의 독립성·Arc<Mutex<Vec>> 공유. 전체 서버의 공유 상태·병렬 DB 정합성 검증은 별도다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
