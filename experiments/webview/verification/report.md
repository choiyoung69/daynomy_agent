# WebView 독립 검증 최종 기록

2026-10-28. 판정: **핵심 웹·Android 파일럿 검증 통과, iOS 실제 실행은 환경 차단**. 범위는 종목 검색 → 최근 저장 종가 → 수동 단가다. 실제 로컬 Rust/DB를 연결한 Chrome156과 Android13/WebView109의 결과이며, 전체 앱·인증·거래 저장·운영 배포 승인이 아니다.

## 역할과 실패 보존

테스트 작성자, 구현자, 최초 독립 검증자가 분리되어 있었다. 최초 검증자는 대부분의 실행 검사를 마친 뒤 `Selected model is at capacity`로 중단됐다. 이 기록의 작성자는 별도 복구 검증자이며 구현·고정 테스트를 수정하지 않았다. 기존 round01 실패, round02 로그 및 JSON을 덮어쓰지 않았다.

round01 실제 브라우저의 `Illegal invocation`은 기본 fetch 수신자 문제였고 구현자가 `globalThis.fetch.bind(globalThis)`로 수정했다. 독립 round02 검사와 실제 화면 흐름이 수정 후 통과했다. 최종 리뷰의 모바일 안내 문구 지적도 수정되었다. 초기에 해시가 다른 이유는 이 의도된 revision02 수정이며, 현재 비교 기준은 `implementation/web/revision-02/source-hashes.json`이다.

보완 검증 도중 기존 공유 에뮬레이터와 Rust fixture가 종료되어 이전 보완 로그에 연결 거절이 남았다. 조정자가 새 disposable DB/Rust18091 fixture를 실행했고, 복구 검증자는 같은 Daynomy_Pilot AVD5564를 wipe 없이 재시작했다. 복구 데스크톱 첫 시도는 진단의 `pages[0]`가 Chrome 확장 페이지를 선택해 실패했다. 그 스크립트와 로그를 `recovery/retry-attempt1.mjs`, `desktop-retry-attempt1.log`에 보존하고 복구 스크립트만 실제 `type === 'page'` 대상으로 고쳤다. 제품 실패로 기록하지 않는다.

## 실제 확인 결과

이전 독립 검증자의 원시 로그와 명령/종료 코드를 읽어 다음 실행 근거를 승계했다. 복구 검증자가 이 모든 검사를 새로 실행했다고 주장하지 않는다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| `npm test` (clients/webview/web) | exit 0, 29/29 | round02-web-unit.log |
| `node --test clients/webview/tests/host-policy.test.mjs` | exit 0, Kotlin/Swift 2/2 | round02-host-policy.log |
| `node --test clients/webview/tests/http-browser.test.mjs` | exit 0, HTTP/실제 Chromium DOM 2/2 | round02-http-browser.log |
| Gradle `-p clients/webview/android --offline --no-daemon :app:assembleDebug` | exit 0 | round02-android-build.json/log |
| 실제 웹18082 → Rust18091 | KR 71000.125, 2026-10-23 / US 193.4 USD | desktop-runtime.json, android-runtime.json |
| 수동 문자열·삭제 | 문자열 보존, 삭제 후 빈 값 유지 | 동일 JSON |
| Android Home/복귀·회전·키보드 | 정확한 수동 값 유지, native keyboard shown | android-runtime.json, 유효 기기 캡처 |
| Android 탐색·쿠키 | 6개 거절 대상 유지, JS marker 미실행, 내부 history/back, synthetic cookie 유지 후 제거 | round02-android-host.json |

복구 검증자가 새로 실행한 핵심 보완 검사는 `node experiments/webview/verification/recovery/retry.mjs desktop` 및 `android`이며 각각 **exit 0**다. 두 환경 모두 가격 오류 class, 표시된 재시도 버튼, 기준일 `조회 전`을 동시에 기다렸다. 이어 실제 버튼 click을 호출하고 CDP Network 이벤트로 가격 요청 수 **1 → 2**, 서로 다른 requestId의 응답 **404 → 404**, 재시도 후 확정 오류와 재시도 버튼·`조회 전`을 기록했다. 결과는 `recovery/desktop-retry.json`, `android-retry.json`이다. 기존 진단이 loading 메시지의 ‘직접 입력’을 잘못 완료 조건으로 삼았던 관측은 그대로 남기며 이 보완 근거로만 재시도 실행을 승인한다.

복구 preflight는 exit 0, 원본 29/29 일치였다. preflight 자체를 기능 실행 근거로 사용하지 않는다. 실제 명령과 종료 코드는 `result.json`에 함께 기록했다.

## 무결성과 실제 제공 파일

복구 검증자가 SHA256을 다시 계산한 결과 고정 테스트 **13/13**, revision02 웹 manifest **9/9**, 호스트 **22/22**, 지식베이스 문서 **21/21** 및 context, APK가 모두 일치했다. 상세 예상값·실제값은 `recovery/integrity.json`에 있다.

- 고정 manifest: `dd1a0fd772bbb142f58b2fd6dafb9df8711f6460fc85af2f216a3553c68a3fb9`
- APK: `16deb760f1b1dce4613885f09820434b631083d9283eaab72ccb115c474420b2`
- 실제 HTTP 200으로 제공된 dist/app.js: `15effc6f529679d1bc452c27c0cf8a37a83786db73a72ea5474f0bb887c4cb97`
- 실제 HTTP 200으로 제공된 dist/market.js: `31fe1e0494e071f7e77522bbf4f82981e0cb14274bc68e832097051434e30a5d`

두 ESM의 HTTP 본문 해시는 디스크 파일과 일치했다(`recovery/served-dist.json`). 최종 증거 파일 해시는 `result.json`에 기록했다. 실행 중인 emulator.log는 계속 증가하므로 고정 증거 해시에서 제외했다.

## 유효 범위와 남은 검증

유효 화면 근거는 `screenshots/round02-desktop-quote-full.png`, `round02-desktop-mobile-full.png`, `round02-android-quote.png`, `round02-android-keyboard-device.png`다. `round02-android-quote-full.png`는 상단이 반복되고 가격 패널이 빠진 캡처이므로 **제외**한다. landscape 캡처는 하단 viewport만 보여주며 전체 가독성 승인이 아니다. 회전 후 값 보존은 실행 JSON의 근거다.

iOS는 전체 Xcode가 없어 앱 빌드·WKWebView 실행·기기 검증이 차단되었다. Swift syntax parse와 순수 정책, plist/project lint 통과를 실제 WKWebView 검증으로 확대하지 않는다. Android 최소 API26·실기기·renderer 종료 복구·전체 process death 복원, TalkBack/VoiceOver, release HTTPS 운영/TLS 검증도 미수행이다. 외부 HTTPS 탭은 Chrome FirstRun 전환까지만 확인했으며 목적 페이지 로딩은 미확인이다. synthetic cookie 유지가 로그인 검증을 뜻하지 않는다.

복구 후 Android는 WebView 앱 전경, KR 단가 71000.125·기준일 2026-10-23, cookie empty boolean true, keyboard hidden 상태다. 회전 설정 user_rotation=0/accelerometer_rotation=1은 복구 전후 동일하다. 복구 중 설정을 변경하지 않았다. 원시 쿠키·토큰은 기록하지 않았다. 에뮬레이터 세션59346, 웹 preview29094, root fixture13254는 조정자에게 정리 책임을 인계한다.
