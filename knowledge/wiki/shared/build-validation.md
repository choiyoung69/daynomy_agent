---
title: 빌드 환경과 대상 버전 준비
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["Q08", "Q09", "DX09", "DX10"]
---

# 빌드 환경과 대상 버전 준비

현재 호스트에서 작은 언어 예제를 실행할 수 있는 범위와 대상 앱을 빌드할 준비는 다르다.
[도구 조사 Q09](../../evidence/2026-10-28-build-inventory.json)에 명령·종료 코드·확인 시점을 보존했다.

| 대상 | 현재 호스트에서 확인 | 착수 전에 고정할 것 |
| --- | --- | --- |
| Android | JDK 21.0.12, Gradle 경로 있음. adb·sdkmanager·kotlinc는 PATH에서 찾지 못함. SDK 디렉터리 전체 설치 여부는 미조사. | 최소/대상/컴파일 SDK, Kotlin·Compose·Gradle 플러그인, HTTP/JSON 의존성과 에뮬레이터/기기. |
| iOS | Swift 6.3.3으로 macOS 예제 실행. 활성 개발 경로는 Command Line Tools이며 xcodebuild -version 종료 1, simctl 조회 종료 72. | Xcode·지원 iOS·Swift 언어 모드, 시뮬레이터와 scheme/destination, 실제 디코더. |
| React Native | Node 22.23.1 예제 실행. RN 프로젝트·런타임 빌드 없음. | RN·TypeScript·런타임·양쪽 OS 버전, 패키지 잠금, 네이티브 도구 연결. |
| Flutter | dart·flutter는 PATH에서 찾지 못함. | Flutter·Dart 버전과 양쪽 OS 도구, 패키지 잠금, 대상 기기. |
| WebView | Node 실행만 확인. Android WebView·WKWebView 호스트 없음. | 웹 번들 식별자, 제공 URL/로컬 방식, 각 OS 호스트 버전과 웹 엔진, 브리지 범위. |

설치된 도구 버전을 곧바로 앱의 지원 버전으로 선택하지 않는다. 선택한 버전은 [packs.json](../../packs.json)의
selected_versions에 기록하고 의존성·실제 빌드 설정과 대조한다. 현재 값은 미정으로 유지한다.
서명·스토어 배포·운영 환경 연결은 이 준비 작업에 포함하지 않는다.

## 실제 앱 검사로 이어지는 순서

1. 지원 OS·플랫폼 범위와 기능 계약을 정하고 도구·의존성을 고정한다.
2. 생성한 프로젝트의 실제 빌드·단위 검사 명령을 파일에 기록하고 실행한다. 아직 없는 프로젝트의 명령을 실행 성공으로 기록하지 않는다.
3. [데이터 경계 예제](data-semantics.md)를 선택한 디코더·런타임으로 옮겨 기대값을 검증한다.
4. 검색 A/B 응답 역전·화면 이탈·수동 단가 보존·빈 결과·404·잘못된 응답을 실제 앱에서 확인한다.
5. 두 OS를 대상으로 하는 방식은 양쪽에서 실행하고, 결과·버전·소스 해시를 연결한다.

첫 공개 조회의 실행 계획과 회원 거래의 DB 검증 계획을 구분한다. 언어 예제 26개 관찰값의 일치는
HTTP 연결·화면 상태·쿠키 호환성·앱 빌드의 검증을 대체하지 않는다.
현재 다섯 묶음의 준비 판정은 미완료다.

## 상세 패키지 보강 이후

위 도구 표는 Q09 조사 시점의 PATH 결과다. 이후 예제용 Kotlin 2.4.21·Dart 3.13.7·TypeScript 6.0.2를
`.local/knowledge-sdks`에 격리해 추가했고 [다섯 언어 100개 사례](../../evidence/2026-10-28-topic-examples-04.json)를 실행했다.
전역 PATH·앱 SDK/버전은 바꾸지 않았다. macOS Swift·JVM·Dart VM·Node 검사를 앱 빌드로 표시하지 않는다.
[상세 패키지 목차](../index.md)의 실행/미실행 범위와 [재실행 절차](../../README.md)를 따른다.
