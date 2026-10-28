# 지식베이스 구축 현황

확인일: 2026-10-28. 문서·근거·언어 예제 구축과 앱의 실제 검증 범위를 구분한다.

## 이번에 보강한 내용

이전 단일 언어 문서는 개요 수준이었다. 사용자 지적과 보완 요청에 따라 언어·플랫폼을 묶은
[상세 패키지](wiki/index.md) 6개를 만들고 각 패키지에 9개 주제, 합계 54개 상세 문서를 추가했다.
이전 보고의 한계와 정정은 [이력](log.md)에 보존했다.

| 패키지 | 포함한 지식 | 실행한 언어 예제 |
| --- | --- | --- |
| [Android/Kotlin](wiki/packages/android-kotlin/index.md) | Kotlin/JVM 의미·Compose/Android 적용 경계 | 25개 |
| [iOS/Swift](wiki/packages/ios-swift/index.md) | Swift/Foundation 의미·SwiftUI/iOS 적용 경계 | 18개 |
| [React Native/TypeScript](wiki/packages/react-native-typescript/index.md) | JS/TS 의미·React 상태·RN 네이티브 차이 | 20개 |
| [Flutter/Dart](wiki/packages/flutter-dart/index.md) | Dart 의미·Flutter 상태·플러그인 경계 | 22개 |
| [WebView](wiki/packages/webview/index.md) | 웹+양쪽 호스트·메시지 스키마·origin·쿠키 | 위 TS/Kotlin/Swift 사례 재사용 |
| [Rust 백엔드](wiki/packages/rust-backend/index.md) | 소유권·JSON·숫자·취소·서버 트랜잭션 경계 | 15개 |

각 패키지의 주제는 타입/JSON, 숫자/금액, 날짜/Unicode, 컬렉션/모델 복사, 비동기/취소,
상태/탐색, 오류/트랜잭션, 인증/저장소, 모듈/의존성/검증이다.
실패하는 변환·적용 코드/설계·경계 사례·공식 자료·실행/미실행 범위를 함께 기록했다.
UI·HTTP·저장소 스니펫은 연결 설계이며 실행 파일의 검사와 구분한다.

기존 공통·DAYNOMY F01–F13·F14 보류 문서와 언어/플랫폼 진입점을 보존했다.
공개 검색에는 해당 패키지의 주요 8개 주제, 인증 기능과 WebView에는 인증/저장을 추가한다.
`--topic`으로 상세 주제를 좁혀도 기능·공통 계약은 유지한다. Rust 서버 패키지는 클라이언트에 기본 포함하지 않는다.

## 근거와 구조 범위

등록 외부 공식 자료·패턴 출처 63개의 응답 보관본과 읽은 범위를 기록했다.
위키 99개, 구조상 필수 문서 96개, 평가 질문 31개를 연결했다.
원본 Java 31개 컨트롤러·81개 핸들러·89개 메서드/경로 조합의 API 지도도 유지한다.
문서 개수나 `coverage` 성공은 의미 정확성·모든 언어 지식의 충분성·앱 호환성을 인증하지 않는다.
자료 원문은 적용 범위/버전을 확인해 사용하며 예제 버전을 앞으로 만들 앱의 버전으로 간주하지 않는다.

## 실제 실행 근거

- [상세 언어 예제](evidence/2026-10-28-topic-examples-04.json): 다섯 언어 합계 100개 assertion 통과.
  Kotlin 실제 kotlinx.serialization/코루틴, Dart JSON/BigInt/Future, macOS Swift JSONDecoder/Decimal/Task/actor,
  TypeScript strict 타입 검사와 Node, Rust JSON/checked 산술/Tokio/가짜 트랜잭션 제어 흐름을 실행했다.
- [기존 원본 웹 디코더/요청 검사](evidence/2026-10-28-stock-contract.json): 가짜 request와 원본 함수를 사용한 23개 사례.
- [기존 언어 관찰](evidence/2026-10-28-language-01.json), [Unicode 비교](evidence/2026-10-28-unicode.json)는 당시 범위의 기록이다.

위 언어/디코더 예제는 실제 UI·네트워크·서버·DB·OS 브리지·기기 검사가 아니다.
현재 검증 명령과 소스 해시 대조는 [상세 패키지 검증 보고서](evidence/2026-10-28-detailed-packages.json)에 기록한다.
이전 [기준 보고서](evidence/2026-10-28-baseline.json)는 그 시점의 기록이며 최신 입력 해시를 증명하지 않는다.

## 구현 전에 남은 일

정확한 최소 OS·언어/SDK/의존성 버전과 잠금 파일, 앱별 HTTP·디코더·스토리지·인증 어댑터를 확정해야 한다.
독립 언어 예제는 실행했지만 Android/iOS/RN/Flutter/WebView 앱 빌드·실제 기기·쿠키·HTTP/DB·화면 검증은 남아 있다.
특히 origin을 호스트 API에서 획득해 검증하는 WebView 연결은 아직 구현·실행하지 않았다.
예제의 origin 함수는 addJavascriptInterface의 출처 확인 한계를 해결하지 않는다.

대상 앱 버전은 임의 값으로 채우지 않았고 `context --require-ready`는 계속 미결정을 표시한다.
F14는 구현 보류 상태다. 독립 의미 평가와 위키 사용 전후 개발 시간 비교도 아직 없다.
같은 작성 문맥의 확인을 독립 검토로 세지 않으며 시간 절감률·비용을 추정하지 않는다.
