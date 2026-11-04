# DAYNOMY React Native

Expo + TypeScript의 Android/iOS 공통 네이티브 UI다. 기존 웹 DOM이나 WebView로 대체하지 않고
View/Text/TextInput/Pressable로 구성했다. 20분 구현 범위와 남은 기능은
[실행 기록](../../runs/019-react-native-twenty-minute.md), [범위표](../../spec/react-native/coverage.md)를 본다.

## 공통 UI/UX 후속 적용

2026-11-04: Android 공통 화면 기준으로 포트폴리오·이슈·내 계정 3탭과 흰 표면·검정 버튼·청색 강조를 적용했다. 보유 조정/삭제와 오늘 뉴스 캐러셀·뉴스 검색/분류/정렬/페이지를 추가했다. 기존 추가 기능은 계정의 보조 진입점에 보존했다. 현재 검사와 미검증 범위는 [후속 계약](../../spec/react-native/common-uiux.md)을 본다. 아래 2026-10-28 기록의 범위와 구분한다.

## 실행

Node 22.23.1 환경에서 설치·타입 검사·계약 테스트·Metro 번들을 확인한다.
잠금 파일의 실제 버전은 Expo58.0.20, React19.3.0, React Native0.88.0이다.
호환 버전은 Expo의 `expo install` 결과와 `package-lock.json`에 고정한다.

```sh
cd clients/react-native
npm ci
npm run typecheck
npm test
npm run export
# 별도 터미널에서 app/README.md대로 실험용 Rust 서버/DB 실행 후:
EXPO_PUBLIC_API_URL=http://127.0.0.1:18081 npm start
```

Android 에뮬레이터는 호스트 API 주소를 `http://10.0.2.2:18081`로 설정한다.
서버 주소는 앱 더보기에서도 바꿀 수 있다. 실기기는 HTTPS 서버 주소를 사용한다.
HTTP는 loopback/Android emulator 개발 주소만 허용한다. 기본 서버는 자동 실행되지 않는다.

네이티브 SDK 환경에서 아래 명령은 native project 생성과 플랫폼 빌드를 실행한다.
`ios/`, `android/`는 생성 산출물이며 Git에서 제외한다.

```sh
npm run android
npm run ios
```

커스텀 OAuth 콜백을 쓰므로 로그인은 Expo Go 대신 개발 빌드에서 확인한다.
웹 프리뷰는 공통 UI 확인용이며 네이티브 로그인 버튼은 활성화하지 않는다.
공식 [Expo SDK 안내](https://docs.expo.dev/versions/v58.0.0/)를 버전별로 확인한다.

## 제공 흐름

- 내 자산: 게스트 매수/매도·거래 수정/삭제·평균 원가·보유 종목·서버 평가와 손익.
- 종목: 국내/미국·주식/ETF 검색, 종가 자동 입력과 수동 단가 보존, 거래일 환율.
- 뉴스: 카테고리·페이지·상세·키워드·시장 분석, 통합 탐색·종목 관련 자료·인물.
- 캘린더: 월 이동·전체/내 종목·게스트/회원 일정과 출처.
- 계정: 외부 브라우저 Google PKCE 연결·프로필·닉네임·로그아웃·탈퇴·피드백.
- 회원: 보유/평가·거래 등록·이력·기존 보유 종목의 거래 수정·거래 삭제·자산 추이·분석 조회.
- 관리자 기본 뉴스/피드백 처리는 별도 화면, 인물/후보는 읽기 화면으로 제공한다.

거래 금액 입력은 문자열로 유지하고 HTTP 직렬화에서 숫자 토큰으로 전송한다.
게스트 원장은 BigInt 기반 십진 연산으로 계산한다. 게스트 거래만 AsyncStorage에 저장하며
회원 응답·인증 토큰·PKCE 검증자는 영구 저장하지 않는다. 저장 데이터가 손상되면
기존 원문을 보존하고 저장을 막아 오류를 알린다. 게스트와 회원 원장을 자동 병합하지 않는다.

쓰기 요청의401은 자동 재전송하지 않는다. 쓰기 결과가 불명확하면 내역을 먼저 확인한다.
쿠키는 React Native 네트워크 계층에 위임한다. iOS/Android의 쿠키 공유·앱 재시작 수명,
실제 Google 로그인, 네이티브 키보드·뒤로가기·접근성 검사는 별도 기기 인수 항목이다.
Metro 번들·웹 프리뷰 성공은 네이티브 설치/실행 성공이 아니다.

## 구조와 검증

`src/core.ts`: 원본 계약·CSRF/갱신·디코더·정확한 거래 원장·비동기 선택 상태.
`src/api.ts`: 기능별 경로·호출. `src/auth.ts`: 난수 PKCE와 고정 콜백 검증.
`App.tsx`: 화면 상태와 실제 AsyncStorage 저장 경로.
`src/storage.ts`: 별도 재사용 저장소 클래스(독립 race 검증 대상); App은 직접 저장 경로를 사용한다.
`tests/core.test.ts`: 별도 작성자가 빈 구현에서 실패를 확인한 뒤 고정한27개 계약.
`experiments/react-native/verification/`: 독립 회귀·실제 Rust/DB·네이티브 빌드 시도 증거.
`experiments/react-native/ui-verification/`: 별도 UI 검증자의 브라우저 실행과 스크린샷.

원본·Rust 백엔드·다른 클라이언트의 기존 변경은 보존했다. 리그·이메일 알림·배포는 제외한다.

## 현재 수정본을 Android에서 보기

현재 작업본은 저장소 루트의 `.local/rn-android-parity/clients/react-native`에 있다. TypeScript는 이 폴더에서 편집하고, Android Studio는 생성한 `android/` 폴더를 Open한다. 기존 `clients/android` Kotlin 프로젝트와 별개다. iOS는 생성된 네이티브 프로젝트를 Xcode에서 연다.

```sh
# 터미널1: React Native 폴더에서 로컬 전용 개발 서버
NODE_OPTIONS=--dns-result-order=ipv4first EXPO_PUBLIC_API_URL=http://10.0.2.2:18109 npx expo start --localhost --port 18089
# 터미널2: 같은 폴더에서 실행. Device Manager에서 에뮬레이터를 먼저 켠다.
npx expo run:android --device emulator-5554 --port 18089 --no-bundler
```

첫 네이티브 빌드는 SDK/NDK 다운로드와 컴파일이 필요하다. 이 호스트에서 JDK21과 Android SDK를 사용해 APK 빌드·설치·실행을 확인했다. 이번 실제 화면과 한계는 `spec/react-native/common-uiux.md`의 후속 확인을 따른다.

Android Studio의 내장 기기에서는 설치와 별도로 Metro 연결이 필요하다. 현재 React Native UI의 serial은 emulator-5556이며, 디버그 앱 서버 주소는 localhost:18089로 지정했다. 에뮬레이터 재시작 후에는 `adb -s emulator-5556 reverse tcp:18089 tcp:18089`를 다시 실행한다. serial은 `adb devices`로 확인한다. 정상 실행 캡처는 `experiments/react-native/android-parity/native/14-metro-fixed.png`다.
