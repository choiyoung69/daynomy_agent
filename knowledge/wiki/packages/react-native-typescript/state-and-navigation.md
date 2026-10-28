---
title: react-native-typescript — UI 상태·탐색·수명
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["E30", "E02", "F04", "DX04", "DX09"]
---

# UI 상태·탐색·수명

## 화면 활성 상태와 mount 상태를 구분한다

네이티브 탐색 스택에서 화면이 보이지 않아도 컴포넌트는 mount 상태로 남을 수 있다.
탐색 도구를 선택한 뒤 화면 활성 이벤트와 요청 수명을 연결한다. 공통 React effect 정리만으로 탐색 정책을 확정하지 않는다.

## 실패하는 변환

```typescript
useEffect(() => { search(query).then(setRows); }, [query]);
// cleanup·요청 세대·선택 변경·수동 단가 편집을 무시
```

## 실행한 순수 상태 모델

```typescript
class Gate {
  generation = 0;
  alive = true;
  result: string | undefined;
  begin() { return ++this.generation; }
  accept(token: number, value: string) {
    if (!this.alive || token !== this.generation) return false;
    this.result = value;
    return true;
  }
  dispose() { this.alive = false; this.generation++; }
}
```

실제 hook 적용에서는 effect마다 token을 만들고 cleanup에서 abort하며, 성공/오류/finally 모두 현재 token을 확인한다(E30).
모델은 검색어·선택 assetId·dirty 단가·loading·빈 결과·오류를 구분한다.

| UI 사건 | 확인 |
| --- | --- |
| 종가 요청 중 직접 입력 | 값과 dirty 상태 유지 |
| 검색어/국가 변경 | 이전 결과·오류·로딩 갱신 차단 |
| Android back/iOS gesture | 화면 이동과 미확정 거래 결과 분리 |
| 앱 복귀 | 초안 보존과 서버 재조회 조건 적용 |

TextInput 키보드·IME·접근성 label·키보드 회피·safe area는 기기별로 확인한다.

## 경계 사례와 확인 범위

실행: Gate의 B 유지/A 무시/dispose 무시. React hook/탐색/접근성 UI 코드는 아직 실행하지 않았다.

[실행 가능한 전체 예제](../../../examples/typescript/core.ts)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
