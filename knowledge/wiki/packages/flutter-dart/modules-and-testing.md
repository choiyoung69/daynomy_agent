---
title: flutter-dart — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E35", "E41", "E32", "DX02", "DX09"]
---

# 모듈·의존성·검증 방법

## Dart 실행 예제와 Flutter 앱을 따로 잠근다

순수 예제는 Dart 3.13.7 네이티브에서 실행했다. 이 버전이 앞으로 선택할 Flutter SDK에 포함된 버전과
자동으로 같지는 않다. Flutter SDK·포함 Dart·pubspec.lock·플러그인 네이티브 의존성을 함께 잠근다.

## 실패하는 구성

```text
공통 모델 파일 → dart:io 직접 import
웹 빌드 추가 → 같은 모델과 HTTP를 그대로 사용
```

## 적용 구성

```text
model/         DTO, validated inputs, money/date, pure state
transport/     native HTTP adapter; web target needs a separate adapter
storage/       guest/member cache and secret store interfaces
presentation/  widgets, state owner, navigation
```

JSON 타입 검사는 경계에서 수행하고, 위젯은 검증한 모델을 받도록 한다. 상태 도구를 선택해도
입력과 HTTP·DB·화면 수명 검사의 책임이 사라지지 않는다.

```sh
python3 scripts/knowledge_topic_examples.py --output /tmp/new-dart-topic-run.json
# Flutter 앱 생성 후: flutter analyze / flutter test / 플랫폼별 빌드·integration_test
```

단위·위젯·통합 검사의 범위는 E35를 따른다. 현재 Flutter SDK/앱/기기 검사는 수행하지 않았다.

## 경계 사례와 확인 범위

네이티브 Dart JSON·BigInt 스케일·날짜·컬렉션·Future·Gate 예제를 실행했다. Flutter 위젯·플러그인·웹 컴파일 검증은 별도다.

[실행 가능한 전체 예제](../../../examples/dart/core.dart)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
