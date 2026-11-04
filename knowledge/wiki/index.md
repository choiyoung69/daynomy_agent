---
title: 지식베이스 목차
confirmed_on: 2026-10-28
review_status: static-reviewed
runtime_status: not-run
source_ids: ["E01", "P02", "G01", "F01", "F04"]
---

# 지식베이스 목차

[구축 현황](../STATUS.md)에서 지식 구조와 실제 앱 검증의 범위를 확인한다.
[패키지 구성](shared/package-map.md)에 따라 공통·기능·언어·플랫폼을 조합한다.

## 공통 기술과 운영

| 문서 | 확인 상태 |
| --- | --- |
| [인증·쿠키·CSRF·저장소 이식](shared/auth-storage.md) | 정적 정리 |
| [빌드 환경과 대상 버전 준비](shared/build-validation.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [클라이언트 이식의 공통 준비 기준](shared/client-porting-baseline.md) | 정적 정리 |
| [언어별 숫자·날짜·null·JSON 경계](shared/data-semantics.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [오류와 재시도 및 요청 취소](shared/error-retry-cancel.md) | 정적 정리 |
| [원문 보관과 위키 갱신 절차](shared/knowledge-maintenance.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [공통·언어·플랫폼·기능 패키지 조합](shared/package-map.md) | 정적 정리 |
| [언어와 플랫폼 공통 자료](shared/reading-list.md) | 초안 |
| [다섯 플랫폼 검증과 시간 측정](shared/testing-migration.md) | 정적 정리 |
| [트랜잭션·동시성과 클라이언트 책임](shared/transactions-concurrency.md) | 정적 정리 |
| [UI 상태·탐색·접근성 이식 기준](shared/ui-state-navigation.md) | 정적 정리 |

## 언어 패키지

| 문서 | 확인 상태 |
| --- | --- |
| [Dart 언어 패키지](languages/dart.md) | 정적 정리 |
| [Kotlin 언어 패키지](languages/kotlin.md) | 정적 정리 |
| [Rust 백엔드 언어 패키지](languages/rust.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [Swift 언어 패키지](languages/swift.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [TypeScript·JavaScript 언어 패키지](languages/typescript.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |

## 플랫폼 패키지

| 문서 | 확인 상태 |
| --- | --- |
| [Android 네이티브 사전 지식](platforms/android.md) | 정적 정리 |
| [Flutter 사전 지식](platforms/flutter.md) | 정적 정리 |
| [iOS 네이티브 사전 지식](platforms/ios.md) | 정적 정리 |
| [React Native 사전 지식](platforms/react-native.md) | 정적 정리 |
| [WebView 사전 지식](platforms/webview.md) | 정적 정리 |

## DAYNOMY 기능

| 문서 | 확인 상태 |
| --- | --- |
| [회원 정보·닉네임·탈퇴](projects/daynomy/account.md) | 정적 정리 |
| [관리자 콘텐츠·피드백](projects/daynomy/administration.md) | 정적 정리 |
| [인증·세션](projects/daynomy/auth-session.md) | 정적 정리 |
| [종목 자료·공개 콘텐츠·인물](projects/daynomy/content-people.md) | 정적 정리 |
| [뉴스·통합 검색](projects/daynomy/content-search.md) | 정적 정리 |
| [피드백](projects/daynomy/feedback.md) | 정적 정리 |
| [투자 캘린더](projects/daynomy/investment-calendar.md) | 정적 정리 |
| [뉴스·키워드·시장 분석](projects/daynomy/news.md) | 정적 정리 |
| [이메일 알림 보류 경계](projects/daynomy/notifications-deferred.md) | 정적 정리 |
| [AI 분석·재사용·근거·이력](projects/daynomy/portfolio-analysis.md) | 정적 정리 |
| [포트폴리오 평가 계산](projects/daynomy/portfolio-calculation.md) | 정적 정리 |
| [보유자산·거래 원장·수익률](projects/daynomy/portfolio-ledger.md) | 정적 정리 |
| [DAYNOMY 전체 서비스 지식 목록](projects/daynomy/service-catalog.md) | 정적 정리·실행 근거 연결(범위는 문서 참조) |
| [종목 검색과 최근 종가](projects/daynomy/stock-search-price.md) | 정적 정리 |
| [종목·종가·환율](projects/daynomy/stocks-exchange.md) | 정적 정리 |
| [Android 뉴스·환율의 실제 이식 경계](projects/daynomy/android-news-exchange.md) | 별도 역할의 JVM·실제 HTTP/DB 검사, 기기 결과는 실행 기록에서 구분 |
| [수집·동기화·배치](projects/daynomy/sync-jobs.md) | 정적 정리 |

## 이식 계획

| 문서 | 확인 상태 |
| --- | --- |
| [종목 검색과 가격 조회 이식 계획](porting/stock-search-price.md) | 초안 |

[출처](../sources.json), [미확인 질문](../questions.md), [평가 기준](../evals/README.md), [이력](../log.md).

## 언어·플랫폼 통합 상세 패키지

### [Android + Kotlin](packages/android-kotlin/index.md)

[타입·null·JSON](packages/android-kotlin/types-and-json.md) · [숫자·금액](packages/android-kotlin/numbers-and-money.md) · [날짜·Unicode](packages/android-kotlin/dates-and-unicode.md) · [컬렉션·모델 복사](packages/android-kotlin/collections-and-models.md) · [비동기·취소](packages/android-kotlin/async-and-cancellation.md) · [상태·탐색·수명](packages/android-kotlin/state-and-navigation.md) · [오류·트랜잭션](packages/android-kotlin/errors-and-transactions.md) · [인증·저장소](packages/android-kotlin/auth-and-storage.md) · [모듈·의존성·검증](packages/android-kotlin/modules-and-testing.md)

### [iOS + Swift](packages/ios-swift/index.md)

현재 앱의 iOS 17·Swift 6 선택과 SDK 검사 경로는 [iOS 준비 문서](platforms/ios.md)를 따른다. SDK/코어/상태/화면의 실제 검증 범위는 [후속 실행 기록](../../experiments/ios-sdk-verification/README.md)에서 구분한다.

[타입·null·JSON](packages/ios-swift/types-and-json.md) · [숫자·금액](packages/ios-swift/numbers-and-money.md) · [날짜·Unicode](packages/ios-swift/dates-and-unicode.md) · [컬렉션·모델 복사](packages/ios-swift/collections-and-models.md) · [비동기·취소](packages/ios-swift/async-and-cancellation.md) · [상태·탐색·수명](packages/ios-swift/state-and-navigation.md) · [오류·트랜잭션](packages/ios-swift/errors-and-transactions.md) · [인증·저장소](packages/ios-swift/auth-and-storage.md) · [모듈·의존성·검증](packages/ios-swift/modules-and-testing.md)

### [React Native + TypeScript](packages/react-native-typescript/index.md)

[타입·null·JSON](packages/react-native-typescript/types-and-json.md) · [숫자·금액](packages/react-native-typescript/numbers-and-money.md) · [날짜·Unicode](packages/react-native-typescript/dates-and-unicode.md) · [컬렉션·모델 복사](packages/react-native-typescript/collections-and-models.md) · [비동기·취소](packages/react-native-typescript/async-and-cancellation.md) · [상태·탐색·수명](packages/react-native-typescript/state-and-navigation.md) · [오류·트랜잭션](packages/react-native-typescript/errors-and-transactions.md) · [인증·저장소](packages/react-native-typescript/auth-and-storage.md) · [모듈·의존성·검증](packages/react-native-typescript/modules-and-testing.md)

### [Flutter + Dart](packages/flutter-dart/index.md)

[타입·null·JSON](packages/flutter-dart/types-and-json.md) · [숫자·금액](packages/flutter-dart/numbers-and-money.md) · [날짜·Unicode](packages/flutter-dart/dates-and-unicode.md) · [컬렉션·모델 복사](packages/flutter-dart/collections-and-models.md) · [비동기·취소](packages/flutter-dart/async-and-cancellation.md) · [상태·탐색·수명](packages/flutter-dart/state-and-navigation.md) · [오류·트랜잭션](packages/flutter-dart/errors-and-transactions.md) · [인증·저장소](packages/flutter-dart/auth-and-storage.md) · [모듈·의존성·검증](packages/flutter-dart/modules-and-testing.md)

### [WebView + TypeScript/Kotlin/Swift](packages/webview/index.md)

[타입·null·JSON](packages/webview/types-and-json.md) · [숫자·금액](packages/webview/numbers-and-money.md) · [날짜·Unicode](packages/webview/dates-and-unicode.md) · [컬렉션·모델 복사](packages/webview/collections-and-models.md) · [비동기·취소](packages/webview/async-and-cancellation.md) · [상태·탐색·수명](packages/webview/state-and-navigation.md) · [오류·트랜잭션](packages/webview/errors-and-transactions.md) · [인증·저장소](packages/webview/auth-and-storage.md) · [모듈·의존성·검증](packages/webview/modules-and-testing.md)

### [Rust 백엔드](packages/rust-backend/index.md)

[타입·null·JSON](packages/rust-backend/types-and-json.md) · [숫자·금액](packages/rust-backend/numbers-and-money.md) · [날짜·Unicode](packages/rust-backend/dates-and-unicode.md) · [컬렉션·모델 복사](packages/rust-backend/collections-and-models.md) · [비동기·취소](packages/rust-backend/async-and-cancellation.md) · [상태·탐색·수명](packages/rust-backend/state-and-navigation.md) · [오류·트랜잭션](packages/rust-backend/errors-and-transactions.md) · [인증·저장소](packages/rust-backend/auth-and-storage.md) · [모듈·의존성·검증](packages/rust-backend/modules-and-testing.md)

## 제한된 앱 실행 결과

[WebView 종목 검색·종가 파일럿](../../runs/013-webview.md)은 웹/Android 실제 흐름과 iOS 미검증을 구분한다. 지식 입력·고정 테스트·수정·독립 리뷰 근거를 함께 확인한다. 다른 플랫폼/전체 기능의 실행 완료를 뜻하지 않는다.
# Android의 작은 상태 수정 진입점

검색어·선택 해제·가격 초안 수정은 [Android 작업 안내](../../clients/android/README.md)의
`android_knowledge.py ensure query-reset`으로 필요한 3문서를 선택한다.
다른 기능의 필수 지식을 대체하지 않으며 변경 시점의 준비·출처·해시는 계속 검사한다.

Android F11은 [피드백](projects/daynomy/feedback.md)의 원문 검증·CSRF 규칙과
인증/JSON/취소 문서 4개를 선택한다. [실행 기록](../../runs/024-android-feedback.md)은
실제 앱 화면 검사와 Rust/DB 미검증을 구분한다.
