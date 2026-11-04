# Android 뉴스 시장 분석 조회

Issue #27. 기존 뉴스 상세에서 공개 `GET /api/news/{newsId}/market-analysis`를 조회한다.
원본 `market/dto/MarketAnalysisResponse.java`, `market/service/MarketAnalysisService.java`,
Rust `app/src/service_discovery.rs`와 기존 `scripts/service_acceptance.py`의 market 사례를 대조한다.

- 성공: `risk`, `watchPoint`는 필수 non-null 문자열이며 Java String.isBlank 기준으로 비어 있지 않다. 원문/Unicode를 보존하고 추가 필드는 허용한다.
- 오직 404 + `MARKET_ANALYSIS_NOT_FOUND`만 정상 분석 없음으로 표시한다. 비발행/없는 뉴스/미생성 분석을 서버 계약대로 구분하지 않는다. 다른 404·401·503·전송 실패는 실패 상태이며 취소 예외를 삼키지 않는다. 조회로 AI 생성이나 서버 쓰기를 실행하지 않는다.
- 기사·키워드·시장 분석은 독립 상태다. 분석 실패가 본문을 지우지 않으며 분석만 명시적으로 재시도할 수 있다.
- 상세 진입/탭 활성에서 조회한다. 선택 전환·목록 복귀·모드/분류/페이지 전환·비활성·close에서 요청을 취소하고, 요청 세대/선택 ID로 취소를 무시한 이전 성공/실패도 차단한다. 회전은 기존 수명 정책에 따라 선택 ID를 유지하며 재조회한다. 프로세스 종료 복원은 제외한다.
- 화면은 시장 분석/위험과 불확실성/확인할 점, 로딩·분석 없음·실패·재시도를 구분하고 기존 뉴스/키워드 흐름을 보존한다.

검사: NewsMarketAnalysisContractTest·NewsMarketAnalysisScreenTest, 기존 뉴스/키워드 회귀, APK/검사 APK/lint·API33 화면. 합성 HTTP 검사를 실제 Rust/DB 검증으로 세지 않는다. 별도 리뷰어는 같은 코드/검사 기준 해시를 확인한다.
