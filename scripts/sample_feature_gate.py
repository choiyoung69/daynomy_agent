#!/usr/bin/env python3
"""Real HTTP/PostgreSQL differential gate for three bounded sample endpoints."""
from datetime import datetime, timezone
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import threading
import uuid

from acceptance import Client, EnvironmentFailure
from agent_workflow import clean_env, dump, digest
from workflow_gate import _stop_group, _stop_server
import run_comparison as spring

ROOT = Path(__file__).resolve().parents[1]
FILES = ("news.rs", "portfolio_calc.rs")
_GATE_LOCK = threading.Lock()


@contextmanager
def gate_lock():
    """Serialize this gate's shared Spring globals, ports, binary and PG lifecycle.

    Applies to old sequential callers too. Other PostgreSQL scripts are not
    covered by this lock and must not be run at the same time.
    """
    path = ROOT / ".local/sample-gate.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _GATE_LOCK, path.open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

SEED = """
INSERT INTO news (id,title,content,image_url,category,published_at,created_at,updated_at,status,sources,image_source) VALUES
(201,'fixture stock A','fixture body A',NULL,'STOCK','2026-08-18 10:00Z',now(),now(),'PUBLISHED','[{"name":"fixture","url":"https://example.test/a"}]','{"name":"","url":"","author":"","license":"","licenseUrl":"","type":"NONE"}'),
(202,'fixture stock B','fixture body B','https://example.test/b.png','STOCK','2026-08-18 10:00Z',now(),now(),'PUBLISHED','[]','{"name":"Wikimedia","url":"https://example.test/b","author":"fixture","license":"CC0","licenseUrl":"https://example.test/license","type":"WIKIMEDIA"}'),
(203,'fixture ETF','fixture body C',NULL,'ETF','2026-08-17 09:00Z',now(),now(),'PUBLISHED','[]','{"name":"","url":"","type":"NONE"}'),
(204,'fixture draft','private draft',NULL,'STOCK',NULL,now(),now(),'DRAFT','[]','{"name":"","url":"","type":"NONE"}'),
(205,'fixture rejected','private rejected',NULL,'REAL_ESTATE',NULL,now(),now(),'REJECTED','[]','{"name":"","url":"","type":"NONE"}');
INSERT INTO assets (id,name,category,asset_code,market,listed,created_at,updated_at) VALUES
(101,'fixture KR A','STOCK','BENCH101','KOSPI',true,now(),now()),
(102,'fixture KR ETF','ETF','BENCH102','KOSDAQ',true,now(),now()),
(103,'fixture unpriced','STOCK','BENCH103','KOSPI',true,now(),now()),
(104,'fixture US','STOCK','BENCH104.US','NASDAQ',true,now(),now()),
(105,'fixture mixed date','ETF','BENCH105','KOSPI',true,now(),now()),
(106,'fixture US unpriced','ETF','BENCH106.US','NYSE_ARCA',true,now(),now());
INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES
(101,'2026-08-17',120,now(),now()),(101,'2026-08-16',100,now(),now()),
(102,'2026-08-17',20.35,now(),now()),(102,'2026-08-16',20.05,now(),now()),
(104,'2026-08-17',10.1234,now(),now()),(104,'2026-08-16',9.9876,now(),now()),
(105,'2026-08-18',50,now(),now()),(105,'2026-08-17',45,now(),now());
INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at) VALUES
('2026-08-17','2026-08-17',1300.123456,now()),('2026-08-16','2026-08-16',1290.987654,now());
"""


def cases():
    out = []
    for name, query in [("news-default", ""), ("news-page", "?page=1&size=2"),
                        ("news-page2", "?page=2&size=2"), ("news-filter", "?category=ETF"),
                        ("news-empty", "?category=REAL_ESTATE"), ("news-page-outside", "?page=10"),
                        ("news-invalid-page", "?page=0"), ("news-invalid-size", "?size=101"),
                        ("news-invalid-category", "?category=BOGUS"), ("news-invalid-number", "?page=abc"),
                        ("news-empty-page", "?page="), ("news-empty-size", "?size="),
                        ("news-empty-category", "?category=")]:
        out.append((name, "/api/news"+query, None, "valid"))
    for name, ident in [("detail-published", "201"), ("detail-image", "202"),
                        ("detail-draft", "204"), ("detail-rejected", "205"), ("detail-missing", "9999")]:
        out.append((name, "/api/news/"+ident, None, "valid"))
    h = lambda ident, qty=2, price=90: {"assetId": ident, "quantity": qty, "averagePurchasePrice": price}
    for name, holdings in [
        ("calc-domestic", [h(101),h(102,3,20)]), ("calc-single", [h(101)]),
        ("calc-order", [h(102,3,20),h(101)]), ("calc-usd", [h(104,3,12000)]),
        ("calc-mixed-currency", [h(101),h(104,3,12000)]),
        ("calc-partial", [h(101),h(103)]), ("calc-all-unpriced", [h(103),h(106)]),
        ("calc-mixed-dates", [h(101),h(105)]),
        ("calc-large-decimal", [{"assetId":101,"quantity":123,"averagePurchasePrice":Decimal("999999999999999.99")}]),
        ("calc-max-quantity", [{"assetId":101,"quantity":9223372036854775807,"averagePurchasePrice":Decimal("999999999999999.99")}]),
        ("calc-min-purchase-price", [h(101,1,Decimal("0.01"))]),
        ("calc-duplicate", [h(101),h(101)]), ("calc-empty", []),
        ("calc-zero-quantity", [h(101,0)]), ("calc-negative-price", [h(101,2,-1)]),
        ("calc-unknown-asset", [h(9999)]), ("calc-too-many", [h(101)]*51),
        ("calc-null-item", [None]), ("calc-extra-price-decimal", [h(101,2,1.234)]),
    ]:
        out.append((name,"/api/portfolio/calculate",{"holdings":holdings},"valid"))
    out += [("calc-unreadable", "/api/portfolio/calculate", b"{", "valid"),
            ("calc-no-csrf", "/api/portfolio/calculate", {"holdings":[h(101)]}, "none")]
    for name, number in [("calc-exponent", "1e2"), ("calc-huge-exponent", "1e100"),
                         ("calc-tiny-exponent", "1e-100"), ("calc-zero-exponent", "0e100")]:
        body=('{"holdings":[{"assetId":101,"quantity":2,"averagePurchasePrice":'+number+'}]}').encode()
        out.append((name,"/api/portfolio/calculate",body,"valid"))
    return out


def encode(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{"+",".join(json.dumps(k)+":"+encode(v) for k,v in value.items())+"}"
    if isinstance(value, list):
        return "["+",".join(encode(v) for v in value)+"]"
    return json.dumps(value, ensure_ascii=False)


def normalize(value):
    if isinstance(value, dict):
        result={k:normalize(v) for k,v in value.items()}
        if isinstance(result.get("errors"),list):
            result["errors"].sort(key=lambda v:json.dumps(v,sort_keys=True))
        return result
    if isinstance(value,list): return [normalize(v) for v in value]
    if isinstance(value,str) and re.fullmatch(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)",value):
        return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc).isoformat()
    return value


def run_gate(candidate, output, run_directory):
    with gate_lock():
        return _run_gate(candidate, output, run_directory)


def _run_gate(candidate, output, run_directory):
    output.mkdir(parents=True,exist_ok=False)
    result={"status":"blocked","results":[],"commands":[],"measurements":{},"started_at":time.time()}
    processes=[]; rust_runtime=None; started_db=False; db_name="daynomy_sample_"+uuid.uuid4().hex[:12]+"_test"
    target=ROOT/".local/sample-target"
    env=clean_env();env.update(CARGO_HOME=str(ROOT/".local/cargo"),CARGO_NET_OFFLINE="true",CARGO_TARGET_DIR=str(target))
    pg=Path(shutil.which("pg_ctl")).parent
    def run(name,cmd,*,env_override=None,sql=None,timeout=600,cwd=ROOT):
        before=time.perf_counter()
        with (output/(name+".log")).open("w") as log:
            p=subprocess.Popen(cmd,cwd=cwd,env=env_override or env,text=True,stdin=subprocess.PIPE if sql else subprocess.DEVNULL,
                               stdout=log,stderr=log,start_new_session=True)
            try: p.communicate(sql,timeout=timeout)
            except subprocess.TimeoutExpired:
                _stop_group(p);raise RuntimeError(name+" timed out") from None
        result["commands"].append({"name":name,"exit_code":p.returncode})
        result["measurements"][name]=round(time.perf_counter()-before,3)
        if p.returncode: raise RuntimeError(name+" failed; see "+name+".log")
    db_env={**env,"PGHOST":"127.0.0.1","PGPORT":"55439","PGUSER":"pilot","PGDATABASE":db_name,"PGCONNECT_TIMEOUT":"5"}
    def sql(query):
        p=subprocess.run([str(pg/"psql"),"-X","-A","-t","-w","-v","ON_ERROR_STOP=1"],input=query,text=True,
                         capture_output=True,env=db_env,timeout=20)
        if p.returncode: raise RuntimeError("Fixture DB query failed")
        return p.stdout.strip()
    def snapshot():
        return "|".join(sql("SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) FROM "+table+" t;")
                        for table in ("news","assets","stock_daily_prices","usd_krw_rates","feedbacks","portfolio_holdings","portfolio_holding_histories","portfolio_daily_snapshots"))
    try:
        run("format",["rustfmt","--edition","2024",*[str(candidate/"src"/name) for name in FILES]])
        run("clippy",["cargo","clippy","--locked","--manifest-path",str(candidate/"Cargo.toml"),"--","-D","warnings"])
        run("build",["cargo","build","--locked","--manifest-path",str(candidate/"Cargo.toml")])
        hashes={name:digest(candidate/"src"/name) for name in FILES}; result["source_hashes"]=hashes
        # Reuse the immutable, previously built full original. No model or app source is changed.
        manifest=json.loads((ROOT/".local/comparison/source-snapshot.json").read_text())
        spring.verify_source(manifest)
        jar=ROOT/".local/spring-reference/build/libs/daynomy-0.0.1-SNAPSHOT.jar"
        if not jar.is_file(): raise RuntimeError("Original Spring jar unavailable; build separately")
        result["spring_jar_sha256"]=digest(jar)
        started_db=subprocess.run([str(pg/"pg_ctl"),"-D",str(ROOT/".local/pgdata"),"status"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
        run("database-start",["bash",str(ROOT/"scripts/local-db.sh"),"start"])
        run("database-create",[str(pg/"createdb"),"-h","127.0.0.1","-p","55439","-U","pilot",db_name])
        spring.LOCAL=output/"spring";spring.LOCAL.mkdir()
        spring.DB_NAMES=(db_name,"unused_test");spring.write_config()
        java_home=subprocess.check_output(["/usr/libexec/java_home","-v","21"],text=True).strip()
        port=18084
        cfg=spring.LOCAL/"application-comparison.properties"
        cfg.write_text(cfg.read_text().replace("server.port=18082","server.port="+str(port)))
        original=spring.start([java_home+"/bin/java","-jar",str(jar)],spring.spring_env(java_home),spring.COPY,"original")
        processes.append(("spring",original));spring.ready(original,port)
        sql(SEED)
        rust_log=output/"rust.log"
        runtime_env={**env,"DATABASE_URL":"postgresql://pilot@127.0.0.1:55439/"+db_name,"PORT":"0"}
        with rust_log.open("w") as log:
            rust=subprocess.Popen(["codex","sandbox","-P","daynomy_runtime","-C",str(candidate),"-c",
                'permissions.daynomy_runtime={filesystem={":root"="read"},network={enabled=true}}',sys.executable,"-c",
                'import os,sys; print("sandbox_runtime_pid="+str(os.getpid()),flush=True); os.execv(sys.argv[1],sys.argv[1:])',
                str(target/"debug/daynomy-sample")],env=runtime_env,stdout=log,stderr=log,start_new_session=True)
        processes.append(("rust",rust));deadline=time.monotonic()+15
        while True:
            text=rust_log.read_text()
            pid=re.search(r"sandbox_runtime_pid=(\d+)",text)
            address=re.search(r"event=server.started address=(127\.0\.0\.1:\d+)",text)
            if pid: rust_runtime=int(pid[1])
            if address and rust_runtime: break
            if rust.poll() is not None or time.monotonic()>deadline: raise RuntimeError("Sample server unavailable")
            time.sleep(.05)
        clients=[Client("http://127.0.0.1:"+str(port)),Client("http://"+address[1])]
        tokens=[c.csrf() for c in clients]
        baseline=snapshot(); oracle=[]
        for name,path,payload,mode in cases():
            observed=[];medias=[]
            for c,(header,token) in zip(clients,tokens):
                headers={"Content-Type":"application/json"}
                if mode=="valid": headers[header]=token
                data=payload if isinstance(payload,bytes) else encode(payload).encode() if payload is not None else None
                try:
                    status,h,body=c.send(path,data,headers)
                    media=h.get("Content-Type","").split(";")[0].lower()
                    value=json.loads(body,parse_float=Decimal) if body else None
                except EnvironmentFailure:
                    status,media,value=None,None,None
                observed.append({"status":status,"body":normalize(value)})
                medias.append(media)
            passed=observed[0]==observed[1] and medias[0]==medias[1]=="application/json"
            expected=True
            if name=="news-default": expected=[v["id"] for v in (observed[1]["body"] or {}).get("items",[])]==[202,201,203]
            if name=="calc-domestic":
                expected=(observed[1]["status"]==200 and observed[1]["body"].get("totalPurchaseAmount")==240
                          and observed[1]["body"].get("totalEvaluationAmount")==Decimal("301.05"))
            unchanged=snapshot()==baseline
            result["results"].append({"case":name,"passed":bool(passed and expected and unchanged),
                "spring_status":observed[0]["status"],"rust_status":observed[1]["status"],
                "http_match":passed,"independent_check":expected,"database_unchanged":unchanged})
            oracle.append({"case":name,"path":path,"observed":observed})
            (output/"observations.json").write_text(encode(oracle)+"\n")
        # A new database row after startup must appear; this rejects canned fixture responses.
        sql("UPDATE news SET title='fixture changed after startup' WHERE id=201;")
        new_values=[json.loads(c.send('/api/news/201')[2]) for c in clients]
        result["results"].append({"case":"news-live-db-update","passed":normalize(new_values[0])==normalize(new_values[1])
            and new_values[1].get("title")=="fixture changed after startup"})
        result["status"]="passed" if all(r["passed"] for r in result["results"]) else "failed"
        (output/"observations.json").write_text(encode(oracle)+"\n")
        if {name:digest(candidate/"src"/name) for name in FILES}!=hashes: raise RuntimeError("Source changed during tests")
    except Exception as exc:
        result.update(status="failed" if result.get("commands") and result["commands"][-1]["exit_code"] else "blocked",
                      reason=type(exc).__name__+": "+str(exc)[:300])
    finally:
        for kind,p in reversed(processes):
            try:
                if kind=="rust": _stop_server(p,rust_runtime)
                else: spring.stop(p)
            except Exception as exc: result.update(status="blocked",reason="Cleanup: "+type(exc).__name__)
        if started_db:
            try: run("database-stop",["bash",str(ROOT/"scripts/local-db.sh"),"stop"],timeout=60)
            except Exception as exc: result.update(status="blocked",reason="Database cleanup: "+type(exc).__name__)
        result.update(finished_at=time.time(),database=db_name,report=str(output/"result.json"))
        dump(output/"result.json",result)
    return result
