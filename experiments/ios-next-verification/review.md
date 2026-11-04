# 다음 단계 독립 UI 소스 리뷰

검토 범위: 사용자가 승인한 현재 주요 화면의 navigation/action/data 연결. 구현·기존 테스트·기존 증거를 수정하지 않았다. 아래 항목은 실제 Simulator 재현 완료가 아니라 현재 소스의 상태 전이와 서버 DTO를 대조한 결함이다. Xcode 설치 및 실행 가능 여부는 조정자가 별도로 확인한다. 이전 핵심 API 검사 통과를 UI 검사 통과로 대신하지 않았다.

## 수정이 필요한 발견

### F1 · P1 · 뉴스 검색의 정상 결과가 빈 목록으로 표시됨

`DiscoveryView.swift:41`의 `items`는 people 이외 모든 모드에서 `payload.items`를 읽는다. 하지만 `load()`의 뉴스 검색 분기는 `/api/search/news`를 호출한다. `app/src/service_discovery.rs:290`의 해당 응답은 `content` 배열이며 일반 `/api/news`의 `items`와 다르다. 정상 검색 결과가 있어도 항목과 페이지 이동 버튼이 사라지고 “표시할 자료가 없어요”가 나온다.

재현: 소식 → 이슈 → 실제 제목 일부 입력 → 서버가 `content:[...]`를 반환. 조치: 응답을 화면 공통 페이지 형태로 정규화하거나 요청 종류에 따라 배열을 명시적으로 선택한다. `items`/`content`를 구분하는 화면 데이터 매핑 검사를 추가한다.

### F2 · P1 · 계정 전환 후 이전 회원의 자산 이력·분석이 남을 수 있음

`CalendarAnalysisView.swift:215`의 `PortfolioHistoryView`는 AppSession/accountKey를 읽지 않으며 `performance`와 `histories`를 State로 유지한다. `.task(id: retry)`만 있고 `load():294`는 기존 내용을 비우지 않는다. A의 이력 화면을 포트폴리오 navigation stack에 남기고 다른 탭에서 로그아웃 또는 B로 로그인한 뒤 돌아오면, 새 조회가 401/네트워크 실패했을 때 A의 자산 추이·거래가 그대로 남는다. 단순한 초기 로딩 중에도 이전 데이터가 노출된다.

분석 화면도 `loadSavedAnalysis():119`의 로그아웃 분기가 실제 실행되는 경우에만 초기화된다. `acceptSaved():127`는 새 응답의 `analysis`가 object일 때만 이전 결과를 교체하므로 `EMPTY` + `analysis:null`을 받은 뒤에도 이전 결과가 남는다. 화면이 사라진 동안 계정이 바뀌어 guest 단계의 task가 실행되지 않는 경로를 막지 못한다.

조치: 금융 화면의 상태와 navigation 수명을 계정키에 묶고 계정 변경 시 즉시 초기화한다. 요청은 시작 계정과 generation을 캡처하여 성공·실패·loading 업데이트 모두에 적용한다. EMPTY/null의 의미에 맞게 분석을 지우고, 같은 계정의 실패 때 과거 분석을 보존하는 정책과 구분한다.

검증: A 이력/분석 표시 → 내 정보 탭 → logout → B login → 기존 화면 복귀, B 응답을 EMPTY/401/500/지연으로 각각 변경. A 데이터가 한 프레임도 다시 표시되지 않아야 한다. 일반적인 같은 계정의 분석 실패에서 허용된 과거 결과 보존은 별도 확인한다.

### F3 · P2 · 보유 정보가 갱신된 뒤 평가 재조회가 실패하면 이전 총액과 섞임

`PortfolioView.swift:63-80`은 새 보유 목록을 먼저 저장하지만 `calculation`은 계정이 바뀌었거나 보유가 비었을 때만 지운다. 이어지는 calculate 요청 실패(`:83-91`)는 error만 설정하여 이전 평가총액·보유별 평가를 남긴다. 예를 들어 1주→2주 거래 저장 후 calculate만 실패하면 보유 수량은 2주, 상단 평가는 1주 기준인 상태로 표시된다. 이 값은 분석 화면에도 전달된다.

조치: 새 보유 snapshot과 계산 결과를 원자적으로 반영하거나 새 보유 반영 시 이전 계산을 무효화한다. 과거 값을 보존하려면 평가 당시 snapshot과 명확한 오래된 값 표시가 필요하다. 검증은 거래 저장 성공/보유 조회 성공/calculate 실패의 분리된 응답으로 수행한다.

### F4 · P2 · 관리자 뉴스 폼이 서버가 거부하는 카테고리를 제공함

`AdminView.swift:473`은 공유 `newsCategories`에서 ALL만 제거해 10개 분야를 선택하게 한다. `app/src/service_admin_news.rs:101`은 STOCK/ETF/REAL_ESTATE만 허용한다. ECONOMY 등 7개는 제목·본문·출처가 정상이더라도 저장 시400이 된다.

조치: 공개 조회 필터와 작성 가능한 카테고리 목록을 분리하고 작성 폼은 서버/원본 작성 계약의 3개만 제공한다. 검증: 새 작성과 수정 폼의 모든 선택값에 대해 실제 POST/PUT이 수용되는지 확인한다.

### F5 · P2 · 자료 탭의 내부 뉴스가 상세 화면으로 연결되지 않음

`DiscoveryView.swift:84`는 mode==news 또는 kind==NEWS일 때만 native 상세로 연결한다. `/api/contents`의 `service_discovery.rs:264` DTO는 kind 없이 `sourceType=INTERNAL_NEWS`, `url=/news/{id}`를 준다. 상대 URL은 publicLink가 거부하므로 자료 탭에서는 클릭할 수 없는 행이 된다. AssetContentsView의 내부 뉴스 분기는 별도 구현되어 있어 이 문제를 해결하지 않는다.

조치: 신뢰하는 INTERNAL_NEWS 경로를 검증하여 ContentDetailView로 연결하는 공통 라우팅을 적용한다. contents record id는 news id와 다를 수 있으므로 URL의 뉴스 id를 사용한다. 검증: `/api/contents`에서 내부 뉴스/외부 영상/잘못된 URL을 각각 눌러 정확한 대상 또는 비활성 상태를 확인한다.

### F6 · P2 · 거래 폼 검색어를 지우면 검색 spinner가 종료되지 않음

`TransactionEditorView.search()`(`PortfolioView.swift:330-344`)에서 이전 task가 취소되면 defer는 searching=false를 수행하지 않는다. 새 task는 검색어가 빈 경우 guard에서 즉시 return하며 searching을 초기화하지 않는다. 검색 요청이 진행 중일 때 검색어를 모두 지우면 spinner가 남는다. 새 검색을 시작할 때 이전 matches를 지우지 않아 국가/검색어를 바꾼 뒤에도 이전 결과가 선택 가능한 기간도 존재한다.

조치: 빈 검색어/선택 완료 분기에서 검색 상태를 명시적으로 idle로 바꾸고, 요청키/generation에 맞춰 결과와 loading을 소유하게 한다. 검증: 느린 검색 → 전체 삭제, KR결과 → US변경, 느린 실패 → 새 성공의 순서로 폼 상태를 확인한다. 독립 MarketModel 검사는 이 별도 폼 구현을 검증하지 않는다.

### F7 · P2 · 게스트 보유 삭제가 편집 중인 수량 문자열에 의존함

`PortfolioStore.adjustHolding`의 게스트 분기는 removing=true여도 먼저 `Int64(quantity)`를 요구한다. 보유 조정 창에서 수량을 지우거나 잘못 입력한 뒤 “현재 보유에서 삭제”를 누르면 삭제에 불필요한 수량 파싱 때문에 invalidTrade가 된다. 회원 DELETE 분기에는 이 요구가 없어 동작도 다르다.

조치: removing 분기에서는 수량/평균 입력을 해석하지 않고 zero/removal 이벤트를 만든다. 검증: 수량이 빈 상태와 잘못된 상태에서도 명시적 삭제 확인 후 보유가 제거되고 기존 거래 이력은 유지되어야 한다.

## SDK 빌드에서 우선 확인할 지점

현재 소스만으로 확인된 컴파일 오류라고 단정한 항목은 없다. 아래 API는 CLT syntax parse로 검증되지 않으며 실제 iOS SDK 타입 검사 대상이다.

- Swift 6 actor isolation: AppSession/Observable 모델을 사용하는 View의 MainActor 경계, ASWebAuthenticationSession callback에서 MainActor Task로 전달되는 값, continuation 단일 완료 및 취소 시 세션 해제.
- SwiftUI result builder: AdminView/PortfolioView의 긴 Form/List, Binding 배열 ForEach, 조건부 Section 및 local let 선언. 타입 검사 지연/추론 실패 여부를 실제 target build로 확인한다.
- Swift Charts의 자동 Y-domain API, LineMark/PointMark와 접근성. 한 점/빈 배열/큰 금액, 가로 화면을 확인한다.
- PhotosPickerItem의 `.task(id: photo)`, loadTransferable(Data.self), UIImage JPEG 변환과 크기 거부. 선택 취소/두 이미지 연속 선택의 오래된 결과 억제를 확인한다.
- iOS17 deployment target에 맞는 Observation environment, 두 인자 onChange, ContentUnavailableView 사용. 앱과 UI 테스트 target을 함께 build-for-testing한다.
- 실제 ASWebAuthenticationSession presentation anchor, callback scheme 등록, 취소/앱 백그라운드/복귀. host PKCE helper 검증은 브라우저 인증 완료의 증거가 아니다.

## 핵심 native UI 실행 시나리오

| 우선순위 | 흐름 | 확인할 결과 |
|---|---|---|
| 1 | A 이력/분석 열기 → 다른 탭에서 logout/B login → 복귀 | 이전 계정 데이터 즉시 제거, 지연·오류 응답에도 복원되지 않음 |
| 1 | 소식 이슈 검색 / 통합 검색 / 자료 내부뉴스 열기 | 검색 DTO별 행 표시, 올바른 뉴스 id navigation, 외부 링크 구분 |
| 1 | 게스트 종목검색 → 종가 대기 중 단가 삭제 → 수동 단가 입력 → 매수 | 삭제한 값이 종가로 덮이지 않음, 저장 후 정확한 수량/원가 |
| 1 | 회원 매수→수정→매도→삭제, 마지막 calculate만 실패 | 저장결과 중복 제출 방지, 새 수량과 과거 평가가 섞이지 않음 |
| 2 | 게스트 보유 조정/빈 수량에서 삭제/과거 거래 수정 | 원자적 replay, oversell rollback, 삭제와 거래기록 보존 |
| 2 | 관리자 뉴스3분야 작성/수정/이미지선택취소/게시/삭제 | 폼과 서버 허용값 일치, multipart와 오류 메시지, 목록 갱신 |
| 2 | 관리자 피드백 상태/인물 프로필/게시물 후보 승인거절 | mutation 후 상세와 목록이 갱신되고 부분 실패가 표시됨 |
| 2 | 월 변경·캘린더 범위·빈 보유·AI EMPTY/FAILED/409 | 이전 월/계정 데이터 혼합 없음, 실패와 빈 결과 구별 |
| 2 | 백그라운드 복귀·탭왕복·검색어 전부삭제 | 취소된 요청이 결과/오류/loading을 덮지 않고 키보드 종료 가능 |
| 2 | Dynamic Type/VoiceOver/가로 화면/차트 없음 | 버튼·입력 접근성, 오류 안내, 표의 정확한 수치 접근 유지 |

모든 시나리오는 자체 합성 fixture 계정으로 실행한다. 실사용 Google/외부 유료 provider는 별도 승인된 환경에서 구분한다. 이번 리뷰는 기존 주요 화면 범위를 확대하라는 제안이 아니라 그 화면들의 실제 연결 결함을 수정하기 위한 목록이다.

## 소스 식별

검토 시각: 2026-10-28T10:10:23.492345+00:00 UTC. 아래 해시는 리뷰 시 읽은 현재 파일 식별용이며 다른 작업자가 후속 수정하면 달라질 수 있다. 발견 본문은 수정 전 동작을 기록한다.

- `clients/ios/DaynomyIOS/DiscoveryView.swift`: `7a35b65d37aec1e185c75d734602cb877314bbc9a7f18faca04b5f552e6a4e89`
- `clients/ios/DaynomyIOS/PortfolioView.swift`: `7f30d0e888d031f79423d8dbf89b3dfc12e329b093ae7f9d1b1415cdb3338aaf`
- `clients/ios/DaynomyIOS/CalendarAnalysisView.swift`: `8b4602a40569a6677cd887286d58633e78d478233d5eab05152ef33f6ee71cdf`
- `clients/ios/DaynomyIOS/AdminView.swift`: `4350d78b4e701fe939934b8a0daab8b979aee57e44a9c94879897a1713b83857`
- `clients/ios/DaynomyIOS/AccountView.swift`: `1c28f35de216a20c852d3f94636611dab874e6b6734d630f1a8ee73d82eae980`
- `clients/ios/DaynomyIOS/Session.swift`: `fa1066d7f67a63f1187c273d6d9d04cd84dbc58b53cc200f933d73c3b14261bb`
- `clients/ios/DaynomyIOS/AuthController.swift`: `b4c2ea0685198a66ef3f59be0af3b6f9e8b0b13051ccb4202095cefb97fc795d`
- `clients/ios/DaynomyIOS/DaynomyApp.swift`: `8d007bb282d55d811336eb13eb96305dca695abe71c498eea3c254c3163dd012`
- `clients/ios/DaynomyIOS/AppShell.swift`: `41869a38b0ac7bf4b36687eb04341fb33bc56cb8234967145096fe44afd1fd9c`
- `clients/ios/DaynomyIOS/ContentDetailView.swift`: `45c621a7af48a49ef3091618530796b369cbecddc957ecd443cf7c7e0bce4e95`
- `clients/ios/DaynomyIOS/MarketView.swift`: `7471410e1defbc2d7a38b67adf5ed95598da80642a04c3a38b1dfab65af9b575`
- `app/src/service_discovery.rs`: `65bc2cf04935bfe5cab67dbd2d4570ab77a755bf189c37606a3221a8d9155b9b`
- `app/src/service_admin_news.rs`: `ab574ddf3c630ff77884a114c733a59d7f5ce6c0755adcbbbefc273d1c6b0995`

## 후속 독립 검사 기록

2026-10-28T10:11:37.236042+00:00 — 새 `NewsPresentationContract.swift`와 runner 및 red-log의 고정 SHA256 3개를 모두 대조했다. 실제 `python3 experiments/ios-next-verification/test-author/run_presentation_contract.py` 실행 결과 10 checks / failures0 / exit0. 이 검사는 helper의 content/items 분리와 관리자 허용 category3개에 한정되며 SwiftUI 화면이 helper를 실제 사용하는지, 나머지 상태 결함이 해결됐는지는 별도 소스 재검토가 필요하다.

읽은 추가 XCUITest 소스5개는 게스트 거래 CRUD/oversell/feedback/뉴스 상세/뉴스 검색을 다룬다. 아직 실행하지 않았다. 계정 전환 데이터 제거·평가 실패·검색 전체삭제·빈 수량 보유삭제는 이5개만으로 검증되지 않는다. sheet 닫힘을 부모 navigationbar 존재만으로 기다리면 animation race가 발생할 수 있어 테스트 작성 역할에 전달했다.
