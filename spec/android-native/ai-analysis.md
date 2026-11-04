# Android 회원 AI 포트폴리오 분석

Issue #15 · PR #19. 사용자 명시 요청으로 기존 3탭 중 포트폴리오의 자산 요약 바로 아래에 AI 분석을 연결한다. 기존 평가·수익률 조회와 다른 기능이다. 캘린더·통합 콘텐츠/인물·관리자는 개발하지 않는다.

## API와 입력 범위

[서비스 F06](../service.md#f06--ai-포트폴리오-분석), 원본 frontend portfolio/api.ts의 isSavedPortfolioAnalysis/isPortfolioAnalysisResponse·history DTO와 Rust service_analysis.rs를 기준으로 한다. 기존 SessionHttpTransport의 회원 쿠키/CSRF/401 갱신 경계를 공유한다.

- GET /api/users/me/portfolio/analysis: 펼칠 때 저장 결과/상태만 조회. AI 생성을 자동 실행하지 않는다.
- POST 동일 경로: 회원 DB 포트폴리오의 생성/재사용. 요청 본문 없이 명시적 버튼으로만 호출한다.
- POST /refresh: 최신 근거 확인. 동일 근거의 저장 결과 재사용/이전 성공 보존을 표시한다.
- GET /history: 최근 이력 조회. 이력 오류는 현재 분석을 지우지 않는다.

Android는 회원 포트폴리오만 지원한다. 게스트 체험·V1/V2 선택 UI는 추가하지 않고 해당 백엔드 경로도 변경하지 않는다.

## 결과와 상태

필수nullable wrapper필드를 누락과null로 구분한다. 상태는 EMPTY/READY/PORTFOLIO_CHANGED/PROCESSING/RECHECK_REQUIRED/FAILED, 근거 확인 결과는 UPDATED/UNCHANGED/UNCONFIRMED 또는null이다. JSON 숫자는 BigDecimal로 보존하고 전체 점수/direction null을0/중립으로 만들지 않는다. PARTIAL/INSUFFICIENT·분석 수/비중·종목별 근거 부족을 구분한다. 출처는 HTTP(S) URL만 허용하고 실제 제목/발행일/근거 문장과 링크로 표시한다.

진행중·실패·보유변경·조회오류에는 이전 성공 결과/생성시각을 남기되 현재 정상 결과와 구분한다. 분석중 중복 POST를 막는다. POST의 전송 실패/잘못된 응답/409는 처리됐을 가능성을 두고 GET 확인 전 재POST를 막으며 자동 재전송/자동 폴링하지 않는다. 401·로그아웃·로그인 시작은 분석/이력/진행 상태를 지우고 양쪽 요청세대를 무효화한다. 계정 GET401도 같은 만료 경로를 쓴다. 보유/거래 변경·쓰기 결과 불명은 분석 상태 재확인이 필요하다고 표시한다.

## 검사 범위

별도 검증 agent의 API/nullable/부분·출처·이력/취소·POST불명/401 검사를 재사용하고, 앱에서 정상·부분·503·409·결과불명·세션만료·늦은응답·빈보유를 합성 HTTP로 검증한다. 실제 외부 AI/DB/OAuth·금융 내용의 의미 정확성 검증은 실행하지 않았다. 실행 결과·시간/토큰은 [실험4](../../docs/time-token-experiment.md)에, 코드/APK/기본·큰글꼴 캡처는 [기존 검증 자료](../../docs/design/2026-11-04-web-reference/android/verification.json)에 연결한다.

## 원본 시각 구조와 휴대폰 대응

원본 `frontend/src/features/portfolio/components/PortfolioAnalysis.tsx`의 PortfolioDonut·PortfolioAssetList·OverallImpactDetail·ImpactDetail·AnalysisSources를 기준으로 Compose Canvas/선택 행/상세/접기 동작을 이식한다. 전체 선택은 종합 방향의 단색 도넛, 종목 선택은 실제 보유 비중만 강조하고 나머지는 비활성 색으로 남긴다. 누락 종목의 비중을 재정규화하거나 부분 분석을 전체 분석처럼 표시하지 않는다.

전체 선택에는 overallImpact·overallScore·전체 sources, 종목 선택에는 해당 종목명·영향 방향/수준·issueSummary/expectedReaction/outlook·그 종목 sources를 표시한다. 종목 점수를 만들어내지 않는다. 출처는 기본 접힘이며 선택에 따라 다시 접힌다. 긍정은 원본 빨강, 부정은 파랑이며 방향 문구도 함께 표시한다.

휴대폰 도넛은 172dp, 큰 글꼴에서는 220dp로 공간을 확보하고 가운데 문구를 축약한다. 종목명은 줄바꿈하며 선택 영역은 최소48dp다. 600dp 이상·기본 글꼴은 좌측 도넛/목록과 우측 설명의 두 열이다. 새 소식 확인은 실제 회원 refresh API만 호출한다. 현재 응답에는 일일 잔여 횟수가 없으므로 원본 캡처의 하루3회/남은3회를 하드코딩하지 않는다.
