# 첫 기능 명세: 비회원 피드백 등록

상태: 원본 정적 분석 완료 / 기존 Spring 서버·테스트 실행 미확인 /
Rust 첫 구현 및 명세의 로컬 검증 완료 (실행 기록: `runs/002-implementation.md`).
분석일: 2026-10-20 (Asia/Seoul). 원본은 `reference/2026-DAYNOMY-dev/`.
Git 이력이 없어 `reference-snapshot.json`의 파일 해시를 기준으로 한다.
코드/기존 테스트에 쓰인 사실과 이번 실험의 선택을 아래에서 구분한다.

## 포함·제외 범위

포함: `POST /api/feedback`, 이를 위한 `GET /api/auth/csrf`, JSON 검증,
앞뒤 공백 제거, PostgreSQL 저장, 공통 오류 응답.

제외: 관리자 피드백 CRUD, 회원/OAuth/JWT 전체 구현, UI, 다른 도메인,
운영 DB 이전, 배포, 스팸 방지·속도 제한 등의 신규 제품 기능.
브라우저 CORS/프록시/TLS 및 전체 Spring Security 호환성도 첫 로컬 실험의 완료 범위가 아니다.
CSRF는 공개 엔드포인트에도 적용되므로 생략하지 않는다.

## 원본 근거

아래 경로는 원본 저장소 기준이다. 줄 번호는 현재 스냅샷 기준이며 해시도 함께 보관한다.

| ID | 파일·위치 | 근거 |
| --- | --- | --- |
| S1 | `backend/src/main/java/org/grit/daynomy/feedback/controller/FeedbackController.java:17` | 경로, POST, @Valid, 204 |
| S2 | `backend/src/main/java/org/grit/daynomy/feedback/dto/FeedbackCreateRequest.java:6` | 필수값, 길이, 오류 문구 |
| S3 | `backend/src/main/java/org/grit/daynomy/feedback/service/FeedbackService.java:27` | 트랜잭션, strip 후 저장 |
| S4 | `backend/src/main/java/org/grit/daynomy/feedback/domain/Feedback.java:36` | 초기 PENDING |
| S5 | `backend/src/main/resources/db/migration/V25__create_feedbacks.sql:1` | 테이블, ID, 필수 열, 타임스탬프 |
| S6 | `backend/src/main/java/org/grit/daynomy/common/BaseEntity.java:11` | 생성·수정 시각 |
| S7 | `backend/src/main/java/org/grit/daynomy/common/exception/GlobalExceptionHandler.java:75` | 검증 오류 형식. 122행은 JSON 읽기 실패 |
| S8 | `backend/src/main/java/org/grit/daynomy/common/response/ErrorResponse.java:16` 및 `ValidationErrorField.java` | code/message/errors, field/reason |
| S9 | `backend/src/main/java/org/grit/daynomy/common/exception/CommonErrorCode.java:6` | INVALID_REQUEST, INTERNAL_SERVER_ERROR |
| S10 | `backend/src/main/java/org/grit/daynomy/config/SecurityConfig.java:42` | 쿠키 CSRF, 피드백은 예외 아님. 73행 permitAll |
| S11 | `backend/src/main/java/org/grit/daynomy/auth/controller/AuthController.java:41` | CSRF 조회 |
| S12 | `backend/src/main/java/org/grit/daynomy/auth/handler/RestAccessDeniedHandler.java:24` 및 `auth/exception/AuthErrorCode.java` | 403 FORBIDDEN |
| S13 | `backend/src/test/java/org/grit/daynomy/feedback/controller/FeedbackControllerTest.java` | 204·빈 입력 400. addFilters=false라 CSRF 증거는 아님 |
| S14 | `backend/src/test/java/org/grit/daynomy/feedback/service/FeedbackServiceTest.java` | 공백 제거·PENDING. Mock 저장이며 실제 영속성 증거는 아님 |
| S15 | `frontend/src/api/client.ts` 및 `frontend/src/features/feedback/api.ts` | CSRF 조회 → 쿠키 포함, 응답 headerName/token으로 POST |

Swagger 어노테이션은 확인했지만 별도 정적 OpenAPI 산출물은 찾지 못했다.
공통 응답/테스트 전략 ADR도 참고했다. 입력 오류 ADR은 템플릿 상태라 계약 근거로 삼지 않는다.
README에 피드백 V22라는 서술이 있으나 실제 SQL은 V25이다. 실제 파일을 기준으로 한다.

## HTTP 계약

### CSRF 준비

`GET /api/auth/csrf`는 로그인 없이 200을 반환한다. JSON에는 비어 있지 않은 문자열
`headerName`, `token`이 있어야 한다. 응답 쿠키와 이 토큰을 함께 사용해 POST한다 [S10–S15].
정확한 토큰 값이나 쿠키 속성 전체는 이 실험에서 바이트 단위로 비교하지 않는다.
토큰은 요청마다 고정 상수를 반환하면 안 된다. 원본의 cookie 기반 동작을 재현하되
제품 전체의 인증을 구현했다고 주장하지 않는다.

다음 경우 POST는 403, `{"code":"FORBIDDEN","message":"접근 권한이 없습니다."}`로 실패하며
저장하지 않는다: CSRF 정보 없음, 쿠키만 있음, 헤더만 있음, 쿠키/헤더 불일치.
CSRF 실패는 입력값 검증보다 먼저 처리한다 [S10,S12].
인수 검증은 JSON에 노출된 헤더명을 사용하므로 라이브러리 기본 이름을 추측할 필요가 없다.

### 피드백 등록

`POST /api/feedback`, `Content-Type: application/json`, 정상 CSRF, 인증 쿠키 없음:

```json
{"content":"  화면이 좋아요.  ","pagePath":"  /news/1  "}
```

- content: null/누락/빈 문자열/공백만 있는 문자열 불가, 최대 1000 [S2].
- pagePath: null/누락/빈 문자열/공백만 있는 문자열 불가, 최대 2048 [S2].
- @Size는 Java String 길이(UTF-16 코드 유닛) 기준이다. Rust UTF-8 바이트 수나
  Unicode scalar 개수로 세면 다르다. 예: 이모지 500개 = 1000, 501개 = 1002.
  JDK 21에서 이모지 길이 2를 직접 확인했으며, Spring validation 런타임은 아직 미실행이다.
- 길이는 **strip 전 원문**을 검사한다. 1000자 본문에 앞뒤 공백이 있으면 제한을 넘는다 [S1–S3].
- 통과하면 두 필드에 Java `String.strip()`과 같은 앞뒤 공백 정리를 적용한다.
  내부 공백/개행은 유지한다 [S3,S14].
- ASCII 공백·탭·개행 및 U+2003은 제거한다. U+00A0(NBSP)는 Java strip에서 유지된다.
  이 차이는 JDK 21에서 직접 확인했다. Rust trim()의 결과와 같다고 가정하지 않는다.
- pagePath에 URL/경로 패턴 제약은 없다. 반드시 `/`로 시작해야 한다는 검증을 추가하지 않는다 [S2].
- 성공은 정확히 204, 본문 없음. response envelope나 생성 ID를 반환하지 않는다 [S1].

### 실패 응답

입력 검증 실패는 400:

```json
{
  "code":"INVALID_REQUEST",
  "message":"요청값이 올바르지 않습니다.",
  "errors":[{"field":"content","reason":"피드백 내용을 입력해주세요."}]
}
```

| 필드·조건 | reason |
| --- | --- |
| content 필수/빈 값 | 피드백 내용을 입력해주세요. |
| content 길이 초과 | 피드백은 1000자 이하여야 합니다. |
| pagePath 필수/빈 값 | 작성 화면 경로가 필요합니다. |
| pagePath 길이 초과 | 작성 화면 경로는 2048자 이하여야 합니다. |
| 잘못된 JSON/비어 있는 본문 | field=requestBody, 요청 본문을 읽을 수 없습니다. |

오류 배열 순서는 비교하지 않는다. 입력값 자체를 오류에 되돌려주지 않는다 [S7–S9].
예상치 못한 저장 오류는 500 `INTERNAL_SERVER_ERROR`,
message=`서버 내부 오류가 발생했습니다.`이며 204로 숨기지 않는다 [S7,S9].

## 저장 계약

- 원본 V25의 `feedbacks` 테이블 구조를 사용한다. 기존 프로젝트의 전체 마이그레이션을 실행하지 않는다.
- 성공당 정확히 1행, 새로운 ID, 정리된 content/page_path, status=PENDING,
  비어 있지 않은 created_at/updated_at을 저장한다 [S3–S6].
- 실패는 행을 추가하지 않는다. 같은 요청 두 번은 각각 저장한다 (멱등성/중복 방지 없음;
  create/save 경로와 SQL의 유니크 제약 부재에서 도출).
- 앱 재시작 후에도 행이 남아야 한다. 인메모리 컬렉션으로 대신하지 않는다.
- 본문/경로/토큰은 로그에 기록하지 않는다. 원본은 ID와 이벤트만 기록한다 [S3].

## 불확실성 처리

| 항목 | 이번 상태 |
| --- | --- |
| 프레임워크 금지의 정확한 라이브러리 경계 | 개별 라이브러리 허용을 작업 가정으로 유지. 의존성 목록 공개 |
| 숫자→문자열 coercion, unknown field, 중복 JSON key | Jackson 실제 설정/런타임 추가 확인 전 완전 호환 주장 금지. 핵심 게이트에서 제외 |
| 모든 Unicode 공백·잘못된 surrogate | 위에 확인한 사례 외 완전 호환 미검증. 분석/테스트 없이 같은 의미라고 주장 금지 |
| 지원하지 않는 method/media type, CORS | 첫 기능 검증 범위 밖. 성공 응답으로 위장하지 말고 구현 선택을 기록 |
| 원본 실제 CSRF 응답/필터 실행 | SecurityConfig와 프론트 호출에서 도출. 원본 실서버 검증 미완료 |
| 저장 장애/재시작 | 계약에 포함. 첫 구현에서 별도 lifecycle 검증 실행 완료 |

근거를 더 찾으면 명세와 검증을 함께 갱신하고 변경 이유를 남긴다. 새로운 제품 요구사항은
임의로 만들지 않는다. 핵심 계약을 바꾸는 결정이 필요하면 해당 부분만 질문한다.

## 완료 기준

자동 인수 검증 (`scripts/acceptance.py`):

- CSRF 발급과 쿠키, 서로 다른 새 클라이언트의 토큰, CSRF 누락/불일치/쿠키 또는 헤더만 있는 요청
- 기본 저장, ASCII·Unicode 공백 정리, 내부 공백 보존, 경로 패턴을 임의로 제한하지 않음
- 각 필드의 누락/null/빈 값/공백/최대 길이/초과, 이모지 길이, strip 전 길이 검사
- 여러 필드 오류, 잘못된/빈 JSON 본문
- 성공마다 실제 PostgreSQL 행 내용·PENDING·시각·새 ID 확인, 실패 시 행 수 불변
- 동일 요청 반복 시 별도 행 생성

자동 검증 외 구현 에이전트가 증거를 남길 항목:

1. 서버 재시작 후 기존 테스트 행이 남는지 조회한다.
2. 전용 테스트 환경에서 저장 실패를 유발해 500과 거짓 성공 없음 확인.
3. 모든 자체 크레이트의 unsafe 금지와 직접 의존성의 프레임워크 여부를 코드 리뷰한다.
4. CSRF 토큰 생성/비교, 입력값 로그 노출 여부를 코드 리뷰한다.
5. 실행·DB 준비 방법과 실패/사람 개입 기록을 작성한다.

2026-10-20 첫 실행에서 1·2는 `scripts/check_lifecycle.py`로 재현했고,
3·4는 구현 에이전트가 코드 리뷰했다. 독립 리뷰 에이전트 검토는 하지 않았다.

인수 테스트 통과만으로 운영 보안·전체 API 호환성·서비스 전체 완성을 선언하지 않는다.
