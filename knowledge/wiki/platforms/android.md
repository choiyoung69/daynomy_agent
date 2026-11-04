---
title: Android 네이티브 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F04", "B04", "E12", "E17", "E23", "E24", "E36", "E44", "E45", "AP01", "AP02", "AP03"]
---

# Android 네이티브 사전 지식

종목 검색·최근 종가 파일럿의 Kotlin/Compose 버전과 계약을 확정했다. 아래 초기 준비 계획과 현재 파일럿 선택을 구분한다. 다른 기능의 Android 준비 완료를 뜻하지 않는다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| A01 | Compose의 remember는 재구성 사이 값을 보관하지만 해당 composable이 제거되면 잊는다. rememberSaveable은 저장 가능한 상태의 복원을 지원한다. | 검색어·선택·수동 단가의 소유자와 화면 재생성 후 유지 범위를 명시한다. 모든 상태를 자동 영구 저장으로 해석하지 않는다. |
| A02 | CoroutineScope.cancel의 취소는 협력적이므로 연산의 즉시 종료를 뜻하지 않는다. | 이전 요청 취소와 최신 요청만 상태에 반영하는 조건을 함께 설계한다. 선택할 HTTP 라이브러리의 취소 계약을 따로 확인한다. |

A01은 E12의 State in composables, A02는 E17의 취소 설명이 근거다.
웹 F04의 250ms 대기·요청 취소·수동 단가 보존은 같은 시나리오로 확인한다.

## 구현 시 확정·실행할 항목

- Kotlin의 null·문자열·정수와 JSON 라이브러리의 실제 디코딩 정책, B04 가격·날짜 타입의 대응.
- 최소 Android·Kotlin·Compose 버전, HTTP·직렬화 라이브러리와 개발 서버 주소.
- 화면 이탈·재생성에서 상태와 작업 수명의 연결, 키보드·탐색·접근성.
- 빌드·단위/화면 검사 명령, 늦은 응답·수동 단가·날짜·숫자 사례의 fixture.

상태·취소 규칙과 데이터 기초를 문서화한 단계다. 인증·저장·전체 앱 이식과 대상 실행은 남아 있다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

Kotlin의 Long/Double 범위와 nullable 타입을 E23/E24에서 확인했다. JSON 디코더의 누락·null·정밀도 처리는 선택 후 실행해야 한다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 플랫폼 적용 계약

기본 제안은 Kotlin/JVM + Compose, UI 상태 소유자는 ViewModel/단방향 데이터 흐름이며(E36),
화면 상태와 입력 초안·서버 저장 데이터의 수명을 분리한다. HTTP는 OkHttp, JSON은 kotlinx.serialization 후보를 사용한다.
정확한 버전은 Kotlin/Compose/Gradle 플러그인의 호환 조합과 잠금 파일로 확정한다.

- 검색어·국가·선택 종목·수동 단가·현재 요청 세대는 하나의 화면 상태에서 관리한다.
  remember/rememberSaveable을 요청·서버 캐시의 수명과 같은 것으로 취급하지 않는다.
- 화면 수명에 맞춰 Job과 Call을 함께 정리하고, 늦은 콜백의 결과·오류·로딩 반영을 막는다.
- 화면 재생성·프로세스 재시작 후 복원할 데이터만 저장하고 인증 비밀은 일반 상태 Bundle에 넣지 않는다.
- 숫자 키보드와 지역 소수점 입력을 처리하고, TalkBack label·오류 연결·동적 글자 크기·IME 가림을 확인한다.
- Activity/내비게이션 back과 거래 모달 닫기의 상태 처리를 구분한다. 뒤로 가기로 거래 롤백을 가정하지 않는다.
- 쿠키·CSRF·외부 브라우저 로그인 callback·API 개발 주소는 환경별 어댑터로 둔다.

## 빌드와 인수 계획

프로젝트 생성 후 Gradle wrapper·JDK·SDK·minSdk/targetSdk/compileSdk를 고정한다.
실제 모듈이 app일 때 assembleDebug/testDebugUnitTest, 기기 준비 후 connectedDebugAndroidTest를 실행하도록 계획한다(E44).
디코더/상태 로컬 검사와 에뮬레이터·실기기 검사를 나누며 현재는 실행하지 않았다.
검색 응답 역전·국가 전환·회전·복귀·수동 단가·접근성·동시 401을 공통 인수 사례와 연결한다.

[Kotlin 패키지](../languages/kotlin.md), [인증·저장](../shared/auth-storage.md),
[UI 상태·탐색](../shared/ui-state-navigation.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[Android + Kotlin 주제별 문서](../packages/android-kotlin/index.md)를 공통·기능 계약과 함께 선택한다.

## 현재 파일럿 선택 — 2026-10-28

적용 기능은 stock-search-price뿐이다. minSdk26/compile·target35, Kotlin·Compose plugin2.1.20,
Compose BOM2025.04.01, AGP8.9.2/Gradle8.11.1/JDK21, OkHttp4.12.0/JSON1.8.1을 고정했다.
[실행 계약](../../../spec/android-native/README.md), [독립 검증 계획](../../../spec/android-native/verification-plan.md),
[환경 근거](../../../experiments/android-native/evidence/environment.json)를 따른다.
빈 구현의 APK 생성만 실행했으며 기능 성공이나 기기 검증 완료가 아니다.
숫자·날짜·취소·초안 복원 정책은 해당 계약에서 정했다. 버전 선택을 Android 전체 기능 준비로 확대하지 않는다.
