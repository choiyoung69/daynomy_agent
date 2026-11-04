# 독립 코드 리뷰 — Issue #31

검토 기준: `e3c9616fb019439ea20626d625fbc7133fe0cfbe` 위 작업 중 diff, `.local/common-uiux.md` 2·11·12절, `spec/service.md` F03–F10. 앱·테스트·KB 수정이나 실행은 하지 않았다. 이 기록은 실제 OAuth·DB·제공자 검증 결과가 아니다. 시각 검토는 조정자의 실제 Simulator 캡처를 받은 뒤 별도 기록한다.

## 수정 필요

- **P2 — 전량 매도 후 누적 실현손익 미표시.** `clients/ios/DaynomyIOS/PortfolioView.swift:205–212`에서 실현손익이 `!store.holdings.isEmpty` 조건 안에 들어갔다. 매수 후 전량 매도하면 정상 거래 내역과 실현손익이 남지만 이 값은 사라지고 `첫 투자 기록을 시작해 보세요`가 표시된다. 기존 화면은 실현손익을 항상 표시했다. F05는 누적 실현손익과 부분/전체 매도를 별도로 보존한다. 실현손익을 보유 유무와 독립 표시하고, 첫 거래 안내는 거래 이력까지 없는 경우로 제한한다. Android 비교 구현의 `PortfolioAnalysis`도 누적 실현손익은 별도 표시한다.

## 정적 확인

조정자가 보유 없음/거래 있음 분기를 수정한 후 재독했다. 첫 기록 안내를 거래 없음에 한정하고 기존 거래가 있으면 현재 보유 없음과 실현손익을 표시한다. 금액 숨김도 같은 분기에 적용한다. 위 P2는 **정적 수정 확인 완료**, 경계 UI 회귀 결과와 최종 소스 해시는 조정자의 새 검사 결과에 연결할 예정이다.

- 하단 목적지는 포트폴리오·이슈·내 계정 세 개이며 종목 조회는 포트폴리오 맥락으로 이동했다.
- 오늘 뉴스와 뉴스 검색은 독립 payload/error/loading을 사용한다. 오늘 뉴스는 최대9건, API 순서, 수동 이전/다음, 상세 연결, 상대 이미지 URL과 실패 상태를 갖는다.
- 뉴스 검색은 입력과 제출을 분리하고 Search/Enter에 실제 `/api/search/news`를 호출한다. 정렬·분류·페이지·검색 해제와 요청 key에 의한 늦은 응답 차단을 유지한다.
- 기존 캘린더·AI 분석·이력과 통합 검색·콘텐츠·인물·관리자 진입은 보조 경로로 남아 있다. 세부 코드의 기존 기능 전체를 재검증한 것은 아니다.
- Android `PortfolioStyle`의 흰 표면·검정 주요 동작·청색 `#326bd5`와 비교했다. iOS는 시스템 semantic surface와 SF Symbol, List·NavigationStack·TabView를 사용한다. 실제 크기/줄바꿈/겹침/사진 대비는 캡처 전에는 승인하지 않는다.

## 범위 판단

공통14절의 AI 확장도 추가 대조했다. 기존 `CalendarAnalysisView`는 모든 일정 결과 뒤에 분석을 표시하므로 AI 목적이 묻힐 수 있다. 조정자가 제안한 AI 단독 진입·기존 view 재사용은 타당한 native 적응이다. AI 목적의 화면은 calendar section뿐 아니라 calendar request task도 생략하고, 기존 AI 상태 GET·명시적 POST·이력은 재사용한다. 투자 캘린더는 기존 보조 진입으로 보존한다. 실제 제공자 연결 완료를 의미하지 않는다.

분류 Picker의 전체·주식·ETF·부동산4개는 Android 최신 화면과 같아 신규 major 결함으로 분류하지 않았다. 실제 네트워크/스크린리더 동작은 이 정적 리뷰로 입증하지 않는다. 시각 리뷰는 첫 캡처 검토와 수정 후 최종 확인의 최대2회로 제한한다.

## 최종 정적 재확인 소스 SHA-256

2026-11-04 최종 시각2/2와 코드 재독 시점. 테스트/실행 결과의 manifest 연결은 조정자가 별도 담당한다.

| 파일 (`clients/ios/DaynomyIOS/`) | SHA-256 |
| --- | --- |
| AccountView.swift | `1f5c6f6c3f91e8e271867326e7c67213bce4b1bf3242c6a4d9538f9200487054` |
| AppShell.swift | `b0dfd51683d2e2d07d6cf2e3147d7164e8920dd0331dad3a120c9cdf98eeb8fa` |
| CalendarAnalysisView.swift | `50a12749f34234dca0ba9cc0c308b6def9d5de92190fd32d91721933699bf9e6` |
| DiscoveryView.swift | `f69eb773f77f18721b30fcf176d4e2d3d0bf18f03b8c3c92545a4aa3cb11b560` |
| PortfolioView.swift | `6884defef2c03cc6d167b15d6b52385445d65eaaafabd4e79f35e586d4939602` |

전량 매도 경계의 실현손익·안내 분기, 주요 CTA label 대비, accessibilitySize actionLayout, 오늘 뉴스 label 내부44pt frame, 기사 Color.primary/secondary, 계정 label/hint, AI 단독 진입의 calendar 요청 생략을 확인했다. 검토 범위에서 미해결 수정 지적은 없다. 상세 시각 증거와 한계는 `visual-review.md`를 따른다.
