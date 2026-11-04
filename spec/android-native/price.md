# Android 네이티브 파일럿: 최근 저장 종가

상태: 문서화 단계 / 원본 정적 대조 / 독립 테스트·구현·Android 실행 전.
범위: 종목 검색에서 선택한 종목의 최근 저장 종가를 조회하고 거래 단가 초안에 연결한다.
거래 저장·환율·인증·동기화·외부 시세 제공자·배포는 이번 가격 기능의 범위가 아니다.
시간: 최초 UTC 계측 `2026-10-28T08:07:26Z`(조사는 이 시각 전부터 진행, 정확한 착수 시각 미계측).
작성 종료 UTC는 아래 기록에 둔다. 이 문서만으로 구현 또는 검증 완료를 선언하지 않는다.

## 원본에서 확인한 계약

근거 경로는 마지막 SHA-256 표와 연결된다. `F01` 등의 ID는 이 문서의 로컬 식별자다.

- GET `/api/stocks/{assetId}/price`, 요청 본문 없음. 선택 ID 1이면 정확히 `/api/stocks/1/price`다.
  국가·검색어·날짜 query를 추가하지 않는다. 공개 조회이며 이 GET을 위해 CSRF 발급/로그인을 요구하지 않는다.
- Java 컨트롤러는 `Long` 경로 변수이며 양수 또는 JS 안전 정수 어노테이션은 없다(B01).
  Rust는 `path_integer`로 i64 파싱 후 조회한다(R01/R02). 따라서 서버의 허용 범위와
  모바일/웹의 양의 안전 정수 경계는 동일한 검사가 아니다. Android는 선택/요청 및 응답 ID를
  `1..9_007_199_254_740_991L`로 제한하는 공개 클라이언트 계약을 제안한다.
  ID를 Double 경유로 절삭하지 않는다. JSON 문자열 ID는 거절한다.
- 성공 200은 객체이며 `assetId`, `assetCode`, `name`, `baseDate`, `closePrice`, `currency`를 반환한다(B02/R01).
  `assetCode`, `name`, `baseDate`는 API 클라이언트에서 문자열 타입이어야 한다. 빈 문자열은 원본 검사상 허용한다(F01).
  ID는 양의 안전 정수다. 필수 필드의 누락/null/다른 타입은 거절한다. 추가 필드는 무시한다.
- `closePrice`는 JSON **숫자**이고 JS Number 변환 결과가 finite여야 한다(F01).
  문자열 숫자, null, boolean, 배열/객체는 거절한다. `0`, `-1`은 이 디코더 검사를 통과한다.
  `1e400`은 유한 범위를 벗어나므로 거절한다. 유효 JSON이 아닌 NaN/Infinity 리터럴도 거절한다.
  가격 양수 조건은 화면 자동 채움 계층의 별도 검사다(F03).
- `baseDate`는 원본 웹 디코더에서 문자열 타입만 검사한다. `2026-02-30`, 빈 문자열도 API 타입 검사는 통과한다(F01).
  Java DTO는 LocalDate이고 정상 서버 출력은 날짜 전용 값이다(B02). 날짜를 Instant/타임존으로 변환하지 않는다.
  Android 디코더는 우선 원문 String을 보존한다. 엄격한 달력 검증은 원본보다 강화되는 정책이므로 자동 추가하지 않는다.
- Java DTO는 BigDecimal, 엔티티/DB 가격 열은 numeric(21,4)다(B02/B06/B07).
  엔티티 생성/동기화는 양수를 요구하지만, 조회 클라이언트 검증의 양수 보장과 혼동하지 않는다.
  Rust latest는 DB numeric을 JSON 숫자로 내보낸다. 최근 저장 행의 `base_date DESC LIMIT 1`을 읽으며,
  외부 제공자를 호출하거나 오늘 가격을 생성하지 않는다(B03/B04/R01). 휴일이면 과거 거래일이 정상이다.
- 저장 행이 없으면 404, `code=STOCK_PRICE_NOT_FOUND`, `message=주식·ETF 종가를 찾을 수 없습니다.`다(B03/B05/R01).
  종목 자체가 없거나 가격만 없어도 조회 경로에서 같은 오류다. 임의로 0 가격/성공으로 바꾸지 않는다.

정상 fixture 예시(실제 수집 데이터 아님):

```json
{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-10-27","closePrice":71000.1250,"currency":"KRW"}
```

## 숫자·날짜·통화의 Android 대응 제안

디코더는 원시 JSON에서 숫자 타입을 먼저 확인하고 그 숫자 토큰의 문자열을 BigDecimal로 읽는다.
BigDecimal(Double)이나 `closePrice.toDouble()` 이후 BigDecimal 변환은 금지한다. finite Double 범위 확인은
기존 웹의 수용 범위와 맞추는 검증용이며, 통과한 가격 저장·표시·자동 채움에는 그 Double을 사용하지 않는다.
`12345678901234567.1234`, `0.1000`, `1.25e2`를 정확한 십진 값으로 보존한다. 자동 채움은 `toPlainString()`을
권장하며 숫자 값은 바꾸지 않는다. 강제 2자리 반올림/단가 계산/거래 전송은 이번 범위에서 수행하지 않는다.
이는 기존 웹 number의 이진 부동소수 손실을 재현하는 대신 서버 십진 값을 보존하는 명시적 개선 제안이다.
DB의 4자리 제한을 모든 API fixture의 별도 디코더 제한으로 추가하지 않는다.

날짜는 String 그대로 화면에 표시한다. 기기 시간대 변경 시 `2026-10-27`이 다른 날짜로 이동하면 실패다.
달력 유효성 검사/정형 YYYY-MM-DD 강제는 현재 제안에 포함하지 않는다.

원본 `stockCurrency`는 `currency ?? (assetCode.endsWith('.US') ? 'USD' : 'KRW')`다(F02).
누락/null이면 `.US`(대소문자 구분) 끝 코드에 USD, 나머지 KRW를 적용한다. 명시 KRW/USD는 코드 추정보다 우선한다.
원본 API는 currency 타입/enum을 검증하지 않는다. `UNKNOWN`도 통과하며 비-null 값은 fallback하지 않는다는 한계가 있다.
조정자가 이번 파일럿에 확정한 방어적 대응은 **KRW/USD만 그대로 사용하고, 누락/null/알 수 없는 문자열/비문자열은
assetCode의 `.US` 끝 여부로 fallback**하는 것이다. 예를 들어 UNKNOWN + AAPL.US는 USD,
123 + 005930은 KRW다. 이는 원본의 unchecked currency 통과와 달라지는 명시적 대응이다.
가격 응답의 currency는 이 규칙으로 정규화한다. UI 선택 종목의 통화도 같은 공통 정규화 규칙을 사용한다.
가격 응답 ID가 요청 ID와 다르더라도 안전 범위 내이면 디코더에서 거절하지 않는다.
원본이 응답/요청 ID 일치를 확인하지 않기 때문이다. 늦은 응답 차단은 응답 ID 비교가 아니라
요청 시작 당시 선택 ID와 generation을 기준으로 수행한다.

## 연결 UI 상태와 수동 입력 보존

기존 F03에서 확인한 순서:

1. 선택 종목 없음 또는 기존 거래 수정이면 가격 요청 없이 loading=false/error 해제다. 데모 모드는 생략한다.
2. 새 종목 선택은 즉시 요청하고 loading=true/error 해제한다. 250ms debounce는 검색에만 있고 가격에는 없다.
3. 현재 응답이면 baseDate를 기록하고 가격<=0이면 실패 처리한다. 가격>0이어도
   `priceEdited`가 true 또는 단가 문자열이 비어 있지 않으면 그 단가를 보존한다.
4. 사용자가 단가를 변경하면 값이 다시 빈 문자열이 되더라도 priceEdited=true다.
   요청 중 `123.4000` 입력, 삭제, `0` 입력 모두 늦은 응답이 덮어쓰면 안 된다.
5. 실패는 `최근 종가를 불러오지 못했습니다. 거래 단가를 직접 입력해 주세요.`를 표시하고 직접 입력을 유지한다.
   조회 실패 때문에 종목 선택/수동 단가를 지우거나 입력을 잠그지 않는다.
6. `종목 변경` 명시 행동은 선택 해제, priceEdited=false, unitPrice='', priceBaseDate=''를 수행한다.
   이는 앞서 보고한 보존 규칙의 명시적 초안 reset 경계다. 다른 종목에 이전 가격을 자동 이월하지 않는다.
   이번 파일럿에서 조정자는 선택/국가 변경 시 새 종목의 가격 초안(unitPrice/edited/baseDate)만 reset하도록 확정했다.
   검색 상태와 가격 초안의 reset을 명시적으로 연결하며, 다른 거래 필드까지 지우는 범위 확장은 하지 않는다.
7. effect 정리는 AbortController.abort를 호출하고, 결과·오류·finally의 loading 변경도 aborted면 무시한다.

Android의 구체 상태 제안:

- 가격 상태는 Idle / Loading / Ready / Unavailable / Error로 구분하고 선택 assetId와 요청 generation을 함께 둔다.
  Unavailable은 404 STOCK_PRICE_NOT_FOUND이며 직접 입력 안내를 표시한다. 404 다른 코드, 비-2xx, 전송 실패,
  malformed payload는 Error로 보되 사용자 직접 입력은 모두 가능하다. 자동 재시도는 추가하지 않는다.
- 화면 상태 소유자는 하나이며 단가 초안 String과 수동 편집 플래그를 서버 가격 DTO와 분리한다.
  Ready의 최근 종가/기준일 표시와 편집 가능한 단가를 혼동하지 않는다. 사용자가 단가를 수정해도 조회 가격 표시는 가능하다.
- 새 요청/선택 해제/화면 닫기는 generation을 증가시키고 이전 Job 및 실제 HTTP 호출을 취소한다.
  Coroutine CancellationException은 일반 오류로 바꾸지 않는다. 취소가 협력적이므로 반환 시점에
  `active && generation == currentGeneration && requestedAssetId == selectedAssetId`를 확인한다.
- 성공·오류·finally 모두 같은 가드를 사용한다. A 실패/finally가 B의 오류/로딩을 덮어쓸 수 없다.
  단가 채움 판단과 상태 갱신은 같은 UI 직렬 흐름/원자적 상태 변환 안에서 실행한다.
- 선택 해제/닫기는 Idle, loading=false로 정리하고 이전 응답을 무시한다. 요청 시작 시 이전 기준일은 지우도록 제안한다.
  원본의 비양수 응답은 baseDate 설정 후 오류가 될 수 있다. Android는 실패 가격의 기준일을 숨기는 것이 제안이며 원본 관찰과 구분한다.
- 회전은 화면 상태 소유자가 유지되면 선택/단가/편집 플래그를 보존한다. 프로세스 사망 복원은 조정자의 앱 수명 계약에 따른다.
  이번 문서에서는 SavedStateHandle 저장 또는 영구 저장을 구현됐다고 가정하지 않는다.

## 공유 Kotlin 인터페이스 제안 (아직 고정 아님)

```kotlin
data class LatestPrice(
    val assetId: Long,
    val assetCode: String,
    val name: String,
    val baseDate: String,
    val closePrice: BigDecimal,
    val currency: String // KRW/USD: 알려진 값 외에는 코드 기반 fallback
)
interface LatestPriceSource {
    suspend fun latestPrice(assetId: Long): LatestPrice
}
```

HTTP 어댑터는 취소를 실제 호출로 연결하고 HttpFailure(status, code)/MalformedResponse/TransportFailure를 구분한다.
UI는 `selectStock`, `editUnitPrice`, `clearSelection`, `close` 사건과 상태를 소유한다.
순수 가격 모듈은 경로 생성·검증·정확한 숫자 디코딩·통화 정규화를 담당하고 Compose/HTTP 구현에 의존하지 않는다.
이 스케치는 제안이다. 이름·파일·직렬화 타입·오류 표현은 조정자가 공유 계약에서 고정하며, 독립 테스트는 고정 계약을 기준으로 작성한다.

## 독립 테스트 작성자에게 전달할 사례

| ID | 입력/사건 | 기대 결과 |
| --- | --- | --- |
| AP01 | assetId 1/최대 안전 정수 | 정확한 GET 경로, 본문/불필요 query 없음 |
| AP02 | 0/-1/최대+1, 문자열/소수/누락/null 응답 ID | 거절; 요청 ID는 네트워크 전 거절 |
| AP03 | 정상 JSON + 추가 필드 | 성공, 추가 필드 허용 |
| AP04 | 문자열 숫자/null/boolean/배열 가격, 누락 필수값 | malformed 실패 |
| AP05 | 0/-1 가격 | 디코더 성공, UI 자동 채움 실패/직접 입력 안내 |
| AP06 | 1e400/NaN/Infinity | 거절; finite 검증 생략 탐지 |
| AP07 | 12345678901234567.1234 / 0.1000 / 1.25e2 | BigDecimal 값 보존, 이진 float 경유 및 임의 반올림 없음 |
| AP08 | baseDate 2026-02-30 / 빈 문자열 / null | 앞 둘은 디코더 허용, null 거절; timezone 변환 없음 |
| AP09 | 통화 누락/null, AAPL.US / 005930, 명시 KRW인 AAPL.US | USD/KRW fallback, 명시 KRW 우선 |
| AP10 | currency UNKNOWN/숫자/객체 | 디코더 실패 대신 코드 기반 KRW/USD fallback; 원본보다 방어적으로 정규화 |
| AP11 | 404 STOCK_PRICE_NOT_FOUND / 기타 HTTP·네트워크·JSON 오류 | 미확보/오류 구분, 직접 입력 가능, loading 해제 |
| AP12 | 선택 A→B, B 성공 후 A 성공/실패/finally | B의 가격/기준일/error/loading만 유지 |
| AP13 | 요청 중 단가 123.4000 입력/삭제/0 입력 후 성공 | 입력 원문과 편집 플래그 유지, 덮어쓰기 없음 |
| AP14 | 이미 채워진 단가/기존 거래/선택 없음 | 기존 단가 보존; 뒤 둘은 요청 자체 없음 |
| AP15 | clearSelection/close 후 늦은 결과·오류 | 상태 변경 없음, 호출 취소, 취소 오류 안내 없음 |
| AP16 | 종목/국가 변경→재선택 | 새 종목 가격 초안의 단가·edited·기준일 reset 후 새 요청과 자동 채움 허용 |
| AP17 | 가격 로딩/404 상태에서 수동 입력 | 입력 활성, 로딩/오류 문구·접근성 확인 |
| AP18 | 화면 회전·복귀 / timezone 변경 | 정의한 초안 수명 유지, baseDate 하루 이동 없음 |
| AP19 | 요청 ID 1, 응답 ID 2(둘 다 안전 범위) | 원본처럼 디코더 허용; UI 반영은 요청 당시 선택 ID/generation guard |

실제 HTTP fixture 검사와 UI/기기 검사를 분리한다. 단위 디코더 성공을 실제 서버·DB 또는 Android 실행으로 세지 않는다.
테스트 작성자는 위키만 복제하지 말고 F01/F03/B01–B07/R01의 원문과 기대값을 대조한다.
이 단계에는 테스트 파일·구현 파일을 만들지 않았다. 서버/DB/Gradle/외부 시세 호출도 실행하지 않았다.
`python3 scripts/check.py preflight`는 종료 0(원본 29/29 및 도구 존재); 동작 검증을 수행하지 않는 준비 검사다.

## 확정 사항과 남은 조율

조정자 메시지로 확정: 숫자 JSON 원문→BigDecimal 및 finite Double 게이트, 임의 날짜 문자열 보존,
화면 계층의 양수 검사, 이상 currency의 코드 기반 fallback, 응답 ID의 안전 범위만 검증(요청 ID 일치 강제 없음),
삭제까지 포함한 수동 단가 편집 보존, 선택/국가 변경 시 새 종목 가격 초안만 reset.
이는 사용자 승인 범위를 구체화하는 조정자의 구현 선택이며 원본 관찰과 구분한다.

남은 조율은 공유 Kotlin 타입/함수/오류 인터페이스와 담당 파일, 실패 가격의 baseDate 표시,
회전/복귀/프로세스 복원 수명·재조회 정책이다. 조정자가 공유 계약에서 고정한 뒤 독립 테스트를 작성한다.
ID의 `1.0`, `1e0` 같은 정수 값 숫자 표기는 JS Number.isSafeInteger상 허용한다.
Kotlin 단순 longOrNull은 거절할 수 있으므로 값 기반 정수 허용을 권장한다.
안전 범위 밖 원문을 Double 반올림 후 허용하지 않는다. 아직 API 구현·테스트 파일은 작성하지 않는다.

## 조사 근거와 SHA-256

모든 경로는 저장소 루트 기준이며 reference는 읽기 전용으로 대조했다.

| ID | 경로 | SHA-256 |
| --- | --- | --- |
| F01 | `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts` | `bd4189b4ae61e779c10beb1eb933d23894385d9a7885aac1eba647384d6c4756` |
| F02 | `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/types.ts` | `bf1e18b274488b6f7a9f15d8b10c3a9e78222e48adb49ca9e0ccc8f83d36627f` |
| F03 | `reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/components/PortfolioTransactionEditor.tsx` | `abacd47444c919ddd4d732951084861d1722bdb1791c271ce5ec6f54ee20154c` |
| B01 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java` | `4496cb9c934702d854cd11b375869658ae2a1020100e1668d5e7337ade16eb76` |
| B02 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/dto/StockPriceResponse.java` | `75c6b490f0bc3209dbe6fc99b988e82de05860bf8d02a3ff6e04b87ef1de47bb` |
| B03 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockPriceService.java` | `c03786eabc892a3effcf4545a1d17a8a7c5a59821606f2e271bca6e2e71de8ff` |
| B04 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/repository/StockDailyPriceRepository.java` | `82098df76c1446d51cf1e07414b8277df543b3643089554b795e2ed67d59af9e` |
| B05 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/exception/AssetErrorCode.java` | `3af94a4827687f3b687000d7011efe45d59a7d26214aad8c338f033d6d3d2621` |
| B06 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/domain/StockDailyPrice.java` | `2f51ff7a657a9e6896dc3ef5b0a0ded8c343575b22da0ede0425f30450ef62bf` |
| B07 | `reference/2026-DAYNOMY-dev/backend/src/main/resources/db/migration/V51__preserve_us_stock_price_precision.sql` | `d444d505a861b897a5c0e2f255dcd5927d547c9c8740c5eed7b236ae8884cea1` |
| B08 | `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/config/SecurityConfig.java` | `65776d056d7198a6a3381ae21ea99ed0bd7df71b52cbb984165d483f5aba6545` |
| R01 | `app/src/service_market.rs` | `72d0e5e6265c284ffed4b2e3f40eee593a5c77c48aea4d4d83caa6ae6f218f79` |
| R02 | `app/src/api.rs` | `d0eb5f514815abba8947ed459f89232555d7b971d276470ea2c11d600b676148` |
| K01 | `knowledge/wiki/projects/daynomy/stock-search-price.md` | `706a51304f7404dd878a5fa809e5070104f5df914e3b4cfba703ce128131c7cf` |
| K02 | `knowledge/wiki/porting/stock-search-price.md` | `54f517cbf3e15a5ce48d9413e82f660e8b623457c437b82c48c2fb5d149af4ed` |
| K03 | `knowledge/wiki/platforms/android.md` | `039a422dc571102d5edaa49b423de31297d6481766644f9d6a63d6b364539606` |
| K04 | `knowledge/wiki/packages/android-kotlin/index.md` | `c1b7d61eb1124f6e94b67817b7d6259b7742c1f3d363e850bdff2a6891f97817` |
| K05 | `knowledge/wiki/packages/android-kotlin/types-and-json.md` | `c65bfd46a9f7918f7b69f7d5efd197d330b3f9e21754686d6cb4da10d7a3ecca` |
| K06 | `knowledge/wiki/packages/android-kotlin/numbers-and-money.md` | `bc5269fa0eef06744dae4117cf1c5e2d848f02e2d1d32196f152e6c4c9c8a36a` |
| K07 | `knowledge/wiki/packages/android-kotlin/dates-and-unicode.md` | `f95469cc81002bd139bfb1d9bef57209cfa8befb447ac0242a2c629f475d654e` |
| K08 | `knowledge/wiki/packages/android-kotlin/async-and-cancellation.md` | `80ae16b4f8c37fd75fdc66aa4ca6068d7132ae889a39141d4ff2a147bbb04ad9` |
| K09 | `knowledge/wiki/packages/android-kotlin/state-and-navigation.md` | `33d9a43b77cf761885cd5cfb72f6942100858e6193fb7d8f84a03c6906eca5f9` |
| K10 | `knowledge/contracts/stock-search-price.json` | `03fb14fe1c685b4737eafcb97c4d25aea8becfa07f49040cb87f3c4b937a4921` |

작성 종료 UTC: `2026-10-28T08:10:53Z`.
