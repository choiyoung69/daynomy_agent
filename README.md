# DAYNOMY Agent

기존 Spring 서비스 분석에서 시작한 Rust 백엔드와 다섯 클라이언트의 개발·실험 저장소다.
기존 구현을 이어서 개선하며, 코드·지식 근거·디자인·사용량을 Issue와 PR로 추적한다.

## 현재 기준

- 보존 태그: [`baseline/2026-11-04`](https://github.com/choiyoung69/daynomy_agent/tree/baseline/2026-11-04).
- [기준선 기록](runs/020-repository-baseline.md)은 보존 범위와 제외 파일을 설명한다.
- 기준선 보존은 전체 기능·다섯 플랫폼의 검증 완료를 뜻하지 않는다.
- 플랫폼별 현재 상태와 오래된 KB 설명을 대조하는 작업은 남아 있다.
- 원본 `reference/`·로컬 SDK/DB·키는 Git에 포함하지 않아 복제만으로 모든 실험이 바로 실행되지는 않는다.

## 작업별 진입점

| 작업 | 계약·지식 | 실행법·증거 |
| --- | --- | --- |
| Rust 백엔드 | [서비스 명세](spec/service.md) | [실행 안내](app/README.md), [기존 결과](runs/010-three-hour-service.md) |
| Android / Kotlin | [명세](spec/android-native/README.md) | [클라이언트](clients/android/README.md), [기존 결과](runs/017-android-core-30min.md) |
| iOS / Swift | [이식 지도](spec/ios-native/porting-map.md) | [클라이언트](clients/ios/README.md), [구현 기록](runs/016-ios-full-thirty-minute.md), [후속 검증](runs/018-ios-native-verification.md) |
| React Native / TypeScript | [계약](spec/react-native/core-contract.md) | [클라이언트](clients/react-native/README.md), [기존 결과](runs/019-react-native-twenty-minute.md) |
| Flutter / Dart | [계약](spec/flutter/test-contract.md) | [클라이언트](clients/flutter/README.md), [기존 결과](runs/012-flutter-verification.md) |
| WebView / 웹·네이티브 호스트 | [명세](spec/webview/README.md) | [클라이언트](clients/webview/README.md), [기존 결과](runs/016-webview-full.md) |
| KB / Wiki | [운영 안내](knowledge/README.md), [목차](knowledge/wiki/index.md) | [현황](knowledge/STATUS.md), [평가 계획](knowledge/evals/README.md) |

표의 실행 기록은 해당 날짜·범위의 증거다. 현재 호스트 환경이나 전체 제품 완료를 인증하지 않는다.
WebView는 별도 구현 방식이며 독립된 여섯 번째 언어가 아니다.

## 개발 절차와 도구

- [폴더·패키지 역할 안내](docs/structure.md): 지식 묶음·앱 의존성·에이전트 확장의 차이와 읽는 순서.
- [기존 로그 병목 보고서](runs/022-log-bottlenecks.md): 시간·토큰 병목 3개, 수정 대상과 개선 계획.
- [Android/Kotlin KB 비교 결과](runs/023-android-kotlin-kb-ab.md): 같은 회귀 수정의 실제 사용량·JVM 검사·준비 비용과 한계.
- [Issue·브랜치·PR 운영](CONTRIBUTING.md): 작업 크기, 기록, 변경별 검사 선택.
- [에이전트 규칙](AGENTS.md): 범위·근거·보안·완료 판정.
- [Python 도구 목록](scripts/README.md): 실제 검사, 과거 AI 호출 실험, KB, 환경 도구 구분.
- `.codex/config.toml`: 프로젝트의 Langfuse 추적 플러그인 활성화. 인증키 파일은 로컬 전용이다.
- `agents/*.json`: 개별 실험의 역할·배정 설정. 파일만으로 에이전트가 자동 실행되지는 않는다.
- `experiments/`: 제한된 실험과 과거 증거. 일반 개발의 기본 실행 경로가 아니다.

## 앞으로의 다섯 목표

1. 논문·agent·skill·hook 학습을 실제 문제와 연결해 정리한다.
2. 품질을 유지하며 탐색·반복 호출·검증·복구의 시간과 사용량을 비교한다.
3. 다음 구현 기능부터 KB의 계약·출처·현재 상태·적용 근거를 보완한다.
4. KB(지식 집합)·Wiki(문서 구조)·RAG(검색한 근거를 생성에 제공하는 방식)를 구분하고 검색 공백을 확인한다.
5. 공통 디자인 방향·사용자 흐름을 정한 뒤 기존 다섯 클라이언트를 개선한다.

## 과거 실험

초기 피드백, 역할 분리, 병렬 샘플, 종가, 작업 큐의 기록은 `runs/001`–`009`다.
시간 제한 요청과 과거 지침은 [지침 보관본](runs/021-agent-guidance-history.md)에 있다.
정리 이전의 README 전체는 [기준선 README](https://github.com/choiyoung69/daynomy_agent/blob/baseline/2026-11-04/README.md)에서 확인한다.
과거 demo·자동 실행 명령은 새로운 작업 요청으로 해석하지 않는다.
