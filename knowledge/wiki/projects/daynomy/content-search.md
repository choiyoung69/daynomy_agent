---
title: 뉴스·통합 검색
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "W09", "JC30", "JC31"]
---

# 뉴스·통합 검색

F09의 기존 명세를 작업용으로 정리한 문서다. 계약의 상세 근거는 [서비스 명세](../../../../spec/service.md)이며,
이 문서는 모든 분기의 현재 런타임 호환성을 인증하지 않는다. 최신 사용자 결정은 명세의 결정 기록을 우선한다.

## 기능 계약

- 원본 JC31 `NewsSearchController`/`NewsSearchResponse`와 서비스 F09 기준: 공개 GET `/api/search/news`.
- q는 원문 UTF-16 길이 100 이하이며 Unicode 문자/숫자를 포함한다. 원본 Java Pattern과 같이 줄바꿈은 거절한다. 공백·중복 단어·대소문자 정규화와 AND/일반문자 %, _, ! 검색은 서버 책임이다.
- category 생략은 전체, page≥1, size=1~100, sort=LATEST/RELEVANCE. 응답은 `content`, `page`, `size`, `totalElements`, `totalPages`이며 목록 API의 `items`/`hasNext`와 다르다.
- Android Issue #11은 뉴스 검색만 연결한다. 통합 콘텐츠 검색은 준비 범위에 포함하지 않는다. 정적 준비와 런타임 검증은 별개다.


## 원본 API 연결

| 메서드 | 경로·별칭 | 명세 권한 |
| --- | --- | --- |
| GET | `/api/search/contents` | 공개 |
| GET | `/api/search/news` | 공개 |

전체 경로는 [API 목록](../../../contracts/api-index.json), 원본 프론트 출처는 W09를 따른다.

## 이식과 검사

검색 단어·정렬·페이지·필터·중복 URL·최신 검색 반영을 확인한다.
공통 입력·오류·인증·UI 상태에 대상 언어/플랫폼의 디코더·수명·저장소를 대응한다.
실제 플랫폼 버전·명령·입력·기대값·관찰값·소스 해시를 남긴다. 서버의 과거 검사 결과를 앱 실행 결과로 재사용하지 않는다.

[패키지 조합](../../shared/package-map.md), [인증·저장](../../shared/auth-storage.md),
[검증](../../shared/testing-migration.md), [미확인 질문](../../../questions.md).
