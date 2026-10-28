---
title: DAYNOMY 전체 서비스 지식 목록
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["P02", "G01", "G05", "W01"]
---

# DAYNOMY 전체 서비스 지식 목록

리그·배포를 제외한 기존 명세 F01–F13과 F14 보류 경계를 포함한다.
기능 명세와 원본 프론트 API, Java HTTP 매핑을 연결했다. UI 기능을 다섯 앱에 구현한 결과는 아니다.

| ID | 기능 | 핸들러/경로 | 상태 |
| --- | --- | --- | --- |
| F01 | [인증·세션](auth-session.md) | 4/4 | 명세·원본 API 정리 |
| F02 | [회원 정보·닉네임·탈퇴](account.md) | 3/3 | 명세·원본 API 정리 |
| F03 | [종목·종가·환율](stocks-exchange.md) | 3/3 | 명세·원본 API 정리 |
| F04 | [포트폴리오 평가 계산](portfolio-calculation.md) | 1/1 | 명세·원본 API 정리 |
| F05 | [보유자산·거래 원장·수익률](portfolio-ledger.md) | 9/17 | 명세·원본 API 정리 |
| F06 | [AI 분석·재사용·근거·이력](portfolio-analysis.md) | 8/8 | 명세·원본 API 정리 |
| F07 | [투자 캘린더](investment-calendar.md) | 2/2 | 명세·원본 API 정리 |
| F08 | [뉴스·키워드·시장 분석](news.md) | 4/4 | 명세·원본 API 정리 |
| F09 | [뉴스·통합 검색](content-search.md) | 2/2 | 명세·원본 API 정리 |
| F10 | [종목 자료·공개 콘텐츠·인물](content-people.md) | 3/3 | 명세·원본 API 정리 |
| F11 | [피드백](feedback.md) | 1/1 | 명세·원본 API 정리 |
| F12 | [관리자 콘텐츠·피드백](administration.md) | 36/36 | 명세·원본 API 정리 |
| F13 | [수집·동기화·배치](sync-jobs.md) | 5/5 | 명세·원본 API 정리 |
| F14 | [이메일 알림 보류 경계](notifications-deferred.md) | 0/0 | 보류·서버 매핑 없음 |

`python3 scripts/knowledge_inventory.py --check`는 원본 Java 31개 컨트롤러의 HTTP 매핑과
기존 명세의 81개 핸들러·89개 메서드/경로 조합을 대조한다. DTO·권한 실행·업무 분기까지 검증하지 않는다.

[고정 API 목록](../../../contracts/api-index.json), [서비스 지도](../../../service-map.json),
[상세 검색·종가 근거](stock-search-price.md), [패키지 구성](../../shared/package-map.md).

F12는 관리자 콘텐츠·피드백, F13은 관리자 종목 동기화와 시스템 배치다.
F14의 프론트 mock과 리그 경로는 서버 구현 완료 범위에 섞지 않는다.
