# iOS 공통 UI — Issue #31

기준 `e3c9616f`(선행 PR #30), 브랜치 `codex/31-ios-common-ui`. 변경 계약은 [iOS 적용 명세](../../spec/ios-native/common-ui.md)다.
기존 root checkout 및 Android 작업은 수정하지 않고 별도 worktree에서 작업했다. 원본/기존 테스트를 보존하고 새 탐색 인수를 추가했다.

## 확인 범위

- 공통 토큰·화면 흐름은 Android `b1b7ded7`의 공통 명세·실제 캡처를 읽어 재사용했다. 초기 Android 승인 시안에 남은 전역 검색보다 최신 제거 결정을 우선한다.
- 디자인 context launcher는 엔진 부재로 실행되지 않아 기존 명세·스크린샷·native 지침을 직접 읽었다. 도구 설치/새 이미지 생성/새 범용 하네스는 수행하지 않았다.
- 테스트 작성자(새 인수/fixture), 이슈 구현자(DiscoveryView), 조정자(AppShell/Portfolio/Account/Xcode), 읽기 전용 리뷰어로 쓰기 영역을 분리했다.
- 기존 기준선의 4개 정적 미구현 신호를 고정했다. 실제 UI RED 실행과 구분한다.
- Xcode27.1 앱/검사 타깃 SDK 빌드 성공. 현재 기능/시각 검사 결과는 아래 최종 증거에 이어 기록한다.

## 의미·검증 경계

테스트 JPEG는 AndroidTest에 이미 쓰인 사진을 합성 fixture에서만 제공한다. 제품 앱에 fixture 자산이나 임의 기사·수익률을 포함하지 않는다. 공개 시각 자료에도 검증용 기사 제목으로 테스트임을 구분한다.
서버는 loopback만 바인딩하고 기존 auth/CSRF/feedback/calculate Handler를 상속한다. Simulator 화면은 실제 Rust/DB 또는 Google·AI 제공자 성공 근거가 아니다.

기존 정식 Swift51·상태13+17의 계약/코어 로직은 선행 PR30에 보존돼 있다. 현재 새 실행과 재사용한 과거 결과를 구분한다. 원장 상태·취소 로직 자체는 이번 디자인 작업에서 변경하지 않는다.

## 최종 결과

- 현재 Xcode27.1/Simulator iOS27.0에서 기능 UI 고유16개가 최신 적용 결과 기준 모두 통과했다. 첫 실행10통과/5실패 → 관련 재검사5통과/2실패 → 피드백 재검사2통과/0실패의 합집합이며, 한 번의 전체16 실행으로 표현하지 않는다.
- 실패를 보존했다. 피드백 진입/전송의 동명 접근성 조회는 식별자로 분리했고, 보유 삭제 뒤 기존 거래가 남는 안내 기준과 키보드 Search를 포함하던 검사 범위를 수정했다. 캐러셀44pt는 Button label 내부 실제 hit 영역을 수정했다. 작성자별 원본 검사와 수정 이유는 `test-author/`에 보존한다.
- 전량 매도 뒤 실현손익80 유지, 거래/보유 삭제, 금액 숨김, 뉴스 최대9건/실제 사진·실패 fallback/상세 복귀, 키보드 제출 검색, 계정/피드백, 종목 조회, 캘린더 요청 없는 AI 단독 진입을 검사했다.
- 기존 상태 회귀13+비동기17 =30개를 현재 소스로 새 실행해 모두 통과했다. Swift51개는 코어 불변인 선행 PR30 결과를 재사용했으며 이번 새 실행으로 세지 않는다.
- iPhone·iPad·iPhone 최대 접근성 글자/Dark 각각 초기1+최종1 시각 검사 통과. 초기9장 대조 후 CTA 대비/큰 글자 세로 배치/기사 글자색을 한 번에 수정하고 최종9장을 확인했다. [독립 코드 리뷰](review/code-review.md)와 [시각 리뷰](review/visual-review.md)에 미해결 지적이 없다.
- [results.json](results.json)에 실행별 성공/실패·로그 SHA-256·고유 검사와 한계를, [final-source.sha256](final-source.sha256)에 최종 코드·테스트·캡처 해시를 연결했다. 원본 `.log`·`.xcresult`는 이 worktree의 `.local/`에 보존하며 저장소에는 큰 native 결과 번들을 추가하지 않는다.
- 실제 Google OAuth·AI 제공자·Rust/DB 통합·실물 기기·VoiceOver·전체 가로 방향은 미검증이다. Dark 계정 캡처는 로그인 CTA까지 보이지 않아 해당 버튼은 코드 대비 확인으로 한정한다. 시간·토큰·비용 절감은 측정하지 않았다.

## 최종 화면

| 기기 | 포트폴리오 | 이슈 | 내 계정 |
| --- | --- | --- | --- |
| iPhone | [화면](screenshots/phone-portfolio-first-entry.png) | [화면](screenshots/phone-issue-first-photo.png) | [화면](screenshots/phone-account-login.png) |
| iPad | [화면](screenshots/ipad-portfolio-first-entry.png) | [화면](screenshots/ipad-issue-first-photo.png) | [화면](screenshots/ipad-account-login.png) |
| iPhone 큰 글자/Dark | [화면](screenshots/phone-large-dark-portfolio-first-entry.png) | [화면](screenshots/phone-large-dark-issue-first-photo.png) | [화면](screenshots/phone-large-dark-account-login.png) |


## 사용자 후속 수정 — AI·캘린더 진입 제거와 뒤로가기

기준 `bf489df4` 이후 사용자 요청으로 포트폴리오의 AI 분석·투자 캘린더 링크를 제거했다. 게스트에게 빈 투자 살펴보기 섹션을 남기지 않는다. 내부 분석/캘린더 API·구현은 삭제하지 않는다.
종목 조회의 중첩 NavigationStack을 제거해 상위 stack의 native 뒤로가기를 유지한다. 다른 push 화면은 기존 stack을 상속하며, 시트는 닫기를 유지한다.
변경 전 새 인수2개 실패를 확인한 뒤 구현했고, 변경 후 새2개와 기존 이슈 상세 복귀1개가 실제 Simulator에서 통과했다. 종목→관련 자료→종목→홈의 2단계 복귀를 포함한다. 상태/전체 기능 검사는 재실행하지 않았다.
현재 수정 해시와 RED/GREEN 로그 해시는 [후속 결과](remove-shortcuts-back-results.json)를 따른다. 위 최초16개 결과·최초 screenshots·final-source.sha256·authored.sha256는 최초 적용 시점의 기록이며 현재 화면 해시로 재해석하지 않는다. AI 단독 진입 인수는 사용자 결정에 따라 제거 인수로 교체했다.
