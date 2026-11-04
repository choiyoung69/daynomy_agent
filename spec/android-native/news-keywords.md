# Android 뉴스 키워드 조회

Issue #25. 기존 뉴스 상세에서 공개 `GET /api/news/{newsId}/keywords`를 조회한다.
원본 `keyword/dto/{KeywordsResponse,KeywordResponse}.java`, `keyword/domain/KeywordCategory.java`,
`keyword/service/KeywordService.java`와 Rust `app/src/service_discovery.rs`를 대조했다.

- `keywords`는 배열이며 서버 순서를 유지한다. 각 항목은 PERSON/POLICY/EVENT/TERM/TREND 중
  category, keyword, points(문자열 3개), definition, context, watchPoint를 필수로 갖는다.
  알 수 없는 추가 필드는 허용하지만 필수 필드 누락/null/타입·enum 오류는 응답 오류다.
- 화면은 named 필드의 뜻·기사 속 의미·확인할 점을 표시한다. Unicode와 원문 순서를 보존하며
  클라이언트가 키워드를 생성하거나 AI를 호출하지 않는다.
- 빈 배열은 정상 빈 상태다. 비발행/없는 뉴스의 404나 네트워크 실패를 빈 배열로 바꾸지 않는다.
- 상세와 키워드의 로딩·오류·재시도는 독립적이다. 상세 진입 때 조회하며 자동 재시도하지 않는다.
  새 상세·목록 복귀·모드/분류/페이지 전환·탭 이탈·종료 시 취소하고 이전 응답/실패를 차단한다.
  회전은 기존 ViewModel의 선택 ID를 재사용하며 기존 수명 정책에 따라 재조회한다. 프로세스 종료 후 복원은 이번 범위 밖이다.

검사: NewsKeywordsContractTest, NewsKeywordsScreenTest, 기존 Discovery/TodayNews 회귀,
APK/검사 APK/lint. 합성 HTTP 화면 검사는 실제 Rust/DB 증거와 구분한다.
서버·시장 분석·이미지 다운로드·날짜 정책·다른 플랫폼 변경은 제외한다.
