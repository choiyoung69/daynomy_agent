---
title: Flutter 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F04", "B04", "E03", "E15", "E16", "E25", "E32", "E35"]
---

# Flutter 사전 지식

Dart·Flutter의 구체적인 버전과 Android/iOS 실행 대상은 미정이다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| D01 | Future는 비동기 작업 결과이며 값 또는 오류로 완료된다. async/await와 try/catch로 결과·실패를 처리한다. | 검색·종가 상태를 성공·오류·로딩으로 구분하고 최신 요청만 반영하는 조건을 설계한다. Future 사용만으로 HTTP 취소를 보장하지 않는다. |
| D02 | setState 콜백은 동기이며 Future를 반환하면 안 된다. dispose 후 호출은 오류다. 공식 문서는 mounted 검사만 하기보다 원인 작업을 취소하는 방식을 권한다. | 네트워크 대기와 상태 반영을 분리하고 이탈·취소·최신 요청을 확인한다. |
| D03 | Dart의 네이티브와 JavaScript 웹 대상은 숫자 표현·정밀도가 다를 수 있다. | 실제 컴파일 대상을 정하고 큰 ID와 소수 가격을 디코딩·표시까지 비교한다. |

D01은 E15, D02는 E16, D03은 E03이 근거다. 실제 HTTP 취소 지원은 선택할 클라이언트에서 확인한다.

## 구현 시 확정·실행할 항목

- Dart의 null·문자열·JSON 모델, B04의 가격·거래일을 보존할 정책과 입력 fixture.
- HTTP·직렬화·상태 관리·탐색 방식, 화면 수명과 요청 취소의 연결.
- 키보드·접근성·저장·인증 대응과 양쪽 OS 지원 범위.
- SDK·OS 버전과 빌드·단위/위젯/통합 검사 명령.

현재 비동기·상태 수명·숫자 차이 일부가 문서화됐다. 플랫폼 실행 검증은 없다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

Dart Map 조회는 키 누락에 null을 반환하므로 명시 null과 구분할 때 키 존재 검사도 필요하다(E25). Dart 도구 부재로 실행은 남아 있다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 플랫폼 적용 계약

기본 제안은 Dart + Flutter, 네이티브 요청은 dart:io HttpClient 어댑터다. 서버 DTO·순수 검증·저장소·위젯 상태를 분리한다.
상태 관리 도구를 고르기 전에 입력값·선택·dirty 단가·요청 세대의 소유자를 정한다.

- await 이후에는 mounted 여부와 요청 세대를 함께 확인하고 dispose에서 요청·타이머·컨트롤러를 정리한다(E16).
- setState 안에서 비동기를 수행하지 않는다. Future.timeout과 실제 request.abort의 역할을 구분한다(E32).
- 숫자 모델·동적 JSON·null/키 누락은 Dart 패키지와 고정 fixture로 검증한다.
- Route pop·modal·back gesture·백그라운드 복귀에서 초안과 서버 변경 상태를 구분한다.
- 키보드·안전 영역·글자 크기·스크린 리더 semantics·초점·스크롤을 실제 위젯/기기에서 확인한다.
- Android/iOS 쿠키·로그인 복귀·비밀 저장소 플러그인은 독립적인 플랫폼 의존성으로 잠근다.

## 빌드와 인수 계획

Flutter SDK와 포함된 Dart 버전, pubspec.lock, Android/iOS 도구를 고정한다.
생성한 프로젝트에서 flutter analyze, flutter test, Android debug 빌드와 iOS simulator debug 빌드를 계획한다.
위젯 검사·integration_test의 시나리오와 양쪽 OS 기기 조건을 기록한다(E35).
현재 Dart/Flutter 도구가 PATH에 없어 해당 명령을 실행하지 않았다.

[Dart 패키지](../languages/dart.md), [인증·저장](../shared/auth-storage.md),
[UI 상태·탐색](../shared/ui-state-navigation.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[Flutter + Dart 주제별 문서](../packages/flutter-dart/index.md)를 공통·기능 계약과 함께 선택한다.
