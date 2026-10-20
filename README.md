# DAYNOMY Rust 에이전트 실험

첫 기능은 **비회원 피드백 등록**(`POST /api/feedback`)이다.
현재는 **Rust 구현 및 첫 로컬 검증 완료** 상태다.
실행 방법은 `app/README.md`, 실제 작업 기록은 `runs/002-implementation.md`에 있다.
운영 배포와 전체 Spring 동작의 완전한 호환성 검증은 수행하지 않았다.

## 왜 이 기능인가

| 후보 | 첫 실험 적합성 |
| --- | --- |
| 피드백 등록 | 외부 API와 로그인 없이 입력 검증 → 문자열 정리 → PostgreSQL 저장을 검증할 수 있다. CSRF는 필요하다. |
| 회원 닉네임 변경 | JWT·회원 데이터 준비가 먼저 필요하다. |
| 포트폴리오 계산/원장 | 가격·환율·여러 도메인·동시성 의존성이 크다. |

근거는 각 Controller와 `spec/feedback.md`의 파일 목록이다. 이것은 전체 서비스 완성이나
운영 이전이 아닌, 에이전트 작업 방식을 확인하는 첫 실험이다.

## 최소 구성

- `AGENTS.md`: 에이전트 작업 규칙
- `spec/feedback.md`: 범위·동작·근거·불확실성·완료 기준
- `spec/reference-snapshot.json`: 분석한 원본 파일의 SHA-256 (원본에 `.git` 없음)
- `prompts/implement.md`: 다음 구현 실행에 줄 요청문
- `scripts/check.py`: 준비 확인과 Rust 검사·인수 검증 진입점
- `scripts/acceptance.py`: 실제 HTTP와 PostgreSQL을 함께 확인하는 인수 검증
- `scripts/test_acceptance.py`: 검증기가 잘못된 결과를 거부하는지 확인하는 자체 테스트
- `runs/001-setup.md`: 이번 준비 작업의 관찰 기록
- `runs/002-implementation.md`: 구현·실패·수정·검증 결과와 에이전트 역할
- `app/`: Rust 피드백 서버, 스키마, 실행 안내

## 지금 실행할 수 있는 것

프로젝트 루트에서:

```sh
python3 scripts/check.py preflight
python3 scripts/test_acceptance.py
```

preflight는 분석 근거의 해시와 명령 설치 여부를 확인한다. 서버나 DB를 생성·수정하지 않는다.
`verify`를 실행하려면 아래처럼 테스트 DB와 서버를 먼저 시작해야 한다.

```sh
bash scripts/local-db.sh start
source .local/pilot.env
cargo build --manifest-path app/Cargo.toml --locked
./app/target/debug/daynomy-feedback
```

다른 터미널에서 같은 폴더로 이동해 `source .local/pilot.env` 후
`python3 scripts/check.py verify`를 실행한다.

## 첫 구현 실험

`prompts/implement.md`는 첫 구현에 사용한 요청문이다. 새 대화에서는 먼저 현재 실행 기록을
읽고 이어서 작업한다. 요청문 파일 자체가 에이전트를 자동 실행시키는 것은 아니다.

구현 에이전트는 `app/`에 Rust 서버와 실행 설명을 만든다. PostgreSQL은 원본과 같은
종류를 사용하되 **별도 로컬 테스트 DB**를 사용한다. DB 이름은 `_test`로 끝나야 한다.
서버의 DB와 인수 검증의 DB가 같아야 하며, 다른 요청이나 테스트를 동시에 보내지 않는다.
검증기는 행을 읽기만 하지만 HTTP 성공 요청으로 테스트 행이 생성되고 남는다.

서버 실행 후 다음 값을 로컬 환경변수로 설정한다. 실제 접속값은 커밋하거나 출력하지 않는다.

- `PILOT_BASE_URL`: 예: `http://127.0.0.1:8080`
- `PILOT_TEST_DB_URL`: 전용 테스트 DB의 PostgreSQL URI. 호스트는 loopback,
  DB 이름은 `_test` 접미사. 검증기는 `psql`을 이용한다.
- 서버의 `DATABASE_URL`: 위 테스트 DB와 동일한 연결 대상. 설정 방법은 구현 README에 기록한다.

```sh
python3 scripts/check.py verify
```

검사 순서: 원본 해시 확인 → Rust fmt/clippy/test/build → 하네스 자체 테스트 →
HTTP/DB 인수 검증. 성공 보고를 꾸미지 않고 누락된 환경이나 실패를 비정상 종료로 반환한다.
각 명령에는 실행 시간 제한이 있다. 최초 의존성 다운로드/빌드가 제한을 넘으면 원인을
기록하고 `PILOT_COMMAND_TIMEOUT_SECONDS`로 조정한다 (기본 600초).

인수 검증만 별도로 실행할 수도 있다:

```sh
python3 scripts/acceptance.py
```

결과는 `runs/acceptance-*.json`에 기록된다. 재시작 후 영속성 및 DB 장애는
`python3 scripts/check_lifecycle.py`로 별도 확인한다. 이 명령은 전용 테스트 DB에 잠시
INSERT 거부 제약을 추가했다 제거하므로 다른 테스트와 동시에 실행하지 않는다.
의존성/unsafe 코드 리뷰는 별도 확인한다.

첫 실행 결과: Rust 테스트 7개, 하네스 자체 테스트 9개,
HTTP/DB 사례 33개 + CSRF 준비 검사, 재시작/장애 관련 검사 4개 통과.
최종 확인 후 서버와 전용 DB는 종료했고 테스트 행 12개는 보존했다.

## 이번 실험에서 볼 것

사람의 추가 지시 횟수와 이유, 총 소요 시간, 최초 실패, 수정 시도, 최종 통과 항목,
남은 결함을 기록한다. 사용량은 도구가 제공하는 값만 기록한다.
첫 실행은 기준선 관찰이며, 이 결과 하나로 하네스가 생산성을 높였다고 단정하지 않는다.
실제 실패 원인을 보고 규칙이나 검사 하나씩 추가한다.
