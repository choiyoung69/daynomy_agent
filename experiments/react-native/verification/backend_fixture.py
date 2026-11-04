#!/usr/bin/env python3
"""Serve existing Rust code against a disposable local DB for Android acceptance.

No original server/.env/providers. Own resources are cleaned on Ctrl-C or a stop file.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import urllib.request
import uuid
import shutil
from contextlib import nullcontext

from admin_feedback_gate import _deadline_gate_lock
from agent_workflow import clean_env
from service_migrate import apply

ROOT=Path(__file__).resolve().parents[3]
PG=Path('/opt/homebrew/opt/postgresql@18/bin')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--discovery',action='store_true',help='Also seed synthetic public news and cached FX for the next increment')
    parser.add_argument('--core30',action='store_true',help='Freeze current Rust and seed a synthetic member; issue-login file mints a 60-second test code')
    parser.add_argument('--http-port',type=int)
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'experiments/react-native/verification'):raise ValueError('output must be React Native verification directory')
    out.mkdir(parents=True,exist_ok=False);stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    env=clean_env();env.update(CARGO_HOME=str(ROOT/'.local/cargo'),CARGO_TARGET_DIR=str(ROOT/'.local/service-target'),CARGO_NET_OFFLINE='true')
    source_root=ROOT/'app'
    if args.core30:
        source_root=out/'candidate';shutil.copytree(ROOT/'app',source_root,ignore=shutil.ignore_patterns('target'))
    apiport=args.http_port or (18109 if args.core30 else 18091)
    report={'started_at':datetime.now(timezone.utc).isoformat(),'status':'preparing','commands':[],
            'source_root':str(source_root.relative_to(ROOT)),
            'source_hashes':{str(p.relative_to(source_root)):sha(p) for p in source_root.rglob('*') if p.is_file() and 'target' not in p.parts},
            'base_url':'http://127.0.0.1:'+str(apiport),'fixture_assets':{'kr':910001,'us':910002,'missing_price':910003}}
    def save(): (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    def command(label,args,environment=None,input=None):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            result=subprocess.run(args,cwd=ROOT,env=environment or env,input=input,text=True,stdout=log,stderr=log,timeout=180)
        report['commands'].append({'name':label,'exit_code':result.returncode,'seconds':time.monotonic()-start});save()
        if result.returncode:raise RuntimeError(label+' failed; inspect local sanitized command log')
    save();server=None;created=False;owned_db=False
    db='daynomy_android_'+uuid.uuid4().hex[:8]+'_test'
    port='55459' if args.core30 else '55439'
    dbargs=['-h','127.0.0.1','-p',port,'-U','pilot']
    try:
        command('rust-build',['cargo','build','--locked','--offline','--manifest-path',str(source_root/'Cargo.toml')])
        binary=ROOT/'.local/service-target/debug/daynomy-feedback'
        if args.core30:
            shutil.copy2(binary,out/'candidate-server');binary=out/'candidate-server'
        report['binary_sha256']=sha(binary);save()
        # A private cluster has no shared DB state. Other runs retain their shared lock unchanged.
        with (nullcontext() if args.core30 else _deadline_gate_lock(time.monotonic()+1800)):
            try:
                if args.core30:
                    command('private-db-init',[str(PG/'initdb'),'-D',str(out/'pgdata'),'-U','pilot','--auth=trust','--encoding=UTF8'])
                    command('private-db-start',[str(PG/'pg_ctl'),'-D',str(out/'pgdata'),'-l',str(out/'postgres.log'),'-o','-h 127.0.0.1 -p '+port+' -k /private/tmp','-w','start']);owned_db=True
                else:
                    owned_db=subprocess.run([str(PG/'pg_ctl'),'-D',str(ROOT/'.local/pgdata'),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
                    command('local-db-start',['bash','scripts/local-db.sh','start'])
                command('fixture-db-create',[str(PG/'createdb'),*dbargs,db]);created=True
                runtime=env.copy();runtime.update(DATABASE_URL='postgresql://pilot@127.0.0.1:'+port+'/'+db,
                    PORT=str(apiport),JWT_SECRET=base64.b64encode(os.urandom(32)).decode(),JWT_ISSUER='daynomy',COOKIE_SECURE='false',JOB_SCHEDULER_ENABLED='false')
                migrate_env=runtime.copy();migrate_env['PATH']=str(PG)+':'+migrate_env.get('PATH','')
                old_path=os.environ.get('PATH','');os.environ['PATH']=migrate_env['PATH']
                try:report['migrations']=apply(runtime['DATABASE_URL'],source_root)
                finally:os.environ['PATH']=old_path
                rows=[(910001,'삼성전자','STOCK','005930','KOSPI',True),(910002,'Apple','STOCK','AAPL.US','NASDAQ',True),
                    (910003,'가격 없음','STOCK','NOPRICE','KOSPI',True),(910004,'KODEX ETF','ETF','KODEX','KOSPI',True),
                    (910005,'숨김 삼성전자','STOCK','HIDDEN','KOSPI',False)]
                rows += [(911000+i,f'LIMIT 샘플{i:02}','STOCK',f'LIMIT{i:02}','KOSPI',True) for i in range(25)]
                def literal(v):return "'"+str(v).replace("'","''")+"'"
                sql=''
                for ident,name,category,code,market,listed in rows:
                    sql+='INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES ('+','.join([str(ident),literal(name),literal(category),literal(code),literal(market),str(listed).lower(),'now()','now()'])+');\n'
                sql+="INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES (910001,'2026-10-22',70000,now(),now()),(910001,'2026-10-23',71000.1250,now(),now()),(910002,'2026-10-22',193.4000,now(),now());\n"
                if args.discovery:
                    for ident,category,status,stamp in [(920001,'STOCK','PUBLISHED','2026-10-23T00:00:00Z'),(920002,'STOCK','PUBLISHED','2026-10-23T00:00:00Z'),(920003,'ETF','PUBLISHED','2026-10-22T00:00:00Z'),(920004,'STOCK','DRAFT','2026-10-23T00:00:00Z'),(920005,'STOCK','REJECTED','2026-10-23T00:00:00Z')]:
                        sql+='INSERT INTO news(id,title,content,category,status,published_at,image_url,image_source,sources,created_at,updated_at) VALUES ('+','.join([str(ident),literal('테스트 뉴스 '+str(ident)),literal('첫 문단\n\n둘째 문단'),literal(category),literal(status),literal(stamp),'NULL',literal('{"name":"","url":"","author":"","license":"","licenseUrl":"","type":"NONE"}')+'::jsonb',literal('[{"name":"합성 출처","url":"https://example.invalid/source"}]')+'::jsonb','now()','now()'])+');\n'
                    sql+="INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at) VALUES ('2026-10-25','2026-10-23',1423.123456,now());\n"
                    report['discovery_fixture']={'published_news':[920001,920002,920003],'hidden_news':[920004,920005],'exchange_date':'2026-10-25','exchange_base_date':'2026-10-23','exchange_rate':'1423.123456'}
                if args.core30:
                    sql+="INSERT INTO members(id,provider,provider_id,email,google_name,nickname,role,status,created_at,updated_at) VALUES (930001,'GOOGLE','android-synthetic-member','android-fixture@example.invalid','합성 사용자','android_fixture','USER','ACTIVE',now(),now());\n"
                    report['core_fixture']={'member_id':930001,'auth_mode':'synthetic DB one-use PKCE code; real Google provider not exercised','login_material':'private login-env.json, never log contents'}
                command('synthetic-seed',[str(PG/'psql'),'-X','-w','-v','ON_ERROR_STOP=1',*dbargs,'-d',db],input=sql)
                log=(out/'server.log').open('w')
                server=subprocess.Popen([str(binary)],cwd=ROOT,env=runtime,stdout=log,stderr=log)
                for _ in range(100):
                    if server.poll() is not None:raise RuntimeError('Rust server exited')
                    try:
                        with urllib.request.urlopen(report['base_url']+'/api/stocks?q=005930',timeout=1) as response:
                            if response.status==200:break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('Rust readiness timeout')
                report.update(status='serving',server_started_at=datetime.now(timezone.utc).isoformat());save()
                print('Rust/DB React Native fixture ready at '+report['base_url'],flush=True)
                issued=0
                while not stop.wait(.25) and not (out/'stop').exists():
                    if server.poll() is not None:raise RuntimeError('Rust server exited during acceptance')
                    if args.core30 and (out/'issue-login').exists():
                        verifier=base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('=')
                        code=base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('=')
                        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
                        issue_sql="DELETE FROM mobile_auth_codes WHERE member_id=930001; INSERT INTO mobile_auth_codes(code_hash,member_id,code_challenge,expires_at,created_at) VALUES ("+literal(hashlib.sha256(code.encode()).hexdigest())+",930001,"+literal(challenge)+",now()+interval '60 seconds',now());"
                        issued+=1;command('issue-synthetic-login-'+str(issued),[str(PG/'psql'),'-X','-w','-v','ON_ERROR_STOP=1',*dbargs,'-d',db],input=issue_sql)
                        material=out/'login-env.json';temporary=out/'login-env.tmp'
                        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                        with os.fdopen(fd,'w') as f:json.dump({'ANDROID_PILOT_BASE_URL':report['base_url'],'ANDROID30_LOGIN_CODE':code,'ANDROID30_LOGIN_VERIFIER':verifier,'ANDROID30_ASSET_ID':'910001'},f)
                        temporary.replace(material);(out/'issue-login').unlink()
                report['status']='stopped'
            finally:
                if server:
                    server.terminate()
                    try:server.wait(timeout=10)
                    except subprocess.TimeoutExpired:server.kill();server.wait()
                if created:command('fixture-db-drop',[str(PG/'dropdb'),'--force',*dbargs,db])
                if owned_db:
                    if args.core30:command('private-db-stop',[str(PG/'pg_ctl'),'-D',str(out/'pgdata'),'-m','fast','-w','stop'])
                    else:command('local-db-stop',['bash','scripts/local-db.sh','stop'])
    except Exception as failure:
        report.update(status='failed',failure_type=type(failure).__name__);raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();save()
    return 0

if __name__=='__main__':raise SystemExit(main())
