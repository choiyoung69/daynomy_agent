---
title: flutter-dart — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["W03", "W04", "E48", "E49", "E47", "F03", "DX02", "DX09"]
---

# 인증·저장소·호스트 경계

## 저장 플러그인의 API보다 수명과 OS 구현을 먼저 확인한다

원본 게스트 원장/체험 상태는 sessionStorage, 회원 분석은 localStorage를 사용할 수 있다(W03/W04).
Flutter의 영구 설정 플러그인에 모두 저장하면 기존 세션 수명이 바뀐다.

## 실패하는 변환

```dart
await preferences.setString('refreshToken', token);
// 일반 설정과 OS 비밀 저장소의 책임을 혼합
```

## 적용 인터페이스 예

```dart
abstract interface class GuestDraftStore {
  Future<GuestDraft?> loadSessionDraft();
  Future<void> saveSessionDraft(GuestDraft draft);
  Future<void> clearSessionDraft();
}
```

GuestDraft는 버전과 타입 검증을 갖는 모델이다. 계정/게스트 전환·구버전·손상·저장 실패를 명시한다.
Android Keystore와 iOS Keychain의 역할은 다르므로(E48/E49) Flutter 플러그인의 양쪽 실제 구현을 검사한다.
쿠키·CSRF·동시 401·refresh 회전·외부 브라우저 OAuth callback도 양쪽에서 확인한다(E47).
기존 쿠키 서버를 플러그인 편의 때문에 새 토큰 계약으로 바꾸지 않는다.

## 경계 사례와 확인 범위

저장/인증 플러그인은 아직 선택·실행하지 않았다. 인터페이스는 수명과 권한을 분리하는 설계 예이며 보안 구현 완료가 아니다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
