# 001 — 최소 하네스 준비

- 날짜: 2026-10-20, Asia/Seoul.
- 사용자 요청: 원본에서 대표 기능 하나를 골라 명세와 최소 하네스를 구성.
- 상태: 준비 완료, Rust 구현 실험은 아직 시작하지 않음.
- 원본: `reference/2026-DAYNOMY-dev`. `.git`가 없어 커밋 SHA 미확인.
  관련 원본 파일 SHA-256을 `spec/reference-snapshot.json`에 보관.
- 변경 범위: 원본 밖의 명세·지침·검증 스크립트. 원본 코드는 수정하지 않음.
- 에이전트: 현재 대화의 에이전트 하나. 하위 에이전트 실행 없음.
- 비용/토큰/총 소요 시간: 미측정. 임의 수치를 작성하지 않음.

## 선정과 발견

피드백 등록을 선택했다. 회원 변경은 인증 준비가 필요하고 포트폴리오는 가격·환율 및
원장 의존성이 커서 첫 실험에서 원인 분리가 어렵다.

분석 중 발견한, 단순 Controller 복사로 놓칠 수 있는 조건:

1. `permitAll`이지만 CSRF 예외가 아니다. 컨트롤러 테스트는 필터를 꺼서 이를 잡지 못한다.
2. DTO 검증 후 Service에서 strip한다. 먼저 trim하면 길이 초과를 잘못 허용할 수 있다.
3. Java String은 UTF-16 길이이며 Rust 바이트 길이와 다르다.
4. Java strip과 Rust trim은 일부 Unicode 공백에서 다르다.
5. 기존 저장 테스트는 Mock이어서 영속성까지 확인했다고 할 수 없다.
6. 입력값 오류 ADR은 템플릿이고 README의 피드백 마이그레이션 번호와 SQL 파일이 다르다.

위 사실을 명세와 인수 검증에 반영했다. 하네스 덕분에 구현 성능이 좋아졌다는
결론은 아직 낼 수 없다. 구현 실패를 보기 전 준비 단계의 관찰이다.

## 실행 환경과 증거

- Python 3.14.2, Rust/Cargo 1.92.0, JDK 21, psql 명령 존재 확인.
- Docker CLI는 있지만 현재 샌드박스에서 daemon socket 접근 권한 오류.
  daemon 중단 여부는 알 수 없다. 이번 준비에는 컨테이너가 필요 없어 변경/재시작하지 않음.
- 임시 Java 프로그램으로 이모지 length=2, U+2003 strip 제거,
  U+00A0 strip 보존 및 isBlank=false를 확인.
- Spring 서버/Gradle 테스트는 실행하지 않았다. 실제 보안 필터·validation provider
  런타임 호환성은 아직 확인하지 않았다.
- Rust 서버와 테스트 DB는 만들지 않았다. HTTP/DB 인수 검증의 제품 통과 결과는 없다.

## 하네스 검증 결과

| 실행 | 결과 |
| --- | --- |
| `python3 scripts/check.py preflight` | 종료 0, 관련 원본 29/29 해시 일치, cargo/rustc/psql 확인 |
| `python3 scripts/test_acceptance.py` | 종료 0, 검증기 자체 테스트 8개 통과 |
| `python3 scripts/check.py verify` | 예상한 종료 2, app/Cargo.toml 부재를 미구현으로 처리 |
| 환경변수 없이 `python3 scripts/acceptance.py` | 예상한 종료 2, HTTP/DB 환경 누락을 실패 처리 |
| Python AST 구문 검사 | 스크립트 3개 통과 |

인수 검증에는 HTTP 사례 33개와 CSRF 준비 검사가 있다. 위 8개는 **검증기 자체 테스트**이며,
Rust 기능 테스트 33개가 통과했다는 뜻이 아니다. 실제 HTTP 전송·psql 연결을 이용한
종단 검증은 Rust 서버와 테스트 DB가 준비된 다음 실행한다.

## 다음 실행

`prompts/implement.md`로 첫 구현을 시작한다. `runs/002-implementation.md`에
실패·수정·사람 개입·실제 검사 결과를 기록한다.
프레임워크 경계는 개별 라이브러리 허용이라는 작업 가정으로 명시했다.
현재 준비 중 사람이 추가로 결정해야 해서 멈춘 사항은 없다.
