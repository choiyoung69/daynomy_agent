# DAYNOMY WebView 검증 파일럿

2026-10-28 사용자 요청: 지식베이스 활용, 별도 테스트 작성 서브에이전트 → 다른 구현 서브에이전트 → 다른 검증 서브에이전트. 먼저 테스트를 실제 실패시키고 SHA256 기준을 보존한다. 구현자의 완료 보고로 검증을 대체하지 않는다.

## 범위와 연결

첫 동작 범위는 종목 검색 → 최근 종가 → 수동 단가다. 거래 저장·회원 로그인·OAuth·전체 서비스 화면·배포는 제외한다. 웹은 TypeScript ESM, Android WebView(min26/target35), iOS WKWebView(iOS15 이상) 호스트를 별도 `clients/webview/`에 구현한다. 기존 `clients/android/` 및 reference/ 원본은 수정하지 않는다.

웹은 동일 origin HTTP 서버에서 제공하고 `/api/`만 기존 Rust 백엔드로 프록시한다. 개발 주소는 http://127.0.0.1:18082 (Android emulator http://10.0.2.2:18082), 기본 Rust 대상은 http://127.0.0.1:18081 이다. HTTP 예외는 debug 로컬 전용이다. release는 설정된 단일 HTTPS origin만 허용한다. 번들 내 secret·실데이터·토큰 저장은 없다. 브리지가 필요하지 않은 기능이므로 특권 JavaScript 브리지를 제공하지 않는다.

## 근거

knowledge/wiki/projects/daynomy/stock-search-price.md S01–S13, knowledge/wiki/platforms/webview.md, knowledge/wiki/packages/webview/의 types-and-json, numbers-and-money, dates-and-unicode, async-and-cancellation, state-and-navigation, errors-and-transactions, auth-and-storage, modules-and-testing. API 의미의 최종 근거는 reference/2026-DAYNOMY-dev/frontend/src/features/stocks/{api,types}.ts 및 PortfolioTransactionEditor다. stock API 디코더는 원본 의미를 유지한다(market String 변환, currency 미검사/누락 fallback 포함). Android native 파일럿의 방어적 변경을 웹에 자동 복제하지 않는다.

## 공통 웹 인터페이스 (테스트 작성 전에 고정)

`web/src/market.ts`:
- export type Country = 'KR'|'US'; export type Category = 'ALL'|'STOCK'|'ETF'.
- Stock: assetId:number, assetCode:string, name:string, category:'STOCK'|'ETF', market:string, currency?:unknown.
- StockPrice: assetId:number, assetCode:string, name:string, baseDate:string, closePrice:number, currency?:unknown.
- export function decodeStocks(value: unknown): Stock[]; decodePrice(value: unknown): StockPrice; stockCurrency(stock: {assetCode:string,currency?:unknown}):unknown.
- export class MarketApi constructor(fetcher: typeof fetch = fetch); search(keyword:string,country:Country,signal?:AbortSignal):Promise<Stock[]>; price(assetId:number,signal?:AbortSignal):Promise<StockPrice>.
- export type MarketState: query:string, country:Country, category:Category, stocks:Stock[], selected:Stock|null, unitPrice:string, dirty:boolean, baseDate:string|null, searchStatus:'idle'|'loading'|'ready'|'error', priceStatus:'idle'|'loading'|'ready'|'error', searchError:string|null, priceError:string|null.
- export class MarketController constructor(api: Pick<MarketApi,'search'|'price'>, onChange:(state:MarketState)=>void, debounceMs:number=250); readonly state:MarketState; setQuery(string), setCountry(Country), setCategory(Category), select(Stock), clearSelection(), setUnitPrice(string), retrySearch(), retryPrice(), setActive(boolean), dispose():void; get visibleStocks():Stock[].
- setQuery/국가 변경은 즉시 이전 검색 타이머/네트워크를 취소하고 이전 응답(성공/실패/finally) 무시. 빈 JS trim 문자열/선택 중에는 검색 없음. 유형은 전체 최대20개 결과의 로컬 필터. 국가 변경은 선택/단가/dirty/날짜 reset. 선택 해제도 reset하고 현재 query 검색 재개.
- 선택 직후 종가 조회. UI는 >0만 자동 채움, 날짜 문자열 보존. API는 0/음수도 디코드하며 UI에서 거절. 단가 수동 편집과 삭제 모두 dirty=true. 늦은 성공/실패가 새로운 종목이나 수동 단가를 덮지 않음. 가격 실패/비양수는 날짜 null 및 수동 입력 안내. 수동 단가는 number 변환 없이 문자열 보존. 재시도는 사용자 행동에서만 한다.
- setActive(false)는 요청/타이머 취소와 세대 무효화, 초안 보존. true 복귀는 선택 가격 또는 검색 재조회. dispose는 영구 종료. 실제 fetch에 credentials:'include'와 signal 전달. 공개 API이므로 자동 인증 갱신은 구현하지 않는다.

웹 UI는 의미 있는 한국어 label/상태/빈 상태/오류와 재시도, 48px 조작 영역, safe-area와 입력 키보드/스크롤, 모바일/데스크톱 반응형을 제공한다. 사용자 데이터는 textContent로 표시해 HTML로 실행하지 않는다. pagehide/visibilitychange 수명과 연결한다. 로그인 미구현을 표시한다.

## 호스트와 검증

Android와 iOS는 URL의 scheme/host/effective port로 신뢰 origin을 비교한다. userinfo/다른 port/하위도메인/위장 hostname과 file/javascript/data/intent 탐색 거절. 내부만 웹에서 탐색하고 외부 https는 사용자 탭/활성화에서 OS 브라우저로 연다. 팝업 임의 허용·SSL 오류 우회·혼합 콘텐츠·토큰 복제 없음. back은 WebView history 우선. 오류/프로세스 종료는 사용자 재시도 제공. 회전/복원·입력·쿠키 동작을 구현/기기 검증 구분한다.

독립 테스트는 `clients/webview/web/tests/`, `clients/webview/tests/`만 테스트 작성자가 작성한다. 구현자는 이 폴더와 명세를 변경하지 않는다. TypeScript 6.0.2 로컬 컴파일러와 Node22 내장 test runner를 재사용할 수 있다. Node 실제 테스트 → 웹 실제 HTTP → Rust/로컬 DB → Android APK/에뮬레이터 → iOS build/device 순으로 근거를 구분한다. Xcode 부재 시 iOS 앱 빌드/기기 검증은 blocked로 기록하고 완료로 세지 않는다. 정적 검사나 Swift 순수 정책 실행은 WKWebView 실행 증거가 아니다.
