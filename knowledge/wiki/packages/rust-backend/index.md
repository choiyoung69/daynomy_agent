---
title: Rust 백엔드 상세 지식 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["DX05", "DX09", "DX10", "P02"]
---

# Rust 백엔드

기존 웹을 옮길 때 필요한 언어 의미와 플랫폼 경계를 함께 읽는 지식 묶음이다. 코드 라이브러리나 설치 가능한 앱 패키지는 아니다.
Rust 서버 조사 전용이며 다섯 클라이언트의 기본 문맥에는 포함하지 않는다.

## 주제별 문서

| 문서 | 확인할 내용 |
| --- | --- |
| [타입·null·JSON](types-and-json.md) | 누락/null/기본값, unknown 필드, 경계 디코딩 |
| [숫자·금액](numbers-and-money.md) | 안전 정수 ID, 이진 소수, 정밀도·반올림 |
| [날짜·Unicode](dates-and-unicode.md) | 날짜 전용 값과 시각, UTF-16/문자/바이트, 공백 |
| [컬렉션·모델 복사](collections-and-models.md) | 얕은 복사, 공유 참조, UI 스냅샷 |
| [비동기·취소](async-and-cancellation.md) | 실제 작업 취소, 늦은 응답, 요청 세대 |
| [상태·탐색·수명](state-and-navigation.md) | 상태 소유자, 화면 전환, 정리 시점 |
| [오류·트랜잭션](errors-and-transactions.md) | 오류 분류·자원 정리, 서버 원자성, 불확실한 결과 |
| [인증·저장소](auth-and-storage.md) | 쿠키/CSRF, 세션, 민감정보와 호스트 경계 |
| [모듈·의존성·검증](modules-and-testing.md) | 의존성 격리, 실제 실행과 통합 미검증 구분 |

## 코드와 실행 범위

각 문서는 실패하는 변환, 적용 코드/설계, 경계 사례와 근거를 담는다. `실행 가능한 전체 예제`로 연결한 파일의 assertion만 실제 검사에 포함된다.
UI·HTTP·저장소·DB 어댑터 스니펫은 해당 앱에 맞춰 연결할 설계 예시이며 독립 컴파일·통합 성공을 뜻하지 않는다.

예제 환경: **Rust 1.92.0 · serde_json 1.0.154 · Tokio 1.54.0**. 이 버전은 예제 실행을 위한 고정값이며 앱의 지원 버전 결정이 아니다.

별도 예제 crate의 JSON·산술·취소·가짜 트랜잭션. 실제 app/ HTTP·DB 재검증은 미실행.

이 언어 예제 15개 사례를 실행했다.
[전체 실행 기록](../../../evidence/2026-10-28-topic-examples-04.json)은 언어별 명령·종료 코드·결과·소스 해시를 담는다. 다섯 언어 합계 100개이며 플랫폼 통합 검사는 포함하지 않는다.

```sh
python3 scripts/knowledge.py package --package rust-backend --topic async-and-cancellation
```

앱 버전·라이브러리 잠금·실제 HTTP/DB·화면·기기 검증·독립 의미 평가가 남아 있다.
[구축 현황](../../../STATUS.md), [공통 검증 기준](../../shared/testing-migration.md), [전체 목차](../../index.md).
