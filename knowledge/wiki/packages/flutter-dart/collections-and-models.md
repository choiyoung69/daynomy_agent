---
title: flutter-dart — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E53", "P02", "DX02", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## final과 List.of는 깊은 불변성을 보장하지 않는다

final은 변수의 재대입을 제한한다. List/Map의 내부 객체는 여전히 변경될 수 있다(E53).
상태 이전 값과 새 값이 내부 Map을 공유하면 늦은 변경이 양쪽에 보인다.

## 실패하는 변환

```dart
final original = <Map<String,int>>[{'price':1}];
final snapshot = List<Map<String,int>>.of(original);
original[0]['price'] = 2;
// snapshot[0]['price']도 2
```

## 적용 코드

```dart
final detached = original
    .map((entry) => Map<String,int>.of(entry))
    .toList(growable: false);
```

Map 값이 또 참조형이면 필요한 경로를 더 분리해야 한다. growable:false는 요소 수정 자체를 막는 뜻이 아니다.
불변 DTO/상태 모델을 정하고 copyWith가 어떤 내부 참조를 보존하는지 설명한다.
Map/Set 변환 전후의 순서·중복·동률 정렬을 기능 계약과 대조한다. UI key는 안정된 서버 ID를 사용하도록 제안한다.

## 경계 사례와 확인 범위

실행: List.of의 내부 Map 공유와 분리한 Map 복사. Flutter 상태 도구의 equals/rebuild와 리스트 key 동작은 위젯 검사 대상이다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
