---
title: 인증·세션
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "W14", "JC05"]
---

# 인증·세션

F01의 기존 명세를 작업용으로 정리한 문서다. 계약의 상세 근거는 [서비스 명세](../../../../spec/service.md)이며,
이 문서는 모든 분기의 현재 런타임 호환성을 인증하지 않는다. 최신 사용자 결정은 명세의 결정 기록을 우선한다.

## 기능 계약



## 원본 API 연결

| 메서드 | 경로·별칭 | 명세 권한 |
| --- | --- | --- |
| GET | `/api/auth/google` | 공개 |
| GET | `/api/auth/csrf` | 공개 |
| POST | `/api/auth/refresh` | 공개 |
| POST | `/api/auth/logout` | 공개 |

전체 경로는 [API 목록](../../../contracts/api-index.json), 원본 프론트 출처는 W14를 따른다.

## 이식과 검사

로그인 복귀·동시 401·refresh 실패·로그아웃 중 늦은 응답을 확인한다.
공통 입력·오류·인증·UI 상태에 대상 언어/플랫폼의 디코더·수명·저장소를 대응한다.
실제 플랫폼 버전·명령·입력·기대값·관찰값·소스 해시를 남긴다. 서버의 과거 검사 결과를 앱 실행 결과로 재사용하지 않는다.

[패키지 조합](../../shared/package-map.md), [인증·저장](../../shared/auth-storage.md),
[검증](../../shared/testing-migration.md), [미확인 질문](../../../questions.md).
