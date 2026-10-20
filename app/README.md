# 피드백 Rust 서버

구현 범위: 비회원 피드백 등록과 필요한 CSRF 발급. 웹 프레임워크 없이 HTTP를 직접
분기하며 자체 Rust 코드에 `#![forbid(unsafe_code)]`를 적용한다.

## 실행

프로젝트 루트(`daynomy_agent`)에서 실행한다. Rust/Cargo, Python 3.11 이상,
PostgreSQL CLI/서버가 필요하다. 검사에는 rustfmt/clippy도 필요하다.
검증 환경은 macOS, Rust 1.92, PostgreSQL 18이다.

```sh
bash scripts/local-db.sh start
source .local/pilot.env
cargo build --manifest-path app/Cargo.toml --locked
./app/target/debug/daynomy-feedback
```

다른 터미널에서 같은 프로젝트 루트로 이동한 뒤:

```sh
source .local/pilot.env
python3 scripts/check.py verify
```

`verify`는 원본 해시, Rust fmt/clippy/test/build, 검증기·비교기 자체 테스트,
실제 HTTP/DB 동작을 차례로 검사한다. 실패하면 비정상 종료한다.
각 실행 명령의 제한 시간은 기본 600초다. 최초 의존성 다운로드 등으로 시간이
초과하면 원인을 기록한 뒤 `PILOT_COMMAND_TIMEOUT_SECONDS`로 조정할 수 있다.
HTTP/DB 검사만 실행하려면 같은 환경에서 `python3 scripts/acceptance.py`를 사용한다.
`PILOT_BASE_URL`은 로컬 서버, `PILOT_TEST_DB_URL`은 서버와 동일한 전용 테스트 DB를
가리켜야 하며 helper가 `.local/pilot.env`에 설정한다. DB 이름은 `_test`로 끝나야 한다.
검사 중에는 다른 요청이나 검사를 동시에 실행하지 않는다. 성공 요청의 테스트 행은 남는다.
자동 결과는 Git에서 제외한 `runs/acceptance-*.json`에 기록된다.

자동 게이트 이후 재시작·저장 장애 검증:

```sh
python3 scripts/check_lifecycle.py
```

이 검증은 별도 포트에서 서버를 두 번 실행하고 종료한다. 전용 테스트 DB에 임시
`pilot_failure_probe` 제약을 추가해 INSERT를 실패시킨 후 제거한다. 기존 데이터는 유지한다.
다른 테스트를 동시에 실행하지 않는다. 강제 종료로 정리가 중단되면 전용 테스트 DB의
해당 제약만 제거한 뒤 재실행한다.

서버는 기본 helper 설정에서 `127.0.0.1:18081`에만 바인딩한다. 종료는 Ctrl+C.
DB 종료는 `bash scripts/local-db.sh stop`. 재시작해도 `.local/pgdata`의 데이터는 유지된다.
helper는 테스트 데이터를 삭제하지 않는다.

`PG_BIN`으로 PostgreSQL 실행 파일 디렉터리를 지정할 수 있다.
기본값은 `/opt/homebrew/opt/postgresql@18/bin`이다. 포트 충돌 시 최초 실행 전에
`PILOT_DB_PORT`와 `PILOT_PORT`를 지정한다. 기존 클러스터의 포트를 바꾸려면 먼저 정지한다.

helper는 기존 시스템 DB를 사용하지 않고 `.local/pgdata`에 별도 클러스터를 만든다.
loopback 전용 trust 인증, 테스트 계정 `pilot`, `daynomy_feedback_test` DB를 사용한다.
이 설정은 로컬 실험용이며 운영용 계정/인증/배포 설정이 아니다. 접속값은 Git에서 제외된
`.local/pilot.env`에 저장하며 원본 프로젝트의 `.env`는 읽지 않는다.

## 설정과 데이터

- `DATABASE_URL`: PostgreSQL 연결. 현재 클라이언트는 NoTls이며 로컬 실험용이다.
- `PORT`: 서버 포트, 직접 실행 시 기본 8080, helper는 18081로 설정.
- 스키마: `migrations/001_feedbacks.sql`을 빈 테스트 DB에 한 번 적용.
  helper는 feedbacks 테이블이 없는 경우만 적용한다. 스키마 drift를 자동 수정하지 않는다.
- 서버는 스키마를 자동 생성하지 않는다. 없거나 DB 접속이 실패하면 시작을 거부한다.
- `.local/cargo`에 프로젝트 전용 의존성 캐시를 둔다. Cargo.lock으로 버전을 고정한다.

## 요청 흐름

1. `GET /api/auth/csrf`: JSON의 headerName/token과 XSRF-TOKEN 쿠키를 받는다.
2. 같은 쿠키와 지정 헤더를 사용하여 `POST /api/feedback`에 JSON을 보낸다.
3. 원문 길이/필수값 검사 → Java 방식 앞뒤 공백 제거 → parameterized INSERT.
4. 저장 완료 시에만 본문 없는 204. DB 오류는 일반화된 500, 입력 오류는 400.

CSRF는 원본과 같은 쿠키/헤더 double-submit 방식이며 UUID v4를 생성한다.
이미 유효한 쿠키가 있으면 재사용한다. 서로 다른 신규 클라이언트에는 다른 토큰을 제공한다.
비교는 subtle의 constant-time 비교를 사용하고, 중복 토큰 헤더/쿠키는 거부한다.
HTTP 로컬 실험에서는 SameSite=Lax, Path=/, Domain 없음, HttpOnly=false를 사용한다.
전체 OAuth·JWT·브라우저 CORS·HTTPS·서브도메인 cookie injection 방어를 구현한 것은 아니다.

## 직접 의존성

| 라이브러리 | 역할 |
| --- | --- |
| hyper | HTTP/1.1 프로토콜 처리. 경로와 요청 처리 구조는 직접 작성 |
| hyper-util | Tokio 소켓/타이머와 Hyper 연결 |
| http-body-util | 응답 body, 요청 body 크기 제한 |
| tokio | 비동기 I/O·태스크·신호·시간 제한 |
| tokio-postgres | 매개변수 SQL로 PostgreSQL 접근 |
| serde, serde_json | DTO와 JSON |
| uuid | UUID v4 토큰 (OS 난수 사용) |
| subtle | 토큰 비교 |

Axum/Actix Web/Rocket 등 웹 프레임워크 없음. 의존 라이브러리 내부의 unsafe는 별도 범위다.
공식 사용법 참고: [Hyper 서버](https://hyper.rs/guides/1/server/hello-world/),
[tokio-postgres](https://docs.rs/tokio-postgres/latest/tokio_postgres/),
[UUID v4](https://docs.rs/uuid/latest/uuid/struct.Uuid.html#method.new_v4).

## 첫 실험의 구현 선택과 한계

- 2026-10-21 사용자 결정으로 content는 문자열만 허용한다. JSON 객체의 중복 키는
  unknown field와 중첩 객체 안에서도 검사해 requestBody 400으로 거부한다.
  중복이 없는 unknown field는 무시한다. 상세 계약은 `spec/feedback.md`를 따른다.
- 원본과 전체 Unicode/Jackson 호환성을 검증한 것은 아니다.
- 알 수 없는 경로 404, 잘못된 메서드 405, JSON 외 Content-Type 415.
  이 응답 문구/형식은 Spring과 완전 호환을 주장하지 않는다.
- 요청 본문 최대 64 KiB, 헤더/본문 수신 제한 각 5초, DB statement timeout 5초.
  본문 제한 초과/읽기 오류는 requestBody 400, 수신 timeout은 408.
- 동시 연결 최대 64개, keep-alive를 끄고 요청 종료 후 연결을 닫는다.
  공유 DB 연결 하나를 사용하며 자동 재연결/커넥션 풀은 없다.
- Ctrl+C/SIGTERM 시 최대 15초 동안 처리 중인 연결을 기다린다.
- 앱 로그는 이벤트와 저장 ID만 남기며 입력 본문·경로·쿠키·DB 오류 원문은 출력하지 않는다.
- 배포·성능 벤치마크·운영 보안 검증은 이번 완료 범위 밖이다.

## 원본 Spring과 비교

프로젝트 루트에서 다음 명령 하나로 두 서버의 빌드·시작·비교·종료를 수행한다.
실행 환경에는 위 도구 외에 JDK 21이 필요하고, 처음에는 Gradle 의존성 다운로드가 필요하다.

```sh
python3 scripts/run_comparison.py
```

- 원본의 빌드 파일과 `src/main`을 `.local/spring-reference`에 복사해 빌드한다.
  원본 `.env`와 사용자 환경의 실제 API 키·DB 설정은 가져오지 않는다.
- 원본 애플리케이션 전체를 시작하되 스케줄러는 끄고 외부 API 주소는 로컬 미사용
  주소로 바꾼다. OAuth·S3 설정에는 테스트 전용 값을 사용한다.
  피드백 Controller·Service·Repository·Validation·Security 필터는 원본 그대로다.
- Spring은 18082, Rust는 18083 포트다. 이미 사용 중이면 중단한다.
- 프로젝트 전용 PostgreSQL 55439에 `daynomy_spring_compare_test`와
  `daynomy_rust_compare_test`를 별도로 만든다. 기존 피드백 실험 DB는 비교에 쓰지 않는다.
- 전체 원본 앱의 JPA 검증에 필요한 원본 Flyway 마이그레이션은 **Spring 비교 DB에만**
  실행한다. Rust 비교 DB에는 피드백 테이블만 준비한다.
- 비교에 사용한 소스·설정·시작 로그는 `.local/comparison/`, 비교 결과는
  `runs/comparison-*.json`에 남긴다. 요청 본문·토큰·접속 문자열은 결과 보고서에 남기지 않는다.
- 서버는 종료하고 DB 데이터는 보존한다. DB는 이 명령이 시작한 경우에만 종료한다.
  정상 실행 또는 예외 처리 중 정리하며, 프로세스를 강제로 kill한 경우에는 수동 확인이 필요하다.

종료 코드: `0`은 공통 계약 및 승인된 정책 차이 검사 통과,
`1`은 계약 위반이나 예상하지 않은 차이, `2`는 환경·실행·정리 문제다.
숫자·boolean·중복 키의 승인된 차이는 `EXPECTED_DIFFERENCE`로 표시한다.
Spring은 정해진 값으로 저장하고 Rust는 정해진 400으로 거절·미저장해야 통과한다.
원본과 완전히 같은지를 뜻하는 보고서의 `full_match`는 별도이며, 승인된 차이가 있으면 false다.
세부 결과와 제외 범위는 `runs/003-comparison.md`, 기준은 `spec/feedback.md`에 있다.

비교기 자체의 검사는 서버 없이 `python3 scripts/test_compare_feedback.py`로 실행한다.
