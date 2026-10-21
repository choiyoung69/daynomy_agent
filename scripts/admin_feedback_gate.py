"""Serialized live Spring/Rust gate for the frozen admin feedback contracts.

The caller builds the candidate first. Only disposable local databases and signed
synthetic principals are used. Oracle reports include synthetic fixture DTOs only.
Other reports contain no HTTP bodies, tokens,
environment values, database connection strings, or raw subprocess output.
"""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from urllib.parse import quote

import run_comparison as spring
import sample_feature_gate as sample_gate
from sample_feature_gate import normalize

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments/admin-feedback/tests/cases.json"
SPRING_JAR = ROOT / ".local/spring-reference/build/libs/daynomy-0.0.1-SNAPSHOT.jar"
SEED = """
INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES
(941001,'GOOGLE','benchadmin','admin@fixture.invalid','BenchAdmin','ADMIN','ACTIVE',now(),now()),
(941002,'GOOGLE','benchuser','user@fixture.invalid','BenchUser','USER','ACTIVE',now(),now()),
(941003,'GOOGLE','benchgone','gone@fixture.invalid','BenchGone','ADMIN','WITHDRAWN',now(),now());
INSERT INTO feedbacks(id,content,page_path,status,created_at,updated_at) VALUES
(941001,'fixture one','/a','PENDING','2026-08-18 10:00Z','2026-08-18 10:00Z'),
(941002,'fixture two','/b','RESOLVED','2026-08-18 10:00Z','2026-08-18 10:00Z'),
(941003,'fixture three','/c','RESOLVED','2026-08-17 09:00Z','2026-08-17 09:00Z');
"""


# v1 criteria remain byte-for-byte immutable. These probes carry no guessed
# expectations: a fresh v2 run captures the actual original HTTP contract first.
ORACLE_VERSION = "admin-feedback-original-http-v2"
TIMESTAMP_SEED = """
INSERT INTO feedbacks(id,content,page_path,status,created_at,updated_at) VALUES
(941004,'fixture timestamp 정밀','/time-precision','PENDING','2026-08-18 20:00:00.123456+09','2026-08-18 20:00:01.000001+09'),
(941005,'fixture timestamp adjacent','/time','RESOLVED','2026-08-18 11:00:00.123455Z','2026-08-18 11:00:01Z');
"""

def oracle_requests():
    probes = []
    values = ["1", "+1", "-1", "0", "0x1", "#1", "-0x1", "-#1", "+0x1", "+#1",
              "01", "１", "١", "1 0", "\t1\t", "\u20031\u2003", "\u00a01\u00a0",
              "2147483647", "2147483648", "-2147483648", "-2147483649", "1e2", "1.0", "abc", " ", ""]
    for field in ("page", "size"):
        for index, raw in enumerate(values):
            probes.append(dict(name=f"v2-{field}-{index:02}",path="/api/admin/feedbacks?"+field+"="+quote(raw,safe=""),principal="admin",fixture="baseline"))
    values = ["941001", "+941001", "-1", "0", "0xE5BC9", "#E5BC9", "-0x1", "-#1",
              "+0x1", "+#1", "000941001", "９４１００１", "٩٤١٠٠١", "9 41001", "\t941001\t",
              "\u2003941001\u2003", "\u00a0941001\u00a0", "9223372036854775807", "9223372036854775808",
              "-9223372036854775808", "-9223372036854775809", "1e2", "1.0", "abc"]
    for index, raw in enumerate(values):
        probes.append(dict(name=f"v2-id-{index:02}",path="/api/admin/feedbacks/"+quote(raw,safe=""),principal="admin",fixture="baseline"))
    for index, raw in enumerate(["page=0&size=abc", "page=abc&size=0", "page=0&size=101", "page=-1&size=0",
                                 "page=abc&size=abc", "page=1&page=abc", "page=abc&page=1", "size=2&size=abc"]):
        probes.append(dict(name=f"v2-mixed-{index:02}",path="/api/admin/feedbacks?"+raw,principal="admin",fixture="baseline"))
    for index,path in enumerate(["/api/admin/feedbacks", "/api/admin/feedbacks?page=1&size=2",
                                 "/api/admin/feedbacks/941004", "/api/admin/feedbacks/941005"]):
        probes.append(dict(name=f"v2-timestamp-{index:02}",path=path,principal="admin",fixture="timestamps-v2"))
    return probes


def run_oracle(output: Path, timeout_seconds: float = 120) -> dict:
    started=time.monotonic(); deadline=started+timeout_seconds; output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    result=dict(status="blocked",mode="oracle",oracle_version=ORACLE_VERSION,results=[],oracle_cases=[],
                source_hashes={},binary_sha256=None,case_sha256=None,commands=[],elapsed_seconds=0,
                report=str(output/"result.json"),
                known_original_behaviors=[{"case":"v2-page-17","status":500,
                    "evidence":"20261021T064712Z original oracle",
                    "scope":"Exact sanitized INTERNAL_SERVER_ERROR for page=2147483647 only"}])
    try:
        with _deadline_gate_lock(deadline):
            _run(None,output,None,deadline,result)
    except TimeoutError:
        result.update(status="blocked",reason="lock-timeout")
    except Exception as exc:
        result.update(status="blocked",reason="oracle: "+type(exc).__name__)
    result["elapsed_seconds"]=round(time.monotonic()-started,3)
    (output/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    return result


# Observed in the first native v2 oracle (20261021T064712Z). The valid i32
# maximum page produces an original server error; retain its sanitized
# response as a compatibility observation, not a blanket allowance for 5xx.
KNOWN_ORIGINAL_500 = {
    "name":"v2-page-17", "path":"/api/admin/feedbacks?page=2147483647",
    "body":{"code":"INTERNAL_SERVER_ERROR","message":"서버 내부 오류가 발생했습니다."},
}


def original_contract(case, status, body):
    if "body" in case:
        return status==case["status"] and normalize(body)==normalize(case["body"])
    if case.get("name")==KNOWN_ORIGINAL_500["name"]:
        return (case.get("path")==KNOWN_ORIGINAL_500["path"] and case.get("principal")=="admin"
                and case.get("fixture","baseline")=="baseline" and status==500
                and body==KNOWN_ORIGINAL_500["body"])
    return isinstance(status,int) and 100<=status<500


def validate_oracle(evidence, baseline_sha256=None):
    if (evidence.get("oracle_version")!=ORACLE_VERSION or evidence.get("status")!="passed"
            or evidence.get("case_sha256")!=(baseline_sha256 or digest(CASES))
            or not re_full_sha(evidence.get("spring_jar_sha256"))
            or not re_full_sha(evidence.get("original_snapshot_sha256"))):
        raise ValueError("Original HTTP oracle evidence is missing or invalid")
    cases=evidence.get("oracle_cases",[])
    expected=json.loads(CASES.read_text())+oracle_requests()
    if len(cases)!=len(expected):
        raise ValueError("Original HTTP oracle case coverage is incomplete")
    for case,probe in zip(cases,expected):
        if any(case.get(k)!=probe.get(k) for k in ("name","path","principal")) or case.get("fixture","baseline")!=probe.get("fixture","baseline"):
            raise ValueError("Original HTTP oracle request changed")
        if not isinstance(case.get("status"),int) or "body" not in case or not isinstance(case.get("input_rows"),list):
            raise ValueError("Original HTTP oracle response is incomplete")
        if not original_contract(probe,case["status"],case["body"]):
            raise ValueError("Original HTTP criteria or known compatibility response changed")
    if len(evidence.get("results",[]))!=len(cases) or not all(row.get("passed") is True and row.get("case")==case["name"] for row,case in zip(evidence["results"],cases)):
        raise ValueError("Original HTTP oracle checks did not pass")
    return cases


def re_full_sha(value):
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(candidate):
    return {str(path.relative_to(candidate)): digest(path)
            for path in sorted(candidate.rglob("*"))
            if path.is_file() and not any(part in {"target", ".git", "__pycache__"}
                                          for part in path.relative_to(candidate).parts)}


def token(principal, secret):
    member = {"user": 941002, "withdrawn": 941003}.get(principal, 941001)
    now = int(time.time())
    claims = dict(iss="daynomy", sub=str(member), role="USER" if principal == "user" else "ADMIN",
                  token_type="access", iat=now, exp=now + 600, jti=str(uuid.uuid4()))
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")
    raw = encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()) + b"." + encode(json.dumps(claims).encode())
    key = os.urandom(32) if principal == "invalid" else secret
    return (raw + b"." + encode(hmac.new(key, raw, hashlib.sha256).digest())).decode()


@contextmanager
def _deadline_gate_lock(deadline):
    """Use the comparison gate's exact locks, with bounded acquisition."""
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not sample_gate._GATE_LOCK.acquire(timeout=remaining):
        raise TimeoutError("Lock deadline elapsed")
    try:
        path = sample_gate.ROOT / ".local/sample-gate.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            acquired = False
            try:
                while not acquired:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Lock deadline elapsed")
                    try:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                    except BlockingIOError:
                        time.sleep(min(.05, remaining))
                yield
            finally:
                if acquired:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    finally:
        sample_gate._GATE_LOCK.release()


def run_gate(candidate: Path, output: Path, target: Path, timeout_seconds: float = 120, *, oracle_path=None) -> dict:
    started = time.monotonic()
    deadline = started + timeout_seconds
    candidate, output, target = Path(candidate).resolve(), Path(output).resolve(), Path(target).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status="blocked", results=[], source_hashes={}, binary_sha256=None,
                  case_sha256=None, commands=[], elapsed_seconds=0, report=str(output / "result.json"))
    if oracle_path is not None:
        oracle_path=Path(oracle_path).resolve()
        result["oracle_path"]=str(oracle_path)
        result["oracle_sha256"]=digest(oracle_path)
    try:
        with _deadline_gate_lock(deadline):
            _run(candidate, output, target, deadline, result)
    except TimeoutError:
        result.update(status="blocked", reason="lock-timeout")
    except Exception as exc:
        result.update(status="blocked", reason="gate: " + type(exc).__name__)
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def _run(candidate, output, target, deadline, result):
    processes = []
    database_created = started_db = False
    previous_local, previous_names = spring.LOCAL, spring.DB_NAMES
    database = "daynomy_admin_feedback_" + uuid.uuid4().hex[:12] + "_test"
    stage = "inputs"
    oracle_only=result.get("mode")=="oracle"
    env = spring.clean_env()
    pg_path = shutil.which("pg_ctl")
    pg = Path(pg_path).parent if pg_path else Path("/opt/homebrew/opt/postgresql@18/bin")

    def remaining(cap=120):
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("Gate deadline elapsed")
        return min(cap, seconds)

    def command(name, args, *, environment=None, sql=None, cleanup=False):
        before = time.monotonic()
        try:
            process = subprocess.run(args, input=sql, text=True, env=environment or env,
                                     capture_output=True, cwd=ROOT,
                                     timeout=max(.1, min(3, deadline-time.monotonic())) if cleanup else remaining())
        except subprocess.TimeoutExpired:
            result["commands"].append(dict(name=name, exit_code=None, timed_out=True))
            raise
        result["commands"].append(dict(name=name, exit_code=process.returncode,
                                       elapsed_seconds=round(time.monotonic()-before, 3)))
        if process.returncode:
            raise RuntimeError("Subprocess failed")
        return process.stdout.strip()

    db_env = {**env, "PGHOST": "127.0.0.1", "PGPORT": "55439", "PGUSER": "pilot",
              "PGDATABASE": database, "PGCONNECT_TIMEOUT": "2"}

    def query(sql):
        return command("database-query", [str(pg / "psql"), "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1"],
                       environment=db_env, sql=sql)

    def snapshot():
        tables = query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
        parts = []
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            parts.append("SELECT '" + table.replace("'", "''") + "' AS name, "
                         "md5(coalesce(string_agg(row_data,E'\\n' ORDER BY row_data),'')) AS digest "
                         "FROM (SELECT row_to_json(t)::text AS row_data FROM public." + quoted + " t) s")
        return hashlib.sha256(query("SELECT row_to_json(s) FROM (" + " UNION ALL ".join(parts) + ") s ORDER BY name").encode()).hexdigest()

    def request(port, path, principal=None, secret=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=remaining(5))
        headers = {"Accept": "application/json"}
        if principal and principal != "none":
            headers["Cookie"] = "access_token=" + token(principal, secret)
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise RuntimeError("Response exceeds limit")
            return response.status, response.getheader("Content-Type", "").split(";")[0].lower(), json.loads(body)
        finally:
            connection.close()

    def ready(process, port):
        while True:
            remaining()
            if process.poll() is not None:
                raise RuntimeError("Server exited")
            try:
                if request(port, "/api/auth/csrf")[0] == 200:
                    return
            except (OSError, http.client.HTTPException):
                time.sleep(min(.1, remaining()))

    try:
        remaining()
        if not oracle_only and (output.is_relative_to(candidate) or target.is_relative_to(candidate)):
            raise ValueError("Output and build target must be outside source candidate")
        binary=None if oracle_only else target / "debug/daynomy-admin-feedback-bench"
        cases=json.loads(CASES.read_text())
        if len(cases)!=18:
            raise ValueError("Expected eighteen frozen cases")
        if oracle_only:
            cases+=oracle_requests()
        elif result.get("oracle_path"):
            evidence=json.loads(Path(result["oracle_path"]).read_text())
            cases=validate_oracle(evidence)
        result.update(source_hashes={} if oracle_only else source_hashes(candidate), binary_sha256=None if oracle_only else digest(binary),case_sha256=digest(CASES))
        if not oracle_only and not result["source_hashes"]:
            raise ValueError("Candidate source missing")
        result["original_snapshot_sha256"]=digest(ROOT/".local/comparison/source-snapshot.json")
        manifest = json.loads((ROOT / ".local/comparison/source-snapshot.json").read_text())
        spring.verify_source(manifest)
        jar_hash = digest(SPRING_JAR)
        result["spring_jar_sha256"] = jar_hash
        if result.get("oracle_path") and any(evidence.get(key)!=result[key] for key in ("spring_jar_sha256","original_snapshot_sha256")):
            raise ValueError("Original source or binary changed since oracle capture")
        for port in ((18082,) if oracle_only else (18082,18087)):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        stage = "database"
        status = subprocess.run([str(pg / "pg_ctl"), "-D", str(ROOT / ".local/pgdata"), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, timeout=remaining(3))
        started_db = status.returncode != 0
        command("database-start", ["bash", str(ROOT / "scripts/local-db.sh"), "start"])
        command("database-create", [str(pg / "createdb"), "-h", "127.0.0.1", "-p", "55439", "-U", "pilot", database])
        database_created = True
        with tempfile.TemporaryDirectory(prefix="admin-feedback-gate-") as temporary:
            spring.LOCAL = Path(temporary)
            spring.DB_NAMES = (database, "unused_test")
            spring.write_config()
            config = spring.LOCAL / "application-comparison.properties"
            config.write_text(config.read_text() + "\njwt.issuer=daynomy\n")
            secret = os.urandom(32)
            encoded_secret = base64.b64encode(secret).decode()
            java = command("java-home", ["/usr/libexec/java_home", "-v", "21"])
            stage = "spring-start"
            java_env = spring.spring_env(java)
            java_env["JWT_SECRET"] = encoded_secret
            original = spring.start([java + "/bin/java", "-jar", str(SPRING_JAR)], java_env, spring.COPY, "original")
            processes.append(original)
            ready(original, 18082)
            result["commands"].append(dict(name="spring-start", exit_code=0))
            query(SEED)
            stage = "rust-start"
            if not oracle_only:
                runtime_env = {**env, "DATABASE_URL": "postgresql://pilot@127.0.0.1:55439/" + database,
                               "PORT": "18087", "JWT_SECRET": encoded_secret, "JWT_ISSUER": "daynomy", "COOKIE_SECURE": "false"}
                with (spring.LOCAL / "rust.log").open("w") as log:
                    rust = subprocess.Popen([str(binary)], env=runtime_env, cwd=candidate, stdout=log, stderr=log)
                processes.append(rust)
                ready(rust, 18087)
                result["commands"].append(dict(name="rust-start", exit_code=0))
            stage = "http-contracts"
            baseline=snapshot();fixture="baseline"
            for case in cases:
                if case.get("fixture","baseline")!=fixture:
                    if fixture!="baseline" or case.get("fixture")!="timestamps-v2":
                        raise ValueError("Unexpected oracle fixture transition")
                    query(TIMESTAMP_SEED);fixture="timestamps-v2";baseline=snapshot()
                observed=[]
                input_rows=json.loads(query("SELECT coalesce(json_agg(row_to_json(t) ORDER BY id),'[]'::json)::text FROM feedbacks t")) if oracle_only or result.get("oracle_path") else None
                if result.get("oracle_path") and input_rows!=case["input_rows"]:
                    raise ValueError("Synthetic oracle fixture changed")
                for port in ((18082,) if oracle_only else (18082,18087)):
                    status,media,body=request(port,case["path"],case["principal"],secret)
                    contract=original_contract(case,status,body)
                    observed.append(dict(status=status,contract=contract,media=media=="application/json",unchanged=snapshot()==baseline))
                    if oracle_only:
                        result["oracle_cases"].append({**case,"status":status,"body":body,"input_rows":input_rows})
                passed=all(value["contract"] and value["media"] and value["unchanged"] for value in observed)
                result["results"].append(dict(case=case["name"],passed=passed,
                    spring_status=observed[0]["status"],rust_status=None if oracle_only else observed[1]["status"],
                    spring_contract=observed[0]["contract"],rust_contract=None if oracle_only else observed[1]["contract"],
                    json_media_type=all(v["media"] for v in observed),database_unchanged=all(v["unchanged"] for v in observed)))
            stage = "integrity"
            remaining()
            spring.verify_source(manifest)
            if ((not oracle_only and (source_hashes(candidate)!=result["source_hashes"] or digest(binary)!=result["binary_sha256"]))
                    or digest(CASES)!=result["case_sha256"] or digest(SPRING_JAR)!=jar_hash
                    or digest(ROOT/".local/comparison/source-snapshot.json")!=result["original_snapshot_sha256"]
                    or result.get("oracle_path") and digest(Path(result["oracle_path"]))!=result["oracle_sha256"]):
                raise RuntimeError("Source, binary or criteria changed")
            result["status"] = "passed" if all(case["passed"] for case in result["results"]) else "failed"
    except Exception as exc:
        result.update(status="blocked", reason=stage + ": " + type(exc).__name__)
    finally:
        cleanup_failed = False
        for process in reversed(processes):
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=max(.1, min(2, deadline-time.monotonic())))
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                cleanup_failed = True
        if database_created:
            try:
                command("database-drop", [str(pg / "dropdb"), "--force", "-h", "127.0.0.1", "-p", "55439", "-U", "pilot", database], cleanup=True)
            except Exception:
                cleanup_failed = True
        if started_db:
            try:
                command("database-stop", ["bash", str(ROOT / "scripts/local-db.sh"), "stop"], cleanup=True)
            except Exception:
                cleanup_failed = True
        spring.LOCAL, spring.DB_NAMES = previous_local, previous_names
        if cleanup_failed:
            result.update(status="blocked", reason="cleanup failed")
