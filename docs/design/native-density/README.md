# Android·React Native 화면 밀도 정리

2026-11-04 시작 · [Issue #39](https://github.com/choiyoung69/daynomy_agent/issues/39) ·
[PR #41](https://github.com/choiyoung69/daynomy_agent/pull/41)

사용자가 두 앱에서 글자·버튼·여백이 전반적으로 크다고 지적했다. 시각 기준은 실제
staff.daynomy.com 모바일 반응형과 기존 WebView이며, 하단 세 탭과 플랫폼별 기능·저장 방식은 유지한다.
새 스타일이나 장식 자산을 추가하지 않고 기존 흰 표면·검정 행동·청색 강조를 정리했다.

## 변경

| 요소 | 적용 |
| --- | --- |
| 글자 위계 | 페이지 22, 섹션 18, 목록 16–17, 본문 14–15, 보조문 12–13. 기사 본문은 15/25 줄간격 |
| RN 버튼 | 세로 패딩 14→8, 라벨 15→14. 터치 영역은 최소48 유지 |
| 페이지 리듬 | 반복24 간격을20으로, 섹션 내부18을12로 조정. 비회원의 빈 분석 버튼 래퍼 제거 |
| 자산 요약 | RN의 큰 테두리 카드를 평평한 요약과 하단 구분선으로 정리. 금액35→30 |
| 뉴스 | 목록/캐러셀 제목을 줄이고 기사 폭680 제한, 상세 사진은 고정높이 대신 비율 유지 |
| 탐색 | RN 하단 바 최소80→64, 라벨14→12. 큰 글자는 자연스럽게 높이가 늘어남 |
| Android | 공통 Material Typography로 크기·줄간격을 지정. 기존 48dp 터치·sp 확대·뒤로가기 유지 |
| 넓은 화면 | 두 앱의 페이지를 최대760으로 제한하고 중앙 정렬하여 긴 읽기 폭 방지 |

숫자·분석·시세를 새로 만들지 않았다. Android의 AI 제외와 비회원 메모리 저장, RN의 기존
로컬 거래 저장·회원 쓰기·뉴스 요청 수명을 보존한다. 계정의 기존 보조 기능을 삭제하지 않았다.

## 기반과 변경 보존

작업 브랜치 `design/39-native-density`는 main `8ab8a55a`에서 만들었다.
RN은 실행 중이던 `codex/rn-android-parity` (`3c5cd119`)와 그 미커밋 뉴스 상세/키워드 작업을
별도 공간에 복사했다. 이 때문에 PR에는 기존 RN의 3탭·실제 뉴스 연결·키워드 기능도 함께 포함된다.
작업 중 원래 RN 공간에서 바뀐 뉴스 상세 진입·이미지 실패 표시·계정 흐름도 읽어 보존했다.
원래 RN/Android 작업 공간에는 이 작업의 스타일 변경을 쓰지 않았다.

사용한 스킬: Impeccable의 native adapt·craft floor, redesign-existing-projects,
daynomy-kb-input, React Best Practices의 관련 React/접근성 검토 항목.
Impeccable 자동 로더는 엔진 캐시 권한 때문에 실행되지 않아 기존 PRODUCT/DESIGN·원본 명세를 직접 읽었다.
밀도 수정 자체에는 새 폰트·라이브러리·범용 하네스·AI 생성 자산을 추가하지 않았다.
기반 RN 미커밋 작업이 이미 사용하던 expo-linear-gradient 의존성과 잠금 파일은 함께 보존했다.

KB의 `news/android --require-ready --check-only`는 준비 판정이 통과했다.
`news/react-native`는 버전·수명·빌드 메타데이터가 오래되어 NOT READY였다.
이를 통과로 바꾸지 않았으며 현행 package-lock·API·요청 취소 코드·기존 검사를 직접 대조했다.

## 현재 검증

- RN 기존 회귀50개와 TypeScript 검사 통과. 동시 변경과 밀도 수정을 반영한 최종 재검사도 모두 통과했다.
- Android debug APK·검사 APK·lint 새 실행 성공: 77 tasks, 1분24초.
- API33 ARM64 별도 emulator-5580에서 화면19개 실행: 18통과, 1실패.
  실패는 `PortfolioWebDesignScreenTest.unauthorizedReadOffersRealAccountRouteInsteadOfGuestStorage`가
  새 비회원 임시 화면 대신 예전 `portfolio-login`을 기다리는 사례다. 고정 검사를 수정/skip하지 않았다.
- 현재 비회원 계약의 `ApprovedPortfolioScreenTest.unauthorizedReadShowsSeparateGuestDraftWithoutMemberDataAndCanOpenAccount`
  한 개를 추가 실행하여 통과했다. 앞선 실패를 통과로 대체하지 않는다.
- 비회원 페이지 폭 제한 보완 후 APK·검사 APK·lint 재실행 성공: 77 tasks 중13 실행·64 캐시.
  변경 영향을 받는 기존 `GuestPortfolioScreenTest` 1개를 새 APK에서 재실행하여 통과했다.
- 실제 staff 390/820폭 원본 캡처, 실행 RN의 자산/계정 화면을 확인했다.
- 승인된 ADB 조작으로 별도 API33 에뮬레이터의 RN을 실제 로컬 API에 연결했다.
  remote295 → local102 기사의 원래 제목·발행일·본문과 실제 이미지 로딩을 확인했다.
  본문의 `공모가`를 눌러 뜻·기사 맥락·확인할 점 3개가 원본 값과 일치함을 대조했고,
  아래 시장 분석의 위험 요인·확인할 점 2개도 원본 값과 일치했다. 닫기와 목록 이동을 확인했다.
- 두 앱의 세로/가로 화면에서 하단 탭과 스크롤을 확인했다. RN 계정과 Android 비회원 화면은
  글자130%에서도 줄바꿈·버튼·하단 탭 접근을 확인했다. 가로 화면은1080×2400 기기의 회전이며
  별도 태블릿 검증으로 세지 않는다. 검증 후 글자1.0·자동회전 원래 설정을 복원했다.
- 11월5일 확인 시 오늘 뉴스는 비어 있고 전체 목록에는 11월4일의 실제 기사가 보였다.
  오늘 표시를 채우려고 원래 발행일을 바꾸지 않았다. Android는 기존 main의 뉴스 부가 기능
  범위를 유지했으며 RN의 이미지·키워드·시장 분석 검증을 Android 완료로 확대하지 않는다.

상세 로컬 근거는 Git 제외 `.local/native-design/`의 소스 manifest·원본 화면·검사 로그에 있다.
Metro 미리보기는 localhost18090에 한정한다. 다른 작업이 쓰던5556의 포트 전달은 원래18089로 복원했다.
주요 캡처는 `device/rn-article-top.png`, `rn-keyword-clean.png`, `rn-market-analysis.png`,
`rn-landscape.png`, `rn-account-font130.png`, `android-portfolio-font130.png`,
`android-portfolio-landscape-final.png`에 있다. `final-verification.json`에 검사 대상 파일·APK 해시를 남겼다.
기존 UI 검사1개 실패를 남겨 PR은 Draft로 유지한다. 운영 브랜치에 병합하지 않았다.
운영 배포·실기기·iOS·TalkBack은 이번 검증으로 표현하지 않는다. 시간·비용 절감은 미계측이다.
