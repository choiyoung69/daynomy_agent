---
title: 언어와 플랫폼 공통 자료
confirmed_on: 2026-10-28
review_status: draft
runtime_status: not-run
source_ids: ["E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10", "E11", "E12", "E13", "E14", "E15", "E16", "E17", "E18"]
---

# 언어와 플랫폼 공통 자료

자료를 등록한 것과 본문을 읽고 규칙으로 정리한 것을 구별한다.
확인 날짜는 프로젝트 적용 버전이나 해당 기술의 출시일을 뜻하지 않는다.
외부 내용의 현재 상태는 [자료 목록](../../sources.json)의 읽은 범위·상태와 함께 확인한다.

## 이번에 본문을 확인한 자료

| ID | 자료 | 활용할 범위 |
| --- | --- | --- |
| E01 | [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | 원본·위키·운영 규칙, 자료 추가·질의·점검 |
| E02 | [React Native 플랫폼별 코드](https://reactnative.dev/docs/platform-specific-code) | Platform과 파일 확장자를 이용한 플랫폼별 구성 |
| E03 | [Dart 숫자 표현](https://dart.dev/resources/language/number-representation) | 네이티브와 JavaScript 웹 실행에서의 숫자·정밀도 차이 |
| E04 | [Android WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview) | 웹 표시, 탐색, JavaScript와 앱 연결 |
| E11 | [WKWebView 개요](https://developer.apple.com/documentation/webkit/wkwebview) | 공식 검색 색인에서 개요의 웹 표시·delegate·configuration 설명 확인 |

플랫폼별 세부 자료 E12–E18은 [Android](../platforms/android.md), [iOS](../platforms/ios.md),
[React Native](../platforms/react-native.md), [Flutter](../platforms/flutter.md)에 규칙과 함께 정리했다.
자료의 실제 읽은 절과 URL은 [자료 목록](../../sources.json)에 있다. 대상 프로젝트 버전은 아직 미정이다.

E03은 실행 대상에 따라 숫자 의미가 달라질 수 있음을 보여 준다. 실제 지원할 컴파일 대상과
버전을 정한 뒤 수치 사례를 실행한다. E02는 플랫폼별 구현의 구성법이며 웹 코드의 전체 재사용을
보장하지 않는다. 이식 적용은 [계획 문서](../porting/stock-search-price.md)에 분리한다.

## 개요에서 확인한 공식 자료

아래 개요도 보관해 확인 범위를 기록했다. 개별 규칙은 언어·플랫폼 패키지의 세부 공식 자료를 따른다. E05는 공식 목차 원문이며 언어 규칙의 근거로 쓰지 않는다.

| ID | 자료 | 조사할 질문 |
| --- | --- | --- |
| E05 | [Kotlin 문서](https://kotlinlang.org/docs/home.html) | null·숫자·문자열·비동기 취소를 어떻게 대응하나? |
| E06 | [Jetpack Compose](https://developer.android.com/compose) | 화면 상태와 생명주기를 어떻게 연결하나? |
| E07 | [Swift 언어 안내](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/guidedtour/) | Optional·값 의미·문자열·비동기의 차이는 무엇인가? |
| E08 | [SwiftUI](https://developer.apple.com/documentation/swiftui) | 상태·화면 이동·작업 수명을 어떻게 정하나? |
| E09 | [Dart 언어 안내](https://dart.dev/language) | null·Future·예외·직렬화의 대응은 무엇인가? |
| E10 | [Flutter의 React Native 개발자 안내](https://docs.flutter.dev/flutter-for/react-native-devs) | 상태·탐색·입력·저장·네트워크를 어떻게 대응하나? |

공통 지식 문서는 필요한 질문별로 확장하고, 특정 플랫폼 API를 선택하기 전에 해당 버전의 문서를 읽는다.

## 전체 기술 패키지

현재 외부 출처 63개는 [자료 목록](../../sources.json)의 보관본·확인 범위를 따른다.
[패키지 구성](package-map.md)에서 언어별 문서와 플랫폼 문서를 조합하고, [구축 현황](../../STATUS.md)의 실제 검증 범위를 확인한다.

언어 의미별 실제 적용은 [통합 상세 패키지](../index.md)의 주제 문서와 DX09 실행 범위를 함께 읽는다.
