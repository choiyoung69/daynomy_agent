---
title: webview — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E04", "E11", "E37", "E57", "E34", "DX04", "DX09"]
---

# 모듈·의존성·검증 방법

## 웹·Android 호스트·iOS 호스트를 독립 빌드 단위로 관리한다

WebView를 선택해도 호스트 검증은 남는다. 웹 번들/제공 URL·웹 의존성 잠금과 Android/iOS SDK·엔진·호스트 버전을 각각 기록한다.
플랫폼 API는 웹 도메인 모델에서 분리한다.

## 실패하는 구성

```text
웹 공통 코드 → Android/iOS 특권 메서드를 직접 가정
호스트 → 임의 URL 탐색과 같은 브리지 권한 공유
```

## 적용 구성

```text
web/core/       기존 모델·디코더·화면 상태
web/bridge/     versioned envelope, request registry, adapter
android/host/   trusted-origin/message/navigation/lifecycle binding
ios/host/       trusted-frame/message/navigation/lifecycle binding
```

공통 JSON fixture를 TS와 양쪽 네이티브 디코더에 적용하고, 같은 id의 왕복·timeout·탐색·프로세스 복구를 테스트한다.
웹 단위 검사와 네이티브 정책 함수는 앱 호스트 E2E를 대체하지 않는다.

```sh
python3 scripts/knowledge_topic_examples.py --output /tmp/new-bridge-topic-run.json
```

현재는 TS close protocol과 Kotlin/Swift 순수 origin 정책을 실행했다. Android/WKWebView 앱과 브리지 실제 왕복은 없다.

## 경계 사례와 확인 범위

문서의 API/version/출처·메시지·권한 경계를 먼저 고정한 후 두 호스트 기기 검사를 수행해야 한다. 실제 앱 검증으로 과장하지 않는다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
