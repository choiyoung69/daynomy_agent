---
title: 보유자산·거래 원장·수익률
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["P02", "W05", "W02", "W03", "JC26", "JC28"]
---

# 보유자산·거래 원장·수익률

F05의 기존 명세를 작업용으로 정리한 문서다. 계약의 상세 근거는 [서비스 명세](../../../../spec/service.md)이며,
이 문서는 모든 분기의 현재 런타임 호환성을 인증하지 않는다. 최신 사용자 결정은 명세의 결정 기록을 우선한다.

## 기능 계약



## 원본 API 연결

| 메서드 | 경로·별칭 | 명세 권한 |
| --- | --- | --- |
| GET | `/api/portfolio`, `/api/users/me/portfolio` | 회원 |
| POST | `/api/portfolio/transactions`, `/api/users/me/portfolio/transactions` | 회원 |
| PATCH | `/api/portfolio/transactions/{transactionId}`, `/api/users/me/portfolio/transactions/{transactionId}` | 회원 |
| DELETE | `/api/portfolio/transactions/{transactionId}`, `/api/users/me/portfolio/transactions/{transactionId}` | 회원 |
| PATCH | `/api/portfolio/holdings/{assetId}`, `/api/users/me/portfolio/holdings/{assetId}` | 회원 |
| DELETE | `/api/portfolio/holdings/{assetId}`, `/api/users/me/portfolio/holdings/{assetId}` | 회원 |
| GET | `/api/portfolio/performance`, `/api/users/me/portfolio/performance` | 회원 |
| GET | `/api/portfolio/histories`, `/api/users/me/portfolio/histories` | 회원 |
| POST | `/api/v2/users/me/portfolio/transactions` | 회원 |

전체 경로는 [API 목록](../../../contracts/api-index.json), 원본 프론트 출처는 W05, W02, W03를 따른다.

## 이식과 검사

게스트/회원 원장·매수/매도·수정/삭제·초과 매도·동시 요청·롤백을 확인한다.
공통 입력·오류·인증·UI 상태에 대상 언어/플랫폼의 디코더·수명·저장소를 대응한다.
실제 플랫폼 버전·명령·입력·기대값·관찰값·소스 해시를 남긴다. 서버의 과거 검사 결과를 앱 실행 결과로 재사용하지 않는다.

[패키지 조합](../../shared/package-map.md), [인증·저장](../../shared/auth-storage.md),
[검증](../../shared/testing-migration.md), [미확인 질문](../../../questions.md).
