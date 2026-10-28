---
title: 관리자 콘텐츠·피드백
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "W13", "W11", "W12", "JC06", "JC10", "JC17", "JC19", "JC20", "JC21"]
---

# 관리자 콘텐츠·피드백

F12의 기존 명세를 작업용으로 정리한 문서다. 계약의 상세 근거는 [서비스 명세](../../../../spec/service.md)이며,
이 문서는 모든 분기의 현재 런타임 호환성을 인증하지 않는다. 최신 사용자 결정은 명세의 결정 기록을 우선한다.

## 기능 계약



## 원본 API 연결

| 메서드 | 경로·별칭 | 명세 권한 |
| --- | --- | --- |
| POST | `/api/admin/assets/{assetId}/contents` | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents` | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents/youtube-search` | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents/social-search` | 관리자 |
| DELETE | `/api/admin/assets/{assetId}/contents/{contentId}` | 관리자 |
| GET | `/api/admin/feedbacks` | 관리자 |
| GET | `/api/admin/feedbacks/{id}` | 관리자 |
| PATCH | `/api/admin/feedbacks/{id}` | 관리자 |
| DELETE | `/api/admin/feedbacks/{id}` | 관리자 |
| POST | `/api/admin/news` | 관리자 |
| POST | `/api/admin/news/generate/economy/korea` | 관리자 |
| POST | `/api/admin/news/generate/economy/us` | 관리자 |
| GET | `/api/admin/news/image-search` | 관리자 |
| POST | `/api/admin/news/{id}/generate-image` | 관리자 |
| GET | `/api/admin/news` | 관리자 |
| GET | `/api/admin/news/{id}` | 관리자 |
| POST | `/api/admin/news/{id}/publish` | 관리자 |
| POST | `/api/admin/news/{id}/reject` | 관리자 |
| PUT | `/api/admin/news/{id}` | 관리자 |
| DELETE | `/api/admin/news/{id}` | 관리자 |
| GET | `/api/admin/people` | 관리자 |
| POST | `/api/admin/people` | 관리자 |
| PUT | `/api/admin/people/{personId}` | 관리자 |
| GET | `/api/admin/people/{personId}/posts/search` | 관리자 |
| DELETE | `/api/admin/people/{personId}` | 관리자 |
| POST | `/api/admin/people/{personId}/posts` | 관리자 |
| DELETE | `/api/admin/people/{personId}/posts/{postId}` | 관리자 |
| GET | `/api/admin/people/{personId}/post-candidates` | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/collect` | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/{candidateId}/approve` | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/{candidateId}/reject` | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/bulk-approve` | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/bulk-reject` | 관리자 |
| GET | `/api/admin/people/post-candidates` | 관리자 |
| POST | `/api/admin/people/post-candidates/bulk-approve` | 관리자 |
| POST | `/api/admin/people/post-candidates/bulk-reject` | 관리자 |

전체 경로는 [API 목록](../../../contracts/api-index.json), 원본 프론트 출처는 W13, W11, W12를 따른다.

## 이식과 검사

ADMIN·CSRF·multipart·게시 상태 전이·항목별 부분 성공을 확인한다.
공통 입력·오류·인증·UI 상태에 대상 언어/플랫폼의 디코더·수명·저장소를 대응한다.
실제 플랫폼 버전·명령·입력·기대값·관찰값·소스 해시를 남긴다. 서버의 과거 검사 결과를 앱 실행 결과로 재사용하지 않는다.

[패키지 조합](../../shared/package-map.md), [인증·저장](../../shared/auth-storage.md),
[검증](../../shared/testing-migration.md), [미확인 질문](../../../questions.md).
