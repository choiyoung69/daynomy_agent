# DAYNOMY Rust 백엔드

웹 프레임워크 없이 Hyper로 요청을 분기한다. 자체 크레이트에는
`#![forbid(unsafe_code)]`를 적용한다. 의존성 내부의 unsafe까지 금지한다는 뜻은 아니다.

범위는 [전체 명세](../spec/service.md)의 F01–F13이다. 리그·UI·배포·이메일 알림(F14)은
제외한다. 구현 여부와 실제 검증 결과는 [이번 실행 기록](../runs/010-three-hour-service.md)에서
구분한다. 코드를 작성했다는 이유만으로 모든 외부 서비스 연결이 검증된 것은 아니다.

## 로컬 실행

프로젝트 루트에서 Rust/Cargo, Python 3.11+, PostgreSQL CLI/서버를 사용한다.
원본 `.env`나 운영 DB를 사용하지 않는다. 아래는 비밀번호 없는 loopback 실험 DB다.

```sh
bash scripts/local-db.sh start
/opt/homebrew/opt/postgresql@18/bin/createdb -h 127.0.0.1 -p 55439 -U pilot daynomy_service_test
export DATABASE_URL=postgresql://pilot@127.0.0.1:55439/daynomy_service_test
export PORT=18081
export JWT_SECRET="$(openssl rand -base64 32)"
export JWT_ISSUER=daynomy
export COOKIE_SECURE=false
python3 scripts/service_migrate.py
export CARGO_HOME="$PWD/.local/cargo"
cargo run --locked --manifest-path app/Cargo.toml
```

DB가 이미 있으면 `createdb`를 반복하지 않는다. `service_migrate.py`는 적용한 SQL의 해시를
검사하고 재실행 시 건너뛴다. 이 도구는 loopback의 `_test` DB만 허용한다. 기존 피드백
전용 DB처럼 스키마는 있지만 이 도구의 이력이 없는 DB에는 적용을 거절한다.

`migrations/reference/`의 SQL 51개는 원본 V1–V53 범위에서 그대로 복사했다.
리그 테이블도 원본 스키마 호환성을 위해 남지만 리그 API·배치는 제공하지 않는다.
원본 V25에 피드백 테이블이 있으므로 별도의 `001_feedbacks.sql`은 중복 적용하지 않는다.
추가 OAuth 상태·비회원 분석 세션 테이블을 적용한다. 서버 자체는 스키마를 생성하지 않는다.

서버는 loopback에 바인딩하고 기본 포트는 8080이다. 종료는 Ctrl+C.
요청 본문·쿠키·토큰·DB 연결 문자열은 서버 로그에 남기지 않는다.
현재 DB 연결은 NoTls이며 로컬 실험 범위다.

## 검증

원본 비교에는 캐시된 원본 Spring JAR과 Java 21도 필요하다. 실행기는 후보 코드를 복사하고,
별도 빌드·일회용 DB·로컬 제공자를 사용하며 끝나면 프로세스와 DB를 정리한다.
DB를 쓰는 검사는 공유 잠금으로 직렬 실행한다. 각 `--output`은 새 디렉터리여야 한다.

```sh
python3 scripts/service_gate.py \
  --output .local/service-verification-1 \
  --standalone-schema --mock-auth --mock-ai \
  --suites public core service_calendar_acceptance service_auth_provider_acceptance service_analysis_acceptance service_admin_acceptance binding
```

각 제공자 모의 서버는 다른 응답 계약을 사용하므로 분리해서 검사한다.

```sh
python3 scripts/service_gate.py --output .local/service-verification-media \
  --standalone-schema --mock-media --suites service_media_acceptance
python3 scripts/service_gate.py --output .local/service-verification-social \
  --standalone-schema --mock-social --suites service_social_acceptance
python3 scripts/service_gate.py --output .local/service-verification-sync \
  --standalone-schema --mock-sync --suites service_sync_acceptance
python3 scripts/service_gate.py --output .local/service-verification-fx \
  --standalone-schema --mock-fx --suites service_fx_acceptance
python3 scripts/service_gate.py --output .local/service-verification-schedule \
  --standalone-schema --mock-schedule --suites service_schedule_acceptance
```

`service_gate`의 결과에는 후보 소스·바이너리 해시, 명령별 시간, 실제 통과·실패 수가 남는다.
`--source`와 `--criteria-source`로 고정한 소스·검사 복사본을 지정할 수 있다.
`--mutant`는 별도 후보 복사본에만 의도적인 결함을 넣는다. 이 후보의 검사 실패는
결함 탐지 증거이며 정상 구현의 성공 결과와 구분한다.
실제 Google/S3/공공데이터/유료 AI 환경 검증과 로컬 모의 서버 검증은 구분한다.

기존 피드백 전용 검사 `scripts/check.py verify`, `scripts/acceptance.py`,
`scripts/check_lifecycle.py`도 유지한다. 이 검사만 통과했다고 전체 서비스를 완료로 판정하지 않는다.

## 배치 실행

기본값으로 예약 작업은 실행하지 않는다. 명시적으로 한 번 실행할 수 있다.

```sh
cargo run --locked --manifest-path app/Cargo.toml -- --job portfolio-snapshots
```

작업: `market-calendar`, `kr-master`, `kr-prices`, `us-stocks`, `exchange-rate`,
`portfolio-snapshots`, `investment-calendar`, `news-korea`, `news-us`, `person-posts`.
결과는 JSON으로 출력하고 실패·부분 성공은 비정상 종료한다. 외부 작업에는 해당 제공자 설정이 필요하다.
예약 실행은 `JOB_SCHEDULER_ENABLED=true`와 `JOB_SCHEDULER_JOBS` CSV를 모두 지정한다.
원본 개별 `*_ENABLED=false`는 선택된 작업도 막는다. 원본 cron·시간대를 사용하며
지원하지 않는 cron 표현식은 거절한다. 동시에 같은 작업을 실행하는 프로세스는 DB 잠금으로 막지만,
재시작을 넘는 실행 체크포인트는 저장하지 않는다.

## 주요 설정

- 인증: `JWT_SECRET`(32바이트 이상 base64), `JWT_ISSUER`, `COOKIE_SECURE`,
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`,
  `SUCCESS_REDIRECT_URI`, `FAILURE_REDIRECT_URI`.
- CORS: `APP_CORS_ALLOWED_ORIGIN` 정확히 한 origin, 기본 `http://localhost:5173`.
- AI: `AI_OPENAI_BASE_URL`, `AI_OPENAI_API_KEY`, `AI_OPENAI_MODEL`.
- 가격·환율: `EODHD_BASE_URL`, `EODHD_API_TOKEN`, `PUBLIC_DATA_SERVICE_KEY`,
  `PUBLIC_DATA_LISTED_STOCK_URL`, `PUBLIC_DATA_STOCK_PRICE_URL`, `PUBLIC_DATA_ETF_PRICE_URL`.
- 미디어: `WIKIMEDIA_BASE_URL`, `WIKIMEDIA_USER_AGENT`, `S3_REGION`, `S3_BUCKET`,
  `S3_OBJECT_PREFIX`, `S3_PUBLIC_BASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  선택적으로 `AWS_SESSION_TOKEN`, `S3_ENDPOINT_URL`.
- 소셜: `YOUTUBE_API_KEY`, `YOUTUBE_BASE_URL`, `AI_OPENAI_SOCIAL_SEARCH_MODEL`.

테스트용 제공자 override는 명시한 loopback 주소만 허용한다. 실제 배포 설정은 이번 범위에 포함하지 않는다.

## 직접 의존성

| 라이브러리 | 용도 |
| --- | --- |
| hyper, hyper-util, http-body-util | HTTP와 제한된 본문 처리 |
| tokio | 비동기 I/O·태스크·신호·타이머 |
| tokio-postgres | 매개변수 SQL·트랜잭션·정확한 NUMERIC 계산 |
| serde, serde_json | JSON, 임의 정밀 숫자 유지 |
| reqwest | 제한 시간·본문 크기를 제한한 제공자 HTTP |
| jsonwebtoken, hmac, sha2, base64, subtle | JWT/OIDC 검증·해시·서명·상수 시간 비교 |
| uuid | 식별자·CSRF·세션 난수 |
| zip, flate2 | OpenDART ZIP 문서의 제한된 메모리 해제 |

ZIP은 [공식 문서](https://docs.rs/zip/9.0.5/zip/)에 따라 필요한 DEFLATE 기능만 사용한다.
의존성 버전은 `Cargo.lock`에 고정한다.

## Flutter 네이티브 로그인 확장

`migrations/004_mobile_auth_codes.sql`을 기존 마이그레이션 이후 적용한다.
기존 Google/OIDC·JWT·쿠키 설정을 그대로 사용하며 새 Google 자격 증명 종류를 만들지 않는다.
`OAUTH_REDIRECT_URI`는 기존 서버의 `/login/oauth2/code/google`이고, 모바일 성공/실패는
서명된 OAuth state를 확인한 뒤 고정 `org.daynomy.app://auth/callback`으로 전달한다.
요청의 임의 redirect 주소는 사용하지 않는다. 웹 성공/실패 redirect 설정과 기존 웹 흐름은 유지한다.

- `GET /api/auth/mobile/start?code_challenge=...&state=...`: S256 challenge·앱 state 검증 후 외부 Google 인증.
- `POST /api/auth/mobile/exchange`: JSON `{code, codeVerifier}`를 검증해 기존 쿠키 세션을 발급하는 204 응답.

DB에는 코드 원문/검증자를 저장하지 않고 SHA-256 해시·회원·challenge·60초 만료만 저장한다.
PKCE·ACTIVE 회원 확인과 단일 코드 소비·refresh 해시 저장은 한 트랜잭션이다. 잘못된 verifier는
유효한 코드를 소비하지 않으며 동시 교환은 한 요청만 성공한다. CSRF 예외는 exchange 경로만이다.
모든 인증 응답에 `Cache-Control: no-store`를 적용한다.

실 Google·디바이스 인증과 로컬 서명 OIDC fixture의 HTTP/DB 검사를 구분한다.
Flutter 실행법과 플랫폼별 제약은 [사용자 앱 안내](../clients/flutter/README.md)를 본다.
