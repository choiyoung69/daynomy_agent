#!/usr/bin/env python3
"""Independent native --job contracts from original KRX/BLS/BOK/DART/FX services.

A coordinator launches the local mock before passing its environment to this
checker. Real CLI processes and a dedicated *_service_test PostgreSQL database
are required. No app implementation reads, external calls, server or DB startup.
Fixture IDs 970001..970099; all subprocess output stays in memory, never logs.
"""
import argparse
import calendar
from contextlib import contextmanager
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import os
import re
import signal
import tempfile
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs,urlsplit
import zipfile
from zoneinfo import ZoneInfo
from acceptance import EnvironmentFailure,require,validate_local_url
from service_acceptance import TestDatabase,equal
from service_core_acceptance import literal

TODAY=datetime.now(ZoneInfo('Asia/Seoul')).date();YEAR=TODAY.year
FX_DAY=datetime.now(ZoneInfo('America/New_York')).date()-timedelta(days=1)
RECEIPT='20261021000001';CODE='987001'


def holidays(year):
    last=date(year,12,31)
    while last.weekday()>4:last-=timedelta(days=1)
    return {date(year,1,1),date(year,5,1),date(year,12,25),last}


class ScheduleMock:
    def __init__(self):
        self.server=None;self.lock=threading.Lock();self.mode='valid';self.counts={};self.delay=0
        self.key='fixture-schedule-key'
    @property
    def base_url(self):return 'http://127.0.0.1:'+str(self.server.server_port)
    @property
    def control_url(self):return self.base_url+'/__test__/state'
    @property
    def environment(self):
        return dict(KRX_CALENDAR_BASE_URL=self.base_url,BLS_BASE_URL=self.base_url+'/bls',BLS_SCHEDULE_URL=self.base_url+'/schedule/home.htm',BOK_BASE_URL=self.base_url,ECOS_BASE_URL=self.base_url,ECOS_API_KEY=self.key,DART_BASE_URL=self.base_url,DART_API_KEY=self.key,EODHD_BASE_URL=self.base_url,EODHD_API_TOKEN=self.key,INVESTMENT_CALENDAR_HISTORY_YEARS='1',INVESTMENT_CALENDAR_READ_TIMEOUT_SECONDS='8',PUBLIC_DATA_SERVICE_KEY=self.key,PUBLIC_DATA_STOCK_PRICE_URL=self.base_url+'/kr/history/stock',PUBLIC_DATA_ETF_PRICE_URL=self.base_url+'/kr/history/etf')
    def state(self):
        with self.lock:return dict(mode=self.mode,counts=self.counts.copy())
    def response(self,method,path,q,body):
        with self.lock:
            self.counts[path]=self.counts.get(path,0)+1;mode=self.mode;delay=self.delay
        if delay and path=='/eod/USDKRW.FOREX':time.sleep(delay)
        if mode=='failure':return 503,{},'application/json'
        if path.endswith('MKD01100305.jsp'):
            return 200,'<select name="search_bas_yy"><option value="'+str(YEAR)+'">Current</option></select>','text/html'
        if path=='/contents/COM/GenerateOTP.jspx':return 200,'fixtureOTP','text/plain'
        if path=='/contents/OPN/99/OPN99000001.jspx':
            values=parse_qs(body.decode());require(values.get('search_bas_yy')==[str(YEAR)] and values.get('gridTp')==['KRX'] and values.get('code')==['fixtureOTP'],'KRX form contract')
            days=sorted(holidays(YEAR))
            if mode=='incomplete':days=[day for day in days if day!=date(YEAR,1,1)]
            return 200,dict(block1=[dict(calnd_dd=day.isoformat()) for day in days]),'text/html'
        if path=='/eod/USDKRW.FOREX':
            require(q.get('api_token')==[self.key] and q.get('fmt')==['json'],'FX authentication/format')
            require(q.get('to')==[FX_DAY.isoformat()],'FX latest New York closed date')
            return 200,[dict(date=FX_DAY.isoformat(),close=1350.123456)],'application/json'
        if path.startswith('/schedule/'):
            year=int(path.split('/')[2]);html='<table></table>'
            if year==YEAR:
                release=date(YEAR,2,11)
                html='<table><tr><td>'+release.strftime('%A, %B ')+str(release.day)+', '+str(YEAR)+'</td><td>8:30 AM</td><td>Consumer Price Index for January '+str(YEAR)+'</td></tr></table>'
            return 200,html,'text/html'
        if path=='/bls/timeseries/data/':
            require(json.loads(body)['seriesid']==['CUUR0000SA0'],'BLS CPI series')
            rows=[dict(year=str(year),period=period,value=value) for year,period,value in [(YEAR,'M01','121'),(YEAR-1,'M01','110'),(YEAR-1,'M12','120'),(YEAR-2,'M12','100')]]
            return 200,dict(status='REQUEST_SUCCEEDED',Results=dict(series=[dict(data=rows)])),'application/json'
        if path.endswith('/listYear.do'):
            html='<table></table>'
            if q.get('pYear')==[str(YEAR)]:html='<table><tr><th scope="row">1월 15일</th></tr></table>'
            return 200,html,'text/html'
        if path.startswith('/StatisticSearch/'):
            require('/'+self.key+'/' in path,'ECOS fixture key')
            return 200,dict(StatisticSearch=dict(row=[dict(TIME=str(YEAR)+'0114',DATA_VALUE='3.50'),dict(TIME=str(YEAR)+'0115',DATA_VALUE='3.25')])),'application/json'
        if path=='/list.json':
            require(q.get('crtfc_key')==[self.key] and q.get('page_no')==['1'],'DART list query')
            return 200,dict(status='000',message='정상',total_page=1,list=[dict(corp_name='Schedule Fixture',stock_code=CODE,report_nm='영업(잠정)실적(공정공시)',rcept_no=RECEIPT,rcept_dt=TODAY.strftime('%Y%m%d'))]),'application/json'
        if path=='/document.xml':
            require(q.get('crtfc_key')==[self.key] and q.get('rcept_no')==[RECEIPT],'DART document identity')
            html='<html><table><tr><td>당기실적</td><td>'+str(YEAR)+'.01.01</td><td>부터</td><td>'+str(YEAR)+'.03.31</td></tr><tr><td>영업이익</td><td>당해실적</td><td>250</td><td>200</td></tr><tr><td>단위:백만원</td></tr></table></html>'
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('fixture.xml',html)
            return 200,buffer.getvalue(),'application/zip'
        # Historical price lookup may find no samples; event import must persist.
        if path.startswith('/eod/') and q.get('api_token')==[self.key]:return 200,[],'application/json'
        if path in ('/kr/history/stock','/kr/history/etf'):
            require(q.get('serviceKey')==[self.key] and q.get('resultType')==['json'] and q.get('numOfRows')==['1000'] and q.get('pageNo')==['1'],'Public history query contract')
            code=q['likeSrtnCd'][0];first=q['beginBasDt'][0];last=q['endBasDt'][0]
            require(len(first)==8 and len(last)==8 and first<=last,'History date range')
            rows=[dict(srtnCd=code,basDt=first,clpr='110.1250'),dict(srtnCd=code,basDt=last,clpr='120.2500'),dict(srtnCd='FOREIGN',basDt=first,clpr='999999'),dict(srtnCd=code,basDt='INVALID',clpr='900'),dict(srtnCd=code,basDt=first,clpr='-1')]
            return 200,dict(response=dict(header=dict(resultCode='00',resultMsg='정상'),body=dict(totalCount=len(rows),numOfRows=1000,pageNo=1,items=dict(item=rows)))),'application/json'
        return 404,{},'application/json'


@contextmanager
def start_mock():
    fixture=ScheduleMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value,media='application/json'):
            raw=value if isinstance(value,bytes) else value.encode() if isinstance(value,str) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def handle_request(self):
            try:
                endpoint=urlsplit(self.path);size=int(self.headers.get('Content-Length','0'));require(0<=size<=100000,'Fixture length');body=self.rfile.read(size)
                if endpoint.path=='/__test__/state':
                    if self.command=='POST':
                        value=json.loads(body);mode=value.get('mode','valid');require(mode in ('valid','incomplete','failure'),'Fixture mode')
                        with fixture.lock:
                            fixture.mode=mode;fixture.delay=min(3,max(0,float(value.get('delay_seconds',0))))
                            if value.get('reset'):fixture.counts={}
                    return self.reply(200,fixture.state())
                status,value,media=fixture.response(self.command,endpoint.path,parse_qs(endpoint.query),body);self.reply(status,value,media)
            except (AssertionError,ValueError,KeyError,TypeError):self.reply(400,{})
        do_GET=handle_request;do_POST=handle_request
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield fixture
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


class ScheduleDatabase(TestDatabase):
    def seed(self,sql):
        env=self.env.copy();env['PGOPTIONS']='-c statement_timeout=10000'
        result=subprocess.run(['psql','-X','-A','-t','-w','-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose'],input='BEGIN;\n'+sql+'\nCOMMIT;',env=env,text=True,capture_output=True,timeout=20)
        if result.returncode:
            found=re.search(r'ERROR:\s+([0-9A-Z]{5}):',result.stderr)
            raise EnvironmentFailure('Fixture SQLSTATE '+(found.group(1) if found else 'unavailable'))


def safe_job_diagnostics(value):
    """Only protocol statuses/error codes/static provider labels, no payloads."""
    diagnostics=[]
    def visit(node):
        if isinstance(node,dict):
            row={}
            for key in ('code','provider','source','job'):
                field=node.get(key)
                if isinstance(field,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,59}',field):row[key]=field
            if type(node.get('status')) is int or node.get('status') in ('completed','partial','failed'):row['status']=node['status']
            for key in ('failedCount','failCount','fetchedCount','createdCount','updatedCount','unchangedCount','assetCount'):
                if type(node.get(key)) is int:row[key]=node[key]
            if row:diagnostics.append(row)
            for nested in node.values():
                if isinstance(nested,(dict,list)):visit(nested)
        elif isinstance(node,list):
            for nested in node:visit(nested)
    visit(value)
    return diagnostics[:16]


class ScheduleSuite:
    def __init__(self,binary,db,url):
        self.binary=binary;self.db=db;self.results=[];endpoint=urlsplit(url)
        validate_local_url(endpoint.scheme+'://'+endpoint.netloc);require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid schedule control URL');self.control_url=url
    def control(self,mode=None,delay=0):
        endpoint=urlsplit(self.control_url);c=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            c.request('POST' if mode else 'GET',endpoint.path,json.dumps(dict(mode=mode,delay_seconds=delay,reset=True)) if mode else None,{'Content-Type':'application/json'})
            r=c.getresponse();require(r.status==200,'Schedule fixture unavailable');return json.loads(r.read(65536))
        finally:c.close()
    def command(self,job,status=200):
        result=subprocess.run([str(self.binary),'--job',job],capture_output=True,text=True,timeout=90,env=os.environ.copy())
        require(len(result.stdout)<1000000,'CLI output excessive')
        try:value=json.loads(result.stdout)
        except ValueError:raise AssertionError('CLI must output exactly one JSON object') from None
        require(set(value)=={'status','result'},'CLI exact envelope')
        require(value['status']==status,'job.status expected '+str(status)+' actual '+str(value['status'])+' diagnostics '+json.dumps(safe_job_diagnostics(value),ensure_ascii=True));equal(result.returncode,0 if 200<=status<300 and status!=207 else 1,'job.exit-code')
        return value['result']
    def run(self,name,fn):
        try:fn();self.results.append(dict(case=name,passed=True))
        except AssertionError as error:self.results.append(dict(case=name,passed=False,reason=str(error)))
        except EnvironmentFailure as error:
            message=str(error);reason=message if re.fullmatch(r'Fixture SQLSTATE ([0-9A-Z]{5}|unavailable)',message) else 'Execution/fixture dependency failed (details withheld)'
            self.results.append(dict(case=name,passed=False,reason=reason))
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))
    @contextmanager
    def normal_server(self,enabled=False):
        env={key:value for key,value in os.environ.items() if not(key.startswith('JOB_SCHEDULER_') or key.endswith('_SYNC_ENABLED') or key.endswith('_SYNC_CRON'))}
        env['PORT']='0'
        if enabled:env.update(JOB_SCHEDULER_ENABLED='true',JOB_SCHEDULER_JOBS='exchange-rate',EXCHANGE_RATE_SYNC_ENABLED='true',EXCHANGE_RATE_SYNC_CRON='* * * * * *')
        with tempfile.TemporaryDirectory(prefix='schedule-native-') as directory:
            path=Path(directory)/'runtime.log'
            with path.open('wb') as log:
                process=subprocess.Popen([str(self.binary)],stdout=log,stderr=log,env=env,start_new_session=True)
            try:
                deadline=time.monotonic()+10;address=None
                while time.monotonic()<deadline:
                    require(process.poll() is None,'Normal binary exited before readiness')
                    match=re.search(r'event=server.started address=(127\.0\.0\.1:\d+)',path.read_text(errors='replace'))
                    if match:address=match.group(1);break
                    threading.Event().wait(0.05)
                require(address is not None,'Normal binary readiness timeout')
                host,port=address.split(':')
                connection=http.client.HTTPConnection(host,int(port),timeout=3)
                try:
                    connection.request('GET','/api/auth/csrf');response=connection.getresponse();response.read(65536)
                    equal(response.status,200,'server.healthy-csrf')
                finally:connection.close()
                yield process
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                        raise AssertionError('Normal binary shutdown exceeded15seconds') from None
                equal(process.returncode,0,'server.clean-shutdown-exit')

    def calendar_hash(self):return self.db.query("SELECT to_json(md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY base_date)::text,'[]'))) FROM(SELECT * FROM market_trading_days WHERE extract(year FROM base_date)="+str(YEAR)+')t')
    def main(self):
        def annual():
            self.control('valid');self.command('market-calendar')
            actual=self.db.query("SELECT json_agg(t ORDER BY base_date) FROM(SELECT base_date,trading FROM market_trading_days WHERE extract(year FROM base_date)="+str(YEAR)+')t')
            expected=[];day=date(YEAR,1,1)
            while day.year==YEAR:
                expected.append(dict(base_date=day.isoformat(),trading=day.weekday()<5 and day not in holidays(YEAR)));day+=timedelta(days=1)
            equal(actual,expected,'db.job.complete-authoritative-calendar')
            before=self.calendar_hash();self.command('market-calendar');equal(self.calendar_hash(),before,'db.job.calendar-idempotent')
        self.run('job-market-calendar-full-year-weekends-holidays-upsert-idempotent',annual)
        def incomplete():
            self.control('incomplete');before=self.calendar_hash()
            self.command('market-calendar',502);equal(self.calendar_hash(),before,'db.job.incomplete-calendar-preserves-existing')
        self.run('job-market-calendar-incomplete-holidays-fails-preserves-existing',incomplete)
        def calendar_failure():
            self.control('failure');before=self.calendar_hash();self.command('market-calendar',502);equal(self.calendar_hash(),before,'db.job.calendar-provider-failure-no-writes')
        self.run('job-market-calendar-provider-failure-preserves-existing',calendar_failure)
        def fx():
            self.control('valid');self.db.seed('INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at) VALUES('+literal(TODAY.isoformat())+','+literal(FX_DAY.isoformat())+",1,now()) ON CONFLICT(requested_date) DO UPDATE SET rate=1,fetched_at=now();")
            value=self.command('exchange-rate');require(self.control()['counts'].get('/eod/USDKRW.FOREX')==1,'Scheduled FX must force provider refresh despite fresh cache')
            equal(self.db.query('SELECT to_json(rate) FROM usd_krw_rates WHERE requested_date='+literal(TODAY.isoformat())),Decimal('1350.123456'),'db.job.fx-exact-refreshed-rate')
        self.run('job-fx-forces-refresh-fresh-cache-and-persists-exact-decimal',fx)
        def fx_failure():
            self.control('failure');before=self.db.query("SELECT to_json(md5(coalesce(jsonb_agg(to_jsonb(t))::text,'[]'))) FROM usd_krw_rates t")
            self.command('exchange-rate',502);equal(self.db.query("SELECT to_json(md5(coalesce(jsonb_agg(to_jsonb(t))::text,'[]'))) FROM usd_krw_rates t"),before,'db.job.fx-failure-retains-cache')
        self.run('job-fx-provider-failure-retains-prior-success',fx_failure)
        def concurrent():
            self.control('valid',delay=3)
            process=subprocess.Popen([str(self.binary),'--job','exchange-rate'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy())
            try:
                deadline=time.monotonic()+10
                while self.control()['counts'].get('/eod/USDKRW.FOREX',0)==0:
                    require(process.poll() is None,'First CLI exited before provider request')
                    require(time.monotonic()<deadline,'First CLI did not reach provider')
                    threading.Event().wait(0.02)
                value=self.command('exchange-rate',409)
                require(isinstance(value,dict) and isinstance(value.get('code'),str),'Concurrent conflict must expose structured error')
                output,_=process.communicate(timeout=15);first=json.loads(output)
                equal(first['status'],200,'job.first-concurrent-status');equal(process.returncode,0,'job.first-concurrent-exit')
                equal(self.control()['counts'].get('/eod/USDKRW.FOREX'),1,'provider.conflicting-job-must-not-call')
            finally:
                if process.poll() is None:process.kill();process.communicate(timeout=5)
                self.control('valid')
        self.run('job-shared-database-advisory-lock-rejects-concurrent-same-job',concurrent)
        def snapshots():
            d1=TODAY-timedelta(days=3);d2=TODAY-timedelta(days=2)
            self.db.seed("DELETE FROM portfolios WHERE member_id=970001; DELETE FROM stock_daily_prices WHERE asset_id=970001; INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES(970001,'GOOGLE','schedule-fixture','schedule@fixture.invalid','ScheduleFixture','USER','ACTIVE',now(),now()) ON CONFLICT(id) DO UPDATE SET status='ACTIVE'; INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES(970001,'Schedule Fixture','STOCK','987001','KOSPI',true,now(),now()) ON CONFLICT(id) DO UPDATE SET market='KOSPI'; INSERT INTO portfolios(id,member_id,created_at,updated_at) VALUES(970001,970001,now(),now()); INSERT INTO portfolio_holdings(portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES(970001,970001,2,100,now(),now()); INSERT INTO portfolio_holding_histories(portfolio_id,asset_id,change_type,quantity,average_purchase_price,transaction_quantity,unit_price,exchange_rate,effective_date,created_at,updated_at) VALUES(970001,970001,'BUY',2,100,2,100,1,"+literal(d1.isoformat())+",now(),now()); INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(970001,"+literal(d1.isoformat())+",110,now(),now()),(970001,"+literal(d2.isoformat())+",120,now(),now());")
            self.control('valid');self.command('portfolio-snapshots')
            query="SELECT json_agg(t ORDER BY base_date) FROM(SELECT base_date,total_purchase_amount,total_evaluation_amount,total_profit_loss,total_return_rate FROM portfolio_daily_snapshots WHERE portfolio_id=970001)t"
            expected=[dict(base_date=d1.isoformat(),total_purchase_amount=200,total_evaluation_amount=220,total_profit_loss=20,total_return_rate=10),dict(base_date=d2.isoformat(),total_purchase_amount=200,total_evaluation_amount=240,total_profit_loss=40,total_return_rate=20)]
            equal(self.db.query(query),expected,'db.job.snapshot-history-calculation');self.command('portfolio-snapshots');equal(self.db.query(query),expected,'db.job.snapshot-idempotent')
        self.run('job-portfolio-snapshots-replays-buy-history-and-idempotent',snapshots)
        def investment():
            self.control('valid');self.command('investment-calendar')
            keys=['BLS-CPI-'+str(YEAR)+'-01','BOK-BASE-RATE-'+str(YEAR)+'-01-15','DART-EARNINGS-'+CODE+'-'+str(YEAR)+'-03-31']
            actual=self.db.query('SELECT json_agg(t ORDER BY source_key) FROM(SELECT source_key,event_type,previous_value,actual_value,value_unit,related_asset_code FROM investment_events WHERE source_key IN('+','.join(map(literal,keys))+'))t')
            expected=[dict(source_key=keys[0],event_type='US_CPI',previous_value=20,actual_value=10,value_unit='%',related_asset_code=None),dict(source_key=keys[1],event_type='KOREA_BASE_RATE',previous_value=Decimal('3.5'),actual_value=Decimal('3.25'),value_unit='%',related_asset_code=None),dict(source_key=keys[2],event_type='CORPORATE_EARNINGS',previous_value=200,actual_value=250,value_unit='백만원',related_asset_code=CODE)]
            equal(actual,expected,'db.job.actual-bls-bok-dart-values')
            require(self.control()['counts'].get('/document.xml',0)>=1,'Actual zipped DART disclosure must be fetched')
            self.command('investment-calendar');equal(self.db.query('SELECT count(*) FROM investment_events WHERE source_key IN('+','.join(map(literal,keys))+')'),3,'db.job.events-source-key-upsert-idempotent')
        self.run('job-investment-calendar-real-bls-bok-dart-zip-import-values-idempotent',investment)
        def historical():
            self.control('valid');self.command('investment-calendar')
            requested=TODAY.replace(year=YEAR-1).isoformat()
            actual=self.db.query('SELECT json_agg(t ORDER BY base_date) FROM(SELECT base_date,close_price FROM stock_daily_prices WHERE asset_id=970001 AND base_date IN('+literal(requested)+','+literal(TODAY.isoformat())+'))t')
            equal(actual,[dict(base_date=requested,close_price=Decimal('110.1250')),dict(base_date=TODAY.isoformat(),close_price=Decimal('120.2500'))],'db.job.public-history-exact-prices')
            equal(self.db.query('SELECT to_json(price_history_from<='+literal(requested)+'::date) FROM assets WHERE id=970001'),True,'db.job.history-coverage-recorded')
            equal(self.db.query('SELECT count(*) FROM stock_daily_prices WHERE asset_id=970001 AND(close_price=999999 OR close_price<0)'),0,'db.job.history-filters-other-code-negative')
        self.run('job-investment-public-data-history-exact-prices-filter-and-coverage',historical)
        def history_idempotent():
            self.control('valid')
            query="SELECT to_json(md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY base_date)::text,'[]'))) FROM(SELECT * FROM stock_daily_prices WHERE asset_id=970001)t"
            before=self.db.query(query);self.command('investment-calendar');equal(self.db.query(query),before,'db.job.historical-prices-byte-idempotent')
            equal(self.control()['counts'].get('/kr/history/stock',0),0,'provider.history-complete-zero-refetch')
        self.run('job-investment-complete-history-idempotent-no-provider-refetch',history_idempotent)
        def disabled_scheduler():
            self.control('valid')
            with self.normal_server() as process:
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    require(process.poll() is None,'Default server exited during observation')
                    equal(self.control()['counts'],{},'scheduler.default-zero-provider-calls')
                    threading.Event().wait(min(0.1,max(0,deadline-time.monotonic())))
                equal(self.control()['counts'],{},'scheduler.default-remains-disabled')
        self.run('scheduler-default-normal-server-healthy-two-seconds-no-provider-calls',disabled_scheduler)
        def enabled_scheduler():
            self.control('valid')
            with self.normal_server(enabled=True) as process:
                deadline=time.monotonic()+5
                while self.control()['counts'].get('/eod/USDKRW.FOREX',0)<2:
                    require(process.poll() is None,'Enabled server exited before recurring jobs')
                    require(time.monotonic()<deadline,'Explicit scheduler did not execute two recurring FX jobs within5seconds')
                    threading.Event().wait(0.05)
                counts=self.control()['counts']
                require(set(counts)=={'/eod/USDKRW.FOREX'},'Only explicitly selected FX job may call providers')
            # A real one-shot job after clean scheduler shutdown proves its
            # driver/advisory lock is released, rather than merely process exit.
            self.command('exchange-rate')
        self.run('scheduler-explicit-recurring-fx-clean-shutdown-releases-advisory-lock',enabled_scheduler)
        self.control('valid')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',required=True,type=Path);parser.add_argument('--database',required=True);parser.add_argument('--mock-control-url',required=True);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    report=dict(contract='Independent original scheduled-provider CLI and PostgreSQL contracts',results=[],environmentLimited=[dict(case='real-external-scheduled-providers',status='unverified',reason='Background and one-shot jobs use deterministic local fixtures; real provider infrastructure not exercised')])
    try:
        require(args.binary.is_file(),'CLI binary missing');db=ScheduleDatabase(args.database)
        require(os.environ.get('DATABASE_URL')==args.database,'Coordinator must supply matching dedicated database environment')
        suite=ScheduleSuite(args.binary.resolve(),db,args.mock_control_url);suite.main();report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']);report['failed']=len(report['results'])-report['passed'];args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],failed=report['failed'])));return int(report['failed']>0)


if __name__=='__main__':sys.exit(main())
