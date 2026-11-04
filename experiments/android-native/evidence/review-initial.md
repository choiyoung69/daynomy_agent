# Android 파일럿 초기 독립 구현 검토

- 검토 UTC: 2026-10-28 08:40경 시작, 2026-10-28 08:44:08 UTC 기록 종료.
- 상태: **revise / 최종 승인 보류**. 현재 실행 중인 JVM/APK/기기/Rust·DB 결과의 최종 해시 대조 전이다.
- 역할: 구현자와 분리된 코드 검토자. 이 역할이 최초 49개 기준과 기기 5개를 작성했으므로 자기 테스트 기대값을 별도 독립 인증한 것은 아니다.
- 읽기 순서: `.local/android-pilot/knowledge-v1/{search,price,integration}/context.md`와 use receipt → 확정 명세 → production source. 해당 역할이 예전에 원본을 직접 대조한 기록은 verification-plan에 있다. 이번 검토 중 새 웹 조회·서버/DB/Gradle 실행은 없다.

## 수정 필요

### R1 [P2] 종목 변경에서 검색어를 보존해야 함

`clients/android/market-core/src/main/kotlin/org/daynomy/market/MarketController.kt:58`은 clearSelection에서 `query = ""`를 함께 설정한다. 검색 → 선택 → 종목 변경을 하면 입력했던 검색어가 사라지고 빈 화면으로 돌아간다.
원본 `PortfolioTransactionEditor.tsx`의 종목 변경 handler(약 375–391행)는 selected/단가/편집 flag/기준일만 reset하고 keyword는 유지한다. 공통 `spec/android-native/README.md`도 새 가격 초안 reset으로 범위를 정한다.
query reset을 제거하고 기존 검색어로 다시 250ms 검색하도록 수정해야 한다. 원래 49개 기준은 변경하지 않았다.
추가 `MarketControllerRegressionTest.kt`의 검색어 보존 사례를 현재 구현 대상으로 작성했다. 즉시 응답 fake와 finally close를 써서 실패해도 대기 작업이 남지 않는다. 조정자가 수정 전 red → 수정 후 재검사한다.

### R2 [P2] 필수 KB 문서 집합을 검증기가 직접 확인해야 함

`scripts/android_knowledge.py:48-71`은 manifest 안에 남아 있는 documents/source_records만 검사한다. `agents/android-native.json`이 해당 task에 요구한 문서 집합이나 manifest.task/feature/platform 일치 여부를 비교하지 않는다.
따라서 필수 문서 한 개와 대응 usage 항목을 manifest/usage 양쪽에서 빠뜨리면, 남은 문서 hash와 covered 집합이 일치해 통과할 수 있다. 이는 읽거나 이해했는지 검증하는 문제가 아니라 **필수 입력 누락을 기계적으로 막는 계약**의 빈틈이다.
검증 시 현재 task의 필수 문서 집합·출처 집합과 manifest를 대조하고, 조정기가 기대 task를 전달하거나 task-경로 일치를 확인해야 한다. 누락 packet/file/hash/use map은 최종 인수에서도 다시 확인할 것을 권한다.
현재 정상 packet에는 검색 3개/가격 4개/통합 5개 문서와 각 usage 항목이 실제로 존재한다. 현재 누락이 발생했다는 보고는 아니며, 잘못된 입력을 받아들이는 검증 경로의 지적이다.

## 실행으로 확인할 잠재 경계

### R3 검색 ID의 JSON 숫자 문법

`StockSearchClient.kt:49-52`는 JsonPrimitive를 BigDecimal로 바로 파싱하므로 `+1`, `01`, `1.`처럼 BigDecimal에서는 해석 가능하지만 JSON 숫자가 아닌 토큰을 직접 차단하지 않는다. 가격 디코더는 `PRICE_JSON_NUMBER`로 이를 차단한다.
실제 kotlinx JSON 1.8.1 tree parser가 이런 토큰을 앞서 거절하는지는 이 정적 리뷰만으로 단정하지 않는다. 조정자의 요청으로 추가 regression 파일에 검색/가격 숫자 문법 사례 2개를 더 작성했다(총 3개 함수). 조정자가 원시 JSON으로 짧은 실제 probe를 실행하고 수용되면 같은 문법 guard와 추가 회귀 사례를 넣어야 한다. 원본 JS JSON.parse와 고정 JSON 계약은 잘못된 숫자 문법을 허용하지 않는다.

## 코드에서 확인한 정상 대응

- 검색 요청은 UTF-8 query 인코딩, KR country 생략, US 명시이며 API client 자체 trim 없음. UI에서 JS trim/250ms를 적용한다.
- 디코더는 전체 배열 검증, 정확한 safe integer 값, 날짜 String 보존, BigDecimal 원문 가격, currency fallback 및 엄격한 문자열 market의 명시적 차이를 유지한다.
- core는 별도 검색/가격 세대와 active/closed/selected guard로 성공·실패를 보호한다. CancellationException을 재던지고 불필요한 finally 덮어쓰기가 없다. 수동 편집은 빈 문자열까지 dirty를 유지한다.
- OkHttp continuation 취소를 Call.cancel과 연결하고 Response.use로 닫는다. 비성공 HTTP와 I/O·형식 실패를 분리하며 기본 클라이언트 자동 retry/redirect를 끈다. 이 정적 관찰과 실제 취소 통과 증거는 별도다.
- MarketViewModel이 controller를 소유하고 SavedStateHandle에 초안 값만 저장한다. ON_STOP은 요청을 무효화하고 ON_START에 적절한 조회를 재개한다. onCleared가 controller/client 자원을 정리한다.
- release manifest는 cleartext=false이며 Intent base_url은 BuildConfig.DEBUG 분기 안에 있다. release endpoint는 배포 불가 placeholder임을 한계로 남겨야 한다. debug는 localhost/127.0.0.1/10.0.2.2만 cleartext 대상으로 둔다.
- Gradle wrapper 배포 해시와 dependency locking이 있다. 빌드 성공은 실행 결과를 기다린다.

## 지식베이스 사용과 이력 경계

- 검색/가격 첫 구현은 gate 도입 이전이며 state에는 `legacy initial draft; knowledge audit required before acceptance`로 남아 있다. retrospective usage를 사전 강제 사용으로 바꾸어 설명하면 안 된다.
- 통합은 materialized packet을 구현 시작 전 확인하는 경로를 사용했다. 관련 applied_rules는 문서·규칙·구현의 연결 선언이다.
- `android_pilot.py`는 root 배정의 의존성/슬롯/시간 장부이며 에이전트를 실행하지 않는다. `finish implement.* --status passed`에서 packet+usage 검증을 호출한다.
- 장부의 일반 finish는 evidence 파일의 존재/해시를 저장하며 테스트 의미·사례 수·skip·최종 프로그램 hash를 스스로 판정하지 않는다. 별도 실제 검사와 독립 최종 대조가 필요하다.
- 현재 `final` 경로 자체는 과거 구현 인수 후 변경된 KB/usage/기준을 다시 검사하지 않는다. 최종 조정 시 재검사 결과와 source hash를 반드시 묶어야 하며, 자동 차단을 주장한다면 해당 재검사를 final 경로에 연결해야 한다.
- use receipt/hash는 자료 읽기나 이해를 증명하지 않는다. 코드·테스트·원본 대조로 적용 내용의 타당성을 확인한다.

## 남은 검증과 테스트 한계

- 초기49 core 기준의 조정자 green 통과 메시지를 받았으나 원시 XML 및 최종 프로그램 hash 대조는 아직 하지 않았다. 실제 기기/Rust DB 결과도 아직 최종 검토 전이다.
- backendTest 7개는 최초 구현 후 추가한 연결 인수다. 초기 test-first 49개와 분리해 보고한다.
- 최초 기기 기준은 잘못된 import 한 줄만 제거한 v2이며 assertion은 유지했다. v1·수정 사유·전후 해시는 보존한다.
- 기기 테스트는 recreation/단가 유지/404/US/filter를 다루며 실제 OS 프로세스 kill 후 복원, background/복귀, 글자 확대·TalkBack·IME 수동 인수 전체를 대신하지 않는다. SavedStateHandle 코드 존재로 이런 기기 시나리오가 실행됐다고 하지 않는다.
- 검색어 보존 누락은 기존 테스트가 발견하지 못한 오류다. 이 역할의 테스트 자체가 완전하다는 주장도 하지 않는다.

## 검토한 소스 해시

아래는 초기 검토 시점이며 수정 후 최종 검토 해시와 구별한다.

| 파일 | SHA-256 |
| --- | --- |
| `clients/android/market-core/src/main/kotlin/org/daynomy/market/StockPriceClient.kt` | `d5c01e106b3d52dedb8167ab966d4e551277f5fb51ab689344ed954f2187851a` |
| `clients/android/market-core/src/main/kotlin/org/daynomy/market/StockSearchClient.kt` | `c218f7a6c9d80040b83c74f47783d1b5932cca8f006f4e212c8b71570a2a9b17` |
| `clients/android/market-core/src/main/kotlin/org/daynomy/market/MarketController.kt` | `0eae46b6a275d5bd267e0f6d7153e97b88a5f65d5d51f2baae78421400e9910a` |
| `clients/android/market-core/src/main/kotlin/org/daynomy/market/Models.kt` | `673fc14e087949567ed3aff8b2a61b3a360061cb77bd3a5755f22f8687b61a50` |
| `clients/android/market-core/src/main/kotlin/org/daynomy/market/OkHttpTransport.kt` | `d5c89ef7f1285be0875dd66a6b4aec26a336e7a2dcfc691afc9fd1dbd1394e4d` |
| `clients/android/app/src/main/kotlin/org/daynomy/android/MainActivity.kt` | `96f6873d988423486860cd16d18d8b77e014553fbc8756398d598cc0a16f4d13` |
| `clients/android/app/src/main/kotlin/org/daynomy/android/MarketViewModel.kt` | `8717506128596a148f22b4ba3b3ce6b945b6a63f8396fbe46a306b3aebbe9d31` |
| `scripts/android_knowledge.py` | `e0b6e5f2ba6d58d2e10ec10e0fabbe68640b4cce04522518e8b5ace3eb3e97f4` |
| `scripts/android_pilot.py` | `ea400324679df9c928b60849a6d60f9cbc157ba60a5d9f69448ac962f79be70c` |
