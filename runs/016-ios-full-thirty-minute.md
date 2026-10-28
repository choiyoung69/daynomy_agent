# iOS 전체 비리그 기능 — 30분 확장

2026-10-28 최신 사용자 요청은 첫 파일럿이 아닌 전체 기능 구현이다. 30분 안에 전체가
어려우면 핵심 기능을 우선하라는 조건을 적용한다. 시작은 18:30:59 KST,
목표 마감은 19:00:59 KST다. 이전 파일럿의 구현·검증 시간은 여기에 포함하지 않는다.

## 배정과 우선순위

[배정 기록](../agents/ios-full.json)에 따라 별도 테스트 작성자, 두 구현자, 독립 검증자를
사용한다. 동시 네 작업을 모두 실행하는 것이 아니라 조정자 포함 네 슬롯 안에서
테스트 작성자가 고정한 묶음을 즉시 넘기고 그 슬롯을 다음 구현자로 전환한다.
조정자는 앱 진입점·탭·프로젝트 파일을 연결한다.

로컬 KB → 연결 원본 → 해결되지 않는 공백의 공식 웹 자료 순서를 유지한다.
포트폴리오·거래·뉴스·검색·분석·캘린더·인증·계정·피드백을 우선하고 관리자 작업을 확장한다.
리그·F14 이메일 알림·배포는 제외한다. 전체 원본 화면과 차이는
[이식 지도](../spec/ios-native/porting-map.md)를 기준으로 확인한다.

## 기준과 초기 실패

- [서비스 묶음](../experiments/ios-full/test-author/bundle-1-freeze.json): 기존 23개와 새 13개,
  총 36개 실행에서 실패 11개를 확인한 뒤 계약·검사·러너를 고정했다.
- [거래 묶음](../experiments/ios-full/test-author/bundle-2-freeze.json): 새 9개를 더한 총 45개,
  당시 서비스/거래 stub의 실패 18개를 확인했다. 구현 중 서비스가 통과한 뒤 거래만 실패하는
  상태와 최종 전체 통과 상태를 구별한다.
- [UI 개정 기준](../experiments/ios-full/test-author/ui-v2-freeze.json): 앱 진입이 포트폴리오
  탭으로 바뀌어 기존 두 UI 검사의 진입 동작에 종목 탭 선택만 추가했다. 이전 소스·diff를
  보존하고 새로운 전체 탭 검사 소스를 더했다. iOS에서 실행한 결과는 아니다.

## 환경과 실제 검사

full Xcode·iOS SDK·Simulator 부재는 그대로다. 이를 이유로 코어 구현을 중단하지 않고,
호스트 검사와 실제 URLSession → Rust → PostgreSQL 검사를 진행한다. Swift Testing의
정식 런타임은 기존 CLT 로더 누락으로 실행할 수 없어, 별도 작성·고정한 본문 assertion
러너를 사용한다. 해당 러너와 실제 iOS 검사 결과를 혼동하지 않는다.

이번에는 공유 중인 DB를 건드리지 않도록 데이터 폴더·소켓·포트가 모두 다른 별도 로컬
PostgreSQL 클러스터를 사용한다. 같은 클러스터 안의 쓰기 검사는 직렬 실행한다.
실제 Google·AI·이미지·소셜 제공자의 통합 성공은 합성 fixture 결과로 대체하지 않는다.

## 최종 결과

**핵심 클라이언트 코어와 폭넓은 화면 소스를 구현했다. iOS 앱 전체 완료는 아니다.**
[독립 판정](../experiments/ios-full/verification/review.json)은 아래 한정된 근거를 수용하고
실제 iOS SDK 빌드·화면·외부 제공자 검증은 미완료로 둔다.

[조정자 최종 대조](../experiments/ios-full/acceptance.json)는 18:56:28 KST에 끝났다.
요청의 측정 시작부터 **25분 29초**이며 30분 목표 안이다. 클라이언트 40개 파일을 식별하고,
실제 컴파일·검사한 코어 및 최종 화면 소스 해시의 불일치가 없음을 확인했다.
이후 보고·문서 연결 시간은 이 구간에 포함하지 않는다. iOS 전체 완성 시간으로 해석하지 않는다.

| 기능 | 구현 | 이번 실제 검증의 범위 |
| --- | --- | --- |
| 인증·회원 | ASWebAuthenticationSession·PKCE·state/콜백 검증·코드 교환·쿠키·단일 갱신·닉네임·로그아웃·탈퇴 | RFC challenge/콜백·합성 일회용 코드 교환·쿠키 profile·닉네임·갱신·로그아웃. 실제 Google·기기 복귀·탈퇴 전체 동작 미검증 |
| 종목·환율 | 국내/미국 검색·종류 필터·최근 저장 종가·수동 입력/삭제 보존·환율·관련 자료 | 기존 23개 코어 기준 보존, 실제 저장 종가/환율/관련 자료. 실시간 공급자 호출 아님 |
| 거래·보유 | 게스트/회원 매수·매도·수정·삭제, 보유 조정/삭제, 합친 거래/조정 이력의 날짜·ID 순 재생, 원자적 실패 복구 | Decimal 원장·환율·수량/날짜/scale·초과 매도·조정/삭제 회귀, 실제 회원 거래 생성/수정/매도/삭제와 손익. 모든 회원 보유 조합을 실제 실행한 것은 아님 |
| 평가·성과 | 평가금액·손익·누락 시세·실현손익, 기간 조회·성과 표·네이티브 선/점 차트·변경 이력 | 실제 게스트 계산, 코어 정확도·추출한 실제 PortfolioStore 컴파일/흐름. 차트 렌더·기기 화면 미검증 |
| 뉴스 | 오늘/전체·분야·검색/정렬·페이지·상세·키워드·시장 분석·이미지/출처 | 채워진 실제 fixture 목록/상세/키워드/분석/검색. 모든 화면 분기 미검증 |
| 통합 검색·자료·인물 | 검색 범위·페이지·자료/인물·종목 관련 자료·외부 미디어 링크 | 실제 콘텐츠/검색/인물 API. X/Threads/YouTube DOM 임베드는 원문 링크로 대체 |
| 캘린더 | 회원/게스트 월·범위·일정·발표 값/근거·포트폴리오 영향 표시 | 실제 합성 일정과 게스트 CSRF 요청. 모든 회원/월/영향 조합 미검증 |
| AI 분석 | 회원 저장/확인/재생성/근거 갱신/이력, 게스트 보유 비중 분석, 이전 결과 유지·오류/409 표시 | 요청·응답 처리와 경로/코드 검토. 실제 AI 공급자 성공 응답 및 기기 화면은 미검증 |
| 피드백 | 공개 제출·CSRF·로딩·성공 초기화·오류 보존 | 실제 204와 DB 행 증가, 관리자 삭제 후 DB 수 검증 |
| 관리자 뉴스 | 목록/상세/등록/수정/발행/거절/삭제·multipart JSON+선택 이미지·이미지 검색/권리 출처·관련 종목·생성 요청 | 실제 ADMIN multipart 등록/수정/soft-delete. 이미지 바이너리는 호스트 wire 검사, 실제 S3/이미지 제공자 업로드 미검증 |
| 관리자 기타 | 피드백 상태/삭제·인물 CRUD·게시물/후보 개별/일괄·종목 자료·동기화/백필 요청 | 실제 ADMIN 피드백·인물 CRUD, 사용자 권한 403. 후보·실제 외부 수집/동기화 작업 전체 미검증 |

경로 카탈로그는 74개다. 경로가 정의돼 있거나 화면 소스가 있다는 사실을 74개 기능 전부의
실행 성공으로 세지 않는다. 런타임으로 확인하지 못한 기능을 단순 완료 수에 합치지 않는다.

## 검사 근거

- [고정된 호스트 검사](../experiments/ios-full/verification/host51-final.log): 총 51개 고유
  테스트 본문 실행, 실패 0. canonical Swift Testing 런타임 결과는 아니다.
- [고정 기준 대조](../experiments/ios-full/verification/frozen-runner-review.json): 최초 23개,
  서비스 13개, 원장 9개, 보유 조정 4개, multipart 2개. 원래 UI 소스는 보관본과 대조하고
  명시적 v2 개정은 새 해시와 대조했다. 고정 기준을 몰래 수정하지 않았다.
- [실제 Rust HTTP/DB](../experiments/ios-full/verification/full-live-final-result.json): 34개
  assertion 성공. 생산 URLSessionTransport·ServiceClient를 컴파일한 실행 파일로 별도
  로컬 Rust/합성 PostgreSQL에 요청했다. 회원/ADMIN은 검증 전용 코드로 인증했다.
- [세션 회귀](../experiments/ios-full/verification/concurrency-final.log): 완료된 갱신 뒤
  도착한 옛 401의 중복 갱신 방지, 로그아웃 뒤 옛 응답의 성공/재요청 방지를 확인했다.
- [실제 쿠키 경쟁](../experiments/ios-full/verification/cookie-race-result.json): 실제
  URLSession과 늦은 Set-Cookie 응답 경쟁에서 로그아웃 뒤 인증 쿠키/옛 요청이 복구되지 않음을 확인했다.
- [소스·실행 파일 식별](../experiments/ios-full/verification/final-source-identity.json): 실제
  컴파일한 코어 복사본과 현재 13개 코어 파일의 해시 일치. 최종 UI/프로젝트 연결은 별도 정적 대조.
- 별도 통화 정책 2개, 추출한 실제 PortfolioStore의 Swift 6 타입 검사와
  매수→보유 조정→매도→보유 삭제 흐름을 확인했다. UIKit/SwiftUI 전체 타입 검사는 아니다.

새 [보유 조정 기준](../experiments/ios-full/test-author/holding-adjustment-freeze.json)과
[multipart 기준](../experiments/ios-full/test-author/multipart-freeze.json)은 실제 빈 구현의
51개 실행에서 새 검사만 실패한 상태를 보존한 뒤 구현자 두 명에게 각각 넘겼다.
조정 stub을 넣기 전의 Engine 소스와 두 줄 diff도 보존했다.

## 발견한 결함·기준 보완

동시 요청에서 이전 Access Token의 401이 갱신 완료 뒤 도착하면 두 번째 refresh를 보내는
문제를 독립 제어 transport가 재현했다. 요청 당시 인증 세대를 기록해 갱신을 한 번으로
줄였다. 로그아웃 전에 시작한 요청이 나중에 성공하는 문제도 재현해 세션 세대·갱신 취소·
공유 ephemeral cookie jar 정리를 추가했다. 실패와 수정 후 실행을 별도로 보존한다.

포트폴리오의 명시적 KRW/USD가 종목 코드 접미사보다 우선하도록 원본과 맞췄다. 검증자의
초기 관리자 뉴스 DELETE 기대값은 404였지만 원본은 `DELETED` soft-delete다. 원본 근거를
기록한 뒤 **검증자의 잘못된 추가 검사만** 수정했다. 실패 실행을 성공으로 덮어쓰지 않았다.
[기준 수정 근거](../experiments/ios-full/verification/admin-expectation-correction.md).

## 앱 통합과 자원 정리

포트폴리오/소식/종목/내 정보의 네 탭과 같은 ServiceClient·시장 API·AppSession을 연결했다.
시장 API와 서비스 API는 동일 ephemeral URLSession을 사용한다. 관리자 화면은 ADMIN 계정의
내 정보에서 접근한다. 모든 앱 Swift 파일과 두 UI 테스트 파일이 Xcode 타깃에 연결되고,
Debug/Release에 고정 인증 callback scheme이 등록됐다. plist·project·scheme XML·Swift
구문 검사는 성공했다. scheme의 단일 UI 테스트 타깃 안에 세 테스트 메서드가 있다.

검증자가 만든 PostgreSQL 55561과 Rust HTTP 18096은 정상 종료했다. PG stop 종료 0,
기존 공유 클러스터는 수정/중단하지 않았다. 원본·백엔드·다른 클라이언트의 동시 작업은
수정하지 않았다. 모델은 배정 파일의 값이며 사용량/비용이나 병렬 배속은 측정하지 않았다.

## 남은 항목

1. full Xcode/iOS SDK/Simulator를 준비해 전체 앱을 실제 타입 검사·빌드하고 세 UI 검사를 실행한다.
   VoiceOver·Dynamic Type·키보드·회전·밝음/어두움·백그라운드 복귀도 확인한다.
2. 실제 Google·AI·이미지/S3·소셜/외부 시세·동기화 제공자와 관리자 전체 동작을 별도로 검증한다.
   합성 코드 교환·DB fixture·서버 응답 검사를 그 성공으로 대체하지 않는다.
3. 웹 전용 소개/약관·개인정보/분석 도구 문구의 iOS 정책을 확정하고 이식한다. 웹 마케팅
   투어·디자인 preview·세밀한 시각 재현·외부 미디어 내장 임베드는 이번 핵심 우선 구현에서 남겼다.
4. iOS SDK가 없는 현재 환경에서는 전체 네이티브 앱 완성을 주장할 수 없다. 현재 결과는
   **핵심 코어 실제 검증 + 폭넓은 네이티브 화면 소스 구현**이며 최종 앱 인수는 보류다.

실행 안내는 [iOS README](../clients/ios/README.md), 독립 최종 설명은
[검토 기록](../experiments/ios-full/verification/review.md)을 따른다.
