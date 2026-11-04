# WebView 직접 테스트

프로젝트 루트 `/Users/seoyeong/develop/AI/daynomy_agent`에서 실행한다. 전체 앱은 `fullweb/`이며 이전 `web/` 검색 파일럿과 구별한다.

## 로컬 환경

터미널 하나에서 전용 임시 DB와 실제 Rust API를 실행한다. 원본 환경파일/운영 데이터는 사용하지 않는다. 현재 머신의 PostgreSQL18, Rust와 로컬 의존성 캐시를 사용한다. private DB 포트55449가 사용 중이면 기존 프로세스를 건드리지 않고 실패한다.

```sh
python3 experiments/webview/full/runtime/start_fixture.py --private-db
```

`Rust/DB Android fixture ready at http://127.0.0.1:18091`가 나오면 준비 완료다. 실행 기록은 새 `.local/webview-manual-*` 폴더에 남는다. 공통 도구가 Android 이름을 쓰지만 WebView에서도 같은 Rust API를 사용한다. `Ctrl+C`로 해당 서버/임시 DB를 정리한다. 다른 공유 DB 검증 잠금은 사용하지 않는다.

터미널 둘에서 웹을 실행한다. 의존성이 없으면 먼저 `npm --prefix clients/webview/fullweb ci --ignore-scripts`를 실행한다.

```sh
npm --prefix clients/webview/fullweb run build
node clients/webview/scripts/serve-full.mjs --port 18082 --api-origin http://127.0.0.1:18091
```

브라우저에서 [테스트 화면](http://127.0.0.1:18082/)을 연다. 이전 화면이 있으면 새로고침한다. 웹 서버는 `Ctrl+C`로 종료한다.

## 수동 확인

1. 포트폴리오의 `거래 기록` 버튼에서 삼성전자 또는005930을 검색한다. 최근 종가71000.125와 기준일2026-10-23은 테스트 데이터다. 실제 현재 시세가 아니다.
2. 종목 선택 후 단가를 직접 바꾸고 수량을 입력해 매수 저장한다.
3. 같은 탭을 새로고침해 거래 유지 확인 → 수량 수정 → 거래 삭제를 확인한다. 비회원 거래는 원래 sessionStorage 저장이므로 탭을 닫은 뒤 복구하는 기능이 아니다.
4. 소식에서 합성 테스트 뉴스와 상세 화면을 확인한다.
5. 오른쪽 아래 피드백을 제출하고 완료 안내를 확인한다. Rust API가 전용 임시 DB에 저장하며 운영 서비스에 전송되지 않는다.

제공자는 ephemeral 로컬 OIDC fixture다. Google 버튼으로 실제 계정에 로그인하는 환경은 아니다. 자동 검증은 로컬 제공자에 합성 authorization을 등록하고 실제 Rust callback/서명 확인/회원 세션을 검사했다. Android는 서버발급 앱 URI를 같은 Chrome 링크로 전달해 native 교환과 회원 상태를 검증했으며, 자동302앱전환 및 실제Google와 구별한다. 외부 AI/S3/소셜 제공자 기능도 이 환경에서 성공한다고 보장하지 않는다. 계약은 `spec/webview/native-auth.md`, 후속 결과는 `experiments/webview/full/native-auth/verification/` 및 실행 기록에 있다.

## Android WebView

웹·API 실행 상태에서 에뮬레이터 또는 USB 디버깅 기기를 연결한다. `adb devices`로 확인한 ID로 아래 `<기기ID>`를 바꾼다. 다른 작업의 기기를 임의로 종료하거나 초기화하지 않는다.

```sh
adb -s <기기ID> reverse tcp:18082 tcp:18082
adb -s <기기ID> install -r clients/webview/android-full/app/build/outputs/apk/debug/app-debug.apk
adb -s <기기ID> shell am start -n com.daynomy.webview.full/com.daynomy.webview.MainActivity
```

APK는 `-PdebugWebOrigin=http://127.0.0.1:18082` 빌드여야 한다. 빌드 명령은 [FULL-HOSTS.md](FULL-HOSTS.md)에 있다. 위 거래 흐름과 홈 화면으로 나갔다 돌아온 뒤 수동 입력 유지를 확인한다. iOS는 Xcode/iOS SDK 머신에서 별도로 빌드·실행한다.

## 자동 검사

```sh
npm --prefix clients/webview/fullweb test
node --test clients/webview/full-tests/server-contract.test.mjs clients/webview/full-tests/query-regression.test.mjs
node --test clients/webview/full-tests/full-host-policy.test.mjs
node --test clients/webview/full-tests/native-auth/native-auth.test.mjs
```

앞의 두 명령은 웹 단위/UI 및 독립 서버 계약 검사다. 마지막 두 정책 검사는 준비된 Kotlin/JDK/Swift 도구가 필요하며 실제 기기 실행을 대체하지 않는다. 실패·해시·실제 DB/기기 결과 구분은 [실행 기록](../../runs/016-webview-full.md)을 따른다.
