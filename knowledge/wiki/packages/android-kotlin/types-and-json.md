---
title: android-kotlin — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E23", "E24", "E31", "E40", "E46", "F01", "DX01", "DX09"]
---

# 타입·null·JSON 디코딩

## 웹에서 달라지는 지점

TypeScript의 optional 필드, Java의 nullable 참조, Kotlin의 `T?`는 JSON 필드 존재 의미까지 같지 않다.
필수 식별자는 Long으로 읽은 다음 기존 웹의 안전 정수 범위를 검사한다. 따옴표 친 숫자를 허용하면 원래 API를 바꾼다(F01).

## 실패하는 변환

```kotlin
@Serializable data class Row(val currency: String?)
// {}도 당연히 currency=null로 읽힐 것이라고 가정하면 기본 Json에서 실패한다.
val row = Json.decodeFromString<Row>("{}")
```

E31에서 explicitNulls 기본값은 true다. 누락 허용 모델에는 기본값을 명시하거나 필드 존재를 별도 표현한다.
explicitNulls=false는 모든 문제의 해결책이 아니라 누락 처리 계약을 바꾸는 설정이다.

## 적용 코드

```kotlin
@Serializable data class RequiredCurrency(val currency: String?)
@Serializable data class DefaultCurrency(val currency: String? = null)
fun checkedId(element: JsonElement): Long {
    val primitive = element as? JsonPrimitive ?: error("ID_TYPE")
    require(!primitive.isString) { "ID_TYPE" }
    val value = primitive.longOrNull ?: error("ID_INTEGER")
    require(value in 1..9_007_199_254_740_991L) { "ID_RANGE" }
    return value
}
```

`RequiredCurrency`는 누락과 명시 null의 계약을 구분하며, `DefaultCurrency`는 누락을 null 기본값으로 받는다.
PATCH의 "유지/삭제/값 설정" 3상태가 필요하면 JsonObject.containsKey와 JsonNull을 별도로 검사한다.
ignoreUnknownKeys=true는 추가 필드만 허용한다. 필수값·enum·숫자 범위 검사를 없애지 않는다(E40).

| 입력 | 선택할 처리 |
| --- | --- |
| currency 누락 | DTO 기본값 또는 필수 오류를 필드 계약으로 결정 |
| currency:null | nullable 계약에서만 허용 |
| assetId:"1" | checkedId에서 거절 |
| 알 수 없는 프로퍼티 | 기존 웹 호환을 원하면 명시적으로 허용하되 필수 검사는 유지 |

## 경계 사례와 확인 범위

실행한 사례: 필수 nullable 누락 거절, 명시 null, 기본값, explicitNulls=false, 추가 필드 기본 거절/허용, ID 한도와 타입.
Android HTTP 응답 본문을 실제 앱 DTO로 읽는 통합 검사는 아직 없다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
