#!/usr/bin/env python3
"""Two independent CLI agents, a trusted gate, and a bounded repair state machine."""
import argparse
from datetime import datetime, timezone
from contextlib import nullcontext
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from workflow_gate import run_gate, _acceptance_valid, _lifecycle_valid

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"main.rs", "feedback.rs", "csrf.rs"}
RESULT_KEYS = {"status", "summary", "findings", "questions"}
REQUIRED_CHECKS = {"preflight", "build", "verify", "lifecycle", "server-stop"}
ROLE_STATUSES = {
    "implementer": {"implemented", "needs_decision", "blocked"},
    "test_author": {"tests_written", "needs_decision", "blocked"},
    "reviewer": {"approve", "revise", "needs_decision", "blocked"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hash(root):
    return hashlib.sha256(json.dumps(
        {name: digest(Path(root) / name) for name in sorted(SOURCES)}, sort_keys=True
    ).encode()).hexdigest()


def clean_env():
    return {"PATH": os.environ["PATH"], "LANG": "en_US.UTF-8", "TZ": "Asia/Seoul",
            "PYTHONDONTWRITEBYTECODE": "1"}


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
    # The leader may exit while a background descendant stays in its group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def capture(command, prompt, events, timeout, env):
    with Path(events).open("w") as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                   text=True, env=env, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_group(process)
            raise RuntimeError("Agent time limit exceeded") from None
        finally:
            # Do not leave agent-started background commands running after the turn.
            stop_group(process)
    return process.returncode


def permission_config(role, workspace):
    access = {":root": "read"}
    if role in ("implementer", "test_author"):
        access[str(Path(workspace).resolve())] = "write"
    table = ",".join(json.dumps(key) + "=" + json.dumps(value) for key, value in access.items())
    return 'permissions.daynomy_role={filesystem={' + table + '},network={enabled=false}}'


def permission_probe(workspace, control, role):
    """Exercise the same native permission profile used by the model's shell tools."""
    workspace, control = Path(workspace), Path(control)
    workspace.mkdir(parents=True, exist_ok=True)
    control.mkdir(parents=True, exist_ok=True)
    outside = control / "permission-sentinel.txt"
    outside.write_text("protected")
    inside = workspace / "permission-probe.txt"
    program = (
        "from pathlib import Path; import json; result={};\n"
        f"for name,path in [('inside',Path({str(inside)!r})),('outside',Path({str(outside)!r}))]:\n"
        " try: path.write_text('changed'); result[name]='write'\n"
        " except PermissionError: result[name]='denied'\n"
        "print(json.dumps(result))"
    )
    command = ["codex", "sandbox", "-P", "daynomy_role", "-C", str(workspace),
               "-c", permission_config(role, workspace), sys.executable, "-c", program]
    result = subprocess.run(command, env=clean_env(), text=True, capture_output=True, timeout=30)
    expected = {"inside": "write" if role in ("implementer", "test_author") else "denied", "outside": "denied"}
    try:
        actual = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("Native permission probe unavailable") from None
    if result.returncode or actual != expected or outside.read_text() != "protected":
        raise RuntimeError("Native role permissions did not enforce expected boundaries")
    if inside.exists():
        inside.unlink()
    return {"role": role, "observed": actual, "passed": True}


def validate_result(result, role):
    if role not in ROLE_STATUSES:
        raise ValueError("Unknown agent role")
    allowed = ROLE_STATUSES[role]
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise ValueError("Invalid agent result keys")
    if result["status"] not in allowed or not isinstance(result["summary"], str):
        raise ValueError("Invalid role status")
    for key in ("findings", "questions"):
        if not isinstance(result[key], list) or not all(isinstance(s, str) and s.strip()
                                                       for s in result[key]):
            raise ValueError("Invalid agent findings/questions")
    if result["status"] == "needs_decision" and not result["questions"]:
        raise ValueError("Decision request requires a concrete question")
    if result["status"] != "needs_decision" and result["questions"]:
        raise ValueError("Unresolved questions cannot count as approval")
    if result["status"] == "approve" and result["findings"]:
        raise ValueError("Unresolved review findings cannot count as approval")
    if result["status"] == "revise" and not result["findings"]:
        raise ValueError("Revision requires a finding")
    return result


def transient_error(events):
    for line in Path(events).read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message") if event.get("type") == "error" else None
        if event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        if isinstance(message, str):
            for status in ("429 Too Many Requests", "503 Service Unavailable"):
                if status in message:
                    return status
    return None


class CliAgent:
    def __init__(self, timeout=240, model=None, max_attempts=3, reasoning_effort=None, executable="codex", max_prompt_bytes=32 * 1024):
        self.timeout = timeout
        if isinstance(max_prompt_bytes, bool) or not isinstance(max_prompt_bytes, int) or max_prompt_bytes < 1:
            raise ValueError("Prompt byte limit must be a positive integer")
        self.max_prompt_bytes = max_prompt_bytes
        if model is not None and (not isinstance(model, str) or not model.strip()
                                  or model.startswith("-") or any(c.isspace() for c in model)):
            raise ValueError("Invalid model identifier")
        if max_attempts not in (1, 2, 3):
            raise ValueError("Agent attempts must be between one and three")
        if reasoning_effort not in (None, "low", "medium", "high", "xhigh", "max", "ultra"):
            raise ValueError("Invalid reasoning effort")
        self.model, self.max_attempts = model, max_attempts
        self.reasoning_effort = reasoning_effort
        self.executable = str(executable)

    def __call__(self, role, workspace, prompt, output_dir):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Agent prompt must be nonempty text")
        prompt_bytes = prompt.encode("utf-8")
        if len(prompt_bytes) > self.max_prompt_bytes:
            raise ValueError(f"Agent prompt is {len(prompt_bytes)} bytes; limit {self.max_prompt_bytes}; use scoped file references, never truncate required evidence")
        input_evidence = {"prompt_bytes": len(prompt_bytes), "prompt_characters": len(prompt),
                          "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
                          "max_prompt_bytes": self.max_prompt_bytes, "context_mode": "fresh-ephemeral"}
        if role not in ROLE_STATUSES:
            raise ValueError("Unknown agent role")
        if (output_dir / "input.json").exists() or (output_dir / "result.json").exists():
            raise RuntimeError("Agent output path must be fresh")
        output_dir.mkdir(parents=True, exist_ok=True)
        dump(output_dir / "input.json", input_evidence)
        statuses = sorted(ROLE_STATUSES[role])
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"status": {"type": "string", "enum": statuses},
                                 "summary": {"type": "string"},
                                 "findings": {"type": "array", "items": {"type": "string"}},
                                 "questions": {"type": "array", "items": {"type": "string"}}},
                  "required": sorted(RESULT_KEYS)}
        schema_path, result_path = output_dir / "schema.json", output_dir / "result.json"
        dump(schema_path, schema)
        if result_path.exists():
            raise RuntimeError("Agent output path must be fresh")
        command = [self.executable, "-a", "never", "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "-C", str(workspace),
                   "-c", 'default_permissions="daynomy_role"',
                   "-c", permission_config(role, workspace), "-c", 'web_search="disabled"',
                   "-c", "project_doc_max_bytes=0", "--json", "--color", "never",
                   "--output-schema", str(schema_path), "-o", str(result_path), "-"]
        if self.model is not None:
            command[-1:-1] = ["--model", self.model]
        if self.reasoning_effort is not None:
            command[-1:-1] = ["-c", f'model_reasoning_effort="{self.reasoning_effort}"']
        attempts = []
        for attempt in range(1, self.max_attempts + 1):
            events = output_dir / ("events.jsonl" if attempt == 1 else f"events-attempt-{attempt}.jsonl")
            capture_error = None
            try:
                code = capture(command, prompt, events, self.timeout, clean_env())
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                code, capture_error = None, error
            session_ids, usage_records = [], []
            with events.open() if events.exists() else nullcontext([]) as event_stream:
                for line in event_stream:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") == "thread.started":
                        session_ids.append(event.get("thread_id"))
                    if event.get("type") in ("turn.completed", "turn.failed") and isinstance(event.get("usage"), dict):
                        usage_records.append(event["usage"])
            attempts.append({"attempt": attempt, "exit_code": code, "events": str(events),
                             "session_ids": session_ids, "usage_records": usage_records})
            if capture_error is not None:
                attempts[-1]["error_type"] = type(capture_error).__name__
            dump(output_dir / "attempts.json", attempts)
            if capture_error is not None:
                raise capture_error
            if code == 0 and result_path.is_file():
                break
            transient = transient_error(events)
            if not transient or attempt == self.max_attempts:
                raise RuntimeError("Agent CLI failed: " + (transient or "missing valid result")
                                   + "; evidence=" + str(events))
            if result_path.exists():
                result_path.rename(output_dir / f"failed-result-{attempt}.json")
            print(json.dumps({"status": "agent_retry", "role": role, "attempt": attempt,
                              "reason": transient}, ensure_ascii=False), flush=True)
            time.sleep(30 * attempt)
        usage = usage_records[-1] if usage_records else None
        if len(session_ids) != 1 or not isinstance(session_ids[0], str):
            raise RuntimeError("Missing unique agent session identity")
        result = validate_result(json.loads(result_path.read_text()), role)
        return result, {"session_id": session_ids[0], "role": role, "exit_code": code,
                        "requested_model": self.model, "model_selection": "explicit" if self.model else "cli_default",
                        "requested_reasoning_effort": self.reasoning_effort,
                        "executable": self.executable,
                        "result": str(result_path), "events": str(events), "usage": usage,
                        "attempts": attempts, "input": input_evidence}


def import_sources(workspace, candidate, baseline):
    actual = {p.name for p in workspace.iterdir()}
    if actual != SOURCES:
        raise ValueError("Agent added or removed a source path")
    for name in SOURCES:
        path = workspace / name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("Only independent regular source files are accepted")
        if path.stat().st_size > 256 * 1024:
            raise ValueError("Agent source size limit exceeded")
        text = path.read_text()
        if name == "main.rs" and not text.startswith("#![forbid(unsafe_code)]\n"):
            raise ValueError("Crate-level unsafe prohibition must remain enabled")
        before = baseline[name]
        marker = "#[cfg(test)]"
        if marker in before and text.partition(marker)[1:] != before.partition(marker)[1:]:
            raise ValueError("Protected embedded Rust tests changed")
    for name in SOURCES:
        target = candidate / "app/src" / name
        if (workspace / name).resolve() != target.resolve():
            shutil.copyfile(workspace / name, target)


def snapshot_files(root, paths):
    result = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("Trusted file must be regular: " + str(relative))
        result[str(relative)] = digest(path)
    return result


def check_snapshot(root, manifest):
    for name, expected in manifest.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError("Trusted criteria changed: " + name)


def inject_no_persistence(candidate):
    path = candidate / "app/src/main.rs"
    text = path.read_text()
    begin = text.index('"INSERT INTO feedbacks')
    end = text.index('RETURNING id"', begin) + len('RETURNING id"')
    text = text[:begin] + ('"SELECT 1::bigint AS id WHERE $1::text IS NOT NULL '
                           'AND $2::text IS NOT NULL"') + text[end:]
    path.write_text(text)


def gate_passes(gate, expected_hash):
    if not isinstance(gate, dict) or gate.get("status") != "passed":
        return False
    if gate.get("source_sha256") != expected_hash:
        return False
    records = gate.get("checks", [])
    if not isinstance(records, list) or not all(isinstance(c, dict) for c in records):
        return False
    checks = {c.get("name"): c.get("exit_code") for c in records}
    if len(checks) != len(records):
        return False
    if not REQUIRED_CHECKS.issubset(checks) or any(checks[name] != 0 for name in REQUIRED_CHECKS):
        return False
    try:
        started = datetime.fromisoformat(gate["started_at"]).timestamp()
        for key, validator, count in (("acceptance", _acceptance_valid, 46),
                                      ("lifecycle", _lifecycle_valid, 4)):
            item = gate[key]
            if not isinstance(item, dict):
                return False
            path = Path(item["report"])
            if (item.get("passed") is not True or item.get("count") != count
                    or path.is_symlink() or not path.is_file() or path.stat().st_mtime < started
                    or not validator(json.loads(path.read_text()))):
                return False
    except (OSError, ValueError, TypeError, KeyError):
        return False
    return True


def summarize_run(run_dir, coordinator_rollout=None, coordinator_turn=None, coordinator_cwd=None):
    """Deterministic accounting from explicitly scoped artifacts; never calls a model or gate."""
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise ValueError('Run directory is missing')
    if any((coordinator_rollout, coordinator_turn, coordinator_cwd)) and not all((coordinator_rollout, coordinator_turn, coordinator_cwd)):
        raise ValueError('Coordinator rollout, turn and cwd must be specified together')
    agent_records, unmeasured, attempt_times = {}, set(), {}
    files = list(run_dir.rglob('attempts.json'))
    for path in files:
        if path.is_symlink() or not (path.parent / 'input.json').is_file():
            raise ValueError('Invalid agent accounting artifact')
        for attempt in json.loads(path.read_text()):
            records = attempt.get('usage_records', [])
            identity = tuple(attempt.get('session_ids') or [str(path)])
            attempt_key = (identity, attempt['attempt'])
            if not records: unmeasured.add(attempt_key)
            attempt_times[attempt_key] = attempt.get('capture_seconds', 0)
            for index, usage in enumerate(records):
                agent_records[(identity, attempt['attempt'], index)] = usage
    missing, capture_seconds = len(unmeasured), sum(attempt_times.values())
    def totals(records, unmeasured=0):
        rows = list(records)
        if not rows:
            return {**{k:None for k in ('input_tokens','cached_input_tokens','non_cached_input_tokens','output_tokens','total_tokens')},
                    'usage_records':0,'unmeasured_attempts':unmeasured}
        for u in rows:
            for key in ('input_tokens', 'output_tokens'):
                if type(u.get(key)) is not int or u[key] < 0:
                    raise ValueError('Invalid usage counters')
            if 'total_tokens' in u and (type(u['total_tokens']) is not int or u['total_tokens'] != u['input_tokens'] + u['output_tokens']):
                raise ValueError('Inconsistent total usage counter')
            c = u.get('cached_input_tokens')
            if c is not None and (type(c) is not int or not 0 <= c <= u['input_tokens']):
                raise ValueError('Invalid cached input counter')
        inp = sum(u['input_tokens'] for u in rows)
        out = sum(u['output_tokens'] for u in rows)
        cached = sum(u['cached_input_tokens'] for u in rows) if all('cached_input_tokens' in u for u in rows) else None
        return {'input_tokens': inp, 'cached_input_tokens': cached,
                'non_cached_input_tokens': inp-cached if cached is not None else None,
                'output_tokens': out, 'total_tokens': inp+out, 'usage_records': len(rows),
                'unmeasured_attempts': unmeasured}
    state_path = run_dir / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    def elapsed(start, end):
        return (datetime.fromisoformat(end.replace('Z','+00:00')) - datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds() if start and end else None
    wall = elapsed(state.get('started_at'), state.get('finished_at'))
    parent, parent_rows = None, {}
    parent_complete = False
    if coordinator_rollout:
        active, contexts, start, end = False, [], None, None
        with Path(coordinator_rollout).open() as stream:
            for line in stream:
                row = json.loads(line); value = row.get('payload', {})
                if row['type'] == 'event_msg' and value.get('type') == 'task_started':
                    active = value.get('turn_id') == coordinator_turn
                    if active: start = row['timestamp']
                if not active: continue
                if row['type'] == 'turn_context': contexts.append(value.get('cwd'))
                if row['type'] == 'token_usage_record' and value.get('turn_id') == coordinator_turn:
                    parent_rows[value['response_id']] = value['usage']
                if row['type'] == 'event_msg' and value.get('type') == 'task_complete' and value.get('turn_id') == coordinator_turn:
                    end = row['timestamp']
        expected = Path(coordinator_cwd).resolve()
        if not start or not contexts or any(not isinstance(c,str) or not Path(c).resolve().is_relative_to(expected) for c in contexts):
            raise ValueError('Coordinator turn/cwd is not in the authorized scope')
        parent = totals(parent_rows.values())
        wall, parent_complete = elapsed(start,end), end is not None
    combined = totals([*agent_records.values(), *parent_rows.values()], missing)
    report = {'generated_at': now(),
              'coordinator_started_at': start if coordinator_rollout else None,
              'coordinator_finished_at': end if coordinator_rollout else None,
              'agent': totals(agent_records.values(),missing), 'coordinator': parent,
              'combined_measured': combined, 'complete': bool(agent_records) and not missing and parent_complete and bool(parent_rows) and combined['cached_input_tokens'] is not None,
              'elapsed_seconds': wall, 'agent_capture_seconds_sum': capture_seconds,
              'phase_seconds': state.get('phase_seconds', {}), 'workflow_status': state.get('status'),
              'scope': 'explicit CLI artifacts plus selected coordinator turn; elapsed times are not added',
              'sources': {'agent_artifact_count': len(files), 'coordinator_turn': coordinator_turn},
              'counts_note': 'CLI usage records are not individual model-response counts; missing usage is unknown'}
    dump(run_dir / 'cost-summary.json',report)
    lines = ['# Run cost summary', '', 'Measured token totals; not billing. Missing scope/usage is unknown.', '',
             '| Scope | Input | Cached | Non-cached | Output | Total |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, value in [('Agents',report['agent']),('Coordinator',parent),('Combined measured',combined)]:
        if value is None: lines.append('| '+name+' | unknown | unknown | unknown | unknown | unknown |')
        else: lines.append('| '+name+' | '+' | '.join(('unknown' if value[k] is None else str(value[k])) for k in ('input_tokens','cached_input_tokens','non_cached_input_tokens','output_tokens','total_tokens'))+' |')
    lines += ['', 'Complete scope: '+str(report['complete']), 'Elapsed seconds: '+str(wall),
              'Phase seconds: '+json.dumps(report['phase_seconds']), 'Workflow status: '+str(report['workflow_status']), report['counts_note']]
    (run_dir / 'cost-summary.md').write_text('\n'.join(lines)+'\n')
    return report


def prepare_coordinator(spec_path, root, output, max_bytes=8192):
    """Create a bounded new-chat entry point, never load referenced source/history."""
    root = Path(root).resolve()
    spec = json.loads(Path(spec_path).read_text())
    required = {'task', 'issue', 'done', 'files', 'checks', 'unverified', 'next'}
    if set(spec) != required:
        raise ValueError('Coordinator packet requires task/issue/done/files/checks/unverified/next')
    for key in ('task', 'issue', 'next'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError('Empty coordinator field: ' + key)
    for key in ('done', 'files', 'checks', 'unverified'):
        if not isinstance(spec[key], list) or not spec[key] or any(not isinstance(v, str) or not v.strip() for v in spec[key]):
            raise ValueError('Nonempty string list required: ' + key)
    for name in spec['files']:
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Selected file must exist within workspace: ' + name)
    lines = ['# 새 채팅 인계', '', '작업 공간: ' + str(root),
             '작업: ' + spec['task'], '연결 Issue/PR: ' + spec['issue'], '',
             '이 인계와 현재 요청·저장소 지침부터 읽는다. 과거 대화·전체 실험 기록을 초기 입력에 넣지 않는다.',
             '먼저 브랜치·미커밋 변경·Issue/PR 상태를 묶어 확인하고 기존 변경을 보존한다.',
             '아래 선택 파일부터 읽고 공백·실패 근거가 있을 때만 조회를 확대한다. 검사를 생략하는 지시가 아니다.']
    for title, key in [('완료 조건', 'done'), ('선택 파일·근거', 'files'), ('필수 검사', 'checks'), ('미검증·주의', 'unverified')]:
        lines += ['', '## ' + title] + ['- ' + value for value in spec[key]]
    lines += ['', '다음 행동: ' + spec['next'], '',
              '독립 조회·검사는 묶고 완료 알림을 기다린다. 같은 조건에서 통과한 검사는 반복하지 않는다.',
              '작업 마감에 기존 --summarize-run과 --record를 한 번 실행한다. 실패·누락도 기록하고 자동 머지하지 않는다.',
              '이 파일 생성은 현재 채팅을 초기화하지 않는다. 새 채팅에 이 파일 경로만 전달한다.']
    body = '\n'.join(lines) + '\n'
    size = len(body.encode('utf-8'))
    if not 1 <= max_bytes <= 8192 or size > max_bytes:
        raise ValueError('Coordinator handoff exceeds byte budget; narrow scope without dropping acceptance criteria')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body)
    return {'handoff': str(output), 'bytes': size, 'max_bytes': max_bytes,
            'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(), 'selected_files': len(spec['files'])}


def record_cost(report, run_dir, destination):
    """Replace this run's short record in place; no model or additional queries."""
    key = hashlib.sha256(str(Path(run_dir).resolve()).encode()).hexdigest()[:16]
    start, end = '<!-- workflow-cost:' + key + ' -->', '<!-- /workflow-cost:' + key + ' -->'
    value = report['combined_measured']
    def show(v): return '미계측' if v is None else str(v)
    block = '\n'.join([start, '### 실행 비용 · ' + Path(run_dir).name, '',
        '| 범위 | 경과(초) | 캐시 입력 | 비캐시 입력 | 출력 | 미계측 시도 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
        '| ' + ('종료 집계' if report['complete'] else '부분 집계') + ' | ' +
        ' | '.join(show(v) for v in (report['elapsed_seconds'], value['cached_input_tokens'],
        value['non_cached_input_tokens'], value['output_tokens'], value['unmeasured_attempts'])) + ' |',
        '', '조정 모델 응답: ' + show((report['coordinator'] or {}).get('usage_records')) +
        '. CLI usage record를 모델 호출 수로 세지 않음. 미계측은 0이 아님. 전체 경과는 PR 게시 경과와 별도.', end])
    path = Path(destination)
    text = path.read_text() if path.exists() else ''
    if start in text:
        a = text.index(start); b = text.index(end, a) + len(end)
        text = text[:a] + block + text[b:]
    else:
        text = text.rstrip() + '\n\n' + block + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Workflow:
    def __init__(self, root, run_dir, task, agent=None, gate=run_gate, rounds=3, demo=False,
                 probe=True):
        self.root, self.run_dir = Path(root).resolve(), Path(run_dir).resolve()
        self.task, self.agent, self.gate = task, agent or CliAgent(), gate
        self.rounds, self.demo, self.probe = rounds, demo, probe
        self.state = {"status": "preparing", "started_at": now(), "task": task,
                      "events": [], "rounds": [], "agents": [], "fault_test": demo}
        self.session_ids = set()

    def event(self, status, **details):
        self.state["status"] = status
        self.state["events"].append({"time": now(), "status": status, **details})
        dump(self.run_dir / "state.json", self.state)
        print(json.dumps({"status": status, **details}, ensure_ascii=False), flush=True)

    def prepare(self):
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.candidate = self.run_dir / "candidate"
        self.candidate.mkdir()
        paths = [Path("AGENTS.md"), Path("README.md"), Path("app/Cargo.toml"),
                 Path("app/Cargo.lock"), Path("app/README.md")]
        for folder, pattern in (("scripts", "*.py"), ("scripts", "*.sh"),
                                ("spec", "*"), ("prompts", "*.md"), ("app/migrations", "*")):
            paths += [p.relative_to(self.root) for p in (self.root / folder).glob(pattern)
                      if p.is_file()]
        snapshot = json.loads((self.root / "spec/reference-snapshot.json").read_text())
        paths += [Path(snapshot["root"]) / item["path"] for item in snapshot["files"]]
        self.protected = snapshot_files(self.root, paths)
        for name in self.protected:
            target = self.candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / name, target)
        source = self.candidate / "app/src"
        source.mkdir(parents=True)
        self.baseline = {}
        for name in SOURCES:
            self.baseline[name] = (self.root / "app/src" / name).read_text()
            (source / name).write_text(self.baseline[name])
        self.original_sources = source_hash(self.root / "app/src")
        dump(self.run_dir / "criteria.json", self.protected)
        self.worker = Path(tempfile.mkdtemp(prefix="daynomy-implementer-", dir="/private/tmp"))
        if self.probe:
            self.state["permission_probes"] = [permission_probe(
                self.worker, self.run_dir / "probe-control", "implementer")]
            reviewer_probe = self.run_dir / "reviewer-probe"
            self.state["permission_probes"].append(permission_probe(
                reviewer_probe, self.run_dir / "probe-control", "reviewer"))

    def integrity(self):
        check_snapshot(self.root, self.protected)
        check_snapshot(self.candidate, self.protected)
        if source_hash(self.root / "app/src") != self.original_sources:
            raise ValueError("Original application source changed")

    def invoke(self, role, workspace, prompt, directory):
        result, identity = self.agent(role, workspace, prompt, directory)
        validate_result(result, role)
        identity = {**identity, "role": role}
        if not identity.get("session_id") or identity["session_id"] in self.session_ids:
            raise ValueError("Agent sessions must be independent")
        self.session_ids.add(identity["session_id"])
        self.state["agents"].append(identity)
        self.integrity()
        return result

    def prompt(self, role, feedback):
        text = (self.root / "prompts" / ("worker.md" if role == "implementer" else "reviewer.md")).read_text()
        # Keep full controller evidence on disk; only actionable review and status enter the next prompt.
        payload = json.dumps(feedback, ensure_ascii=False, indent=2) + "\n"
        evidence_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        evidence_path = self.run_dir / "prompt-evidence" / (evidence_hash + ".json")
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if evidence_path.exists() and evidence_path.read_text() != payload:
            raise ValueError("Prompt evidence changed")
        if not evidence_path.exists():
            evidence_path.write_text(payload)
        summary = {key: feedback[key] for key in ("message", "review") if key in feedback}
        gate = feedback.get("gate")
        if isinstance(gate, dict):
            summary["gate_status"] = gate.get("status")
        return (text + "\n\nTASK:\n" + self.task + "\n\nAUTHORITATIVE CONTRACT:\n"
                + str(self.candidate / "spec/feedback.md") + "\n\nPREVIOUS EVIDENCE:\n"
                + str(evidence_path) + "\nSHA256: " + evidence_hash
                + "\nRead the referenced evidence and relevant failure reports before changing code or approving. "
                  "A summary does not replace the original evidence. Do not reread unrelated history.\n"
                + json.dumps(summary, ensure_ascii=False))

    def format_sources(self, round_dir):
        with (round_dir / "format.log").open("w") as log:
            formatted = subprocess.run(
                ["cargo", "fmt", "--manifest-path", str(self.candidate / "app/Cargo.toml")],
                env=clean_env(), stdout=log, stderr=log, timeout=60)
        if formatted.returncode:
            raise RuntimeError("Controller formatter failed; see format.log")
        import_sources(self.candidate / "app/src", self.candidate, self.baseline)

    def execute(self):
        try:
            self.prepare()
            feedback = {"message": "First implementation pass. Inspect the existing source against the contract."}
            for number in range(1, self.rounds + 1):
                self.integrity()
                round_dir = self.run_dir / f"round-{number}"
                round_dir.mkdir()
                for child in self.worker.iterdir():
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                for name in SOURCES:
                    shutil.copyfile(self.candidate / "app/src" / name, self.worker / name)
                self.event("implementing", round=number)
                implementation = self.invoke("implementer", self.worker,
                                             self.prompt("implementer", feedback), round_dir / "implementer")
                if implementation["status"] in ("needs_decision", "blocked"):
                    self.event(implementation["status"], questions=implementation["questions"],
                               reason=implementation["summary"])
                    break
                import_sources(self.worker, self.candidate, self.baseline)
                if self.demo and number == 1:
                    inject_no_persistence(self.candidate)
                    self.event("fault_injected", kind="false-204-without-persistence", round=number)
                # Formatting is a deterministic controller action, never a model verdict.
                self.event("formatting", round=number)
                self.format_sources(round_dir)
                gated_hash = source_hash(self.candidate / "app/src")
                shutil.copytree(self.candidate / "app/src", round_dir / "gated-source")
                self.event("verifying", round=number, source_sha256=gated_hash)
                gate = self.gate(self.candidate, self.root, round_dir / "gate",
                                 "daynomy_workflow_" + uuid.uuid4().hex[:12] + "_test")
                self.integrity()
                if source_hash(self.candidate / "app/src") != gated_hash:
                    raise ValueError("Candidate changed during validation")
                gate["source_sha256"] = gated_hash
                dump(round_dir / "gate/result.json", gate)
                passed = gate_passes(gate, gated_hash)
                entry = {"round": number, "source_sha256": gated_hash,
                         "implementation": implementation, "gate": gate}
                self.state["rounds"].append(entry)
                if gate.get("status") == "blocked":
                    self.event("blocked", reason=gate.get("reason", "Gate environment unavailable"))
                    break
                review_space = round_dir / "review-input"
                shutil.copytree(round_dir / "gated-source", review_space / "src")
                shutil.copyfile(self.candidate / "spec/feedback.md", review_space / "feedback.md")
                dump(review_space / "gate.json", gate)
                review_manifest = snapshot_files(review_space, [p.relative_to(review_space)
                                                 for p in review_space.rglob("*") if p.is_file()])
                self.event("reviewing", round=number, gate_passed=passed, source_sha256=gated_hash)
                review = self.invoke("reviewer", review_space, self.prompt("reviewer", {
                    "gate": str(review_space / "gate.json"), "source": str(review_space / "src"),
                    "source_sha256": gated_hash}), round_dir / "reviewer")
                check_snapshot(review_space, review_manifest)
                if source_hash(self.candidate / "app/src") != gated_hash:
                    raise ValueError("Reviewed source differs from validated source")
                entry["review"] = review
                if review["status"] in ("needs_decision", "blocked"):
                    self.event(review["status"], questions=review["questions"], reason=review["summary"])
                    break
                if passed and review["status"] == "approve":
                    self.integrity()
                    patch = "".join("".join(difflib.unified_diff(
                        self.baseline[name].splitlines(keepends=True),
                        (self.candidate / "app/src" / name).read_text().splitlines(keepends=True),
                        fromfile="a/app/src/" + name, tofile="b/app/src/" + name,
                    )) for name in sorted(SOURCES))
                    (self.run_dir / "candidate.patch").write_text(patch)
                    self.event("completed", round=number, patch=str(self.run_dir / "candidate.patch"),
                               source_sha256=gated_hash)
                    break
                feedback = {"gate": gate, "review": review}
                self.event("repairing", round=number, gate_passed=passed, review_status=review["status"])
            else:
                self.event("failed", reason="Repair round limit reached")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.event("blocked", reason=type(exc).__name__ + ": " + str(exc)[:250])
        finally:
            if hasattr(self, "worker"):
                shutil.rmtree(self.worker)
            self.state["finished_at"] = now()
            dump(self.run_dir / "state.json", self.state)
        return self.state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-coordinator', type=Path, help='JSON task packet to bounded new-chat handoff; no model/check execution')
    parser.add_argument('--handoff-output', type=Path)
    parser.add_argument('--coordinator-root', type=Path, default=ROOT)
    parser.add_argument('--record', type=Path, help='Update one run block in existing experiment record alongside summary')
    parser.add_argument('--summarize-run', type=Path, help='Read existing evidence and emit one bounded cost report; no model/check execution')
    parser.add_argument('--coordinator-rollout', type=Path)
    parser.add_argument('--coordinator-turn')
    parser.add_argument('--coordinator-cwd', type=Path)
    parser.add_argument("--task", default="Implement the approved feedback contract without changing its requirements.")
    parser.add_argument("--demo", action="store_true", help="Inject one no-save fault after first implementation")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.prepare_coordinator:
        if not args.handoff_output or args.summarize_run or args.record or any((args.coordinator_rollout, args.coordinator_turn, args.coordinator_cwd)):
            parser.error('Prepare requires --handoff-output and cannot summarize/record')
        print(json.dumps(prepare_coordinator(args.prepare_coordinator, args.coordinator_root, args.handoff_output), ensure_ascii=False))
        return 0
    if args.handoff_output:
        parser.error('--handoff-output requires --prepare-coordinator')
    if args.record and not args.summarize_run:
        parser.error('--record requires --summarize-run')
    if args.summarize_run:
        report = summarize_run(args.summarize_run,args.coordinator_rollout,args.coordinator_turn,args.coordinator_cwd)
        if args.record:
            record_cost(report, args.summarize_run, args.record)
        print(json.dumps({'report':str(args.summarize_run/'cost-summary.json'),'complete':report['complete'],'elapsed_seconds':report['elapsed_seconds'],'combined_measured':report['combined_measured']},ensure_ascii=False))
        return 0
    if any((args.coordinator_rollout,args.coordinator_turn,args.coordinator_cwd)):
        parser.error('Coordinator arguments require --summarize-run')
    if not 1 <= args.rounds <= 3:
        parser.error("rounds must be 1..3")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / ".local/agent-workflows" / run_id
    state = Workflow(ROOT, directory, args.task, rounds=args.rounds, demo=args.demo).execute()
    print("Workflow evidence: " + str(directory / "state.json"), flush=True)
    return 0 if state["status"] == "completed" else (3 if state["status"] == "needs_decision" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
