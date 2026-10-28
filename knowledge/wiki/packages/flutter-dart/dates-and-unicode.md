---
title: flutter-dart — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E60", "W02", "F01", "E25", "DX02", "DX09"]
---

# 날짜·시간대·Unicode

## DateTime.parse 성공은 달력 날짜 유효성의 증거가 아니다

Dart parse는 범위 밖 구성 요소를 다음 달 등으로 정규화할 수 있다(E60).
원본 거래 입력의 달력 유효성 검사를 그대로 옮기려면 원문과 파싱 결과를 비교한다(W02).

## 실패하는 변환

```dart
final valid = DateTime.tryParse(input) != null;
// 2026-02-30도 정규화되어 성공할 수 있다.
```

## 적용 코드

```dart
bool validCalendarDate(String text) {
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return false;
  final date = DateTime.tryParse('${text}T00:00:00Z');
  return date != null && date.toIso8601String().substring(0, 10) == text;
}
```

이 함수는 거래 입력에 대한 엄격한 날짜 검사 예다. 현행 종가 응답 String 검사에 무조건 적용하면 계약을 강화한다(F01).
baseDate를 현지 DateTime으로 바꿨다가 UTC로 표시하지 않는다. 서울 오늘과 시각 데이터의 timeZone도 명시한다.

```dart
assert('😀'.length == 2);       // UTF-16
assert('😀'.runes.length == 1); // Unicode scalar
```

사람이 보는 grapheme 수는 runes 수와도 다를 수 있다. 검색 길이·정규화·trim은 서버와 같은 단위/정책인지 확인한다.

## 경계 사례와 확인 범위

실행: DateTime의 잘못된 날짜 정규화, strict helper의 거절, 윤년 허용, emoji 길이. 시간대 자정/DST와 기기 표시 검증은 별도다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
