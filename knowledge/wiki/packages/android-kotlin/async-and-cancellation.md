---
title: android-kotlin — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E17", "E45", "E55", "F04", "DX01", "DX09"]
---

# 비동기·취소·요청 경쟁

## Job 취소와 HTTP 취소를 연결한다

취소는 협력적이다. CPU 루프와 일부 blocking 작업은 다음 취소 확인/중단 가능한 지점 전까지 계속될 수 있다(E17/E55).
OkHttp Call.cancel은 HTTP 호출을 중단하는 별도 인터페이스다(E45).

## 실패하는 변환

```kotlin
runCatching { api.search(query) }
    .onFailure { showError(it) } // CancellationException도 일반 실패 UI로 바뀔 수 있다.
```

## 적용 코드

```kotlin
try {
    val value = api.search(query)
    if (gate.accept(token, value)) render(value)
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (failure: IOException) {
    if (token == currentToken) renderTransportFailure()
}
```

위 코드는 어댑터 경계의 적용 예다. api/gate/render는 앱에서 정의할 인터페이스이며 통합 실행하지 않았다.
취소 정리의 실제 실행 예제는 다음과 같다.

```kotlin
suspend fun cancelledWorkCleansUp(): Boolean = coroutineScope {
    val started = CompletableDeferred<Unit>()
    var cleaned = false
    val job = launch {
        try { started.complete(Unit); awaitCancellation() }
        finally { cleaned = true }
    }
    started.await()
    job.cancelAndJoin()
    cleaned
}
```

Callback을 suspend로 감쌀 때 취소 handler에서 Call.cancel을 연결하고, 늦은 callback이 이미 취소된 continuation을
다시 완료하지 않도록 어댑터의 단일 완료 규칙을 정한다. finally의 로딩 갱신도 현재 요청에만 허용한다.

## 경계 사례와 확인 범위

실행: Job 취소 후 finally 정리, runCatching의 CancellationException 포획. OkHttp/Compose 실제 통신 연결은 별도 검사다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
