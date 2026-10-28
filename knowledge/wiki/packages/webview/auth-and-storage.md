---
title: webview — 인증·저장소·호스트 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E57", "E37", "E47", "E04", "E11", "DX01", "DX03", "DX04", "DX09"]
---

# 인증·저장소·호스트 경계

## 출처는 메시지 본문이 아니라 호스트가 관찰한 프레임에서 확인한다

Android addJavascriptInterface는 호출 프레임 origin을 확인할 수 없는 경계가 있으므로(E57)
메시지의 `origin` 필드를 신뢰하는 검사는 충분하지 않다. 임의 외부 페이지에 특권 브리지를 노출하지 않는다.
WKScriptMessageHandler도 frame/main-frame/security origin과 허용 method/payload를 함께 검토한다(E37).

## 실패하는 검사

```typescript
if (message.origin === TRUSTED_ORIGIN) runPrivilegedAction(message);
// message.origin은 공격자가 쓸 수 있다.
```

## 실행한 순수 호스트 정책

```kotlin
fun trustedBridgeOrigin(originFromHost: String, isMainFrame: Boolean): Boolean =
    isMainFrame && originFromHost == "https://app.example.invalid"
```

```swift
func trustedBridgeOrigin(_ originFromHost: String, isMainFrame: Bool) -> Bool {
    isMainFrame && originFromHost == "https://app.example.invalid"
}
```

예제의 app.example.invalid는 설명용 고정 origin이다. 실제 프로젝트에서는 호스트가 수신 API에서 얻은
scheme/host/port/main-frame 정보를 검증해 정규화해야 하며 JSON 본문에서 이 인자를 가져오면 안 된다.
이 함수만으로 addJavascriptInterface의 origin 확인 한계가 해결되지 않는다. 검증 가능한 메시지 API와
지원 버전/프레임 정책을 선택하거나 브리지를 신뢰한 제한 콘텐츠에만 노출하는 설계를 따로 검토한다.

웹 쿠키/HttpOnly·WK website data store·네이티브 저장소는 별개다. 토큰을 JS로 꺼내 복제하지 않는다.
OAuth는 외부 user-agent 원칙과 서버 callback 계약을 따른다(E47).

## 경계 사례와 확인 범위

실행: Kotlin/Swift 정책 함수의 신뢰 origin 허용·다른 origin/하위 프레임 거절, TS 메시지 스키마. 실제 수신 origin 획득과 OS 브리지 바인딩은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
