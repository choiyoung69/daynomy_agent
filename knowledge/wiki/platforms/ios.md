---
title: iOS 네이티브 사전 지식
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["F04", "B04", "E13", "E18", "E26", "Q08", "E08", "E33", "E42", "E43", "E49"]
---

# iOS 네이티브 사전 지식

Swift·SwiftUI는 현재 후보이며 지원 OS·언어 버전은 미정이다.

## 공식 근거와 이식 적용

| ID | 공식 자료에서 확인한 내용 | 이식에 적용할 제안 |
| --- | --- | --- |
| I01 | Swift 작업 취소는 협력적이다. 작업이 취소를 확인하고 대응해야 하며, 작업 완료 순서는 보장되지 않는다. | 새 검색 때 이전 작업을 취소하고, 취소·최신 요청 여부를 확인한 뒤 결과를 반영한다. |
| I02 | SwiftUI의 task(id:…) 문서는 관찰 값이 바뀌면 작업을 취소·재생성하고 화면이 사라질 때 완료 전 작업을 취소할 수 있다고 설명한다. | 선택한 OS에서 사용 가능한 오버로드와 상태 소유자를 정한 뒤 검색·화면 수명에 대응한다. |

I01은 E13의 Tasks and Task Groups와 Task Cancellation, I02는 E18의 Discussion이 근거다.
E18은 현재 문서의 오버로드이며 그대로 최소 OS 지원 API라고 확정하지 않는다.

## 구현 시 확정·실행할 항목

- Optional·누락 필드·String 의미와 JSON 디코딩, 정수 범위·십진수·날짜 전용 값의 대응.
- 최소 iOS·Swift 버전, UI 상태 격리와 네트워크·직렬화 API의 구체적 선택.
- 취소 후 화면 변경 방지, 검색어·선택·수동 단가의 화면 이탈·복귀 정책.
- 빌드·단위/화면 검사 명령과 공통 숫자·날짜·응답 순서 사례.

현재 규칙은 공식 자료 정리와 이식 제안이며 실제 iOS 구현을 검증한 결과가 아니다.
[준비 상태](../../packs.json), [공통 준비](../shared/client-porting-baseline.md), [남은 질문](../../questions.md).

## 데이터·도구 준비 보강

macOS Swift 예제에서 Int64, Optional 누락/null, Decimal, 문자열 차이를 확인했다(Q08/E26). iOS 런타임과 선택한 디코더의 검증은 남아 있다.
[공통 경계와 재현 근거](../shared/data-semantics.md), [빌드 환경](../shared/build-validation.md)을 따른다.

## 플랫폼 적용 계약

기본 제안은 Swift + SwiftUI + Foundation URLSession/JSONDecoder다(E08/E42/E43).
앱 모델과 view 의존성을 분리하고(E33) UI 갱신의 actor 격리를 명시한다.
Observation의 SwiftUI 지원은 iOS 17부터라는 공식 조건을 확인했으며(E33),
더 낮은 지원 OS를 선택하면 대응 상태 모델을 별도로 정한다. 현재 최소 OS를 승인된 값으로 확정하지 않는다.

- 검색어·국가·선택·dirty 단가·요청 세대를 모델에서 관리하고 task(id:)의 사용 가능한 오버로드를 SDK와 대조한다.
  E18의 name/file/line 매개변수 설명은 새 OS 조건이 있으므로 오래된 OS에 그대로 적용하지 않는다.
- Task 취소·URLSession 어댑터·최신 요청 반영을 함께 검사한다. view 이탈과 모델 소멸을 같다고 가정하지 않는다.
- NavigationStack·sheet 닫기·딥링크 복귀·백그라운드 복귀의 입력 보존과 요청 수명을 기록한다.
- Decimal·날짜 전용 모델·Optional·문자열 UTF-16 길이를 Swift 패키지와 공통 fixture로 확인한다.
- VoiceOver 이름·동적 글자 크기·안전 영역·키보드 가림·포커스 오류 이동을 검사한다.
- 쿠키 저장소·CSRF·외부 브라우저 로그인·Keychain 경계는 인증 문서를 따른다.

## 빌드와 인수 계획

Xcode 선택 경로·SDK·Swift 언어 모드·지원 iOS·scheme·simulator destination을 잠근다.
생성한 프로젝트에서 xcodebuild -list로 실제 scheme을 확인한 뒤 build/test 명령과 destination을 기록한다.
현재 호스트는 활성 Xcode/시뮬레이터가 준비되지 않아 이 빌드를 실행하지 않았다.
선택한 OS에서 화면 이탈·재진입·응답 역전·입력 보존·쿠키/로그인 복귀를 재현한다.

[Swift 패키지](../languages/swift.md), [인증·저장](../shared/auth-storage.md),
[UI 상태·탐색](../shared/ui-state-navigation.md), [검증](../shared/testing-migration.md).

## 상세 패키지

[iOS + Swift 주제별 문서](../packages/ios-swift/index.md)를 공통·기능 계약과 함께 선택한다.
