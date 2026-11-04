# Android/Kotlin KB 전달 비교

관련 Issue: [#5](https://github.com/choiyoung69/daynomy_agent/issues/5).

## 실험 범위

현재 앱의 검색어·수동 단가 보존은 구현/테스트에 이미 존재한다. 이 실험은 과거 리뷰 R1의
검색어 소실 결함을 별도 복사본에 구성한 **통제된 회귀 재현**이다. 과거 원본 소스 스냅샷이나
현재 제품의 새 결함 수정으로 표현하지 않는다. 실제 앱 소스는 변경하지 않는다.

[과거 리뷰](../android-native/evidence/review-initial.md),
[당시 red 기록](../android-native/evidence/review-regression-red.json),
[고정 회귀 테스트](../../clients/android/market-core/src/test/kotlin/org/daynomy/market/MarketControllerRegressionTest.kt)를 기준으로 삼는다.

## 고정 조건

- 입력: 같은 구성된 MarketController.kt, Models.kt, 작업 설명, 기존 회귀 테스트 전체.
- 실패 구성: clearSelection에 query 초기화 한 항목만 추가. historical-input.diff 참조.
- 완료 기준: 검색어 원문 보존, 선택/가격 초안만 초기화, 250ms 후 기존 검색어로 재조회.
  기존 취소·수명·단가 보존·JSON 경계 회귀를 유지한다.
- 모델: 앱 하위 에이전트 gpt-6.1-sol / medium, fork_turns=none.
- A: 기존 context --require-ready의 Android stock-search-price 조합(18문서).
- B: 기능 문서 + Android 상태/탐색 + 비동기/취소(3문서).
- 두 조건 모두 다른 결과·외부 자료를 읽지 않고 제공 입력으로 수정 소스를 생성한다.
- 조정자가 동일 Gradle 환경에서 실제 JVM 검사를 실행한다. 구현자는 검사를 실행했다고 주장하지 않는다.
- 단일 사례이며 실행 순서·캐시 효과·전달 실패와 준비 비용을 결과 보고서에 명시한다.

## 실행과 보존

저장소 루트의 .local/android-kb-ab-20261104에 격리 프로젝트·입력·원시 응답·로그를 보관한다.
개인 세션 링크·원시 사용량 식별자·로그·호스트 정보는 Git에 올리지 않는다.
공개본에는 구성한 입력 diff·수정 diff·확인된 집계와 제한만 남긴다.

이 실험은 전체 Android 앱·화면·기기·서버/DB 검증이나 세 병목 전체 해결을 뜻하지 않는다.
향후 실제 새 기능·복수 사례에서 유효성과 전체 비용을 확인해야 한다.

## 결과 읽기

[보고서](../../runs/023-android-kotlin-kb-ab.md), [공개 집계](results.json), [독립 검토](validation.json)를 함께 본다.
A.diff와 B.diff는 격리된 실패 입력을 고친 결과이며 두 파일은 동일하다.
구현 구간의 총 토큰은 A 136,463개, B 99,308개이며 각각 JVM 105개를 통과했다.
별도로 발생한 기준 조사·전달 실패·최종 검토·조정 비용은 이 절감률에서 제외됐으므로 전체 비용 절감으로 해석하지 않는다.
원시 로그·비공개 세션 식별자·개인 설정은 공개 집계에 포함하지 않는다.
