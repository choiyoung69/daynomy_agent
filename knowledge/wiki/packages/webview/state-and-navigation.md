---
title: webview — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E04", "E11", "W01", "F04", "DX04", "DX09"]
---

# UI 상태·탐색·수명

## 웹 탐색과 네이티브 back은 하나의 스택이 아니다

Android WebView와 WKWebView는 별도 호스트 API이며 탐색 delegate·외부 링크·프로세스 수명을 각각 처리한다(E04/E11).
웹 라우터의 내부 이동, 웹 history back, 네이티브 화면 닫기의 우선순위를 정한다.

## 실패하는 변환

```typescript
// Android back이 오면 무조건 window.history.back()
// 또는 모든 탐색을 외부 브라우저로 열어 로그인 복귀/웹 상태를 잃음
```

## 적용 결정표

```text
신뢰한 내부 URL → 웹 라우터/웹 history
승인된 외부 URL → 외부 user-agent, 브리지 권한 없음
닫기 요청 → 호스트 정책으로 처리, 미확정 거래 확인과 분리
페이지 재생성 → generation 변경, 과거 pending 응답 무시
```

입력 중 키보드 back·모달 닫기·웹 내부 back·호스트 닫기를 구분한다.
화면 회전·백그라운드·웹 콘텐츠 프로세스 종료 후 복원할 초안과 회원 재조회 조건도 정한다.
safe area·키보드·파일 선택·임베드·스크린 리더는 웹과 네이티브 양쪽에서 검사한다.

## 경계 사례와 확인 범위

결정표는 이식 제안이다. 실제 두 호스트의 back/탐색 delegate·프로세스 복구·UI 접근성 검사는 아직 없다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
