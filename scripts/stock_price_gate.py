#!/usr/bin/env python3
"""Real original/Rust HTTP gate for the bounded latest-stock-price experiment.

The caller compiles and tests the frozen candidate first. This gate executes the
prebuilt binary against a fresh fixture DB; it does not invoke any model.
"""
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from acceptance import Client, EnvironmentFailure
from agent_workflow import clean_env, digest, dump
from sample_feature_gate import encode, gate_lock, normalize
from workflow_gate import _stop_group, _stop_server
import run_comparison as spring

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("news", "assets", "stock_daily_prices", "usd_krw_rates", "feedbacks",
          "portfolio_holdings", "portfolio_holding_histories", "portfolio_daily_snapshots")
SEED = """
INSERT INTO assets (id,name,category,asset_code,market,listed,created_at,updated_at) VALUES
(101,'fixture KR A','STOCK','BENCH101','KOSPI',true,now(),now()),
(102,'fixture KR ETF','ETF','BENCH102','KOSDAQ',true,now(),now()),
(103,'fixture unpriced','STOCK','BENCH103','KOSPI',true,now(),now()),
(104,'fixture US','STOCK','BENCH104.US','NASDAQ',true,now(),now()),
(105,'fixture no market','STOCK','BENCH105',NULL,true,now(),now()),
(106,'fixture unlisted','STOCK','BENCH106.US','NASDAQ',false,now(),now()),
(107,'fixture NYSE','STOCK','BENCH107.US','NYSE',true,now(),now()),
(108,'fixture ARCA','ETF','BENCH108.US','NYSE_ARCA',true,now(),now()),
(109,'fixture AMERICAN','STOCK','BENCH109.US','NYSE_AMERICAN',true,now(),now()),
(110,'fixture BATS','ETF','BENCH110.US','BATS',true,now(),now());
INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES
(101,'2026-08-16',100,now(),now()),(101,'2026-08-17',120,now(),now()),
(102,'2026-08-17',20.35,now(),now()),(104,'2026-08-17',10.1234,now(),now()),
(105,'2026-08-17',3.14,now(),now()),(106,'2026-08-17',4.56,now(),now()),
(107,'2026-08-17',7.0001,now(),now()),(108,'2026-08-17',8.0002,now(),now()),
(109,'2026-08-17',9.0003,now(),now()),(110,'2026-08-17',10.0004,now(),now());
"""


def expected_price(ident, *, date="2026-08-17", price=None):
    """Fixed expectations from the source DTO, independent of either response."""
    fixtures = {
        101: ("BENCH101", "fixture KR A", "120", "KRW"),
        102: ("BENCH102", "fixture KR ETF", "20.35", "KRW"),
        104: ("BENCH104.US", "fixture US", "10.1234", "USD"),
        105: ("BENCH105", "fixture no market", "3.14", "KRW"),
        106: ("BENCH106.US", "fixture unlisted", "4.56", "USD"),
        107: ("BENCH107.US", "fixture NYSE", "7.0001", "USD"),
        108: ("BENCH108.US", "fixture ARCA", "8.0002", "USD"),
        109: ("BENCH109.US", "fixture AMERICAN", "9.0003", "USD"),
        110: ("BENCH110.US", "fixture BATS", "10.0004", "USD"),
    }
    code, name, close, currency = fixtures[ident]
    return {"assetId": ident, "assetCode": code, "name": name, "baseDate": date,
            "closePrice": Decimal(close if price is None else price), "currency": currency}


def cases():
    success = [("latest-domestic", "101", 101), ("latest-etf", "102", 102),
               ("latest-nasdaq", "104", 104), ("latest-null-market", "105", 105),
               ("latest-unlisted", "106", 106), ("latest-nyse", "107", 107),
               ("latest-arca", "108", 108), ("latest-american", "109", 109),
               ("latest-bats", "110", 110), ("latest-leading-zero", "000101", 101),
               ("latest-leading-plus", "+101", 101)]
    out = [(name, ident, 200, expected_price(asset)) for name, ident, asset in success]
    missing = {"code": "STOCK_PRICE_NOT_FOUND", "message": "주식·ETF 종가를 찾을 수 없습니다."}
    for name, ident in [("latest-unpriced", "103"), ("latest-missing", "9999"),
                        ("latest-zero", "0"), ("latest-negative", "-1"),
                        ("latest-max-id", "9223372036854775807"),
                        ("latest-min-id", "-9223372036854775808")]:
        out.append((name, ident, 404, missing))
    invalid = {"code": "INVALID_REQUEST", "message": "요청값이 올바르지 않습니다.",
               "errors": [{"field": "assetId", "reason": "타입이 올바르지 않습니다."}]}
    for name, ident in [("latest-invalid-text", "abc"), ("latest-invalid-fraction", "1.5"),
                        ("latest-overflow", "9223372036854775808"),
                        ("latest-underflow", "-9223372036854775809")]:
        out.append((name, ident, 400, invalid))
    return out


def run_gate(candidate: Path, output: Path, run_directory: Path, *, target=None) -> dict:
    with gate_lock():
        return _run_gate(Path(candidate), Path(output), Path(run_directory), target=target)


def _run_gate(candidate, output, run_directory, *, target=None):
    output.mkdir(parents=True, exist_ok=False)
    result = {"status": "blocked", "results": [], "commands": [], "measurements": {},
              "started_at": time.time(), "run_directory": str(run_directory)}
    processes = []
    rust_runtime = None
    started_db = False
    db_name = "daynomy_stock_price_" + uuid.uuid4().hex[:12] + "_test"
    target = Path(target) if target is not None else ROOT / ".local/stock-price-target"
    env = clean_env()
    env.update(CARGO_HOME=str(ROOT / ".local/cargo"), CARGO_NET_OFFLINE="true",
               CARGO_TARGET_DIR=str(target))
    pg_binary = shutil.which("pg_ctl")
    pg = Path(pg_binary).parent if pg_binary else None
    previous_spring = (spring.LOCAL, spring.DB_NAMES)

    def command(name, cmd, *, timeout=120):
        before = time.perf_counter()
        with (output / (name + ".log")).open("w") as log:
            process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _stop_group(process)
                raise RuntimeError(name + " timed out") from None
        result["commands"].append({"name": name, "exit_code": process.returncode})
        result["measurements"][name] = round(time.perf_counter() - before, 3)
        if process.returncode:
            raise RuntimeError(name + " failed; see " + name + ".log")

    db_env = {**env, "PGHOST": "127.0.0.1", "PGPORT": "55439", "PGUSER": "pilot",
              "PGDATABASE": db_name, "PGCONNECT_TIMEOUT": "5"}

    def sql(query):
        process = subprocess.run([str(pg / "psql"), "-X", "-A", "-t", "-w", "-v",
                                  "ON_ERROR_STOP=1"], input=query, text=True,
                                 capture_output=True, env=db_env, timeout=20)
        if process.returncode:
            raise RuntimeError("Fixture DB query failed")
        return process.stdout.strip()

    def snapshot():
        return "|".join(sql("SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY "
                                "to_jsonb(t)::text)::text,'[]')) FROM " + table + " t;")
                        for table in TABLES)

    observations = []

    def check_case(name, ident, expected_status, expected_body, baseline, clients):
        observed = []
        database_checks = []
        for client in clients:
            try:
                status, headers, body = client.send("/api/stocks/" + ident + "/price")
                media = headers.get("Content-Type", "").split(";")[0].lower()
                value = json.loads(body, parse_float=Decimal) if body else None
                observed.append({"status": status, "media": media, "body": normalize(value)})
            except (EnvironmentFailure, ValueError):
                observed.append({"status": None, "media": None, "body": None})
            database_checks.append(snapshot() == baseline)
        expected = {"status": expected_status, "media": "application/json",
                    "body": normalize(expected_body)}
        http_match = observed[0] == observed[1]
        independent = all(value == expected for value in observed)
        unchanged = all(database_checks)
        result["results"].append({"case": name, "passed": http_match and independent and unchanged,
                                  "spring_status": observed[0]["status"],
                                  "rust_status": observed[1]["status"],
                                  "http_match": http_match, "independent_check": independent,
                                  "database_unchanged": unchanged,
                                  "per_request_database_unchanged": database_checks})
        observations.append({"case": name, "asset_id": ident, "expected": expected,
                             "observed": observed})
        (output / "observations.json").write_text(encode(observations) + "\n")

    try:
        if pg is None:
            raise RuntimeError("PostgreSQL tools unavailable")
        binary = target / "debug/daynomy-stock-price"
        if not binary.is_file():
            raise RuntimeError("Caller must build the candidate first")
        hashes = {"stock_price.rs": digest(candidate / "src/stock_price.rs")}
        result["source_hashes"] = hashes
        result["binary_sha256"] = digest(binary)
        manifest = json.loads((ROOT / ".local/comparison/source-snapshot.json").read_text())
        spring.verify_source(manifest)
        result["original_source_files"] = len(manifest)
        jar = ROOT / ".local/spring-reference/build/libs/daynomy-0.0.1-SNAPSHOT.jar"
        if not jar.is_file():
            raise RuntimeError("Original Spring jar unavailable")
        result["spring_jar_sha256"] = digest(jar)
        started_db = subprocess.run([str(pg / "pg_ctl"), "-D", str(ROOT / ".local/pgdata"),
                                     "status"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL).returncode != 0
        command("database-start", ["bash", str(ROOT / "scripts/local-db.sh"), "start"])
        command("database-create", [str(pg / "createdb"), "-h", "127.0.0.1", "-p", "55439",
                                    "-U", "pilot", db_name])
        spring.LOCAL = output / "spring"
        spring.LOCAL.mkdir()
        spring.DB_NAMES = (db_name, "unused_test")
        spring.write_config()
        port = 18085
        config = spring.LOCAL / "application-comparison.properties"
        config.write_text(config.read_text().replace("server.port=18082", "server.port=" + str(port)))
        java_home = subprocess.check_output(["/usr/libexec/java_home", "-v", "21"], text=True).strip()
        original = spring.start([java_home + "/bin/java", "-jar", str(jar)],
                                spring.spring_env(java_home), spring.COPY, "original")
        processes.append(("spring", original))
        spring.ready(original, port)
        result["commands"].append({"name": "spring-startup", "exit_code": 0})
        sql(SEED)
        rust_log = output / "rust.log"
        runtime_env = {**env, "DATABASE_URL": "postgresql://pilot@127.0.0.1:55439/" + db_name,
                       "PORT": "0"}
        with rust_log.open("w") as log:
            rust = subprocess.Popen([
                "codex", "sandbox", "-P", "daynomy_runtime", "-C", str(candidate), "-c",
                'permissions.daynomy_runtime={filesystem={":root"="read"},network={enabled=true}}',
                sys.executable, "-c", 'import os,sys; print("sandbox_runtime_pid="+str(os.getpid()),'
                'flush=True); os.execv(sys.argv[1],sys.argv[1:])', str(binary)],
                env=runtime_env, stdout=log, stderr=log, start_new_session=True)
        processes.append(("rust", rust))
        deadline = time.monotonic() + 15
        while True:
            text = rust_log.read_text()
            pid = re.search(r"sandbox_runtime_pid=(\d+)", text)
            address = re.search(r"event=server.started address=(127\.0\.0\.1:\d+)", text)
            if pid:
                rust_runtime = int(pid[1])
            if address and rust_runtime:
                break
            if rust.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Rust stock-price server unavailable")
            time.sleep(.05)
        result["commands"].append({"name": "rust-startup", "exit_code": 0})
        clients = [Client("http://127.0.0.1:" + str(port)), Client("http://" + address[1])]
        baseline = snapshot()
        for name, ident, status, body in cases():
            check_case(name, ident, status, body, baseline, clients)
        sql("INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) "
            "VALUES(101,'2026-08-18',123.45,now(),now());")
        baseline = snapshot()
        check_case("latest-live-db-insert", "101", 200,
                   expected_price(101, date="2026-08-18", price="123.45"), baseline, clients)
        spring.verify_source(manifest)
        if hashes != {"stock_price.rs": digest(candidate / "src/stock_price.rs")}:
            raise RuntimeError("Source changed during HTTP tests")
        if digest(binary) != result["binary_sha256"]:
            raise RuntimeError("Binary changed during HTTP tests")
        result["status"] = "passed" if all(item["passed"] for item in result["results"]) else "failed"
    except Exception as exc:
        result.update(status="blocked", reason=type(exc).__name__ + ": " + str(exc)[:300])
    finally:
        for kind, process in reversed(processes):
            try:
                if kind == "rust":
                    _stop_server(process, rust_runtime)
                else:
                    spring.stop(process)
                result["commands"].append({"name": kind + "-shutdown", "exit_code": 0})
            except Exception as exc:
                result.update(status="blocked", reason="Cleanup: " + type(exc).__name__)
        if started_db:
            try:
                command("database-stop", ["bash", str(ROOT / "scripts/local-db.sh"), "stop"], timeout=60)
            except Exception as exc:
                result.update(status="blocked", reason="Database cleanup: " + type(exc).__name__)
        spring.LOCAL, spring.DB_NAMES = previous_spring
        result.update(finished_at=time.time(), database=db_name, report=str(output / "result.json"))
        dump(output / "result.json", result)
    return result
