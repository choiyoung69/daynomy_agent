---
title: rust-backend — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "J01", "R02", "F03", "E47", "DX05", "DX09"]
---

# 인증·저장소·호스트 경계

## principal을 신뢰하는 위치와 DB 소유권 검사를 구분한다

회원 ID를 요청 본문에서 받아 본인으로 취급하지 않는다. 인증 principal과 회원 상태/소유권/ADMIN·CSRF 계약을
서버 경계에서 확인한다(J01/P02). 로그인 전용 API·공개 POST·관리자 변경의 순서가 다를 수 있다.

## 실패하는 변환

```text
member_id = request.body.memberId
거래 조회/변경 = 이 member_id를 그대로 사용
```

## 적용 경계

```text
security input → verified principal → field validation → ownership/transaction → response
refresh input → signature/expiry/hash/member-state → rotation → cookie response
```

탈퇴 후 오래된 access 토큰과 동시 거래의 회원 상태 재확인을 현재 잠금 경로와 비교한다(R02).
refresh는 원문 비밀 대신 해시 저장/회전/재사용 거절을 기존 계약으로 확인한다(P02).
네이티브 OAuth·쿠키 전달을 추가할 때 기존 서버 흐름을 우회하는 개발용 고정 principal로 대체하지 않는다.
실험에는 로컬 테스트 DB·외부 fixture만 쓰고 운영 .env/실제 사용자 자료를 지식 원문으로 수집하지 않는다.

## 경계 사례와 확인 범위

현재 백엔드의 과거 인수 결과와 새 앱 인증 연결을 구분한다. 이 문서는 새 인증/DB 실행을 수행한 근거가 아니다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
