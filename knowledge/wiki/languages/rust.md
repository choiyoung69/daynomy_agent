---
title: Rust 백엔드 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E38", "E39", "E27", "E28", "R01", "R02", "Q08", "P02"]
---

# Rust 백엔드 언어 패키지

현재 app/의 서버를 이해하고 다섯 클라이언트의 API 계약을 유지하기 위한 패키지다.
클라이언트 작업마다 서버 내부 구현 전체를 넣지 않고 서버 작업 또는 경계 조사 때 선택한다.

## 데이터와 직렬화

- 소유권·이동·빌림의 수명으로 메모리를 관리하며(E38), 공유 상태의 업무 원자성과는 별개다.
  메모리 안전성만으로 DB 트랜잭션·중복 전송·같은 회원의 동시 거래가 해결되지 않는다.
- serde_json Value는 동적 JSON이다. 필수 키·null·타입·정수 범위·업무 제약을 각각 검사한다.
  `.get()`의 None과 Some(Null)을 구분한다. 기존 probe에서 arbitrary_precision으로 숫자를 보존해도
  as_f64 변환 후 큰 ID가 손실됐다(Q08). 금액 경로를 일괄 f64로 바꾸지 않는다.
- Result는 복구 가능한 오류를 전달하는 언어 도구다(E39). 내부 오류를 어떤 HTTP status/code로
  보낼지는 기능 계약을 따른다. 사용자 입력 때문에 panic/unwrap에 의존하는 구현을 추가하지 않는다.
- 날짜 전용 값, nullable 응답, 추가 필드, 경로 별칭은 기존 API와 대조한다.
  피드백에서 확정한 중복 키 거절을 모든 API에 자동 확대하지 않는다(P02).

## 비동기와 트랜잭션

현재 포트폴리오 거래는 SQL BEGIN/COMMIT/ROLLBACK을 명시적으로 호출한다(R02).
Rust가 자원 수명을 관리한다는 설명을 현재 코드에 없는 자동 롤백 보장으로 바꾸지 않는다.
Task 취소·연결 종료·COMMIT 응답 유실·풀 재사용에서 열린 트랜잭션이 남는지 별도 확인한다.
Read Committed·회원/포트폴리오 잠금·잠금 순서는 [공통 트랜잭션](../shared/transactions-concurrency.md)을 따른다.

## 모듈과 검증

Rust 구현은 app/에 두고 프레임워크 제약·unsafe 금지·직접 의존성 설명을 유지한다.
spec/service.md는 요구사항이며 runs/010은 과거 실행 결과다. 어느 하나만으로 현재 호환성을 승인하지 않는다.
실제 HTTP/실험 DB·원본 비교·소스 해시·수동 항목을 함께 확인한다. 원본 서버나 운영 DB를 임의 실행하지 않는다.
Q08은 작은 JSON 예제의 증거이며 전체 백엔드 검증을 다시 수행한 결과가 아니다.
[기능 목록](../projects/daynomy/service-catalog.md), [공통 오류](../shared/error-retry-cancel.md).

## 상세 패키지

[Rust 백엔드의 주제별 문서](../packages/rust-backend/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.
