# iOS SDK 빌드와 기존 상태 회귀 — Issue #29

기준 main `892151432ee774a735f04de731c6379717585b01`, 작업 브랜치 `codex/29-ios-native-verification`.
이 작업은 기존 앱의 SDK 빌드·후속 리뷰 F1–F7 대조이며 전체 서비스·외부 제공자 인수 완료를 뜻하지 않는다.
기존 루트 checkout의 미커밋 변경과 다른 플랫폼 작업은 보존하고 별도 worktree에서 진행했다.

## 시작 시 확인

- Xcode 27.1(27A9275), Apple Swift 6.4 컴파일러·Swift 6 언어 모드, iOS 최소 17.
- 전역 developer directory는 CLT다. 명령별 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`를 사용했다.
- 앱과 UI 검사 타깃의 첫 `build-for-testing` 성공. canonical `swift test`는 51개/9 suites 통과.
- 기존 상태 본문 13개 단언 중 7개 실패를 독립 테스트 작성자가 재현했다. 실패 로그·기준 해시는 `test-author/`에 보존한다.
- 기존 F1 뉴스 검색(content/items), F4 관리자3분류, F5 내부 뉴스 연결의 기본 분기는 이미 반영돼 있었다. 기존 코어·상태 기준은 수정하지 않았다. 실제 실행에서 발견한 UI 접근성 query 오류는 아래 근거와 원본 보존을 통해 테스트 작성자가 별도 개정했다.

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

## 실제 UI 기준의 개정과 빌드 복구

- 표준 iPhone의 초기 UI3은 2통과/1실패였다. 빈 단가의 AX value가 placeholder를 반환하는 실제 녹화와 실패값을 확인해 빈값 또는 정확한 placeholder만 허용했다. 77/종가/nil을 허용하지 않는다.
- 첫 후속 UI7은 4통과/3실패였다. 원래 fixture에 pending 검색 지연이 없고 매도 Picker는 Button label `유형, 매수`로 제공되었다. 원본 fixture 응답을 상속한 stocks 지연 wrapper와 정확한 Picker query를 사용했다.
- 재실행 준비의 x86_64 링크 실패는 Debug 앱의 전체 architecture와 package의 active architecture 불일치였다. project Debug `ONLY_ACTIVE_ARCH=YES`로 맞췄으며 Release·ARCHS·EXCLUDED_ARCHS는 변경하지 않았다.
- 이 수정 후 UI6은 4통과/2실패였다. 남은 failure의 AX에는 `ActivityIndicator` 타입의 `검색 중`과 합쳐진 `실현손익, 80 원`이 실제 표시되어 있었다. ProgressIndicator·standalone80 query를 실제 타입/정확한 문구에 맞춰 개정했다. 기대 손익·원장·초과 매도 조건은 바꾸지 않는다.
- 원본·개정diff·AX/영상frame·각 SHA는 [UI 개정 기록](test-author/ui-baseline/README.md)에 있다. 증거 없는 반복 재시도나 테스트 skip으로 통과시키지 않았다.

## 최종 결과

- generic Simulator SDK build-for-testing 및 실제 iPhone17 destination 빌드/실행 성공. generic→기기 전환도 Debug active architecture 수정 후 성공했다.
- 정식 Swift Testing51, 기존 상태13, 추가 비동기17, 내부URL16, presentation10 및 정적 wiring9/identity1 통과. 정적 검사와 실행 검사는 별개다.
- 실제 Simulator 고유 UI10개 모두 통과했다. 한 번의 전체10 실행이 아니라 변경/실패 영향만 재실행한 최신 결과의 합집합이다. 기존 후속7의 통과4, 재실행6의 통과4, 마지막2의 검색 통과1, 마지막1의 전체 거래원장 통과1로 연결한다.
- 마지막 거래 흐름은 매수10@100→수정12@110→매도2@150→보유10/평균110·실현80→매도삭제 보유12→매수삭제 빈보유/빈원장까지 실제 화면에서 확인했다. 삭제 제스처는 row가 탭바 뒤에 가려진 원본 실패를 보존하고 전체노출/부분drag로 개정했다.
- 코드·검사 기준과 각 로컬 raw log의 SHA/결과는 [results.json](results.json), 최종 파일은 [final-source.sha256](final-source.sha256)에 있다. raw xcresult/log는 작업 worktree의 `.local/`에 유지하고 공개 기록에는 원문 전체를 복제하지 않는다.
- [독립 리뷰](review/review.md)는 원본·코드·기준 개정·host 근거를 대조했다. 최종 UI 실행 메타데이터도 로그11개·소스41파일과 대조해 오류0으로 확인했다.

실제 Google·AI·미디어 제공자, 실제 계정 전환 중 한 프레임도 이전 데이터가 보이지 않는지, VoiceOver·Dynamic Type·태블릿/다크/회전·Duo 화면·Release 배포는 미검증이다. 현재 기본 탐색은 기존4탭이며 공통3탭 UI 적용과 추가 제품 범위 결정은 후속 작업이다.

루프백 fixture 두 프로세스를 종료했고 작업 전용 Simulator 두 대가 이미 Shutdown 상태임을 확인했다. 다른 작업의 서버·기기는 종료하지 않았다. PR #30은 Draft로 게시했으며 자동 머지하지 않았다.
