# 최근 종가 조회 실험

대상: 공개 GET `/api/stocks/{assetId}/price`. 리그와 무관한 포트폴리오의 기반 조회 API다.
기존 피드백 앱과 뉴스/계산 실험을 유지하고 `experiments/stock-price/`에서 구현한다.
웹 프레임워크를 쓰지 않고 자체 Rust 크레이트에 unsafe를 금지한다.

## 계약과 근거

1. 해당 자산의 저장된 종가 중 `base_date`가 가장 최근인 행을 반환한다.
   원본은 StockPriceService.getLatestPrice →
   StockDailyPriceRepository.findFirstByAssetIdOrderByBaseDateDesc를 사용한다.
   오늘 가격을 생성하거나 외부 데이터를 요청하지 않는다.
2. 성공은 200 JSON, 필드는 정확히 `assetId`, `assetCode`, `name`, `baseDate`,
   `closePrice`, `currency`다. 날짜는 YYYY-MM-DD. 숫자 closePrice를 문자열/부동소수점으로
   바꾸지 않고 serde_json arbitrary_precision으로 보존한다. 원본 DTO는 BigDecimal이다.
3. NASDAQ/NYSE/NYSE_ARCA/NYSE_AMERICAN/BATS는 USD, KOSPI/KOSDAQ/market=null은 KRW다.
   원본 Asset.getCurrency와 StockMarket.currency의 규칙이다. 환율 환산은 하지 않는다.
4. 자산에 가격이 없거나 자산 자체가 없으면 모두 404,
   `{ "code":"STOCK_PRICE_NOT_FOUND", "message":"주식·ETF 종가를 찾을 수 없습니다." }`.
   errors 필드는 생략한다. AssetErrorCode 및 ErrorResponse가 근거다.
5. 상장 여부나 주식/ETF 구분으로 저장된 가격을 숨기지 않는다. 이 조회 서비스에는
   그런 필터가 없으므로 상장폐지 종목도 저장 가격이 있다면 반환한다.
6. assetId는 원본 Long 경로 변수다. 일반 십진수·부호·선행0, 0/음수·i64 최대값을 검증한다.
   abc/소수/i64 범위 초과는 400:
   `{ "code":"INVALID_REQUEST", "message":"요청값이 올바르지 않습니다.",
      "errors":[{"field":"assetId","reason":"타입이 올바르지 않습니다."}] }`.
   0/음수는 양수 검증이 없어 조회 결과 없음에 따른 404다. 타입 오류의 근거는
   GlobalExceptionHandler.handleMethodArgumentTypeMismatch다.
7. 인증/CSRF 없이 읽을 수 있고 DB를 변경하지 않는다. 서버 시작 후 새 최신 가격을
   넣으면 다음 요청에 반영한다. 요청별 전체 JSON·상태·미디어 타입과 DB 불변성을 원본과 비교한다.

이번 실험의 HTTP 호환 검증은 위 입력 범위다. URL 인코딩/프록시 정규화/다른 메서드,
외부 연동·가격 수집·인증·전체 종목 검색·운영 부하 검증은 포함하지 않는다.
DB 전수 로딩 어댑터는 작은 fixture 목적이며 운영 쿼리/성능 구현이 아니다.

원본 루트: `reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/`.
근거 파일: asset/controller/StockController.java, asset/service/StockPriceService.java,
asset/repository/StockDailyPriceRepository.java, asset/dto/StockPriceResponse.java,
asset/domain/Asset.java, asset/domain/StockMarket.java, asset/exception/AssetErrorCode.java,
common/exception/GlobalExceptionHandler.java, common/response/ErrorResponse.java.
원본 테스트: backend/src/test/java/org/grit/daynomy/asset/service/StockPriceServiceTest.java,
asset/controller/StockControllerTest.java.

## 역할과 인터페이스

- 테스트 작성: 명세와 원본만 보고 `tests/stock_price_contract.rs`에 Rust 통합 테스트를 작성한다.
  원본이 요구하는 기대값을 직접 선언한다. 구현 코드는 읽지 않는다.
  `#[path = "../src/stock_price.rs"] mod stock_price;`로 모듈을 포함한다.
  최소 8개의 독립 test 함수, 실제 assert, ignore/skip/외부 명령/파일·네트워크 I/O 없이 작성한다.
  정상·최근 날짜 선택·국내/미국/market=null 통화·상장폐지·가격 없음·없는 자산·잘못된 ID·정밀도를 포함한다.
- 구현: `src/stock_price.rs`만 작성/수정. 테스트·명세·기반 HTTP/DB 코드는 수정할 수 없다.
- 리뷰: 명세·원본·테스트·구현·실행 근거를 읽고 승인/수정 요청. 파일은 읽기 전용이다.
- 프로그램: 빌드·테스트 실행·잘못된 구현 주입·실제 Spring/Rust/DB 비교·해시/완료 판정.

```rust
pub fn latest(asset_id: &str, data: &serde_json::Value) -> (u16, serde_json::Value);
```

data는 실제 테이블의 to_jsonb 행 배열을 `assets`, `stock_daily_prices` 키에 가진다.
asset 행: id,asset_code,name,market,category,listed 등. 가격 행: asset_id,base_date,close_price 등.
배열은 정렬됐다고 가정하지 않고 요청 대상 이외 종목도 들어 있다.
사용 가능 라이브러리는 serde_json과 표준 라이브러리다.

## 완료 기준

독립 테스트 작성 → 빈 구현에서 실패 확인 → 테스트 고정 → 구현/수정 →
고정 테스트 통과 → 잘못된 통화/날짜/가격/없는 가격 응답 주입 시 테스트 실패 →
실제 원본 비교와 DB 불변 검사 → 별도 리뷰 승인과 해시 일치가 모두 필요하다.
호출 실패·누락된 증거·검사 기준의 임의 완화·미결정 질문이 있으면 완료로 처리하지 않는다.
한 API이므로 이번에는 구현 병렬 슬롯을 불필요하게 두 개 채우지 않는다.
