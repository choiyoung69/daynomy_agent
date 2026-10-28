---
title: flutter-dart — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E03", "E25", "E41", "F01", "DX02", "DX09"]
---

# 타입·null·JSON 디코딩

## dynamic 결과에서 모델 경계를 먼저 검사한다

jsonDecode의 반환값은 dynamic이다(E41). DTO cast만 하면 누락·잘못된 타입·중첩 배열 오류가
뒤늦은 런타임 예외가 된다. Map 조회는 누락과 null 둘 다 null을 반환하므로 존재 의미를 별도로 검사한다(E25).

## 실패하는 변환

```dart
final id = (json['assetId'] as num).toInt();
// 1.5가 1로 잘리며 따옴표/누락/범위 검사를 우회할 수 있다.
```

## 적용 코드

```dart
int checkedId(Object? value) {
  if (value is! int || value <= 0 || value > 9007199254740991) {
    throw const FormatException('ID_RANGE_OR_TYPE');
  }
  return value;
}
String presence(Map<String, Object?> object, String key) {
  if (!object.containsKey(key)) return 'missing';
  return object[key] == null ? 'null' : 'value';
}
```

Map<String,dynamic>인지 확인하기 전에 root를 cast하지 않는다. 배열의 모든 요소·enum·필수 키도 검증한다.
서버의 추가 필드를 허용하는 것과 필수 필드가 없어도 허용하는 것은 별개다.

| 입력 | 현재 공통 계약 |
| --- | --- |
| ID 1 / 최대 안전 정수 | 허용 |
| ID 1.5 / "1" / null | 거절 |
| 큰 네이티브 int | 디코딩 가능해도 공통 안전 정수 밖이면 거절 |
| 필드 없음과 null | 부분 수정 모델에서 구분 |

## 경계 사례와 확인 범위

실행: 누락/null 존재·안전 ID·소수 절삭 위험·네이티브 큰 정수 보존. 전체 API의 생성 DTO와 실제 Flutter HTTP 디코딩은 별도다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
