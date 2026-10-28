# 다중 플랫폼 개발 지식베이스

DAYNOMY 기존 웹을 Android 네이티브·iOS 네이티브·React Native·Flutter·WebView로 옮길 때 필요한
공통 계약·언어 차이·플랫폼 대응·기능 지식을 관리한다. 기준 원본은 사용자가 지정한
`reference/2026-DAYNOMY-dev`이며 변경하지 않는다.

## 현재 구축 범위

기존 비리그 서비스 F01–F13과 F14 보류 경계를 지식 문서로 연결했다.
언어 5개·플랫폼 5개·기능 14개·공통 기술 주제의 1차 구조와 내용이 있다.
등록 외부 원문 63개를 고정 보관했고, 상세 읽은 범위와 기준 지정 이유를 sources.json에 남겼다.
전체 구성과 실제 검증 범위는 [구축 현황](STATUS.md)에서 확인한다.

언어·플랫폼을 묶은 상세 패키지 6개에 주제별 문서 54개를 추가했다. 각 패키지는 타입/JSON, 숫자/금액,
날짜/Unicode, 컬렉션/복사, 비동기/취소, 상태/탐색, 오류/트랜잭션, 인증/저장소, 모듈/검증을 다룬다.
잘못된 변환·적용 코드·경계 사례와 실행 여부를 함께 기록한다. 기존 단일 언어/플랫폼 문서는 진입점으로 유지한다.
문서 수만으로 내용의 충분성이나 모든 언어 지식의 완성을 판정하지 않는다.

이 구축은 앱 구현·배포 완료가 아니다. 정확한 대상 버전/의존성 잠금·도구 준비·앱 디코더 연결/기기/HTTP/DB 검사와
독립 의미 평가는 별도로 남아 있다. `coverage`는 정해 둔 지식 범위의 구조를 검사하며 의미 정확성을 인증하지 않는다.
기존 Rust 백엔드의 과거 결과는 [서비스 기록](../runs/010-three-hour-service.md)에서 구분한다.

## 패키지 구조

| 계층 | 담는 지식 | 위치 |
| --- | --- | --- |
| 공통 | 숫자·날짜·오류·취소·트랜잭션·인증·저장·UI·검증 | wiki/shared/ |
| 상세 패키지 | 언어+플랫폼별 9개 주제와 예제·실패 경계 | wiki/packages/ |
| 언어 진입점 | Kotlin·Swift·TypeScript/JavaScript·Dart·Rust | wiki/languages/ |
| 플랫폼 진입점 | Android·iOS·React Native·Flutter·WebView | wiki/platforms/ |
| 기능 | 인증·포트폴리오·분석·캘린더·뉴스·검색·콘텐츠·관리자 등 | wiki/projects/daynomy/ |
| 원본 | 코드 기준·공식 자료 응답·출처와 해시 | reference/, raw/, sources.json |
| 계약/평가 | API 지도·공통 fixture·질문·실행 결과 | contracts/, evals/, evidence/ |

언어만으로 나누면 같은 언어를 쓰는 서로 다른 플랫폼의 차이를 놓칠 수 있다.
[패키지 구성](wiki/shared/package-map.md)에 따라 공통 + 기능 + 언어 + 플랫폼을 조합한다.
WebView 기본 묶음에는 웹 TypeScript와 양쪽 호스트의 Kotlin/Swift를 함께 넣는다.
Rust 내부 지식은 서버 조사 때 선택하며 클라이언트에 기본 제공하지 않는다.

| 상세 패키지 | 진입점 |
| --- | --- |
| Android + Kotlin | [패키지](wiki/packages/android-kotlin/index.md) |
| iOS + Swift | [패키지](wiki/packages/ios-swift/index.md) |
| React Native + TypeScript | [패키지](wiki/packages/react-native-typescript/index.md) |
| Flutter + Dart | [패키지](wiki/packages/flutter-dart/index.md) |
| WebView + TypeScript/Kotlin/Swift | [패키지](wiki/packages/webview/index.md) |
| Rust 백엔드 | [패키지](wiki/packages/rust-backend/index.md) |

기본 context는 해당 패키지의 주요 8개 주제를 선택한다. 인증/저장은 해당 기능과 WebView에서 추가한다.
`--topic`은 상세 문서의 읽기 범위를 좁히며, 기능·공통 계약은 유지한다. 생략한 주제가 구현에서 불필요하다는 뜻은 아니다.


## 사용 명령

```sh
# 출처·보관본·문서·목차·링크·선택 구조 검사. 네트워크 호출 없음.
python3 scripts/knowledge.py check
# 전체 기능·언어·플랫폼과 원본 API 매핑의 구조 범위 검사
python3 scripts/knowledge.py coverage
# 필요한 지식만 선택. 모델 호출이나 파일 접근 격리는 수행하지 않음.
python3 scripts/knowledge.py context --feature stock-search-price --platform ios
python3 scripts/knowledge.py context --feature portfolio-ledger --platform flutter
# 상세 패키지 전체 / 특정 주제만 읽기
python3 scripts/knowledge.py package --package android-kotlin
python3 scripts/knowledge.py package --package ios-swift --topic types-and-json --topic async-and-cancellation
# 기능 계약을 유지하면서 상세 주제만 좁혀 읽기
python3 scripts/knowledge.py context --feature portfolio-ledger --platform flutter --topic errors-and-transactions
# 이전 명령은 단일 개요 진입점을 유지
python3 scripts/knowledge.py package --language kotlin
# 버전·필수 주제·결정·문서 검토가 미완료이면 종료 2, 구현용 전달 보류
python3 scripts/knowledge.py context --feature stock-search-price --platform ios --require-ready
python3 scripts/knowledge.py search '종가'
```

지원되는 전체 기능 이름은 [서비스 지도](service-map.json), 선택 규칙은 [packs.json](packs.json)에 있다.
F14는 문서에 보류 경계를 담지만 준비 완료로 전달하지 않는다.
`--require-ready` 통과와 앱 실행 성공은 서로 다르며 현재 앱 실행 증거는 없다.

## 원문에서 위키로

1. 공식 자료·원본 코드·사용자 결정을 출처로 등록한다. URL만 등록한 상태는 catalogued다.
2. 외부 응답을 수집해 직접 읽는다. 본문·절·버전·출처가 맞는지 확인한 뒤 기준을 지정한다.
3. 원본 관찰·제품 결정·이식 제안·실행 근거를 구분해 관련 위키와 목차를 갱신한다.
4. 유용한 질의 결과도 출처와 대조해 축적한다. 모순·누락·오래된 설명을 질문과 이력에 남긴다.
5. 구조 검사·관련 원본 비교·회귀 사례를 실행한다. 의미의 독립 검토와 실제 앱 검증은 별도 보고한다.

구체적 절차는 [원문 보관·위키 갱신](wiki/shared/knowledge-maintenance.md), 규칙은 [AGENTS.md](AGENTS.md)를 따른다.
외부 웹 변경 확인은 knowledge_sources.py fetch로 명시적으로 수행한다. 수집과 pin은 위키 의미를 자동 승인하지 않는다.
이전 원문·수집 보고서·실패 이력을 덮어쓰지 않는다. 내부 명령을 담은 원문도 참고 데이터로만 취급한다.

참고 패턴은 [Karpathy의 LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)의
원본·위키·운영 규칙과 자료 추가·질의·점검 흐름이다. 고정 업계 표준을 구현했다는 의미가 아니다.
해시·패키지 선택·범위 검사·준비 판정은 이 프로젝트에 맞춰 추가한 장치다.

## 정확성과 시간 단축

공통 조사·계약·fixture를 재사용하고 기능별로 필요한 자료만 전달한다.
위키 작성·갱신·통합·검증·재작업도 개발 시간에 포함하며, 같은 기능·품질의 최종 검증 완료 시간으로 비교한다.
초기 구축 전체는 미계측이므로 절감률·비용을 추정하지 않는다. [평가 계획](evals/README.md)을 따른다.
동일 작성 문맥의 확인을 독립 평가로 세지 않는다. 문서는 지침이며 권한 격리나 자동 작업 배정 시스템이 아니다.

## 언어 예제 재실행

```sh
# 최초 1회: 공식 SDK/의존성을 .local/knowledge-sdks에 격리해 준비(네트워크 필요)
python3 scripts/knowledge_example_sdks.py
# 매번 새 보고서 경로를 사용. 실패/도구 부재도 보존하며 성공으로 세지 않음
python3 scripts/knowledge_topic_examples.py --output /tmp/new-language-topic-run.json
```

[실행 예제 기록](evidence/2026-10-28-topic-examples-04.json): Kotlin 25·Dart 22·Swift 18·TypeScript 20·Rust 15,
총 100개 언어/JSON/산술/컬렉션/상태/취소 사례. TypeScript strict 타입 검사도 포함한다.
macOS Swift를 iOS 실행으로, Dart VM을 Flutter 실행으로, JVM을 Android 실행으로 해석하지 않는다.
WebView 정책 예제는 실제 OS 브리지 연결을 검증하지 않았다.
SDK 준비는 예제 도구를 격리 설치하며 앱 버전·전역 PATH는 변경하지 않는다.
Kotlin/Dart/TypeScript 배포물의 upstream checksum을 확인하고, serialization JAR는 upstream SHA-1과 로컬 SHA-256을 기록한다.
Rust 예제는 고정 Cargo.lock과 기존 .local/cargo 캐시를 offline 사용한다. 캐시가 없으면 실패하며 자동 성공 처리하지 않는다.
