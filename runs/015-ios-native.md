# iOS 네이티브 첫 파일럿

사용자 요청: 서로 다른 서브에이전트의 테스트 작성 → 구현 → 독립 검증 구조로,
로컬 iOS·Swift KB를 우선 사용하고 빈 부분만 웹 검색하며 최대한 병렬 진행한다.
첫 묶음은 종목 검색 → 선택 → 최근 저장 종가 → 수동 단가 보존이다.
전체 프론트 이식은 후속 묶음이며 리그·F14 이메일 알림·배포는 제외한다.

## 진행과 역할

중앙 시각 확인은 2026-10-28 18:12:01 KST다. 최초 요청부터 이 시각까지의
전체 경과를 측정했다고 주장하지 않는다. 역할 배정은 [설정](../agents/ios-native.json)을 따른다.
테스트 작성·구현·검증은 각각 다른 새 문맥의 에이전트다.
환경 조사와 테스트 작성, 구현 준비를 병렬 진행한다. 기능 구현은 해당 테스트의 실제 red 실행과
해시 고정 이후 시작한다. 검증 준비는 구현과 겹치며 실제 DB 검사는 공유 잠금으로 직렬 실행한다.

## KB와 환경

[입력 자료·소스 해시](../experiments/ios-native/knowledge-packet.json)에 기준을 기록한다.
`knowledge.py check`는 로컬 출처 108/108, 위키 99개, 고정 외부 응답 63개 검사에 성공했다.
이는 의미 평가·앱 실행 검증이 아니다. iOS `context --require-ready`는 버전·수명·빌드 준비
미완료로 종료 2이며, 이를 임의로 준비 완료로 변경하지 않는다.

파일럿의 구현 기본값은 iOS 17 이상·Swift 6 언어 모드다. 호스트 도구는 Swift 6.3.3이다.
현재 활성 개발 경로는 `/Library/Developer/CommandLineTools`이며 `xcodebuild -version`은
full Xcode 필요 오류로 종료 1이다. iOS SDK 빌드·시뮬레이터 실행은 별도 준비가 필요하다.
원본·기존 미커밋 Android/WebView/KB 작업을 보존한다.

## 현재 상태

**코어·실제 HTTP 검사는 통과했으며, iOS SDK 빌드·화면 실행은 환경 부재로 보류다.**
전체 프론트 또는 iOS 앱 전체 완료를 선언하지 않는다. 구현은 [클라이언트](../clients/ios/README.md),
후속 전체 기능의 의존 관계는 [이식 지도](../spec/ios-native/porting-map.md)에 있다.
최종 [독립 리뷰](../experiments/ios-native/verification/review.md)는 이 한정된 호스트 코어·HTTP
근거를 수용하고 iOS 앱 전체 승인은 보류했다. [조정자 최종 대조](../experiments/ios-native/acceptance.json)는
클라이언트 16개 파일 해시 불변·검사 성공·남은 플랫폼 검증을 확인했다.
최종 대조 시각은 18:29:30 KST다. 중앙 시각 확인 18:12:01부터 약 17분 29초이며,
그 이전 요청·준비와 이후 보고 시간은 포함하지 않는다. 전체 iOS 완료 시간이나 병렬 배속이 아니다.

## 실제 결과와 고정 기준

| 검사 | 결과와 근거 |
| --- | --- |
| 첫 테스트 고정 | [최초 기준](../experiments/ios-native/test-author/frozen-tests.json): 실제 빈 구현에서 22개 코어 본문 실행·실패 assertion 32개·종료 1. 계약·러너·테스트·UI 테스트 소스 7개 해시 고정 |
| 구현 인계 | [인계 대조](../experiments/ios-native/handoff.json): 18:18:09 KST, 고정 7개·임시 stub 2개·원본 3개 해시 일치 이후 API/모델 구현 허용 |
| 추가 회귀 | [추가 기준](../experiments/ios-native/test-author/supplemental-query-freeze.json): 실제 HTTP에서 발견한 `+` 손실. 정확한 수정 전 소스를 격리 복사해 총 23개 실행·새 assertion 3개만 실패·종료 1. 최초 기준은 보존 |
| 코어 최종 | [별도 검증](../experiments/ios-native/verification/candidate-result.json): 총 23개 본문 실행·실패 0·종료 0. 코드·테스트·프로젝트 해시를 실행 전후 대조 |
| 실제 URLSession | [루프백](../experiments/ios-native/verification/loopback.json): Unicode·리터럴 `+`·긴 십진수·업무/일반 404·잘못된 JSON 숫자·요청 취소. 서버에서 TCP 연결 종료도 관찰 |
| 독립 숫자 경계 | [추가 검증](../experiments/ios-native/verification/supplemental-result.json): 14개 assertion 성공. 긴 선행 0+지수 ID·중복 키 마지막 값·미세 양수의 원문 보존/자동 채움 거절 포함 |
| 실제 Rust/DB 연결 | 같은 추가 검증: 7개 assertion 성공. 실제 URLSession → StockAPI → Rust → 합성 PostgreSQL 조회. KR/US·숨김 제외·검색 제한·최근 날짜/정밀 소수·가격 없음 확인 |
| iOS 소스 정적 검사 | [화면 검토](../experiments/ios-native/verification/ui-static-review.json): plist/project·scheme XML·Swift 구문·모델 연결 검토. iOS SDK 타입 검사/앱 실행을 대체하지 않음 |

코어 검사는 **canonical Swift Testing 런타임을 실행한 결과가 아니다.** 현재 CLT는 테스트를
컴파일해도 `lib_TestingInterop.dylib`가 없어 실행에 실패했다. 별도 작성자가 같은 테스트
본문의 `#expect`/`#require`를 assertion 함수로 바꿔 실행하는 고정 러너를 작성했고, 제3의
검증자가 현재 문법의 변환 의미를 검토했다. 23개 실행 수와 실패 0을 외부 검증기에서도 확인한다.
순차·MainActor 실행은 원래 Swift Testing의 스케줄링과 다르다. 임의 미래 매크로까지 지원하는
일반 테스트 프레임워크로 설명하지 않는다. 기존 컴파일·로더 실패 로그도 보존한다.

## 실제 HTTP에서 발견한 결함과 수정

가짜 transport의 URLComponents 디코딩은 문자 `+`를 보존해 기존 22개 테스트가 통과했다.
실제 폼 쿼리 디코더는 raw `+`를 공백으로 읽어 검색어가 바뀌었다. 독립 HTTP 검증에서
실패를 확인한 뒤 `%2B` 인코딩을 추가했다. 추가 테스트 작성 전에 수정이 먼저 반영된
사실도 숨기지 않는다. 별도 작성자는 이전 API의 정확한 SHA를 확인한 격리 복사본에 새 검사를
실행해 재현했고, 새 기준과 실제 실패를 별도로 고정했다. 최초 테스트가 이 문제를
구현 전에 잡았다고 표현하지 않는다.

원본 대조로 지수 ID의 선행 0 처리, 아주 작은 가격의 양수 판정, JSON 중복 키 마지막 값
처리도 보완했다. [원본 대조 보완](../spec/ios-native/clarifications.md)에 호환 수정과 의도적
네이티브 매핑을 구별한다. 테스트·명세를 약화해 실패를 없애지 않았다.

## 공유 DB 자원과 병렬성

새 조정기나 SDK 설치기를 만들지 않고 기존 `android_backend_fixture.py`를 재사용했다.
이 대화의 첫 fixture 시도는 다른 검사가 공유 잠금을 보유해 대기했다. 이미 실행 중인
합성 fixture의 [소스·바이너리 식별](../experiments/ios-native/verification/shared-fixture-identity.json)을
확인한 뒤 읽기 전용 조회만 재사용했다. 이 대화가 시작한 대기 프로세스만 정확한 PID로
종료했으며 타 작업의 서버·DB는 중단하지 않았다. [취소 기록](../experiments/ios-native/fixture-cancellation.json).

실제 검증은 serving fixture의 시작 시 전체 소스 목록·바이너리 SHA와 현재 시장/API 소스를
대조했다. 실행 전후 현재 트리의 차이는 다른 작업의 `app/README.md`뿐이며 명시적으로 남겼다.
소스 전체가 실행 도중 완전히 같았다고 주장하지 않는다. DB를 새로 수정하거나 외부 제공자를
호출하지 않았다. 최근 날짜 검사는 알려진 데이터와 SQL `ORDER BY`를 대조한 범위이며
삽입 순서를 따로 뒤집는 DB 변형 검사는 하지 않았다.

테스트 작성과 환경·화면 프로젝트 준비를 겹쳤고, 구현 중 검증 도구와 후속 기능 지도를
준비했다. 같은 기능의 테스트 고정 → 구현 → 실제 검증 의존 관계는 유지했다.
순차 대조 실행이 없어 병렬 배속·비용 절감을 추정하지 않는다.

## 남은 검증과 재개

- full Xcode·iOS SDK·선택한 Simulator runtime 준비. [환경 증거](../experiments/ios-native/verification/environment.json).
- 실제 scheme/destination 조회 후 iOS build와 2개 독립 XCUITest 실행. 해당 테스트 소스는
  작성·타깃 연결만 완료했으며 아직 컴파일/실행하지 않았다.
- 작은 iPhone/가로 방향·큰 Dynamic Type·VoiceOver·밝음/어두움·키보드·배경 복귀 인수.
- canonical `swift test`를 정상 Testing 런타임에서 실행. 현재 호스트 대체 검사의 한계를 유지한다.
- 전체 프론트의 뉴스/콘텐츠·검색·인증/계정·포트폴리오·캘린더·분석·피드백·관리자 묶음은
  후속 이식 지도에 있으며 이번 파일럿 구현에 포함하지 않는다. 네이티브 OAuth 콜백/쿠키 연결과
  게스트 저장 수명은 실제 서버·제품 계약을 확정해야 한다.

현재 호스트에서 같은 코어 본문을 재검사하는 명령:

```sh
python3 experiments/ios-native/test-author/run_host_tests.py
```

Xcode 준비 후 UI 테스트의 독립 합성 fixture는 아래 명령으로 실행한다. 이 fixture는
화면 검사용이며 Rust/DB 연결 증거와 구별한다. 이후 실제 조회한 Simulator destination으로
`DaynomyIOS` scheme의 `test`를 실행한다. 이 명령을 현재 호스트에서 실행했다고 기록하지 않는다.

```sh
python3 experiments/ios-native/verification/ui_fixture.py
```
