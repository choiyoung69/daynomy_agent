---
title: android-kotlin — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E44", "E50", "E51", "DX01", "DX09"]
---

# 모듈·의존성·검증 방법

## 예제와 Android 앱의 검증 범위를 분리한다

예제는 Kotlin 2.4.21/JDK21과 kotlinx.serialization 1.12.0을 저장소 .local에 고정했다.
coroutines는 컴파일러 배포에 포함된 JAR의 해시를 기록했다. 이는 앱의 Kotlin/Compose/Gradle 버전 승인과 다르다.

## 실패하는 구성

```kotlin
// UI composable 안에서 URL/JSON/전역 저장소/원장 계산을 모두 처리
@Composable fun Screen() { /* 수명·취소·단위검사가 결합됨 */ }
```

## 적용 모듈 구성

```text
model/       DTO, decoder, 순수 입력/수치 규칙
transport/   HTTP, cancellation, status/code mapping
storage/     guest/session/member cache adapter
presentation/ ViewModel, immutable state, Compose view
```

JSON compiler plugin과 runtime 라이브러리의 호환성, ABI·JVM target·최소 Android SDK를 함께 잠근다.
read-only List를 불변 스냅샷으로 가정하지 않는 규칙도 model 경계에 둔다.

```sh
python3 scripts/knowledge_example_sdks.py
python3 scripts/knowledge_topic_examples.py --output /tmp/new-topic-run.json
```

실제 앱이 생성되면 Gradle wrapper/JDK/SDK를 고정하고 assembleDebug·로컬 단위 검사·기기 검사를 수행한다(E44).
패키지 문서의 코드 조각 중 전체 예제에 포함된 함수만 현재 컴파일/실행 근거가 있다.

## 경계 사례와 확인 범위

타입/JSON·숫자·날짜·컬렉션·취소·세대 모델의 25개 예제를 실행했다. Android 앱/Compose/HTTP/저장소 검증으로 확대하지 않는다.

[실행 가능한 전체 예제](../../../examples/kotlin/Core.kt)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
