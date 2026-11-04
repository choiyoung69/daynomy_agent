# DAYNOMY Rust 백엔드

웹 프레임워크 없이 Hyper로 요청을 분기한다. 자체 크레이트에는
`#![forbid(unsafe_code)]`를 적용한다. 의존성 내부의 unsafe까지 금지한다는 뜻은 아니다.

범위는 [전체 명세](../spec/service.md)의 F01–F13이다. 리그·UI·배포·이메일 알림(F14)은
제외한다. 구현 여부와 실제 검증 결과는 [이번 실행 기록](../runs/010-three-hour-service.md)에서
구분한다. 코드를 작성했다는 이유만으로 모든 외부 서비스 연결이 검증된 것은 아니다.

## Docker DB와 공통 개발 서버

원본 `reference/`에는 백엔드 DB용 `.env`가 없고 프런트엔드용 `.env.example`만 있다.
아래 구성은 새 로컬 실험 DB를 사용한다. PostgreSQL은 Docker에서, 공통 Rust API는
호스트에서 실행한다. Android와 다른 클라이언트가 같은 API를 사용할 수 있다.
Docker Desktop(Compose v2), Rust/Cargo, Python 3.11+, PostgreSQL 클라이언트 `psql`이 필요하다.

```sh
# 저장소 루트. Git 제외 .env에 임의 DB 비밀번호/JWT 키를 생성한다. 기존 파일은 보존한다.
python3 scripts/dev_backend.py init
# Docker DB 시작 → 기존 마이그레이션 → 선택한 합성 데이터 → Rust API 실행
python3 scripts/dev_backend.py start --seed
```

호스트 API는 `http://127.0.0.1:18109`, Docker PostgreSQL은 `127.0.0.1:55459`다.
Android 디버그 앱의 기본 주소도 `http://10.0.2.2:18109/`이므로 에뮬레이터에서 연결할 수 있다.
앱이 다른 서버로 실행 중이면 다음처럼 다시 연다.

```sh
adb shell am start -S -n org.daynomy.android/.MainActivity --es base_url http://10.0.2.2:18109/
# USB 실기기는 해당 기기에 포트 전달 후 localhost 사용
adb reverse tcp:18109 tcp:18109
adb shell am start -S -n org.daynomy.android/.MainActivity --es base_url http://127.0.0.1:18109/
```

기기가 여러 대면 `adb -s <serial>`로 대상을 고른다. DB 접속 정보는 서버에서만 사용한다.
`.env`는 커밋하지 않으며 `docker compose config` 등으로 비밀값을 출력하지 않는다.
이 실행 도구는 `.env`를 명령으로 실행하지 않고 단순 `KEY=value`(선택적 따옴표)로 읽는다.
변수 치환·여러 줄 값·줄 끝 주석은 지원하지 않는다. `.env.example`과 같은 형식을 사용한다.

`--seed`는 선택 사항이다. 삼성전자·Apple, 예시 종가, 합성 뉴스 1건, 예시 USD/KRW 환율을 넣는다.
화면에 로컬 샘플임을 표시하며 종가·환율 기준일은 **2026-11-03**, 환율 예시값은 **1400**이다.
최신 시장 데이터가 아니다. 뉴스 목록에서 샘플을 열거나 종목 이름/코드를 검색하고,
환율 화면에서 해당 날짜를 조회해 연결을 확인한다. 반복 seed는 기존 행·수정값을 보존한다.
`--seed` 없이 시작하면 새 DB는 비어 있다. 아래 공개 데이터 import를 사용할 수 있다.
Google 로그인·기존 전체 종목 동기화·AI는 별도 제공자 설정이 필요하다.
인증 우회나 고정 회원은 추가하지 않았고 예약 수집은 비활성화한다.

### 실제 공개 종목·뉴스를 로컬 DB에 넣기

```sh
# 위의 start 또는 prepare로 DB·스키마를 먼저 준비한 뒤 별도 터미널에서 실행
python3 scripts/import_public_data.py
```

국내 주요 KOSPI 종목 10개는 네이버 공개 차트의 종목명·일봉을, 미국 주요 종목 10개는
Yahoo Finance 공개 차트의 종목명·일봉을 저장한다. 전체 상장 목록 수집 도구가 아니다.
장중 가격을 종가로 저장하지 않도록 각 시장의 오늘 날짜는 제외한다. 최신 실시간 시세가 아닌
**제공자의 완료된 일봉 종가**이며, 소수는 기존 DB NUMERIC 자릿수로 저장된다.
이 공개 차트 URL은 버전이 보장된 공식 개발자 API가 아니므로 응답 변경 시 재확인이 필요하다.

뉴스는 [한국경제 공식 RSS](https://www.hankyung.com/feed)의 증권 피드 최대 50건이다.
제목·원래 발행시각·출처·원문 URL을 보존하며 기사 HTML의 `og:image`에서 대표 이미지 URL을 확인한다.
한국경제 이미지 CDN의 HTTPS 주소만 허용하고 원문 출처를 함께 저장한다. 기사 전문과 이미지 파일을
복제·재배포하거나 AI 기사로 바꾸지 않는다. Android가 원문 CDN의 대표 이미지를 불러온다.
대표 이미지가 없으면 기존 빈 이미지 표시를 유지한다. 개별 조회 실패는 별도로 집계한다.
기존 뉴스의 빈 이미지 URL만 채우려면 다음을 실행한다. 이미 지정된 이미지는 보존한다.

```sh
python3 scripts/import_public_data.py --news-images
```

Android 뉴스 상세에 출처와 원문 URL을 표시한다. RSS의 원래 날짜를 사용하므로 이후 날짜의
오늘 뉴스에 과거 기사를 억지로 표시하지 않는다.

모든 응답 검증 후 한 트랜잭션으로 저장한다. 종목 ID는 유지하며 종목코드/거래일로 갱신하고,
뉴스는 원문 URL로 중복을 방지한다. 위 seed의 알려진 합성 뉴스·합성 종가/환율만 식별해 제거한다.
원문 주소·응답 해시·수집시각은 `local_public_import_sources`와 Git 제외
`.local/public-data/`에 기록한다. 실제 데이터 import 후 `--seed`는 거절하므로
이후에는 `python3 scripts/dev_backend.py start`로 실행한다. import는 명시적으로 실행할 때만
최신 데이터를 가져오며 예약 실행은 추가하지 않는다.

기존 전체 종목/가격 수집은 위 `주요 설정`의 공공데이터·EODHD 키와 기존 `--job` 진입점을 사용한다.
기존 국내 종가 배치는 거래일 캘린더 준비와 제공자의 데이터 게시 시점도 필요하다.
전체 동기화의 일부 성공을 전체 종목·전체 거래일 검증으로 세지 않는다.

Ctrl-C는 API를 종료한다. Docker DB는 계속 실행되며 named volume에 데이터를 보존한다.
다음 시작은 `python3 scripts/dev_backend.py start`로 충분하다. DB까지 멈추려면 다음을 쓴다.

```sh
python3 scripts/dev_backend.py stop
# API를 실행하지 않고 DB·스키마만 준비할 때
python3 scripts/dev_backend.py prepare --seed
```

`compose.yaml`은 프로젝트 `daynomy-local`의 DB 하나만 관리한다. 기존 fixture의 DB와 분리한다.
`stop`은 데이터를 지우지 않는다. `docker compose down -v`는 데이터를 삭제하므로 일상 종료에
사용하지 않는다. 볼륨 생성 후 `.env`의 DB 비밀번호를 바꾸는 것만으로 DB 비밀번호가 바뀌지는 않는다.
포트 변경 시 `POSTGRES_PORT`와 `DATABASE_URL`을 함께 수정하고, `PORT`를 바꾸면 앱 API 주소도 바꾼다.
마이그레이션은 기존 loopback/`_test` 제한과 해시 검사를 그대로 사용한다.
과거 피드백 전용 DB나 임의 기존 DB를 이 구성에 연결하지 않는다.

Compose의 포트·healthcheck는 [Docker 문서](https://docs.docker.com/reference/compose-file/services/),
PostgreSQL 18 볼륨 경로는 [공식 이미지 안내](https://hub.docker.com/_/postgres)를 따른다.

## 기존 호스트 PostgreSQL로 로컬 실행

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
