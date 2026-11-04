# Android F09 뉴스 검색

Issue #11. F09 중 뉴스 검색만 구현하며 통합 콘텐츠 검색은 남긴다.
근거: [서비스 F09](../service.md#f09--검색), 원본 `search/controller/NewsSearchController.java`, `search/dto/NewsSearchResponse.java`, `news/dto/NewsListItemResponse.java`.

- `NewsSource.search(query, category, page, size, sort)` → 기존 `NewsPage`로 변환한다. q 원문을 URL query로 인코딩하고 정규화·정렬·검색 의미는 서버에 둔다.
- q는 UTF-16 1~100자, Unicode 문자/숫자 포함, Java 정규식의 줄바꿈 문자 불가. page≥1, size 1~100. 입력 실패는 전송하지 않는다.
- 응답 `content` 필수 배열·각 필드 타입을 기존 뉴스 디코더로 검사한다. 양의 page/size, 음이 아닌 totalPages/totalElements. hasNext는 page<totalPages로 계산한다. 잘못된 응답은 빈 성공으로 바꾸지 않는다.
- 검색은 명시적 제출이다. 편집 초안과 제출한 검색어를 구분하고 활성 검색어를 표시한다. 새 검색·분류·정렬·검색 해제 시 페이지 1과 상세 선택을 초기화한다.
- 목록/검색/상세는 기존 NewsController 세대·취소·활성 수명으로 관리한다. 늦은 성공/실패는 무시하고 오류는 안전한 문구를 쓴다. 재시도는 사용자 행동으로만 한다.
- 검색 해제는 일반 목록으로 돌아간다. 상세 복귀는 검색 조건과 페이지를 유지한다. 회전은 ViewModel과 rememberSaveable 초안으로 유지하며 프로세스 종료 후 검색 결과 복원은 보장하지 않는다.
- 기존 Material·48dp·검색 label·IME Search·상태 알림·스크롤을 사용한다. JVM 계약/상태·기존 뉴스 회귀, APK, 실제 에뮬레이터 화면을 분리해 기록한다. 실제 Rust/DB 의미 검증은 별도다.

## 공통 UI 적용과의 통합 — Issue #15 · PR #19

Issue #11의 구현 커밋 `3a2d9e46`에 있던 NewsClient/NewsController/입력 검증과 계약/상태/화면 검사를 재사용했다. 새 검색 API를 중복 구현하지 않는다. 이슈 화면에서만 검색 입력을 제공하고 거래·종목 추가의 F03 종목 검색과 분리한다. 통합 콘텐츠 검색은 구현하지 않았다.

오늘 뉴스는 별도 NewsController 인스턴스가 `/api/news/today`를 조회하는 상단 대시보드다. 최신3건 미리보기와 최대9건 펼침을 제공하며 검색/분류/페이지·오류·상세 선택 상태를 검색 controller와 공유하지 않는다. 오늘 뉴스에서 기사를 열면 기존 상세 경로로 이동하고 뒤로 돌아와 검색 조건을 유지한다.

최신 입력/상단 표현: 별도 검색 버튼 없이 IME Search/Enter로 제출한다. 오늘 뉴스는 사진 HorizontalPager(최대9건)로 표시하며 별도 controller와 선택 기사ID 복원은 유지한다. 이미지 로딩/누락/실패는 분리한다. 상세/일반 목록의 모든 이미지 기능을 구현했다는 의미는 아니다.
