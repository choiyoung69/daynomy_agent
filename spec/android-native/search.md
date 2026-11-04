# Android 네이티브 파일럿 — 종목 검색 계약

- 문서 작업 시작: 2026-10-28 08:06:39 UTC.
- 범위: 공개 종목 검색 → 결과 선택 → 최근 종가 기능에 선택 종목 전달. 거래 저장·인증·환율·전체 앱 이식 제외.
- 단계: 원본 정적 조사와 계약 초안. 이 문서의 사례는 독립 테스트 작성자에게 전달할 기준이며 테스트 실행 결과가 아니다. 구현·테스트·원본·서버 설정을 변경하지 않았다.
- 대상 연결: 현재 Rust `app/` API. 원본 Spring/웹 관찰과 Android 제안은 아래에서 구별한다. 문서만으로 Android 빌드·기기·HTTP/DB 호환 완료를 주장하지 않는다.

## 1. 원본에서 확인한 요청·응답

`frontend/src/features/stocks/api.ts`의 `searchStocks(keyword, signal?, country='KR')`는 다음 요청을 만든다.

```text
GET /api/stocks?q=<URLSearchParams로 인코딩한 keyword>
GET /api/stocks?q=<인코딩한 keyword>&country=US
```

KR이면 country를 생략한다. country는 대문자 KR/US이며 category 파라미터는 없다. 본문·CSRF 준비 요청은 없다. Spring SecurityConfig의 공개 조회 대상이며 웹 공통 request는 credentials include를 사용한다. 공통 request의 401 처리에는 refresh 후 원 요청 한 번 재시도가 있으나, 공개 조회 Android 파일럿에서 회원 인증 흐름을 구현하겠다는 의미는 아니다.

성공은 200 JSON 객체이며 빈 검색 결과도 성공이다.

```json
{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"}]}
```

웹 런타임 검증은 다음과 같다. 타입 선언만으로 보장하는 항목과 구별한다.

| 필드 | 실제 웹 검증 |
| --- | --- |
| stocks | 응답이 null이 아닌 object이며 stocks가 Array; 모든 행을 검증; 하나라도 잘못되면 전체 실패 |
| assetId | JSON number를 읽은 결과가 양의 safe integer, 최대 9,007,199,254,740,991 |
| assetCode / name | string; 빈 문자열도 허용 |
| category | 정확히 STOCK 또는 ETF |
| market | `String(value)`가 KOSPI, KOSDAQ, NASDAQ, NYSE, NYSE_ARCA, NYSE_AMERICAN, BATS 중 하나 |
| currency | 검증 없음. 타입 선언에는 optional KRW/USD. `stockCurrency`는 null/누락일 때만 `.US`로 끝나는 코드→USD, 나머지→KRW |
| 추가 필드 | 허용; 응답 배열 길이·중복 ID·국가와 market의 일치 여부 검사 없음 |

market의 `String(value)` 때문에 JSON 배열 `["KOSPI"]`도 통과할 수 있다. 이는 원본의 느슨한 경계 관찰이며 올바른 서버 DTO가 배열을 반환한다는 뜻은 아니다. currency가 `"EUR"`, 빈 문자열, 숫자 등이어도 searchStocks는 거절하지 않는다. DTO에 enum을 사용해 자동으로 거절하면 원본보다 강한 동작이다.

## 2. 서버 검증과 검색 방식

| 항목 | Spring 원본 코드 | 현재 Rust 코드 |
| --- | --- | --- |
| q 누락/빈 값/공백 | @NotBlank, 400 | 누락은 빈 문자열; trim().is_empty면 400 |
| 길이 | @Size(max=50), Java String UTF-16 단위; strip 전 | encode_utf16().count > 50 거절; trim 전 |
| 문자 조건 | `.*[\p{L}\p{N}].*` @Pattern | char::is_alphanumeric를 하나 이상 포함 |
| country | 기본 KR; KR/US 이외 400 | 누락/빈 값 KR; KR/US 이외 400 |
| 검색어 전처리 | Java strip 후 !→!!, %→!%, _→!_ | Rust trim 후 동일 이스케이프 |
| 검색 범위 | listed=true, STOCK/ETF, 선택 국가의 market | 동일 SQL 조건 |
| 국가별 market | KR: KOSPI/KOSDAQ; US: NASDAQ/NYSE/NYSE_ARCA/NYSE_AMERICAN/BATS | 동일 |
| 매칭 | lower(name/code) 부분 일치, LIKE ESCAPE '!' | 동일 형태 SQL |
| 순서 | 코드 완전 일치→이름 완전 일치→코드 접두→이름 접두→나머지; 이후 name ASC, id ASC | 동일 형태 SQL |
| 개수 | PageRequest(0,20) | LIMIT 20 |

완전 일치 순위 비교에도 이스케이프된 keyword가 사용된다. 특수문자가 있는 검색의 순위를 일반적인 원문 완전 일치라고 강화하지 않는다. DB collation과 lower의 언어별 결과는 이번 정적 조사만으로 전체 Unicode 일치를 보장하지 않는다.

오류: Rust의 잘못된 검색 입력은 400 `INVALID_REQUEST`, 일반 message와 errors 배열(field/reason)이다. q 오류의 field는 `q`이며 country 오류는 `country`다. 원본 StockControllerTest의 q 누락 기대 field는 `keyword`다. Android는 이 둘을 동일 필드명이라고 가정하지 않는다. 여러 조건을 동시에 위반할 때 Spring 오류 배열 순서는 고정하지 않는다. Rust는 빈 값→길이→문자 조건→국가 순으로 첫 실패를 반환한다. DB 실패는 Rust rows에서 500으로 변환된다. 검색 결과 없음은 404가 아니라 `{"stocks":[]}`다.

Rust query는 percent UTF-8 디코딩, `+`→공백, 동일 키의 첫 값 사용; 잘못된 percent/UTF-8은 400 query 오류다. Android 요청은 q를 한 번만 보내고 미리 percent 인코딩한 문자열을 다시 인코딩하지 않는다.

## 3. 원본 UI와 Android 적용 제안

웹 PortfolioTransactionEditor는 다음 동작을 한다.

- 선택 종목이 있거나 JS trim 결과가 비면 요청하지 않고 결과·오류·로딩을 초기화한다.
- 입력과 국가 변경 시 결과·오류를 비우고 로딩을 시작, 250ms 뒤 trim한 검색어로 요청한다.
- 이전 타이머와 요청은 취소한다. 결과·실패·finally 로딩 변경 전에 aborted를 확인한다.
- 주식/ETF/전체는 이미 받은 최대 20개 결과에 로컬 필터를 적용한다. 필터 변경은 새 요청을 만들거나 서버의 20개 한도를 각 유형별 20개로 바꾸지 않는다.
- 실패는 `검색 결과를 불러오지 못했어요.`와 다시 시도 버튼으로 표시한다. 빈 결과는 `검색 결과가 없습니다. 종목명이나 코드를 확인해 주세요.`다. 선택 시 해당 행의 식별자와 표시 데이터를 가격 기능으로 전달한다.

Android 제안: 검색어/국가/유형/선택/로딩/오류의 화면 상태를 한 소유자에서 관리하고 위 계약을 보존한다. 코루틴 취소와 실제 HTTP 호출 취소를 연결하며, 요청 세대 번호로 오래된 성공·실패·finally가 최신 상태를 덮지 않게 한다. CancellationException은 검색 실패 UI로 변환하지 않는다. 재시도는 사용자가 눌렀을 때 현재 검색어·현재 국가로 한 번 시작하며 자동 무한 재시도하지 않는다. 최종 상태 소유자·수명·화면 전환 계약은 조정자의 공통 UI 명세에 따른다.

### Unicode·공백을 구분할 기준

웹 UI는 JS trim 후 전송하고 API 함수 자체는 trim하지 않는다. Java는 strip, Rust는 trim, Kotlin 기본 trim은 같은 규칙이 아니다. 예를 들어 NBSP(U+00A0)는 JS/Kotlin/Rust trim에서 제거되지만 Java strip에서는 남는다. BOM(U+FEFF)은 JS trim에서 제거되나 Java strip/Rust trim에서 남는다. Rust trim은 NEL(U+0085)을 공백으로 처리하지만 JS trim은 보존한다. 따라서 `keyword.trim()`을 Kotlin에 그대로 옮겨 모든 경계가 같다고 주장하지 않는다.

Android UI 제안은 ECMAScript trim 문자 집합을 명시한 순수 함수를 써서 웹 UI와 같은 전송어를 만든다: U+0009–000D, U+0020, U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F, U+3000, U+FEFF. NEL은 보존한다. 입력 원문은 화면에 보존한다. NFC/NFKC 정규화·로컬 대문자화·중간 공백 축약은 추가하지 않는다.

길이는 Kotlin/JVM String.length가 UTF-16이므로 50단위 경계를 표현할 수 있다. 다만 원본 UI에는 maxLength/사전 정규식 거절이 없다. Android에서도 서버의 문자 검증을 재구현해 다른 Unicode 범위를 차단하지 말고 비공백 검색을 전송하며 400을 실패로 표시하는 것이 제안이다. Java regex의 dot은 기본적으로 줄바꿈 전체를 덮지 못하지만 Rust any는 줄바꿈 포함 문자열에서 문자/숫자를 찾는다. 이 차이는 서버 동작 차이로 남기고 클라이언트가 임의로 감추지 않는다.

## 4. 제안 Kotlin 경계 — 테스트 고정 전 조정 필요

아래는 책임 분리 제안이며 아직 컴파일 대상이나 확정 시그니처가 아니다. JSON 라이브러리의 enum 기본 디코딩에 전체 정책을 맡기지 않는다.

```kotlin
enum class StockCountry { KR, US }
enum class AssetCategory { STOCK, ETF }
enum class CategoryFilter { ALL, STOCK, ETF }
enum class StockMarket { KOSPI, KOSDAQ, NASDAQ, NYSE, NYSE_ARCA, NYSE_AMERICAN, BATS }
data class StockSearchItem(
    val assetId: Long, val assetCode: String, val name: String,
    val category: AssetCategory, val market: StockMarket,
    val currency: String // Normalized KRW/USD; malformed values use assetCode fallback.
)
interface StockSearchGateway {
    suspend fun search(keyword: String, country: StockCountry = StockCountry.KR): List<StockSearchItem>
}
// Pure helpers proposed: normalizeSearchKeyword(raw), buildSearchPath(keyword,country),
// decodeSearchResponse(json), filterSearchResults(items,filter).
```

ID는 Long 저장 + 1..9_007_199_254_740_991 범위를 적용한다. numeric JSON `1.0`/`1e0`은 JS number의 안전 정수 검사에서는 통과하므로 Long 리터럴 전용 파싱으로 거절하지 않도록 테스트한다. 문자열 `"1"`, null, boolean, 소수, 범위 초과는 실패다. 중간 Double 변환만으로 큰 원문 정수를 반올림해 허용하지 않도록 숫자 토큰의 정수성과 범위를 확인한다.

권고 Android 응답 정책: 필수 필드 누락/null/잘못된 타입 또는 unknown category/market이면 전체 FormatFailure. unknown JSON 프로퍼티는 허용. market은 JSON string만 허용하는 것으로 조정자가 확정했다. 원본 String(value) 강제변환과 구별되는 Android 방어 매핑이다. currency는 KRW/USD만 그대로 사용하고, absent/null/unknown string/숫자/boolean/배열/객체는 코드 접미사 기반 fallback으로 정규화한다. `.US`는 대소문자를 구분한다. 이는 조정자가 확정한 Android 방어 매핑이며, 잘못된 currency까지 원본과 동일하게 보존하는 동작은 아니다. 길이 21개를 클라이언트에서 자르거나 거절하는 동작은 기존 웹에는 없으므로 추가하지 않는 것을 제안한다. 서버 20개 제한은 서버 인수 사례로 확인한다.

HTTP 비성공은 HttpFailure(status, optional string code/message), 전송 실패는 TransportFailure, 성공 본문 JSON/형식 오류는 FormatFailure로 분리한다. 기존 UI 메시지로 통합 표시하더라도 진단 분류는 유지한다. 오류 본문이 없거나 HTML/깨진 JSON이어도 상태 기반 실패를 유지한다. 취소는 이 실패 분류에 넣지 않는다. 토큰·쿠키·원문 요청 본문을 로그에 남기지 않는다.

## 5. 독립 테스트 작성자에게 전달할 고정 사례

아래의 기본 JSON 행은 `assetId=1, assetCode="005930", name="삼성전자", category="STOCK", market="KOSPI", currency="KRW"`다. 실행 결과가 아니라 기대 기준이다. 정책 결정 표시가 있는 사례는 조정자가 확정한 뒤 테스트를 고정한다.

| ID | 입력/시나리오 | 기대 기준 |
| --- | --- | --- |
| S01 | 삼성, KR | GET path /api/stocks, q UTF-8 percent encoding, country 없음 |
| S02 | AAPL, US | q=AAPL, country=US; KR로 재전환하면 country 없음 |
| S03 | `A+B &삼성%_!` | decode한 q가 원문과 동일; +는 %2B, &는 %26, %는 %25; 서버 LIKE escape는 클라이언트가 하지 않음 |
| S04 | 빈 값/JS 공백만, 선택 종목 있음 | UI 요청 0회, 결과/오류/로딩 초기화 |
| S05 | `  삼성  ` / NBSP 삼성 NBSP / BOM 삼성 BOM | UI 원문 유지, 전송어는 삼성 (제안 JS trim 매핑) |
| S06 | NEL 삼성 NEL | 전송어 NEL 보존; Kotlin 기본 trim과 구별 |
| S07 | 50 UTF-16 q / 51 UTF-16 q, emoji 포함 | 서버 제한은 trim 전 UTF-16; Android UI가 사전 축약하지 않음. Rust 50은 다른 조건 충족 시 허용, 51은 400 |
| S08 | q 누락/기호만/country=JP | 서버 400; Rust field q/q/country; 원본 누락 field keyword 차이 보존 |
| S09 | 상장/비상장·채권·KR/US 혼합 DB fixture | 서버가 listed STOCK/ETF + 해당 국가만 반환; 최대 20, 원본 순서 보존 |
| S10 | 이미 받은 STOCK 2 + ETF 1, filter=ETF | ETF 1개 표시, 네트워크 추가 호출 0회; 전체로 돌아가면 원래 순서 3개 |
| S11 | `{"stocks":[]}` | 성공/빈 결과; 404로 취급하지 않음 |
| S12 | null/배열 최상위/{}/stocks:null/stocks:{} | 전체 FormatFailure |
| S13 | 한 정상 행 + 한 잘못된 행 | 전체 FormatFailure, 정상 행만 골라 표시하지 않음 |
| S14 | ID 1, 1.0, 1e0, 9007199254740991 | 안전 정수 허용; 0,-1,1.5,"1",null,true,9007199254740992,9007199254740993 거절 |
| S15 | name/code 빈 문자열, 추가 필드 | 허용; 필수 name/code 누락/null/숫자는 거절 |
| S16 | unknown category/market, market:null | 실패; market:["KOSPI"]는 원본 허용 가능/Android는 거절 (확정 방어 매핑) |
| S17 | currency missing/null; 코드 AAPL.US/005930 | fallback USD/KRW. unknown string/숫자/boolean/배열/객체도 같은 fallback (확정 방어 매핑); AAPL.us는 KRW |
| S18 | 서버가 21개/중복 ID/국가와 다른 market | 웹은 길이/중복/국가 검사 없음; Android에서 조용히 절단·중복제거·국가필터 추가하지 않는 제안 |
| S19 | A 요청 지연→B 성공→A 성공/실패/finally | 결과·오류·로딩 모두 B 유지, 이전 HTTP 취소 연결 |
| S20 | 대기 249ms→입력 변경, 국가 변경, 선택, 화면 정리 | 이전 timer/request 정리; 250ms 규칙과 최신 요청만 반영 |
| S21 | 400 JSON / 500 HTML / I/O failure / 200 invalid JSON / 204 | HTTP/HTTP/Transport/Format/Format; cancellation은 사용자 오류로 표시하지 않음 |
| S22 | 실패 후 다시 시도 | 현재 keyword/country 한 요청; 이전 오류 초기화, 자동 반복 없음 |
| S23 | 항목 선택 | 같은 assetId/code/name/category/market/currency를 가격 기능에 전달; stale 검색 응답으로 선택 변경 금지 |

## 6. 남은 결정과 검증 경계

1. 공통 Kotlin 패키지·파일 경로·HTTP/JSON 어댑터 시그니처는 조정자가 테스트 작성 전에 확정한다.
2. market 문자열 enum + currency 방어 fallback은 조정자가 확정했다. 독립 테스트에 malformed 응답의 원본과 Android 차이를 명시한다.
3. JS trim 문자 집합 매핑 제안을 공통 입력 정책으로 확정한다. 원본 서버 간 Unicode 차이 자체는 이 파일럿에서 변경하지 않는다.
4. 실제 서버의 검색 fixture/정렬/20개와 Android 요청 인코딩·취소·상태 반영은 이후 독립 테스트·통합 검사에서 확인한다. 이번 단계에는 DB/Gradle/기기 실행이 없다.

## 7. 근거 파일과 SHA-256

아래 해시는 이번 조사 종료 시 읽은 파일 bytes의 해시다. 모든 경로는 저장소 루트 기준이며 `reference/`는 읽기 전용 분석 근거다. 위키는 계약의 안내로 사용하고 API/검증 주장은 원본 코드와 대조했다. 해시가 같다는 사실만으로 의미 검증이나 실행 성공을 뜻하지 않는다.

```text
a8b49fa5a120365ae1328afb91aaabe77cca269c0dc24336f36d8a1c1e7b6f10  AGENTS.md
d1f01b2321d4914903ca1f3f9111cd2f418d6d84ac7060f3bc5342a3c530c516  README.md
bd4189b4ae61e779c10beb1eb933d23894385d9a7885aac1eba647384d6c4756  reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts
bf1e18b274488b6f7a9f15d8b10c3a9e78222e48adb49ca9e0ccc8f83d36627f  reference/2026-DAYNOMY-dev/frontend/src/features/stocks/types.ts
f2284ccc24c4394d02f3ae4db3e5c2a55af0754c066a5a254203d6e33dfca59e  reference/2026-DAYNOMY-dev/frontend/src/api/client.ts
abacd47444c919ddd4d732951084861d1722bdb1791c271ce5ec6f54ee20154c  reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/components/PortfolioTransactionEditor.tsx
4496cb9c934702d854cd11b375869658ae2a1020100e1668d5e7337ade16eb76  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java
9e951391d788b6820c55b1dfb8b7c42581174f07d361a2831fd13f22cdd672e1  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockSearchService.java
ec01b40445644f526966a2c995eb520ce1e08df37fc5548e9db3aedff987139f  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/repository/AssetRepository.java
671174806406830fe2ea3717488703ef9a460021ccc0e61d700d31072dbf4384  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/dto/StockSearchResponse.java
e36be1cc93d56266d998c678ddb1bdb587066092c9e7aa70599ed5b86f578ab2  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/dto/StockSearchItemResponse.java
3ae09aee4f01cf14502bf212faba9d1df13ca8eaf60052829c025bd8a3826ff3  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/domain/StockMarket.java
cd3bebc455c2c702c3fb2af82c32f63a67ff9f475266bcee817b6177b16b2bba  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/domain/Asset.java
65776d056d7198a6a3381ae21ea99ed0bd7df71b52cbb984165d483f5aba6545  reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/config/SecurityConfig.java
fb1a06ca083ad57a42fc8a679d995c9180d8577a7101c21283e4cb0580bdea87  reference/2026-DAYNOMY-dev/backend/src/test/java/org/grit/daynomy/asset/controller/StockControllerTest.java
0a33ded7ad202d1b2f0ab3e1ac1aca5743515bd98d41cd7c398deb535a62b994  reference/2026-DAYNOMY-dev/backend/src/test/java/org/grit/daynomy/asset/service/StockSearchServiceTest.java
72d0e5e6265c284ffed4b2e3f40eee593a5c77c48aea4d4d83caa6ae6f218f79  app/src/service_market.rs
d0eb5f514815abba8947ed459f89232555d7b971d276470ea2c11d600b676148  app/src/api.rs
706a51304f7404dd878a5fa809e5070104f5df914e3b4cfba703ce128131c7cf  knowledge/wiki/projects/daynomy/stock-search-price.md
c1b7d61eb1124f6e94b67817b7d6259b7742c1f3d363e850bdff2a6891f97817  knowledge/wiki/packages/android-kotlin/index.md
c65bfd46a9f7918f7b69f7d5efd197d330b3f9e21754686d6cb4da10d7a3ecca  knowledge/wiki/packages/android-kotlin/types-and-json.md
f95469cc81002bd139bfb1d9bef57209cfa8befb447ac0242a2c629f475d654e  knowledge/wiki/packages/android-kotlin/dates-and-unicode.md
80ae16b4f8c37fd75fdc66aa4ca6068d7132ae889a39141d4ff2a147bbb04ad9  knowledge/wiki/packages/android-kotlin/async-and-cancellation.md
039a422dc571102d5edaa49b423de31297d6481766644f9d6a63d6b364539606  knowledge/wiki/platforms/android.md
ace191323dac9dc5c197d7159dca589822cc3c6a06d8e40dc45ad2257b24652f  knowledge/wiki/shared/client-porting-baseline.md
d180bff29e9217ff8e951f9be327f142abc65811d59761f646b96ebd91fab57b  knowledge/wiki/shared/data-semantics.md
0ed58c961e6f954cbfefe2b0f3e3935de3bf72cf99b68a656f3ce52753bedcb1  knowledge/wiki/shared/error-retry-cancel.md
7945e60fa3ddb4ff837d5371c16353f688a88e912e59157174087f63f9919f09  knowledge/wiki/shared/testing-migration.md
```

문서 작업 종료 시각: 2026-10-28 08:10:11 UTC.
