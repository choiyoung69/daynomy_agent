---
title: flutter-dart — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E16", "F04", "DX02", "DX09"]
---

# UI 상태·탐색·수명

## mounted만 확인하면 같은 화면의 요청 경쟁은 남는다

setState의 callback은 동기여야 하고 dispose 이후 갱신은 오류다(E16).
화면이 살아 있어도 검색 A보다 B가 먼저 끝나는 경쟁은 세대/선택 검사로 막는다.

## 실패하는 변환

```dart
final result = await api.search(query);
if (mounted) setState(() => rows = result);
// 이전 A 응답이 현재 B를 덮어쓸 수 있다.
```

## 실행한 순수 상태 모델

```dart
class Gate {
  int generation = 0;
  bool alive = true;
  String? result;
  int begin() => ++generation;
  bool accept(int token, String value) {
    if (!alive || token != generation) return false;
    result = value;
    return true;
  }
  void dispose() { alive = false; generation++; }
}
```

위젯에서는 State의 mounted와 요청 token을 함께 확인하고 dispose에서 실제 요청/타이머/컨트롤러를 정리한다.
TextEditingController에 보관한 입력 문자열과 검증된 금액 모델의 수명을 구분한다.
Route pop·modal·back gesture·앱 복귀마다 초안 유지와 재조회 정책을 정한다.
키보드 가림·safe area·semantics label·글자 크기·오류 초점은 양쪽 OS에서 검사한다.

## 경계 사례와 확인 범위

실행: Dart Gate의 B 유지/A 무시/dispose 무시. 실제 Flutter State·탐색·키보드·접근성은 미실행이다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
