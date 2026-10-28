---
title: react-native-typescript — 모듈·의존성·검증 방법
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E02", "E34", "E29", "DX04", "DX09"]
---

# 모듈·의존성·검증 방법

## 순수 코드와 RN 의존 코드를 분리한다

Node에서 실행한 TS 함수는 DOM·네이티브 모듈·Metro·OS API 호환성을 검증하지 않는다.
기존 웹의 모델/검증은 재사용할 수 있지만 JSX·form·focus·CSS·Vite 설정은 별도 대응이 필요하다(E02/E34).

## 실패하는 구성

```text
shared.ts → imports document, window, localStorage, import.meta.env
RN 화면 → shared.ts를 그대로 import
```

## 적용 구성

```text
core/        DTO guard, field presence, numeric/date, pure state
adapters/    HTTP, storage, environment, platform module
ui/          RN components, hooks, navigation, accessibility
```

순수 예제는 TypeScript 6.0.2 strict 타입 검사와 Node22 타입 제거 실행을 사용한다.
ES2022/DOM 타입은 예제의 AbortController 등을 검사하기 위한 환경이며 실제 RN 타입 정의/엔진 선택을 대신하지 않는다.

```sh
python3 scripts/knowledge_topic_examples.py --output /tmp/new-ts-topic-run.json
```

RN 프로젝트를 만들면 RN/React/TS/Node·네이티브 SDK·lockfile을 고정하고 JS 단위·네이티브 모듈·양쪽 OS E2E를 구분한다.

## 경계 사례와 확인 범위

현재 순수 TS 예제·원본 웹 디코더는 실행했다. RN 빌드·Metro·네이티브 모듈·UI/E2E는 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
