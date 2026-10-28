---
title: Kotlin 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E23", "E24", "E17", "E31", "E40", "E45", "E46", "F01", "B04"]
---

# Kotlin 언어 패키지

Android/JVM에서 사용하는 언어 지식이다. Compose·화면 수명은 Android 패키지에서 조합한다.
아래 라이브러리 구성은 이번 이식의 기본 제안이며 빌드 호환성을 검증한 선택은 아니다.

## 데이터와 직렬화

- ID는 Long으로 디코딩하되 공통 계약의 양의 안전 정수 범위를 별도로 검사한다(F01/E23).
  Long을 Double로 거쳐 파싱하지 않는다. Int로 축소하는 변환은 범위 검사 후 수행한다.
- 가격·수량·통화는 별개 값이다. JVM의 BigDecimal과 날짜 전용 타입을 사용하는 방향을 제안한다.
  서버 전송 형식은 기존 숫자 JSON을 유지하고, 십진 값의 문자열 원문에서 파싱하는 어댑터를 둔다.
  kotlinx.serialization JsonPrimitive.content는 따옴표 없는 내용을 주지만 JsonNull도 문자열 "null"을
  반환하므로 null·숫자·문자열 타입 확인을 먼저 해야 한다(E46).
- `T?`는 null 허용이다(E24). 필드 누락·null·기본값은 JSON 설정과 모델 선언까지 함께 결정한다.
  kotlinx.serialization의 explicitNulls 기본값은 true이고 false일 때 누락 처리도 달라진다(E31).
  ignoreUnknownKeys 기본값은 false다(E40). 기존 웹이 허용하는 추가 필드를 유지하려면 허용 설정과
  필수 필드 검사를 각각 고정한다. 잘못된 타입·enum을 기본값으로 조용히 바꾸지 않는다.
- 검색 길이의 UTF-16 기준과 Unicode 정규화는 공통 계약을 따른다. 문자열을 바이트 수로 잘라내지 않는다.
  JSON 라이브러리 설정·직렬화 어댑터·기대 fixture는 같은 패키지 버전으로 검사한다.

## 비동기와 오류

- suspend 호출을 썼다는 사실만으로 모든 작업이 즉시 중단되지 않는다. 취소는 협력적이다(E17).
  CancellationException을 일반 네트워크 실패로 삼켜 UI 오류나 재시도로 바꾸지 않는다.
- HTTP 기본 후보는 OkHttp다. 공식 원문의 Canceling a Call을 근거로 실제 Call 취소를 연결하되(E45),
  coroutine 취소·Call 취소·콜백의 늦은 결과 무시를 모두 어댑터 계약에 포함한다.
- 성공 HTTP라도 응답 디코딩이 실패할 수 있다. HTTP status, 업무 code, 필드 오류, 전송 실패,
  디코딩 실패, 취소, 변경 결과 미확정을 구분해 공통 오류 모델에 대응한다.
- blocking I/O와 무거운 파싱은 UI 실행 흐름에서 분리한다. UI 반영 시 최신 요청 식별자도 확인한다.

## 모듈 경계

API DTO/디코더, 순수 규칙, 저장소 인터페이스, HTTP 어댑터, UI 상태를 분리한다.
Java 원본의 DTO를 그대로 가져와 null과 예외 의미까지 같다고 가정하지 않는다.
외부 라이브러리는 Gradle 잠금과 Kotlin/직렬화 플러그인 호환 버전을 함께 기록한다.

## 필수 검사

큰 ID·정수 오버플로·소수 경계·null/누락/추가 필드·잘못된 enum·날짜·문자열 길이,
취소 후 결과 반영·동시 401·응답 유실을 공통 fixture와 대조한다.
Kotlin 컴파일러와 디코더의 실제 실행은 아직 없다. 문서 준비와 런타임 증거를 구분한다.
[Android 패키지](../platforms/android.md), [공통 데이터](../shared/data-semantics.md), [패키지 구성](../shared/package-map.md).

## 상세 패키지

[Android + Kotlin의 주제별 문서](../packages/android-kotlin/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.
