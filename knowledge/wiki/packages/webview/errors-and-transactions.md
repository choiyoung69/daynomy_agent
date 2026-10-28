---
title: webview — 오류·자원·트랜잭션 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E19", "R02", "E37", "E57", "DX04", "DX09"]
---

# 오류·자원·트랜잭션 경계

## 오류 응답에도 요청 식별과 권한 경계를 유지한다

브리지 decode 실패·허용하지 않은 origin/method·호스트 기능 실패·HTTP 업무 오류·timeout·결과 미확정을 구분한다.
실패한 브리지 요청을 임의 JavaScript 실행으로 복구하지 않는다.

## 실패하는 변환

```typescript
catch (error) { webView.evaluateJavaScript(error.rawScript); }
// 신뢰하지 않은 내용을 실행 경계로 되돌린다.
```

## 적용 응답 제안

```json
{"v":1,"id":"req_1","ok":false,"error":{"code":"METHOD_NOT_ALLOWED","message":"허용되지 않은 동작"}}
```

이 응답 스키마는 제안이며 현재 close decoder의 입력 검사와 별도로 네이티브/웹 구현에 추가해야 한다.
응답에도 id·version·한 번만 완료 규칙을 적용한다. 내부 예외/토큰/경로를 그대로 전달하지 않는다.
거래의 서버 적용 상태는 HTTP 계약과 확인 API를 따르며 브리지 오류가 DB 롤백 증거는 아니다(E19/R02).

중복 요청 id, 같은 callback의 이중 실행, 이미 폐기된 웹 페이지에 도착한 응답을 실패 사례로 고정한다.

## 경계 사례와 확인 범위

입력 프로토콜의 거절 사례는 실행했다. 응답 스키마·evaluateJavaScript 호출·실제 거래/브리지 실패 통합은 미실행이다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
