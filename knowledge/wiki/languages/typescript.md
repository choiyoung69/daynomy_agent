---
title: TypeScript·JavaScript 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E21", "E22", "E29", "E30", "F01", "F02", "F03", "Q08"]
---

# TypeScript·JavaScript 언어 패키지

기존 웹·React Native·WebView 웹 영역이 공유하는 지식이다. DOM과 네이티브 호스트 지식은 플랫폼 패키지에 둔다.

## 데이터와 직렬화

- TypeScript 타입은 네트워크 응답의 실체를 검증하지 않는다. unknown으로 받아 type guard로
  좁히고(E29), 기능별 필수 필드·숫자 범위·enum·null 허용을 확인한다(F01/F03).
- JS number로 파싱한 큰 정수는 이미 손실됐을 수 있다(Q08). Number.isSafeInteger를 적용하고
  잘못된 ID를 문자열 변환으로 복구했다고 설명하지 않는다. BigInt는 기존 숫자 JSON 계약을
  자동 보존하는 대체재가 아니므로 직렬화 경계와 서버 계약을 먼저 정한다.
- undefined 프로퍼티는 객체 JSON에서 빠지고 명시 null은 남는다(E21/Q08).
  `??` fallback과 `||` fallback은 다르다. 0·빈 문자열·null·누락을 섞어 처리하지 않는다.
- 이진 소수 계산을 금액의 반올림 정답으로 삼지 않는다. 원문·계산·표시 단계와 decimal 정책을
  분리한다. baseDate에 `new Date()`를 적용해 현지 날짜로 표시하지 않는다(E22/Q08).
- 문자열 길이와 비교·trim 정책을 서버와 대조한다. 화면 표시는 locale을 사용해도 API 숫자에는
  천 단위 쉼표나 현지 소수 구분자를 보내지 않는다.

## 비동기와 오류

- Promise는 결과 전달 방식이다. 실제 취소는 HTTP 클라이언트에 연결한다.
  AbortController 취소와 최신 요청만 화면에 반영하는 조건을 함께 유지한다.
- React effect는 설정과 정리를 짝지으며 fetch 결과를 취소하거나 무시하는 처리가 필요하다(E30).
  응답·오류·finally의 로딩 갱신 모두 이전 요청인지 확인한다. 개발 모드 재실행을 서버 쓰기 요청의
  중복 수행으로 이어지게 하지 않는다. 사용자 거래는 명시적인 이벤트와 요청 수명으로 처리한다.
- F03의 shared refreshPromise는 공통화할 수 있지만 DOM 쿠키, RN 저장소, WebView 쿠키 환경이
  같은 것은 아니다. 실패한 refresh를 무한 재귀로 재시도하지 않는다.

## 모듈 경계

순수 모델·검증·포맷 규칙과 React hook·DOM·환경변수·스토리지·HTTP를 분리한다.
React Native에서 window/document/localStorage가 있다고 가정하지 않는다.
strict 타입 검사와 런타임 검증을 함께 사용하고 타입 단언으로 응답 검사를 대체하지 않는다.

## 필수 검사

공통 JSON 경계, 204의 빈 본문, 추가 필드·알 수 없는 enum, 응답 역전, unmount, 동시 401,
브라우저 전용 의존성 탐지를 확인한다. Q08은 Node 결과이며 RN/WebView 엔진 검증은 별도다.
[React Native](../platforms/react-native.md), [WebView](../platforms/webview.md), [공통 데이터](../shared/data-semantics.md).

## 상세 패키지

[React Native + TypeScript의 주제별 문서](../packages/react-native-typescript/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.

WebView 호스트와 브리지 경계는 [WebView 패키지](../packages/webview/index.md)를 사용한다.
