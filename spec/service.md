# DAYNOMY Rust 백엔드 기능 명세 — 투자 리그 제외

작성: 2026-10-21, v0.1. 근거: `reference/2026-DAYNOMY-dev`의 프론트 경로·API 호출,
Spring Controller·요청 DTO·주요 Service·SecurityConfig.

**이 문서는 리그를 제외한 전체 기능의 범위와 1차 완료 기준이다.**
실제 Rust 구현이 완료됐다는 기록이 아니며, 전체 API의 모든 JSON 필드·오류 분기를
실서버로 확정한 상세 호환 명세도 아니다. 각 기능을 착수할 때 연결한 DTO·서비스·테스트로
필드·오류 코드를 확정하고 실제 요청 사례를 고정한다. 피드백은 [기존 상세 명세](feedback.md)를 따른다.

표기: **코드 확인**은 원본에서 관찰한 동작, **목표**는 Rust 구현·검증에 적용할 기준,
**결정 필요**는 원본만으로 제품 의도를 확정할 수 없는 부분이다. 원본 버그를 임의로 정답으로 만들지 않는다.

## 1. 포함·제외 범위

### 포함

| ID | 기능 | 이용자 | 주요 의존성 |
| --- | --- | --- | --- |
| F01 | Google 로그인·CSRF·토큰 갱신·로그아웃 | 비회원/회원 | Google OIDC, 회원, 토큰 저장소 |
| F02 | 내 정보·닉네임 변경·회원 탈퇴 | 회원 | F01 |
| F03 | 국내·미국 주식/ETF 검색·최근 종가·환율 | 공개 | 종목/가격/환율 데이터 |
| F04 | 포트폴리오 평가 계산 | 공개 | F03 |
| F05 | 내 보유자산·매수/매도·거래 수정/삭제·수익률 이력 | 회원 | F01, F03, 원장/스냅샷 |
| F06 | 포트폴리오 AI 분석·재사용·근거 갱신·분석 이력 | 비회원/회원 | F03–F05, 외부 AI/검색 |
| F07 | 투자 캘린더·경제 지표/실적 일정·보유자산 영향 | 비회원/회원 | F03, F05, 일정/과거 가격 |
| F08 | 발행 뉴스·오늘 뉴스·상세·키워드·시장 분석 | 공개 | 발행 뉴스 저장소 |
| F09 | 뉴스 검색·뉴스/인물 글/종목 자료 통합 검색 | 공개 | F08, F10 |
| F10 | 종목 관련 자료·공개 콘텐츠·주요 인물/게시물 | 공개 | 종목, 콘텐츠, 인물 저장소 |
| F11 | 비회원 피드백 등록 | 공개 | CSRF, DB — 기존 Rust 구현 있음 |
| F12 | 관리자 뉴스·이미지·종목 자료·인물·후보 게시물·피드백 관리 | 관리자 | F01, F08, F10, F11, 외부 API |
| F13 | 종목/가격·환율·거래일·일정·뉴스/인물 수집과 스냅샷 작업 | 시스템/관리자 | 외부 API, F03–F10 |
| F14 | 투자 캘린더 이메일 알림 설정·인증 | 회원 | 프론트에 존재, 원본 백엔드 구현은 확인되지 않음 — D06 |

메인 `/`의 포트폴리오는 유지한다. `/news`의 소식, 검색, `/stocks/:assetId`, `/people`,
`/mypage`, 관리자 화면을 지원하는 백엔드가 대상이다. 투자 캘린더는 독립 메뉴 리다이렉트와
별개로 소식 화면에서 API를 사용하므로 포함한다.

### 제외

- `/league`, `/league/profile`, `/league/portfolio`, `/league/following`, `/league/reviews`,
  `/league/:publicId`: 주간 리그·순위·투자자 공개 프로필·공유 포트폴리오·팔로잉·투자 회고/판단.
- `/portfolio/publication`: 공개 설정. `/portfolio/records`는 `/league/portfolio`로 연결되므로 함께 제외.
- `/membership`에서 리그로 이동하는 흐름, 마이페이지의 리그 프로필/팔로잉 연결.
- backend `league/`의 공개·내 리그·공유 포트폴리오·관리자 리그 API와 리그 전용 배치.
- UI 재구현·디자인·랜딩/약관/정책 페이지·카드 미리보기·클라이언트 분석 이벤트.
  리다이렉트 화면만을 위해 새 백엔드 API를 만들지 않는다.

주의: 리그 화면의 “공유 포트폴리오”와 메인 화면의 “내 포트폴리오”는 다르다.
메인에서 사용하는 보유자산·거래·수익률 API를 이름만 보고 제거하지 않는다.

범위 근거: [프론트 경로](../reference/2026-DAYNOMY-dev/frontend/src/App.tsx),
[상단 탭](../reference/2026-DAYNOMY-dev/frontend/src/features/navigation/ServiceHeader.tsx),
[포트폴리오 API 호출](../reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/api.ts),
[투자 캘린더 API 호출](../reference/2026-DAYNOMY-dev/frontend/src/features/investment-calendar/api.ts).

## 2. 공통 계약

- 목표: Rust, 웹 프레임워크 없이 구현한다. HTTP/JSON/DB/비동기 등 개별 라이브러리는 허용한다.
  자체 크레이트는 `#![forbid(unsafe_code)]`를 유지한다. 의존성 내부 unsafe까지 없다는 뜻은 아니다.
- 목표: 기존 클라이언트가 사용하는 HTTP 메서드·경로·JSON 필드·페이지 번호·null 의미를 보존한다.
  새 기능이 추가된 것으로 착각하지 않도록 경로 별칭과 버전 API를 기능 수와 구분한다.
- 코드 확인: `/api/admin/**`는 ADMIN, `/api/users/**`와 버전별 users 경로는 인증이 필요하다.
  `/api/portfolio/analysis`, `/api/portfolio/calculate`는 공개이며 그 밖의 `/api/portfolio/**`는 인증 대상이다.
- 코드 확인: 공개 API라고 CSRF가 모두 면제되지는 않는다. 비회원 POST 분석은 access 쿠키가
  없을 때만 특별 면제된다. 공개 POST 계산·캘린더·피드백은 유효 CSRF 조건을 준비한다.
- 목표: 인증·CSRF·요청 검증·업무 오류의 순서를 원본 보안 필터를 포함해 비교한다.
  “인증 없음=무조건 401”로 단정하지 않는다. 쓰기 요청은 CSRF가 먼저 거절할 수 있다.
- 코드 확인: 일반 오류 본문은 `code`, `message`, 필요할 때 `errors` 배열이며 빈 errors는 생략된다.
  세부 status·code·field/reason은 각 도메인의 ErrorCode와 실제 비교로 고정한다.
- 목표: 금액·환율은 원본의 십진수·소수 자릿수·반올림을 보존한다. 이진 부동소수점 오차를 허용 기준으로 삼지 않는다.
- 목표: 본인 데이터 격리, 변경의 원자성, 재시작 후 저장 유지, 실패 시 부분 저장 방지,
  동시 요청의 일관성, 토큰·개인정보·요청 본문 비노출을 검증한다.
- 날짜는 원본의 시간대와 경계 조건을 개별 확인한다. Java 시스템 기본 시간대, 서울, 뉴욕을 하나로 합치지 않는다.
- 피드백의 문자열 전용 content·중복 JSON 키 거절은 사용자 확정 정책이다.
  다른 API까지 같은 정책을 일괄 적용하는 것은 별도 결정이다.

근거: [SecurityConfig](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/config/SecurityConfig.java),
[ErrorResponse](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/common/response/ErrorResponse.java).

## 3. 기능별 동작과 인수 기준

### F01 — 인증·세션

- API: `GET /api/auth/google`, `GET /api/auth/csrf`, `POST /api/auth/refresh`, `POST /api/auth/logout`.
  Google 진입은 302로 `/oauth2/authorization/google`에 연결된다. OIDC 시작/콜백 처리도 필요하다.
- 코드 확인: Google 식별자로 회원을 조회/생성한다. 초기 공개 닉네임은 Google 실명에서 만들지 않는다.
  탈퇴 회원을 일반 회원으로 다시 활성화하지 않는다.
- refresh는 저장된 refresh 토큰 해시·서명·만료·회원 상태를 확인하고 이전 토큰을 지운 뒤 새 토큰을 발급한다.
  성공은 새 쿠키와 204다. 유효하지 않은 refresh는 쿠키를 지우고 오류를 반환한다.
- logout은 refresh를 무효화하고 쿠키를 삭제해 204를 반환한다. refresh가 없으면 삭제할 토큰이 없다.
- 인수 기준: 신규/기존 로그인, 잘못된 OIDC 응답, 만료·변조·재사용 refresh, 탈퇴 회원,
  로그아웃 후 refresh 실패, CSRF 정상/누락/불일치, 쿠키 속성·CORS를 검증한다.
- 미확정 세부: Rust의 OIDC 라이브러리·키/쿠키 환경별 설정은 구현 시 명시한다. 인증을 개발용 고정 회원으로 대체하지 않는다.

근거: [AuthController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/auth/controller/AuthController.java),
[TokenService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/auth/service/TokenService.java),
[MemberService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/member/service/MemberService.java).

### F02 — 내 정보·닉네임·탈퇴

- `GET /api/users/me`: `id`, `email`, `name`, `nickname`, `role` 반환. 본인 정보만 조회한다.
- `PATCH /api/users/me`: `{nickname}`. 앞뒤 strip 후 비어 있지 않아야 하고 최대 20자다. 중복 닉네임을 거절한다.
- `DELETE /api/users/me`: 회원 탈퇴 및 저장 refresh 토큰 제거. 기존 access 토큰·연관 데이터 처리도 비교 대상이다.
- **결정 필요 D01**: 원본의 정보 조회·닉네임 변경은 리그 공개 프로필의 표시명·중복 검사·동기화와 연결된다.
  리그를 제외한 신규 DB에서 회원 닉네임만 사용할지, 기존 공개명 호환 데이터를 남길지 결정해야 한다.
  임의로 리그 기능 전체를 구현하거나 조용히 기존 이름을 바꾸지 않는다.
- 인수 기준: 본인/다른 회원 격리, 빈 값·21자·중복·동시 닉네임 변경, 탈퇴 후 접근/refresh를 확인한다.

근거: [회원 요청 DTO](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/member/controller/dto/MemberUpdateRequest.java), MemberService.

### F03 — 종목·가격·환율

- `GET /api/stocks?q=&country=KR|US`: 이름/코드 검색, 국가 기본 KR, 최대 20개.
  q는 공백뿐이면 안 되고 최대 50자이며 문자/숫자를 하나 이상 포함해야 한다.
- `GET /api/stocks/{assetId}/price`: 저장된 최근 거래일 종가. 실시간 가격으로 표현하지 않는다.
- `GET /api/exchange-rates/usd-krw?date=YYYY-MM-DD`: 날짜별 환율과 실제 기준일을 반환한다.
  원본은 2000-01-01 이전·미래 입력을 제한하고 뉴욕 기준 어제까지만 외부 가격 기준으로 사용한다.
  원본의 날짜 fallback·캐시·조회 제한을 보존 대상으로 확인한다. 현재 제한은 인스턴스 전체 60초/120회다.
- 인수 기준: KR/US 검색·결과 없음·특수문자·잘못된 국가·없는 종목·종가 없음·휴장일,
  USD 종목·환율 fallback·외부 장애·캐시와 제한을 fixture로 고정한다.

근거: [StockController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java),
[ExchangeRateService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/exchangerate/service/ExchangeRateService.java).

### F04 — 포트폴리오 평가 계산

- `POST /api/portfolio/calculate`, 본문 `{holdings:[{assetId,quantity,averagePurchasePrice}]}`.
- holdings는 1~50개, 같은 assetId 중복 금지. ID/수량은 양의 정수다.
  평균 매수가는 최소 0.01, 정수 15자리·소수 2자리 이하다.
- 종목별 최근/직전 종가로 매입금액·평가금액·손익·수익률·비중·시장별 비중을 계산한다.
  USD 가격은 해당 기준일 환율로 KRW 환산한다.
- 가격/환율 없는 종목은 `priceAvailable=false`와 해당 평가 필드 null로 표시한다.
  `pricingStatus`는 `COMPLETE`, `MIXED_DATES`, `PARTIAL`을 구분한다.
  미평가 종목이 있으면 전체 손익/수익률을 임의로 완성하지 않는다.
- 일간 손익은 모든 가격과 직전 가격이 있고 현재·직전 날짜가 각각 일치할 때만 계산한다.
  금액/비율은 소수 2자리 HALF_UP이다. 계산 요청을 보유자산 저장으로 취급하지 않는다.
- 인수 기준: KR·US 혼합, 중복/0수량/51종목, 날짜 불일치, 가격/환율 누락,
  반올림 경계와 0 분모를 원본과 비교한다.

근거: [PortfolioCalculationService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/service/PortfolioCalculationService.java),
[계산 DTO](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/dto/PortfolioCalculateRequest.java).

### F05 — 내 포트폴리오·거래 원장·수익률

- `/api/users/me/portfolio` 및 `/api/portfolio`는 같은 기능의 경로 별칭이다.
- 조회: holdings와 누적 실현손익을 반환한다. 아직 포트폴리오가 없으면 빈 결과다.
- 거래 등록: `POST .../transactions` → 201. `assetId,type,tradeDate,quantity,unitPrice,fee,tax,exchangeRate?`.
  type은 BUY/SELL, 거래일은 과거/오늘, 수량 양수, 단가 최소 0.0001·소수 4자리,
  수수료/세금은 0 이상·소수 2자리, 환율이 있으면 양수·소수 6자리다.
- 거래 수정/삭제: `PATCH/DELETE .../transactions/{transactionId}`. 수정은 날짜·수량·단가·비용 등을 변경한다.
  assetId/type을 수정 가능한 필드로 새로 추가하지 않는다.
- 기존 `POST /api/v2/users/me/portfolio/transactions`도 같은 거래 DTO와 201 응답을 사용하며,
  거래·보유·과거 스냅샷의 단일 트랜잭션 처리를 별도 V2 서비스로 제공한다. D02의 유지 여부에 포함한다.
- 거래 원장을 재생해 보유 수량·평균가·실현손익을 다시 계산하며, 보유량 초과 매도를 거절한다.
  미국 거래의 환율 필수 조건·수수료/세금의 계산 방식은 원장 도메인을 기준으로 확정한다.
- 거래일은 해당 종목의 마지막 보유 등록/조정일 이후(당일 포함)여야 한다.
  거래 수정은 이전/이후 날짜 중 빠른 날짜부터, 삭제는 기존 날짜부터 스냅샷을 갱신한다.
- 보유 직접 수정/삭제: `PATCH/DELETE .../holdings/{assetId}`. 수량·원화 평균 매입가를 조정하고 이력을 남긴다.
- `GET .../performance?from=&to=`: 저장 스냅샷·오늘 현재 계산값·데이터 부족 상태를 구분한다.
  오늘 계산값을 조회만으로 저장하지 않는다. `GET .../histories`는 유효일·생성일·ID 역순의 이력이다.
- 인수 기준: 매수→추가 매수→부분/전체 매도, 비용·환율, 거래 수정/삭제 후 재계산,
  다른 회원 거래 접근, 동시 매도, 실패 시 원장/보유/스냅샷 롤백, 재시작 후 유지.
  `/histories`를 리그 화면에서 쓴다는 이유로 제거하지 않는다. 메인도 호출한다.

근거: [SavedPortfolioController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/SavedPortfolioController.java),
[SavedPortfolioService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/service/SavedPortfolioService.java),
[원장 계산](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/service/PortfolioLedgerCalculator.java),
[스냅샷](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/service/PortfolioSnapshotService.java).

### F06 — AI 포트폴리오 분석

- 공개 `POST /api/portfolio/analysis`: `{assets:[{assetName,weight,quantity?}]}`.
  최대 50개, 종목명 최대 100자, 비중은 0 초과~100, 선택 수량은 양수다.
  배열 전체 합계·빈 배열·중복 종목 규칙은 서비스 검증과 실제 사례로 확정한다.
- 비회원은 세션당 1회 체험. 회원은 요청 자산이 DB 저장 자산과 일치해야 하며 동일 기준 결과를 재사용한다.
- 회원 분석 `GET/POST /api/users/me/portfolio/analysis`:
  GET은 AI 호출 없이 저장 결과·현재 상태를 반환한다. POST는 생성 또는 재사용한다.
- `POST .../analysis/refresh`는 실제 검색으로 새 근거를 확인하는 별도 작업이다.
  동일 근거이면 기존 분석·생성 시각을 유지한다. 실패·불확실한 근거 때문에 이전 성공 결과를 잃지 않는다.
  동시 분석은 409다. 종목별 공통 분석 재사용도 포트폴리오 전체 결과 재사용과 구분한다.
- 상태: EMPTY/READY/PORTFOLIO_CHANGED/PROCESSING/RECHECK_REQUIRED/FAILED.
  `GET .../analysis/history`는 본인 최근 최대 10건이다.
- 기존 V1/V2 POST 경로도 목록에 포함한다. V2는 비중 상위 3개와 유효 분석 HIGH 최대 2개로 최대 5개를
  선별하고 빈자리는 비중순, 동률은 이름순이다. 제외 종목·부분 분석의 null 전체 점수를 보존한다.
  **D02**: 실험용 버전 경로 유지 여부는 사용자 선택 전까지 삭제 대상으로 간주하지 않는다.
- 인수 기준: 체험 소진, 회원 자산 불일치, 재사용 시 AI 호출 0회, 강제 근거 갱신,
  동시 요청, 일부 종목 실패·전체 외부 장애·timeout, 기존 결과 보존, 이력 제한, V2 선별 규칙.
  AI 문장 자체를 원본과 완전히 같게 비교하지 않는다. 구조·출처 검증·보존 정책은 결정적 fixture로 검사한다.

근거: [분석 Controller](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/PortfolioAnalysisController.java),
[저장 분석 Controller](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/SavedPortfolioAnalysisController.java),
[V2 Controller](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/v2/controller/SavedPortfolioAnalysisV2Controller.java).

### F07 — 투자 캘린더

- 회원 `GET /api/users/me/investment-calendar`, 비회원 `POST /api/investment-calendar`.
  공통 query: year=2000~2100, month=1~12, scope=PORTFOLIO(기본)/ALL.
- 비회원 본문 `{holdings:[{assetId,quantity}]}`: null 불가·최대 50개·각 ID/수량 양수.
  코드상 빈 목록 허용, 같은 자산은 첫 수량을 채택한다. 중복 거절로 바꾸려면 별도 결정한다.
- CPI·한국 기준금리·기업 실적 이벤트, 일정·이전/발표 수치·출처·보유자산 영향/과거 반응을 반환한다.
  READY/NO_PORTFOLIO/INSUFFICIENT_DATA를 구분한다. 전용 화면 리다이렉트와 기능 유무를 혼동하지 않는다.
- 인수 기준: 월/연도 경계, 회원/게스트 동일 보유 조건, ALL/PORTFOLIO 차이,
  빈 보유·이벤트 없음·과거 반응 데이터 부족·일정 시간대, 비회원 CSRF 검증.

근거: [회원 캘린더](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/investmentcalendar/controller/InvestmentCalendarController.java),
[공개 캘린더](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/investmentcalendar/controller/PublicInvestmentCalendarController.java).

### F08 — 뉴스와 뉴스 부가 분석

- `GET /api/news`: page 기본 1, size 기본 15(1~100), category 선택.
  PUBLISHED만 발행일·ID 내림차순으로 조회한다.
- `GET /api/news/today`: 서버 시스템 기본 시간대의 오늘 발행 뉴스 최신 최대 9개.
  **D03**: 배포 환경의 오늘을 서울로 고정할지 원본 환경 시간대를 재현할지 확인한다.
- `GET /api/news/{id}`: 발행 뉴스 상세. 초안/거절 뉴스와 없는 ID는 공개하지 않는다.
- `GET /api/news/{newsId}/keywords`, `GET /api/news/{newsId}/market-analysis`: 키워드·시장 분석 조회.
  조회가 AI 생성 작업을 자동 시작한다고 가정하지 않는다. 데이터 없음의 응답은 기존 서비스/테스트로 확정한다.
- 인수 기준: 발행/초안/거절 구분, 페이지 경계·카테고리, 발행일 동률, 자정 경계,
  없는 ID·분석 없음, 상세의 출처·이미지·관련 종목 필드 보존.

근거: [NewsService](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/news/service/NewsService.java),
[KeywordController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/keyword/controller/KeywordController.java),
[MarketAnalysisController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/market/controller/MarketAnalysisController.java).

### F09 — 검색

- 뉴스 `GET /api/search/news?q=&category?=&page=1&size=20&sort=LATEST|RELEVANCE`.
  q는 문자/숫자 포함·최대 100자·공백만 불가, page≥1, size=1~100.
  모든 검색 단어가 제목 또는 본문에 포함돼야 하며 반복 공백·중복 단어·영문 대소문자를 정규화한다.
  `%`, `_`, `!`는 일반 문자다. 관련도는 제목 일치 단어 수 우선, 동률은 발행일·ID 역순이다.
- 통합 `GET /api/search/contents?q=&source=ALL&page=1&size=12`.
  뉴스·인물 글·저장된 외부 자료를 통합하고 출처 필터를 지원한다.
  같은 URL 자산 자료는 병합하고 인물 글과 겹치면 인물 글을 우선한다.
  날짜는 뉴스 발행일/외부 자료 등록일이며 동률은 종류·ID로 구분한다.
- 인수 기준: AND 검색, 공백·중복·대소문자·와일드카드 문자, 빈 결과·필터·페이지,
  같은 URL 중복·인물 우선, 정렬 동률, 비발행 뉴스 미노출.

근거: [뉴스 검색](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/search/controller/NewsSearchController.java),
[통합 검색](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/search/controller/ContentSearchController.java).

### F10 — 종목 자료·공개 콘텐츠·주요 인물

- `GET /api/assets/{assetId}/contents`: 종목에 연결한 내부 뉴스/외부 자료를 조회한다.
- `GET /api/contents?page=1&size=12`: 저장된 YouTube·Threads·X 자료, size=1~100,
  원문 게시일·등록일·ID 내림차순. 통합 검색의 날짜 기준과 혼동하지 않는다.
- `GET /api/people`: 주요 인물과 공개 게시물 목록. 리그 투자자의 공개 프로필과 다른 기능이다.
- 인수 기준: 없는 종목, 자료 없는 종목, 내부/외부 출처 구분, 공개 목록 정렬·페이지,
  인물 없는 경우·공개 게시물·프로필 URL·이미지·출처 필드 확인.

근거: [AssetContentController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/content/controller/AssetContentController.java),
[ContentController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/content/controller/ContentController.java),
[FeaturedPersonController](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/controller/FeaturedPersonController.java).

### F11 — 피드백

- `POST /api/feedback`: 문자열 content·pagePath, 유효 CSRF, 정상 204와 DB 정확히 한 행.
- 길이·strip·UTF-16·중복 키·오류·DB 장애·로그 비노출은 [feedback.md](feedback.md)가 상세 기준이다.
- 인수 기준: 기존 HTTP/DB 46개·재시작/장애 4개를 유지한다. 관리자 기능까지 구현됐다는 뜻은 아니다.

### F12 — 관리자

모든 API는 `/api/admin/**`, ADMIN 권한과 변경 요청 CSRF를 검증한다.

| 하위 기능 | 코드에서 확인한 작업 | 인수 기준 |
| --- | --- | --- |
| 뉴스 | 목록/상세/등록/수정/삭제, 발행/거절, 한국·미국 경제 뉴스 초안 생성 | DRAFT/PUBLISHED/REJECTED 전이, 공개 목록 노출, 없는 ID, 잘못된 전이, 생성 실패 |
| 이미지 | Wikimedia 검색/선택, 뉴스 이미지 생성·저장 | 검색·권리/출처 메타데이터·저장 URL, 업로드 실패 시 DB 일관성 |
| 종목 자료 | 등록/목록/삭제, YouTube/소셜 검색 | 종목 존재·URL·중복 등록·내부 뉴스 연결의 보호 규칙 |
| 주요 인물 | 목록/등록/수정/삭제, 인물 게시물 등록/삭제·검색 | 이름 중복·플랫폼별 URL 검증·기본 게시물 제목·이미지 선택 |
| 게시물 후보 | 인물별/전체 대기함, 즉시 수집, 단건/선택 일괄 승인·거절 | 승인 전 공개 금지, 중복 수집, 최대 100개 ID·중복 ID 정리·항목별 부분 성공 |
| 피드백 | 목록/상세/상태 변경/삭제 | 최신 생성일·ID순, page=1/size=15 기본, 허용 상태 enum, 저장 반영, 삭제 204 |

- 뉴스·관련 자료·인물의 입력 제약은 각각 AdminNews 요청 DTO, AssetContentRequest,
  FeaturedPersonRequest/PostRequest를 따른다. 원본에 없는 일반 파일 업로드 API를 추가하지 않는다.
- 게시물 후보 일괄 처리는 한 건의 실패 때문에 전부 성공/전부 실패로 축약하지 않는다.
  결과는 succeeded/failed와 항목별 식별자·오류 정보를 보존한다.
- 공통 인수 기준: 비회원/일반 회원 접근 차단, 관리자 정상, CSRF 누락/불일치,
  다른 인물의 후보/게시물 식별자 혼용, 외부 검색·이미지·수집 실패를 검증한다.

근거: 부록의 관리자 Controller 전체 및
[후보 일괄 처리](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/service/FeaturedPersonPostCandidateBulkService.java),
[피드백 서비스](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/feedback/service/FeedbackService.java).

### F13 — 동기화·배치·운영 데이터

- 관리자 수동 실행: 국내 종목 동기화, 국내 종가 동기화/최대 31일 백필, 미국 종목·종가 동기화.
  미국 종목은 주요 거래소 USD 보통주/ETF 대상이며 OTC·우선주·펀드·워런트 제외 조건이 있다.
- 스케줄 작업: 국내/미국 종목·가격, 거래일 달력, 환율, 투자 캘린더,
  한국/미국 뉴스 초안 생성, 인물 공식 게시물 수집, 포트폴리오 일별 스냅샷.
  활성 플래그·cron·서울/뉴욕 시간대·중복 실행·같은 데이터 재실행을 구분한다.
- 외부 연동: Google OIDC, 공공데이터 종목/가격, KRX 달력, EODHD 가격/환율,
  OpenAI 분석·검색·뉴스/이미지, YouTube, Wikimedia, S3 이미지 저장.
- 인수 기준: 외부 응답 fixture를 고정한 정상/빈 값/잘못된 값/시간 초과/429/5xx,
  재시도 상한, 중복 방지, DB 충돌/부분 실패, 완료 후 조회 API 반영, 재실행의 일관성.
- **D04**: 배치 실행 수단은 Rust 프로세스·OS 작업·배포 스케줄러 중 구현 시 선택한다.
  기존 Spring의 스케줄러·키·운영 데이터를 그대로 실행하지 않는다. 별도 실험 DB/외부 sandbox가 필요하다.

근거: `asset/service/*Scheduler.java`, `exchangerate/service/ExchangeRateSyncScheduler.java`,
`investmentcalendar/service/InvestmentCalendarDataSyncScheduler.java`, `news/service/*Scheduler.java`,
`person/service/FeaturedPersonPostCollectionScheduler.java`, `portfolio/service/PortfolioSnapshotScheduler.java`.

### F14 — 프론트에만 있는 캘린더 알림 기능

프론트 `notificationApi.ts`에는 다음 요청이 있지만, 원본 Java 전체의 HTTP mapping에서 대응 API를 찾지 못했다.
개발 기본 mock은 localStorage에 저장하고 `emailVerified=true`로 처리한다. 이를 실제 이메일 인증 완료로 옮기면 안 된다.

| 프론트 요청 | 의미 | 현재 확인 수준 |
| --- | --- | --- |
| GET `/api/users/me/investment-calendar-notification` | 내 알림 설정 조회 | 프론트 계약만 존재 |
| PUT 같은 경로 | 이메일·대상·시점·발표 전후 발송 설정 | 프론트 계약만 존재 |
| DELETE 같은 경로 | 알림 해지 | 프론트 계약만 존재 |
| POST `.../email-verifications` | 이메일 인증 요청 | 프론트 계약만 존재 |

대상 enum: PORTFOLIO/WATCHLIST/MAJOR_ECONOMIC. 시점 enum: SEVEN_DAYS_BEFORE/ONE_DAY_BEFORE/SAME_DAY_MORNING.
**D06 결정(2026-10-21 사용자 승인)**: 이번 Rust 구현에서는 보류한다.
구현한다면 이메일 소유 확인·코드 만료/재발송 제한·관심종목 데이터의 출처·발송 시간대·발송 중복 방지·실제 메일 공급자를
추가 명세해야 한다. 원본 백엔드에 이미 완성된 기능인 것처럼 이식·검증했다고 보고하지 않는다.

근거: [알림 API](../reference/2026-DAYNOMY-dev/frontend/src/features/investment-calendar/notificationApi.ts),
[알림 타입](../reference/2026-DAYNOMY-dev/frontend/src/features/investment-calendar/notificationTypes.ts).

## 4. 결정 대기와 상세화할 부분

| ID | 내용 | 영향과 진행 방법 |
| --- | --- | --- |
| D01 | 회원 닉네임만 유지 — 사용자 승인 완료 | 리그 기능·연결은 제공하지 않는다. 원본 SQL의 리그 테이블은 스키마 호환을 위해 남는다. |
| D02 | V1/V2 분석·V2 거래 경로와 별칭의 유지 | 코드에는 실제 존재. 실험 경로를 제품 필수로 볼지 결정 전 임의 삭제하지 않음. |
| D03 | “오늘 뉴스”의 배포 시간대 | 자정 경계의 조회 결과에 영향. 원본 실행 환경과 목표 설정 확인 후 사례 고정. |
| D04 | 배치·외부 서비스·배포 환경 | 실제 외부 통합·예약 실행·운영 배포 검증의 완료 조건. 로컬 fixture 통과와 구분. |
| D05 | 원본의 이상 동작·부족한 검증·JSON 자동 변환 | 증거·선택지·영향을 남겨 질문. 피드백의 정책을 다른 API로 임의 확장하지 않음. |
| D06 | 프론트 전용 이메일 알림 보류 — 사용자 승인 완료 | 이번 범위에서 제외한다. 이후 인증·발송 정책을 정한 뒤 별도 착수. |

이 문서에 기록된 미결정을 전부 먼저 답해야 다른 작업을 시작할 수 있는 것은 아니다.
각 작업은 결정된 부분을 진행하고, 해당 결정에 의존하는 부분은 `needs_decision`으로 분리한다.

## 5. 구현 순서와 완료 판정

제안 순서: **F03/F08/F10 공개 조회 → F09 검색 → F01/F02 인증 → F04 계산 → F05 원장/수익률
→ F07 캘린더 → F06 AI 분석 → F12 관리자 → F13 실제 동기화/예약**.
F11은 기존 회귀 검사를 유지한다. 필요한 관리자/수집 fixture 준비는 앞 단계와 함께 진행한다.
순서가 독립적인 조회·검색 작업은 분담 가능하고, 원장·인증·스키마를 동시에 충돌시키지 않는다.

각 기능은 다음 조건을 모두 만족해야 완료다.

1. 아래 API 목록과 원본 DTO·서비스·테스트에서 입력/출력/오류/DB 효과의 구체적 사례를 고정한다.
2. 구현과 별도 검토를 분리한다. 구현 역할이 기준을 완화해 통과시키지 못하게 한다.
3. 실제 HTTP 상태·JSON·DB 효과·재시작/장애·권한을 확인한다. 응답만 보고 저장 성공으로 계산하지 않는다.
4. 결정적 동작은 같은 fixture를 원본 Spring/Rust에 보내 비교한다. 생성 ID·시각 등의 값만 허용 범위로 정규화한다.
5. AI/외부 호출은 fixture 검사와 실제 sandbox 통합 결과를 구분한다. 키가 없으면 실통합을 미검증으로 남긴다.
6. 검증한 코드와 검토한 코드의 해시 일치, 독립 리뷰 승인, 미해결 질문 없음이 필요하다.

**기존 피드백용 `agent_workflow.py`는 Rust 소스 3개만 허용하고 검사도 피드백 전용이다.**
이 문서를 넘긴다고 다른 기능을 자동 구현할 수 있는 상태는 아니다. 다음 구현 전에 기능별
허용 파일·명세·인수 사례·DB fixture를 조정기에 연결해야 한다. 전체 서비스 구현·배포는 이번 문서 작성의 결과가 아니다.

2026-10-21 전체 구현 작업은 앱의 조정자·역할별 에이전트와 `scripts/service_gate.py`를 사용한다.
실제 코드·독립 검사·원본 비교·제공자 fixture·남은 차이는 `runs/010-three-hour-service.md`에 기록한다.
과거 피드백 조정기의 허용 범위를 자동으로 늘린 것은 아니다.

## 6. API 전체 목록

아래 목록은 원본 Java 전체에서 비리그 HTTP mapping을 전수 추출했다.
각 행은 Handler 1개이며, 같은 Handler의 경로 별칭은 같은 행에 적는다.
별표/정규식 추정이 아닌 실제 경로만 적었다. OIDC 프레임워크 경로는 F01에 별도로 포함한다.
권한 열은 URL 보안 규칙이며 CSRF 면제 여부를 뜻하지 않는다.

비리그 Controller **31개**, HTTP Handler **81개**, 경로 별칭 전개 시 **89개 메서드/경로 조합**이다.
리그 패키지의 Handler 20개는 제외했다. 이는 기능 81개 또는 전부 Rust 구현 완료라는 뜻이 아니다.
프론트 전용 알림 4개 요청은 백엔드 구현 목록에 섞지 않고 F14에 따로 표시했다.

### asset/controller/StockController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/stocks` | 국내·미국 주식·ETF 통합 검색 | 공개 |
| GET | `/api/stocks/{assetId}/price` | 국내·미국 주식·ETF 최근 종가 조회 | 공개 |

근거: [StockController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java).

### asset/controller/StockPriceSyncAdminController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/admin/stocks/prices/sync` | 국내 주식·ETF 종가 동기화 | 관리자 |
| POST | `/api/admin/stocks/prices/backfill` | 국내 주식·ETF 종가 백필 | 관리자 |

근거: [StockPriceSyncAdminController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockPriceSyncAdminController.java).

### asset/controller/StockSyncAdminController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/admin/stocks/sync` | 국내 주식·ETF 종목 동기화 | 관리자 |

근거: [StockSyncAdminController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockSyncAdminController.java).

### asset/controller/UsStockSyncAdminController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/admin/stocks/us/sync` | 미국 주식·ETF 종목 동기화 | 관리자 |
| POST | `/api/admin/stocks/us/prices/sync` | 미국 주식·ETF 종가 동기화 | 관리자 |

근거: [UsStockSyncAdminController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/UsStockSyncAdminController.java).

### auth/controller/AuthController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/auth/google` | Google 로그인 | 공개 |
| GET | `/api/auth/csrf` | CSRF 토큰 조회 | 공개 |
| POST | `/api/auth/refresh` | Access Token 재발급 | 공개 |
| POST | `/api/auth/logout` | 로그아웃 | 공개 |

근거: [AuthController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/auth/controller/AuthController.java).

### content/controller/AdminAssetContentController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/admin/assets/{assetId}/contents` | 종목 관련 자료 등록 | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents` | 종목 관련 자료 목록 조회 | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents/youtube-search` | YouTube 영상 검색 | 관리자 |
| GET | `/api/admin/assets/{assetId}/contents/social-search` | Threads·X 게시물 검색 | 관리자 |
| DELETE | `/api/admin/assets/{assetId}/contents/{contentId}` | 종목 관련 자료 삭제 | 관리자 |

근거: [AdminAssetContentController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/content/controller/AdminAssetContentController.java).

### content/controller/AssetContentController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/assets/{assetId}/contents` | 종목 관련 자료 조회 | 공개 |

근거: [AssetContentController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/content/controller/AssetContentController.java).

### content/controller/ContentController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/contents` | 소식의 공개 외부 자료 목록 | 공개 |

근거: [ContentController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/content/controller/ContentController.java).

### exchangerate/controller/ExchangeRateController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/exchange-rates/usd-krw` | USD/KRW 날짜별 환율 조회 | 공개 |

근거: [ExchangeRateController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/exchangerate/controller/ExchangeRateController.java).

### feedback/controller/AdminFeedbackController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/admin/feedbacks` | 피드백 목록 조회 | 관리자 |
| GET | `/api/admin/feedbacks/{id}` | 피드백 상세 조회 | 관리자 |
| PATCH | `/api/admin/feedbacks/{id}` | 피드백 상태 수정 | 관리자 |
| DELETE | `/api/admin/feedbacks/{id}` | 피드백 삭제 | 관리자 |

근거: [AdminFeedbackController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/feedback/controller/AdminFeedbackController.java).

### feedback/controller/FeedbackController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/feedback` | 피드백 등록 | 공개 |

근거: [FeedbackController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/feedback/controller/FeedbackController.java).

### investmentcalendar/controller/InvestmentCalendarController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/users/me/investment-calendar` | 월별 투자 캘린더 조회 | 회원 |

근거: [InvestmentCalendarController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/investmentcalendar/controller/InvestmentCalendarController.java).

### investmentcalendar/controller/PublicInvestmentCalendarController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/investment-calendar` | 비회원 월별 투자 캘린더 조회 | 공개 |

근거: [PublicInvestmentCalendarController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/investmentcalendar/controller/PublicInvestmentCalendarController.java).

### keyword/controller/KeywordController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/news/{newsId}/keywords` | 뉴스 키워드 조회 | 공개 |

근거: [KeywordController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/keyword/controller/KeywordController.java).

### market/controller/MarketAnalysisController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/news/{newsId}/market-analysis` | 뉴스 시장 분석 조회 | 공개 |

근거: [MarketAnalysisController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/market/controller/MarketAnalysisController.java).

### member/controller/MemberController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/users/me` | 내 정보 조회 | 회원 |
| PATCH | `/api/users/me` | 내 정보 수정 | 회원 |
| DELETE | `/api/users/me` | 회원 탈퇴 | 회원 |

근거: [MemberController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/member/controller/MemberController.java).

### news/controller/AdminNewsController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/admin/news` | 뉴스 등록 | 관리자 |
| POST | `/api/admin/news/generate/economy/korea` | 한국 뉴스 초안 생성 실행 | 관리자 |
| POST | `/api/admin/news/generate/economy/us` | 미국 뉴스 초안 생성 실행 | 관리자 |
| GET | `/api/admin/news/image-search` | Wikimedia Commons 이미지 검색 | 관리자 |
| POST | `/api/admin/news/{id}/generate-image` | 뉴스 이미지 생성 | 관리자 |
| GET | `/api/admin/news` | 관리자 뉴스 목록 조회 | 관리자 |
| GET | `/api/admin/news/{id}` | 관리자 뉴스 상세 조회 | 관리자 |
| POST | `/api/admin/news/{id}/publish` | 뉴스 발행 | 관리자 |
| POST | `/api/admin/news/{id}/reject` | 뉴스 거절 | 관리자 |
| PUT | `/api/admin/news/{id}` | 뉴스 수정 | 관리자 |
| DELETE | `/api/admin/news/{id}` | 뉴스 삭제 | 관리자 |

근거: [AdminNewsController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/news/controller/AdminNewsController.java).

### news/controller/NewsController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/news` | 뉴스 목록 조회 | 공개 |
| GET | `/api/news/today` | 오늘의 뉴스 조회 | 공개 |
| GET | `/api/news/{id}` | 뉴스 상세 조회 | 공개 |

근거: [NewsController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/news/controller/NewsController.java).

### person/controller/AdminFeaturedPersonController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/admin/people` | 주요 인물 목록 조회 | 관리자 |
| POST | `/api/admin/people` | 주요 인물 등록 | 관리자 |
| PUT | `/api/admin/people/{personId}` | 주요 인물 수정 | 관리자 |
| GET | `/api/admin/people/{personId}/posts/search` | 주요 인물 Threads·X 게시물 AI 검색 | 관리자 |
| DELETE | `/api/admin/people/{personId}` | 주요 인물 삭제 | 관리자 |
| POST | `/api/admin/people/{personId}/posts` | 주요 인물 게시물 등록 | 관리자 |
| DELETE | `/api/admin/people/{personId}/posts/{postId}` | 주요 인물 게시물 삭제 | 관리자 |

근거: [AdminFeaturedPersonController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/controller/AdminFeaturedPersonController.java).

### person/controller/AdminFeaturedPersonPostCandidateController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/admin/people/{personId}/post-candidates` | 승인 대기 중인 주요 인물 게시물 후보 조회 | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/collect` | 주요 인물 공식 프로필 게시물 즉시 수집 | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/{candidateId}/approve` | 주요 인물 게시물 후보 승인 | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/{candidateId}/reject` | 주요 인물 게시물 후보 거절 | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/bulk-approve` | 주요 인물 게시물 후보 선택 일괄 승인 | 관리자 |
| POST | `/api/admin/people/{personId}/post-candidates/bulk-reject` | 주요 인물 게시물 후보 선택 일괄 거절 | 관리자 |

근거: [AdminFeaturedPersonPostCandidateController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/controller/AdminFeaturedPersonPostCandidateController.java).

### person/controller/AdminFeaturedPersonPostCandidateInboxController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/admin/people/post-candidates` | 전체 주요 인물 승인 대기 게시물 후보 조회 | 관리자 |
| POST | `/api/admin/people/post-candidates/bulk-approve` | 전체 주요 인물 게시물 후보 선택 일괄 승인 | 관리자 |
| POST | `/api/admin/people/post-candidates/bulk-reject` | 전체 주요 인물 게시물 후보 선택 일괄 거절 | 관리자 |

근거: [AdminFeaturedPersonPostCandidateInboxController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/controller/AdminFeaturedPersonPostCandidateInboxController.java).

### person/controller/FeaturedPersonController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/people` | 주요 인물 목록 조회 | 공개 |

근거: [FeaturedPersonController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/person/controller/FeaturedPersonController.java).

### portfolio/controller/PortfolioAnalysisController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/portfolio/analysis` | 포트폴리오 분석 | 공개 |

근거: [PortfolioAnalysisController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/PortfolioAnalysisController.java).

### portfolio/controller/PortfolioController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/portfolio/calculate` | 포트폴리오 계산 | 공개 |

근거: [PortfolioController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/PortfolioController.java).

### portfolio/controller/SavedPortfolioAnalysisController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/users/me/portfolio/analysis/history` | 내 포트폴리오 분석 변경 이력 조회 | 회원 |
| GET | `/api/users/me/portfolio/analysis` | 내 포트폴리오 저장 분석 조회 | 회원 |
| POST | `/api/users/me/portfolio/analysis/refresh` | 내 포트폴리오 새 근거 확인 | 회원 |
| POST | `/api/users/me/portfolio/analysis` | 내 포트폴리오 분석 생성 또는 재사용 | 회원 |

근거: [SavedPortfolioAnalysisController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/SavedPortfolioAnalysisController.java).

### portfolio/controller/SavedPortfolioController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/portfolio`<br>`/api/users/me/portfolio` | 내 포트폴리오 조회 | 회원 |
| POST | `/api/portfolio/transactions`<br>`/api/users/me/portfolio/transactions` | 매수·매도 거래 등록 | 회원 |
| PATCH | `/api/portfolio/transactions/{transactionId}`<br>`/api/users/me/portfolio/transactions/{transactionId}` | 매수·매도 거래 수정 | 회원 |
| DELETE | `/api/portfolio/transactions/{transactionId}`<br>`/api/users/me/portfolio/transactions/{transactionId}` | 매수·매도 거래 삭제 | 회원 |
| PATCH | `/api/portfolio/holdings/{assetId}`<br>`/api/users/me/portfolio/holdings/{assetId}` | 보유자산 수정 | 회원 |
| DELETE | `/api/portfolio/holdings/{assetId}`<br>`/api/users/me/portfolio/holdings/{assetId}` | 보유자산 삭제 | 회원 |
| GET | `/api/portfolio/performance`<br>`/api/users/me/portfolio/performance` | 기간별 포트폴리오 수익률 조회 | 회원 |
| GET | `/api/portfolio/histories`<br>`/api/users/me/portfolio/histories` | 보유자산 변경 이력 조회 | 회원 |

근거: [SavedPortfolioController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/controller/SavedPortfolioController.java).

### portfolio/v1/controller/SavedPortfolioAnalysisV1Controller.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/v1/users/me/portfolio/analysis` | 포트폴리오 분석 V1: 종목별 가격 조회 및 기존 AI 분석 | 회원 |

근거: [SavedPortfolioAnalysisV1Controller.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/v1/controller/SavedPortfolioAnalysisV1Controller.java).

### portfolio/v2/controller/PortfolioTransactionControllerV2.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/v2/users/me/portfolio/transactions` | 매수·매도 거래 등록 V2 | 회원 |

근거: [PortfolioTransactionControllerV2.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/v2/controller/PortfolioTransactionControllerV2.java).

### portfolio/v2/controller/SavedPortfolioAnalysisV2Controller.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| POST | `/api/v2/users/me/portfolio/analysis` | 포트폴리오 분석 V2: 가격 일괄 조회 및 최대 5종목 선별 분석 | 회원 |

근거: [SavedPortfolioAnalysisV2Controller.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/portfolio/v2/controller/SavedPortfolioAnalysisV2Controller.java).

### search/controller/ContentSearchController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/search/contents` | 소식 전체 검색 | 공개 |

근거: [ContentSearchController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/search/controller/ContentSearchController.java).

### search/controller/NewsSearchController.java

| 메서드 | 경로 | 기능 | 권한 |
| --- | --- | --- | --- |
| GET | `/api/search/news` | 뉴스 검색 | 공개 |

근거: [NewsSearchController.java](../reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/search/controller/NewsSearchController.java).

### 추출 근거 보존

분석한 Controller의 상대 경로순 `경로:파일SHA256\n` 목록을 SHA-256한 값:
`4ddd7d4021c567b11494331fe0fe18b0f07fd800c390e43632e8ceec851f18d0`.
원본 코드가 바뀌면 다시 목록과 동작을 확인한다. 기존 `reference-snapshot.json`의 29개는 피드백 분석용이며 전체 기능 스냅샷으로 확대해 해석하지 않는다.
