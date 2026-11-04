# 시각 검토 1 / 최대2 — Issue #31

조정자가 제공한 실제 Simulator PNG9장을 각각 열어 검토했다. 직접 캡처·앱 실행은 하지 않았다. 증거 manifest는 `.local/phone-normal-captures/manifest.json`, `.local/ipad-captures/manifest.json`, `.local/phone-large-dark-captures/manifest.json`이다. 각 묶음의 포트폴리오·이슈·계정3장을 모두 확인했다. 사진·기사·로그인 전 상태는 합성 HTTP fixture이며 실제 뉴스·OAuth 완료 증거가 아니다. AI 단독 진입 추가 전 캡처다.

Android 비교 이미지는 별도 worktree `/Users/seoyeong/develop/AI/daynomy_agent/.local/android-portfolio-15/docs/design/2026-11-04-web-reference/android/`의 `carousel-search.png`, `shell-account-guest.png`, `carousel-dashboard-font200.png`를 열었다. 사진/scrim·본문 검색·하단3탭·계정 로그인과 서비스 행의 의미·검정 제목/회색 보조문을 대조했다. iOS 위젯 외형 자체가 Android와 다른 점은 결함으로 보지 않았다.

## 이번 수정 배치

1. **P2 — Dark XXXL 주요 CTA 텍스트 소실.** `96AA4151-7CE4-4420-B04B-5BF4989B7D8E.png`의 거래 기록 capsule은 흰 배경에 파랑+만 보이고 버튼 이름을 읽을 수 없다. `.tint(.primary)`와 기본 prominent foreground가 dark에서 대비 쌍을 이루지 못한다. 거래·로그인 주요 CTA 모두 배경/글자를 semantic 대비 쌍으로 명시한다. 계정 dark 캡처는 버튼까지 스크롤되지 않아 로그인 버튼 결함 자체를 그 이미지에서 관찰했다고 주장하지 않는다.
2. **P2 — XXXL에서 종목 조회가 한 글자씩 분리.** 같은 캡처에서 거래 버튼 옆 종목 조회가 세로 글자열로 좁아진다. accessibility category에서는 CTA 두 개를 세로로 배열하고 읽을 수 있는 폭·44pt 터치를 보장한다.
3. **P2 — 이슈 목록의 보조 글자가 낮은 대비의 청색으로 노출.** 라이트 Phone·iPad 이슈 캡처에서 제목은 청색, 날짜·분류는 더 옅은 청색이다. NavigationLink tint 계층이 `foregroundStyle(.primary/.secondary)`에 영향을 준다. 일반 기사 행을 `.buttonStyle(.plain)`으로 만들거나 `Color.primary/Color.secondary`를 명시해 공통 기준의 검정 제목·회색 메타데이터를 복구한다. 픽셀 측정 없이 정확한 대비 비율은 단정하지 않는다.

## 동일 배치의 기존 지적

- 오늘 뉴스 이전/다음 아이콘의 44pt frame은 label 안에 적용해 실제 버튼 hit frame을 보장한다. 조정자의 UI 검사에서 현재 width12.67pt가 관찰됐다.
- 계정 의견 진입은 이름 `의견 보내기`와 설명 hint를 분리한다. 시각 설명문은 유지한다.
- AI 분석을 캘린더와 별도 의미로 노출하고 캘린더 보조 진입을 보존한다. 추가 제공자 호출은 만들지 않는다.

## 확인한 점과 제한

일반 Phone과 iPad에서 세 목적지는 하단에 유지되며 본문은 native List/ScrollView로 읽힌다. 오늘 뉴스는 실제 fixture 사진·어두운 scrim·흰 제목/분류/일자를 사용하고 순위/가상 인기도는 없다. iPad에서도 carousel 한 장·위치1/9·이전/다음과 아래 검색/목록 관계가 유지된다. 일반 계정 로그인 CTA와 피드백 행은 읽을 수 있다.

XXXL에서 이슈 카드와 계정 설명은 화면보다 길지만 수직 스크롤 콘텐츠이므로 화면 첫 장에서 아래 내용이 보이지 않는 사실만으로 잘림으로 판단하지 않는다. 최종 확인에서는 조정자가 제공하는 수정 후 캡처와 UI 결과로 위 항목 해결 여부만 확인한다. VoiceOver 발화·실제 접근성 탐색·키보드·회전은 정지 이미지9장만으로 승인하지 않는다.

## 최종 확인 2 / 2

`experiments/ios-common-ui/screenshots/`의 Phone·iPad·PhoneLargeDark 각3개 PNG, 총9개를 모두 개별 열어 확인했다. 이 패스에서는 기존 지적 해결 여부만 확인하고 추가 앱 실행·촬영·취향 수정을 하지 않았다.

- **해결:** `phone-large-dark-portfolio-first-entry.png`에서 거래 기록은 흰 배경과 검정 이름/아이콘으로 읽힌다. 이전에 흰 이름이 사라지던 문제가 없다.
- **해결:** 같은 이미지의 거래 기록과 종목 조회는 세로로 배치된다. 종목 조회가 한 글자씩 세로로 쪼개지던 문제가 없다. 화면 하단의 일부 내용은 스크롤 중간 상태와 시스템 tab bar 뒤에 놓이며, 최종 항목 가림 여부나 실제 터치 가능성은 이 이미지로 단정하지 않는다.
- **해결:** Phone/iPad 이슈 목록 제목은 검정, 메타데이터는 회색으로 복구됐다. 사진/scrim/흰 기사 제목 패턴은 유지된다.
- **확인:** Phone/iPad 요약 아래 AI 포트폴리오 분석 독립 진입과 투자 캘린더 보조 진입이 보인다. 코드에서 `showCalendar:false`는 calendar section·request task·refresh retry를 실행하지 않고 기존 saved analysis GET/명시 POST를 재사용한다.
- **코드 확인:** 오늘 뉴스 버튼은 label 안44pt frame/contentShape를 사용한다. 계정 의견 진입은 label/hint를 구분하며 전송 버튼은 별도 identifier를 갖는다. 로그인 CTA도 systemBackground foreground로 대비 쌍을 명시했다. Dark 계정 정지 이미지는 로그인 버튼까지 내려가지 않아 이 버튼의 dark 시각 검증 완료로 세지 않는다.

이전 지적 범위에서 미해결 사항은 없다. 조정자가 전달한 UI 합집합16·상태13/17 통과는 별도 실제 검사 기록에 연결하며, 이 리뷰어가 재실행했다고 기록하지 않는다. API·DB·OAuth·외부 제공자·VoiceOver 실기 검증 결과가 아니다. 최종 소스/검사 manifest 해시는 조정자가 전달하는 메타데이터에 연결한다.
