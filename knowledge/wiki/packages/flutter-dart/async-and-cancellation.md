---
title: flutter-dart — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E59", "E32", "E15", "DX02", "DX09"]
---

# 비동기·취소·요청 경쟁

## Future.timeout과 HTTP abort는 다른 작업이다

timeout은 시간 안에 끝나지 않은 원래 Future를 자동 중단하지 않는다(E59).
HttpClientRequest.abort도 done이 이미 완료되면 효과가 없으므로 늦은 결과를 반영할지 별도로 검사한다(E32).

## 실패하는 변환

```dart
await request.timeout(const Duration(seconds: 3));
// timeout 이후 원래 요청이 완료되지 않는다고 가정
```

## 실제 실행한 시간 제한 예

```dart
final completion = Completer<void>();
  var completedOriginal = false;
  final originalWork = completion.future.then((_) { completedOriginal = true; });
  var timedOut = false;
  try { await originalWork.timeout(Duration.zero); } on TimeoutException { timedOut = true; }
  completion.complete();
  await originalWork;
  test('timeout_does_not_cancel_original', timedOut && completedOriginal);
```

실제 네이티브 HTTP 어댑터는 보유한 HttpClientRequest에 abort를 연결하고, 요청 소유자 dispose 시 타이머와
구독도 정리한다. `.then`, `catch`, `finally`의 모든 상태 반영에서 요청 세대를 확인한다.
웹 컴파일을 추가하면 dart:io 대신 해당 네트워크 어댑터가 필요하다.

## 경계 사례와 확인 범위

실행: timeout 이후 원래 Future의 완료. 실제 HttpClient 연결·SSL·서버 처리 중단·Flutter 수명 연동은 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
