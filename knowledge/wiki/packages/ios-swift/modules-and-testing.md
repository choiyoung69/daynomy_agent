---
title: ios-swift — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E13", "E56", "E33", "E42", "DX03", "DX09"]
---

# 모듈·의존성·검증 방법

## 예제의 Swift 버전과 앱 SDK를 구분한다

현재 순수 예제는 macOS의 Swift 6.3.3에서 Swift 6 모드로 컴파일했다.
Foundation JSON·Decimal·값/참조·actor·취소를 확인했지만 Xcode/iOS SDK 빌드를 수행하지 않았다.

## 실패하는 모듈 구성

```swift
struct Screen: View {
    // view가 HTTP, Codable, 인증, 영구 저장, 거래 검증을 모두 직접 소유
}
```

## 적용 구성

```text
Domain/      값 모델, 입력 규칙, decimal/date 정책
API/         DTO, decoder, status/code, URLSession adapter
Storage/     guest/member cache and secret store interfaces
Presentation/ actor-isolated state, view, navigation
```

프로토콜 경계의 가짜 구현으로 순수 상태를 검사하고, 실제 URLSession/보안 저장소/SwiftUI는 별도 통합 검사한다.
Sendable·actor 경고를 타입 단언이나 무분별한 unchecked 선언으로 덮지 않는다(E13/E56).

```sh
python3 scripts/knowledge_topic_examples.py --output /tmp/new-swift-topic-run.json
```

앱 생성 후 Xcode 경로·지원 iOS·SDK·scheme·destination·Swift 언어 모드를 고정하고 build/test를 실행한다.
단일 macOS 예제 성공을 iOS 모든 버전의 호환으로 표현하지 않는다.

## 경계 사례와 확인 범위

현재 실행한 Swift 예제 18개와 기기/호스트 미실행 범위를 함께 확인한다. 예제의 강제 언래핑은 고정 리터럴 검증용이며 사용자 입력 처리 방식으로 복사하지 않는다.

[실행 가능한 전체 예제](../../../examples/swift/Core.swift)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
