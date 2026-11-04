# DAYNOMY Android 네이티브 파일럿

첫 범위는 **종목 검색 → 선택 → 최근 저장 종가 표시 → 수동 단가 입력**이다.
후속 묶음은 **공개 뉴스 목록·분류·페이지·상세와 날짜별 USD/KRW 환율 조회**다.
상단 종목/뉴스/환율 탭으로 이동한다. 후속 실제 검사 결과는 [실행 기록](../../runs/015-android-native-parallel.md)에서 확인한다.
Kotlin/Compose 네이티브 앱이며 Rust 백엔드는 기존 app/을 사용한다.
30분 핵심 확장으로 외부 브라우저 PKCE 로그인 연결·내 정보·닉네임·로그아웃·탈퇴와
보유자산·매수/매도·거래 수정/삭제·이력·조정·평가·수익률의 화면/클라이언트를 추가했다.
현재 전체 구현/검증 범위는 [Rust 대비 지도](../../spec/android-native/coverage.md),
실제 검사·제한은 [30분 기록](../../runs/017-android-core-30min.md)을 따른다.
실제 Google 계정 인증·전체 앱·운영 배포 완료를 의미하지 않는다.
뉴스 키워드 조회는 [별도 계약](../../spec/android-native/news-keywords.md)을 따르며 상세에서 확인한다.
뉴스 이미지 다운로드·시장 분석은 미구현이다. 오늘 뉴스는 기존 모드 전환을 사용한다.

## 구성

- market-core/: 순수 Kotlin 모델·JSON 경계·취소 가능한 OkHttp·검색/가격 상태 소유자.
- app/: Compose 화면·ViewModel·SavedStateHandle 초안. 회전 유지와 초안 복원 경로를 분리한다.
- ../../spec/android-native/: 원본에서 추출한 검색·가격 계약, 검증 기준과 Android의 명시적 차이.
- ../../agents/android-native.json: 이번 대화의 역할·동시 실행 상한·작업별 필수 지식 목록.

minSdk26, compile/target35, JDK21, Gradle8.11.1/AGP8.9.2/Kotlin+Compose plugin2.1.20,
Compose BOM2025.04.01, OkHttp4.12.0/JSON1.8.1/coroutines1.10.2를 고정했다.
설치된 SDK35를 재사용하는 파일럿 조합이다. 최신 버전 사용을 주장하지 않는다.
Gradle wrapper 배포물 SHA256과 모듈별 dependency lock을 보존한다.

## 빌드와 실행

저장소 루트에서 JDK21·Android SDK35/BuildTools35.0.0을 준비한다.
`local.properties`의 sdk.dir에 본인 SDK 경로를 넣는다. 이 파일과 빌드 캐시는 Git 제외다.
macOS의 이번 환경에서는 /Users/seoyeong/Library/Android/sdk를 사용했다.

```sh
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export GRADLE_USER_HOME="$PWD/.local/android-gradle"
clients/android/gradlew -p clients/android :market-core:test :app:assembleDebug :app:lintDebug
```

디버그 앱의 기본 API는 현재 로컬 미리보기 서버인 http://10.0.2.2:18109/이다.
기존 Rust 개발 서버를 18081로 실행한다면 아래 Intent의 `base_url`로 해당 주소를 지정한다.
일반 Rust 실행법은 [백엔드 안내](../../app/README.md)를 따른다.
실기기는 자신의 개발 서버 주소·TLS 또는 adb reverse에 맞춰 연결해야 하며 이번 실험은 API33 ARM64 에뮬레이터에서 실행했다.

```sh
adb install -r clients/android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -S -n org.daynomy.android/.MainActivity --es base_url http://10.0.2.2:18109/
```

`base_url` Intent override는 debug에서만 사용한다. debug cleartext는 localhost/127.0.0.1/10.0.2.2로 제한했다.
release의 실제 API 주소는 아직 구성하지 않았고 배포용 앱은 아니다. release 분기는 예시용 불가 도메인을 사용하며
이 파일럿 APK를 운영 배포하지 않는다.

회원 로그인은 계정 탭에서 외부 브라우저를 열고 `org.daynomy.app://auth/callback`을 받는다.
기존 서버의 모바일 코드 교환 경로와 `004_mobile_auth_codes.sql`이 필요하며 [서버 안내](../../app/README.md)를 따른다.
세션 쿠키·PKCE 대기 상태는 메모리에만 둔다. 앱 프로세스 종료 후 영구 로그인은 구현하지 않았다.
거래 응답을 잃으면 결과 미확정으로 표시하고 자동 재전송하지 않는다. 내역을 다시 조회해 확인한다.

## 실제 검증

1. 독립 테스트를 빈 구현 복사본에서 실행해 최초49개가 모두 실패함을 확인하고 해시를 고정했다.
2. API 구현2개를 병렬 배정하고, 연결 화면·상태·실제 HTTP 취소를 구현했다.
3. 독립 리뷰의 검색어 보존·숫자 토큰 문법 지적에 회귀3개를 추가했다. 수정 전2개 실패/가격 대조1개 성공을 보존했다.
4. 최종 JVM52개, 실제 Rust/DB 연결7개, API33 기기 화면5개를 별도로 실행했다.

```sh
# 터미널1: 기존 Rust + 새 합성 데이터 DB. .env/운영 데이터/원본 서버를 사용하지 않음.
python3 scripts/android_backend_fixture.py --output .local/android-backend-new
# 뉴스·환율을 함께 검사할 때는 별도의 새 출력 경로에 --discovery를 추가한다.
# python3 scripts/android_backend_fixture.py --output .local/android-discovery-new --discovery

# 터미널2: 연결 인수. backendTest는 주소가 없으면 실패하며 skip하지 않음.
export ANDROID_PILOT_BASE_URL=http://127.0.0.1:18091
clients/android/gradlew -p clients/android :market-core:backendTest
# 연결된 전용 에뮬레이터/기기가 필요. 이 5개 화면 테스트는 기기 내부 MockWebServer 사용.
clients/android/gradlew -p clients/android :app:connectedDebugAndroidTest
# 기기의 실제 앱 -> Rust/DB까지 확인. 매번 새 출력 경로 사용.
python3 scripts/android_device_probe.py --serial emulator-5564 --output /tmp/android-device-new.json
```

connectedDebugAndroidTest는 완료 후 대상 APK를 제거할 수 있다. 직접 연결 probe는 같은 검증 APK를 재설치한다.
fixture는 Ctrl-C 또는 출력 폴더에 stop 파일 생성으로 종료하며 자기 서버·일회용 DB를 정리한다.
기존에 실행 중이던 DB 서비스는 중단하지 않는다. DB 검사는 저장소의 공유 잠금을 사용한다.

원본 기대값의 독립 인증, 실제 프로세스 kill 복원·TalkBack·큰 글자·IME 전체 수동 인수·다른 OS/API 기기는 별도다.
코드 검토자는 테스트도 작성했으므로 자신의 테스트 기대값을 별도 독립 검토한 것으로 세지 않는다.

## 지식베이스를 기본 입력으로 쓰는 흐름

검색어·선택 해제·가격 초안 상태만 고치는 작업은 기존 도구의 작은 프로필을 사용한다.

```sh
python3 scripts/android_knowledge.py ensure query-reset --base .local/my-task/knowledge
```

처음에는 3문서 패킷을 만들고, 같은 경로가 있으면 준비·출처·해시를 확인해 재사용한다.
변경된 패킷은 덮어쓰지 않고 거절하므로 새 작업 경로를 사용한다. 이 명령 뒤 prepare/verify를
동일 시작 단계에서 다시 실행할 필요는 없다. 구현 결과 수용 시의 verify는 유지한다.
manifest의 documents에 적힌 기능·상태/탐색·비동기/취소 문서를 각각 읽는다.
checks에는 관련 MarketController 계약·회귀 검사 명령이 들어 있다. 아래 두 클래스만 먼저 확인한다.

```sh
clients/android/gradlew -p clients/android :market-core:test \
  --tests org.daynomy.market.MarketControllerContractTest \
  --tests org.daynomy.market.MarketControllerRegressionTest
```

기존 실행 안내의 JAVA_HOME/GRADLE_USER_HOME을 사용한다. 수정이 JSON·금액·인증·HTTP·화면 연결까지
확대되면 해당 프로필과 검사를 추가한다. 위 명령은 전체 앱 완료 판정이 아니다.
문서/작업 도구만 바꾼 경우 위 앱 검사를 자동 실행하지 않고 해당 도구 자체 테스트만 확인한다.
기존 android_pilot의 implement 시작도 ensure를 사용해 새 패킷의 준비 검사를 중복 실행하지 않는다.

일반 작업은 로컬 지식 → 필요한 원본/보관본 → 해소되지 않는 항목만 외부 조회 순서다.
검색은3문서·가격4문서·통합5문서만 묶어 제공한다. 평가 기대 답변이나 전체 원문은 전달하지 않는다.

```sh
python3 scripts/android_knowledge.py prepare search --base .local/new-android-run/knowledge-v1
python3 scripts/android_knowledge.py verify .local/new-android-run/knowledge-v1/search/manifest.json --usage .local/new-android-run/knowledge-v1/search/usage.json
```

android_pilot.py의 implement 시작은 준비 검사/필수 지식 입력 생성을 수행하며, 구현 결과 수용과 final에서는
요구 task·문서 집합·출처·해시·적용 규칙 맵을 검사한다. 누락/변조/다른 작업 패킷을 거절한다.
이는 **자료 제공과 결과 수용 조건의 강제**다. 모델이 읽고 이해했는지는 증명하지 못하며 테스트·원본 대조·리뷰로 확인한다.
이번 검색/가격 초안은 이 장치를 도입하기 전에 작성돼 사후 KB 대조를 거쳤다. 처음부터 강제 적용한 실행으로 바꾸어 보고하지 않는다.
통합 구현부터는 선행 패킷을 사용했다. 프로그램은 앱 서브에이전트를 직접 실행하는 무인 실행기가 아니며 root가 배정한다.

[실행 근거](../../experiments/android-native/evidence/verification-05.json),
[최종 리뷰](../../experiments/android-native/evidence/review-final.json),
[시간·실패·한계 기록](../../runs/014-android-native.md)을 함께 확인한다.

후속 뉴스·환율은 테스트 작성·구현·검증을 서로 다른3개 역할로 분리했다.
최신 [독립 검증 승인](../../experiments/android-native/next/validation-final.json)과
[병렬 작업 기록](../../runs/015-android-native-parallel.md)은 기존 회귀 포함106개 검사,
실제 Rust에 연결한 뉴스·환율 화면, 실패·수정·범위 제한을 구분한다.

## 피드백 보내기(F11)

계정 → 의견 보내기에서 로그인 없이 입력·전송한다. 기존 CSRF 통신을 재사용하며
중복 클릭·자동 POST 재전송을 막는다. 응답 유실은 결과 불명으로 표시하고 새 의견 작성으로만 초기화한다.
계약은 [피드백 명세](../../spec/android-native/feedback.md), 검사와 시간·토큰은
[실행 기록](../../runs/024-android-feedback.md)을 따른다.
작업 시작 시 `python3 scripts/android_knowledge.py ensure feedback`으로 필요한 4문서만 전달한다.
관련 JVM 검사는 FeedbackContractTest·Android30SessionContractTest, 화면 검사는 FeedbackScreenTest다.
