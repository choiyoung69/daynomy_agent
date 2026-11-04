# 사용자 후속 수정 독립 리뷰

기준 `bf489df4822a698f47d2e81eed8f68c281e4570e` 이후 실제 diff와 `remove-shortcuts-back-results.json`·README 후속 절을 읽었다. 앱/테스트 수정·native 실행·추가 캡처 없이 확인했다.

- 포트폴리오 홈의 AI 분석·투자 캘린더 NavigationLink 두 개만 제거됐다. 게스트의 빈 투자 살펴보기 Section을 없애며 회원의 자산 추이/변경 이력 진입은 유지한다. 거래 기록·종목 조회·보유/거래 탭과 기존 내부 분석/캘린더 구현은 보존됐다.
- MarketView의 중첩 NavigationStack만 제거됐다. 실제 MarketView 생성 위치는 PortfolioView의 NavigationLink 하나이며 상위 NavigationStack을 사용한다. 종목 관련 자료 NavigationLink도 같은 stack에 push되어 두 단계 native back이 가능하다. 검색/단가 모델·수명 관리 로직 변경은 없다.
- 새 인수는 홈 shortcut 부재/거래·종목 조회 보존과 종목→관련 자료→종목→포트폴리오 왕복을 확인한다. 기존 오늘 뉴스 상세 복귀 인수도 함께 GREEN에 포함됐다.
- 후속 결과의 소스4개와 RED/GREEN 로그2개 SHA-256이 현재 파일과 모두 일치한다. RED2실패와 GREEN3통과가 구분되어 있으며, README는 최초16개/최초 시각 캡처/최초 manifest를 과거 적용 시점 기록으로 명시한다. 기존 AI 단독 진입 인수를 최신 사용자 결정에 따른 제거 인수로 바꾼 이유도 기록했다.

이 변경 범위에서 미해결 결함·누락은 발견하지 못했다. 통과 결과는 조정자의 실제 실행 기록이며 리뷰어가 재실행했다고 주장하지 않는다. 전체 기능·다른 상태·실물 기기/VoiceOver·OAuth/DB/제공자 검증으로 확대하지 않는다. 추가 시각 검토 패스는 수행하지 않았다.
