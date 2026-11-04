# Flutter 사용자 앱: 구현 전 고정 계약

작성 역할: `/root/flutter_tests` (구현과 독립). 작성일: 2026-10-28 KST.
사용자 요구: 테스트 작성 서브에이전트 → 다른 구현 서브에이전트 → 다른 검증 서브에이전트.
테스트 작성 단계에서는 `lib/`를 작성하지 않는다. 패키지 이름은 `daynomy_flutter`, 공개
테스트 인터페이스는 `package:daynomy_flutter/daynomy.dart`다. 실제 앱 내부 구성은 자유다.

## 근거와 제품 범위

`knowledge/contracts/stock-search-price.json` 전체 decoder fixture를 그대로 실행한다.
원본 frontend `src/api/client.ts`, `src/features/{stocks,portfolio,investment-calendar,
news,search,stock-content,people,feedback,pages}`의 API와 DTO를 읽고 사용자 endpoint를 고정했다.
백엔드 `config/SecurityConfig.java`, `member/controller/dto/MemberUpdateRequest.java`,
`investmentcalendar/controller/PublicInvestmentCalendarController.java`,
`portfolio/controller/PortfolioAnalysisController.java`, `content/controller/ContentController.java`,
`feedback/controller/FeedbackController.java`를 대조했다.

전체 사용자 앱은 검색·포트폴리오·뉴스·캘린더·내 정보 5개 탐색 항목을 제공한다.
관리자·리그·이메일 알림·배포는 포함하지 않는다. 회원 주 실행 환경은 Flutter Web same-origin
쿠키이며 Google OAuth는 서버 redirect다. 이후 사용자가 네이티브 로그인을 위한 서버 확장을
승인했다. Android/iOS는 `native-auth.md`의 외부 UA + PKCE 일회용 code 교환을 구현한다.
앱 쿠키는 메모리에만 보관하고 재시작 시 재인증한다. 실 Google/디바이스 검증은 별도다.

## 공개 인터페이스

- `ExactNumber(String lexeme)`: 유효한 JSON finite 숫자. `lexeme`는 원문 보존.
- `Object? decodeJsonExact(String)`, `String encodeJsonExact(Object?)`: 객체/리스트를 재귀 처리하고
  모든 JSON 숫자는 ExactNumber로 보존한다. 문자열 속 숫자/escape/키 중복은 변조하지 않는다.
  중복 객체 키는 FormatException으로 거절한다. int 입력도 encode 지원. double 금액은 사용하지 않는다.
- `int checkedId(Object?)`: int 또는 ExactNumber 중 양의 정수 1..9007199254740991만 허용.
  `1.0`/`1e0`은 수학적 정수이므로 허용할 수 있으나 소수·범위 밖·문자열·bool은 거절한다.
- `PriceQuote decodePrice(String)`: `assetId`, `assetCode`, `name`, `baseDate`,
  `ExactNumber closePrice`, `String currency`를 노출. 날짜는 원문 문자열이다.
  통화 누락/null/unknown은 `.US` 접미사면 USD, 아니면 KRW로 표시용 추론한다.
- `List<Stock> decodeStocks(String)`: Stock의 `assetId,assetCode,name,category,market,currency`.
  기존 API permissiveness(종가 0/음수, 달력상 잘못된 날짜 string)는 decoder에서 보존한다.
- `CancellationToken`: `bool get isCancelled`, `void cancel()`,
  `void onCancel(void Function() callback)`; 전송 계층이 실제 요청 취소에 연결해야 한다.
- `ApiRequest`: `String path,method`, `Map<String,String> headers`, `String? body`,
  `CancellationToken? cancel`, `bool credentials` (항상 true).
- `ApiResponse(int status,String body,{Map<String,String> headers = const {'content-type':'application/json'}})`.
- `abstract class ApiTransport { Future<ApiResponse> send(ApiRequest request); }`
- `ApiClient({required ApiTransport transport})`:
  `Future<String?> request(String path,{String method='GET',Object? body,bool csrf=false,CancellationToken? cancel})`.
  204는 null. non-2xx는 `ApiException` (`status`, `code`, `message`).
  변경 요청의 csrf는 토큰 GET 후 서버의 headerName을 사용하며 malformed CSRF는 쓰기 전 거절한다.
  401의 GET만 한 번 재시도: CSRF를 획득하여 refresh POST하고 concurrent refresh를 공유한다.
  실패 refresh/재시도 401은 무한 반복하지 않는다. 쓰기는 401/timeout/5xx에도 자동 재전송하지 않는다.
  이는 원본 자동 write retry보다 보수적인 클라이언트 정책이며 중복 거래 방지가 근거다.
- `AppRepository(ApiClient client)`:
  `Future<Object?> invoke(UserOperation operation,{Map<String,String> params=const {},Object? body,CancellationToken? cancel})`.
  경로/검색쿼리를 인코딩하고 응답 구조를 검증하여 exact JSON 객체/리스트를 반환한다.
  DTO 오류는 FormatException. 검색/종가는 위 전용 decoder로 검증하되 반환은 exact JSON이다.
- `SearchController(AppRepository repository)` extends ChangeNotifier:
  `void query(String)`, `void updateFilters({String? country,String? category})`,
  `Future<void> selectStock(Stock)`, `void setManualPrice(String)`, `dispose()`;
  getters `List<Stock> stocks`, `bool loading`, `Object? error`, `String priceText`.
  기본 KR/ALL, 250ms debounce. country는 요청 query, category는 결과 필터다.
  이전 전송을 취소하고 세대 검사로 늦은 완료도 무시한다. dispose 이후 notify하지 않는다.
  종가 응답 중 사용자가 가격을 편집했다면 같은 선택의 응답으로 덮지 않는다.
- `DaynomyApp({required AppRepository repository})`: MaterialApp 포함.
  초기 검색 탭, profile bootstrap으로 guest/member 구별. 화면 요소의 안정적 ValueKey는 widget 테스트를 참조한다.
- `abstract class NativeAuthBroker { Future<String?> authenticate(Uri authorizationUri,{required String callbackScheme}); }`
- `NativeAuthCoordinator({required ApiClient client,required NativeAuthBroker broker,required Uri baseUri,List<int> Function(int)? randomBytes})`:
  `Future<void> login()`. 기본 entropy는 암호학적 난수. 32 random byte의 base64url verifier,
  별도 24 byte 이상 state를 사용한다. 테스트용 randomBytes 주입은 재현성만 위한 것이다.
  콜백 scheme/host/path/포트/userinfo/state 및 code/state 중복을 확인하고 exchange POST한다.
  취소는 `NativeAuthException`의 `code == 'cancelled'`. 잘못된 callback은 exchange하지 않는다.
  origin은 HTTPS 또는 명시적 개발용 loopback/emulator HTTP만 허용한다.
- `MemoryCookieJar({DateTime Function()? now})`: `void accept(Uri origin,List<String> setCookieHeaders)`,
  `String headerFor(Uri target)`, `void clear()`. origin(host/scheme/port), Path 경계, Secure,
  Max-Age/Expires를 지키고 HttpOnly를 앱 HTTP 전송에 사용할 수 있다. 임의 Domain으로 누출하지 않는다.
  자동 cookie adapter가 실제 HTTP에서 이 jar에 연결되었는지는 검증 역할이 별도 확인한다.

## UserOperation 경로 계약

테스트의 routeCases가 고정한 명세다. params는 문자열이며 query 출력 순서는 자유다.
portfolio CRUD는 현행 unversioned 원장을 사용한다. V1/V2를 임의 선택하지 않는다.

| 영역 | 연산 |
|---|---|
| 검색 | stocks, price, exchangeRate, assetContents |
| 포트폴리오 | calculate, guestAnalysis, portfolio, createTransaction, updateTransaction, deleteTransaction, updateHolding, deleteHolding, performance, histories, savedAnalysis, generateAnalysis, refreshAnalysis, analysisHistory |
| 뉴스 | news, todayNews, newsDetail, newsKeywords, newsMarketAnalysis, searchNews, searchContents, contents, people |
| 캘린더 | guestCalendar, memberCalendar |
| 내 정보 | profile, updateProfile, withdraw, logout, feedback |

POST/PATCH/DELETE는 guestAnalysis도 CSRF를 전송한다. guest는 서버에서 면제이지만 회원 쿠키가
존재하면 보호되는 동일 URL이므로 토큰을 붙이는 것은 호환된다. query 검증은 year/month/scope,
date/from/to가 서버 계약에 맞는지 호출 전에 수행한다. asset/transaction/news ID는 checkedId 적용.

## 테스트가 증명하는 것과 별도 검증

| 고정 자동 검사 | 증명 범위 | 추가 검증이 필요한 범위 |
|---|---|---|
| exact JSON/21개 원본 fixture | 타입·숫자·ID·날짜 decoder | 모든 서비스 DTO 전수 parity |
| fake transport | 경로·body·CSRF·401 single flight·쓰기 재전송 금지 | 실제 브라우저 쿠키·OAuth·실서버 통신 |
| 34개 사용자 endpoint 사례 | 사용자 route/주요 응답 shape/실패 거절 | 실제 DB CRUD·서버 연산의 정확성 |
| SearchController | debounce·cancel·세대·dirty 가격 | 디바이스 실제 HTTP abort |
| widget | 5탭/검색/뉴스/게스트/피드백 로딩·빈·오류 | 전체 편집 폼 E2E/접근성·좁은 화면/실기기 |
| native auth coordinator/cookie jar | PKCE challenge/state/콜백 검증/취소/쿠키 격리 | 실제 외부 UA와 플랫폼 callback |
| `scripts/flutter_auth_acceptance.py` | 로컬 서명 Google fixture HTTP/DB·single-use/expiry/concurrency/CSRF | 실 Google 환경과 디바이스 |

검증 역할은 테스트 통과를 전체 앱 완료로 확대해서 보고하지 않는다. 실제 Rust HTTP/DB와
회원 거래 추가·수정·삭제·보유 변경·성과·분석·닉네임·탈퇴는 별도 확인하고 결과/미검증을 남긴다.
AI는 fixture 화면 검증과 실 제공자 호출을 구별한다. 네이티브 로그인 실환경 미검증을 숨기지 않는다.

백엔드 테스트의 DB 계약은 `mobile_auth_codes(code_hash,member_id,code_challenge,expires_at,created_at)`이다.
소비된 코드는 삭제 또는 consumed_at으로 표시할 수 있다. 원문 code/verifier는 저장하지 않는다.
기존 Google fixture 모듈은 `service_auth_provider_acceptance.py`이며 OIDCSuite/Browser/HTTP를
재사용한다. checker CLI는 `--base-url --database --jwt-secret-file --mock-control-url --output`이다.
독립 DB·기존 공유 DB 잠금 안에서 실행한다. 파일/HTTP/SQL 진단에 비밀 값을 출력하지 않는다.

핵심 사용자 widget 흐름을 추가 고정했다. 검색 선택 뒤 `holding-quantity`와 `price-input`을
입력하고 `holding-add`로 게스트 보유를 추가한다. portfolio의 `holding-<assetId>`를 확인하고
`guest-calculate`로 실제 클라이언트 요청 body를 검증한다. PARTIAL 응답은 `pricing-partial`로 표시한다.
회원은 검색에서 선택한 종목으로 `transaction-add`를 열고 `transaction-quantity`,
`transaction-unit-price`, `transaction-fee`, `transaction-tax`, `transaction-date`를 입력한다.
`transaction-submit` 후 서버 portfolio를 다시 조회한다. 이력의 `transaction-edit-<historyId>`,
`transaction-delete-<historyId>` 및 `transaction-delete-confirm`으로 PATCH/DELETE를 검증한다.
실제 DB 변화를 증명하는 테스트는 아니며 fake transport가 반환한 서버 응답을 UI에 연결하는 검사다.

백엔드 red 기준에서 table 부재가 모든 HTTP 사례를 가리지 않도록 reset은 존재하는 새 table만
정리한다. `mobile-code-durable-hash-schema`가 table/필드 존재를 독립적으로 요구하며, `issue()`의
SQL 검사도 제거하지 않는다. 이는 미구현 endpoint의 404와 schema 누락을 분리하기 위한 준비다.
