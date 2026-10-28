---
title: ios-swift — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E49", "E47", "F03", "W03", "W04", "E43", "E11", "DX03", "DX09"]
---

# 인증·저장소·호스트 경계

## 저장소 수명·쿠키·로그인을 별도 어댑터로 둔다

원본 sessionStorage와 localStorage의 수명을 그대로 Keychain에 대응시키지 않는다(W03/W04).
Keychain은 작은 비밀 저장 도구이며 게스트 포트폴리오의 버전·손상·수명 정책은 별도다(E49).

## 실패하는 변환

```swift
UserDefaults.standard.set(refreshToken, forKey: "refresh")
// 일반 설정 저장과 인증 회전/삭제/접근 정책을 동일하게 취급
```

## 적용 계약 예

```swift
protocol GuestDraftStore {
    func loadSessionDraft() throws -> GuestDraft?
    func saveSessionDraft(_ draft: GuestDraft) throws
    func clearSessionDraft() throws
}
```

GuestDraft는 버전 있는 검증 모델이다. 로그인 계정이 바뀌면 회원 캐시 키·미완료 요청·화면 초안을 정리한다.
URLSession의 cookie storage와 WKWebView의 website data store를 같은 세션이라고 가정하지 않는다.
외부 브라우저 OAuth의 callback/state/PKCE와 서버 쿠키 세션 연결을 명세해야 한다(E47).
원래 서버가 쿠키 기반이면 임의 bearer 방식으로 바꾸지 않는다. CSRF 준비·동시 401 공유·회전 refresh 재사용 거절을 확인한다.

## 경계 사례와 확인 범위

Keychain 접근·URLSession/WKWebView 쿠키·실제 로그인 복귀·계정 전환 캐시는 아직 실행하지 않았다. 인터페이스를 구현하기 전에 수명과 삭제 조건을 고정한다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
