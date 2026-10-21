#!/usr/bin/env python3
"""Small real-model queue experiment; isolated candidates, never auto-merge."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from agent_workflow import CliAgent, clean_env, digest, dump, stop_group, capture, permission_config, validate_result, ROLE_STATUSES, RESULT_KEYS
from task_queue import Job, TaskQueue

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments/admin-feedback"
ORIGINAL = ROOT / "reference/2026-DAYNOMY-dev/backend/src/main/java/org/grit/daynomy"
ROLES = json.loads((ROOT / "agents/service.json").read_text())["roles"]
STUBS = {
    "list": '#![forbid(unsafe_code)]\npub fn list(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n',
    "detail": '#![forbid(unsafe_code)]\npub fn detail(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (501, serde_json::json!({})) }\n',
}
CONTRACT = """Scope: GET /api/admin/feedbacks and GET /api/admin/feedbacks/{id}, read only.
Implement pure functions feedback_list::list(query:&str, rows:&serde_json::Value)
and feedback_detail::detail(id:&str, rows:&serde_json::Value), returning (u16, Value).
HTTP authentication and DB access are provided separately; do not implement them here.
Input rows is an array with id,content,page_path,status,created_at,updated_at fields.
Output DTO has exactly id,content,pagePath,status,createdAt,updatedAt.
List defaults page=1,size=15; integer32 binding, empty defaults, 1<=page,1<=size<=100.
Sort created_at DESC then id DESC. Timestamps in inputs are UTC ISO8601 strings.
List output exactly items,page,size,totalPages,totalElements,hasNext.
Detail id is an ALREADY percent-decoded UTF-8 path variable supplied by the HTTP adapter.
The adapter decodes exactly once and preserves literal '+' (path encoding, not form encoding).
Do not percent-decode id again. Query input remains the raw URL query; list handles form decoding.
Detail parses signed integer64, validates positive, returns row or FEEDBACK_NOT_FOUND.
Use exact Java errors in reference excerpts. Do not invent new policies.
No web framework, no unsafe. Keep #![forbid(unsafe_code)] in each source/test file.
The harness runs strict cargo clippy -D warnings. Do not add lint allowances.
Use integer.is_multiple_of(n) for integer divisibility and character-array patterns
instead of closures comparing a character against several literals.
"""


def files(directory):
    result = {}
    for p in directory.rglob("*"):
        if p.is_symlink():
            raise ValueError("Symbolic links are not accepted")
        if p.is_file():
            if p.stat().st_nlink != 1:
                raise ValueError("Hard links are not accepted")
            result[str(p.relative_to(directory))] = digest(p)
    return result


def validate_tests(text, feature):
    if not text.startswith("#![forbid(unsafe_code)]"):
        raise ValueError("Tests must forbid unsafe")
    paths = re.findall(r'#\s*\[\s*path\s*=\s*"([^"]+)"\s*\]', text)
    if paths != [f"../src/feedback_{feature}.rs"]:
        raise ValueError("Test must import only its candidate module")
    if len(re.findall(r"#\s*\[\s*test\s*\]", text)) < 3 or "assert" not in text:
        raise ValueError("At least three actual assertion tests required")
    if re.search(r"#\s*\[\s*ignore\b|\bunsafe\b|\buse\s+(?:::)?std\b|std\s*::\s*(fs|net|process|env)\b|\b(include|include_str|include_bytes|env|option_env)\s*!", text):
        raise ValueError("Tests must be pure, unignored assertions")


def _rust_mask(text, strings=False):
    """Mask nested comments (and optionally string literals), preserving offsets."""
    out = list(text)
    i = 0
    while i < len(text):
        end = None
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
        elif text.startswith("/*", i):
            depth, end = 1, i + 2
            while end < len(text) and depth:
                if text.startswith("/*", end):
                    depth += 1
                    end += 2
                elif text.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
        else:
            raw = re.match(r'r(#{0,255})"', text[i:])
            if raw:
                close = '"' + raw[1]
                found = text.find(close, i + raw.end())
                end = len(text) if found < 0 else found + len(close)
                if not strings:
                    i = end
                    continue
            elif text[i] == '"':
                end = i + 1
                while end < len(text):
                    if text[end] == "\\":
                        end += 2
                    elif text[end] == '"':
                        end += 1
                        break
                    else:
                        end += 1
                if not strings:
                    i = end
                    continue
        if end is not None:
            for j in range(i, min(end, len(text))):
                if text[j] != "\n":
                    out[j] = " "
            i = end
        else:
            i += 1
    return "".join(out)


def validate_regression_tests(text, feature):
    """Stricter append-only regression contract: three unconditionally asserted tests."""
    if feature not in STUBS:
        raise ValueError("Unknown regression feature")
    clean = _rust_mask(text)
    validate_tests(clean, feature)
    code = _rust_mask(text, strings=True)
    if re.search(r"#\s*\[\s*(?:cfg|cfg_attr|ignore|should_panic)\b", code):
        raise ValueError("Regression tests must be unconditional and unignored")
    bodies = []
    for match in re.finditer(r"#\s*\[\s*test\s*\]\s*(?:pub\s+)?fn\s+\w+\s*\([^)]*\)[^{]*\{", code):
        start = match.end()
        depth, end = 1, start
        while end < len(code) and depth:
            depth += (code[end] == "{") - (code[end] == "}")
            end += 1
        if depth:
            raise ValueError("Malformed regression test body")
        bodies.append(code[start:end - 1])
    if len(bodies) < 3 or any(not re.search(r"\bassert(?:_eq|_ne)?\s*!", body) for body in bodies):
        raise ValueError("Every regression test requires an actual assertion")


class ResponseArtifactAgent(CliAgent):
    """Single read-only CLI call returning a strict JSON source artifact."""
    def __call__(self, role, workspace, prompt, output_dir):
        output_dir=Path(output_dir)
        # Never replace an earlier call's evidence, including failure records.
        if output_dir.exists():
            raise RuntimeError("Response artifact evidence path must be fresh")
        started=time.monotonic()
        try:
            return self._call(role,workspace,prompt,output_dir)
        except Exception as exc:
            events=output_dir/"events.jsonl"
            sessions=[];usage=None
            if events.is_file() and not events.is_symlink():
                for line in events.read_text(errors="replace").splitlines():
                    try:event=json.loads(line)
                    except ValueError:continue
                    if not isinstance(event,dict):continue
                    if event.get("type")=="thread.started" and isinstance(event.get("thread_id"),str):
                        sessions.append(event["thread_id"])
                    if event.get("type")=="turn.completed" and isinstance(event.get("usage"),dict):
                        usage={key:value for key,value in event["usage"].items()
                               if key in ("input_tokens","cached_input_tokens","output_tokens","total_tokens")
                               and isinstance(value,int) and not isinstance(value,bool) and value>=0}
            timed_out=isinstance(exc,subprocess.TimeoutExpired) or str(exc)=="Agent time limit exceeded"
            metadata={"role":role,"executable":self.executable,"requested_model":self.model,
                      "requested_reasoning_effort":self.reasoning_effort,"budget_seconds":self.timeout,
                      "elapsed_seconds":round(time.monotonic()-started,3),
                      "status":"timeout" if timed_out else "transport_failed","failure_type":type(exc).__name__,
                      "model_selection":"explicit" if self.model else "cli_default","max_attempts":1,
                      "session_id":sessions[0] if len(sessions)==1 else None,"usage":usage,
                      "events":str(events),"artifact_mode":"response","artifact_imported":False}
            output_dir.mkdir(parents=True,exist_ok=True)
            dump(output_dir/"identity.json",metadata)
            dump(output_dir/"execution-result.json",metadata)
            if isinstance(exc,(RuntimeError,subprocess.TimeoutExpired)):
                raise
            raise RuntimeError("Response artifact transport failed") from None

    def _call(self, role, workspace, prompt, output_dir):
        if role not in ("implementer","test_author"):
            raise ValueError("Response artifacts require an implementation or test role")
        output_dir.mkdir(parents=True,exist_ok=False)
        schema={"type":"object","additionalProperties":False,"properties":{
            "status":{"type":"string","enum":sorted(ROLE_STATUSES[role])},
            "summary":{"type":"string"},"findings":{"type":"array","items":{"type":"string"}},
            "questions":{"type":"array","items":{"type":"string"}},"rust_source":{"type":"string"}},
            "required":sorted(RESULT_KEYS|{"rust_source"})}
        schema_path=output_dir/"schema.json";result_path=output_dir/"result.json";events=output_dir/"events.jsonl"
        dump(schema_path,schema)
        command=[self.executable,"-a","never","exec","--ignore-user-config","--ephemeral",
                 "--skip-git-repo-check","-C",str(workspace),"-c",'default_permissions="daynomy_role"',
                 "-c",permission_config("reviewer",workspace),"-c",'web_search="disabled"',
                 "-c","project_doc_max_bytes=0","--json","--color","never",
                 "--output-schema",str(schema_path),"-o",str(result_path)]
        if self.model is not None:
            command += ["--model",self.model]
        if self.reasoning_effort is not None:
            command += ["-c",f'model_reasoning_effort="{self.reasoning_effort}"']
        command += ["-"]
        code=capture(command,prompt,events,self.timeout,clean_env())
        if code!=0 or not result_path.is_file() or result_path.is_symlink() or result_path.stat().st_size>600_000:
            raise RuntimeError("Response artifact CLI failed or missing complete result")
        try:
            result=json.loads(result_path.read_text())
        except ValueError:
            raise RuntimeError("Invalid response artifact JSON") from None
        if not isinstance(result,dict) or set(result)!=RESULT_KEYS|{"rust_source"} or not isinstance(result["rust_source"],str):
            raise RuntimeError("Invalid response artifact JSON")
        source=result.pop("rust_source")
        try:
            verdict=validate_result(result,role)
        except ValueError:
            raise RuntimeError("Invalid response artifact verdict") from None
        if len(source.encode())>100_000:
            raise RuntimeError("Oversized response artifact")
        sessions=[];usage=None
        for line in events.read_text().splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if not isinstance(event,dict):continue
            if event.get("type")=="thread.started":sessions.append(event.get("thread_id"))
            if event.get("type")=="turn.completed":usage=event.get("usage")
        if len(sessions)!=1 or not isinstance(sessions[0],str):
            raise RuntimeError("Missing unique agent session identity")
        return {**verdict,"rust_source":source},{"session_id":sessions[0],"role":role,"exit_code":code,
            "requested_model":self.model,"requested_reasoning_effort":self.reasoning_effort,
            "model_selection":"explicit" if self.model else "cli_default","executable":self.executable,
            "result":str(result_path),"events":str(events),"usage":usage,"artifact_mode":"response",
            "attempts":[{"attempt":1,"exit_code":code,"events":str(events)}]}


def compact_oracle(evidence, feature, canonical_sha256):
    """Lossless feature projection; full canonical evidence remains authoritative."""
    if feature not in STUBS:
        raise ValueError("Unknown oracle feature")
    def value_sha(value):
        return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    fixtures,responses,cases={},{},[]
    for index,case in enumerate(evidence["oracle_cases"]):
        actual_feature="detail" if case["path"].split("?")[0].startswith("/api/admin/feedbacks/") else "list"
        if actual_feature!=feature:
            continue
        fixture=case.get("fixture","baseline")
        rows=case["input_rows"]
        row_sha=value_sha(rows)
        if fixture in fixtures and fixtures[fixture]["sha256"]!=row_sha:
            raise ValueError("Oracle fixture label has inconsistent rows")
        fixtures[fixture]={"sha256":row_sha,"input_rows":rows}
        response_sha=value_sha(case["body"])
        responses[response_sha]=case["body"]
        cases.append({"canonical_index":index,"name":case["name"],"path":case["path"],
                      "principal":case["principal"],"status":case["status"],"fixture":fixture,"response_ref":response_sha})
    return {"canonical_file":"original-http-evidence.json","canonical_sha256":canonical_sha256,
            "oracle_version":evidence["oracle_version"],"feature":feature,"cases":cases,
            "fixtures":fixtures,"responses":responses}


class Experiment:
    def __init__(self, directory, slots, timeout, executable="codex", contract_version="v1", agent_timeout=240, artifact_mode="files"):
        if artifact_mode not in ("files","response"):
            raise ValueError("Unknown artifact mode")
        self.artifact_mode=artifact_mode
        if not 0<agent_timeout<=300:
            raise ValueError("Agent timeout must be positive and at most 300 seconds")
        self.agent_timeout=agent_timeout
        if contract_version not in ("v1","v2"):
            raise ValueError("Unknown contract version")
        self.contract_version=contract_version
        self.oracle_path=None
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.candidate = self.directory / "candidate"
        shutil.copytree(BASE, self.candidate)
        shutil.rmtree(self.candidate / "tests")
        (self.candidate / "tests").mkdir()
        for feature, stub in STUBS.items():
            (self.candidate / f"src/feedback_{feature}.rs").write_text(stub)
        refs = ["feedback/controller/AdminFeedbackController.java", "feedback/service/FeedbackService.java",
                "feedback/dto/AdminFeedbackPageResponse.java", "feedback/dto/AdminFeedbackResponse.java",
                "feedback/exception/FeedbackErrorCode.java", "common/exception/GlobalExceptionHandler.java",
                "common/exception/CommonErrorCode.java", "common/response/ErrorResponse.java",
                "common/response/ValidationErrorField.java"]
        self.reference = "\n\n".join("SOURCE " + p + "\n" + (ORIGINAL / p).read_text() for p in refs)
        (self.directory / "contract.txt").write_text(CONTRACT + "\n" + self.reference)
        dump(self.directory/"criteria.json",{"case_sha256":digest(BASE/"tests/cases.json"),
             **({"contract_version":"v2","oracle_status":"pending"} if contract_version=="v2" else {})})
        self.trusted = {str(p): digest(p) for p in BASE.rglob("*") if p.is_file()}
        self.trusted.update({str(ORIGINAL / p): digest(ORIGINAL / p) for p in refs})
        if (self.candidate/"src/main.rs").is_file():
            dump(self.directory/"scaffold-contract.json",{
                "version":"admin-feedback-decoded-path-v2","sha256":digest(self.candidate/"src/main.rs"),
                "detail_input":"UTF-8 path variable percent-decoded exactly once; literal + preserved",
                "query_input":"raw URL query; function performs form decoding"})
            self.trusted[str(self.directory/"scaffold-contract.json")]=digest(self.directory/"scaffold-contract.json")
        self.backend_failed = threading.Event()
        self.slots, self.timeout = slots, timeout
        self.executable = str(executable)
        self.target = self.directory / "target"  # never reuse another candidate's binary
        self.env = clean_env()
        self.env.update(CARGO_HOME=str(ROOT / ".local/cargo"), CARGO_NET_OFFLINE="true",
                        CARGO_TARGET_DIR=str(self.target),
                        CARGO_TARGET_AARCH64_APPLE_DARWIN_RUNNER=f"python3 {ROOT / 'scripts/readonly_runner.py'}")
        self.lock = threading.Lock()
        self.generated = {}
        self.pending_test_revisions = {}
        self.previous_review_revisions = {}
        self.frozen_tests = {}
        self.regression_artifacts = {}
        self._verified_regression_checks = {}
        spec = ROOT / "spec/service.md"
        self.full_spec = spec.read_text() if spec.is_file() else CONTRACT

    def bind_oracle(self, path, expected_sha=None):
        from admin_feedback_gate import validate_oracle
        path=Path(path)
        if expected_sha is not None and digest(path)!=expected_sha:
            raise ValueError("Frozen original HTTP evidence changed")
        evidence=json.loads(path.read_text())
        validate_oracle(evidence,digest(BASE/"tests/cases.json"))
        destination=self.directory/"original-http-evidence.json"
        if path.resolve()!=destination.resolve():
            shutil.copyfile(path,destination)
        self.oracle_path=destination
        self.contract_version="v2"
        self.trusted[str(destination)]=digest(destination)
        dump(self.directory/"criteria.json",{"contract_version":"v2","case_sha256":digest(BASE/"tests/cases.json"),
             "oracle_sha256":digest(destination),"oracle_version":evidence["oracle_version"],
             "spring_jar_sha256":evidence["spring_jar_sha256"],"original_snapshot_sha256":evidence["original_snapshot_sha256"]})
        self.trusted[str(self.directory/"criteria.json")]=digest(self.directory/"criteria.json")

    def prepare_oracle(self):
        from admin_feedback_gate import run_oracle
        started=time.monotonic()
        result=run_oracle(self.directory/"original-oracle",timeout_seconds=self.timeout)
        self.timeout=max(0,self.timeout-(time.monotonic()-started))
        if result.get("status")!="passed":
            raise ValueError("Original HTTP oracle preflight failed; no model tasks dispatched")
        self.bind_oracle(self.directory/"original-oracle/result.json")

    def integrity(self):
        if any(digest(Path(p)) != sha for p, sha in self.trusted.items()):
            raise ValueError("Frozen reference or baseline changed")
        if any(digest(self.candidate / p) != sha for p, sha in self.frozen_tests.items()):
            raise ValueError("Frozen original tests changed")

    def command(self, name, args, deadline, allowed=(0,)):
        if time.monotonic() >= deadline:
            raise RuntimeError("Command deadline reached: " + name)
        log = self.directory / (name + ".log")
        with log.open("w") as handle:
            process = subprocess.Popen(args, cwd=self.candidate, env=self.env,
                                       stdout=handle, stderr=handle, start_new_session=True)
            try:
                code = process.wait(timeout=max(.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                stop_group(process)
                raise RuntimeError("Command deadline reached: " + name)
            finally:
                stop_group(process)
        if code not in allowed:
            raise RuntimeError("Command failed: " + name + "; see " + str(log))
        return {"name": name, "exit_code": code, "log": str(log)}

    def agent(self, job, deadline):
        if job.id.startswith("test-regression-"):
            role, feature = "test-regression", job.id.removeprefix("test-regression-")
        else:
            role, feature = job.id.split("-", 1)
        if feature not in STUBS or role not in ("implement", "repair", "test", "test-regression", "review"):
            raise ValueError("Unknown agent task")
        if role=="review" and self.pending_test_revisions:
            return {"status":"needs_test_revision", "reason":"Frozen tests have unresolved review requests; source-only repair cannot close them", "report":str(self.directory/"pending-test-revisions.json")}
        if self.backend_failed.is_set():
            return {"status": "blocked", "reason": "model_backend_unavailable"}
        self.integrity()
        if self.contract_version=="v2" and self.oracle_path is None:
            raise ValueError("Original HTTP evidence required before model dispatch")
        worker = self.directory / job.id
        worker.mkdir()
        (worker / "reference.txt").write_text(CONTRACT + "\n" + self.reference)
        if role in ("implement", "repair"):
            relative = f"feedback_{feature}.rs"
            (worker / relative).write_text((self.candidate / f"src/{relative}").read_text() if role == "repair" else STUBS[feature])
            prompt = f"Implement ONLY {relative} in this workspace from reference.txt. Pure {feature} function signature is in the contract. Do not read other implementations/tests or modify other paths. Do not run Cargo. No unsafe/framework. Return implemented only after writing the file."
            if role == "repair":
                (worker / "check-findings.txt").write_text(self.repair_notes)
                prompt += " This is a bounded repair of the existing implementation. Read check-findings.txt and fix the reported compiler/lint/test problem without weakening behavior or adding lint allowances. The independent tests are frozen. Final checks include cargo clippy -D warnings (except unused scaffold dead_code)."
            cli_role, config = "implementer", ROLES["implementer"]
        elif role == "test-regression":
            findings = list(self.pending_test_revisions.get(feature, []))
            if not findings:
                raise ValueError("No pending regression request")
            relative = self.regression_filename(feature)
            original_test = self.candidate / f"tests/feedback_{feature}_contract.rs"
            frozen_hash = self.frozen_tests.get(f"tests/feedback_{feature}_contract.rs")
            if frozen_hash is None or digest(original_test) != frozen_hash:
                raise ValueError("Original tests must be frozen before regression authoring")
            shutil.copyfile(original_test, worker / "frozen-original-tests.rs")
            (worker / "spec.md").write_text(self.full_spec)
            dump(worker / "review-findings.json", {"feature": feature, "findings": findings})
            prompt = f"Write ONLY {relative}, an ADDITIONAL independent regression test module for {feature}. Read reference.txt, spec.md, review-findings.json and frozen-original-tests.rs. Do not read any implementation or other workspace. Preserve every original test; do not edit provided inputs. Cover ALL review findings with at least three unconditional #[test] functions, each with actual assert!/assert_eq!/assert_ne!. Start #![forbid(unsafe_code)] then #[path=\"../src/feedback_{feature}.rs\"] mod subject;. Pure serde_json/std assertions only; no file/network/process/env I/O, include macros, ignored/cfg/should_panic tests, unsafe, or external commands. Do not run Cargo. Return tests_written only after writing this one file."
            cli_role, config = "test_author", ROLES["test_author"]
        elif role == "test":
            relative = f"feedback_{feature}_contract.rs"
            prompt = f"Write ONLY {relative}: >=3 Rust #[test] functions using assertions against {feature}, from reference.txt, without reading any implementation or existing tests. The file will be installed into tests/; start #![forbid(unsafe_code)], then #[path=\"../src/feedback_{feature}.rs\"] mod subject;. Use serde_json fixture rows. Check normal DTO, empty/not found, malformed input, and boundary behavior where supported by source. Pure assertions; no file/network/process/env I/O or includes or ignored tests. Do not run Cargo. Return tests_written after writing."
            cli_role, config = "test_author", ROLES["test_author"]
        else:
            relative = None
            shutil.copytree(self.candidate, worker / "candidate")
            shutil.copyfile(self.directory / "verification.json", worker / "verification.json")
            dump(worker/"previous-review.json",self.previous_review_revisions)
            prompt = f"Read-only independent review of candidate/src/feedback_{feature}.rs, candidate/tests/feedback_{feature}_contract.rs, reference.txt and verification.json. Check exact original contract and missing cases. Do not modify files. approve only when concrete evidence supports it, otherwise revise with specific findings. No deployment/fullservice claim."
            prompt += f" Read previous-review.json and verify prior findings are resolved. Inspect ALL candidate/tests/feedback_{feature}_regression*.rs additions together with unchanged contract tests and verification regression_checks; append-only regressions can resolve prior missing-coverage findings. Prefix findings about tests with TEST_REVISION, and implementation findings with CODE_REVISION."
            cli_role, config = "reviewer", ROLES["critical_reviewer"]
        if self.oracle_path is not None:
            shutil.copyfile(self.oracle_path,worker/"original-http-evidence.json")
            (worker/"original-http-summary.json").write_text(json.dumps(
                compact_oracle(json.loads(self.oracle_path.read_text()),feature,digest(self.oracle_path)),
                ensure_ascii=False,separators=(",",":"))+"\n")
            prompt += " Read original-http-summary.json BEFORE writing or reviewing. It is a lossless feature-filtered projection with fixtures and response bodies deduplicated; cases identify canonical indices and body references. The complete immutable original-http-evidence.json is available for deeper inspection and bound by canonical_sha256. The summary records actual original HTTP requests, responses and input_rows from synthetic fixtures. Use its observed numeric binding and timestamp behavior, including rejected +0x1 and +#1; do not guess Java parsing. Preserve all v1 tests. These observations supplement source, and do not replace independent tests, red/green checks or review."
        response_mode=self.artifact_mode=="response" and cli_role!="reviewer"
        if response_mode:
            prompt += " RESPONSE ARTIFACT MODE overrides file-writing instructions above: do not edit files or run tools/commands. Return the COMPLETE Rust source verbatim as JSON string rust_source together with status,summary,findings,questions. No markdown fences, placeholders, patches, omitted code, or path fields. The harness alone validates and installs the expected artifact. All primary inputs follow inline."
            for name in ("reference.txt","original-http-summary.json","check-findings.txt","review-findings.json","frozen-original-tests.rs","spec.md"):
                if (worker/name).is_file():
                    prompt += "\nINLINE INPUT "+name+"\n"+(worker/name).read_text()
            if role=="repair":
                prompt += "\nEXISTING OWNED SOURCE\n"+(worker/relative).read_text()
        baseline = files(worker)
        budget=min(self.agent_timeout,max(.1,deadline-time.monotonic()))
        evidence_dir=self.directory/(job.id+"-evidence")
        execution={"role":cli_role,"executable":self.executable,"requested_model":config["model"],
                   "requested_reasoning_effort":config["reasoning_effort"],"budget_seconds":budget,
                   "max_attempts":1,"artifact_mode":"response" if response_mode else "files","model_selection":"explicit" if config["model"] else "cli_default"}
        dump(self.directory / (job.id + "-dispatch.json"), {"role": cli_role, **config,**execution})
        invoked=time.monotonic()
        try:
            verdict, identity = (ResponseArtifactAgent if response_mode else CliAgent)(timeout=budget,
                model=config["model"], reasoning_effort=config["reasoning_effort"], max_attempts=1, executable=self.executable)(
                    cli_role, worker, prompt, evidence_dir)
        except (RuntimeError,subprocess.TimeoutExpired) as exc:
            self.backend_failed.set()
            timed_out=isinstance(exc,subprocess.TimeoutExpired) or str(exc)=="Agent time limit exceeded"
            events=evidence_dir/"events.jsonl"
            session_ids=[]
            if events.is_file():
                for line in events.read_text().splitlines():
                    try:
                        event=json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type")=="thread.started" and isinstance(event.get("thread_id"),str):
                        session_ids.append(event["thread_id"])
            metadata={**execution,"status":"timeout" if timed_out else "transport_failed",
                      "elapsed_seconds":round(time.monotonic()-invoked,3),
                      "session_id":session_ids[0] if len(session_ids)==1 else None,
                      "events":str(events),"usage":None,"artifact_imported":False}
            evidence_dir.mkdir(exist_ok=True)
            if response_mode and (evidence_dir/"execution-result.json").is_file():
                transport_metadata=json.loads((evidence_dir/"execution-result.json").read_text())
                metadata.update({key:transport_metadata[key] for key in ("session_id","usage","failure_type","elapsed_seconds") if key in transport_metadata})
            dump(evidence_dir/"identity.json",metadata)
            dump(evidence_dir/"execution-result.json",metadata)
            return {"status":"blocked","reason":"model_timeout" if timed_out else "model_transport_failed",
                    "evidence":str(evidence_dir),"identity":metadata}
        actual = files(worker)
        protected = set(baseline) - ({relative} if relative and not response_mode else set())
        if any(actual.get(p) != baseline[p] for p in protected) or set(actual)-set(baseline)-({relative} if relative else set()):
            raise ValueError("Worker modified protected inputs")
        expected = {"implementer":"implemented", "test_author":"tests_written", "reviewer":"approve"}[cli_role]
        if verdict["status"] != expected:
            return {"status":"failed", "verdict":verdict, "identity":identity}
        if response_mode:
            source=verdict.pop("rust_source",None)
            if not isinstance(source,str) or not source or len(source.encode())>100_000:
                raise ValueError("Missing complete response artifact")
            if role in ("test","test-regression"):
                (validate_regression_tests if role=="test-regression" else validate_tests)(source,feature)
            elif not source.startswith("#![forbid(unsafe_code)]"):
                raise ValueError("Implementation must forbid unsafe")
            (worker/relative).write_text(source)
        if relative:
            path = worker / relative
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 100_000:
                raise ValueError("Missing or oversized worker artifact")
            text = path.read_text()
            if role in ("test", "test-regression"):
                (validate_regression_tests if role == "test-regression" else validate_tests)(text, feature)
            elif not text.startswith("#![forbid(unsafe_code)]"):
                raise ValueError("Implementation must forbid unsafe")
            destination = self.candidate / (f"src/feedback_{feature}.rs" if role in ("implement", "repair") else f"tests/{relative}")
            with self.lock:
                if role == "test-regression" and destination.exists():
                    raise ValueError("Additional regression tests cannot replace existing tests")
                key = str(destination.relative_to(self.candidate))
                if role == "test" and key in self.frozen_tests and digest(path) != self.frozen_tests[key]:
                    raise ValueError("Original test criteria cannot be replaced")
                shutil.copyfile(path, destination)
                key = str(destination.relative_to(self.candidate))
                self.generated[key] = digest(destination)
                if role == "test":
                    self.frozen_tests[key] = self.generated[key]
                if role == "test-regression":
                    self.regression_artifacts[feature] = {"path": key, "sha256": self.generated[key],
                        "findings": findings, "identity": identity}
                    dump(self.directory / "regression-artifacts.json", self.regression_artifacts)
                dump(self.directory/"artifacts.json",self.generated)
        self.integrity()
        return {"status":"completed", "identity":identity, "verdict":verdict}

    def regression_filename(self, feature):
        if feature not in STUBS:
            raise ValueError("Unknown regression feature")
        name = f"feedback_{feature}_regression.rs"
        number = 2
        while (self.candidate / "tests" / name).exists():
            name = f"feedback_{feature}_regression_{number}.rs"
            number += 1
        return name

    def regression_covers_pending(self, feature):
        artifact = self.regression_artifacts.get(feature)
        if not artifact:
            return False
        if not re.fullmatch(rf"tests/feedback_{re.escape(feature)}_regression(?:_\d+)?\.rs", artifact.get("path", "")):
            return False
        path = self.candidate / artifact["path"]
        return (path.is_file() and not path.is_symlink()
                and digest(path) == artifact.get("sha256")
                and set(artifact.get("findings", [])) >= set(self.pending_test_revisions.get(feature, [])))

    def clear_test_revisions(self, checks, *, final_checks_passed=False):
        """Only this run's complete verification receipts may resolve author requests."""
        if not final_checks_passed:
            return
        if any(not (self.candidate / p).is_file() or digest(self.candidate / p) != sha
               for p, sha in self.frozen_tests.items()):
            return
        for feature in list(self.pending_test_revisions):
            receipt = checks.get(feature)
            if (not receipt or receipt != self._verified_regression_checks.get(feature)
                    or receipt.get("red") is not True or receipt.get("green") is not True
                    or not self.regression_covers_pending(feature)
                    or receipt.get("sha256") != self.regression_artifacts[feature]["sha256"]):
                continue
            del self.pending_test_revisions[feature]
        dump(self.directory / "pending-test-revisions.json", self.pending_test_revisions)

    def verify(self, deadline):
        from admin_feedback_gate import run_gate
        self._verified_regression_checks = {}
        self.integrity()
        original = {f:(self.candidate/f"src/feedback_{f}.rs").read_text() for f in STUBS}
        targets = [(feature, f"feedback_{feature}_contract", feature) for feature in STUBS]
        for path in sorted((self.candidate / "tests").glob("*.rs")):
            match = re.fullmatch(r"feedback_(list|detail)_regression(?:_(\d+))?\.rs", path.name)
            if not match:
                if path.name not in {f"feedback_{f}_contract.rs" for f in STUBS}:
                    raise ValueError("Unexpected test module")
                continue
            feature = match[1]
            validate_regression_tests(path.read_text(), feature)
            key = str(path.relative_to(self.candidate))
            if self.generated.get(key) != digest(path):
                raise ValueError("Regression test artifact is not frozen")
            targets.append((feature, path.stem, path.stem.removeprefix("feedback_").replace("_", "-")))
        commands, receipts = [], {}
        try:
            for feature in STUBS:
                (self.candidate/f"src/feedback_{feature}.rs").write_text(STUBS[feature])
            for feature, target, label in targets:
                name = f"red-{label}"
                evidence = self.command(name, ["cargo","test","--locked","--offline","--test",target], deadline, allowed=(101,))
                commands.append(evidence)
                red = (self.directory / (name + ".log")).read_text()
                summary = re.search(r"test result: FAILED\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out", red)
                if (evidence.get("exit_code") != 101 or not summary or int(summary[2]) < 1
                        or int(summary[1]) + int(summary[2]) < 3 or any(int(summary[n]) for n in (3,4,5))):
                    raise ValueError("Stub rejection not established by actual test failures")
                receipts[target] = {"red": True}
        finally:
            for feature,text in original.items():
                (self.candidate/f"src/feedback_{feature}.rs").write_text(text)
        for feature, target, label in targets:
            name = f"unit-{label}"
            evidence = self.command(name, ["cargo","test","--locked","--offline","--test",target], deadline)
            commands.append(evidence)
            text = (self.directory / (name + ".log")).read_text()
            summary = re.search(r"test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out",text)
            if evidence.get("exit_code") != 0 or not summary or int(summary[1]) < 3 or any(int(summary[n]) for n in (2,3,4,5)):
                raise ValueError("Missing real unignored feature tests")
            receipts[target]["green"] = True
        for name,args in [("scaffold-unit", ["cargo","test","--locked","--offline","--bin","daynomy-admin-feedback-bench"]),
                          ("build", ["cargo","build","--locked","--offline"]),
                          ("clippy", ["cargo","clippy","--locked","--offline","--all-targets","--","-D","warnings","-A","dead_code"])]:
            evidence = self.command(name, args, deadline)
            commands.append(evidence)
            if evidence.get("exit_code") != 0:
                raise ValueError("Build or Clippy did not succeed")
        result = run_gate(self.candidate,self.directory/"http",self.target,timeout_seconds=max(.1,deadline-time.monotonic()),
                          **({"oracle_path":self.oracle_path} if self.oracle_path else {}))
        if self.oracle_path and result.get("oracle_sha256")!=digest(self.oracle_path):
            raise ValueError("Frozen original HTTP evidence changed during checks")
        self.integrity()
        if any(digest(self.candidate/p) != sha for p,sha in self.generated.items()):
            raise ValueError("Generated code/tests changed during checks")
        if result.get("case_sha256") != digest(BASE / "tests/cases.json"):
            raise ValueError("Frozen HTTP criteria changed during checks")
        passed = result.get("status") == "passed"
        if passed:
            for feature, artifact in self.regression_artifacts.items():
                receipt = receipts.get(Path(artifact["path"]).stem)
                if receipt and self.regression_covers_pending(feature):
                    self._verified_regression_checks[feature] = {**receipt, "sha256": artifact["sha256"]}
        evidence = {"status":result["status"],"commands":commands,"http":result,"generated_hashes":self.generated,
                    "regression_checks":self._verified_regression_checks}
        dump(self.directory/"verification.json",evidence)
        self.clear_test_revisions(self._verified_regression_checks, final_checks_passed=passed)
        return {"status":"completed" if passed else "failed", "report":str(self.directory/"verification.json")}

    def run(self):
        if self.contract_version=="v2":
            try:
                self.prepare_oracle()
            except ValueError:
                blocked={"status":"blocked","reason":"original_http_oracle_preflight_failed",
                         "report":str(self.directory/"original-oracle/result.json"),"tasks":{},"metrics":{}}
                dump(self.directory/"preflight-result.json",blocked)
                return blocked
        initial=[Job(f"{role}-{feature}","agent") for role,feature in
                 (("implement","list"),("test","list"),("implement","detail"),("test","detail"))]
        jobs=initial+[Job("verify","check",tuple(j.id for j in initial))]+[
            Job(f"review-{feature}","agent",("verify",)) for feature in STUBS]
        def execute(job,deadline):
            return self.verify(deadline) if job.kind=="check" else self.agent(job,deadline)
        return TaskQueue(jobs,execute,self.directory/"queue",agent_slots=self.slots,timeout_seconds=self.timeout).run()

    def repair_once(self, parent):
        """Reuse exact failed artifacts; fresh model repair, unchanged test criteria."""
        parent=Path(parent).resolve()
        state=json.loads((parent/"queue/state.json").read_text())
        review_revisions={name.split("-",1)[1]:task["result"]["verdict"] for name,task in state["tasks"].items()
                          if name.startswith("review-") and task.get("result") and task["result"].get("verdict",{}).get("status")=="revise"}
        if state["status"]!="failed" or (state["tasks"]["verify"]["status"]!="failed" and not review_revisions):
            raise ValueError("Only a failed actual check can start recovery")
        pending_path=parent/"pending-test-revisions.json"
        self.pending_test_revisions=json.loads(pending_path.read_text()) if pending_path.is_file() else {}
        for feature,verdict in review_revisions.items():
            pending=[finding for finding in verdict["findings"] if "TEST_REVISION" in finding or re.search(r"\btests/",finding)]
            if pending:
                self.pending_test_revisions[feature]=sorted(set(self.pending_test_revisions.get(feature,[])+pending))
        previous_path = parent / "previous-review-revisions.json"
        self.previous_review_revisions = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
        self.previous_review_revisions.update(review_revisions)
        dump(self.directory / "previous-review-revisions.json", self.previous_review_revisions)
        dump(self.directory/"pending-test-revisions.json",self.pending_test_revisions)
        prior_verification=parent/"verification.json"
        verified=json.loads(prior_verification.read_text()) if prior_verification.is_file() else None
        previous_scaffold=(verified or {}).get("http",{}).get("source_hashes",{}).get("src/main.rs")
        if previous_scaffold is not None and (digest(self.candidate/"src/main.rs")!=previous_scaffold
                or digest(parent/"candidate/src/main.rs")!=previous_scaffold):
            raise ValueError("HTTP scaffold differs from verified parent; start a fresh versioned experiment instead of rebasing frozen criteria")
        artifact_path=parent/"artifacts.json"
        artifacts=json.loads(artifact_path.read_text()) if artifact_path.is_file() else None
        criteria_path=parent/"criteria.json"
        criteria=json.loads(criteria_path.read_text()) if criteria_path.is_file() else {}
        if criteria.get("contract_version","v1")=="v2":
            self.bind_oracle(parent/"original-http-evidence.json",criteria["oracle_sha256"])
            copied=json.loads((self.directory/"criteria.json").read_text())
            if copied!=criteria:
                raise ValueError("Frozen v2 criteria changed between phases")
        else:
            self.contract_version="v1"
            dump(self.directory/"criteria.json",{"case_sha256":digest(BASE/"tests/cases.json")})
        previous_case=(verified["http"].get("case_sha256") if verified is not None else
                       json.loads(criteria_path.read_text())["case_sha256"] if criteria_path.is_file() else None)
        if (verified is not None and previous_case is None) or (previous_case is not None and previous_case!=digest(BASE/"tests/cases.json")):
            raise ValueError("Frozen HTTP criteria changed between phases")
        for role in ("implement","test"):
            for feature in STUBS:
                if verified is None and artifacts is None and state["tasks"][f"{role}-{feature}"]["status"]!="completed":
                    raise ValueError("Failed model transport cannot start code repair")
                relative=f"feedback_{feature}.rs" if role=="implement" else f"feedback_{feature}_contract.rs"
                candidate=parent/"candidate"/(f"src/{relative}" if role=="implement" else f"tests/{relative}")
                source=parent/f"{role}-{feature}"/relative if verified is None and artifacts is None else candidate
                known=artifacts if artifacts is not None else verified["generated_hashes"] if verified is not None else None
                expected=digest(source) if known is None else known[str(candidate.relative_to(parent/"candidate"))]
                if expected!=digest(candidate):
                    raise ValueError("Parent artifacts changed after import")
                if role=="test":
                    validate_tests(source.read_text(),feature)
                destination=self.candidate/candidate.relative_to(parent/"candidate")
                shutil.copyfile(source,destination)
                key = str(destination.relative_to(self.candidate))
                self.generated[key] = digest(destination)
                if role == "test":
                    self.frozen_tests[key] = self.generated[key]
        # Prior regression modules are immutable too; import every manifest-bound
        # addition, even when the next repair only changes implementation code.
        known = artifacts if artifacts is not None else verified["generated_hashes"] if verified is not None else {}
        for key, sha in known.items():
            match = re.fullmatch(r"tests/feedback_(list|detail)_regression(?:_(\d+))?\.rs", key)
            if not match:
                if key not in {f"src/feedback_{f}.rs" for f in STUBS} | {f"tests/feedback_{f}_contract.rs" for f in STUBS}:
                    raise ValueError("Unexpected parent artifact")
                continue
            source = parent / "candidate" / key
            if source.is_symlink() or digest(source) != sha:
                raise ValueError("Parent regression tests changed after import")
            validate_regression_tests(source.read_text(), match[1])
            shutil.copyfile(source, self.candidate / key)
            self.generated[key] = sha
        regression_manifest = parent / "regression-artifacts.json"
        self.regression_artifacts = json.loads(regression_manifest.read_text()) if regression_manifest.is_file() else {}
        for feature, artifact in self.regression_artifacts.items():
            if feature not in STUBS or not self.regression_covers_pending(feature):
                # New findings may exceed coverage, but a corrupted artifact is
                # never repaired by silently discarding its frozen test module.
                key = artifact.get("path", "")
                if (feature not in STUBS
                        or not re.fullmatch(rf"tests/feedback_{re.escape(feature)}_regression(?:_\d+)?\.rs", key)
                        or self.generated.get(key) != artifact.get("sha256")):
                    raise ValueError("Invalid regression author artifact")
        dump(self.directory / "regression-artifacts.json", self.regression_artifacts)
        logs=[p.read_text() for p in parent.glob("*.log")]
        self.repair_notes="\n".join(logs)[-24000:]
        features=set(re.findall(r"src/feedback_(list|detail)\.rs",self.repair_notes))
        for feature, verdict in review_revisions.items():
            if any("TEST_REVISION" not in finding and not re.search(r"\btests/", finding)
                   for finding in verdict.get("findings", [])):
                features.add(feature)
        if review_revisions:
            self.repair_notes+="\nRead-only reviewer revisions:\n"+json.dumps(review_revisions,ensure_ascii=False)
        if verified is not None:
            failed={row["case"] for row in verified["http"]["results"] if not row["passed"]}
            for case in (json.loads(self.oracle_path.read_text())["oracle_cases"] if self.oracle_path else json.loads((BASE/"tests/cases.json").read_text())):
                if case["name"] in failed:
                    features.add("detail" if case["path"].split("?")[0].startswith("/api/admin/feedbacks/") else "list")
            self.repair_notes+="\nActual frozen HTTP failures:\n"+json.dumps([r for r in verified["http"]["results"] if not r["passed"]],ensure_ascii=False)
            self.repair_notes+="\nUse the newly included CommonErrorCode, ErrorResponse and ValidationErrorField sources for exact message/field presence. Do not infer messages from the status alone."
        features=sorted(features)
        if any(feature not in STUBS for feature in set(features) | set(self.pending_test_revisions)):
            raise ValueError("Unknown revision feature")
        if not features and not self.pending_test_revisions:
            raise ValueError("Failure cannot be assigned to implementation files or test revisions")
        dump(self.directory/"recovery.json",{"parent":str(parent),"features":features,"test_revision_features":sorted(self.pending_test_revisions),"frozen_tests":{p:h for p,h in self.generated.items() if p.startswith("tests/")},"note":"Separate recovery run; not included in initial preparation timing."})
        dump(self.directory/"artifacts.json",self.generated)
        repairs=[Job(f"repair-{feature}","agent") for feature in features]
        authors=[Job(f"test-regression-{feature}", "agent", priority=0)
                 for feature in sorted(self.pending_test_revisions)
                 if not self.regression_covers_pending(feature)]
        jobs=authors+repairs+[Job("verify","check",tuple(j.id for j in authors+repairs))]+[
            Job(f"review-{feature}","agent",("verify",)) for feature in STUBS]
        def execute(job,deadline):
            return self.verify(deadline) if job.kind=="check" else self.agent(job,deadline)
        return TaskQueue(jobs,execute,self.directory/"queue",agent_slots=self.slots,timeout_seconds=self.timeout).run()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-version",choices=("v1","v2"),default="v2",help="Fresh runs default to original HTTP oracle v2; recovery inherits its parent")
    parser.add_argument("--slots",type=int,choices=(1,3))
    parser.add_argument("--timeout",type=float,default=600)
    parser.add_argument("--artifact-mode",choices=("files","response"),default="files",help="Opt-in strict JSON Rust artifacts for implementers/test authors; reviewers remain read-only")
    parser.add_argument("--agent-timeout",type=float,default=240,help="Per CLI call seconds, positive and at most 300; whole experiment deadline still applies")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--codex",default="codex",help="Explicit installed CLI executable; does not change model")
    parser.add_argument("--repair-from",type=Path,help="One bounded recovery from a failed check; keeps tests fixed")
    parser.add_argument("--max-repairs",type=int,choices=(0,1,2),default=2)
    args=parser.parse_args()
    if not 0<args.agent_timeout<=300:
        parser.error("--agent-timeout must be positive and at most 300")
    directory=args.output or ROOT/".local/task-queue"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory.mkdir(parents=True,exist_ok=False)
    dump(directory/"execution.json", {"executable":args.codex,"models":ROLES,"requested_contract_version":args.contract_version,"agent_timeout":args.agent_timeout,"artifact_mode":args.artifact_mode,"started_at":datetime.now(timezone.utc).isoformat()})
    results=[]
    for slots in ([args.slots or 3] if args.repair_from else [args.slots] if args.slots else [1,3]):
        started=time.monotonic()
        experiment=Experiment(directory/f"slots-{slots}",slots,args.timeout,executable=args.codex,contract_version=args.contract_version,agent_timeout=args.agent_timeout,artifact_mode=args.artifact_mode)
        result=experiment.repair_once(args.repair_from) if args.repair_from else experiment.run()
        phases=[{"directory":str(experiment.directory),"status":result["status"],"metrics":result["metrics"]}]
        for attempt in range(1,args.max_repairs+1):
            tasks=result["tasks"]
            needs_repair=tasks.get("verify",{}).get("status")=="failed" or any(
                name.startswith("review-") and task.get("result") and task["result"].get("verdict",{}).get("status")=="revise"
                for name,task in tasks.items())
            remaining=args.timeout-(time.monotonic()-started)
            if result["status"]!="failed" or not needs_repair or remaining<=0:
                break
            parent=experiment.directory
            experiment=Experiment(directory/f"slots-{slots}-repair-{attempt}",slots,remaining,executable=args.codex,agent_timeout=args.agent_timeout,artifact_mode=args.artifact_mode)
            result=experiment.repair_once(parent)
            phases.append({"directory":str(experiment.directory),"status":result["status"],"metrics":result["metrics"]})
        results.append({"slots":slots,"status":result["status"],"metrics":result["metrics"],"phases":phases,"total_wall_seconds":time.monotonic()-started})
        dump(directory/"comparison.json",{"runs":results,"note":"Single ordered pair, not a statistically controlled speed benchmark; model/caches vary."})
        print(json.dumps(results[-1]),flush=True)
        if result["status"]!="completed":
            break
    return 0 if all(r["status"]=="completed" for r in results) else 1


if __name__=="__main__":
    raise SystemExit(main())
