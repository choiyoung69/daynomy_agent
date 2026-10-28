---
title: 종목 검색과 최근 종가
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F02", "F03", "F04", "F05", "B01", "B02", "B03", "B04", "B05", "B06", "R01", "P01"]
---

# 종목 검색과 최근 종가

기준 원본은 `reference/2026-DAYNOMY-dev`다. 아래는 코드를 읽어 확인한 현행 동작이다.
제품 정책으로 새로 승인한 목록이나 이번에 실제 서버·화면으로 재현한 결과가 아니다.
출처 ID는 [자료 목록](../../../sources.json)의 파일 경로·해시와 연결된다.

## 검색에서 가격 입력까지

`PortfolioTransactionEditor`의 검색 effect → `searchStocks` → 공통 `request` →
Spring `StockController.search` 또는 Rust `service_market::search` → 결과 선택 →
가격 effect → `getLatestStockPrice` → 최근 저장 가격 조회 → 거래 단가 자동 채움으로 연결된다.
이 문서 범위는 단가 채움까지이며 거래 저장·원장 계산은 포함하지 않는다.

| 주장 ID | 코드에서 확인한 동작 | 근거 |
| --- | --- | --- |
| S01 | `searchStocks`는 `q`를 URLSearchParams로 인코딩한다. 기본 KR은 country를 생략하고 US만 명시한다. | F01 `searchStocks` |
| S02 | 거래 편집기에서 선택 종목이 있거나 검색어가 공백이면 검색하지 않는다. 검색어를 trim하고 250ms 후 요청한다. | F04 첫 검색 effect |
| S03 | 검색어·국가 등의 변경과 effect 정리 시 타이머를 해제하고 이전 요청을 취소한다. 응답·오류·로딩 반영 전 취소 상태도 확인한다. | F04 첫 검색 effect |
| S04 | 검색 응답은 stocks 배열이어야 하며, 각 종목의 ID는 양의 안전 정수, 코드는 문자열, category는 STOCK 또는 ETF, market은 허용 목록이어야 한다. 통화는 이 검증에서 검사하지 않는다. | F01 `isStock`, `isStockMarket`, `searchStocks` |
| S05 | 원본 Controller는 q의 필수·최대 50자·문자/숫자 포함과 country KR/US를 검증한다. Service는 strip 및 LIKE 특수문자 이스케이프 후 해당 시장의 상장 주식·ETF를 최대 20개 검색한다. | B01 `search`, B02 `search` |
| S06 | 기존 거래 수정 또는 선택 종목 없음에서는 종가 요청을 시작하지 않는다. 새 종목의 종가 요청에는 취소 신호를 전달한다. | F04 두 번째 가격 effect |
| S07 | 종가 응답에서 baseDate는 문자열, closePrice는 유한한 number인지 검사한다. API 클라이언트는 날짜 문법이나 양수 가격을 검사하지 않는다. | F01 `getLatestStockPrice` |
| S08 | 편집기는 가격이 0 이하이면 오류로 처리한다. 사용자가 단가를 수정했거나 입력값이 이미 있으면 응답으로 단가를 덮어쓰지 않는다. 실패 시 직접 입력 안내를 표시한다. | F04 가격 effect, `change` |
| S09 | currency가 없을 때 `.US` 코드이면 USD, 나머지는 KRW로 처리한다. 타입 선언만으로 런타임 응답의 currency를 검증한 것은 아니다. | F02 `stockCurrency`, F01 응답 검증 |
| S10 | 최근 종가는 저장된 데이터 중 baseDate 내림차순 첫 행이다. 이 조회 경로는 외부 시세 요청이나 오늘 가격 생성을 수행하지 않는다. | B03 `getLatestPrice`, B06 `findFirstByAssetIdOrderByBaseDateDesc` |
| S11 | 저장 가격이 없으면 STOCK_PRICE_NOT_FOUND 업무 오류이며 HTTP 상태는 404다. 응답 DTO의 가격은 BigDecimal, 날짜는 LocalDate다. | B03, B04, B05 |
| S12 | Rust의 검색·종가 경로는 service_market에 있다. 검색 SQL은 상장 주식·ETF와 시장을 제한하고 20개를 반환한다. 종가 SQL은 base_date DESC LIMIT 1이며 없으면 같은 코드의 404다. | R01 `handle`, `search`, `latest` |
| S13 | 공통 request는 credentials include를 사용한다. 401이면 공유 refreshPromise로 갱신을 시도하고 원 요청을 한 번 재시도한다. 204는 undefined, 그 외 성공은 JSON으로 읽는다. | F03 `request`, `refreshAccessToken` |

## 검증 근거의 경계

F05의 테스트 파일에는 기본 종목 검증, 검색·종가 경로와 검색 취소 신호 전달,
잘못된 시장·가격 타입 거절 사례가 있다. 이 테스트를 이번 작업에서 실행하지 않았다.
해당 사례만으로 실제 네트워크 취소, UI의 응답 순서, 양쪽 OS 생명주기, 금액 정밀도가
보장된다고 해석하지 않는다.

P01은 과거 종가 실험의 명세다. 전체 서비스의 현재 구현·실행 결과는 별도 확인해야 한다.
Spring의 BigDecimal, JSON 숫자, 웹의 number는 서로 다른 층이다. DTO의 타입만으로
웹·모바일의 전체 금액 처리 정확성을 확정하지 않는다.

## 이식 전에 확인할 질문

- 날짜 문자열을 각 언어에서 거래일로 보존하는 방법은 Q02에 남겨 두었다.
- 큰 ID·십진수의 표현과 반올림은 Q03의 재현 사례로 정한다.
- 검색 취소·수동 단가 보존의 실제 화면 검증은 Q04다.
- 모바일 로그인·세션 저장·복귀 계약은 Q05이며 공개 조회만으로 해결했다고 판단하지 않는다.

다음 문서: [이식 계획](../../porting/stock-search-price.md), [미확인 질문](../../../questions.md).
