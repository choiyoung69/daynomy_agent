# 비회원 임시 포트폴리오 작성·평가

2026-11-04 사용자 결정: 뉴스 대표 이미지 연결과 함께 비회원 작성·평가를 Android에 연결한다.
이 결정은 이전 AI 분석 전용 추가 범위를 이번 기능에 한해 확장한다.

원본은 `reference/2026-DAYNOMY-dev/frontend/src/features/portfolio/PortfolioPage.tsx`,
`hooks/usePortfolioHoldings.ts`, `portfolioHoldingsStorage.ts`다. 웹은 비회원 목록을
현재 탭의 sessionStorage에 보관한다. 공개 계산 계약은 `spec/service.md` F04,
Rust `app/src/service_market.rs`의 calculate 경로를 따른다.

## 범위와 상태

- 회원 포트폴리오 조회의 401에서 별도의 비회원 임시 목록을 표시한다.
  503 등 조회 실패를 빈 비회원 목록으로 바꾸지 않는다.
- 공개 종목 검색 → 선택 → 수량·원화 평균 매수가 입력 → 임시 목록 추가/수정/제거 → 평가.
- 1~50개 종목, assetId 중복 없이 덮어쓰기, 양의 안전 정수 수량, 평균 매수가 0.01 이상,
  정수 15자리·소수 2자리까지 허용한다. 과학 표기는 입력하지 않는다.
- 목록은 Activity의 ViewModel 메모리에 보관한다. 회전·탭 이동에 유지하고 앱 프로세스가 종료되면
  사라진다. 이 차이는 화면에 명시한다. 계정 자산과 자동으로 합치거나 서버에 저장하지 않는다.
- 별도 쿠키 저장소를 가진 SessionHttpTransport로 기존 CSRF를 받아 공개
  `POST /api/portfolio/calculate`만 호출한다. 회원 원장·저장 API의 인증은 유지한다.
- 평가 중 수정/제거하면 요청을 취소하고 이전 결과를 버린다. 실패해도 임시 보유는 유지한다.
  PARTIAL·MIXED_DATES 상태와 가격 없는 기준일을 표시하고 전체 손익을 임의로 만들지 않는다.
- 임시 보유 작성·평가가 이번 범위다. 비회원 거래 원장·AI 분석·회원 데이터 이관은 별도 범위다.

## 검사

GuestPortfolioControllerTest는 공개 요청 본문·회원 쓰기 없음·입력 경계·50개 제한·임시 상태 분리·
늦은 응답 무효화·실패 시 목록 유지를 확인한다. GuestPortfolioScreenTest는 실제 Compose의
추가→평가→회전→수정→제거를 로컬 HTTP fixture로 확인한다.

기존 ApprovedPortfolioScreenTest의 회원 금액 노출 차단 조건은 유지한다. 401의 목적지만
사용자 결정에 따라 비회원 화면으로 바꾸고 그 화면에서 계정으로 이동할 수 있는지 확인한다.
TodayNewsScreenTest의 이미지 성공·실패·빈 이미지·탭/검색/상세 회귀도 유지한다.

로컬 fixture 결과와 실제 Rust/Docker DB·공개 CDN 연결 화면 결과를 구분해 기록한다.
