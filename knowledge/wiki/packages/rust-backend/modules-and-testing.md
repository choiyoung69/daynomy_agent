---
title: rust-backend — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["P02", "E38", "E39", "E58", "DX05", "DX09"]
---

# 모듈·의존성·검증 방법

## 라이브러리·기능·검사 범위를 작은 단위로 고정한다

예제 crate는 Rust1.92.0·serde_json1.0.154(arbitrary_precision)·Tokio1.54.0을 사용한다.
이들은 예제 직접 의존성이며 전체 app/의 의존성 승인이나 버전 변경을 뜻하지 않는다.

## 실패하는 구성

```text
cargo test 통과 → 실제 HTTP/DB·원본 호환·수동 항목까지 통과로 보고
```

## 적용 검증 층

```text
Value/input helpers → pure fixture tests
request binding/status → real HTTP tests
transaction/ownership/concurrency → dedicated local DB tests
source parity → fixed original comparison and reviewed source hashes
```

crate 루트의 forbid(unsafe_code)는 직접 코드에 대한 규칙이며 의존성 내부까지 unsafe가 없다는 뜻은 아니다.
원본을 수정하지 않고 실패를 없애기 위해 명세/테스트를 약화하지 않는다.

```sh
CARGO_HOME="$PWD/.local/cargo" cargo run --offline --manifest-path knowledge/examples/rust/Cargo.toml
python3 scripts/knowledge_topic_examples.py --output /tmp/new-rust-topic-run.json
```

실제 app/의 검사는 기존 서비스 실행 안내와 인수 기준을 사용한다. 예제의 가짜 transaction을 DB 대체 구현으로 합치지 않는다.

## 경계 사례와 확인 범위

현재 JSON·고정 스케일·컬렉션·Tokio 취소·가짜 트랜잭션 제어 흐름 15개 사례를 실행했다. 실제 백엔드 통합 재검증은 아니다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
