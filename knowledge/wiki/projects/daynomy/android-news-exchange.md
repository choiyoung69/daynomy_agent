---
title: Android 뉴스·환율 이식에서 확인한 경계
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: evidence-linked
source_ids: ["P02", "W07", "W08", "F01", "AP04", "AP05"]
---

# Android 뉴스·환율에서 재사용할 지식

다음 이식에서는 이 문서를 먼저 읽고 [뉴스](news.md), [종목·환율](stocks-exchange.md),
[타입](../../packages/android-kotlin/types-and-json.md), [금액](../../packages/android-kotlin/numbers-and-money.md)을 필요한 만큼 조합한다.
정확한 공개 계약·원본 근거·의도적 차이는 [고정 명세](../../../../spec/android-native/discovery.md)에 있다.

- 뉴스 목록의 기본 요청은 page=1/size=6이다. 서버 기본15와 다르므로 명시해서 보낸다.
  응답 분류의10개 값과 서버 조회 필터의3개 값(부동산/주식/ETF)은 서로 다르다.
- 목록 imageUrl/publishedAt은 null을 허용하되 누락은 거절한다. 상세 imageUrl은 누락/null을
  허용하지만 imageSource는 누락만 허용하고 명시적 null은 거절한다. 상세 publishedAt은 문자열이어야 한다.
- 상세 content는 문자열 또는 문자열 배열이다. 문자열은 웹 화면처럼 줄바꿈으로 나누고 빈 문단만
  제거한다. 공백만 있는 문단과 배열의 내용은 유지한다. 출처·이미지 저작자·라이선스 필드는 보존한다.
- stock의 안전한 양수 ID 검사를 뉴스에 무조건 복사하지 않는다. 웹 뉴스는 Number.isInteger를 사용한다.
  Kotlin 모델은 signed Long의 정확한 범위를 사용한다. JS가 반올림하는 범위까지 완전 동치라는 뜻은 아니다.
- 환율은 요청 날짜와 실제 기준일이 다를 수 있다. 화면에 둘을 구분한다. rate 원문을 BigDecimal로
  읽고 형식·유한한 양수 조건을 검사한다. 원본 JS의 1e-400은0으로 언더플로해 거절되지만
  5e-324는 양수로 남는다. BigDecimal.signum만 검사하면 원본과 다른 경계가 된다.
- 클라이언트 입력 날짜·page·size의 추가 강화 검증으로 서버 오류를 숨기지 않는다.
  API 오류·형식 오류·취소·빈 정상 결과를 구분하고 자동 재전송하지 않는다.
- 목록과 상세는 별도 Job·요청 세대가 필요하다. 뒤로 가기는 상세 요청만 무효화하고 목록/페이지는
  유지한다. 탭 이탈·화면 중지는 요청을 취소하며 복귀 때 현재 선택을 다시 조회한다.
- 네이티브 공통 탭을 추가하면 기존 검색 결과·오류 버튼이 IME에 가려질 수 있다. 새 기능 검사만
  통과해도 기존 기기 회귀를 함께 실행한다. 조회 때 focus 해제와 키보드 숨기기를 구분하고,
  노드 존재 대기만으로 화면에 보이는 시점이 보장되지 않는다는 점을 확인한다.
- 원본 뉴스 목록의 Content-Type 검증과 JSON/필드 디코딩은 서로 다른 검사다. 이번 전송 추상화는
  성공 본문만 노출하므로 MIME 헤더 동치까지 구현했다고 보고하지 않는다.

테스트 작성·구현·검증은 서로 다른 역할이었다. 검증자가 발견한 환율 언더플로 경계를
테스트 작성자에게 보강 요청한 뒤 기존 기준을 유지하며 확인했다.
[실제 JVM/HTTP/DB 근거](../../../../experiments/android-native/next/verification-core.json)는
88개 JVM·10개 실제 Rust/합성 DB 검사다. 이 숫자에는 이전 종목·종가 회귀가 포함된다.
화면·기기·접근성·배포의 성공 근거로 이 코어 결과를 대신 사용하지 않는다.
[실행 기록](../../../../runs/015-android-native-parallel.md)의 별도 기기 결과와 제한을 확인한다.
