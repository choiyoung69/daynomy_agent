# 002 — 피드백 기능 구현 실험

- 시작: 2026-10-20 15:26:10 KST (preflight 후 기록 시각).
- 검증/환경 정리 완료: 2026-10-20 15:35:21 KST. 이 구간 관찰 시간 9분 11초.
  최초 사용자 요청 수신부터의 전체 시간이나 사람의 작업 시간을 측정한 값은 아니다.
- 상태: Rust 첫 기능 구현·로컬 검증 완료. 서버/전용 PostgreSQL 종료, 테스트 데이터 보존.
- 작업자: 현재 대화의 구현 에이전트 1개. 별도 하위 AI 에이전트 없음.
- 검증자: 고정된 Python 인수 검증 + Rust 테스트 + 구현 에이전트의 코드 리뷰.
  독립 AI 리뷰를 수행한 것으로 해석하지 않는다.
- 사람의 역할: 요구사항/범위 결정. 함수·파일별 구현 지시는 요구하지 않는다.
- 비용/토큰: 미측정.

## 진행

1. 기존 명세·작업 규칙·요청문을 다시 읽고 preflight 통과, 원본 29/29 해시 일치.
2. 개별 라이브러리로 Hyper(HTTP), Tokio(비동기), Serde(JSON), tokio-postgres(DB),
   UUID v4(무작위 토큰), subtle(토큰 비교)을 선택. 웹 프레임워크는 사용하지 않는다.
3. app/에 입력 검증, CSRF, 서버와 DB 저장을 구현. 로컬 전용 PostgreSQL을 준비한다.

## 막힌 지점과 처리

| 문제 | 분류 | 처리/결과 |
| --- | --- | --- |
| cargo check: crates.io DNS 접근 실패, 종료 101 | 실행 환경 | 프로젝트 전용 CARGO_HOME 유지, 필요한 네트워크 권한으로 재실행. 종료 0 |
| initdb: shared memory Operation not permitted, 종료 1 | 실행 환경 | 전용 클러스터만 필요한 권한으로 초기화, 시작 성공 |
| verify 첫 실행: DB 확인 단계에서 종료 2 | 하네스 결함 | PGDATABASE에 URI를 넣으면 psql이 해당 URI를 연결 인자로 확장하지 않아 기본 소켓을 시도함 |
| 하네스 DB 연결 수정 | 수정 | URI를 PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD로 분리하고 상속된 연결 우회 설정 제거. 회귀 테스트 추가 |

세 번째 문제는 실제 서버 기능 실패가 아니라 검증기의 DB 접속 실패였다.
당시 Rust fmt/clippy/test/build와 기존 검증기 자체 테스트 8개는 이미 통과했었다.
HTTP/DB 동작을 아직 확인하지 못했으므로 완료로 처리하지 않았다.
고정된 인수 사례의 입력·기대 상태·DB 검사 조건은 변경하지 않았다.
접속 인자를 수정한 뒤 같은 33개 사례를 실행했다.

## 최종 검증

| 명령/검사 | 결과 |
| --- | --- |
| `python3 scripts/check.py preflight` | 원본 29/29 일치 |
| `cargo check --manifest-path app/Cargo.toml` | 종료 0 |
| `cargo fmt --manifest-path app/Cargo.toml -- --check` | 종료 0 |
| `cargo clippy --manifest-path app/Cargo.toml --all-targets -- -D warnings` | 종료 0 |
| `cargo test --manifest-path app/Cargo.toml` | 7 passed, 0 failed, 0 ignored |
| `cargo build --manifest-path app/Cargo.toml` | 종료 0 |
| `python3 scripts/test_acceptance.py` | 9 passed (DB 환경변수 전달 회귀 테스트 1개 추가) |
| `python3 scripts/check.py verify` | 종료 0, CSRF 준비 + HTTP/DB 33개 사례 통과 |
| `python3 scripts/check_lifecycle.py` | 종료 0, 아래 4개 검증 통과 |
| `bash -n scripts/local-db.sh` 및 Python 구문 검사 | 통과 |

원시 결과 파일(로컬 실행 산출물로 Git 제외):

- `runs/acceptance-20261020T063148460630Z.json`: 첫 DB 연결 실패.
- `runs/acceptance-20261020T063256478660Z.json`: 34/34 검사 통과.
- `runs/lifecycle-20261020T063425283245Z.json`: 재시작·장애 검사 통과.

재시작·장애 검증:

1. 새 서버에서 저장한 행이 서버 종료/재시작 후 그대로 남았다.
2. 전용 DB에 임시 CHECK 제약을 추가해 저장을 거부시키자 500을 반환했고 행은 늘지 않았다.
3. 제약을 제거한 뒤 같은 서버에서 다시 저장하면 204와 새 행을 확인했다.
4. 실험 서버 로그에 입력 본문 마커·토큰·DB 연결 문자열이 없음을 확인했다.

정리 결과: feedbacks 12행 보존, 임시 장애 제약 0개, 서버는 정상 종료 코드 0,
전용 DB도 정상 종료. 기존 원본 파일과 시스템 DB는 수정하지 않았다.

## 코드 리뷰

- 자체 크레이트는 하나이며 main.rs의 forbid(unsafe_code)가 모든 모듈에 적용된다.
  자체 unsafe 사용 없음. 의존성 내부의 unsafe는 검사/금지 대상이 아니다.
- 직접 의존성 9개를 cargo tree로 확인. 웹 프레임워크 없음.
- SQL은 매개변수로 전달하며 입력을 SQL 문자열에 삽입하지 않는다.
- 원문 UTF-16 길이 검사 후 Java whitespace 규칙으로 정리한다.
- CSRF는 신규 UUID v4 난수, 쿠키/헤더 일치와 중복 거부, subtle 비교를 사용한다.
- 응답 오류는 고정된 공개 문구이며 DB/입력/쿠키 원문을 앱 로그에 출력하지 않는다.
- 요청 크기/시간/동시 연결 제한과 종료 시 대기를 넣었다.
- 세부 의존성·실행 방법·구현 선택은 app/README.md에 기록했다.

## 사람이 한 일과 에이전트 수

추가 요구사항 결정을 위한 질문이나 함수별 지시는 없었다. 실행 권한 요청은 도구의
권한 절차로 처리했으며 기능 요구사항에 대한 사람의 개입과 구분한다.

에이전트는 1개를 사용했다. 같은 에이전트가 설계·구현·오류 수정·코드 리뷰를 수행하고,
고정된 프로그램이 기대 HTTP 응답과 DB 결과를 검사했다. 테스트 프로그램은 AI 에이전트가 아니다.
따라서 여러 독립 에이전트가 서로 검증했다고 주장하지 않는다.
독립 기능이 여러 개 생기면 작업자 분리를 검토하고, 별도 리뷰가 필요하면 읽기 전용
리뷰 에이전트를 추가하는 방식을 다음 실험으로 고려할 수 있다.

## 한계/다음 판단

기존 Spring 실서버와 직접 차등 비교하지 않았다. Jackson/Unicode/브라우저 보안의
모든 동작, 운영 성능·복구·배포를 검증한 것은 아니다. DB 연결 단절 시 자동 재연결은 없다.
현재는 공유 DB 연결 하나와 로컬 HTTP 실험 설정이다.

이번 관찰은 첫 실행의 사례다. 비교 실행 없이 하네스가 시간/비용을 절감했다고 결론 내리지 않는다.
실제로 드러난 개선점은 검증기의 환경 연결도 테스트해야 한다는 것이었다.
