---
title: android-kotlin — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["W03", "W04", "F03", "E47", "E48", "DX01", "DX09"]
---

# 인증·저장소·호스트 경계

## 브라우저 저장소를 Android 저장소 이름으로 치환하지 않는다

게스트 원장은 원본에서 sessionStorage, 분석은 회원 localStorage/게스트 sessionStorage를 사용한다(W03/W04).
Android 영구 저장으로 옮기면 재시작·계정 전환 수명이 달라진다.

## 실패하는 변환

```kotlin
preferences.edit().putString("auth", rawCookie).apply()
// 일반 설정 저장소를 인증 비밀 저장/쿠키 회전 정책의 대체로 사용한다.
```

## 적용 계약 예

```kotlin
interface GuestDraftStore {
    suspend fun loadSessionDraft(): Draft?
    suspend fun saveSessionDraft(value: Draft)
    suspend fun clearSessionDraft()
}
interface SessionTransport {
    suspend fun ensureCsrf(): CsrfHeader
    suspend fun refreshOnce(): RefreshOutcome
}
```

이 인터페이스는 책임 분리 예제다. 저장 라이브러리나 암호화 구현을 제공한 것은 아니다.
Keystore는 키 관리 도구이고(E48), 포트폴리오 자료형 검증/손상 복구는 별도다.
Google 로그인을 네이티브로 연결할 때 외부 user-agent와 callback/state/PKCE·서버 세션 연결을 확인한다(E47).
쿠키 포함·CSRF header·동시 401 갱신 공유·로그아웃 중 늦은 응답 처리는 현재 서버 계약에 맞춘다.

| 자료 | 수명/삭제 조건 |
| --- | --- |
| 입력 초안 | 화면/게스트 세션 정책 |
| 회원 조회 캐시 | 계정 ID로 격리·로그아웃/탈퇴 정리 |
| 인증 비밀 | 플랫폼 보안 저장·만료/회전/삭제 정책 |

## 경계 사례와 확인 범위

손상 JSON·구버전·계정 전환·로그아웃·동시 401·refresh 실패·로그인 복귀를 기기와 실험 서버에서 검증해야 한다. 현재 저장소/인증 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
