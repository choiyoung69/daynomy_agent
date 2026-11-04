# Android 피드백 보내기 — F11

기존 미구현 F11을 계정 화면의 '의견 보내기'에서 연다. 로그인 없이도 사용할 수 있다.
기준은 ../feedback.md, ../service.md F11, 원본 frontend/src/features/feedback/api.ts와
backend FeedbackCreateRequest/FeedbackController다. Rust/API 기준을 새로 바꾸지 않는다.

## 계약

- POST /api/feedback에 문자열 content, pagePath를 JSON으로 전송한다.
- content 원문 UTF-16 길이는 1~1000, pagePath는 1~2048. Java Character.isWhitespace 기준
  공백만 있는 값은 거절한다. 길이는 trim 전 검사한다. NBSP와 이모지 경계를 보존한다.
- 클라이언트에서 원문을 trim하지 않는다. 서버가 기존 strip 정책을 적용한다.
- 현재 폼 pagePath는 /feedback이다. pagePath가 반드시 /로 시작해야 한다는 새 제약은 없다.
- 기존 SessionHttpTransport를 재사용해 CSRF 쿠키/헤더를 준비한다. 성공 204 빈 본문을 JSON 파싱하지 않는다.
- POST 자동 재시도 없음. 전송 중 중복 클릭과 내용 변경을 막는다.
- 성공 시에만 내용 초기화/완료 표시. API 오류는 입력을 유지하고 명시적 재시도 가능.
- IOException 등 전송 결과 불명은 입력 유지·결과 미확정 표시·재전송 차단.
  사용자가 '새 의견 작성'을 선택해야 초안을 비우고 별도 전송을 시작할 수 있다.
- 닫기/취소 뒤 늦은 결과가 새 상태를 바꾸지 않는다. 취소 예외를 일반 실패로 감추지 않는다.
- UI는 입력 label·1000자 안내/계수·오류/성공의 텍스트·48dp 버튼·키보드 스크롤을 제공한다.

## 고정 인터페이스

market-core의 Feedback.kt:
- interface FeedbackSource { suspend fun submit(content: String, pagePath: String) }
- class FeedbackClient(transport: SessionTransport) : FeedbackSource
- fun feedbackContentError(content: String): String?
- data class FeedbackUiState(content: String = "", isSubmitting: Boolean = false,
  sent: Boolean = false, error: String? = null, outcomeUnknown: Boolean = false)
- class FeedbackController(source: FeedbackSource, scope: CoroutineScope,
  pagePath: String = "/feedback") : AutoCloseable
- controller.state: StateFlow<FeedbackUiState>; editContent(String), submit(), reset(), close().

## 필요한 확인

독립 JVM 계약/상태 테스트의 실제 red→green, 기존 세션 계약 회귀와 앱 debug 빌드.
CSRF→POST·204·실패·중복 클릭은 로컬 MockWebServer/제어 source로 확인한다.
기기/화면 실행, 실제 Rust/DB 저장, 실제 사용자 데이터 검증은 실행 증거를 따로 표시한다.
새 실행기·A/B 실험·모델 비교를 추가하지 않는다.
