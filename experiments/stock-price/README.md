# 최근 종가 조회 — 독립 테스트 작성 실험

계약: [spec/stock-price.md](../../spec/stock-price.md).
대상은 공개 GET `/api/stocks/{assetId}/price` 하나다. 피드백 앱·뉴스/계산 샘플과 분리한다.

```text
테스트 작성 에이전트 → Rust 테스트 작성 → 빈 구현에서 실패 확인 → 테스트 고정
구현 에이전트 → Rust 모듈 구현/수정
검사 프로그램 → 고정 테스트 + 결함 주입 4개 + 실제 Spring/Rust/DB 비교
리뷰 에이전트 → 구현·테스트·실행 근거 검토 → 승인 또는 구현 수정 요청
```

API 하나이므로 구현 담당은 1개다. 테스트 작성 1개·구현 1개·공유 검토 역할 1개를
필요할 때 각각 새 문맥으로 호출한다. 구현은 고정 테스트를 수정할 수 없다.
테스트 작성은 구현 이전에 수행한다. 전체 파일 읽기를 격리한 보안 환경은 아니다.

```sh
python3 scripts/stock_price_workflow.py --plan
python3 scripts/stock_price_workflow.py
```

설정은 `agents/stock-price.json`. 현재 backend는 Codex CLI, model=null은 CLI 기본 선택이다.
새 API용 후보 Rust, 명세, 필요한 원본 발췌와 검사 결과를 모델 서비스에 전송한다.
테스트·구현 담당은 각 임시 폴더만 쓰고 검토는 읽기 전용이다. 테스트 실행 바이너리도
파일 읽기 전용·네트워크 차단 환경에서 실행하며 컴파일은 조정기가 수행한다.

실제 비교는 별도 새 PostgreSQL fixture와 원본 Spring 전체 앱을 사용한다.
실험 데이터 전수 로딩 어댑터이므로 운영 SQL/성능·가격 수집·외부 API·인증은 범위 밖이다.
결과와 실패 이력은 `.local/stock-price-workflows/`에 저장한다. 호출 실패는 완료가 아니다.
실행 기록: [runs/007-stock-price.md](../../runs/007-stock-price.md).

## 현재 결과

최근 종가 모듈과 테스트를 구현했다. 독립 작성 테스트 11개 통과, 고립된 빌드 폴더의
잘못된 통화/날짜/가격/가격 없음 응답 4개 모두 테스트에서 탐지, 실제 Spring/Rust/DB
비교 22개 통과, 별도 읽기 전용 리뷰 승인이다. 승인받은 소스와 테스트를 그대로 반영했다.

CLI 실행은 경로 실수·429로 중단됐다. 최종 구현/리뷰에는 실제 앱 서브에이전트를 사용했고,
현재 대화가 요청/응답을 연결했다. **단독 CLI 무인 실행의 성공은 아니다.**
`--backend desktop_bridge`는 대화의 배정이 필요하다. `--from-run`은 중단 기록을 보존하며
그때의 변경 없는 테스트를 재사용한다. `--reuse-implementation`도 코드 재사용일 뿐,
새 실행의 모든 검사와 새 리뷰를 생략하지 않는다.

테스트와 변형 바이너리는 각각 별도 Cargo target을 사용한다. 첫 실제 비교에서 마지막
변형 서버가 재사용되는 문제를 발견해 수정했다. 함수 테스트 통과만으로 HTTP 동작을
확인했다고 가정하지 않는다. 최종 실행은 `.local/stock-price-workflows/20261021T032402Z-67ebf2cf/`다.
