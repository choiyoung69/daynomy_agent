---
name: daynomy-ios
description: DAYNOMY의 기존 SwiftUI 앱에서 기능·상태 결함을 수정하고 iOS SDK·Simulator 검증을 이어갈 때 사용한다.
---

# DAYNOMY iOS 작업

루트 AGENTS.md·CONTRIBUTING.md를 따르고 현재 Issue, checkout, 미커밋 변경을 먼저 확인한다.
진입점은 `clients/ios/README.md`다. `spec/ios-native/porting-map.md`는 오래된 배정 계획이며 현재 미구현 목록으로 사용하지 않는다.
현재 기능 계약은 `full-contract.md`, 종목 계약은 `interfaces.md`와 `clarifications.md`를 선택한다.

## 입력과 역할

- 전달 전에 `python3 scripts/knowledge.py context --platform ios --feature <기능> --require-ready`를 실행한다. 준비 확인만 필요하면 `--check-only`, 선택 문서 본문이 필요하면 관련 `--topic`을 사용한다. 준비 상태와 앱 인수 완료를 구분한다.
- 테스트 작성자는 기존 고정 기준과 원본을 먼저 대조한다. 후속 상태 기준은 `experiments/ios-next-verification/test-author/`에 있다. 이미 재현되는 실패를 새 테스트로 복제하지 않는다.
- 사용자가 역할 분리를 요청한 작업에서는 조정자가 공통 세션·탐색·Xcode 프로젝트를 소유하고 구현자는 서로 다른 파일을 소유한다. 같은 기능의 테스트 작성→구현→독립 검증은 순서를 지킨다. `agents/ios-full.json`은 과거 배정 기록이며 자동 실행기가 아니다.
- 각 역할에는 기준 커밋·목표·선택 계약/KB·쓰기 파일·고정 검사 경로만 전달한다. 리뷰어는 앱과 고정 기준을 수정하지 않는다.

## 실제 실행 경로

명령별 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`를 지정한다. 전역 xcode-select를 바꾸지 않는다.
설치 버전은 직접 조회한다. 과거 README의 Xcode 부재나 CLT Swift Testing 로더 실패를 현재 환경 사실로 사용하지 않는다.

- 코어: `swift test --package-path clients/ios`를 Xcode toolchain으로 실행한다.
- 상태: `python3 experiments/ios-next-verification/test-author/run_state_contract.py`는 실제 메서드 추출 호스트 검사다. SwiftUI 화면 검사로 표현하지 않는다.
- 앱/검사 타깃: `xcodebuild -project clients/ios/DaynomyIOS.xcodeproj -scheme DaynomyIOS -destination 'generic/platform=iOS Simulator' -derivedDataPath .local/ios-derived CODE_SIGNING_ALLOWED=NO build-for-testing`.
- 화면: 설치된 실제 destination을 조회하고 작업 전용 Simulator에서 실행한다. 기존 UI fixture는 `experiments/ios-next-verification/test-author/ui_fixture.py`(18082), 후속 검색 취소 UI는 그 Handler에 지연만 추가한 `experiments/ios-sdk-verification/ui_fixture.py --port 18097 --stock-delay 3`을 사용한다. 둘 다 루프백 합성 HTTP이며 Rust/DB 근거가 아니다. 동시에 같은 Simulator·포트·DB를 사용하지 않는다.

완료된 동일 코드 검사를 반복하지 않고 실패·수정 영향만 재실행한다. Xcode result bundle·로그는 `.local/`에 보존하고 PR에 기준 커밋·최종 소스/검사 해시·실행 범위와 미검증을 연결한다.

## Hook 경계

기존 `.codex/config.toml`의 tracing 플러그인 설정을 재사용한다. 설정 존재와 실제 수집 성공은 구분한다.
매 도구 호출에 모델 리뷰·전체 빌드를 추가하지 않는다. 기능 수정 중 hook 권한/계측 복구로 범위를 넓히지 않는다.
상태를 반복 조회하지 않고 프로세스 완료 대기 후 결과를 요약한다. 누락 사용량은 0으로 기록하지 않는다.
