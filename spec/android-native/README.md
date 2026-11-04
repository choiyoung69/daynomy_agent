# Android 네이티브 — 종목 검색·최근 종가 파일럿

사용자 확정: 2026-10-28, 첫 범위는 종목 검색과 최근 종가 및 연결 화면이다.
거래 저장·로그인·환율·전체 앱·배포는 이번 범위에 포함하지 않는다.
원본은 reference/2026-DAYNOMY-dev 읽기 전용, 연결 대상은 기존 Rust app/이다.

## 계약과 책임

- [검색](search.md), [가격](price.md), [독립 검증 계획](verification-plan.md)을 함께 사용한다.
- 확정 시그니처는 clients/android/market-core/src/main/kotlin/org/daynomy/market/Models.kt다.
  각 기능 문서의 제안 코드보다 이 공통 인터페이스를 우선한다.
- 검색 StockSearchClient / 가격 StockPriceClient는 HttpTransport.get의 본문을 검증한다.
  HttpTransport는 비성공 HTTP를 ApiException(status, optional code, message), 전송 문제를 IOException으로 전달한다.
  취소 예외는 일반 실패로 감추지 않는다. 필수 성공 JSON 위반은 ResponseFormatException이다.
- 숫자 ID는 실제 JSON 숫자이고 정확한 십진수 값이 양의 안전 정수 범위여야 한다. 1.0/1e0 허용.
  원본 JS에서 반올림된 소수의 잘못된 수용은 복제하지 않는 명시적 Android 방어 매핑이다.
- market은 허용 문자열 enum만, currency는 KRW/USD만 그대로 사용하고 나머지는 코드 .US 접미사 fallback이다.
  원본의 String(market) 강제 변환과 malformed currency 무검사에 대한 의도적인 Android 방어 매핑이다.
- 가격은 JSON 숫자 원문 BigDecimal로 보존하며 Double 변환이 유한한 범위인지 확인한다.
  날짜는 원본처럼 문자열이며 달력 유효성 강화는 하지 않는다. API 계층은 0/음수 가격을 읽고 UI가 거절한다.
- price.assetId와 요청 ID 일치를 새로 강제하지 않는다. 요청 세대와 선택 상태로 늦은 응답을 막는다.

## 연결 화면

Compose + ViewModel + StateFlow. 검색어·국가·유형·선택·단가·수동 편집 여부를 명시한다.
250ms 검색 debounce, JS trim 문자집합(BOM 제거/NEL 보존), 선택 중 검색 중단,
유형 ALL/STOCK/ETF는 받은 목록의 로컬 필터다. 서버 최대20개를 유형별20개로 바꾸지 않는다.
MarketUiState.search Ready.value에는 전체 응답을 두고 화면에서 filter를 적용한다.

선택 시 즉시 종가 조회. 성공·실패·로딩 모두 요청 세대를 확인하며 실제 OkHttp Call.cancel과 연결한다.
수동 단가는 입력·삭제 모두 dirty=true이며 늦은 가격이 덮지 않는다.
새 선택·국가 전환·선택 해제는 새 종목의 가격 초안만 reset한다. 가격 실패/비양수면 기준일을 숨긴다.
이는 실패 가격의 날짜를 먼저 설정할 수 있는 원본 UI와 구별되는 명시적 표시 정책이다.
재시도는 사용자 행동으로만 한다. 거래 저장 버튼은 구현하지 않는다.

회전은 ViewModel로 초안을 유지한다. SavedStateHandle에는 검색어/국가/유형/선택 필드/단가/dirty만 저장하며
진행 중 요청이나 조회 결과를 저장했다고 가정하지 않는다. 프로세스 복원 시 필요한 조회는 새로 시작한다.
setActive(false)는 요청 취소/세대 무효화 후 초안을 유지한다. true 복귀는 현재 선택의 종가 또는 검색을 다시 요청한다.
close는 영구 종료다. 취소가 협력적이지 않은 가짜 응답에서도 늦은 결과 반영을 막아야 한다.

기본 화면은 원본의 정보 위계와 한국어 입력/오류를 따른다. 최소48dp 터치, 명시적 label, 상태와 오류의 semantics,
큰 글자/IME 가림·스크롤을 고려한다. 디자인 스킬의 웹 랜딩 패턴은 이 네이티브 유틸리티 화면에 적용하지 않는다.

## 빌드 선택

설치된 SDK35/BuildTools35.0.0과 API33 ARM64 가상 기기를 활용하는 파일럿 구성이다.
최신 버전 사용을 주장하지 않는다. AGP8.9.2 / Gradle8.11.1 / Kotlin+Compose plugin2.1.20 /
Compose BOM2025.04.01 / activity-compose1.10.1 / lifecycle2.9.0 / coroutines1.10.2 /
kotlinx JSON1.8.1 / OkHttp4.12.0. JDK21, minSdk26, compile/target35.
Gradle wrapper 배포물 SHA256과 Gradle dependency lock을 보존한다.

근거: [AGP8.9 호환표](https://developer.android.com/build/releases/agp-8-9-0-release-notes),
[Kotlin2+ Compose compiler plugin](https://developer.android.com/jetpack/androidx/releases/compose-kotlin),
[Compose BOM](https://developer.android.com/develop/ui/compose/bom/bom-mapping).
호환표 읽기와 실제 빌드 성공은 별도 기록한다.

## 실험과 완료 기준

문서 → 독립 테스트 → 빈 구현의 실제 실패/테스트 해시 고정 → 구현 → JVM/HTTP/APK/기기 검사 → 독립 코드 리뷰 → 수정/재검증.
기능별 선행 조건을 지키며 검색/가격 구현을 병렬 배정한다. 앱 서브에이전트는 root가 배정하며 프로그램은 준비 작업·상태·시간·해시를 기록한다.
완료 보고만으로 승인하지 않는다. 테스트 작성자가 구현 리뷰를 맡지만 자신의 테스트 해석을 독립 인증했다고 표현하지 않는다.
명세·테스트 수정이 필요하면 원본 근거/이유를 기록하고 기존 red 실행과 해시를 보존한다.

측정 시작은 최초 중앙 계측 2026-10-28 08:05:15 UTC다. 그 이전 사용자 요청/첫 도구 실행 수 초는 미계측이다.
SDK/의존성 준비·명세·테스트·구현·검증·리뷰·재작업을 포함하고, 작업 시간 합과 실제 경과 시간을 구별한다.
순차 대조 실행이 없으므로 과거 2.5배나 백엔드 측정치를 이번 속도 향상으로 환산하지 않는다.
