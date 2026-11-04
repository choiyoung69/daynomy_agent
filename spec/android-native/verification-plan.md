# Android 네이티브 검색·최근 종가 독립 검증 계획

- 작성 역할: 구현과 분리된 테스트 작성·코드 검토 에이전트. 배정 모델 `gpt-6-astra`, 추론 `high`.
- 조사 시작: 2026-10-28 08:07:18 UTC.
- 문서 단계 종료: 2026-10-28 08:10:56 UTC.
- 상태: 원본 정적 대조 및 검증 계획 작성. Kotlin 테스트 작성·실행, Android 빌드·기기 실행은 아직 하지 않았다.
- 범위: 공개 종목 검색과 최근 저장 종가 조회, 조회 화면의 수동 단가 초안. 거래 저장·인증·배포·전체 앱 이식은 제외한다.
- 절차: 기능 문서와 공유 시그니처 확정 → 구현이 빈 상태에서 독립 테스트 작성 → 실제 red 실행 → 기준 해시 고정 → 구현 → 같은 기준으로 재검사 → 원본 대조 리뷰.
- 이 문서를 쓴 역할이 후속 테스트와 코드 리뷰도 담당한다. 구현 작성자와는 독립이지만 **자신이 작성한 테스트 기대값에 대한 별도 독립 검토는 아니다**. 조정자의 원본 대조와 이 한계 표기를 유지한다.

## 원본에서 직접 확인한 계약

| 근거 | 관찰 | 검증 경계 |
| --- | --- | --- |
| `frontend/src/features/stocks/api.ts` | `q`를 URLSearchParams로 인코딩; 기본 KR 생략, US 명시. 검색 배열 전체 원소 검사 | HTTP URI에서 값뿐 아니라 누락/추가 query 파라미터를 확인 |
| 같은 파일 | ID는 양의 JS 안전 정수, 이름·코드 문자열, category STOCK/ETF, market 허용 목록 | Kotlin Long 범위 전체를 허용하면 공개 웹 계약과 차이가 생김 |
| 같은 파일 | market을 `String(value)`로 비교함 | `["KOSPI"]` 같은 원본 강제 변환 허용은 엄격한 문자열 enum과 다름. Kotlin이 거절하면 의도적 경계 강화로 문서화 |
| 같은 파일, `types.ts` | currency는 API 검증 대상 아님; missing/null은 `.US` 접미사이면 USD, 그 외 KRW | 잘못된 통화 문자열·숫자 거절/대체를 원본 동작이라 주장하지 않음. 최종 파일럿 정책에 표시 |
| 같은 파일 | baseDate는 문자열만, closePrice는 유한 number만 검사 | 날짜 문법/양수 검사는 디코더의 원본 계약 아님 |
| `PortfolioTransactionEditor.tsx` 검색 effect | trim한 비어 있지 않은 검색어, 선택 없음 조건에서 250ms 대기; 변경·해제 때 타이머와 요청 취소 | API 클라이언트 자체 trim과 화면 trim을 혼동하지 않음 |
| 같은 파일 가격 effect/change/종목 변경 | 가격 <=0 오류, 현재 단가가 비어 있고 편집하지 않았을 때만 채움; 입력 후 지운 빈 값도 보존; 종목 변경은 편집 여부/단가/기준일 초기화 | 취소된 성공·오류·finally 모두 현재 상태를 바꾸면 안 됨 |
| 원본 `PortfolioTransactionEditor.test.tsx` | 수동 입력/삭제 보존, 이전 종목 늦은 응답 무시, 기존 거래 수정 시 조회 안 함, 닫을 때 abort | 소스 기대값 근거이며 이번 작업에서 원본 테스트를 실행한 결과는 아님 |
| Spring StockController/StockSearchService 및 Rust service_market | 상장 주식·ETF, KR/US 시장, 최대 20개, 검색어 제약/특수 LIKE 문자 escaping | 서버가 담당하는 계약. Android fixture 성공만으로 실제 DB 검색 보장 안 됨 |
| Spring StockPriceService/StockPriceResponse/AssetErrorCode 및 Rust latest | 저장 행 중 baseDate 내림차순 첫 행; 없으면 404 STOCK_PRICE_NOT_FOUND; JSON 숫자 가격·날짜 문자열 | 오늘 시세/외부 API 호출 아님. 최신 날짜를 실제 fixture DB로 증명 |

위 경로의 `frontend`/`backend`는 `reference/2026-DAYNOMY-dev/` 아래다. 지식베이스는 탐색에 사용했고 기대값은 위 원본과 직접 대조했다.
조사 시작 시 `search.md`와 `price.md`는 아직 없었다. 조정자가 다음 파일럿 선택을 확정했다. 최종 명세·시그니처와 대조한 후 테스트로 고정한다.

- market은 허용 enum의 실제 문자열만 허용한다. 웹 String 강제 변환 허용은 알려진 차이로 기록한다.
- currency는 KRW/USD만 사용하고, missing/null/잘못된 타입/알 수 없는 문자열은 assetCode 접미사 fallback을 적용한다. 이는 원본에 없던 방어 처리다.
- 날짜는 문자열 그대로, 가격은 finite JSON number를 유지한다. <=0은 API 허용/UI 오류로 분리한다.
- 응답 ID와 요청 ID 일치는 새 제약으로 추가하지 않는다. 안전 정수 ID와 요청 세대를 확인한다.
- 프로젝트: `clients/android/market-core` JVM, `clients/android/app` Compose. Kotlin 2.1.20, kotlinx.serialization JSON 1.8.1, coroutines 1.10.2, OkHttp/MockWebServer 4.12.0, JUnit 4.13.2, coroutines-test 1.10.2; Gradle 8.11.1, AGP 8.9.2, compile/target SDK 35, min SDK 26.
- 조정자 보고로 startup preflight 원본 29/29 통과. 이 역할이 별도 실행한 결과가 아니다.

## 고정할 디코더·요청 fixture

기존 `knowledge/contracts/stock-search-price.json`의 21개 응답 사례와 요청 2개를 원본 대조의 출발점으로 사용한다.
수정하지 않고 Android test resource로 복사하거나 읽기 전용 입력으로 사용하며 두 해시를 기록한다.
원본 수용 여부와 파일럿의 명시적 강화 정책을 서로 다른 기대값으로 표시한다.

| ID | 입력과 확인할 결과 |
| --- | --- |
| D01 | 정상 KR 주식/ETF, US 5개 시장과 KR 2개 시장; 순서/필드/빈 배열 보존 |
| D02 | stocks missing/null/object, 배열 원소 null/string, 응답 최상위 배열/null; 전체 응답 거절 |
| D03 | ID 1, 9007199254740991 허용; 0/음수/소수/문자열/null/missing/9007199254740992 이상 거절. `1.0`, `1e0`은 웹이 허용하므로 최종 Kotlin 숫자 정책과 대조 |
| D04 | code/name missing/null/숫자 거절; 빈 문자열은 원본 허용. category/market 알 수 없는 값 거절. market 배열 강제 변환 차이 별도 기록 |
| D05 | price 정상 소수 100.1234와 0/음수 디코더 허용, 문자열/null/missing/overflow 1e400 거절; API와 UI 양수 판단 분리 |
| D06 | baseDate 정상/윤일/휴일/임의 문자열/2026-02-30은 문자열 그대로 보존; null/missing/숫자 거절. 시간대 변환 금지 |
| D07 | 추가 필드는 허용. currency missing/null/정상/잘못된 문자열/비문자열의 최종 정책 및 .US 대소문자 접미사 fallback을 분리 검사 |
| D08 | `삼성 & ETF`, `AAPL`, `%_!+?#`, Unicode를 실제 URL query로 디코딩해 원문 동일 확인; KR country 생략·US 명시·UTF-8 확인 |
| D09 | latest URI에 선택한 ID 정확히 삽입; 공개 GET 이외 쓰기 호출/인증 갱신 없음 |
| D10 | 404 업무 오류, 400, 500, malformed JSON, 연결 실패/timeout은 실패 상태로 구별; 실패를 빈 검색 성공이나 가격 0으로 변환하지 않음 |

## 상태·경쟁 테스트

가상 시간을 지원하는 고정 coroutine scheduler와 제어 가능한 fake repository를 사용한다.
취소에 협력하는 fake만 쓰면 세대 검사 결함을 놓친다. 취소 후에도 성공/실패를 반환하는 fake를 별도로 사용한다.
단순 sleep 지연으로 테스트 성공 여부를 정하지 않는다.

| ID | 시나리오 | 기대값 |
| --- | --- | --- |
| S01 | 빈/공백 검색어, 이미 선택된 종목 | 새 검색 호출 없음, 결과/오류/로딩 초기화 |
| S02 | 검색 입력 후 249ms → 250ms 경계, 경계 전 재입력 | 이전 입력 호출 없음, 마지막 trim 입력 한 번 호출 |
| S03 | A 요청 중 B 입력, B 응답 후 A 늦은 성공 | B 결과 유지, A cancel 확인 |
| S04 | A 요청 중 B 요청 진행, A 늦은 실패/finally | B 로딩 유지·A 오류 노출 없음; B 완료 후 B 상태 유지 |
| S05 | KR 요청 중 US 변경, 동일 keyword 검색; 결과 선택 직전 검색 진행 | 올바른 국가 요청, 이전 국가/선택 전 검색은 결과·오류·로딩 갱신 금지 |
| S06 | 검색 실패 후 명시적 retry | 입력/국가 보존, 새 요청; 성공 또는 빈 결과로 전환 가능 |
| P01 | 선택 A의 양수 가격 응답 | 선택·가격·기준일 표시, 미편집 빈 단가에 한 번 자동 채움 |
| P02 | 요청 중 78000 입력 또는 입력 후 빈 문자열로 지움 | 응답 후에도 정확한 입력 문자열 또는 빈 값 유지, 편집 flag 유지 |
| P03 | 미편집이어도 단가가 이미 존재하는 초기 상태 | 응답으로 기존 단가 덮어쓰지 않음 |
| P04 | A 가격 진행 → 종목 변경 → B 선택/응답 → A 늦은 성공/실패/finally | B 단가/기준일/오류/로딩 유지, A 취소; A 편집 상태는 B 자동 채움을 막지 않음 |
| P05 | 0/음수 또는 404·네트워크·형식 실패 | 직접 입력 안내와 편집 가능 상태. 조회 실패를 성공 가격으로 표시하지 않음 |
| P06 | 기존 거래 수정 모드가 최종 API에 포함되는 경우 | 저장 단가 유지, 최신 종가 호출 없음. 파일럿 미포함이면 범위 제외로 표시 |
| L01 | dispose/close 후 늦은 검색·가격 성공/실패/finally | 모든 요청 취소, 이후 상태 방출/새 요청 없음 |
| L02 | 상태 저장/복원 모델이 최종 계약에 포함되는 경우 | 검색어/국가/선택/입력/편집 flag 보존; 진행 중 Job·Call 저장하지 않음 |

원본 가격 effect는 <=0을 확인하기 전에 기준일을 설정한다. 오류의 기준일 표시 정책을 바꾸면 파일럿 차이로 기록한다.
숫자 문자열 표시의 끝자리/지수 표기 차이는 승인된 표시 정책으로 고정하며, 금액 계산이나 반올림 정확성을 이 파일럿으로 주장하지 않는다.

## 실제 HTTP 및 Android 기기 검사

조정자가 모든 Gradle/DB 런타임 검사를 직렬로 실행하고 명령·종료 코드·XML 사례 수·skip·실패를 보존한다.

1. MockWebServer 등 실제 localhost 소켓과 실제 HTTP adapter로 UTF-8 URI/GET/status/JSON/요청 취소 연결을 검사한다. HTTP interceptor만 모의한 테스트와 구별한다.
2. 별도 실험 PostgreSQL과 Rust 서버를 기동한 환경에서 실제 Android 공유 repository/JVM HTTP adapter로 KR/US 검색, 검색 결과 없음, 선택 ID 최신 저장 종가 및 과거 날짜, 가격 없는 404를 검사한다. 두 날짜를 삽입 순서와 반대로 넣어 날짜 기준임을 확인한다.
3. 실제 서버에서 검색 결과 category/market/currency/ID와 가격 baseDate/closePrice를 fixture DB 기대값과 대조한다. Python curl만 성공한 결과를 Kotlin 연결 성공으로 표현하지 않는다.
4. 실제 에뮬레이터 또는 기기에서는 Compose 입력 → 대기 → 결과 → 선택 → 단가 표시, 빠른 입력/국가 전환, 수동 입력/삭제 보존, back/닫기, 회전/재생성, 앱 background/복귀를 검사한다.
5. 회전 시 검색어·국가·선택·수동 단가/편집 flag 유지와 불필요한 중복 요청 여부를 확인한다. 요청 중 회전과 요청 완료 후 회전을 나눈다. 프로세스 종료 후 복원은 명세가 별도로 보장할 때만 합격 기준으로 삼는다.
6. 화면 읽기 label/오류 연결, 큰 글자와 키보드 가림은 기기 수동 확인으로 기록한다. 실행 장치가 없으면 미검증으로 남긴다.

| 증거 단계 | 증명 가능한 범위 | 증명하지 못하는 범위 |
| --- | --- | --- |
| Kotlin 언어 예제 | 해당 예제의 언어 동작 | 앱 구현·Android 수명·화면 |
| JVM 디코더/상태 테스트 | 제품 core의 fixture/가상 시간·경쟁 동작 | 실제 기기 ViewModel 연결·Compose·OS 취소 |
| JVM 실제 localhost HTTP | HTTP adapter·socket·fixture 서버 연결 | Rust SQL/실제 기기 cleartext·네트워크 설정 |
| Rust HTTP + 실험 DB + Kotlin repository | 선택한 실제 API·DB 계약 | 기기 UI·전체 원본 호환·운영 |
| assembleDebug | Android 프로젝트 컴파일/APK 생성 | 설치·실행·회전·화면 인수 |
| connected/device 검증 | 해당 기기/OS와 시나리오 | 미실행 OS/모든 접근성·프로세스 경계 |

## 고정·리뷰·완료 판정

- 테스트 작성 전에 공유 타입/생성자/함수/상태 필드, module 경로, JSON·HTTP·coroutine·test 의존성 버전을 조정자가 확정한다.
- red 단계는 실제 컴파일 성공 후 기능 assertion 실패를 확보한다. 의존성 다운로드 실패/컴파일 오류만으로 올바른 red라 하지 않는다.
- 테스트·fixture·최종 명세·빈 구현 stub·빌드 파일 해시를 red 증거에 저장하고 구현자는 테스트를 수정하지 않는다.
- 테스트의 원본 해석 오류 발견 시 근거와 기대값 변경 이유를 먼저 기록하고 별도 검토 후 새 기준으로 다시 red/freeze한다. 과거 실패 기록을 바꾸지 않는다.
- 구현 후 같은 테스트 해시로 재실행하며 소스 해시를 검증 결과와 리뷰에 묶는다. 리뷰 후 수정되면 영향을 받는 검사를 다시 실행한다.
- 리뷰는 원본 의미, cancellation 전파/세대 guard, callback 완료·close, 상태 소유자, 수동 입력 flag, 응답 검증, 오류 표시, HTTPS/개발 cleartext 설정, test skip/약화 여부를 읽기 전용으로 확인한다.
- 실행 안 된 단계·실패한 검사·해시 불일치·미해결 리뷰를 완료로 바꾸지 않는다. JVM 성공과 Android 기기 인수를 별도 보고한다.

## 조사 시점 근거 SHA-256

전체 파일 기준이며 이후 파일 변경은 재검토 대상이다. 원본은 수정하지 않았다.

| 경로 | SHA-256 |
| --- | --- |
| `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts` | `bd4189b4ae61e779c10beb1eb933d23894385d9a7885aac1eba647384d6c4756` |
| `reference/2026-DAYNOMY-dev/frontend/src/features/stocks/types.ts` | `bf1e18b274488b6f7a9f15d8b10c3a9e78222e48adb49ca9e0ccc8f83d36627f` |
| `reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/components/PortfolioTransactionEditor.tsx` | `abacd47444c919ddd4d732951084861d1722bdb1791c271ce5ec6f54ee20154c` |
| `reference/2026-DAYNOMY-dev/frontend/tests/portfolio/PortfolioTransactionEditor.test.tsx` | `f8596a3d3965b307570626fdfea27c26924c054c5a6566597e76b30b9e395c60` |
| `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java` | `4496cb9c934702d854cd11b375869658ae2a1020100e1668d5e7337ade16eb76` |
| `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockSearchService.java` | `9e951391d788b6820c55b1dfb8b7c42581174f07d361a2831fd13f22cdd672e1` |
| `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockPriceService.java` | `c03786eabc892a3effcf4545a1d17a8a7c5a59821606f2e271bca6e2e71de8ff` |
| `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/dto/StockPriceResponse.java` | `75c6b490f0bc3209dbe6fc99b988e82de05860bf8d02a3ff6e04b87ef1de47bb` |
| `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/exception/AssetErrorCode.java` | `3af94a4827687f3b687000d7011efe45d59a7d26214aad8c338f033d6d3d2621` |
| `app/src/service_market.rs` | `72d0e5e6265c284ffed4b2e3f40eee593a5c77c48aea4d4d83caa6ae6f218f79` |
| `knowledge/contracts/stock-search-price.json` | `03fb14fe1c685b4737eafcb97c4d25aea8becfa07f49040cb87f3c4b937a4921` |
| `knowledge/wiki/projects/daynomy/stock-search-price.md` | `706a51304f7404dd878a5fa809e5070104f5df914e3b4cfba703ce128131c7cf` |
| `knowledge/wiki/platforms/android.md` | `039a422dc571102d5edaa49b423de31297d6481766644f9d6a63d6b364539606` |
| `knowledge/wiki/packages/android-kotlin/async-and-cancellation.md` | `80ae16b4f8c37fd75fdc66aa4ca6068d7132ae889a39141d4ff2a147bbb04ad9` |
| `knowledge/wiki/packages/android-kotlin/state-and-navigation.md` | `33d9a43b77cf761885cd5cfb72f6942100858e6193fb7d8f84a03c6906eca5f9` |

## 테스트 작성 단계 — 구현 전

- 공유 시그니처와 `NotImplementedError` stub을 읽고 테스트만 작성했다. production/build 파일은 수정하지 않았다.
- 최종 조정 정책: JS trim 문자 집합(BOM 제거/NEL 보존), 정확한 숫자 토큰 기반 ID 정수성·안전 범위, BigDecimal 가격 저장, 자동 채움 `stripTrailingZeros().toPlainString()`, 비양수/오류 가격의 기준일 숨김.
- 정확한 숫자 토큰 ID 검사는 웹의 Double 반올림 뒤 안전 정수 검사보다 엄격하다. 예: `1.0000000000000001`은 웹에서 1로 반올림될 수 있으나 Android는 거절한다.
- 상태의 search Ready.value는 전체 수신 배열을 보존하고 filter는 UI에서 파생한다. filter 변경은 요청하지 않는다.
- 화면 inactive는 요청을 무효화/취소하고 초안을 보존, 다시 active면 적절한 요청을 재시작한다. close는 최종 종료다. 회전은 ViewModel 유지, 프로세스 복원은 query/country/filter/selected/unitPrice/dirty 데이터만 대상으로 한다. Job/Call은 저장하지 않는다.
- 기존 거래 수정 모드는 고정 인터페이스에 없으므로 이 파일럿 테스트 범위에서 제외했다. 복원된 비편집 단가의 보존은 별도 core 테스트로 포함했다.
- JVM 테스트는 49개 함수, 기기 instrumentation 테스트는 5개 함수다. 반복 fixture 수와 테스트 함수 수는 구별한다.
- 아직 실행 결과가 아니다. 이 역할은 Gradle/DB를 실행하지 않았으며 조정자가 red 실행·컴파일 오류 수정 확인 후 테스트 해시를 고정한다.
- 조사 후 `search.md`, `price.md`를 대조했고 원본 해석에서 위 정책 차이 외 차단 지적은 발견하지 않았다. 추후 소스·실행 리뷰는 별도 단계다.
- 테스트 작성 종료: 2026-10-28 08:20:40 UTC.

| 테스트 파일 | SHA-256 (red 실행 전) |
| --- | --- |
| `clients/android/market-core/src/test/kotlin/org/daynomy/market/ContractFixtures.kt` | `d9449c31b426a61cbb3afd1afef33577c733845c93f9c76496f0dc40fee59ab3` |
| `clients/android/market-core/src/test/kotlin/org/daynomy/market/MarketControllerContractTest.kt` | `e8201ff7f3b21fcdba473803c02381a22f7584147442ff364e6c858e4cb82199` |
| `clients/android/market-core/src/test/kotlin/org/daynomy/market/OkHttpTransportContractTest.kt` | `b80f55ddd41b33270018ab88bc4527a93378f0b6802f1c50098a1b7f8cc7bc4a` |
| `clients/android/market-core/src/test/kotlin/org/daynomy/market/StockPriceClientContractTest.kt` | `1d568f1a3a654baa847beb5fc409bf0d3c2b2d916318a753472cabe833525093` |
| `clients/android/market-core/src/test/kotlin/org/daynomy/market/StockSearchClientContractTest.kt` | `fb3205972876f584cef4d43ba86d2ae16ae9a27feece05daef7edb20628e2566` |
| `clients/android/app/src/androidTest/kotlin/org/daynomy/android/MarketScreenAcceptanceTest.kt` | `e6d383dab7244d311c29b0a5daccd117394dfb681f67a8a13b7ee0be245d42e4` |
