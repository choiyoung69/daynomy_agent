---
title: android-kotlin — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "E45", "R02", "W05", "DX01", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 전송 실패와 확정 실패를 구분한다

HTTP status, 업무 code, JSON 형식 오류, 취소, 응답 유실의 의미는 서로 다르다.
거래 요청 뒤 연결이 끊겼다고 서버 미적용을 확신할 수 없다(E19/R02). 클라이언트 try/catch는 DB 트랜잭션이 아니다.

## 실패하는 변환

```kotlin
catch (error: Exception) {
    api.createTransaction(request) // 중복 매수/매도 가능
}
```

## 적용 코드

```kotlin
sealed interface SubmitState {
    data object Sending : SubmitState
    data class Confirmed(val transactionId: Long) : SubmitState
    data class Rejected(val code: String) : SubmitState
    data object OutcomeUnknown : SubmitState
}
```

정상 응답도 transactionId/holding/실현손익의 형식을 확인해야 한다(W05).
확정 실패는 계약된 status/code로, 전송 후 결과를 못 확인하면 OutcomeUnknown으로 분류하도록 제안한다.
재조회·중복 방지 계약이 확정되기 전 자동 재전송하지 않는다.

```kotlin
response.use { body ->
    val payload = decodeAndValidate(body)
    applyOnlyIfCurrent(payload)
} // 자원 해제와 서버 롤백은 다른 동작이다.
```

예시는 앱의 응답 어댑터 계약이다. 실제 Response/DB를 사용해 실행하지 않았다.
회원 잠금·포트폴리오 잠금·원장/스냅샷 원자성은 Rust 서버 책임을 따른다.

## 경계 사례와 확인 범위

거절 code·잘못된 성공 JSON·전송 전 실패·응답 유실·동시 클릭·커밋 후 화면 종료를 따로 재현한다. 이 문서의 거래 UI/HTTP 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
