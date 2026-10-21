# 008 — 새 관리자 API 두 개 병렬 구현

2026-10-21 KST. 기존 API 재작성 대신 아직 Rust 구현이 없던 GET /api/admin/feedbacks와 GET /api/admin/feedbacks/{id}를 새로 구현했다.

- 구현 2개: gpt-6.1-sol / medium, 파일 소유권 분리.
- 독립 테스트 작성·후속 구현 리뷰 1개: gpt-6-astra / high. 구현 작성에는 참여하지 않았다.
- 조정 담당이 원본 Controller/Service/DTO를 발췌하고 공통 HTTP/DB/JWT 어댑터를 연결했다.
- 같은 전용 fixture DB를 실제 Spring/Rust가 조회. 독립 기대값 18개가 양쪽 모두 통과했다.
  관리자 정상·비회원401·일반회원403·잘못된 토큰/탈퇴회원401·페이지/정렬/DTO/오류·DB 불변 포함.
- 최초 실제 검사 종료까지 192.522초. 이후 리뷰 승인.
- 마지막 Clippy에서 재사용 인증 보조 코드의 collapsible_if 경고로 실패했다.
  조건문 스타일만 수정한 뒤 Clippy와 실제 Spring/Rust 18개를 재실행해 모두 통과했다.
- Clippy는 -D warnings -A dead_code. 재사용 scaffold의 미사용 함수만 허용했다.
- 수정에 대한 별도 리뷰 승인 + 후보/반출/검사 기준/바이너리 해시 일치 확인.
- 새 범위 선택부터 최종 완료 판정까지 **435.711초**. 5분 목표 달성: **False**.

첫 실행 기록은 lint_failed_after_http_and_review로 보존하고, 최종 결과는 repair-1에 보존한다.
이전 뉴스/계산 재구현 준비는 사용자 수정 요청으로 에이전트 배정 전 취소했으며 별도 기록을 남겼다.
이번 시간에는 새 API 선택, 원본 분석, 작업 배정, 공통 서버 연결, 실행기 준비, 검사, 리뷰, 스타일 수정, 재검증이 포함된다.
기존 의존성 캐시·JWT 검증 모듈·Spring 빌드는 재사용했다. 승인 대기는 없었다.
전용 명세 에이전트·공통 무인 스케줄러·순차 대비 속도 향상은 이번에 검증하지 않았다.
실행 배정은 이 대화가 연결했고 작업자 문맥을 재사용했다.

코드: experiments/admin-feedback/. app에 통합하거나 커밋·배포하지 않았다.
id≤0 정확한 검증 메시지·상태 변경/삭제·전체 로그인/OIDC·운영 부하·전체 입력 호환은 미검증이다.
DB 전수 로딩은 작은 fixture용이다. 원본/복사본 474파일 해시 일치. 서버·이번에 시작한 DB는 종료했다.
원시 근거: .local/five-minute-split/20261021T045212Z-new/repair-1/timing.json.
