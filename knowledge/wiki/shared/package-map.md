---
title: 공통·언어·플랫폼·기능 패키지 조합
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E01", "E02", "E03", "E04", "E11", "P02"]
---

# 공통·언어·플랫폼·기능 패키지 조합

언어별 패키지는 필요하다. 같은 언어라도 Android/iOS 수명·UI·쿠키·빌드가 다르므로
공통 계약 + 언어 + 플랫폼 + 기능을 조합한다. 구현 라이브러리나 배포 패키지가 아니라 AI에 전달하는 지식 묶음이다.

| 개발 방식 | 언어 패키지 | 플랫폼 패키지 |
| --- | --- | --- |
| Android 네이티브 | Kotlin | Android·Compose·JVM |
| iOS 네이티브 | Swift | iOS·SwiftUI·Foundation |
| React Native | TypeScript/JavaScript | RN·Android/iOS 네이티브 연동 |
| Flutter | Dart | Flutter·Android/iOS |
| WebView | TypeScript/JavaScript + Kotlin + Swift | 기존 웹·Android WebView·WKWebView 양쪽 호스트 |
| Rust 백엔드 조사 | Rust | 서버·DB의 기존 계약. 클라이언트에 기본 제공하지 않음 |

## 내용의 소유 위치

- 공통에는 데이터 경계·오류 분류·트랜잭션·인증 원칙·상태와 검증 방법을 둔다.
- 언어에는 타입·null·문자열·직렬화·예외·비동기·의존성 경계를 둔다.
- 플랫폼에는 UI 상태 소유자·탐색·수명·입력·접근성·호스트·HTTP/저장소·빌드 계획을 둔다.
- 기능에는 DAYNOMY의 메서드·경로·필드·상태·제약·원본 차이와 인수 사례를 둔다.

동일한 서버 정책을 언어마다 재작성하지 않는다. 공통 문서를 링크하고 해당 언어의 구현상 차이만 추가한다.
React Native와 WebView는 언어를 공유하지만 플랫폼 문서와 실제 실행 증거는 각각 갖는다.

## 작업 전달

`knowledge.py context --feature <기능> --platform <대상>`은 packs.json에 선언한 공통·기능 문서,
대상 언어/플랫폼 진입점과 연결된 통합 상세 패키지의 주요 주제를 출력한다. 전체 원문·다른 플랫폼·평가 기대 답변은 기본 출력하지 않는다.
출처 ID와 고정 보관 위치를 함께 제공해 필요할 때 원문을 찾아갈 수 있다.
`knowledge.py package --language kotlin`은 언어 문서만 읽는 진입점이다.

문서의 범위가 채워진 상태와 구현 준비 완료를 구분한다. 버전·라이브러리의 정확한 잠금·도구 준비와
실행 검증은 `--require-ready`에서 별도로 확인한다. 문서 검사 통과를 앱 성공으로 표시하지 않는다.

## 구축 범위

1차 지식베이스는 기존 서비스 명세 F01–F13의 기능·F14의 보류 경계, 언어 5개,
플랫폼 5개, 공통 기술 주제, 원문 관리와 평가 절차를 다룬다.
세상의 모든 라이브러리나 언어 기능을 수집하는 것을 완료 기준으로 삼지 않는다.
기능·언어·플랫폼 중 누락된 조합은 coverage 검사에서 드러내고, 실제 앱 이식 완료는 별도 검증한다.

[서비스 기능 목록](../projects/daynomy/service-catalog.md), [데이터](data-semantics.md),
[인증·저장](auth-storage.md), [UI 상태](ui-state-navigation.md), [검증](testing-migration.md).

## 상세 패키지와 주제 선택

언어와 플랫폼의 구현상 차이는 `wiki/packages/` 아래 한 묶음으로 관리한다.
`packs.json`의 packages는 각 묶음의 목차·9개 주제·언어·대상 플랫폼을 고정한다.
`context` 기본은 주요 8개 주제이며 인증 기능 및 WebView는 인증/저장을 추가한다.
`--topic`을 반복하면 기능·공통 계약을 유지하며 상세 주제만 좁힌다. 생략 주제의 구현 필요성을 없애지 않는다.

```sh
python3 scripts/knowledge.py package --package android-kotlin --topic types-and-json
python3 scripts/knowledge.py context --feature portfolio-ledger --platform flutter --topic errors-and-transactions
```

`package`는 자료 읽기이며 준비 상태 승인 명령이 아니다. 지원 버전·미결정·검토 상태는 context의
`--require-ready`로 따로 확인하며 그 통과도 앱 실행 성공을 의미하지 않는다.
[상세 묶음 목록](../index.md), [현재 검증 범위](../../STATUS.md).
