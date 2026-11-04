# Android 오늘 뉴스

F08 중 오늘 뉴스만 기존 뉴스 화면에 추가한다. GET /api/news/today는 NewsPageResponse의 items/page/size/totalElements/totalPages/hasNext를 반환한다. 원본 NewsController/NewsService 및 Rust service_discovery.rs route1과 대조했다. 서버가 발행 상태·오늘 범위·발행일/ID 내림차순·최대9개를 결정한다. D03 시간대 정책은 서버에 두며 앱에서 날짜 필터나 query를 추가하지 않는다.

API: NewsSource.today(): NewsPage, NewsClient.today(). 기존 엄격한 뉴스 디코더 재사용. 잘못된 필드/JSON은 ResponseFormatException, 전송/HTTP/취소는 기존 의미 유지. 빈 목록은 정상 성공. 미래/과거 문자열을 클라이언트가 필터링하지 않는다.

상태: NewsUiState.todayOnly=false 추가, NewsController.selectToday(Boolean). 전환은 상세를 닫고 page1/category=null로 초기화한다. today일 때 source.today()를 사용하고 category/page 변경은 무시한다. 모든 뉴스 복귀는 source.list(null,1,6). 같은 모드 재선택은 추가 조회하지 않는다. 상세 뒤로는 모드/목록 유지. 기존 활성화/취소/세대로 늦은 목록/상세 성공·실패를 차단한다. 재시도는 명시적 사용자 행동으로만.

UI: 기존 NewsScreen 상단에 전체 뉴스/오늘 뉴스 모드, testTag news-mode-all/news-mode-today. today일 때 category와 previous/next 버튼을 표시하지 않는다(서버 hasNext=true여도 추가 페이지 미지원). 기존 news-item-ID/news-back/news-detail/news-retry/news-empty 태그 재사용. 오늘의 빈 결과는 '오늘 발행된 뉴스가 없습니다.'로 표시. 서버 기준 안내·최소48dp·선택 semantics·스크롤·기존 Material 테마 사용. 회전은 ViewModel로 유지, 프로세스 복원 미보장.

고정 검사 클래스: TodayNewsClientContractTest, TodayNewsControllerTest, TodayNewsScreenTest. 모델은 검사/빌드/DB를 실행하지 않으며 controller가 수행한다. 실제 Rust/DB 오늘 데이터·자정 경계·TalkBack/태블릿/다크 실측과 다른 F08 부가기능은 별도 검증이다.
