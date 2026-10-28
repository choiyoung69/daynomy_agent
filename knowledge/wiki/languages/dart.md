---
title: Dart 언어 패키지
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E03", "E09", "E15", "E25", "E32", "E41", "F01", "B04"]
---

# Dart 언어 패키지

Flutter Android/iOS용 Dart를 기본 대상으로 한다. 웹 컴파일을 추가하면 숫자·네트워크 구현을 다시 확인한다.

## 데이터와 직렬화

- 네이티브와 JavaScript 웹의 숫자 표현이 다를 수 있다(E03). ID에 int를 썼다는 이유로
  공통 안전 정수 한도를 없애지 않는다. num.toInt()로 소수를 정수 ID로 허용하지 않는다.
- jsonDecode의 결과는 dynamic이므로(E41), Map·List·숫자·필수 키·허용 enum을 먼저 검사한다.
  런타임 cast 오류를 사용자에게 그대로 노출하지 않고 디코딩 오류로 대응한다.
- nullable 타입과 Map 키 존재는 별개다. 없는 키 조회도 null을 반환하므로(E25)
  필수 필드와 부분 수정에서 containsKey 등으로 존재 의미를 보존한다.
- double만으로 금액의 십진수 정밀도를 보장하지 않는다. 숫자 JSON 파싱 뒤 잃은 정밀도를
  되살릴 수 있다고 가정하지 않는다. 정밀한 금액의 디코더·계산 라이브러리 선택은 별도 결정을 기록하고
  원시 숫자와 전송·표시의 왕복 fixture로 검증한다. 단순 검색·가격 표시와 금액 계산 요구를 구분한다.
- 날짜 전용 값은 검증한 원문/모델을 유지하고, 현지 DateTime·UTC 변환으로 거래일을 이동시키지 않는다.
  문자열 길이·Unicode 정규화는 공통 계약의 단위를 따른다.

## 비동기와 오류

- Future는 값 또는 오류로 완료되고 async/await·try/catch로 처리한다(E15).
  timeout이 발생했다고 원래 네트워크 작업까지 중단됐다고 가정하지 않는다.
- 기본 네이티브 HTTP 어댑터 후보는 dart:io HttpClient다. HttpClientRequest.abort는 연결을 중단하지만
  done이 이미 완료된 뒤에는 효과가 없다(E32). 응답 도착 후 무시할 조건과 화면 수명도 별도로 검사한다.
- 서버 status·업무 code·전송 실패·잘못된 JSON·취소·결과 미확정을 공통 모델로 나눈다.
  catch/finally에서도 최신 요청의 상태인지 확인하고 dispose된 UI를 갱신하지 않는다.

## 모듈 경계

DTO/디코더·순수 입력 규칙·HTTP 인터페이스·저장소·위젯 상태를 분리한다.
웹과 네이티브를 동시에 지원한다면 dart:io를 공통 파일에 직접 가져오지 않고 대상별 어댑터로 둔다.
Flutter SDK와 포함된 Dart 버전, pubspec.lock을 함께 고정한다.

## 필수 검사

int/num/double 경계·잘못된 타입·키 누락/null·금액·날짜·타임아웃 후 완료·abort·dispose를 검사한다.
현재 Dart 런타임과 실제 디코더 실행 증거는 없다.
[Flutter 패키지](../platforms/flutter.md), [공통 데이터](../shared/data-semantics.md), [패키지 구성](../shared/package-map.md).

## 상세 패키지

[Flutter + Dart의 주제별 문서](../packages/flutter-dart/index.md)에서 변환 코드·실행 근거·플랫폼 미검증 범위를 확인한다.
