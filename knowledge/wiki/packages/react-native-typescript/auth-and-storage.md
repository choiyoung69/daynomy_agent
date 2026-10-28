---
title: react-native-typescript — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E14", "F03", "W03", "W04", "E48", "E49", "E47", "DX04", "DX09"]
---

# 인증·저장소·호스트 경계

## 웹 환경 의존성을 목록화하고 어댑터로 바꾼다

RN은 브라우저 DOM/localStorage 환경과 같지 않다. 쿠키 인증 문서의 제약도 확인해야 한다(E14).
원래 웹은 쿠키 포함·CSRF 준비·shared refreshPromise를 사용한다(F03).

## 실패하는 변환

```typescript
localStorage.setItem('token', token);
const url = import.meta.env.VITE_API_BASE_URL;
// 브라우저 저장소와 Vite 환경을 네이티브 런타임에서 그대로 사용
```

## 적용 인터페이스

```typescript
interface GuestDraftStore {
  load(): Promise<GuestDraft | undefined>;
  save(draft: GuestDraft): Promise<void>;
  clear(): Promise<void>;
}
interface ApiEnvironment { baseUrl: string; sessionGeneration: number; }
```

저장 플러그인을 고르기 전에 게스트 세션과 회원 영구 분석의 수명·손상 복구·계정 격리를 정한다(W03/W04).
보안 저장소의 OS 구현과 일반 설정 저장소를 구분한다(E48/E49).
외부 user-agent OAuth callback·서버 쿠키 연결·동시 401·logout 후 늦은 응답을 양쪽 OS에서 검사한다(E47).
플러그인 자동 연결, 권한, iOS/Android 프로젝트 설정은 TypeScript API만 보고 완료로 판단하지 않는다.

## 경계 사례와 확인 범위

저장소 인터페이스·환경 주입은 설계 예다. 선택 플러그인의 실제 보안 저장·쿠키·로그인 복귀는 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
