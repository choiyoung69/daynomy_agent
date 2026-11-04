---
title: AI 분석·재사용·근거·이력
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "W05", "W04", "JC15", "JC23", "JC25", "JC27", "JC29"]
---

# AI 분석·재사용·근거·이력

F06의 기존 명세를 작업용으로 정리한 문서다. 계약의 상세 근거는 [서비스 명세](../../../../spec/service.md)이며,
이 문서는 모든 분기의 현재 런타임 호환성을 인증하지 않는다. 최신 사용자 결정은 명세의 결정 기록을 우선한다.

## 기능 계약



## 원본 API 연결

| 메서드 | 경로·별칭 | 명세 권한 |
| --- | --- | --- |
| GET | `/api/news/{newsId}/market-analysis` | 공개 |
| POST | `/api/portfolio/analysis` | 공개 |
| GET | `/api/users/me/portfolio/analysis/history` | 회원 |
| GET | `/api/users/me/portfolio/analysis` | 회원 |
| POST | `/api/users/me/portfolio/analysis/refresh` | 회원 |
| POST | `/api/users/me/portfolio/analysis` | 회원 |
| POST | `/api/v1/users/me/portfolio/analysis` | 회원 |
| POST | `/api/v2/users/me/portfolio/analysis` | 회원 |

전체 경로는 [API 목록](../../../contracts/api-index.json), 원본 프론트 출처는 W05, W04를 따른다.

## 이식과 검사

저장 상태·체험 소진·재사용·409·실패 후 이전 결과 보존·부분 분석을 확인한다.
공통 입력·오류·인증·UI 상태에 대상 언어/플랫폼의 디코더·수명·저장소를 대응한다.
실제 플랫폼 버전·명령·입력·기대값·관찰값·소스 해시를 남긴다. 서버의 과거 검사 결과를 앱 실행 결과로 재사용하지 않는다.

[패키지 조합](../../shared/package-map.md), [인증·저장](../../shared/auth-storage.md),
[검증](../../shared/testing-migration.md), [미확인 질문](../../../questions.md).

## Android 회원 분석의 준비 범위

2026-11-04 사용자 요청으로 Android 포트폴리오에 F06 회원 분석을 연결한다. 원본 W05의 isSavedPortfolioAnalysis/isPortfolioAnalysisResponse와 JC25 SavedPortfolioAnalysisController·Rust service_analysis.rs handle/saved_response를 대조했다. GET 저장 결과/상태, POST 생성·재사용, POST /refresh 근거 확인, GET /history 최근10건을 기존 세션/CSRF로 연결한다. 게스트 체험·V1/V2 선택 UI는 이번 Android 범위가 아니며 백엔드 경로는 유지한다.

- EMPTY/READY/PORTFOLIO_CHANGED/PROCESSING/RECHECK_REQUIRED/FAILED와 lastCheckOutcome·matchesCurrentPortfolio를 분리한다. 실패/변경/진행중의 이전 성공 결과는 현재 정상 결과로 오인시키지 않고 생성시각과 함께 보존한다.
- score/direction null·PARTIAL/INSUFFICIENT·분석종목수·출처를 보존한다. score를0으로 바꾸지 않는다. JSON 숫자는 BigDecimal로 읽고 출처는HTTP(S)만 허용한다. 원본 필수nullable 필드는 누락과null을 구분한다.
- 화면 열기는GET만 수행한다. 분석/근거갱신은 명시적 POST이며 중복 제출을 막는다. 409/전송 후결과불명/잘못된POST응답에는 재전송하지 않고GET으로 확인한다. GET 실패때 기존 결과를 빈성공으로 대체하지 않는다.
- 계정/보유 변경·로그아웃 후 늦은응답을 차단한다. 이력오류는 현재결과를 지우지 않는다. 실제외부AI호출/운영설정/DB검증 완료로 표현하지 않는다.

[Android 회원 AI 연결/검증 범위](https://github.com/choiyoung69/daynomy_agent/blob/design/15-android-portfolio/spec/android-native/ai-analysis.md)는 별도 기록으로 관리한다. 합성 HTTP·상태 검사를 실제 외부 모델/DB 실행 증거로 재사용하지 않는다.
