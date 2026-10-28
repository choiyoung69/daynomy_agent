---
title: React Native 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F01", "F03", "F04", "E02", "E14", "Q08", "E21", "E22", "E30", "E34"]
---

# React Native 사전 지식

TypeScript와 기존 웹의 공통 규칙을 활용하되 브라우저 의존성·실행 버전·대상 OS는 별도로 확인한다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| N01 | React Native는 Fetch를 제공한다. 공식 Networking 문서는 쿠키 인증의 주의점과 네이티브의 웹과 다른 CORS 모델을 설명한다. | F03의 credentials와 갱신 로직을 그대로 인증 호환으로 판단하지 않는다. 서버 주소와 OS별 연결·쿠키를 별도 검증한다. |
| N02 | Platform 모듈과 플랫폼별 파일 확장자로 OS별 코드를 구성할 수 있다. | 공통 모델·규칙과 OS 탐색·입력 처리를 분리하고 Android/iOS를 각각 확인한다. |

N01은 E14, N02는 E02가 근거다. 쿠키 관련 문서의 주의점은 대상 버전의 실제 결함을 확정하는 진단이 아니다.
F04의 window 타이머·DOM form·focus 처리 등 브라우저 의존 부분은 원본 전체에서 조사해야 한다.

## 구현 시 확정·실행할 항목

- TypeScript·JavaScript 런타임, React Native 버전과 JSON 숫자·날짜·null 처리.
- effect 수명과 네이티브 요청 취소, 화면 이탈 후 상태 갱신의 실제 계약.
- UI·탐색·키보드·접근성, 쿠키·로그인·저장소의 OS별 대응.
- Android/iOS 빌드와 검증 명령, 응답 순서·단가 보존 시나리오.

현재는 플랫폼 구성·통신 차이의 일부를 정리했다. 상태·언어·실행 환경 준비는 미완료다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

Node에서 큰 ID의 정밀도 손실·undefined 누락·날짜 이동을 재현했다(Q08/E21/E22). 대상 React Native 런타임에서 다시 확인해야 한다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 플랫폼 적용 계약

기본 제안은 TypeScript + React Native, 요청은 Fetch 어댑터다. 기존 DOM 컴포넌트를 그대로 실행하지 않고
View/Text/TextInput 등의 네이티브 UI로 대응하며 원래의 순수 모델·검증만 재사용한다.
라우터·보안 저장소·쿠키 어댑터는 OS별 계약을 확인한 뒤 선택한다.

- effect 정리는 타이머·구독·이전 요청을 정리하며 취소/늦은 결과 무시를 함께 적용한다(E30).
- 화면이 내비게이션 스택에 남아 있으면 unmount가 아닐 수 있으므로 화면 활성 상태와 요청 수명을 명시한다.
- React state에는 입력 문자열·선택·dirty 단가·요청 세대·로딩·오류를 구분해 둔다.
- window/document/localStorage/import.meta.env·HTML form·CSS·브라우저 focus의 대체를 코드별로 조사한다.
- 플랫폼 파일 확장자와 Platform 분기로 OS 차이를 격리하되 공통 제품 규칙을 복제하지 않는다(E02).
- 키보드 회피·Android back·iOS back gesture·접근성 label·딥링크 복귀를 양쪽에서 검사한다.
- 쿠키와 인증의 문서상 제약을 버전별 실제 결함으로 단정하지 않고 실제 기기에서 검증한다(E14).

## 빌드와 인수 계획

RN·React·TypeScript·Node·네이티브 SDK와 잠금 파일을 같이 고정한다.
생성한 package.json의 타입 검사·테스트·빌드 스크립트를 확인하고 Android Gradle/iOS Xcode 검사를 모두 실행한다.
JS 단위 검사만으로 네이티브 연결·탐색·화면까지 통과했다고 하지 않는다(E34).
현재 Node 예제와 웹 디코더만 실행했고 RN 앱·쿠키·UI 검증은 수행하지 않았다.

[TypeScript 패키지](../languages/typescript.md), [인증·저장](../shared/auth-storage.md),
[UI 상태·탐색](../shared/ui-state-navigation.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[React Native + TypeScript 주제별 문서](../packages/react-native-typescript/index.md)를 공통·기능 계약과 함께 선택한다.
