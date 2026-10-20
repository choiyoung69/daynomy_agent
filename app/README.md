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

- unknown JSON 필드는 무시하고 숫자→문자열 자동 변환은 하지 않는다.
  중복 DTO 필드와 잘못된 JSON은 requestBody 오류로 거부한다.
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
