---
title: flutter-dart — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E03", "P02", "W02", "DX02", "DX09"]
---

# 숫자·금액·반올림

## double로 읽은 소수의 정밀도는 되돌릴 수 없다

Dart 네이티브와 웹의 숫자 표현은 다르다(E03). 금융 입력을 double로 바꾼 후 문자열로 되돌리는 경로는
원래 값의 복구가 아니다. BigInt 고정 스케일은 특정 입력 규칙의 한 선택이며 전체 금액 API를 자동 대체하지 않는다.

## 실패하는 변환

```dart
final total = 0.1 + 0.2;
final exact = BigInt.from(total * 100); // 앞선 이진 소수 변환/절삭을 숨김
```

## 실행 가능한 입력 변환

```dart
BigInt minorUnits(String input, int scale) {
  if (scale < 0 || scale > 6 || !RegExp(r'^\d+(\.\d+)?$').hasMatch(input)) {
    throw const FormatException('DECIMAL_SYNTAX');
  }
  final parts = input.split('.');
  final fraction = parts.length == 2 ? parts[1] : '';
  if (fraction.length > scale) throw const FormatException('DECIMAL_SCALE');
  return BigInt.parse(parts[0]) * BigInt.from(10).pow(scale) +
      BigInt.parse(fraction.padRight(scale, '0').isEmpty ? '0' : fraction.padRight(scale, '0'));
}
```

이 함수는 부호 없는 고정 소수 입력의 예다. 초과 소수를 반올림하지 않고 거절한다.
화면의 2자리 금액과 서버 거래 단가4/비용2/환율6 규칙을 각각 적용해야 한다(P02/W02).
BigInt를 JSON 숫자로 바꾸거나 문자열로 보내는 정책은 별도 API 직렬화 계약이다.
jsonDecode가 이미 double을 만든 응답에 이 함수를 적용해 정밀도가 복구됐다고 하지 않는다.

| 입력 | scale | 기대 |
| --- | --- | --- |
| 1.20 | 2 | 120 |
| 9007199254740993.01 | 2 | 900719925474099301 |
| 1.005 | 2 | 자릿수 오류 |
| -1 / 1. / 통화 기호 | 2 | 현재 예제 문법 거절 |

## 경계 사례와 확인 범위

문자열→BigInt 스케일 예제와 초과 자릿수 거절을 실행했다. 임의 decimal 계산/반올림 라이브러리와 서버 왕복 검증은 아니다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
