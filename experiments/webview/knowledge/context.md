PASS local source hashes 108/108; wiki pages 99; evaluation questions 31; metadata, source IDs and local links
External sources 63: pinned response hashes 63; live content not checked.
Platform mappings 5: structure checked, preparation status assessed by context.
No semantic answer evaluation or app/server/DB/UI verification was performed.

Context: stock-search-price / webview
Preparation: READY FOR IMPLEMENTATION; app execution still unverified

Selected documents only; no agent invocation or file-access isolation:

--- knowledge/wiki/projects/daynomy/stock-search-price.md ---

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


--- knowledge/wiki/shared/client-porting-baseline.md ---

---
title: 클라이언트 이식의 공통 준비 기준
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F02", "F03", "F04", "B04", "B05"]
---

# 클라이언트 이식의 공통 준비 기준

첫 기능은 종목 검색·선택·최근 종가 조회의 초기안이다. 아래는 작업 전달 전에 준비할 공통 계약과
검사 계획이다. 현재 코드 근거는 [기능 문서](../projects/daynomy/stock-search-price.md)를 따른다.

## 작업 전에 정리할 지식

| 영역 | 준비할 내용 | 첫 기능의 남은 작업 |
| --- | --- | --- |
| 언어와 데이터 | null·누락 필드·안전 정수·십진수·날짜·문자열·JSON 대응 | 대상별 ID·가격·날짜 디코딩 정책과 경계값 확인 |
| 상태와 생명주기 | 입력·선택·로딩·빈 결과·오류의 상태 전환, 이탈·복귀 | 화면 상태의 소유자와 유지 범위 결정 |
| 통신과 취소 | API 주소·응답 검증·오류·취소·늦은 응답 무시 | HTTP 클라이언트와 환경별 연결·취소 계약 결정 |
| UI와 탐색 | 입력·키보드·뒤로 가기·접근성·화면 크기 | 실제 UI와 탐색 방법 및 시나리오 선택 |
| 인증과 저장 | 쿠키·토큰·401 갱신·저장 위치·로그인 복귀 | 공개 조회의 준비와 회원 기능 확장 준비를 구분 |
| 빌드와 검증 | 대상 OS·SDK·버전·명령·테스트 환경 | 실행 가능한 대상과 검증 명령 고정 |

첫 공개 조회의 착수 준비에서는 언어/데이터·상태·통신·빌드 검증을 필수로 확인한다.
인증·탐색·저장의 범위는 대상에 맞춰 명시하며, 전체 회원 앱의 준비 완료로 확대하지 않는다.

첫 공통 주제인 [오류·재시도·요청 취소](error-retry-cancel.md)는 HTTP 표준·원본 코드·이식 제안을
나누어 작성했다. [데이터 경계](data-semantics.md)와 [빌드 환경](build-validation.md)도 기능 입력에 포함한다.
회원 거래에는 [트랜잭션과 동시성](transactions-concurrency.md)을 추가한다. 대상 앱의 실행 확인은 남아 있다.

## 공통으로 전달할 사례

- 검색어 `삼성`과 KR/US를 요청으로 만들고, 공백·빈 결과·잘못된 응답의 상태를 구분한다.
- A 검색 응답을 지연한 뒤 B를 먼저 완료한다. 최종 결과와 로딩·오류가 B의 상태를 유지해야 한다.
- 종가 응답 전에 단가를 직접 입력한다. 응답 후에도 입력한 단가를 유지해야 한다.
- 종가 없음의 404와 응답 형식 오류를 구별한다. 실패 시 직접 단가 입력 안내를 유지한다.
- baseDate의 달력 날짜, 큰 정수 ID, 소수 가격을 디코딩·처리·표시 단계별로 비교한다.

이 목록은 테스트 계획이다. 실제 입력 fixture·기대값을 원본과 대조해 고정하는 작업은 남아 있다.
사용자 입력 보존과 날짜·숫자 정책을 검증 없이 플랫폼 기본값에 맡기지 않는다.

## 필요한 문서만 전달하는 방법

`python3 scripts/knowledge.py context --platform ios --feature stock-search-price`는 이 공통 기준,
해당 기능 근거, 공통 기술 주제, 언어 패키지, iOS 문서와 그 출처만 출력한다.
다른 플랫폼 문서와 평가 정답은 기본 묶음에 넣지 않는다.
이는 문서를 선택하는 명령이며 모델 호출·앱 구현·파일 읽기 권한 격리를 수행하지 않는다.

`--require-ready`는 필수 주제·대상 버전·미해결 결정의 준비 상태를 확인하고 미충족 시 종료 2로 멈춘다.
현재 묶음은 초안이며 실제 작업 실행기가 자동으로 이 명령을 호출하는 연결은 아직 없다.
위키 구조 검사의 통과와 구현 착수 준비 판정은 별개다.


--- knowledge/wiki/shared/error-retry-cancel.md ---

---
title: 오류와 재시도 및 요청 취소
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F03", "F04", "E19"]
---

# 오류와 재시도 및 요청 취소

종목 검색·최근 종가 조회의 사전 지식이다. 아래에서 HTTP 표준, 원본 코드의 관찰,
이식 설계 제안을 구분한다. 현재 요청 코드나 사용자 정책을 변경하지 않는다.

## 오류를 구분할 기준

| ID | 구분 | 처리 판단 | 근거와 상태 |
| --- | --- | --- | --- |
| C01 | HTTP 실패 | status와 업무 code를 읽어 계약에 맞게 처리한다. 원본은 JSON 오류 본문에서 문자열 code·message를 추출하고 없으면 상태 기반 오류를 만든다. | F03 `parseError`, 코드 관찰 |
| C02 | 성공 응답의 형식 오류 | HTTP 성공과 유효한 업무 데이터를 구별한다. 검색 stocks 배열·종목 필드와 종가 ID·가격을 런타임 검증한다. | F01 `searchStocks`, `getLatestStockPrice`, 코드 관찰 |
| C03 | 인증 실패 | 원본 request는 401 때 공유 refreshPromise로 갱신하고 원 요청을 한 번 재시도한다. | F03, 코드 관찰. 대상별 쿠키·갱신 호환은 미검증 |
| C04 | 이전 요청의 취소 | 원본 검색은 이전 타이머·요청을 취소하고 결과·오류·로딩 반영 전에 aborted를 확인한다. 가격 요청도 취소 여부를 확인한다. | F04의 effect, 코드 관찰 |
| C05 | 통신 끊김과 변경 요청 | 비멱등 요청은 실제 멱등성이나 미적용 여부를 알 수 있는 조건 없이 자동 재시도하지 말아야 한다. | E19 RFC 9110 9.2.2, 표준의 조건 |

E19의 멱등성은 동일 요청 반복의 의도한 서버 효과에 대한 성질이다. 모든 응답이 같다는 뜻이나
단순 HTTP 메서드 이름만으로 업무의 중복 처리가 해결된다는 뜻으로 사용하지 않는다.

## 이식할 때의 설계 제안

취소는 오류 메시지 표시와 구별한다. 이전 검색을 취소한 결과가 새 검색의 오류·로딩 상태를
덮어쓰지 않도록 요청 식별 또는 취소 상태 확인을 연결한다. 실제 HTTP 작업 중단과 화면 반영 방지는
각각 선택한 클라이언트와 상태 관리 방식에서 검사한다.

서버 응답을 받지 못한 변경 요청은 처리 결과가 미확인일 수 있다고 모델링한다.
서버에 적용되지 않았다고 단정해 재전송하지 않고, 해당 API의 결과 확인·중복 방지 계약을 먼저 조사한다.
이는 향후 변경 API 이식의 설계 제안이다. 현재 첫 조회 기능에 새 저장 정책을 추가하지 않는다.

GET 조회의 재시도 횟수·지연·시간 제한도 별도 정책이다. 멱등성만으로 무한 재시도를 허용하지 않는다.
현재 원본 공통 request에서 확인한 자동 재시도는 401 갱신 후 한 번이며, 통신 실패용 반복 정책은 이 문서에서 확정하지 않는다.

## 언어와 플랫폼별 확인

선택한 플랫폼 문서에서 취소·예외·상태 수명 규칙을 함께 읽는다.
공통 결과는 유지하되 실제 중단·오류 전파·화면 변경 방법은 언어·런타임·HTTP 라이브러리별로 확인한다.

- [Android](../platforms/android.md): 코루틴의 협력적 취소와 상태 보존, 실제 HTTP 취소 계약.
- [iOS](../platforms/ios.md): Task 취소 확인과 선택한 UI 작업 수명·API 가용성.
- [React Native](../platforms/react-native.md): 런타임 응답 검사와 쿠키·통신·요청 취소의 대상 버전 차이.
- [Flutter](../platforms/flutter.md): Future 완료·오류와 HTTP 취소의 구별, dispose 후 상태 변경 방지.
- [WebView](../platforms/webview.md): 웹의 취소 동작과 호스트별 탐색·로그인·복귀의 연결.

## 실행해서 확인할 사례

| 사례 | 확인할 기대 결과 | 준비 상태 |
| --- | --- | --- |
| 검색 A를 지연하고 검색 B를 먼저 완료 | A의 결과·오류·로딩이 B를 덮어쓰지 않음 | 원본 분기 확인, 실행 미완료 |
| 선택 종목 가격 요청 중 화면 이탈 | 이탈한 화면에 늦은 응답 상태를 반영하지 않음 | 원본 취소 분기 확인, 대상별 실행 필요 |
| 200이지만 잘못된 종목·가격 필드 | 데이터 검증 오류를 처리하고 잘못된 값을 표시·저장하지 않음 | F01 검증 확인, UI 실행 필요 |
| 동시 401과 갱신 실패 | 공유 갱신·원 요청 한 번 재시도 계약과 최종 오류 처리를 확인 | F03 확인, 대상별 연결 필요 |
| 변경 요청 처리 후 응답 유실 | 미적용으로 단정하지 않고 결과 확인·중복 방지 계약을 따름 | 향후 변경 API 계약 조사 필요 |

위 사례는 실행 계획이다. 플랫폼별 실제 예외 타입, 오류 메시지, 재시도 정책과 fixture는
대상 버전·클라이언트를 선택한 뒤 고정한다. [공통 준비](client-porting-baseline.md)와
[미확인 질문](../../questions.md)의 Q04·Q05·Q09에 연결한다.


--- knowledge/wiki/shared/data-semantics.md ---

---
title: 언어별 숫자·날짜·null·JSON 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["F01", "F02", "F03", "B04", "E03", "E20", "E21", "E22", "E23", "E24", "E25", "E26", "Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "B02", "R01", "G11", "G12", "G13"]
---

# 언어별 숫자·날짜·null·JSON 경계

다섯 개발 방식은 다섯 언어와 일치하지 않는다. Android는 Kotlin, iOS는 Swift,
React Native와 WebView의 웹 코드는 JavaScript/TypeScript, Flutter는 Dart가 후보다.
WebView는 호스트 코드와 웹 코드 사이의 데이터 전달도 확인해야 한다.
아래는 언어 규칙·관찰과 이식 제안이다. 클라이언트별 라이브러리·버전 선택은 남아 있다.

## 공통으로 유지할 경계

| ID | 확인한 규칙·관찰 | 이식에 적용할 제안 |
| --- | --- | --- |
| L01 | JSON 숫자의 정밀도는 구현마다 제한된다. RFC 8259 §6은 ±(2^53−1) 범위 정수의 상호 운용성을 설명한다(E20). 웹은 양의 안전 정수 ID를 검사한다(F01). | 네이티브가 더 큰 정수를 읽어도 기존 웹과 같은 공개 계약을 먼저 적용한다. API를 문자열 ID로 바꾸는 일은 별도 계약 변경으로 결정한다. |
| L02 | Node의 `0.1+0.2`는 `0.30000000000000004`이고, Swift Decimal의 같은 십진 문자열 연산은 `0.3`이다(Q08). 서버 DTO는 BigDecimal, 웹 종가는 number다(B04/F01). | 입력 원문·서버 전송·계산·화면 표시 단계를 구분한다. 금액의 자릿수·반올림·허용 범위를 확인한 후 자료형을 정한다. 소수 문자열로 바꾸는 제안과 현행 API를 혼동하지 않는다. |
| L03 | JSON에는 null이 있지만 undefined는 없다. JS 객체의 undefined 프로퍼티는 직렬화에서 빠진다(E21/Q08). Swift 합성 Optional 디코딩은 이 사례에서 누락과 null 모두 nil이다(Q08). | 필수값·누락·명시 null·잘못된 타입의 기대 결과를 필드별로 정한다. 부분 수정에서 구별이 필요하면 필드 존재 여부를 보존한다. |
| L04 | JS의 표준 날짜 전용 문자열은 UTC로 해석된다(E22). Node에서 이를 미국 LA 시간대로 표시하면 `2026-10-28`이 `2026-10-27`이 됐다(Q08). | 종가 baseDate는 달력 날짜로 유지한다. 시각으로 만들고 현지 시간대로 변환하는 처리를 피한다. 달력 유효성 검사는 원본의 문자열 타입 검사보다 강화되므로 별도 동작 결정이 필요하다(F01/B04). |
| L05 | `😀` 길이는 Node UTF-16 2, Swift Character 1·UTF-16 2, Rust UTF-8 바이트 4·Unicode scalar 1이다. `é`와 분해된 `é`의 동등 비교도 Swift와 Node/Rust가 달랐다(E26/Q08). | 검색어 제한·잘라내기·동등성 비교에서 길이 단위와 정규화 위치를 명시한다. 현재 Java/Rust 검색 정규화가 같다는 결론은 내리지 않는다. |
| L06 | 공통 웹 request의 TypeScript 제네릭은 JSON을 런타임 검증하지 않는다. 종목 API에 별도 검증이 있으며 currency 검사는 없다(F03/F01). | 타입 선언과 경계 디코더를 구분한다. 알 수 없는 enum·타입 불일치·누락 응답의 정책을 필드별로 고정한다. |

## 플랫폼별 적용 지점

| 대상 | 언어·디코더 대응 | 현재 확인 범위와 남은 일 |
| --- | --- | --- |
| Android/Kotlin | Long과 Double의 범위를 구분한다. `T?`는 null 허용을 나타낸다(E23/E24). | 공식 언어 문서 확인. JSON 라이브러리의 기본값·누락/null·정밀도와 날짜 타입은 선택 후 재현. Kotlin 실행 미실시. |
| iOS/Swift | Int64로 ID를 읽되 서비스의 허용 범위는 별도 검사한다. Optional만으로 누락/null을 구별하지 않는다. | macOS Foundation 예제 실행. iOS 빌드·네트워크 디코딩·Decimal 범위와 반올림 정책은 미검증. |
| React Native | JS number와 JSON 직렬화 경계를 반영하고 응답 스키마를 검사한다. | Node 예제 실행. 대상 RN 런타임에서 같은 fixture를 실행해야 한다. |
| Flutter/Dart | 네이티브와 웹의 숫자 표현 차이를 고려한다(E03). Map 조회의 null만으로 키 누락을 판별하지 않는다(E25). | 공식 자료 확인. 선택한 디코더·Dart 네이티브에서 실행 필요. Flutter 웹을 추가하면 별도 실행. |
| WebView | 웹 데이터 검사와 네이티브 브리지의 직렬화를 각각 확인한다. | Node 예제만 실행. Android WebView·WKWebView·브리지 왕복은 미실시. |

통화는 기존 웹의 `currency ?? (assetCode.endsWith('.US') ? 'USD' : 'KRW')`를 출발점으로 삼는다(F02).
누락/null fallback과 잘못된 통화 문자열 거절은 다른 정책이다. 현재 API가 후자를 검증한다고 설명하지 않는다.

## 재현 근거와 사용법

[실행 결과 Q08](../../evidence/2026-10-28-language-01.json)는 명령·종료 코드·런타임 버전·기대값·관찰값과
입력 소스의 SHA-256을 담는다. Node 10개, Swift 8개, Rust 8개 관찰 필드를 비교했다.
이는 작은 합성 예제이며 대상 앱의 성공이나 독립 평가를 뜻하지 않는다.

```sh
python3 scripts/knowledge_probes.py --output /tmp/daynomy-language-new-run.json
```

출력은 기존 파일을 덮어쓰지 않는다. 실행 가능한 예제의 일치 여부와 도구 부재를 구분해 보고한다.
새 실행의 종료 0만으로 다섯 플랫폼 검증 완료를 선언하지 않는다. 이 예제는 대형 정수의 반올림·누락/null·날짜 이동 등
문제를 드러내는 검사이며, 제품 정책의 정답을 새로 승인하지 않는다.

프로브의 직접 외부 의존성은 Rust의 serde_json 1.0.154(`arbitrary_precision`: JSON 숫자 보존·관찰)다.
이 기능을 켜도 이후 `as_f64()` 변환에서 정밀도가 손실되는 사례를 포함한다. Swift는 Foundation,
Node는 기본 API를 쓴다. Rust 루트는 unsafe 코드를 금지한다.

관련: [기능의 현행 계약](../projects/daynomy/stock-search-price.md), [준비 상태](../../packs.json),
[남은 질문](../../questions.md). 실제 버전과 JSON 라이브러리를 선택한 뒤 같은 경계값으로 보강한다.

## 검색 공백의 추가 재현

Java strip과 Rust trim이 모든 Unicode 공백에서 같지는 않다. NBSP(U+00A0)를 양쪽에 붙인 `삼성`은
Java strip 후 UTF-16 길이 4, Rust trim 후 길이 2였다. EM SPACE(U+2003)는 둘 다 길이 2였다.
[실행 근거 G11](../../evidence/2026-10-28-unicode.json)에 Java/Rust 버전·명령·종료 코드·소스 해시를 보관했다.
B02와 R01은 각각 strip/trim을 검색어에 적용한다. 이는 언어 경계의 차이를 재현한 것이며
실제 SQL 검색 결과나 전체 원본 호환성을 검증한 결과는 아니다.


--- knowledge/wiki/shared/build-validation.md ---

---
title: 빌드 환경과 대상 버전 준비
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["Q08", "Q09", "DX09", "DX10"]
---

# 빌드 환경과 대상 버전 준비

현재 호스트에서 작은 언어 예제를 실행할 수 있는 범위와 대상 앱을 빌드할 준비는 다르다.
[도구 조사 Q09](../../evidence/2026-10-28-build-inventory.json)에 명령·종료 코드·확인 시점을 보존했다.

| 대상 | 현재 호스트에서 확인 | 착수 전에 고정할 것 |
| --- | --- | --- |
| Android | JDK 21.0.12, Gradle 경로 있음. adb·sdkmanager·kotlinc는 PATH에서 찾지 못함. SDK 디렉터리 전체 설치 여부는 미조사. | 최소/대상/컴파일 SDK, Kotlin·Compose·Gradle 플러그인, HTTP/JSON 의존성과 에뮬레이터/기기. |
| iOS | Swift 6.3.3으로 macOS 예제 실행. 활성 개발 경로는 Command Line Tools이며 xcodebuild -version 종료 1, simctl 조회 종료 72. | Xcode·지원 iOS·Swift 언어 모드, 시뮬레이터와 scheme/destination, 실제 디코더. |
| React Native | Node 22.23.1 예제 실행. RN 프로젝트·런타임 빌드 없음. | RN·TypeScript·런타임·양쪽 OS 버전, 패키지 잠금, 네이티브 도구 연결. |
| Flutter | dart·flutter는 PATH에서 찾지 못함. | Flutter·Dart 버전과 양쪽 OS 도구, 패키지 잠금, 대상 기기. |
| WebView | Node 실행만 확인. Android WebView·WKWebView 호스트 없음. | 웹 번들 식별자, 제공 URL/로컬 방식, 각 OS 호스트 버전과 웹 엔진, 브리지 범위. |

설치된 도구 버전을 곧바로 앱의 지원 버전으로 선택하지 않는다. 선택한 버전은 [packs.json](../../packs.json)의
selected_versions에 기록하고 의존성·실제 빌드 설정과 대조한다. 현재 값은 미정으로 유지한다.
서명·스토어 배포·운영 환경 연결은 이 준비 작업에 포함하지 않는다.

## 실제 앱 검사로 이어지는 순서

1. 지원 OS·플랫폼 범위와 기능 계약을 정하고 도구·의존성을 고정한다.
2. 생성한 프로젝트의 실제 빌드·단위 검사 명령을 파일에 기록하고 실행한다. 아직 없는 프로젝트의 명령을 실행 성공으로 기록하지 않는다.
3. [데이터 경계 예제](data-semantics.md)를 선택한 디코더·런타임으로 옮겨 기대값을 검증한다.
4. 검색 A/B 응답 역전·화면 이탈·수동 단가 보존·빈 결과·404·잘못된 응답을 실제 앱에서 확인한다.
5. 두 OS를 대상으로 하는 방식은 양쪽에서 실행하고, 결과·버전·소스 해시를 연결한다.

첫 공개 조회의 실행 계획과 회원 거래의 DB 검증 계획을 구분한다. 언어 예제 26개 관찰값의 일치는
HTTP 연결·화면 상태·쿠키 호환성·앱 빌드의 검증을 대체하지 않는다.
현재 다섯 묶음의 준비 판정은 미완료다.

## 상세 패키지 보강 이후

위 도구 표는 Q09 조사 시점의 PATH 결과다. 이후 예제용 Kotlin 2.4.21·Dart 3.13.7·TypeScript 6.0.2를
`.local/knowledge-sdks`에 격리해 추가했고 [다섯 언어 100개 사례](../../evidence/2026-10-28-topic-examples-04.json)를 실행했다.
전역 PATH·앱 SDK/버전은 바꾸지 않았다. macOS Swift·JVM·Dart VM·Node 검사를 앱 빌드로 표시하지 않는다.
[상세 패키지 목차](../index.md)의 실행/미실행 범위와 [재실행 절차](../../README.md)를 따른다.


--- knowledge/wiki/shared/ui-state-navigation.md ---

---
title: UI 상태·탐색·접근성 이식 기준
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F04", "W01", "W02", "E12", "E16", "E30", "E33", "E36"]
---

# UI 상태·탐색·접근성 이식 기준

화면을 그대로 문법 변환하기 전에 상태 소유자·입력·탐색·효과를 분리한다.
기능별 서버 계약은 유지하고 화면 구조·키보드·시스템 뒤로 가기는 플랫폼에 맞춰 구현한다.
다음은 원본 관찰에 기반한 이식 기준이며 실제 다섯 앱의 화면 검증 결과는 아니다.

## 검색·종가 상태

| 사건 | 유지할 상태와 효과 |
| --- | --- |
| 검색어 입력 | 입력 원문 보존, 새 요청 세대 부여, 이전 타이머/작업 정리 |
| 유효 검색 시작 | 250ms 원본 대기 규칙 적용, 현재 요청의 loading 표시(F04) |
| 응답 완료 | 성공/빈 목록/HTTP 실패/디코딩 실패를 구분. 현재 세대만 목록·오류·loading 변경 |
| 종목 선택 | 선택 ID·시장·통화 보존, 관련 종가 요청을 소유한 상태에서 시작 |
| 수동 단가 입력 | dirty/편집 상태를 기록. 늦은 자동 가격이 덮어쓰지 않음(F04) |
| 화면 이탈 | 요청 수명과 초안 보존 수명을 구분. 취소 후에도 서버 거래 결과 확인은 별도 |

SwiftUI 모델과 Compose 상태 소유자, Flutter State와 React effect에 같은 사례를 대응한다.
관찰 가능한 모델의 반영·저장 가능한 상태·dispose/unmount는 같은 용어로 뭉뚱그리지 않는다(E12/E16/E30/E33/E36).

## 입력·탐색

- 금액은 편집 중 문자열로 보관하고 완료된 값으로 검증한다. 빈 문자열·입력 중 소수점·0·null을 구분한다.
  원본 거래일 검증은 오늘을 서울 기준으로 계산하며 종가 baseDate의 문자열 검사와 다르다(W02/F01 문서 참조).
- 기존 경로의 기능과 접근 권한을 W01 라우트 근거에서 확인한다. 회원 전용·관리자 화면·404·리다이렉트를 보존한다.
  라우트 이름과 서버 API 경로가 같아야 하는 것은 아니다.
- back 제스처·Android 시스템 뒤로 가기·모달 닫기·딥링크 복귀의 대상과 초안 유지를 명시한다.
  입력 중 이탈 확인은 제품 동작을 새로 추가하는 경우 별도 결정한다.
- 웹 CSS·DOM·focus·window는 네이티브 뷰와 직접 호환되지 않는다. 표·그래프·임베드·파일 선택의 대체를 목록화한다.
- 스크린 리더 이름·입력 label·오류 연결·포커스 이동·동적 글자 크기·명암·터치 영역·키보드 겹침을 검사한다.
  비동기 로딩과 오류가 색만으로 전달되지 않도록 한다.

## 생명주기 검사

빠른 입력·국가 전환·종목 재선택·지연 응답·수동 입력 후 응답·뒤로 가기·회전/화면 재생성·
백그라운드 복귀·프로세스 재시작·네트워크 복구를 각 대상에서 실행한다.
상태를 무조건 영구 저장하거나 화면이 사라지면 모두 지우는 정책을 기본값으로 숨기지 않는다.
[언어·플랫폼 구성](package-map.md), [검증 방법](testing-migration.md).


--- knowledge/wiki/shared/testing-migration.md ---

---
title: 다섯 플랫폼 검증과 시간 측정
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E34", "E35", "E44", "P02", "F01", "F04", "T01", "Q08"]
---

# 다섯 플랫폼 검증과 시간 측정

지식베이스 구조 검사·의미 검토·언어 예제·앱 빌드·API/DB·실제 UI는 다른 검증 단계다.
동일한 기능과 품질에서 전체 검증 완료 시간으로 효과를 비교한다.

| 단계 | 확인할 것 | 증거 |
| --- | --- | --- |
| 원문/구조 | 출처 해시·보관본·목차·문서 선택·누락 범위 | knowledge.py check/coverage, 선택/수집 검사 |
| 의미 평가 | 답변 근거·누락·모순·미확인 구분 | evals/questions.json과 별도 새 문맥의 답변. 같은 작성 문맥은 독립 평가 아님 |
| 언어/디코더 | 타입·숫자·날짜·null·취소 경계 | 고정 입력·기대값·런타임 버전·명령·결과·소스 해시 |
| 단위/상태 | 상태 전환·요청 역전·수동 값 보존·오류 대응 | 순수 상태 모델·가짜 HTTP의 지연/실패 fixture |
| 앱/화면 | 대상 OS 빌드·실행·키보드·탐색·접근성 | SDK·기기·화면 시나리오와 결과 |
| 통합 | 실제 서버 계약·인증·트랜잭션·저장 | 실험용 HTTP/DB·원본과의 고정 기준 비교 |

Android의 로컬/기기 검사(E44), RN의 JS와 네이티브/화면 검사(E34), Flutter의 단위·위젯·통합 검사(E35)를
각각 필요한 층에 적용한다. 한 층의 통과를 다른 층의 통과로 대체하지 않는다.

## 공통 fixture

[종목 계약 사례](../../contracts/stock-search-price.json)는 같은 JSON·기대 결과를 다섯 디코더에 적용할 출발점이다.
원본 API 검사와 UI의 추가 양수 검사를 구분한다. 미래 앱에 맞추기 위해 현행 기대값을 약화하지 않는다.
변경 요청에는 중복·응답 유실·동시 요청·롤백·계정 격리 사례를 추가한다.
원본 동작을 일부러 바꾸는 경우 결정·영향·기준 수정 이유를 함께 보존한다.

## 개발 시간

사전 조사·자료 보관·위키 작성·공통 계약 작성·플랫폼 구현·검증·통합·재작업·위키 갱신 시간을 나눠 기록한다.
병렬 작업의 시간 합과 전체 경과 시간을 구분한다. 구현 준비 시간과 최종 검증 완료 시간도 구분한다.
현재 초기 구축 일부는 미계측이므로 전체 절감률이나 비용 절감을 추정하지 않는다.

기능을 늘릴 때 새 API·응답 필드·상태·라이브러리·실패 사례를 먼저 해당 패키지에 반영한다.
반복된 오류는 원문 근거를 확인한 후 위키 규칙과 회귀 사례로 남긴다.
[평가 계획](../../evals/README.md), [전체 기능](../projects/daynomy/service-catalog.md).


--- knowledge/wiki/languages/typescript.md ---

---
title: TypeScript·JavaScript 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E21", "E22", "E29", "E30", "F01", "F02", "F03", "Q08"]
---

# TypeScript·JavaScript 언어 패키지

기존 웹·React Native·WebView 웹 영역이 공유하는 지식이다. DOM과 네이티브 호스트 지식은 플랫폼 패키지에 둔다.

## 데이터와 직렬화

- TypeScript 타입은 네트워크 응답의 실체를 검증하지 않는다. unknown으로 받아 type guard로
  좁히고(E29), 기능별 필수 필드·숫자 범위·enum·null 허용을 확인한다(F01/F03).
- JS number로 파싱한 큰 정수는 이미 손실됐을 수 있다(Q08). Number.isSafeInteger를 적용하고
  잘못된 ID를 문자열 변환으로 복구했다고 설명하지 않는다. BigInt는 기존 숫자 JSON 계약을
  자동 보존하는 대체재가 아니므로 직렬화 경계와 서버 계약을 먼저 정한다.
- undefined 프로퍼티는 객체 JSON에서 빠지고 명시 null은 남는다(E21/Q08).
  `??` fallback과 `||` fallback은 다르다. 0·빈 문자열·null·누락을 섞어 처리하지 않는다.
- 이진 소수 계산을 금액의 반올림 정답으로 삼지 않는다. 원문·계산·표시 단계와 decimal 정책을
  분리한다. baseDate에 `new Date()`를 적용해 현지 날짜로 표시하지 않는다(E22/Q08).
- 문자열 길이와 비교·trim 정책을 서버와 대조한다. 화면 표시는 locale을 사용해도 API 숫자에는
  천 단위 쉼표나 현지 소수 구분자를 보내지 않는다.

## 비동기와 오류

- Promise는 결과 전달 방식이다. 실제 취소는 HTTP 클라이언트에 연결한다.
  AbortController 취소와 최신 요청만 화면에 반영하는 조건을 함께 유지한다.
- React effect는 설정과 정리를 짝지으며 fetch 결과를 취소하거나 무시하는 처리가 필요하다(E30).
  응답·오류·finally의 로딩 갱신 모두 이전 요청인지 확인한다. 개발 모드 재실행을 서버 쓰기 요청의
  중복 수행으로 이어지게 하지 않는다. 사용자 거래는 명시적인 이벤트와 요청 수명으로 처리한다.
- F03의 shared refreshPromise는 공통화할 수 있지만 DOM 쿠키, RN 저장소, WebView 쿠키 환경이
  같은 것은 아니다. 실패한 refresh를 무한 재귀로 재시도하지 않는다.

## 모듈 경계

순수 모델·검증·포맷 규칙과 React hook·DOM·환경변수·스토리지·HTTP를 분리한다.
React Native에서 window/document/localStorage가 있다고 가정하지 않는다.
strict 타입 검사와 런타임 검증을 함께 사용하고 타입 단언으로 응답 검사를 대체하지 않는다.

## 필수 검사

공통 JSON 경계, 204의 빈 본문, 추가 필드·알 수 없는 enum, 응답 역전, unmount, 동시 401,
브라우저 전용 의존성 탐지를 확인한다. Q08은 Node 결과이며 RN/WebView 엔진 검증은 별도다.
[React Native](../platforms/react-native.md), [WebView](../platforms/webview.md), [공통 데이터](../shared/data-semantics.md).

## 상세 패키지

[React Native + TypeScript의 주제별 문서](../packages/react-native-typescript/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.

WebView 호스트와 브리지 경계는 [WebView 패키지](../packages/webview/index.md)를 사용한다.


--- knowledge/wiki/languages/kotlin.md ---

---
title: Kotlin 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E23", "E24", "E17", "E31", "E40", "E45", "E46", "F01", "B04"]
---

# Kotlin 언어 패키지

Android/JVM에서 사용하는 언어 지식이다. Compose·화면 수명은 Android 패키지에서 조합한다.
아래 라이브러리 구성은 이번 이식의 기본 제안이며 빌드 호환성을 검증한 선택은 아니다.

## 데이터와 직렬화

- ID는 Long으로 디코딩하되 공통 계약의 양의 안전 정수 범위를 별도로 검사한다(F01/E23).
  Long을 Double로 거쳐 파싱하지 않는다. Int로 축소하는 변환은 범위 검사 후 수행한다.
- 가격·수량·통화는 별개 값이다. JVM의 BigDecimal과 날짜 전용 타입을 사용하는 방향을 제안한다.
  서버 전송 형식은 기존 숫자 JSON을 유지하고, 십진 값의 문자열 원문에서 파싱하는 어댑터를 둔다.
  kotlinx.serialization JsonPrimitive.content는 따옴표 없는 내용을 주지만 JsonNull도 문자열 "null"을
  반환하므로 null·숫자·문자열 타입 확인을 먼저 해야 한다(E46).
- `T?`는 null 허용이다(E24). 필드 누락·null·기본값은 JSON 설정과 모델 선언까지 함께 결정한다.
  kotlinx.serialization의 explicitNulls 기본값은 true이고 false일 때 누락 처리도 달라진다(E31).
  ignoreUnknownKeys 기본값은 false다(E40). 기존 웹이 허용하는 추가 필드를 유지하려면 허용 설정과
  필수 필드 검사를 각각 고정한다. 잘못된 타입·enum을 기본값으로 조용히 바꾸지 않는다.
- 검색 길이의 UTF-16 기준과 Unicode 정규화는 공통 계약을 따른다. 문자열을 바이트 수로 잘라내지 않는다.
  JSON 라이브러리 설정·직렬화 어댑터·기대 fixture는 같은 패키지 버전으로 검사한다.

## 비동기와 오류

- suspend 호출을 썼다는 사실만으로 모든 작업이 즉시 중단되지 않는다. 취소는 협력적이다(E17).
  CancellationException을 일반 네트워크 실패로 삼켜 UI 오류나 재시도로 바꾸지 않는다.
- HTTP 기본 후보는 OkHttp다. 공식 원문의 Canceling a Call을 근거로 실제 Call 취소를 연결하되(E45),
  coroutine 취소·Call 취소·콜백의 늦은 결과 무시를 모두 어댑터 계약에 포함한다.
- 성공 HTTP라도 응답 디코딩이 실패할 수 있다. HTTP status, 업무 code, 필드 오류, 전송 실패,
  디코딩 실패, 취소, 변경 결과 미확정을 구분해 공통 오류 모델에 대응한다.
- blocking I/O와 무거운 파싱은 UI 실행 흐름에서 분리한다. UI 반영 시 최신 요청 식별자도 확인한다.

## 모듈 경계

API DTO/디코더, 순수 규칙, 저장소 인터페이스, HTTP 어댑터, UI 상태를 분리한다.
Java 원본의 DTO를 그대로 가져와 null과 예외 의미까지 같다고 가정하지 않는다.
외부 라이브러리는 Gradle 잠금과 Kotlin/직렬화 플러그인 호환 버전을 함께 기록한다.

## 필수 검사

큰 ID·정수 오버플로·소수 경계·null/누락/추가 필드·잘못된 enum·날짜·문자열 길이,
취소 후 결과 반영·동시 401·응답 유실을 공통 fixture와 대조한다.
Kotlin 컴파일러와 디코더의 실제 실행은 아직 없다. 문서 준비와 런타임 증거를 구분한다.
[Android 패키지](../platforms/android.md), [공통 데이터](../shared/data-semantics.md), [패키지 구성](../shared/package-map.md).

## 상세 패키지

[Android + Kotlin의 주제별 문서](../packages/android-kotlin/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.


--- knowledge/wiki/languages/swift.md ---

---
title: Swift 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E07", "E13", "E26", "E42", "E43", "Q08", "F01", "B04"]
---

# Swift 언어 패키지

iOS 앱과 WKWebView 호스트에 필요한 언어 지식이다. SwiftUI 수명과 화면 구성은 iOS 패키지에서 다룬다.

## 데이터와 직렬화

- ID는 Int64로 디코딩하고 공통 안전 정수 범위를 따로 검사한다. macOS Foundation 예제에서는
  큰 ID를 Int64로 보존했지만 기존 웹보다 API 허용 범위를 넓힌다는 뜻은 아니다(Q08/F01).
- Codable/JSONDecoder는 모델 디코딩 도구다(E42). 필수 필드·추가 필드·enum·통화에 관한 업무 검증까지
  자동 보장하지 않는다. 합성 Optional은 관찰 예제에서 누락/null을 모두 nil로 처리했다(Q08).
  구별이 필요한 수정 요청에는 keyed container의 존재 확인과 null 검사를 사용하는 어댑터를 둔다.
- 가격은 Decimal 기반 처리를 기본 제안으로 삼는다. Double로 먼저 변환한 뒤 Decimal로 바꿔
  정밀도가 회복된다고 가정하지 않는다. JSONDecoder가 선택한 Foundation 버전에서 십진 값을
  어떻게 읽는지는 별도로 검사한다. 기존 예제의 Decimal 검사는 문자열 연산까지의 증거다.
- baseDate는 String 또는 검증된 날짜 전용 모델로 유지한다. Date는 시각이므로 표시 시간대에 따라
  날짜가 바뀌는 문제를 피해야 한다. 서버 계약을 강화하는 달력 검증은 별도 결정으로 남긴다.
- String.count와 UTF-16 길이는 다르며 canonically equivalent 문자열은 같을 수 있다(E26/Q08).
  서버의 길이·중복 정책을 Swift 기본 비교만으로 재현했다고 판단하지 않는다.

## 비동기와 오류

- Task 취소는 협력적이다(E13). 새 검색의 Task와 이전 응답의 반영 권한을 함께 관리한다.
  await 전후에 보유한 UI 상태가 같다고 가정하지 않는다. 요청 세대 번호·선택 종목을 다시 확인한다.
- 네트워크 기본 후보는 URLSession이며 HTTPURLResponse의 상태와 Data 디코딩을 구분한다(E43).
  전송 성공과 HTTP 4xx/5xx, JSON 오류, 업무 실패, 취소를 각각 공통 오류에 연결한다.
- UI 상태 갱신의 actor 격리를 명시한다. Task를 화면 밖에서 생성했다면 소유자와 취소 시점을 정한다.
  완료한 거래의 서버 결과를 화면 이탈 때문에 실패한 거래로 바꾸지 않는다.

## 모듈 경계

Codable DTO, 순수 입력 규칙, API 프로토콜, URLSession 어댑터, UI 모델을 분리한다.
공유 모델을 참조형으로 만들 때 변경 소유자를 명확히 하고, 병렬 Task 사이 값 전달과 Sendable 제약은
선택한 Swift 언어 모드에서 컴파일해 확인한다. Swift 버전과 Xcode/SDK/지원 OS를 각각 기록한다.

## 필수 검사

Optional의 누락/null·정수·Decimal 디코딩·날짜 보존·문자열·Task 취소·UI 격리 경고를 검사한다.
Q08은 macOS Swift 예제이며 iOS 빌드·URLSession 취소·쿠키 검증 결과가 아니다.
[iOS 패키지](../platforms/ios.md), [공통 데이터](../shared/data-semantics.md), [패키지 구성](../shared/package-map.md).

## 상세 패키지

[iOS + Swift의 주제별 문서](../packages/ios-swift/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.


--- knowledge/wiki/platforms/webview.md ---

---
title: WebView 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F03", "F04", "E04", "E11", "Q08", "E21", "E22", "E37", "E47"]
---

# WebView 사전 지식

초기에는 호스트 범위·버전·제공 URL이 미정이었다. 현재 종목 검색·최근 종가 파일럿의 착수 계약은 아래에 확정했고, 실제 호스트 실행은 별도 검증한다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| W01 | Android WebView는 앱 안에서 웹을 표시하며 JavaScript 설정·앱 연결·탐색 처리를 구성한다. | 기존 웹의 요청·취소·수동 단가 동작을 유지하고 호스트의 링크·뒤로 가기·키보드와 연결한다. |
| W02 | WKWebView 개요는 HTML·CSS·JavaScript 표시, navigation/UI delegate와 configuration을 통한 탐색·설정을 설명한다. | iOS 호스트 설정과 쿠키·로그인 복귀를 별도 검증한다. Android 결과를 iOS에 그대로 적용하지 않는다. |

W01은 E04, W02는 E11의 개요가 근거다. WKWebView 개요를 읽은 것만으로 로그인·쿠키의 실제 호환을 확인한 것은 아니다.

## 구현 시 확정·실행할 항목

- 원격 웹·앱 번들 중 제공 방식, API 주소·쿠키·저장소와 개발/운영 도메인의 연결.
- Android/iOS 최소 버전, 외부 링크·뒤로 가기·앱 복귀·프로세스 재생성 정책.
- 필요한 호스트 연결 메시지와 접근 범위, 키보드·안전 영역·접근성.
- 웹 자체의 공통 검사와 OS별 호스트 빌드·화면 검증 명령.

웹 로직 재사용과 호스트 검증의 작업 범위를 구분한다. 현재는 호스트별 기초 문서 정리 단계다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

Node의 숫자·날짜·JSON 예제를 실행했다(Q08/E21/E22). Android/iOS WebView 엔진과 호스트 브리지 왕복은 별도 검사해야 한다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 호스트와 웹의 적용 계약

기존 웹 번들을 최대한 재사용하되 Android WebView와 WKWebView를 각각 호스트로 다룬다.
웹의 TypeScript 패키지에 Android의 Kotlin, iOS의 Swift 패키지를 함께 제공한다.
한 OS만 구현할 때는 새 호스트 범위를 명시해 필요한 언어만 남기며 현재 기본 묶음은 양쪽 OS다.

- 원격 URL/로컬 번들·허용 탐색 도메인·외부 링크·back/forward·딥링크 복귀를 호스트별로 정의한다.
- 웹 sessionStorage·쿠키와 네이티브 저장소의 수명·동기화를 검증한다. 브리지가 HttpOnly 쿠키를
  읽어 토큰을 복제하는 방식으로 기존 보안 계약을 바꾸지 않는다.
- Android JavaScript 연결과 WKScriptMessageHandler는 각각 다른 호스트 API다(E04/E37).
  메시지 버전·메서드 allowlist·payload 스키마·요청 ID·응답/오류·호출 origin을 좁혀 검증하도록 제안한다.
- 임의 URL에서 브리지를 쓸 수 있게 하지 않는다. 원문 내부 JavaScript를 네이티브 실행 권한으로 취급하지 않는다.
- 외부 OAuth user-agent 원칙과 기존 서버 callback 계약을 대조한다(E47). 웹 로그인 화면이 표시된다는
  사실만으로 네이티브 로그인 세션 연결까지 검증됐다고 하지 않는다.
- 웹 키보드·safe area·파일 선택·이미지·임베드·접근성·WebView 프로세스 복구를 양쪽에서 검사한다.

## 빌드와 인수 계획

웹 번들/잠금 파일과 두 호스트의 SDK·지원 OS·엔진 정보를 기록한다.
웹 자체 빌드·상태 검사를 먼저 통과시키고 Android/iOS 호스트 빌드와 기기 검사를 따로 수행한다.
검색·수동 단가·쿠키·외부 링크·뒤로 가기·브리지 잘못된 메시지·앱 재시작을 실제 호스트에서 재현한다.
현재 Node/웹 디코더 예제만 실행했으며 WebView 호스트 빌드는 없다.

[웹 언어](../languages/typescript.md), [Kotlin](../languages/kotlin.md), [Swift](../languages/swift.md),
[인증·저장](../shared/auth-storage.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[WebView + TypeScript/Kotlin/Swift 주제별 문서](../packages/webview/index.md)를 공통·기능 계약과 함께 선택한다.

## 2026-10-28 종목 검색·최근 종가 파일럿 착수 결정

사용자가 지식베이스를 활용한 테스트 작성자 → 별도 구현자 → 별도 검증자를 요청했다.
범위와 공통 인터페이스는 [WebView 계약](../../../spec/webview/README.md)에 고정한다.
이는 전체 서비스 또는 로그인·배포 승인으로 확대하지 않는다.

- 웹 TypeScript6.0.2 ESM, Node22.23.1; Android min26/compile·target35, iOS15.0 소스 타깃이다. iOS Xcode/시뮬레이터는 현재 호스트에 없으며 빌드·기기 성공을 뜻하지 않는다.
- 웹은 로컬 HTTP 제공 + `/api/` 동일 origin 프록시다. 기본 웹18082/API18081, 검증용 API18091; Android 에뮬레이터는10.0.2.2를 사용한다. release는 명시 설정한 단일 HTTPS origin을 사용한다.
- 원본 웹 디코더·JS trim·250ms 취소·요청 세대·수동 단가 보존 계약을 재사용한다. UI 상태와 네이티브 탐색 정책을 분리한다.
- 공개 조회만 제공하며 로그인·OAuth·토큰 복제는 구현하지 않는다. 특권 JavaScript 브리지도 필요하지 않아 노출하지 않는다. 쿠키는 웹 엔진 저장소에 유지하고 native로 추출하지 않는다.
- 내부 scheme/host/effective port만 탐색; 외부 HTTPS는 사용자 행동에서 OS 브라우저로 열고 임의 scheme/팝업/SSL 우회는 거절한다. 웹 history 우선 back과 사용자 재시도/프로세스 복구를 각 호스트에 구현한다.
- 초안은 화면 background에서 유지하고 요청을 취소한다. 프로세스 종료 후 거래 입력의 영구 복원을 보장하지 않는다. 실제 회전/복원·입력/키보드·쿠키 실행 결과는 별도로 기록한다.
- 웹은 `npm test`(설정은 독립 테스트 작성자가 작성), Android는 별도 프로젝트 assembleDebug 및 독립 정책/기기 검사, iOS는 순수 Swift 정책과 Xcode 앱 빌드/기기를 구분한다. 테스트 해시와 구현 해시를 기록한다.

`packs.json`의 documented는 이 제한된 파일럿의 착수 계약이 문서화됐음을 뜻한다.
원본 의미·WebView 엔진·호스트 실행 검증 완료 상태가 아니다. 다른 기능은 approved_features 경계로 막는다.


--- knowledge/wiki/packages/webview/index.md ---

---
title: WebView + TypeScript/Kotlin/Swift 상세 지식 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["DX01", "DX03", "DX04", "DX09", "DX10", "P02"]
---

# WebView + TypeScript/Kotlin/Swift

기존 웹을 옮길 때 필요한 언어 의미와 플랫폼 경계를 함께 읽는 지식 묶음이다. 코드 라이브러리나 설치 가능한 앱 패키지는 아니다.
공통 계약·DAYNOMY 기능 문서를 먼저 읽고 아래에서 해당 작업의 주제를 선택한다.

## 주제별 문서

| 문서 | 확인할 내용 |
| --- | --- |
| [타입·null·JSON](types-and-json.md) | 누락/null/기본값, unknown 필드, 경계 디코딩 |
| [숫자·금액](numbers-and-money.md) | 안전 정수 ID, 이진 소수, 정밀도·반올림 |
| [날짜·Unicode](dates-and-unicode.md) | 날짜 전용 값과 시각, UTF-16/문자/바이트, 공백 |
| [컬렉션·모델 복사](collections-and-models.md) | 얕은 복사, 공유 참조, UI 스냅샷 |
| [비동기·취소](async-and-cancellation.md) | 실제 작업 취소, 늦은 응답, 요청 세대 |
| [상태·탐색·수명](state-and-navigation.md) | 상태 소유자, 화면 전환, 정리 시점 |
| [오류·트랜잭션](errors-and-transactions.md) | 오류 분류·자원 정리, 서버 원자성, 불확실한 결과 |
| [인증·저장소](auth-and-storage.md) | 쿠키/CSRF, 세션, 민감정보와 호스트 경계 |
| [모듈·의존성·검증](modules-and-testing.md) | 의존성 격리, 실제 실행과 통합 미검증 구분 |

## 코드와 실행 범위

각 문서는 실패하는 변환, 적용 코드/설계, 경계 사례와 근거를 담는다. `실행 가능한 전체 예제`로 연결한 파일의 assertion만 실제 검사에 포함된다.
UI·HTTP·저장소·DB 어댑터 스니펫은 해당 앱에 맞춰 연결할 설계 예시이며 독립 컴파일·통합 성공을 뜻하지 않는다.

예제 환경: **TypeScript 6.0.2 · Kotlin 2.4.21 · Swift 6.3.3**. 이 버전은 예제 실행을 위한 고정값이며 앱의 지원 버전 결정이 아니다.

TS 브리지 스키마와 Kotlin/Swift 순수 origin 정책만 실행. 실제 호스트 origin 획득·브리지 바인딩은 미실행.

기존 TS/Kotlin/Swift 예제에서 브리지 관련 사례를 재사용한다. WebView만의 추가 실행 수로 중복 집계하지 않는다.
[전체 실행 기록](../../../evidence/2026-10-28-topic-examples-04.json)은 언어별 명령·종료 코드·결과·소스 해시를 담는다. 다섯 언어 합계 100개이며 플랫폼 통합 검사는 포함하지 않는다.

```sh
python3 scripts/knowledge.py context --feature stock-search-price --platform webview
python3 scripts/knowledge.py package --package webview --topic async-and-cancellation
```

앱 버전·라이브러리 잠금·실제 HTTP/DB·화면·기기 검증·독립 의미 평가가 남아 있다.
[구축 현황](../../../STATUS.md), [공통 검증 기준](../../shared/testing-migration.md), [전체 목차](../../index.md).


--- knowledge/wiki/packages/webview/types-and-json.md ---

---
title: webview — 타입·null·JSON 디코딩
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E04", "E37", "E57", "F01", "F03", "DX04", "DX09"]
---

# 타입·null·JSON 디코딩

## 웹 JSON과 호스트 메시지의 경계를 각각 검증한다

기존 API 응답은 TypeScript guard로 검증하고(F01/F03), 호스트 브리지는 별도 버전/메서드/payload 스키마를 갖는다.
브리지 메시지가 앱 내부에서 왔다고 가정하지 않는다. 출처 검사는 JSON 안의 origin 문자열로 대체할 수 없다(E57/E37).

## 실패하는 변환

```typescript
const message = JSON.parse(raw) as any;
native[message.method](message.payload); // 임의 메서드 호출 경계가 된다.
```

## 실행한 최소 프로토콜

```typescript
type Envelope = { v: 1; id: string; method: 'close'; payload: Record<string, never> };
function decodeBridge(value: unknown): Envelope {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('MESSAGE_TYPE');
  const input = value as Record<string, unknown>;
  if (input.v !== 1 || typeof input.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(input.id) || input.method !== 'close') {
    throw new Error('MESSAGE_SCHEMA');
  }
  if (!input.payload || typeof input.payload !== 'object' || Array.isArray(input.payload) || Object.keys(input.payload).length !== 0) {
    throw new Error('PAYLOAD_SCHEMA');
  }
  return { v: 1, id: input.id, method: 'close', payload: {} };
}
```

이 예제는 close 한 가지 동작만 허용하며 payload도 빈 객체만 허용한다. 실제 서비스에 메서드를 추가할 때는
기능별 권한/출처/필드 스키마/응답/오류를 각각 정의한다. 이 프로토콜이 기존 DAYNOMY 구현이라는 뜻은 아니다.

| 메시지 | 결과 |
| --- | --- |
| v1·유효 id·close·빈 payload | 허용 |
| v2 또는 eval 등 알 수 없는 method | 거절 |
| 잘못된 id·배열/root null | 거절 |
| close에 임의 code payload | 거절 |

네이티브도 같은 의미를 독립 검증해야 하며 웹 guard만 신뢰하지 않는다.

## 경계 사례와 확인 범위

실행: TS 메시지 decode의 정상 close·unknown method·version·payload 거절. Android/WK 네이티브 메시지 수신 통합과 왕복은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/numbers-and-money.md ---

---
title: webview — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["F01", "P02", "E23", "E42", "DX04", "DX09"]
---

# 숫자·금액·반올림

## 브리지로 숫자를 넘길 때도 손실 위치를 확인한다

JS number → JSON → Kotlin/Swift 숫자 변환은 정밀도를 되살리는 과정이 아니다.
웹의 Number.isSafeInteger 한도와 거래 금액 precision을 넘는 값은 protocol에서 표현/범위를 먼저 결정한다(F01/P02).

## 실패하는 변환

```typescript
native.postMessage(JSON.stringify({ id: Number('9007199254740993') }));
// 호스트 Long/Int64가 크더라도 JS가 이미 반올림한 ID를 복구하지 못한다.
```

## 적용 예

```typescript
function bridgeAssetId(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('ID_RANGE_OR_TYPE');
  }
  return value;
}
```

금액의 브리지 문자열 표현을 새로 정하더라도 서버 숫자 JSON과 같은 계약이라고 부르지 않는다.
호스트와 웹이 둘 다 계산을 맡으면 반올림/통화/환율 정책이 갈라질 수 있으므로 업무 계산의 소유자를 정한다.
예를 들어 웹이 화면 입력을 소유하고 호스트가 외부 링크/탐색만 맡으면 금액 브리지 자체를 줄일 수 있다.

| 검사 | 기대 |
| --- | --- |
| 안전 정수 한도 | JS와 호스트에 같은 한도 적용 |
| 잘못된 문자열 ID | 암묵 변환 없이 거절 |
| 소수 가격 | 원문·파싱·전송·표시 경로별 precision 확인 |
| 금액 protocol 변경 | 버전·양쪽 어댑터·서버 계약 영향 기록 |

## 경계 사례와 확인 범위

JS 안전 정수 예제는 실행했다. 호스트별 금액 JSON 왕복과 실제 브리지는 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/dates-and-unicode.md ---

---
title: webview — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E22", "E26", "G11", "B04", "DX04", "DX09"]
---

# 날짜·시간대·Unicode

## 웹과 호스트가 다른 날짜/문자열 의미를 가질 수 있다

웹 baseDate를 호스트 Date/Instant로 바꾸고 다시 웹에 넘기는 과정에서 날짜가 이동할 수 있다(B04/E22).
문자열 길이·동등성도 JS UTF-16, Swift Character/canonical equality, Kotlin의 문자열 처리 사이에서 다르다.

## 실패하는 변환

```typescript
postToHost({ baseDate: new Date(api.baseDate).toISOString() });
// 달력 날짜를 시각 계약으로 변환한다.
```

## 적용 메시지 예

```json
{"v":1,"id":"price_1","method":"showPriceDate","payload":{"calendarDate":"2026-10-28"}}
```

이 메시지는 날짜 의미 설명용 제안이며 현재 실행한 close-only 프로토콜에는 포함되지 않는다.
새 method를 허용하려면 양쪽 allowlist와 payload 검사를 추가하고 별도 fixture를 만든다.

| 값 | 확인한 언어 의미 |
| --- | --- |
| 😀 | JS/Kotlin UTF-16 길이 2, Swift Character 1 |
| e+결합 악센트 / é | Swift 동등 가능, JS 단순 비교는 다름 |
| NBSP 양쪽 삼성 | Kotlin trim/Rust trim과 Java strip의 차이 있음 |

경로·검색·닉네임·브리지 id를 표시 문자열과 동일한 정규화 규칙으로 일괄 처리하지 않는다.

## 경계 사례와 확인 범위

언어별 작은 문자열/시간대 예제는 실행했다. 브리지 날짜 method와 실제 OS 표시 왕복은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/collections-and-models.md ---

---
title: webview — 컬렉션·변경 가능성·모델 복사
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E21", "E54", "E04", "E11", "DX04", "DX09"]
---

# 컬렉션·변경 가능성·모델 복사

## JSON 메시지는 메모리 객체 공유가 아니라 직렬화 경계다

웹의 객체를 호스트로 전송하면 별도의 값이 된다. 참조 identity·클래스 메서드·undefined 등은 유지되지 않는다(E21).
반대로 웹 내부 spread와 readonly는 얕은 복사/타입 제약일 뿐이다(E54).

## 실패하는 변환

```typescript
const pending = { id: 'x', payload: model };
postToHost(pending);
model.price = 2;
// 호스트가 같은 객체를 참조하며 자동으로 바뀔 것이라고 가정
```

## 적용 계약 예

```typescript
type MessageState = {
  id: string;
  version: 1;
  payloadSnapshot: string; // 검증한 값의 직렬화 결과
};
```

프로토콜의 요청/응답은 id로 연결하고, payload의 스냅샷 시점과 세대·시간 제한을 명시한다.
같은 id 재사용·페이지 재생성·네이티브 복구 후 오래된 응답은 거절한다.

복잡한 포트폴리오 상태 전체를 웹/호스트 양쪽에 복제하기 전에 기능의 소유자를 정한다.
가능하면 기존 웹이 모델/화면을 소유하고 호스트는 좁은 네이티브 기능만 맡는 구성을 먼저 검토한다.

## 경계 사례와 확인 범위

JS alias/shallow copy는 실행했다. 메시지 스냅샷·호스트 모델 복제·요청 id 재사용 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/async-and-cancellation.md ---

---
title: webview — 비동기·취소·요청 경쟁
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "E04", "E37", "E30", "DX04", "DX09"]
---

# 비동기·취소·요청 경쟁

## 페이지 이탈 후 브리지 응답과 네트워크 응답을 모두 다룬다

웹의 AbortController는 호스트 작업을 자동 취소하지 않는다. 호스트의 cancel도 이미 서버에 적용된 거래를
롤백하지 않는다(E19). 각 작업의 취소·응답 무시·결과 확인 프로토콜을 별도로 정한다.

## 실패하는 변환

```typescript
window.addEventListener('pagehide', () => controller.abort());
// 호스트가 진행하는 작업과 서버 거래도 취소됐다고 간주
```

## 적용 흐름 예

```text
요청: pageGeneration + requestId + method + validatedPayload
취소: cancel(requestId) 지원 여부를 method별로 선언
응답: 현재 pageGeneration이며 살아 있는 requestId만 반영
변경 결과 미확정: 조회/중복 방지 계약으로 확인
```

현재 실행한 TS Gate는 오래된 결과/폐기 후 반영을 막는 순수 모델이다.
브리지 cancel을 구현한다면 호스트가 어떤 작업을 실제 중단했는지 응답 의미를 정의하고 권한도 검사한다.
웹 타이머·message listener·pending map·호스트 delegate/handler 수명과 정리를 함께 검토한다.

Promise.race는 원래 작업을 취소하지 않는 관찰을 브리지 timeout에도 적용한다.

## 경계 사례와 확인 범위

실행: JS race 후 작업 완료·순수 Gate·취소 신호 wiring. 실제 host cancel과 페이지/프로세스 이탈 테스트는 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/state-and-navigation.md ---

---
title: webview — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E04", "E11", "W01", "F04", "DX04", "DX09"]
---

# UI 상태·탐색·수명

## 웹 탐색과 네이티브 back은 하나의 스택이 아니다

Android WebView와 WKWebView는 별도 호스트 API이며 탐색 delegate·외부 링크·프로세스 수명을 각각 처리한다(E04/E11).
웹 라우터의 내부 이동, 웹 history back, 네이티브 화면 닫기의 우선순위를 정한다.

## 실패하는 변환

```typescript
// Android back이 오면 무조건 window.history.back()
// 또는 모든 탐색을 외부 브라우저로 열어 로그인 복귀/웹 상태를 잃음
```

## 적용 결정표

```text
신뢰한 내부 URL → 웹 라우터/웹 history
승인된 외부 URL → 외부 user-agent, 브리지 권한 없음
닫기 요청 → 호스트 정책으로 처리, 미확정 거래 확인과 분리
페이지 재생성 → generation 변경, 과거 pending 응답 무시
```

입력 중 키보드 back·모달 닫기·웹 내부 back·호스트 닫기를 구분한다.
화면 회전·백그라운드·웹 콘텐츠 프로세스 종료 후 복원할 초안과 회원 재조회 조건도 정한다.
safe area·키보드·파일 선택·임베드·스크린 리더는 웹과 네이티브 양쪽에서 검사한다.

## 경계 사례와 확인 범위

결정표는 이식 제안이다. 실제 두 호스트의 back/탐색 delegate·프로세스 복구·UI 접근성 검사는 아직 없다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/errors-and-transactions.md ---

---
title: webview — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "R02", "E37", "E57", "DX04", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 오류 응답에도 요청 식별과 권한 경계를 유지한다

브리지 decode 실패·허용하지 않은 origin/method·호스트 기능 실패·HTTP 업무 오류·timeout·결과 미확정을 구분한다.
실패한 브리지 요청을 임의 JavaScript 실행으로 복구하지 않는다.

## 실패하는 변환

```typescript
catch (error) { webView.evaluateJavaScript(error.rawScript); }
// 신뢰하지 않은 내용을 실행 경계로 되돌린다.
```

## 적용 응답 제안

```json
{"v":1,"id":"req_1","ok":false,"error":{"code":"METHOD_NOT_ALLOWED","message":"허용되지 않은 동작"}}
```

이 응답 스키마는 제안이며 현재 close decoder의 입력 검사와 별도로 네이티브/웹 구현에 추가해야 한다.
응답에도 id·version·한 번만 완료 규칙을 적용한다. 내부 예외/토큰/경로를 그대로 전달하지 않는다.
거래의 서버 적용 상태는 HTTP 계약과 확인 API를 따르며 브리지 오류가 DB 롤백 증거는 아니다(E19/R02).

중복 요청 id, 같은 callback의 이중 실행, 이미 폐기된 웹 페이지에 도착한 응답을 실패 사례로 고정한다.

## 경계 사례와 확인 범위

입력 프로토콜의 거절 사례는 실행했다. 응답 스키마·evaluateJavaScript 호출·실제 거래/브리지 실패 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/modules-and-testing.md ---

---
title: webview — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E04", "E11", "E37", "E57", "E34", "DX04", "DX09"]
---

# 모듈·의존성·검증 방법

## 웹·Android 호스트·iOS 호스트를 독립 빌드 단위로 관리한다

WebView를 선택해도 호스트 검증은 남는다. 웹 번들/제공 URL·웹 의존성 잠금과 Android/iOS SDK·엔진·호스트 버전을 각각 기록한다.
플랫폼 API는 웹 도메인 모델에서 분리한다.

## 실패하는 구성

```text
웹 공통 코드 → Android/iOS 특권 메서드를 직접 가정
호스트 → 임의 URL 탐색과 같은 브리지 권한 공유
```

## 적용 구성

```text
web/core/       기존 모델·디코더·화면 상태
web/bridge/     versioned envelope, request registry, adapter
android/host/   trusted-origin/message/navigation/lifecycle binding
ios/host/       trusted-frame/message/navigation/lifecycle binding
```

공통 JSON fixture를 TS와 양쪽 네이티브 디코더에 적용하고, 같은 id의 왕복·timeout·탐색·프로세스 복구를 테스트한다.
웹 단위 검사와 네이티브 정책 함수는 앱 호스트 E2E를 대체하지 않는다.

```sh
python3 scripts/knowledge_topic_examples.py --output /tmp/new-bridge-topic-run.json
```

현재는 TS close protocol과 Kotlin/Swift 순수 origin 정책을 실행했다. Android/WKWebView 앱과 브리지 실제 왕복은 없다.

## 경계 사례와 확인 범위

문서의 API/version/출처·메시지·권한 경계를 먼저 고정한 후 두 호스트 기기 검사를 수행해야 한다. 실제 앱 검증으로 과장하지 않는다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


--- knowledge/wiki/packages/webview/auth-and-storage.md ---

---
title: webview — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E57", "E37", "E47", "E04", "E11", "DX01", "DX03", "DX04", "DX09"]
---

# 인증·저장소·호스트 경계

## 출처는 메시지 본문이 아니라 호스트가 관찰한 프레임에서 확인한다

Android addJavascriptInterface는 호출 프레임 origin을 확인할 수 없는 경계가 있으므로(E57)
메시지의 `origin` 필드를 신뢰하는 검사는 충분하지 않다. 임의 외부 페이지에 특권 브리지를 노출하지 않는다.
WKScriptMessageHandler도 frame/main-frame/security origin과 허용 method/payload를 함께 검토한다(E37).

## 실패하는 검사

```typescript
if (message.origin === TRUSTED_ORIGIN) runPrivilegedAction(message);
// message.origin은 공격자가 쓸 수 있다.
```

## 실행한 순수 호스트 정책

```kotlin
fun trustedBridgeOrigin(originFromHost: String, isMainFrame: Boolean): Boolean =
    isMainFrame && originFromHost == "https://app.example.invalid"
```

```swift
func trustedBridgeOrigin(_ originFromHost: String, isMainFrame: Bool) -> Bool {
    isMainFrame && originFromHost == "https://app.example.invalid"
}
```

예제의 app.example.invalid는 설명용 고정 origin이다. 실제 프로젝트에서는 호스트가 수신 API에서 얻은
scheme/host/port/main-frame 정보를 검증해 정규화해야 하며 JSON 본문에서 이 인자를 가져오면 안 된다.
이 함수만으로 addJavascriptInterface의 origin 확인 한계가 해결되지 않는다. 검증 가능한 메시지 API와
지원 버전/프레임 정책을 선택하거나 브리지를 신뢰한 제한 콘텐츠에만 노출하는 설계를 따로 검토한다.

웹 쿠키/HttpOnly·WK website data store·네이티브 저장소는 별개다. 토큰을 JS로 꺼내 복제하지 않는다.
OAuth는 외부 user-agent 원칙과 서버 callback 계약을 따른다(E47).

## 경계 사례와 확인 범위

실행: Kotlin/Swift 정책 함수의 신뢰 origin 허용·다른 origin/하위 프레임 거절, TS 메시지 스키마. 실제 수신 origin 획득과 OS 브리지 바인딩은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).


Selected source records:
B01: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/controller/StockController.java [read; 2026-10-28]
B02: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockSearchService.java [read; 2026-10-28]
B03: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/service/StockPriceService.java [read; 2026-10-28]
B04: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/dto/StockPriceResponse.java [read; 2026-10-28]
B05: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/exception/AssetErrorCode.java [read; 2026-10-28]
B06: reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy/asset/repository/StockDailyPriceRepository.java [read; 2026-10-28]
DX01: knowledge/examples/kotlin/Core.kt [read; 2026-10-28]
DX03: knowledge/examples/swift/Core.swift [read; 2026-10-28]
DX04: knowledge/examples/typescript/core.ts [read; 2026-10-28]
DX09: knowledge/evidence/2026-10-28-topic-examples-04.json [read; 2026-10-28]
DX10: scripts/knowledge_example_sdks.py [read; 2026-10-28]
E03: https://dart.dev/resources/language/number-representation [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E03/8cc19ce22d1e6fbdef980396c6c4bfcf55d80d7729fe89235e0773026db3c364.html [sha256 8cc19ce22d1e6fbdef980396c6c4bfcf55d80d7729fe89235e0773026db3c364]
E04: https://developer.android.com/develop/ui/views/layout/webapps/webview [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E04/aa3fa4dd7231f8cad30d5ee6fd1662406d94bebb78a20b20978fe19e0eb56a6a.html [sha256 aa3fa4dd7231f8cad30d5ee6fd1662406d94bebb78a20b20978fe19e0eb56a6a]
E07: https://docs.swift.org/swift-book/documentation/the-swift-programming-language/guidedtour/ [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E07/0becd1b48ee0baab2fd3432c70448f0c5edfa5fd1d36fa242aa08c4191391261.txt [sha256 0becd1b48ee0baab2fd3432c70448f0c5edfa5fd1d36fa242aa08c4191391261]
E11: https://developer.apple.com/documentation/webkit/wkwebview [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E11/60a42a0f4cfa6cfc6b841692c2ceeed1b3eae52ebda35814a9044fd5278251a0.txt [sha256 60a42a0f4cfa6cfc6b841692c2ceeed1b3eae52ebda35814a9044fd5278251a0]
E12: https://developer.android.com/develop/ui/compose/state [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E12/024da75da6c5f4e45c3c72edb15ae7efa41af1f58302ea5338b25234124eacb8.html [sha256 024da75da6c5f4e45c3c72edb15ae7efa41af1f58302ea5338b25234124eacb8]
E13: https://github.com/swiftlang/swift-book/blob/main/TSPL.docc/LanguageGuide/Concurrency.md [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E13/a01fcb1120386332272c41321c3e2a05b8d34d781d4abb7083c398bc8ee8853a.txt [sha256 a01fcb1120386332272c41321c3e2a05b8d34d781d4abb7083c398bc8ee8853a]
E16: https://api.flutter.dev/flutter/widgets/State/setState.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E16/81aabfe03c03e6d98ee0fd6115841cc4a776b8b721ef6b6a10897c20d8cfdae7.html [sha256 81aabfe03c03e6d98ee0fd6115841cc4a776b8b721ef6b6a10897c20d8cfdae7]
E17: https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/cancel.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E17/3284e5f2861a2e6bf0426b449578480864ab0f4e884e9ad9910e0cd0a3e006c1.html [sha256 3284e5f2861a2e6bf0426b449578480864ab0f4e884e9ad9910e0cd0a3e006c1]
E19: https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2 [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E19/21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a.txt [sha256 21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a]
E20: https://www.rfc-editor.org/rfc/rfc8259.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E20/61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7.txt [sha256 61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7]
E21: https://tc39.es/ecma262/multipage/structured-data.html#sec-json.stringify [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E21/90683188abaf6810ff92056f8e5cd2a53fc5ff347772ed6c35b75c322aec2c81.html [sha256 90683188abaf6810ff92056f8e5cd2a53fc5ff347772ed6c35b75c322aec2c81]
E22: https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.parse [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E22/bf0a432ab6ec1fdfb42467628f3a7e55852aec875af951f74f074b9e8fcaebcd.html [sha256 bf0a432ab6ec1fdfb42467628f3a7e55852aec875af951f74f074b9e8fcaebcd]
E23: https://kotlinlang.org/docs/numbers.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E23/d8cb45cc423b44311800cd62d42463a51f1944ecd773cd91ea7e3b49f0c5297b.html [sha256 d8cb45cc423b44311800cd62d42463a51f1944ecd773cd91ea7e3b49f0c5297b]
E24: https://kotlinlang.org/docs/null-safety.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E24/b691cc0e8f41c03d56a55f330e64471081019d6dbfcdc285b5be808040b3ef6c.html [sha256 b691cc0e8f41c03d56a55f330e64471081019d6dbfcdc285b5be808040b3ef6c]
E25: https://dart.dev/null-safety/understanding-null-safety [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E25/861c28eef38c69c646e05c7b1adc139c2ab119f999faa2797f2f031b6ec24b64.html [sha256 861c28eef38c69c646e05c7b1adc139c2ab119f999faa2797f2f031b6ec24b64]
E26: https://github.com/swiftlang/swift-book/blob/main/TSPL.docc/LanguageGuide/StringsAndCharacters.md [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E26/45a009419cda5959c8cce619b3191dc5104440dddc0bdedd9c4e854ddb328b3b.txt [sha256 45a009419cda5959c8cce619b3191dc5104440dddc0bdedd9c4e854ddb328b3b]
E29: https://www.typescriptlang.org/docs/handbook/2/narrowing.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E29/054fcc2caa61dab93cae4b792d9a29fd7054653cb2a18998c034a92dff23c9b9.html [sha256 054fcc2caa61dab93cae4b792d9a29fd7054653cb2a18998c034a92dff23c9b9]
E30: https://react.dev/learn/synchronizing-with-effects [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E30/b0db0766c453856720d156cc675ff08e856b5e29b7e3b3b70397ab106f93694b.html [sha256 b0db0766c453856720d156cc675ff08e856b5e29b7e3b3b70397ab106f93694b]
E31: https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-json/kotlinx.serialization.json/-json-builder/explicit-nulls.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E31/78b3270b5e76ebaee9d176818e39f5bb3d49ad08bea24a022418b70ff5aafb88.html [sha256 78b3270b5e76ebaee9d176818e39f5bb3d49ad08bea24a022418b70ff5aafb88]
E33: https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E33/26cc2d96b4c89f13a5e54c61e76f5c65fcf19de0066a62e521db3992b4ed29cd.txt [sha256 26cc2d96b4c89f13a5e54c61e76f5c65fcf19de0066a62e521db3992b4ed29cd]
E34: https://reactnative.dev/docs/testing-overview [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E34/a6e49a001040dd9955e129e32ba709c6c7030ac7e9f8c42bc04475c9f5aa1eb3.html [sha256 a6e49a001040dd9955e129e32ba709c6c7030ac7e9f8c42bc04475c9f5aa1eb3]
E35: https://docs.flutter.dev/testing/overview [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E35/4187e13aceb96c6e4101ebc131c027d0fc4f7d56e1c93e89ca65a5e733cfd328.html [sha256 4187e13aceb96c6e4101ebc131c027d0fc4f7d56e1c93e89ca65a5e733cfd328]
E36: https://developer.android.com/topic/architecture/recommendations [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E36/c5a30ad2c9f137af9ad75a99db669b9d148ad863935ac8be6b447884df8ccc42.html [sha256 c5a30ad2c9f137af9ad75a99db669b9d148ad863935ac8be6b447884df8ccc42]
E37: https://developer.apple.com/documentation/webkit/wkscriptmessagehandler [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E37/65afc02f6194ee3d529c0fcc1c3ad3c551ca5aace10f5c4cf90ddb4b7a152b6c.txt [sha256 65afc02f6194ee3d529c0fcc1c3ad3c551ca5aace10f5c4cf90ddb4b7a152b6c]
E40: https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-json/kotlinx.serialization.json/-json-builder/ignore-unknown-keys.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E40/123e3be1a8e6e77823b2dc3156be9bf60b337ce173d8b43d2eabc670b21fd3f1.html [sha256 123e3be1a8e6e77823b2dc3156be9bf60b337ce173d8b43d2eabc670b21fd3f1]
E42: https://developer.apple.com/documentation/foundation/jsondecoder [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E42/e1a6c055b42735746eea54641e28a33c03571e0f67d57c60fb156666d3479767.txt [sha256 e1a6c055b42735746eea54641e28a33c03571e0f67d57c60fb156666d3479767]
E43: https://developer.apple.com/documentation/foundation/urlsession [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E43/72bf72d2e694a04e04d8f0e2cb240fff96839b6c3e94ad6e178cdef18ab2207c.txt [sha256 72bf72d2e694a04e04d8f0e2cb240fff96839b6c3e94ad6e178cdef18ab2207c]
E44: https://developer.android.com/training/testing/fundamentals [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E44/55c4e54316aa7cbc319e39f188cc274ce37c5707cb4b83d0fb4cdb695bc84d87.html [sha256 55c4e54316aa7cbc319e39f188cc274ce37c5707cb4b83d0fb4cdb695bc84d87]
E45: https://github.com/square/okhttp/blob/master/docs/recipes.md [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E45/001ed65e6ec707902b03025e1e5a382ec5eb766606ea7240f0eb64f59bd0ca78.txt [sha256 001ed65e6ec707902b03025e1e5a382ec5eb766606ea7240f0eb64f59bd0ca78]
E46: https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-json/kotlinx.serialization.json/-json-primitive/content.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E46/f27c04b0827013e356d6fee59fde67d7ecd85ee3e7abe1fa3b8aef314bb1af91.html [sha256 f27c04b0827013e356d6fee59fde67d7ecd85ee3e7abe1fa3b8aef314bb1af91]
E47: https://www.rfc-editor.org/rfc/rfc8252.txt [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E47/4233c0650ec7e7918c20e0fde2dc565f85e2aa2d4c18123e3cd834295c2f68d0.txt [sha256 4233c0650ec7e7918c20e0fde2dc565f85e2aa2d4c18123e3cd834295c2f68d0]
E54: https://www.typescriptlang.org/docs/handbook/2/objects.html [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E54/e888c00735b69363b49c6247fb127d0ebc6dfae5059f43c5793867149ea36b7f.html [sha256 e888c00735b69363b49c6247fb127d0ebc6dfae5059f43c5793867149ea36b7f]
E57: https://developer.android.com/privacy-and-security/risks/insecure-webview-native-bridges [read; 2026-10-28]
  pinned snapshot: knowledge/raw/external/E57/ddda0da89a60bae92ab8dd3a054cb54e01cdbea6707c138b2206295ab491afc3.html [sha256 ddda0da89a60bae92ab8dd3a054cb54e01cdbea6707c138b2206295ab491afc3]
F01: reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts [read; 2026-10-28]
F02: reference/2026-DAYNOMY-dev/frontend/src/features/stocks/types.ts [read; 2026-10-28]
F03: reference/2026-DAYNOMY-dev/frontend/src/api/client.ts [read; 2026-10-28]
F04: reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/components/PortfolioTransactionEditor.tsx [read; 2026-10-28]
F05: reference/2026-DAYNOMY-dev/frontend/tests/stocks/stocksApi.test.ts [read; 2026-10-28]
G11: knowledge/evidence/2026-10-28-unicode.json [read; 2026-10-28]
G12: experiments/knowledge-contracts/UnicodeProbe.java [read; 2026-10-28]
G13: experiments/knowledge-contracts/unicode.rs [read; 2026-10-28]
P01: spec/stock-price.md [read; 2026-10-28]
P02: spec/service.md [read; 2026-10-28]
Q01: scripts/knowledge_probes.py [read; 2026-10-28]
Q02: experiments/knowledge-probes/node.mjs [read; 2026-10-28]
Q03: experiments/knowledge-probes/swift.swift [read; 2026-10-28]
Q04: experiments/knowledge-probes/rust/src/main.rs [read; 2026-10-28]
Q05: experiments/knowledge-probes/rust/Cargo.toml [read; 2026-10-28]
Q06: experiments/knowledge-probes/rust/Cargo.lock [read; 2026-10-28]
Q07: experiments/knowledge-probes/expected.json [read; 2026-10-28]
Q08: knowledge/evidence/2026-10-28-language-01.json [read; 2026-10-28]
Q09: knowledge/evidence/2026-10-28-build-inventory.json [read; 2026-10-28]
R01: app/src/service_market.rs [read; 2026-10-28]
R02: app/src/service_portfolio.rs [read; 2026-10-28]
T01: scripts/service_core_acceptance.py [read; 2026-10-28]
W01: reference/2026-DAYNOMY-dev/frontend/src/App.tsx [read; 2026-10-28]
W02: reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/transactionForm.ts [read; 2026-10-28]
