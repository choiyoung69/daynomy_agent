# iOS SDK 빌드와 기존 상태 회귀 — Issue #29

기준 main `892151432ee774a735f04de731c6379717585b01`, 작업 브랜치 `codex/29-ios-native-verification`.
이 작업은 기존 앱의 SDK 빌드·후속 리뷰 F1–F7 대조이며 전체 서비스·외부 제공자 인수 완료를 뜻하지 않는다.
기존 루트 checkout의 미커밋 변경과 다른 플랫폼 작업은 보존하고 별도 worktree에서 진행했다.

## 시작 시 확인

- Xcode 27.1(27A9275), Apple Swift 6.4 컴파일러·Swift 6 언어 모드, iOS 최소 17.
- 전역 developer directory는 CLT다. 명령별 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`를 사용했다.
- 앱과 UI 검사 타깃의 첫 `build-for-testing` 성공. canonical `swift test`는 51개/9 suites 통과.
- 기존 상태 본문 13개 단언 중 7개 실패를 독립 테스트 작성자가 재현했다. 실패 로그·기준 해시는 `test-author/`에 보존한다.
- 기존 F1 뉴스 검색(content/items), F4 관리자3분류, F5 내부 뉴스 연결의 기본 분기는 이미 반영돼 있었다. 기존 고정 기준은 수정하지 않았다.

## 역할·변경 경계

테스트 작성자는 새 회귀/실패 근거만, 구현자는 PortfolioView·CalendarAnalysisView만,
조정자는 AppShell identity·뉴스 URL 경계·Xcode 연결·문서만 수정했다. 별도 리뷰어는 읽기 전용으로 원본과 최종 변경을 검토한다.
프로젝트 `.agents/skills/daynomy-ios/SKILL.md`는 재사용 절차이며 에이전트 자동 실행기나 검증 결과가 아니다.
기존 tracing 플러그인 설정은 유지했고 새 hook/범용 하네스/모델 A/B는 만들지 않았다. 실제 Langfuse 수집 성공은 이번에 확인하지 않았다.

## 검사 환경의 실패 구분

- 기본 CLT 경로의 xcodebuild 탐색 실패, sandbox의 Simulator 접근/Swift 매크로 실행 실패는 제품 테스트 실패와 구분했다.
- iPhone Duo/iOS27.1에서 기존 3개 UI 테스트는 6 assertions 실패했다. 첨부 hierarchy에는 탭 버튼이 측면에 있고 `TabBar` 아래에 없어 기존 쿼리로 찾지 못했다. 이 기기의 화면 인수 성공으로 세지 않는다.
- 표준 iPhone 17은 iOS27.1 런타임과 호환되지 않아 생성 실패, 설치된 iOS27.0으로 작업 전용 기기를 생성했다. 기존 다른 기기는 변경하지 않았다.
- 화면 HTTP는 기존 loopback 합성 fixture다. 실제 Rust/DB·Google·AI·S3/소셜 제공자 성공으로 확대하지 않는다.

최종 검사·코드/기준 해시·독립 판정은 같은 폴더의 최종 결과와 연결한다. 전체 시간/토큰·비용 절감은 측정하지 않았다.
