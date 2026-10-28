---
title: android-kotlin — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E12", "E36", "F04", "DX01", "DX09"]
---

# UI 상태·탐색·수명

## 요청 상태와 화면 상태의 소유자를 정한다

Compose remember, rememberSaveable, ViewModel은 보존 조건과 수명이 다르다(E12/E36).
검색 텍스트·국가·선택·수동 단가·요청 세대는 명시한 상태 소유자에서 관리한다. 서버 결과와 편집 중 초안도 구분한다.

## 실패하는 변환

```kotlin
launch { state = search("A") }
launch { state = search("B") }
// 늦게 끝난 A가 B를 덮어쓴다. loading/error finally도 같은 경쟁이 있다.
```

## 적용 코드

```kotlin
class Gate {
    private var generation = 0
    private var alive = true
    var result: String? = null; private set
    fun begin(): Int = ++generation
    fun accept(id: Int, value: String): Boolean {
        if (!alive || id != generation) return false
        result = value
        return true
    }
    fun dispose() { alive = false; generation++ }
}
```

Gate는 순수 수명/세대 모델 예제다. Compose 상태 객체나 다중 스레드 동기화 도구는 아니다.
실제 ViewModel에서는 UI 실행 흐름/StateFlow 갱신과 Job을 연결해야 한다.

| 사건 | 상태 처리 |
| --- | --- |
| 새 검색 | 세대 증가·이전 타이머/Job/Call 취소 |
| 종가 도착 | 현재 종목/세대와 수동 편집 여부 확인 |
| 화면 이탈 | 요청 취소와 초안 보존 정책을 각각 수행 |
| back/모달 닫기 | 서버 거래가 롤백됐다고 간주하지 않음 |

화면 회전·프로세스 복구·IME 가림·TalkBack label은 기기에서 확인한다.

## 경계 사례와 확인 범위

실행: B 결과 유지·A 무시·dispose 후 무시. 실제 Compose·탐색·프로세스 복구·접근성은 아직 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
