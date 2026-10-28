---
title: flutter-dart — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "W05", "R02", "E15", "DX02", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 오류와 서버 변경의 확정 상태를 분리한다

FormatException, HTTP status, 업무 code, TimeoutException, 취소, 변경 결과 미확정을 같은 UI 메시지로 축약하지 않는다.
원본 transaction 응답은 holding이 null일 수도 있고 결과 형식 검사가 따로 있다(W05).

## 실패하는 변환

```dart
try { await createTrade(input); }
catch (_) { await createTrade(input); } // 중복 거래 가능
```

## 적용 모델 예

```dart
sealed class SubmitState {}
class Sending extends SubmitState {}
class Confirmed extends SubmitState { Confirmed(this.id); final int id; }
class Rejected extends SubmitState { Rejected(this.code); final String code; }
class OutcomeUnknown extends SubmitState {}
```

확인된 실패와 응답 유실을 나누고, 비멱등 요청의 재전송은 중복 방지/미적용 확인 계약을 따른다(E19).
try/finally의 자원 해제는 서버 DB 롤백이 아니다. 서버 원장·보유량·스냅샷 원자성은 백엔드 검증을 따른다(R02).

```dart
try { return await transport.execute(); }
finally { transport.releaseOwnedResources(); }
```

위 모델/transport는 실제 앱에서 정의할 인터페이스 예다. 입력 본문·쿠키·토큰을 예외 로그에 넣지 않는다.

## 경계 사례와 확인 범위

잘못된 성공 응답·timeout·응답 유실·취소·동시 클릭·서버 롤백은 통합 fixture로 확인해야 한다. 이 문서의 거래 모델은 아직 통합 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
