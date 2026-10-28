---
title: rust-backend — 날짜·시간대·Unicode
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["Q08", "G11", "P02", "B02", "R01", "DX05", "DX09"]
---

# 날짜·시간대·Unicode

## UTF-8 바이트 수와 서버 계약의 길이 단위는 다르다

Rust String.len은 UTF-8 바이트 수다. JS/Java의 UTF-16 길이와 동일하게 적용하면 emoji 등에서 차이가 난다(Q08/G11).
날짜 전용 값과 시각을 타입/파싱 정책으로 구분하고 원본의 서울/뉴욕/시스템 시간대 조건을 보존한다(P02).

## 실패하는 변환

```rust
if input.len() > 50 { return Err("TOO_LONG"); }
// 원래 UTF-16 50 단위 제한을 바이트 50개로 축소할 수 있다.
```

## 적용 관찰

```rust
assert_eq!("😀".len(), 4);
assert_eq!("😀".chars().count(), 1);
assert_eq!("😀".encode_utf16().count(), 2);
assert_eq!("\u{a0}삼성\u{a0}".trim(), "삼성");
```

trim의 Unicode 공백과 Java strip의 차이는 이미 실제 예제로 확인했다(G11).
원본 검색어를 SQL LIKE로 만들 때 `%`/`_`/escape 문자와 대소문자 정규화도 언어 공백 처리와 별도로 대조한다.
날짜 parser를 교체할 때 잘못된 달력 날짜·윤년·today/timeZone·허용 범위를 사례로 고정한다.

## 경계 사례와 확인 범위

실행: UTF-8/UTF-16 관찰 및 기존 Java/Rust 공백 비교. 실제 SQL 검색과 전체 시간대 경계는 별도다.

[실행 가능한 전체 예제](../../../examples/rust/src/main.rs)와 [언어 예제 실행 결과](../../../evidence/2026-10-28-topic-examples-04.json)를 함께 읽는다.
보고서는 순수 언어·JSON·상태·취소 예제의 결과다. 이 문서의 UI/HTTP/DB/호스트 통합 코드까지 실행했다는 뜻은 아니다.
[패키지 목차](index.md), [공통 데이터](../../shared/data-semantics.md), [검증 기준](../../shared/testing-migration.md).
