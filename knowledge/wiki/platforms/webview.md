---
title: WebView 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F03", "F04", "E04", "E11", "Q08", "E21", "E22", "E37", "E47"]
---

# WebView 사전 지식

기존 웹을 표시할 호스트의 Android/iOS 범위, 앱·WebView 버전과 제공 URL은 미정이다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| W01 | Android WebView는 앱 안에서 웹을 표시하며 JavaScript 설정·앱 연결·탐색 처리를 구성한다. | 기존 웹의 요청·취소·수동 단가 동작을 유지하고 호스트의 링크·뒤로 가기·키보드와 연결한다. |
| W02 | WKWebView 개요는 HTML·CSS·JavaScript 표시, navigation/UI delegate와 configuration을 통한 탐색·설정을 설명한다. | iOS 호스트 설정과 쿠키·로그인 복귀를 별도 검증한다. Android 결과를 iOS에 그대로 적용하지 않는다. |

W01은 E04, W02는 E11의 개요가 근거다. WKWebView 개요를 읽은 것만으로 로그인·쿠키의 실제 호환을 확인한 것은 아니다.

## 구현 시 확정·실행할 항목

- 원격 웹·앱 번들 중 제공 방식, API 주소·쿠키·저장소와 개발/운영 도메인의 연결.
- Android/iOS 최소 버전, 외부 링크·뒤로 가기·앱 복귀·프로세스 재생성 정책.
- 필요한 호스트 연결 메시지와 접근 범위, 키보드·안전 영역·접근성.
- 웹 자체의 공통 검사와 OS별 호스트 빌드·화면 검증 명령.

웹 로직 재사용과 호스트 검증의 작업 범위를 구분한다. 현재는 호스트별 기초 문서 정리 단계다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

Node의 숫자·날짜·JSON 예제를 실행했다(Q08/E21/E22). Android/iOS WebView 엔진과 호스트 브리지 왕복은 별도 검사해야 한다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 호스트와 웹의 적용 계약

기존 웹 번들을 최대한 재사용하되 Android WebView와 WKWebView를 각각 호스트로 다룬다.
웹의 TypeScript 패키지에 Android의 Kotlin, iOS의 Swift 패키지를 함께 제공한다.
한 OS만 구현할 때는 새 호스트 범위를 명시해 필요한 언어만 남기며 현재 기본 묶음은 양쪽 OS다.

- 원격 URL/로컬 번들·허용 탐색 도메인·외부 링크·back/forward·딥링크 복귀를 호스트별로 정의한다.
- 웹 sessionStorage·쿠키와 네이티브 저장소의 수명·동기화를 검증한다. 브리지가 HttpOnly 쿠키를
  읽어 토큰을 복제하는 방식으로 기존 보안 계약을 바꾸지 않는다.
- Android JavaScript 연결과 WKScriptMessageHandler는 각각 다른 호스트 API다(E04/E37).
  메시지 버전·메서드 allowlist·payload 스키마·요청 ID·응답/오류·호출 origin을 좁혀 검증하도록 제안한다.
- 임의 URL에서 브리지를 쓸 수 있게 하지 않는다. 원문 내부 JavaScript를 네이티브 실행 권한으로 취급하지 않는다.
- 외부 OAuth user-agent 원칙과 기존 서버 callback 계약을 대조한다(E47). 웹 로그인 화면이 표시된다는
  사실만으로 네이티브 로그인 세션 연결까지 검증됐다고 하지 않는다.
- 웹 키보드·safe area·파일 선택·이미지·임베드·접근성·WebView 프로세스 복구를 양쪽에서 검사한다.

## 빌드와 인수 계획

웹 번들/잠금 파일과 두 호스트의 SDK·지원 OS·엔진 정보를 기록한다.
웹 자체 빌드·상태 검사를 먼저 통과시키고 Android/iOS 호스트 빌드와 기기 검사를 따로 수행한다.
검색·수동 단가·쿠키·외부 링크·뒤로 가기·브리지 잘못된 메시지·앱 재시작을 실제 호스트에서 재현한다.
현재 Node/웹 디코더 예제만 실행했으며 WebView 호스트 빌드는 없다.

[웹 언어](../languages/typescript.md), [Kotlin](../languages/kotlin.md), [Swift](../languages/swift.md),
[인증·저장](../shared/auth-storage.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[WebView + TypeScript/Kotlin/Swift 주제별 문서](../packages/webview/index.md)를 공통·기능 계약과 함께 선택한다.
