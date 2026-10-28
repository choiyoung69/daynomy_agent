# iOS 전체 프론트 이식 지도 — 후속 계획

확인일 2026-10-28. 원본 정적 조사이며 새 기능 구현·화면 실행·HTTP/DB 검증 보고가 아니다. 현재 실제 구현 범위는 종목 검색 → 선택 → 저장된 최근 종가 → 수동 단가 보존의 첫 파일럿뿐이다. 파일럿의 테스트·검증 근거는 별도 `experiments/ios-native/test-author/frozen-tests.json`과 조정자의 실행 기록을 따른다. 아래 묶음은 후속 배정 제안이다.

조사 순서는 KB 목차·기능 문서·API 목록 → 원본 `frontend/src/App.tsx` 경로 → 해당 화면·공통 API·저장소 코드다. 지금 필요한 것은 구조 매핑이므로 외부 검색은 하지 않았다. SDK API/OAuth 구현을 확정할 때는 해당 iOS 공식 자료를 별도로 확인해야 한다.

## 기준과 준비 수준

- [서비스 지식 목록](../../knowledge/wiki/projects/daynomy/service-catalog.md)은 F01–F13·F14 보류를 연결한다. 여러 기능 문서의 `기능 계약` 절은 아직 비어 있다. 경로 목록만으로 화면의 모든 규칙이 준비됐다고 판정하지 않는다. 배정 전 [서비스 명세](../service.md), 원본 DTO·컴포넌트·테스트를 더 읽어 테스트 입력/기대값을 고정한다.
- [백엔드 실행 안내](../../app/README.md), [기존 백엔드 검증 기록](../../runs/010-three-hour-service.md)은 리그·UI·배포·F14 제외 구현과 과거 고정 소스의 로컬 검사 근거다. 이번 iOS 요청에 대해 그 검사를 재실행하지 않았다. Google·AI·S3·외부 시세 등 실제 제공자 연결은 기존 기록에서도 미검증으로 구분한다.
- [iOS 언어·플랫폼 묶음](../../knowledge/wiki/packages/ios-swift/index.md)의 숫자/날짜/취소/상태/저장소 문서를 공통으로 사용한다. Swift6.3.3 macOS 실행 근거를 iOS SDK·실기기 근거로 확대하지 않는다.
- 리그·공개 프로필·팔로우·투자 복기·공개 포트폴리오 및 F14 이메일 알림은 이 지도에서 구현 배정 대상이 아니다. 관리 화면에 섞인 리그 재계산도 제외한다. 배포 자동화는 별도다.

## 원본의 실제 화면과 네이티브 모듈

원본 경로는 `reference/2026-DAYNOMY-dev/frontend/src/App.tsx` 기준이다. 아래 `frontend/...` 경로는 모두 그 원본 폴더 안이다. 모듈 이름은 제안이며 현재 구현된 파일 이름이라는 뜻이 아니다.

| 원본 경로/표면 | 실제 컴포넌트·하위 흐름 | iOS 모듈 후보 | KB·백엔드 연결 / 준비 경계 |
| --- | --- | --- | --- |
| `/`, `/welcome` | `features/landing/LandingPage.tsx`, `HomeRoute`, 시작 후 `PortfolioPage` | AppShell + Welcome | API 없는 소개/시작 상태와 자산 홈을 구분. `startedService.ts`의 localStorage→sessionStorage 대체 처리까지 읽기. 첫 방문·기존 게스트 자산·로그인 여부에 따라 홈이 달라짐 |
| `/`의 포트폴리오 | `features/portfolio/PortfolioPage.tsx`: 보유/거래내역 탭, 평가·수익률·자산 추이, 거래 추가/수정/삭제, 보유 조정/삭제, AI 분석·투어 | PortfolioDashboard, Ledger, TransactionEditor, Performance | [계산](../../knowledge/wiki/projects/daynomy/portfolio-calculation.md) F04 → `service_market.rs`; [원장](../../knowledge/wiki/projects/daynomy/portfolio-ledger.md) F05 → `service_portfolio.rs`; [분석](../../knowledge/wiki/projects/daynomy/portfolio-analysis.md) F06 → `service_analysis.rs`. 게스트 원장은 클라이언트 상태이며 회원 API와 같지 않음 |
| 거래 편집기의 종목/단가 | `PortfolioTransactionEditor.tsx`, `features/stocks/api.ts`, `types.ts` | Market/Quote core | [종목 검색·종가](../../knowledge/wiki/projects/daynomy/stock-search-price.md), [종목·환율](../../knowledge/wiki/projects/daynomy/stocks-exchange.md) F03 → `service_market.rs`. 첫 파일럿은 이 작은 부분만 구현 대상. 환율·수량·비용·거래 저장은 후속 |
| `/news` | `features/news/issue/IssueHomePage.tsx`: 일정, 인물, 통합 피드, `PortfolioContentsPage` 자산 관련 자료 | NewsHome + PortfolioFeed | [뉴스](../../knowledge/wiki/projects/daynomy/news.md) F08, [콘텐츠·인물](../../knowledge/wiki/projects/daynomy/content-people.md) F10 → `service_discovery.rs`; 일정은 F07. 여러 독립 요청의 부분 실패 표시를 구분해야 함 |
| `/news/today` | `features/news/newslist/NewsListPage.tsx` | NewsList | F08 공개 `/api/news`, `/api/news/today`; 페이지·필터·자정·이미지 대체 검사 필요 |
| `/news/contents` | `IssueHomePage fullFeed` | ContentFeed | F10 `/api/contents`, 출처별 필터·페이지·외부 링크; `/news`와 같은 화면 모듈의 모드 차이 |
| `/news/:newsId` | `features/news/newsdetail/NewsDetailPage.tsx`, 키워드·시장 분석 | NewsDetail | F08 상세/키워드 + F06 `/api/news/{newsId}/market-analysis`; 본문 표현·외부 링크·없음/부분 오류 규칙을 테스트로 고정 |
| `/news/real-estate-loan-rule` | `RealEstateLoanRulePage.tsx` 정적 설명/영향 카드 | EditorialArticle | 해당 TSX의 정적 콘텐츠. 서버 상세 API로 간주하지 않음. 텍스트·탐색을 native article로 옮길지 콘텐츠화할지 결정 필요 |
| `/search` 및 헤더 검색 오버레이 | `features/search/SearchPage.tsx`, `components/SearchOverlay.tsx`, api/response/mapper | UniversalSearch | [통합 검색](../../knowledge/wiki/projects/daynomy/content-search.md) F09 `/api/search/news`, `/api/search/contents` → `service_discovery.rs`. 최근 검색, 출처·정렬·페이지, 여러 응답의 합치기/중복/취소 검사 |
| `/stocks/:assetId` | `features/stock-content/StockContentPage.tsx`: 기사/영상/소셜 자료, 상세 모달·임베드 | AssetContent | F10 `/api/assets/{assetId}/contents` → `service_discovery.rs`. X/Threads script와 YouTube iframe의 네이티브 대체 정책 필요 |
| `/stocks/:assetId/card-preview` | `CardDesignPreviewPage.tsx`: 고정 previewCards와 10가지 previewDesigns | 디자인 검토용 preview 후보 | 서버 종목 콘텐츠 동작이 아님. 제품 탐색에 노출할지 개발 전용으로 둘지 미결정. 디자인 예제 데이터를 실제 자료로 오인하면 안 됨 |
| `/people` | `features/people/PeoplePage.tsx` 인물/공개 글 | PeopleFeed | F10 `/api/people` → `service_discovery.rs`; 외부 미디어와 콘텐츠 페이지 표현 재사용 가능 |
| `/login`, `/signup` | `LoginPage.tsx`; signup은 login으로 redirect | Authentication | [인증](../../knowledge/wiki/projects/daynomy/auth-session.md) F01 → `service_auth.rs`. 현재 Google 서버 redirect 로그인, 별도 회원가입 폼 아님. native OAuth 귀환/쿠키 공유는 미정 |
| `/mypage` | `features/account/MyPage.tsx`: 회원정보·닉네임·로그아웃·탈퇴 | Account | [회원](../../knowledge/wiki/projects/daynomy/account.md) F02 `/api/users/me` GET/PATCH/DELETE, F01 logout → `service_auth.rs`. 닉네임은 회원 기준 유지; 탈퇴 후 늦은 응답·로컬 데이터/내비게이션 정리 필요 |
| `/about`, `/terms`, `/privacy`, `/standard` | `InfoPage.tsx`의 정적 INFO_PAGE_CONTENT | Information/Legal | 전용 백엔드 없음. 기존 문구에 브라우저 탭 임시 저장·웹 경로·리그 설명이 있으므로 native 앱 정책에 맞게 문구 검토 후 확정 |
| 전역 FeedbackWidget | `features/feedback/FeedbackWidget.tsx`, api.ts | Feedback sheet | [피드백](../../knowledge/wiki/projects/daynomy/feedback.md) F11 공개 POST `/api/feedback` → `feedback.rs`. CSRF·204·빈/초과 길이·중복 클릭·성공 후 초기화 |
| `*` | `NotFoundPage.tsx` | Navigation fallback | native 잘못된 deep link/삭제된 콘텐츠 경로에 대응. 웹 URL 404와 API 404를 구분 |

### 일정과 redirect의 예외

`/investment-calendar`는 현재 `App.tsx`에서 `/news`로 redirect한다. 실제 `InvestmentCalendarPage`는 `IssueHomePage.tsx` 안에 `embedded`로 렌더링된다. 따라서 독립 일정 탭이 원본 현행 구조라는 가정은 틀리다. 네이티브에서 독립 화면으로 추출할 수는 있으나 별도 UX 결정으로 기록한다. F07은 회원 GET `/api/users/me/investment-calendar`, 게스트 POST `/api/investment-calendar`, `service_calendar.rs`다. 월/연도·범위·선택 일정·목록/달력 모드·demo/부족 데이터 상태가 있다.

`/portfolio`→`/`, `/finance/*`→`/`, `/stocks`→`/`는 별도 기능 화면이 아니다. `/portfolio/records`→`/league/portfolio`, `/portfolio/publication`, `/membership`→`/league`는 리그 영역과 연결되므로 비리그 원장 화면으로 잘못 옮기지 않는다.

## 관리자 화면

모든 아래 화면은 원본 `AdminRoute`의 로그인 로딩 → 로그인 귀환 경로 → ADMIN 판정 → AdminShell 분기를 거친다. SwiftUI에서 버튼을 숨기는 것만으로 권한 검증이 끝나지 않으며 실제 서버의 401/403/CSRF 결과를 따로 확인해야 한다.

| 경로·컴포넌트 | iOS 모듈 후보 / 독립 묶음 | API·백엔드·주요 검사 |
| --- | --- | --- |
| `/admin` | AdminRoot | `/admin/news`로 redirect; 역할별 진입/이탈·로그아웃 정리 |
| `/admin/news`, `AdminNewsPage` | AdminNewsList | F12 뉴스 조회·상태 필터·게시/거절/삭제 → `service_admin_news.rs`; 동시 액션·404·페이지·정렬·취소 후 상태 |
| `/admin/news/new`, `/admin/news/:newsId/edit`, `AdminNewsFormPage` | AdminNewsEditor + MediaPicker | F12 생성/수정/지역별 AI 뉴스 생성·이미지 검색/생성·multipart → `service_admin_news.rs`, `service_media.rs`; 문서/이미지 권한·업로드 취소·중복 제출·부분 실패·저장 후 목록 갱신 |
| `/admin/feedbacks`, `AdminFeedbackPage` | AdminFeedback | F12 목록/상세/PATCH/DELETE → `service_admin_feedback.rs`; 상세 전환·읽음/답변 등 원본 DTO 상태를 먼저 고정; 실제 이메일 발송으로 확대하지 않음 |
| `/admin/stocks`, `AdminStockSyncPage` | AdminMarketJobs | F13 국내 마스터/가격/기간 backfill, 미국 마스터/가격 5개 API → `service_sync.rs`; 날짜 입력·요청 중 잠금·결과/부분 실패. 같은 페이지의 리그 재계산 카드는 제외 |
| `/admin/stock-contents`, `AdminStockContentsPage` | AdminAssetContent | F12 종목 콘텐츠 등록/조회/삭제, YouTube/소셜 검색 → `service_admin_content.rs`, `service_social.rs`; 검색 선택·외부 URL·중복·부분 결과 |
| `/admin/people`, `AdminPeoplePage` | AdminPeople + PostReviewQueue | F12 인물 CRUD·글 검색/등록/삭제·후보 수집/개별·일괄 승인/거절 → `service_admin_content.rs`, `service_social.rs`; 인물별/전체 큐·선택 해제·항목별 오류/부분 성공 |

[관리자 기능 KB](../../knowledge/wiki/projects/daynomy/administration.md), [수집·배치 KB](../../knowledge/wiki/projects/daynomy/sync-jobs.md), 원본 `features/admin/api.ts`를 공통으로 읽는다. 서버 스케줄러·크롤러를 iOS background 작업으로 복제하지 않는다. 앱은 승인된 관리자 실행 API와 결과를 표현하는 클라이언트다. 실제 외부 제공자 실행은 테스트 작성이나 읽기 전용 검토에 포함되지 않는다.

## 인증·저장소·OAuth가 먼저 결정되어야 하는 이유

원본 `api/client.ts`는 fetch credentials include, 동시에 발생한 401을 공유 refreshPromise로 묶기, refresh 후 원 요청 한 번 재시도, CSRF endpoint가 반환한 headerName/token 사용, 204 빈 본문을 구현한다. 첫 파일럿의 공개 API 클라이언트에는 이 인증 계약이 들어 있지 않다. 후속 회원·관리자 작업은 별도 SessionTransport 계약과 고정 테스트를 먼저 만든다.

`LoginPage.tsx`는 `/api/auth/google`로 브라우저를 이동시키고 sessionStorage에 귀환 화면을 저장한다. `safeReturnPath`는 같은 origin 경로만 허용하며 //, 역슬래시, 제어문자, api/oauth2/login 귀환을 거절한다. `AuthProvider`는 `/api/users/me` 조회를 취소하고 로그아웃 시 회원/role/nickname을 비운다. `App.tsx`는 guest/memberId를 key로 포트폴리오 소유 상태를 분리한다.

iOS에서는 다음을 계약으로 확정해야 한다. 이 문서는 구현 답을 추정하지 않는다.

1. 서버의 웹 OAuth 성공 redirect를 앱으로 어떻게 돌려보내는지, 등록된 개발 redirect/callback과 유효 state/실패/사용자 취소 처리. 브라우저 인증 세션 쿠키가 URLSession으로 자동 넘어온다고 가정하면 안 된다. 새 토큰 교환 API를 앱 개발자가 임의로 만들어서는 안 된다.
2. 쿠키 jar와 세션 소유자, 프로세스 종료/재실행·계정 전환·로그아웃·탈퇴의 정리 범위. Keychain은 쿠키 연동을 자동 해결하는 수단이 아니다. 토큰/쿠키를 로그나 UserDefaults에 복사하는 설계를 전제로 하지 않는다.
3. 동시 refresh·refresh 실패·logout 중 완료된 refresh/profile/기능 요청의 세대 무효화. 사용자가 로그아웃했는데 이전 응답이 다시 로그인 상태를 만들면 안 된다.
4. deep link 귀환 허용 경로와 ADMIN route 권한 재평가. 임의 외부 URL을 OAuth 귀환으로 신뢰하지 않는다. Universal Link/custom URL scheme 선택은 서버 설정·앱 entitlement와 함께 검증해야 함.

게스트 보유/원장(`portfolioHoldingsStorage.ts`)과 분석 체험(`portfolioAnalysisStorage.ts`)은 sessionStorage를 사용한다. 회원 분석 보관은 localStorage를 사용하며, 시작 여부는 localStorage 실패 시 sessionStorage로 대체한다. 이를 iOS 영구 디스크 저장으로 기계적으로 바꾸면 현재의 탭 임시 보관 수명이 달라진다. 첫 파일럿의 MarketDraft는 한 모델 수명의 화면 이탈/복귀 계약이며 프로세스 복원·회원 저장 계약이 아니다. 게스트 세션 정의, 백업/암호화/삭제/버전 마이그레이션, 회원 로그인 시 기존 게스트 데이터 처리 정책을 후속 테스트 전에 선택한다.

## 후속 테스트 우선 배정 묶음

각 묶음은 테스트 작성자 → 별도 구현자 → 원본을 보는 독립 검증자의 순서를 유지한다. 테스트/계약 hash를 고정한 뒤 구현자에게 넘긴다. API DTO 테스트와 화면 상태 테스트를 분리 고정하면 서로 다른 모듈의 조사·UI 골격 작업을 병행할 수 있다. 공통 계약 변경과 실제 DB 검사는 조정자가 직렬화한다. 아래 순서는 제안이며 자동 배정 실행기라는 뜻이 아니다.

| 묶음 | 선행 조건 | 먼저 고정할 검사 | 병행 후보 |
| --- | --- | --- | --- |
| P0 현재 Market/Quote | 현재 frozen contract | 기존 22 core 본문·2 UI source와 독립 HTTP/DB/기기 근거를 구분 | 구현자와 검증자의 현재 작업 |
| P1 공개 News/Content/People read | 공통 URLSession 오류·JSON 경계 | 목록/페이지/날짜/없음/이미지·URL/부분 실패/취소 후 응답; 구조화 decoder와 상태 모델 | P2와 서로 다른 쓰기 파일로 병행 가능 |
| P2 Search/Navigation shell | 원본 route·귀환 allowlist | 검색 입력/최근 검색 정책·취소/정렬/필터/페이지·deep link·back; 리그 redirect 제외 | P1, 정적 소개/법적 문구 검토 |
| P3 Session/Auth 계약 | OAuth callback·쿠키 소유·개발 환경 결정 | 실제 redirect/실패/취소·CSRF·204·동시401 단일 refresh·한 번 재시도·logout 후 늦은 응답 | 공개 화면 구현과 병행 가능. 미결정 OAuth만 보류하고 순수 session state 테스트 준비 |
| P4 Account | P3 | 닉네임 validation/중복·프로필 stale·logout·탈퇴 실패/성공·계정 전환 데이터 격리 | P5의 게스트 순수 계산 부분과 병행 |
| P5 Portfolio ledger + FX | P0, P3(회원), 게스트 저장 수명 결정 | 수량 정수·단가/비용 scale·환율·서울 거래일·매수/매도·초과매도·원장 재생·수정/삭제·롤백·요청 결과 불확실성; 서버 저장·로컬 게스트 구분 | UI 차트/목록 skeleton, 게스트 fixture 작성 |
| P6 Performance + Calendar | P5 자산/날짜 계약, P3 회원 경로 | 보유/현금/성과 null·다중 날짜·월/연도·서울 자정·NO_PORTFOLIO/INSUFFICIENT_DATA·게스트CSRF | 각각 별도 모듈로 병행 가능 |
| P7 AI analysis | P5, P3 회원 경로 | 1회 체험·재사용·refresh409·실패 시 이전 결과 보존·근거 날짜·부분 분석·계정별 캐시 | 관리자 데이터 조회 묶음과 병행 가능 |
| P8 Feedback | P3의 CSRF transport 부분; 로그인은 불필요 | trim/길이/입력 보존·중복 클릭·204·DB 실패·닫기 후 늦은 응답 | P1/P2과 독립; 실제 인증 로그인 완성 전에도 CSRF 계약만 고정 가능 |
| A1 관리자 read + role shell | P3/P4 | ADMIN 권한·401/403·목록/상세·페이지/필터·로그아웃 중 응답 | A2/A3 테스트 authoring은 분리 가능 |
| A2 관리자 뉴스/미디어 | A1, 파일 선택/업로드 계약 | 생성·수정·게시/거절·multipart·이미지 대체·취소·실패 복구·삭제 일관성 | A3/A4와 별도 DTO·source로 병행 |
| A3 관리자 콘텐츠·인물 큐 | A1, P1 공통 콘텐츠 | 외부 검색·선택·중복·후보 개별/일괄·항목별 부분 성공·현재 필터 보존 | A2/A4 |
| A4 관리자 피드백·종목 실행 | A1 | feedback 상태 변경·삭제; 날짜/기간 입력·중복 실행 방지·부분 실패·리그 실행 제외 | A2/A3. 실제 DB/외부 실행은 공유 잠금·별도 승인 범위 준수 |

## 웹 전용 요소의 native 적용 결정

React Router/DOM 제목·scroll/focus·body overflow·Escape focus trap은 Native NavigationStack/시트/VoiceOver 초점·Dynamic Type·키보드 회피로 매핑할 후보다. 같은 CSS/DOM 동작을 SwiftUI에 그대로 옮겼다고 설명하지 않는다. 각 화면에 loading/error/empty/ready·취소·back·복귀·접근성 식별자 검사를 준비한다.

X/Threads script·YouTube iframe은 원본 `StockContentPage.tsx`에서 실제 DOM 주입·모달 초점 정리를 수행한다. 외부 앱/브라우저로 열기, 승인된 임베드 WebView, 네이티브 카드 요약 중 제품 선택이 필요하다. 이 선택이 없는데 임베드 완료로 세지 않는다. 뉴스 본문·링크·이미지 failure와 관리자 파일 입력도 native 별도 구현/기기 검증 대상이다.

정적 법적 페이지의 브라우저 저장소 설명, 랜딩의 스크롤/영상·투어 위치 측정, 포트폴리오 SVG 차트의 hover/keyboard 조작은 native 문구·제스처·접근성 설계가 필요하다. `CardDesignPreviewPage`의 샘플은 디자인 검토용으로 분리하고, 원본에서 import되지 않는 별도 기능 코드를 현재 경로에 자동 편입하지 않는다. 일정 알림 컴포넌트/notificationApi mock은 F14 보류이며 native push나 이메일 발송으로 확대하지 않는다.

## 후속 인수 증거

각 묶음의 완료는 frozen 테스트 통과와 별도 원본 대조 리뷰만으로 끝내지 않는다. 연결된 실제 URLSession → Rust → 실험 DB 시나리오, iOS SDK build·Simulator/실기기 화면, 쿠키/OAuth·미디어의 실제 환경 검증 여부를 별도로 기록한다. 없는 Xcode·제공자 자격정보·미결정 제품 정책은 명시적으로 미검증/보류로 남긴다. 코어의 문자열 금액을 거래 연산에 쓰기 시작할 때는 임의 정밀 또는 명시적 제한/반올림 정책을 별도 계약으로 고정한다.

### 이번 정적 조사의 원본 소스 해시

경로 기준 `reference/2026-DAYNOMY-dev/`. 선택한 경계·경로 근거의 SHA256이며 전체 프론트 검토 완료를 뜻하지 않는다.

| 경로 | SHA256 |
| --- | --- |
| `frontend/src/App.tsx` | `31de7e2e424f03ccee4dc0c60ade1c6a1494166a35c4a09a0bb379ffdf4bdebf` |
| `frontend/src/api/client.ts` | `f2284ccc24c4394d02f3ae4db3e5c2a55af0754c066a5a254203d6e33dfca59e` |
| `frontend/src/auth/AuthProvider.tsx` | `b6861586e264eda5ba15aad4b3e46601c55172004c2b7d0ca5d67cffde14aafc` |
| `frontend/src/auth/returnPath.ts` | `1561489c0cf11f71dcfad1d762726e32e4693da40c13806efb835dac4825e6d9` |
| `frontend/src/features/pages/components/LoginPage.tsx` | `573b35b91814b8685c478e9c6d9f4f96f22858863e36d9ee77c6924376997142` |
| `frontend/src/features/portfolio/portfolioHoldingsStorage.ts` | `ba20cb040efbf688482956549aa27d73d22748c6431b8f656fea23aac6690dc5` |
| `frontend/src/features/portfolio/portfolioAnalysisStorage.ts` | `735e065ec6de33f692b1836d40035cb6b71b7a60b71a6a966d72eb61aa581262` |
| `frontend/src/features/stock-content/CardDesignPreviewPage.tsx` | `a82d96287993d1e4d6d43e106a312301dedcdf6d89c870271ee9ff5e9903d629` |
| `frontend/src/features/stock-content/StockContentPage.tsx` | `67ba25066c23e1af36645a435341463454b5666d5f92aea1bc22d996e493831b` |
| `frontend/src/features/news/issue/IssueHomePage.tsx` | `66e758a99d38e22fb1e732eebe42afbf2156b7fdb773c29ebd083d04d230bfee` |
| `frontend/src/features/admin/AdminStockSyncPage.tsx` | `e6bde85200177179e391de9a8eabb86adb2001a797e938767d11ebfcd2a3e924` |
