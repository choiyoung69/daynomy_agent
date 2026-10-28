---
title: rust-backend — 숫자·금액·반올림
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["B04", "R02", "P02", "Q08", "DX05", "DX09"]
---

# 숫자·금액·반올림

## f64와 SQL numeric의 경계를 명시한다

현재 서버 금액을 일괄 f64로 바꾸면 BigDecimal/numeric의 십진수 의미와 달라진다(B04/R02).
간단한 입력에는 checked 고정 스케일 정수를 사용할 수 있지만 그 함수의 문법/범위와 업무 반올림을 구분해야 한다.

## 실패하는 변환

```rust
let units = (user_price * 100.0) as i128;
// 반올림 정책·오버플로·자릿수·음수/NaN 처리를 숨긴다.
```

## 실행한 입력 변환 예

```rust
fn minor_units(raw: &str, scale: u32) -> Option<i128> {
    let (whole, fraction) = raw.split_once('.').unwrap_or((raw, ""));
    if whole.is_empty() || !whole.bytes().all(|c| c.is_ascii_digit()) ||
       !fraction.bytes().all(|c| c.is_ascii_digit()) || fraction.len() > scale as usize ||
       (raw.contains('.') && fraction.is_empty()) { return None; }
    let factor = 10i128.checked_pow(scale)?;
    whole.parse::<i128>().ok()?.checked_mul(factor)?.checked_add(
        if fraction.is_empty() { 0 } else {
            fraction.parse::<i128>().ok()?.checked_mul(10i128.checked_pow(scale - fraction.len() as u32)?)?
        })
}
```

이 예제는 부호 없는 문자열을 고정 scale 정수로 읽고 초과 소수/오버플로를 거절한다.
DB의 numeric 연산, 환율6/단가4/비용2, HALF_UP, 입력 최소값을 전부 구현한 함수가 아니다(P02).
JSON 숫자→문자열 경로도 lexical precision을 보존해야 한다. as_f64로 경유한 뒤 복구했다고 하지 않는다.

| 입력 | 기대 |
| --- | --- |
| 1.20 / scale2 | 120 |
| 1.005 / scale2 | 초과 자릿수 거절 |
| 매우 큰 정수 | checked 연산/파싱에서 거절 |
| 음수·부호·통화 기호 | 현재 문법 거절 |

## 경계 사례와 확인 범위

실행: 고정 스케일·초과 소수·큰 수 거절. 전체 원장 수치/DB numeric 왕복은 과거/별도 서버 검사로 확인한다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
