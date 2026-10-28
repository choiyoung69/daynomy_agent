---
title: android-kotlin — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E50", "E51", "P02", "DX01", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## val과 읽기 전용 뷰는 스냅샷을 보장하지 않는다

val은 변수의 재대입을 막는다. List 인터페이스와 data class copy도 깊은 불변성을 자동 보장하지 않는다(E50/E51).
UI 이전 상태와 새 상태가 같은 MutableList를 공유하면 나중 변경이 이전 스냅샷까지 바꿀 수 있다.

## 실패하는 변환

```kotlin
val source = Basket(mutableListOf("A"))
val snapshot = source.copy()
source.symbols.add("B")
// snapshot.symbols에도 B가 보인다.
```

## 적용 코드

```kotlin
data class Basket(val symbols: MutableList<String>)
fun detachedBasket(source: Basket) = source.copy(symbols = source.symbols.toMutableList())
```

String 요소 목록은 toMutableList 복사로 요소 자체의 변경 공유를 걱정하지 않아도 된다.
그러나 요소가 또 변경 가능한 객체이면 요소의 복사도 필요하다. 무조건 serialization 왕복으로 깊은 복사를 수행하지 말고
모델이 보유하는 참조·컬렉션별로 소유자를 정한다.

```kotlin
val source = mutableListOf(1)
val view: List<Int> = source
source.add(2)
check(view.size == 2) // List 타입이어도 원래 컬렉션과 별개가 아니다.
```

목록의 UI key는 이름이나 위치 대신 안정된 assetId/historyId를 사용하도록 제안한다.
Map/Set을 사용하면 순서·중복 처리·첫 값/마지막 값 우선 정책도 서버 계약과 비교한다.

## 경계 사례와 확인 범위

실행: shallow copy, 리스트를 분리한 복사, read-only alias. Compose의 recomposition 및 객체 equals 영향은 앱 상태 모델에서 추가 검사한다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
