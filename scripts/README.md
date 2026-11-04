# Python 도구 목록

2026-11-04 파일 정적 열람 기준: Python 63개. 이 목록 작성 중 도구를 실행하지 않았다.

앱 구현은 `app/`·`clients/`에 있다. Python은 검사·실험·환경·KB를 지원한다.
현재 운영 절차는 [CONTRIBUTING](../CONTRIBUTING.md), 대상별 실행법은 각 README를 따른다.
분류는 삭제나 의존성 분리 완료를 뜻하지 않는다. 일부 과거 도구는 다른 실행기에서 import한다.
이 목록은 수동 관리한다. 도구 추가·역할 변경 시 갱신한다.

## 실제 동작 검사·gate

제품 변경 시 관련 명세에 맞게 선택한다. 이름이 비슷해도 피드백·전체 서비스·플랫폼 검사의 범위는 다르다. DB·서버·기기를 사용하는 도구가 있으므로 실행 전 해당 파일과 안내를 읽는다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [acceptance.py](acceptance.py) | Local HTTP + PostgreSQL acceptance gate; never deletes test data. |
| [admin_feedback_gate.py](admin_feedback_gate.py) | Serialized live Spring/Rust gate for the frozen admin feedback contracts. |
| [android_device_probe.py](android_device_probe.py) | Actual emulator UI -> Rust/DB smoke flow; requires the disposable backend fixture. |
| [check.py](check.py) | Fail-closed checks; preflight is not an implementation pass. |
| [check_lifecycle.py](check_lifecycle.py) | Restart/fault probe on the dedicated test DB. Temporarily rejects inserts. |
| [compare_feedback.py](compare_feedback.py) | Send identical feedback bodies to two real servers; compare HTTP and DB effects. |
| [flutter_auth_acceptance.py](flutter_auth_acceptance.py) | Frozen pre-implementation mobile PKCE bridge checks over loopback HTTP/PostgreSQL. |
| [flutter_check.py](flutter_check.py) | Run Flutter checks, preserving criteria/source hashes and actual command logs. |
| [run_comparison.py](run_comparison.py) | Build an exact source copy, run isolated Spring/Rust servers, compare, then stop. |
| [sample_feature_gate.py](sample_feature_gate.py) | Real HTTP/PostgreSQL differential gate for three bounded sample endpoints. |
| [service_acceptance.py](service_acceptance.py) | Independent F03/F04/F08/F09/F10 HTTP + real PostgreSQL acceptance cases. |
| [service_admin_acceptance.py](service_admin_acceptance.py) | Independent F12 native HTTP/PG tests from original Java controllers/DTOs/services. |
| [service_analysis_acceptance.py](service_analysis_acceptance.py) | Independent F06 deterministic HTTP/PG contracts from original Java V1..53. |
| [service_auth_provider_acceptance.py](service_auth_provider_acceptance.py) | Independent loopback Google OIDC fixture and native HTTP/PostgreSQL checks. |
| [service_binding_acceptance.py](service_binding_acceptance.py) | Compare Spring integer binding to Rust over real HTTP, without assuming answers. |
| [service_calendar_acceptance.py](service_calendar_acceptance.py) | Independent F07 real HTTP/PostgreSQL contracts, original Java V1..53 basis. |
| [service_core_acceptance.py](service_core_acceptance.py) | Independent F01/F02/F05 real HTTP/PostgreSQL contract checks. |
| [service_fx_acceptance.py](service_fx_acceptance.py) | Independent F03/F05 local FX-provider HTTP/PG checks; no real EODHD calls. |
| [service_gate.py](service_gate.py) | Build an isolated Rust snapshot and run independent suites on disposable DBs. |
| [service_media_acceptance.py](service_media_acceptance.py) | Independent F12 local Wikimedia/OpenAI/S3 provider and native DB contracts. |
| [service_schedule_acceptance.py](service_schedule_acceptance.py) | Independent native --job contracts from original KRX/BLS/BOK/DART/FX services. |
| [service_social_acceptance.py](service_social_acceptance.py) | Independent original Java YouTube/social-search/official-profile collection gate. |
| [service_sync_acceptance.py](service_sync_acceptance.py) | Independent F13 native synchronization contracts from original Java V1..53. |
| [stock_price_gate.py](stock_price_gate.py) | Real original/Rust HTTP gate for the bounded latest-stock-price experiment. |
| [workflow_gate.py](workflow_gate.py) | Trusted, real HTTP/PostgreSQL gate for an isolated workflow candidate. |

## 과거 AI 호출·조정 실험

명시적으로 해당 실험을 선택한 경우만 실행한다. Codex 호출·검사·복구 비용이 발생할 수 있다. 일반 개발의 기본 명령으로 사용하지 않는다. 공용 adapter로 import되는 코드도 있어 파일 이동·삭제는 별도 영향 조사 후 진행한다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [admin_feedback_queue.py](admin_feedback_queue.py) | Small real-model queue experiment; isolated candidates, never auto-merge. |
| [agent_workflow.py](agent_workflow.py) | Two independent CLI agents, a trusted gate, and a bounded repair state machine. |
| [parallel_features.py](parallel_features.py) | Two independent sample implementers, one reviewer slot and a trusted merge gate. |
| [sample_features.py](sample_features.py) | Measured sample using the existing real CLI adapter and a separate local gate. |
| [stock_price_workflow.py](stock_price_workflow.py) | Independent test author -> implementation -> real tests -> read-only review. |

## 실행·격리·작업 상태 지원

실행기나 조정자가 사용한다. task_queue는 콜백 실행기이며 파일 자체가 모델을 의미하지 않는다. android_pilot은 상태/의존성 기록이며 에이전트 자동 실행기가 아니다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [android_pilot.py](android_pilot.py) | Dependency/slot/time ledger for root-dispatched desktop agents; not an agent launcher. |
| [readonly_runner.py](readonly_runner.py) | Cargo target runner: execute candidate tests with read-only filesystem access. |
| [task_queue.py](task_queue.py) | A bounded DAG dispatcher for real, deadline-aware agent/check callbacks. |

## KB·원문·언어 예제

관련 KB 변경·원문 갱신·언어 예제 작업 때 사용한다. 수집/해시/적용 선언과 의미 정확성·앱 동작 검증을 구분한다. SDK 설치와 외부 수집을 모든 작업에서 반복하지 않는다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [android_knowledge.py](android_knowledge.py) | Materialize minimal pinned KB input and validate declared use; no model-thinking guarantee. |
| [knowledge.py](knowledge.py) | Read-only checks and lexical search for the local knowledge base. |
| [knowledge_example_sdks.py](knowledge_example_sdks.py) | Prepare checksummed, repository-local Kotlin/Dart runtimes for knowledge examples. |
| [knowledge_inventory.py](knowledge_inventory.py) | Compare the documented non-league API inventory with original Java mappings. |
| [knowledge_probes.py](knowledge_probes.py) | Run synthetic language boundary probes, without starting apps or databases. |
| [knowledge_sources.py](knowledge_sources.py) | Capture public source responses; review and pin separately. No wiki/model execution. |
| [knowledge_topic_examples.py](knowledge_topic_examples.py) | Compile/run topic examples and preserve failures. No target app/server/DB execution. |

## 환경·fixture·미리보기

필요한 개발·검증 환경에서만 사용한다. 서버·DB 생성·SDK 설치가 포함될 수 있다. 운영 환경에 사용하지 않는다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [android_backend_fixture.py](android_backend_fixture.py) | Serve existing Rust code against a disposable local DB for Android acceptance. |
| [flutter_backend_fixture.py](flutter_backend_fixture.py) | Own a disposable Rust/PostgreSQL fixture for Flutter verification only. |
| [flutter_preview.py](flutter_preview.py) | Serve a Flutter web build and proxy the local API on one loopback origin. |
| [flutter_setup.py](flutter_setup.py) | Install the pinned official macOS ARM64 Flutter SDK inside .local only. |
| [service_migrate.py](service_migrate.py) | Initialize an isolated local service database without running Java/Flyway. |

## 검사기·실행기의 자체 테스트

주로 해당 도구를 변경할 때 실행한다. 일부 기존 gate는 이 테스트를 함께 실행한다. 이 PR은 호출 관계를 수정하지 않으므로 자동 분리가 적용된 것은 아니다. 자체 테스트 통과만으로 앱 동작 완료를 선언하지 않는다.

| 파일 | 파일에 선언된 역할 |
| --- | --- |
| [test_acceptance.py](test_acceptance.py) | Tests for false-positive risks in the acceptance gate, not for the future Rust app. |
| [test_admin_feedback_gate.py](test_admin_feedback_gate.py) | Lock regression checks; never start models, servers, or a database. |
| [test_admin_feedback_oracle.py](test_admin_feedback_oracle.py) | Oracle v2 safeguards: synthetic evidence only, no models/servers/database. |
| [test_admin_feedback_queue.py](test_admin_feedback_queue.py) | Local orchestrator safeguards; no model, subprocess, HTTP or database calls. |
| [test_admin_feedback_revision.py](test_admin_feedback_revision.py) | Independent regression-author contracts; no model, HTTP, or database calls. |
| [test_agent_workflow.py](test_agent_workflow.py) | Controller unit tests with explicitly synthetic agents and gate evidence. |
| [test_android_knowledge.py](test_android_knowledge.py) | Regression checks for required KB packet provenance and acceptance mapping. |
| [test_compare_feedback.py](test_compare_feedback.py) | Guard against comparator false positives; no servers or database required. |
| [test_knowledge.py](test_knowledge.py) | Check context selection and readiness decisions with isolated synthetic fixtures. |
| [test_knowledge_inventory.py](test_knowledge_inventory.py) | Check that changed, missing and newly added source routes cannot silently pass. |
| [test_knowledge_sources.py](test_knowledge_sources.py) | Exercise source revision handling without network or product data. |
| [test_parallel_features.py](test_parallel_features.py) | Synthetic parallel-controller tests: no model, native sandbox, Rust or DB runs. |
| [test_readonly_runner.py](test_readonly_runner.py) | Real native-process probes of the read-only Cargo runner, no model calls. |
| [test_sample_feature_gate.py](test_sample_feature_gate.py) | Regression checks for observed comparison mistakes, without model/DB calls. |
| [test_service_acceptance.py](test_service_acceptance.py) | Checker self-tests: meaningful false-positive and environment-boundary probes. |
| [test_stock_price_workflow.py](test_stock_price_workflow.py) | Exercise stock-price completion guards without models, servers or compilation. |
| [test_task_queue.py](test_task_queue.py) | Independent, local-only scheduling contract tests (no real agent calls). |
| [test_task_queue_metrics.py](test_task_queue_metrics.py) | Focused callback measurement regressions; local callbacks, not agent evidence. |

## 관련 파일

`flutter.sh`는 Flutter CLI 실행 경로를 제공하는 셸 래퍼다. 위 Python 수에는 포함하지 않는다.
`agents/*.json`·`prompts/`는 실험별 설정/입력이다. 역할 파일 존재와 실제 모델 호출은 구분한다.

## 다음 검토 후보

- 앱 변경 때 함께 실행되는 하네스 자체 테스트의 선택 조건.
- 같은 후보에 대한 중복 빌드·HTTP/DB 실행과 로그 재전달.
- 재시도·리뷰 호출과 사용량 집계의 연결.
- KB 필수 규칙과 참고 문서의 구분.

위 항목은 계획이며 이번 문서 정리로 실행 시간·토큰 절감을 입증하지 않았다.


## 기존 CLI adapter의 입력 경계

`agent_workflow.CliAgent`를 사용하는 기존 실험에는 새 ephemeral 세션과 기본 32 KiB UTF-8 prompt 제한을 적용한다. 초과 입력은 계약을 자르지 않고 호출 전에 거절한다. `max_prompt_bytes`로 명시적으로 조정할 수 있다. Workflow의 기본 `--evidence-mode inline`은 전체 근거 본문을 유지한다. `--evidence-mode reference`를 명시한 실험에서만 전체 gate JSON을 `prompt-evidence/`에 보존하고 prompt에 근거 경로/해시·리뷰 지적을 전달한다. 실제 작은 회귀 비교에서는 참조 방식이 더 느려 기본으로 채택하지 않았다. `input.json`은 입력 크기/해시, `attempts.json`은 실패 시도까지 원본 사용량(없으면 빈 목록)을 기록한다. 크기 제한은 시스템·도구·파일 읽기까지 포함하는 모델 토큰 상한이 아니다. 과거 실행기를 자동 시작하지 않으며 실제 개발의 새 채팅 시작은 `HANDOFF.md`를 따른다.


## 작업별 KB를 실제 공통 입력에 넣기

기존 Android 작업 프로필을 명시한 `CliAgent(knowledge_task="query-reset", knowledge_base=".local/<작업>/knowledge")`는 ensure/준비·출처 검증 후 선택 문서 본문만 실제 모델 prompt에 삽입한다. Workflow CLI에서도 `--knowledge-task`/`--knowledge-base`로 연결한다. 프로필은 해당 과제에 맞아야 한다. caller prompt에 KB 전체를 미리 넣지 않는다. custom adapter를 직접 주는 경우 KB는 그 adapter에 설정해야 하며 Workflow가 무시하지 않고 오류로 알린다. 현재 선택기는 Android만 지원하며 다른 플랫폼을 자동 판정하지 않는다.

`input.json`의 knowledge에는 task·manifest/문서/삽입 문자열 해시와 bytes, 실제 최종 prompt 크기·해시, 준비 시간을 남긴다. attempts에는 프로세스/이벤트 처리 경과도 남긴다. 알 수 없는/미준비/변경된 자료는 호출 전 실패한다. 관련 실구현 비교와 시간 악화까지 `experiments/task-kb-input-ab`에 보존했다.


## 준비·조정·검증·기록 비용을 한 번에 확인

기존 Workflow 종료 시 cost-summary.json/md를 자동 생성하고 phase_seconds에 단계 경과를 기록한다. CLI 출력은 짧은 상태/근거 경로로 제한하지만 전체 질문·실패 근거는 state.json에 보존한다. 기존 인수 gate를 생략하거나 성공 결과를 캐시해 승인하지 않는다.

종료한 작업의 조정 비용까지 포함하려면 모델을 다시 실행하지 않고 다음 명령 한 번만 사용한다.

```sh
python3 scripts/agent_workflow.py --summarize-run .local/<실행> \
  --coordinator-rollout <해당 세션.jsonl> --coordinator-turn <해당 턴 ID> \
  --coordinator-cwd <해당 저장소 경로>
```

보고 모드는 Workflow/모델/검사/DB를 시작하지 않는다. 지정한 턴과 cwd만 읽고 response_id·CLI session/attempt 식별자로 중복을 제거한다. 실패/사용량 누락은 unknown으로 표시한다. 부모 전체 경과에 child 시간을 더하지 않는다. 조정 로그를 주지 않으면 agent 비용만 알 수 있어 complete=false다. 진행 중 조정 턴도 complete=false이며 생성 시각까지 부분 집계다. 내부 모델 응답 수가 없는 CLI usage record 수를 모델 호출 수로 바꾸지 않는다. 보고서를 한 번 확인해 기존 기록/PR에 링크하고 수동 Python 재계산·반복 상태 조회·원시 로그 재출력을 하지 않는다. 이 도구가 현재 데스크톱 대화의 누적 문맥을 초기화하지는 않는다.
