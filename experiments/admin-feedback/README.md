# 관리자 피드백 조회 실험

새 Rust API: GET /api/admin/feedbacks, GET /api/admin/feedbacks/{id}.
목록·상세는 별도 구현 담당, HTTP 기대값은 구현을 읽지 않은 별도 담당이 작성했다.
공통 Hyper/DB/서명 JWT 검증 코드는 재사용했다. 별도 로그인 발급·쓰기 API·운영 배포는 포함하지 않는다.
서버는 DATABASE_URL, JWT_SECRET(base64 32바이트 이상), JWT_ISSUER(기본 daynomy), PORT를 사용한다.
실험용 DB의 실제 회원 상태·관리자 권한을 검사하며 인증 우회 헤더는 없다.
DB 행 전체 로딩은 작은 fixture용이며 운영 성능 구현이 아니다.

검증 근거는 루트 runs/008-new-api-parallel.md에 기록한다. 독립 기대값은 tests/cases.json이다.
실제 검사 당시 실행기는 .local/five-minute-split/20261021T045212Z-new/run.py이며,
이 실행기가 공통 무인 스케줄러라는 의미는 아니다. 수정·배포 전 별도 통합 검증이 필요하다.
