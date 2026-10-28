# 012 — 언어·플랫폼 상세 지식 패키지

- 요청: 단일 개요 수준의 언어 지식을 실제 이식에 사용할 수 있도록 보강하고, 언어/플랫폼을 하나의 패키지 아래 주제별 문서로 구성한다.
- 기준: reference/2026-DAYNOMY-dev 읽기 전용. 실제 앱·서버 구현·배포와 원본 변경은 이번 범위 밖이다.
- 작업자: 현재 대화 에이전트 1개. 하위 에이전트·독립 리뷰 실행 없음.
- 시작: 2026-10-28 16:06:52 KST (07:06:52 UTC). 종료와 실제 검증은 아래 보고서를 기준으로 기록한다.

## 구축 내용

Android/Kotlin, iOS/Swift, React Native/TypeScript, Flutter/Dart, WebView/TS+Kotlin+Swift,
Rust 백엔드의 6개 상세 패키지에 9개 주제씩 54개 문서를 작성했다.
기존 언어/플랫폼 파일은 개요 진입점으로 유지하고 상세 목차에 연결했다.

각 주제는 잘못된 변환·적용 코드 또는 어댑터 설계·경계 사례·공식 자료·실행 범위를 담는다.
UI/HTTP/스토리지 스니펫은 실제 프로젝트에 연결할 설계이며 전체 컴파일/통합 성공을 주장하지 않는다.
제품 계약과 기존 F01–F13/F14 보류는 공통·기능 문서를 재사용한다.

`packs.json`과 `knowledge.py`에 상세 패키지·주제 선택을 연결했다. 기본은 해당 패키지의 주요 8개 주제,
인증 기능과 WebView는 인증/저장도 추가한다. 명시 --topic은 상세 읽기 범위를 좁히며 기능/공통 계약은 유지한다.
다른 플랫폼 상세 본문과 평가 기대 답변을 출력하지 않는다. 자료 선택은 접근 통제·자동 작업 배정이 아니다.

## 공식 자료와 실행 예제

E50–E63에서 컬렉션/복사·readonly·취소·actor·timeout·날짜 정규화·Arc·BigDecimal·브리지 경계를 보강했다.
응답 바이트와 제한된 읽기 범위, 기준 지정 이유를 sources.json에 기록했다.
외부 총 63개는 보관본 기준이며 전체 사이트·전체 언어의 지식을 수집했다는 뜻은 아니다.

예제용 Kotlin 2.4.21·Dart 3.13.7·TypeScript 6.0.2를 .local/knowledge-sdks에 격리했다.
Kotlin/Dart/TS 배포물은 upstream SHA-256/SHA-512, serialization 1.12.0 JAR는 upstream SHA-1로 확인하고
모든 다운로드의 로컬 SHA-256을 기록했다. 예제 버전을 앱 지원 버전으로 선택하지 않는다.
Rust 예제 직접 의존성은 serde_json 1.0.154(arbitrary_precision), Tokio 1.54.0이며 Cargo.lock을 고정했다.
Kotlin은 bundled coroutine JAR를 사용하며 별도 프로젝트 버전 승인과 구별한다.

[최종 언어 실행](../knowledge/evidence/2026-10-28-topic-examples-04.json): Kotlin 25·Dart 22·Swift 18·TS 20·Rust 15 = 100개.
TS strict 타입 검사, 실제 Kotlin serialization/coroutine·Dart VM·macOS Swift Foundation/Task/actor·Rust Tokio를 실행했다.
브리지 origin 순수 함수·메시지 스키마와 가짜 트랜잭션 제어 흐름은 실제 호스트/DB 검증으로 집계하지 않는다.
이전 01–03 보고서는 당시 소스의 성공 결과이며 현재 해시와 구별해 보존했다.

## 발견한 실패와 수정

- Maven .sha256 주소는 404였다. 제공되는 upstream .sha1로 검증하고 로컬 SHA-256도 기록했다.
- E55 첫 raw 주소 수집은 실패했다. 이전 경로의 응답은 redirect shell이므로 기준으로 지정하지 않았다.
  canonical cancellation 문서의 본문과 CancellationException·협력 취소 절을 확인한 뒤 고정했다.
  실패·shell·canonical 수집 보고서는 모두 보존했다.
- 문서 링크 검사가 코드의 native[message.method](message.payload)를 링크로 오인했다.
  fenced/inline code를 제외하고 실제 Markdown 링크를 검사하도록 수정했다. 실제 깨진 링크 거부 회귀 검사는 유지했다.
- 첫 확장 선택기 회귀 검사에서 새 detailed-package 언어 검증이 기존 검증보다 먼저 실패해 진단 문구 검사가 1개 실패했다.
  누락을 거부하는 조건을 유지하고 실제 새 진단을 확인하도록 수정했다.
- EV21의 과거 'Dart 실행 증거 없음' 기준은 실제 DX02/DX09 실행으로 낡았다.
  Dart VM 사례와 Flutter/웹 통합 미검증을 구별하도록 갱신하고 EV26–EV31을 추가했다. 다른 기존 기대 기준은 보존했다.

## 검증과 남은 범위

[검증 보고서](../knowledge/evidence/2026-10-28-detailed-packages.json)는 실행 명령·종료 코드·소스 해시를 기록한다.
check는 출처/링크/목차/패키지 매핑과 언어 실행 기록의 현재 예제 해시를 검사한다.
coverage는 위키 99개 중 필수 96개, 상세 패키지 6개/주제 54개, 기능 14개, API 지도 연결의 구조 검사다.
숫자나 통과 표시는 내용의 충분성·독립 의미 평가·앱 준비/완료를 인증하지 않는다.

앱 지원 OS/SDK/의존성 잠금·HTTP/인증/저장소 어댑터·실제 기기·화면·HTTP/DB·호스트 브리지 검증은 남아 있다.
기존 Rust 서비스의 실제 동작 결과는 과거 run 010의 범위이며 이번에 다시 검증한 것으로 표시하지 않는다.
위키 효과를 비교하는 독립 실험과 개발 시간 절감률·모델 비용은 미측정이다.

## 최종 결과

- 종료: 2026-10-28 16:48:10 KST. 이번 상세 패키지 작업 경과 41분 18초(자료 수집·SDK 준비·문서·검사·재작업·대기 포함). 이전 전체 지식베이스 구축 시간은 미측정이다.
- preflight: 원본 29/29 해시 일치, 종료 0. 서버/DB 동작 검증은 아님.
- knowledge.py check: 로컬 출처 105/105·위키 99·질문 31·외부 고정 응답 63/63, 종료 0.
- coverage 및 knowledge_inventory.py --check: 구조·원본 API 매핑 일치, 종료 0.
- 선택/준비/증거 회귀 18개·원문 관리 6개·API 매핑 4개 = 28개 통과, 각 종료 0.
- 독립 언어 예제 100개 성공 및 현재 예제/러너 8개 파일의 실행 기록 해시 일치.
- 다섯 플랫폼의 context --require-ready는 모두 예상한 종료 2. 미정 버전·정책을 성공으로 바꾸지 않았다.
- 독립 의미 평가·실제 앱/호스트/HTTP/DB 통합·개발 시간 비교는 미실행이다.
