# Android 공개 뉴스·환율 계약

테스트 작성 시작: 2026-10-28 09:09:39 UTC. 뉴스 목록·상세와 USD/KRW 조회의 원본 웹 계약을 대상으로 한다.
오늘 뉴스, 키워드, 시장 분석, 관리자, 거래 작성, 외부 제공자 호출은 이번 클라이언트 범위에 포함하지 않는다.
조정자가 인터페이스와 아래 계약을 동결했다. 테스트 작성과 실행 성공은 구별한다.

## 먼저 읽은 지식과 원본 근거

- `knowledge/wiki/projects/daynomy/news.md`, `stocks-exchange.md`
- `knowledge/wiki/packages/android-kotlin/types-and-json.md`, `numbers-and-money.md`, `dates-and-unicode.md`, `async-and-cancellation.md`, `errors-and-transactions.md`, `modules-and-testing.md`
- `spec/service.md` F03, F08
- `reference/2026-DAYNOMY-dev/frontend/src/features/news/newslist/{api.ts,types.ts,NewsListPage.tsx}`
- `reference/2026-DAYNOMY-dev/frontend/src/features/news/newsdetail/{api.ts,types.ts,NewsDetailPage.tsx}`
- `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts`
- `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/news/{controller/NewsController.java,service/NewsService.java,dto/NewsPageResponse.java,dto/NewsListItemResponse.java,dto/NewsDetailResponse.java,dto/ImageSourceResponse.java,dto/NewsSourceResponse.java}`
- `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/exchangerate/{controller/ExchangeRateController.java,service/ExchangeRateService.java,dto/ExchangeRateResponse.java}`

외부 검색은 사용하지 않았다. 원본·기존 테스트·프로덕션 코드는 테스트 작성 역할의 수정 대상이 아니다.

## 뉴스 응답

`GET /api/news?page=1&size=6`이 앱 기본값이다. 서버 기본 size=15와 구별한다.
전체 카테고리는 쿼리에서 생략하며, 선택 시 `&category=STOCK` 같은 서버 enum 이름을 보낸다.
서버는 page≥1, size=1..100을 검사한다. 서버 오류를 빈 목록으로 바꾸지 않는다.
응답은 `items,page,size,totalPages,totalElements,hasNext`이며 모두 필수다. 순서를 재정렬하지 않는다.
페이지 정수는 Int, 전체 개수와 ID는 Long으로 유지한다. 문자열 숫자·소수·overflow는 거절한다.
원본 뉴스 ID 검사는 Number.isInteger이고 종목의 positive safe integer 검사와 다르다.
뉴스 ID에 종목 전용의 양수·safe integer 제약을 자동으로 추가하지 않는다.

카테고리는 REAL_ESTATE, DEPOSIT_SAVINGS, STOCK, ECONOMY, ETF, BOND, PENSION,
FOREIGN_EXCHANGE, VIRTUAL_ASSET, GOLD의 열 가지다. ALL은 서버 enum이 아니다.
원본 서버가 지원하는 목록 필터는 REAL_ESTATE/STOCK/ETF이므로 화면에는 이 셋과 전체만 노출한다.
응답 디코더는 원본 웹처럼 열 가지를 허용한다.
목록 항목의 `id,title,category,imageUrl,publishedAt`은 필수다.
`imageUrl`과 `publishedAt`은 명시 null을 허용하지만 필드 누락은 오류다.
날짜는 원본 검증과 동일하게 문자열로 보존하며 장치 시간대로 변환하지 않는다.

`GET /api/news/{id}`는 발행 뉴스만 반환한다. 상세 필수값은
`id,title,category,publishedAt,content,sources`다. 상세 publishedAt은 null을 허용하지 않는다.
content가 문자열이면 `split('\n').filter(nonempty)`로 문단을 얻고, 문자열 배열이면 순서와 빈 문자열까지 보존한다.
imageUrl은 누락·null·문자열을 허용한다. imageSource는 누락을 허용하지만 명시 null은 원본 웹에서 오류다.
존재하는 imageSource는 name,url,author,license,licenseUrl 문자열과 NONE/AI_GENERATED/WIKIMEDIA/MANUAL type을 갖는다.
sources는 name,url 문자열을 갖는 배열이며 빈 배열도 정상이다. 알 수 없는 추가 필드는 허용한다.
모든 항목을 검사하며 일부 잘못된 항목을 조용히 버리거나 성공 빈 목록으로 바꾸지 않는다.

## 환율 응답

`GET /api/exchange-rates/usd-krw?date=...`의 date는 URLSearchParams에 해당하는 UTF-8 폼 인코딩을 사용한다.
입력 날짜를 클라이언트에서 수정하거나 오늘 날짜로 바꾸지 않는다. 날짜 범위 검사는 서버 책임이다.
원본 웹이 소비하는 값은 `baseDate:String, rate:number`이다. requestedDate, baseCurrency, quoteCurrency는 추가 필드다.
baseDate는 요청일과 달라도 보존한다. rate는 JSON 숫자이며 유한하고 0보다 커야 한다.
Kotlin은 JSON 십진 원문에서 BigDecimal을 만들며 Double 중간 변환으로 정밀도를 잃지 않는다.
숫자 문자열, null, boolean, NaN/Infinity, 잘못된 JSON 숫자 문법은 거절한다.
원본 JavaScript에서 0으로 underflow하는 1e-400은 거절하되 양수 5e-324는 허용한다.
미래·범위 밖·잘못된 날짜, 429, 404 등은 실제 HTTP 오류로 전달하며 자동 재시도하지 않는다.

## 오류·취소·수명

HttpTransport의 ApiException, IOException, CancellationException을 decoder 오류로 재분류하지 않는다.
성공 HTTP의 잘못된 JSON만 ResponseFormatException으로 변환한다.
UI에는 Loading, Ready(빈 결과 포함), Failed를 구분한다. 네트워크 응답/예외의 민감한 원문을 화면에 노출하지 않는다.
같은 영역의 이전 요청을 취소하고, 취소에 협력하지 않는 늦은 응답도 최신 상태를 덮어쓰지 못하게 한다.
뉴스 카테고리 변경은 page=1로 돌아간다. 상세 닫기는 목록의 카테고리와 페이지를 유지한다.
컨트롤러는 active=false/Idle로 생성한다. 최초 활성화는 현재 선택을 조회하고 같은 true 반복은 중복 요청하지 않는다.
비활성화와 close는 진행 중인 요청을 취소하며, 재활성화는 현재 선택을 다시 조회한다. close는 영구 종료다.
환율 입력이 blank면 Idle이며 요청하지 않는다. raw 날짜를 보존하고 유효성 판정은 서버로 전달한다.
화면의 환율 텍스트 편집은 요청하지 않고 조회 버튼이 controller.updateDate를 호출한다.

## 동결 인터페이스

`NewsCategory`, `NewsImageSourceType`, `NewsListItem`, `NewsPage`, `NewsSourceLink`,
`NewsImageSource`, `NewsDetail`, `NewsSource.list(category=null,page=1,size=6)`,
`NewsSource.detail(newsId)`, `NewsClient(HttpTransport)`를 사용한다.
`NewsDetail.content`는 정규화한 문단 List<String>이고 `NewsPage`는 hasNext까지 보존한다.
`NewsController(source,scope)`는 state, load, selectCategory, selectPage, openDetail,
closeDetail, retryList, retryDetail, setActive, close를 제공한다.
`NewsUiState`는 category/page/list/selectedId/detail을 갖는다.
`ExchangeRate(baseDate,rate:BigDecimal)`, `ExchangeRateSource.quote(date)`,
`ExchangeRateClient(HttpTransport)`, `ExchangeController(source,scope)`를 사용한다.
환율 컨트롤러는 state, updateDate, retry, setActive, close를 제공하며 state는 date/quote를 갖는다.

UI 태그: tab-market/tab-news/tab-exchange, news-list/news-item-{id}/news-back/news-detail,
news-next/news-previous/news-retry/detail-retry, category-ALL/category-{enum},
exchange-date/exchange-load/exchange-value/exchange-error/exchange-retry.
exchange-value는 실제 기준일과 정확한 십진 환율을 함께 표시한다.

## 실제 백엔드 검사 fixture

별도 조정자가 폐기 가능한 DB에 920001/920002 STOCK 발행 뉴스(동일 발행시각),
920003 ETF 발행 뉴스(더 오래된 시각), 920004 DRAFT, 920005 REJECTED를 생성한다.
STOCK size=1의 첫 페이지는 920002, 두 번째는 920001이다. 전체 공개 개수는 3이며 REAL_ESTATE는 빈 결과다.
초안·거절·없는 뉴스의 공개 상세는 404 NEWS_NOT_FOUND다.
환율은 요청일 2026-10-25, 실제 기준일 2026-10-23, rate=1423.123456의 저장된 캐시를 사용한다.
외부 환율 제공자 호출, 운영 DB, 원본 .env 사용 없이 실제 Kotlin→HTTP→Rust→DB 경로를 검증한다.
필수 환경 변수 누락 시 실패하며 skip이나 메모리 fixture로 대체하지 않는다.

## 완료 증거

테스트 작성·빈 구현 실패·구현·실제 실행·세 번째 에이전트 검증을 분리한다.
테스트 파일 해시는 `experiments/android-native/next/tests.json`에 고정한다.
JVM 검사, MockWebServer 기기 검사, 실제 Rust/DB 검사 결과를 서로 구분한다.
기기 실행 없이 Android 기능을 검증했다고 기록하지 않는다.
