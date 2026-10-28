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
