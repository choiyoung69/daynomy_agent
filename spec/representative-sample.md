# 대표 기능 재현 실험

2026-10-21. 목적: 몇 개 기능을 실제로 구현·검증해 시간을 측정한다.
대상은 GET /api/news, GET /api/news/{id}, POST /api/portfolio/calculate.
이 샘플은 전체 뉴스·전체 포트폴리오 기능, 실제 외부 환율 연동, 인증/거래 원장 구현 완료를 뜻하지 않는다.
Spring과 Rust가 같은 전용 fixture DB를 조회한다. 운영/기존 실험 데이터는 사용하지 않는다.

## 구현 역할 인터페이스

구현 역할은 작업 폴더의 `news.rs`, `portfolio_calc.rs`만 수정한다.
빌드·서버 실행·DB 쓰기·명세/검사/기반 코드 수정·추가 에이전트 생성은 하지 않는다.
허용 의존성은 serde_json 및 Rust 표준 라이브러리. 크레이트는 unsafe를 금지한다.
두 파일은 crate 모듈이며 별도 main 함수는 없다.

```rust
// news.rs
pub fn list(query: &str, rows: &serde_json::Value) -> (u16, serde_json::Value);
pub fn detail(id: &str, rows: &serde_json::Value) -> (u16, serde_json::Value);
// portfolio_calc.rs
pub fn calculate(body: &[u8], data: &serde_json::Value) -> (u16, serde_json::Value);
```

rows는 실제 PostgreSQL `news` 각 행의 `to_jsonb` 배열이며 snake_case 열 이름을 사용한다.
data는 `assets`, `stock_daily_prices`, `usd_krw_rates` 각 테이블의 실제 행 배열을 키로 갖는다.
데이터 로딩·HTTP·CSRF·본문 제한은 고정한 main.rs가 담당한다.
이 전수 로딩 어댑터는 샘플 검증 목적이며 운영용 쿼리 계획·성능 구현이 아니다.
DB의 numeric과 입력 JSON 숫자는 serde_json arbitrary_precision으로 보존한다.

## 뉴스

- 공개 목록은 PUBLISHED만, published_at DESC/id DESC. query page 기본 1, size 기본 15, category 선택.
  page≥1, size 1~100, category는 원본 enum. 빈 페이지는 빈 items이며 전체 개수/페이지를 유지한다.
- 목록 응답: items[{id,title,imageUrl,category,publishedAt}], page,size,totalPages,totalElements,hasNext.
- 상세는 PUBLISHED만. 없거나 초안/거절이면 404 NEWS_NOT_FOUND, message=`해당 뉴스를 찾을 수 없습니다.`.
- 상세 응답: id,title,content,imageUrl,imageSource,sources,category,publishedAt.
  imageSource는 name,url,author,license,licenseUrl,type(비어 있으면 NONE). sources는 [{name,url}].
- 잘못된 page/size/category 등의 입력은 원본 검증 응답과 비교한다. 값이 정해지지 않은 정책을 새로 추가하지 않는다.
- 시간 문자열은 같은 Instant이면 동등하게 비교한다. 키 순서·검증 errors 배열 순서만 정규화한다.

## 평가 계산

- body는 {holdings:[{assetId,quantity,averagePurchasePrice}]}.
  원본 DTO 검증을 따른다: 1~50개, null 요소 금지, ID/수량 양의 정수,
  평균가≥0.01, 정수15자리/소수2자리. 같은 자산 중복은 400 DUPLICATE_PORTFOLIO_ASSET.
- 없는 자산은 원본 AssetErrorCode. 잘못된 입력·JSON은 GlobalExceptionHandler/DTO의 오류 형식을 따른다.
- 종목별 최신 두 가격을 사용. USD는 각 가격일의 캐시 환율로 KRW 환산한다. 환산 단가를 먼저 반올림하지 않고
  수량을 곱한 평가금액 단계에서 소수2자리 HALF_UP을 적용한다.
  캐시 환율 fixture가 없으면 이 샘플에서는 가격 미확인으로 취급한다. 실제 외부 조회는 범위 밖이다.
- 매입금액=원화평균가×수량, 평가금액=원화환산종가×수량, 손익=평가-매입, 수익률=손익/매입×100.
  금액·비율은 소수2자리 HALF_UP. 이진 부동소수점 근사로 계산하지 않는다. 0 분모 비율은 0이다.
- holdings는 입력 순서. 필드: assetId,assetCode,name,category,market,priceAvailable,baseDate,quantity,
  averagePurchasePrice,closePrice,purchaseAmount,evaluationAmount,profitLoss,returnRate,weight,
  averagePurchasePriceCurrency='KRW',currency=(시장별KRW/USD),evaluationCurrency='KRW'.
  closePrice는 원래 통화의 종가이며 평가금액만 환산한다.
- 가격 없는 종목은 baseDate/closePrice/evaluationAmount/profitLoss/returnRate/weight=null, priceAvailable=false.
  매입금액은 포함한다. 모든 가격이 없으면 baseDate=null.
- 전체: baseDate는 가격이 있는 종목 중 가장 이른 날짜. pricingStatus=PARTIAL(미평가 존재),
  MIXED_DATES(전부 평가되지만 최신 날짜 혼합), COMPLETE(나머지).
- 전체 필드: baseDate,pricingStatus,pricedHoldingCount,unpricedHoldingCount,totalPurchaseAmount,
  totalEvaluationAmount,dailyProfitLoss,dailyReturnRate,totalProfitLoss,totalReturnRate,holdings,marketAllocations.
  부분 평가 시 totalProfitLoss/totalReturnRate=null. 전체 평가금액은 확인된 종목만 합친다.
- 일간 손익은 모든 종목에 최신/직전 가격이 있고 각 날짜가 서로 맞을 때만 계산하며 아니면 둘 다 null.
- 비중=종목 평가금액/확인된 전체평가금액×100. marketAllocations는 StockMarket enum 순서이고
  각 {market,evaluationAmount,weight}. 미평가 종목은 시장 배분에서 제외한다.

## 원본 근거

원본 루트는 reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy.
구현과 검토는 다음 원본을 읽어 누락된 세부를 확인할 수 있다. 참조 코드는 수정하지 않는다.

- news/controller/NewsController.java, news/service/NewsService.java, news/domain/Category.java
- news/dto/NewsPageResponse.java, NewsListItemResponse.java, NewsDetailResponse.java, ImageSourceResponse.java, NewsSourceResponse.java
- portfolio/service/PortfolioCalculationService.java, exchangerate/service/ExchangeRateService.java
- portfolio/dto/PortfolioCalculateRequest.java, PortfolioHoldingRequest.java, PortfolioHoldingResponse.java, PortfolioCalculationResponse.java
- portfolio/exception/PortfolioErrorCode.java, asset/exception/AssetErrorCode.java, common/exception/GlobalExceptionHandler.java
- 원본 테스트 news/service/NewsServiceTest.java, portfolio/service/PortfolioCalculationServiceTest.java.

## 판정과 시간

실제 Spring/Rust의 같은 요청에 대해 상태·미디어 타입·JSON 전체를 비교한다.
정규화는 숫자 표현(1과1.00)·동일 시각·객체 키/검증 errors 순서에 한정한다.
배열의 종목/뉴스 순서·추가/누락 필드·null·오류 메시지는 비교에서 지우지 않는다.
성공 응답에 대한 독립 기대값과 fixture DB 불변 검사도 수행한다.
별도 검토 역할이 코드·원본·검사 근거를 읽어 승인해야 샘플 완료다.
구현 호출 시간, 빌드·원본 준비·검사 시간, 검토·수정 시간, 프로세스 전체 경과를 따로 기록한다.
샘플 실행 전 코드 분석·명세·기반 실행기 작성 시간은 구현 호출 시간에 포함하지 않고 별도 한계로 표시한다.
