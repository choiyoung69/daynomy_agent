#!/usr/bin/env python3
"""Own isolated PG55561 + Rust18096. No shared cluster/DB writes. Secret-free logs.
Place run-client.json {"argv":[...]} in output to run once with ephemeral auth code.
Place stop in output or SIGTERM to clean up only owned server and cluster.
"""
import argparse,base64,hashlib,json,os,shutil,signal,socket,subprocess,sys,threading,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from agent_workflow import clean_env
from service_migrate import apply
from service_acceptance import fixture_sql
PG=Path('/opt/homebrew/opt/postgresql@18/bin');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve()
 if not out.is_relative_to(ROOT/'.local'):raise ValueError('Requires isolated repository-local output')
 out.mkdir(parents=True,exist_ok=False);stop=threading.Event()
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
 for port in (55561,18096):
  with socket.socket() as probe:
   if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Reserved isolated port already in use')
 shared=json.loads((ROOT/'.local/android-next-backend-01/result.json').read_text())
 binary_source=ROOT/'.local/service-target/debug/daynomy-feedback'
 assert sha(binary_source)==shared['binary_sha256']
 assert all(sha(ROOT/'app'/p)==h for p,h in shared['source_hashes'].items() if p!='README.md')
 candidate=out/'candidate';shutil.copytree(ROOT/'app',candidate,ignore=shutil.ignore_patterns('target'))
 binary=out/'daynomy-feedback';shutil.copy2(binary_source,binary)
 db='ios_full30_service_test';pgdata=out/'pgdata';sock=out/'socket';sock.mkdir()
 env=clean_env();env['PATH']=str(PG)+':'+env.get('PATH','')
 runtime=env.copy();runtime.update(DATABASE_URL=f'postgresql://pilot@127.0.0.1:55561/{db}',PORT='18096',JWT_SECRET=base64.b64encode(os.urandom(32)).decode(),JWT_ISSUER='daynomy',COOKIE_SECURE='false',JOB_SCHEDULER_ENABLED='false',APP_TIMEZONE='Asia/Seoul')
 report={'started_at':datetime.now(timezone.utc).isoformat(),'status':'preparing','base_url':'http://127.0.0.1:18096','source_hashes':{str(p.relative_to(candidate)):sha(p) for p in candidate.rglob('*') if p.is_file()},'binary_sha256':sha(binary),'binary_provenance':'Copied verified existing compiled binary; all non-README source matches startup hash','commands':[],'data':'isolated synthetic only; no real provider; own PG port55561; shared cluster untouched'}
 def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 def command(name,argv,input=None,environment=None):
  started=time.monotonic()
  with (out/(name+'.log')).open('w') as log:p=subprocess.run(argv,cwd=ROOT,env=environment or env,input=input,text=True,stdout=log,stderr=log,timeout=120)
  report['commands'].append({'name':name,'exit_code':p.returncode,'seconds':time.monotonic()-started});save()
  if p.returncode:raise RuntimeError(name+' failed; details withheld')
 def sql(text):
  p=subprocess.run([str(PG/'psql'),'-X','-w','-A','-t','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p','55561','-U','pilot','-d',db],input=text,capture_output=True,text=True,env=env,timeout=20)
  if p.returncode:raise RuntimeError('Fixture SQL failed; details withheld')
  return p.stdout.strip()
 save();server=None;started_pg=False
 try:
  command('initdb',[str(PG/'initdb'),'-D',str(pgdata),'--auth=trust','--username=pilot','--encoding=UTF8','--no-locale'])
  command('pg-start',[str(PG/'pg_ctl'),'-D',str(pgdata),'-l',str(out/'postgres.log'),'-o',f'-h 127.0.0.1 -p 55561 -k {sock}','start']);started_pg=True
  command('db-create',[str(PG/'createdb'),'-h','127.0.0.1','-p','55561','-U','pilot',db])
  old=os.environ.get('PATH','');os.environ['PATH']=env['PATH']
  try:report['migrations']=apply(runtime['DATABASE_URL'],candidate)
  finally:os.environ['PATH']=old
  today=datetime.now(ZoneInfo('Asia/Seoul')).replace(hour=12,minute=0,second=0,microsecond=0)
  seed,_,_=fixture_sql(today)
  seed+="INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at) VALUES('2020-01-03','2020-01-03',1300.25,now()),('2020-01-02','2020-01-02',1299.50,now());"
  seed+="INSERT INTO investment_events(id,event_type,title,announced_at,previous_value,actual_value,value_unit,source_name,source_url,source_key,created_at,updated_at) VALUES(960001,'US_CPI','iOS fixture CPI',date_trunc('month',now())+interval '15 days 5 hours',3,2.5,'%','Synthetic','https://fixture.invalid/calendar','ios-fixture-cpi',now(),now());"
  seed+="INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES(970001,'GOOGLE','ios-fixture','ios@fixture.invalid','iosfixture','USER','ACTIVE',now(),now());"
  sql(seed)
  log=(out/'server.log').open('w');server=subprocess.Popen([str(binary)],cwd=ROOT,env=runtime,stdout=log,stderr=log)
  for _ in range(100):
   if server.poll() is not None:raise RuntimeError('Rust exited')
   with socket.socket() as probe:
    if probe.connect_ex(('127.0.0.1',18096))==0:break
   time.sleep(.1)
  else:raise RuntimeError('Rust readiness timed out')
  report.update(status='serving',server_started_at=datetime.now(timezone.utc).isoformat());save();print('Isolated iOS Rust fixture ready at http://127.0.0.1:18096',flush=True)
  processed=False
  while not stop.wait(.2) and not (out/'stop').exists():
   if server.poll() is not None:raise RuntimeError('Rust exited')
   trigger=out/'run-client.json'
   if trigger.exists() and not processed:
    processed=True;request=json.loads(trigger.read_text());code=uuid.uuid4().hex+uuid.uuid4().hex;verifier=base64.urlsafe_b64encode(os.urandom(48)).rstrip(b'=').decode();challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    sql("INSERT INTO mobile_auth_codes(code_hash,member_id,code_challenge,expires_at) VALUES('"+hashlib.sha256(code.encode()).hexdigest()+"',970001,'"+challenge+"',now()+interval '60 seconds');")
    before=int(sql('SELECT count(*) FROM feedbacks;'));client_env=env.copy();client_env.update(IOS_FIXTURE_BASE_URL=report['base_url'],IOS_FIXTURE_AUTH_CODE=code,IOS_FIXTURE_AUTH_VERIFIER=verifier)
    command('swift-client',request['argv'],environment=client_env)
    after=int(sql('SELECT count(*) FROM feedbacks;'));report['feedback_count_before']=before;report['feedback_count_after']=after;report['feedback_exactly_one_row']=after==before+1
    report['client_completed_at']=datetime.now(timezone.utc).isoformat();save();print('Isolated Swift client finished; feedback row delta '+str(after-before),flush=True)
  report['status']='stopped'
 except Exception as error:
  report.update(status='failed',failure_type=type(error).__name__);raise
 finally:
  if server:
   server.terminate()
   try:server.wait(timeout=10)
   except subprocess.TimeoutExpired:server.kill();server.wait()
  if started_pg:command('pg-stop',[str(PG/'pg_ctl'),'-D',str(pgdata),'-m','fast','stop'])
  report['finished_at']=datetime.now(timezone.utc).isoformat();save()
if __name__=='__main__':main()
