# 폴더·패키지는 각각 무엇인가?

2026-11-04 현재 파일을 읽어 정리한 안내다. 폴더의 존재는 기능 완료나 실제 사용의 증거가 아니다.
우선 [README의 작업별 진입점](../README.md)을 선택하고 필요한 부분만 읽는다.

## 먼저 구분할 세 가지

| 여기서 쓰는 말 | 실제 의미 | 예 |
| --- | --- | --- |
| 지식 패키지 | 에이전트가 참고할 문서 묶음. 설치되는 코드가 아님 | `knowledge/wiki/packages/ios-swift/` |
| 앱 모듈·의존성 패키지 | 실제 컴파일·실행되는 코드와 라이브러리 | Cargo, npm, Gradle, Swift Package, pubspec |
| Skill·플러그인 | 에이전트 작업 절차나 도구·hook을 제공하는 확장 | 개인 설치 skill, Langfuse 추적 플러그인 |

이 세 가지를 모두 '패키지'라고 부르면 무엇을 실행하는지와 무엇을 읽는지가 섞인다.
사용자 안내에서는 첫 번째를 **지식 묶음**, 두 번째를 **앱/의존성**, 세 번째를 **에이전트 확장**으로 구분한다.
이번 안내는 명칭 설명이며 실제 폴더·설정 이름을 변경하지 않는다.

## 루트 폴더 지도

| 위치 | 역할 | 언제 볼까? | 주의할 점 |
| --- | --- | --- | --- |
| [app/](../app/README.md) | Rust 백엔드 실제 구현·마이그레이션 | 서버/API·DB 변경 | 라이브러리와 검사 스크립트는 별개 |
| [clients/](../clients/) | 다섯 클라이언트의 실제 앱 코드 | 화면·플랫폼 구현 | 웹 빌드와 실제 네이티브 실행 구분 |
| [spec/](../spec/) | 제품·플랫폼의 동작 계약과 확인 기준 | 무엇을 만들지 결정 | 과거 파일럿 범위와 전체 범위를 구분 |
| [knowledge/](../knowledge/README.md) | 출처·규칙·언어/플랫폼 차이·지식 평가 | 구현 전에 필요한 근거 찾기 | 전체를 모든 요청에 읽히지 않음 |
| [scripts/](../scripts/README.md) | 검사·환경·KB·과거 AI 실행기 | 필요한 도구를 선택할 때 | Python 63개가 모두 에이전트는 아님 |
| [experiments/](../experiments/) | 제한된 실험 코드·테스트 작성/검증 산출물·증거 | 특정 실험 재현·근거 조사 | 현재 앱의 기본 구현 위치와 구분 |
| [agents/](../agents/) | 실험별 역할·모델·담당 파일·제약 설정 | 해당 작업 배정을 확인 | JSON만으로 모델이 실행되지는 않음 |
| [prompts/](../prompts/) | 초기 구현·검토 실행기의 입력 문서 | 해당 과거 실행기를 분석 | 현재 사용자 요청을 대체하지 않음 |
| [runs/](../runs/) | 당시 실행·실패·결정·분석 보고서 | 결과의 날짜·범위 확인 | 과거 완료를 현재 소스의 완료로 재사용하지 않음 |
| [.codex/config.toml](../.codex/config.toml) | 저장소 범위의 추적 설정 | 플러그인 활성화 확인 | 인증키·개인 승인·전역 확장 전체는 포함 안 됨 |
| `.local/` | SDK·캐시·실험 DB·로컬 결과 | 환경 준비·실험 상세 조사 | Git 제외, 복제한 저장소에 없음 |
| `reference/` | 분석용 원본 복사본 | 원본 계약·구현과 대조 | 읽기 전용 취급, Git 제외 |
| [.github/](../.github/) | Issue·PR 작성 양식 | 새 작업 기록 | 현재 Actions 자동 검사 workflow는 없음 |

## knowledge 안의 역할

| 위치 | 담는 내용 | 사람이 이해할 이름 |
| --- | --- | --- |
| [wiki/projects/daynomy/](../knowledge/wiki/projects/daynomy/service-catalog.md) | 제품 기능의 동작·원본 근거 | 기능 규칙 |
| [wiki/shared/](../knowledge/wiki/shared/package-map.md) | 데이터·인증·취소·트랜잭션 등 여러 대상에 공통인 규칙 | 공통 기준 |
| [wiki/languages/](../knowledge/wiki/languages/) | 다섯 언어별 의미 차이·상세 지식 진입점 | 언어 안내 |
| [wiki/platforms/](../knowledge/wiki/platforms/) | UI 수명·호스트·빌드·버전·플랫폼 정책 | 플랫폼 안내 |
| [wiki/packages/](../knowledge/wiki/packages/) | 언어+플랫폼을 결합한 6개 묶음의 상세 9개 주제 | 구현 주의사항 상세편 |
| [wiki/porting/](../knowledge/wiki/porting/) | 기능을 옮기는 흐름·미결정·순서 | 이식 계획 |
| [contracts/](../knowledge/contracts/) | API 목록과 기계가 읽는 계약 데이터 | 계약 색인 |
| [sources.json](../knowledge/sources.json) | 출처 ID·경로/URL·고정 보관본·검토 범위·해시 | 출처 장부 |
| [packs.json](../knowledge/packs.json) | 기능/플랫폼/주제별 문서 연결과 준비 조건 | 문서 선택 설정 |
| [service-map.json](../knowledge/service-map.json) | 제품 기능과 API·문서의 연결 | 서비스 지도 |
| [raw/](../knowledge/raw/README.md) | 외부 원문 고정 보관본 | 원본 보관함 |
| [evidence/](../knowledge/evidence/) | 과거 수집·예제 실행·확인 결과 | 증거 보관함 |
| [examples/](../knowledge/examples/) | Kotlin·Swift·TS·Dart·Rust 경계 예제 | 학습/경계 재현 코드 |
| [evals/](../knowledge/evals/README.md) | 지식 질문과 평가 기준·비교 절차 | 지식 평가 |
| [templates/article.md](../knowledge/templates/article.md) | 근거·상태를 갖춘 문서 작성 형식 | 문서 양식 |
| [STATUS.md](../knowledge/STATUS.md), [questions.md](../knowledge/questions.md), [log.md](../knowledge/log.md) | 구축 상태·남은 질문·변경 이력 | 현황·미결정·이력 |

`raw`는 읽을 자료, `wiki`는 그 자료를 정리한 주장, `evidence`는 수행 결과다.
문서를 수집했다고 wiki가 자동 갱신되지는 않고, 실행 예제 통과가 실제 앱 성공을 뜻하지 않는다.
`evals/questions.json`은 31개 평가 기준이며 독립 응답 평가 결과가 아니다.

## 상세 지식 묶음 6개

| 묶음 | 역할 | 주로 필요한 작업 |
| --- | --- | --- |
| [android-kotlin](../knowledge/wiki/packages/android-kotlin/index.md) | Kotlin·JSON/JVM 의미와 Android 상태/수명 경계 | Android 구현·검토 |
| [ios-swift](../knowledge/wiki/packages/ios-swift/index.md) | Swift·Foundation 의미와 iOS UI/저장소 경계 | iOS 구현·검토 |
| [react-native-typescript](../knowledge/wiki/packages/react-native-typescript/index.md) | TS/JS 의미와 RN 네이티브 수명/네트워크 경계 | RN 구현·검토 |
| [flutter-dart](../knowledge/wiki/packages/flutter-dart/index.md) | Dart 의미와 Flutter 상태/취소/디코딩 경계 | Flutter 구현·검토 |
| [webview](../knowledge/wiki/packages/webview/index.md) | 웹 JS/TS와 Android Kotlin·iOS Swift 호스트 사이의 브리지/쿠키 경계 | WebView와 호스트 구현·검토 |
| [rust-backend](../knowledge/wiki/packages/rust-backend/index.md) | Rust의 타입·오류·소유권과 서버/DB 경계 | 백엔드 구현·대조. 일반 클라이언트 작업에 기본 제공하지 않음 |

언어 안내는 '어디를 볼까', 플랫폼 안내는 '대상에서 무엇이 다를까', 상세 묶음은 '어떻게 잘못 옮길 수 있을까'를 맡는다.
중복 여부는 같은 주장의 소유 위치를 기준으로 검토한다. 같은 제품 정책은 기능 문서에 두고 대상 문서는 차이만 연결하는 방향이 맞다.
현재 파일이 그 원칙을 모두 지키는지 의미 중복 감사까지 완료한 것은 아니다.

## 상세 주제 9개의 읽는 시점

| 주제 파일 | 필요한 상황 |
| --- | --- |
| `types-and-json.md` | API 응답, ID 타입, 누락/null, 잘못된 데이터 처리 |
| `numbers-and-money.md` | 가격·환율·수량·반올림·안전 정수 |
| `dates-and-unicode.md` | 거래일·종가일·시간대·문자열 길이/공백 |
| `collections-and-models.md` | 목록 복사·공유 참조·상태 스냅샷 |
| `async-and-cancellation.md` | 늦은 응답·취소·중복 요청·작업 수명 |
| `state-and-navigation.md` | 화면 전환·초안·뒤로 가기·재생성 |
| `errors-and-transactions.md` | 실패·재시도·응답 유실·서버 원자성 |
| `auth-and-storage.md` | 로그인·쿠키·CSRF·계정 전환·보존 수명 |
| `modules-and-testing.md` | 의존성·검사 범위·실제 앱과 예제의 구분 |

9개는 학습 목록이지 모든 요청의 필독 목록이 아니다. 전체 기능 구현에서는 관련 필수 조건을 누락하지 않되
작은 질문·수정에는 해당 주제부터 읽는다. 예를 들어 늦은 가격 응답 문제는 기능 규칙+비동기+상태를,
가격 계산 변경은 기능 규칙+금액+날짜를 중심으로 시작하고 필요한 다른 근거를 추가한다.

## 실제 앱·의존성은 어디에 있나?

| 대상 | 코드/설정 진입점 | 지식 묶음과 다른 점 |
| --- | --- | --- |
| Rust | [app/Cargo.toml](../app/Cargo.toml), `app/src/`, 마이그레이션 | 실제 서버와 Rust 라이브러리 의존성 |
| Android | [clients/android/README.md](../clients/android/README.md), Gradle 모듈 `app`·`market-core` | 실제 UI 앱과 핵심 Kotlin 코드 |
| iOS | [clients/ios/README.md](../clients/ios/README.md), Swift 코어·Xcode 앱 | 호스트 Swift 검사와 iOS 앱 빌드를 구분 |
| RN | [clients/react-native/package.json](../clients/react-native/package.json), `src/` | 실제 Expo/RN 앱과 npm 의존성 |
| Flutter | [clients/flutter/pubspec.yaml](../clients/flutter/pubspec.yaml), `lib/` | 실제 Flutter 앱과 Dart 의존성 |
| WebView | [clients/webview/README.md](../clients/webview/README.md), 웹 앱·Android/iOS 호스트 | 웹 번들과 각 OS 호스트가 함께 필요 |

파일럿·전체 확장·독립 검증 복사본도 남아 있다. 이름이 비슷하다고 모두 동시에 빌드하거나 삭제하면 안 된다.
활성 코드·과거 후보·검증 전용 복사본의 구체적인 이동/삭제는 참조·고정 해시·재현 영향을 조사한 별도 변경으로 진행한다.

## 지금 개선할 점

1. 진입점은 README 한 곳으로 유지하고 다음 기능/대상에 필요한 문서만 선택한다.
2. 역할이 겹치는 안내는 짧게 만들고 같은 제품 규칙의 복제를 줄인다.
3. 필수 적용 규칙과 배경 참고 자료를 구분하고 실제 전달 목록·버전을 기록한다.
4. 현재/과거 상태와 코드/지식/증거를 분리해 표시한다.
5. 도구 추가보다 기존 검색·topic 선택을 먼저 활용한다.

현재 `knowledge.py`는 문자열 검색과 문서 선택을 제공한다. 별도 벡터 DB 검색은 이 구조에서 확인되지 않았다.
KB는 지식 집합, Wiki는 그 지식을 문서로 정리한 구조, RAG는 검색한 근거를 생성에 제공하는 방식이다.
현재 문제를 해결하는 데 벡터 DB 도입이 필수라고 결론내리지 않는다.

구체적인 시간·토큰 근거와 수정 대상은 [병목 보고서](../runs/022-log-bottlenecks.md)를 본다.
