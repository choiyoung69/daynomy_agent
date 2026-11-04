# React Native 독립 검증 — 2026-10-28

조정자와 별도 문맥의 검증 에이전트가 구현·고정 테스트를 수정하지 않고 검토했다. 새 검증 파일만 작성했다. 전체 작업 제한은 10:15:33–10:35:33 UTC(19:15:33–19:35:33 KST)다. 아래 결과는 이번 실제 실행이며 기존 iOS·Android 결과를 재사용한 성공 수치가 아니다.

## 실제 검사

- 독립 작성자가 빈 구현으로 실행한 core27의 RED 21실패·6통과 로그 및 고정 해시를 확인했다. 거절만 요구하는 6개는 throw stub도 통과한다는 점이 manifest에 표시돼 있다. 구현 후 같은 테스트27개 모두 통과했고, SHA-256 `346c27cc3aa445f355293fbcffd87723c21d7828452af06a2748a4790be37d92` 일치를 독립 재확인했다.
- 추가 독립 regression 최초9개 중 첫 실행7통과·2실패. 동시 게스트 거래 추가에서 한 건이 소실되는 문제와 저장 대기 중 clear 이후 기록이 되살아나는 문제를 실제 재현했다. 구현자가 queue 내부 상태 계산·clear 직렬화를 고친 뒤9개 모두 통과했다. 응답 본문까지 timeout이 유지되는 검사1개를 추가해 최종10개 모두 통과했다. 첫 실패 로그는 보존했다. 손상 저장 원본을 자동 삭제하지 않고 보존하는 조정자의 별도 정책은 `storage-policy-correction.md`에 근거와 기대값 수정 이유를 기록했다. 앱 자체 AsyncStorage 화면 경로와 GuestLedgerStore는 별개이므로 이 검사10개를 화면 영속 저장 성공으로 세지 않는다.
- 실제 Rust 서버와 전용 PostgreSQL의 합성 데이터로 HTTP15개 모두 통과했다. 국내·미국 종목, 최근 종가·기준일, 없는 가격404, 뉴스 null metadata·미발행404, 공개 CSRF 피드백204·입력400, 평가계산, 단일사용 PKCE 교환, 회원조회·거래등록후조회·닉네임·관리자403·로그아웃401을 실행했다. Node 주입 쿠키 어댑터이며 RN OS 쿠키 저장소 검증은 아니다.
- 실제 DB 읽기 확인4개: 성공 피드백1행, 회원 보유2주, BUY 이력1행, 로그아웃 후 refresh0행. 토큰·본문·접속문자열을 결과에 기록하지 않았다.

## 원본 대조로 발견한 통합 오류

작성 중인 App에서 회원 거래 DTO의 `transactionType/tradedOn` 대신 `type/tradeDate`, 숫자문자열의 불필요한 Number 변환, 미지원 GET transactions 대신 histories array, 뉴스·검색의 page0 대신1, 미지원 INDUSTRY/TECH 카테고리를 지적했다. 조정자가 수정했다. 회원 이력의 stock metadata는 현재 보유목록과 결합하며 매도완료 종목처럼 metadata가 없으면 편집을 숨기고 삭제만 제공한다. 원본 histories가 배열이라는 점을 코드로 확인했고, 검증자가 처음 제안한 portfolio.transactions 및 {histories} 추측은 잘못되어 즉시 철회했다.

## 플랫폼과 실행 경계

Node22.23.1/npm10.9.8. Xcode27.1 조회 성공, 샌드박스 밖 Simulator runtime 목록은 비어 있다. 라이선스 동의 동작은 수행하지 않았다. Android SDK34·35 및 emulator5564·5576은 존재하지만 RN용 Expo Go는 확인한 emulator5576에 없었다. 검증 전용 복사본에서 Expo Android prebuild는 성공했다. Android 실제 assembleDebug 결과는 `android-native-build.json`과 로그를 따른다. 빌드용 복사본과 조정자가 계속 수정한 최종 App은 다른 시점일 수 있다. Metro 번들 생성은 네이티브 앱 설치·기기 UI 실행·OS OAuth 쿠키 검증을 대체하지 않는다.

원본 Spring/운영 .env·실사용자 데이터는 사용하지 않았다. 기존 DB에 접속하거나 시작·중단하지 않았고 전용 PG55459/API18129만 만들었다. 최초 sandbox shmget 실패, 긴 Unix socket 실패, localhost fetch 차단은 별도 로그에 보존했으며 성공으로 바꾸지 않았다.

## 남은 범위

실제 Google 브라우저 인증→앱 callback→양 OS HttpOnly 쿠키→회원 UI 전체 흐름, 네이티브 iOS 빌드·Simulator/기기 실행, 최종 Android 앱 설치·화면·접근성·키보드·복귀 동작은 별도 검증이다. 정밀 차트·원본 전체 화면 재현과 관리자 편집·발행 등 모든 쓰기 화면의 동등성은 이번 core/HTTP 검사로 증명하지 않는다. 관리자 API route 정의만 있는 기능은 화면 구현 완료로 세지 않는다.

## 최종 추가 확인

최종 소스로 core27·독립10·전체 TypeScript typecheck를 다시 실행해 모두 종료0이다. `final-source-identity.json`에 검사한 최종 소스·테스트·잠금파일 해시를 고정했다. 조정자의 별도 최종 Metro/화면 검사 로그는 coordination 폴더와 테스트 작성자 결과를 따른다.

Admin UI의 실제 saveNews 함수를 TypeScript로 추출하고 Node 쿠키 어댑터를 주입해 실제 Rust에 전송했다. multipart 초안 생성201·수정200·연결종목보존·삭제 및 피드백 상태 변경 등5개 통과, 발행1개는500으로 실패했다. publish는 내부 analyze에 AI 제공자 설정을 요구하며 이번 fixture에는 제공자·운영키를 넣지 않았다. 실패는 보존하고 발행 성공을 주장하지 않는다. 이것은 UI 네트워크함수 실행이며 RN 화면/OS 실행이 아니다. 반복 Admin 로그인으로 남은 이전 세션을0개라고 기대한 DB 검사 오류는 `db-effects-scope-correction.md`에 정정하고 로그아웃 직전2행→직후1행으로 현재 세션 정확히1개 제거를 확인했다.

Android Expo prebuild는 성공했지만 assembleDebug는180초 제한에서 종료했다. Gradle 다운로드·플러그인 빌드까지만 진행했고 APK는 없다. 자체 Gradle 캐시 데몬은 --stop 조회에서 실행 중 없음. debug/debugOptimized manifest는 cleartextTraffic=true이고 release/main에는 없으며 HTTPS 운영 설정 원칙과 구별한다.

원본 프론트는 뉴스 카테고리10개를 정의하지만 현재 Rust category 필터는 주식·ETF·부동산3개만 받는다. 이 차이를 조정자에게 알렸고 최종 앱은 전체+지원3개만 표시한다. decoder는 원본 응답10개를 수용한다. 기존 backend는 변경하지 않았다.

전용 Rust/DB 최종 종료: 2026-10-28T10:33:57.115480+00:00 UTC. fixture-db-drop 및 private-db-stop 모두 종료0, fixture status=stopped. 앞선03 fixture도 정상종료했다. `shutdown.json`에 별도 증거를 남겼다. 기존 원본·공유 DB·다른 서버는 중단하지 않았다.
