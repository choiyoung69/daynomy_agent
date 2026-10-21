#!/usr/bin/env python3
"""Independent F03/F05 local FX-provider HTTP/PG checks; no real EODHD calls.

Basis: ExchangeRateService/Controller/Response, EodhdClient, UsdKrwRate and saved
portfolio snapshot flow in original Java. Only coordinator starts the candidate
and serializes this checker against the dedicated local *_service_test DB.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date,datetime,timedelta
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure,require,validate_local_url
from sample_feature_gate import encode
from service_acceptance import TestDatabase,equal
from service_core_acceptance import Suite,literal

MEMBER,ASSET=940191,940191
RATE=Decimal('1300.123456')
PUBLIC='/api/exchange-rates/usd-krw?date='
PORTFOLIO='/api/users/me/portfolio'
TODAY=datetime.now(ZoneInfo('Asia/Seoul')).date()
_days=[]; _cursor=TODAY-timedelta(days=1)
while len(_days)<2:
    if _cursor.weekday()<5:_days.append(_cursor)
    _cursor-=timedelta(days=1)
D1,D2=sorted(_days)


class FXMock:
    def __init__(self):
        self.lock=threading.Lock();self.mode='exact';self.delay=0;self.calls=0;self.last=None;self.server=None
        self.token=base64.urlsafe_b64encode(os.urandom(18)).decode()

    @property
    def base_url(self):return 'http://127.0.0.1:'+str(self.server.server_port)

    @property
    def environment(self):return dict(EODHD_BASE_URL=self.base_url,EODHD_API_TOKEN=self.token)

    @property
    def control_url(self):return self.base_url+'/__test__/state'

    def state(self):
        with self.lock:return dict(mode=self.mode,delay_seconds=self.delay,calls=self.calls,last_range=self.last)


@contextmanager
def start_mock():
    fixture=FXMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,status,value):
            raw=encode(value).encode();self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

        def do_POST(self):
            try:
                if self.path!='/__test__/state':return self.reply(404,{})
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=10000:return self.reply(400,{})
                value=json.loads(self.rfile.read(size));mode=value.get('mode','exact')
                if mode not in ('exact','fallback','empty','failure','filtered'):return self.reply(400,{})
                with fixture.lock:
                    fixture.mode=mode;fixture.delay=max(0,min(3,float(value.get('delay_seconds',0))))
                    if value.get('reset'):fixture.calls=0;fixture.last=None
                self.reply(200,fixture.state())
            except (ValueError,KeyError,TypeError):self.reply(400,{})

        def do_GET(self):
            if self.path=='/__test__/state':return self.reply(200,fixture.state())
            endpoint=urlsplit(self.path)
            if endpoint.path!='/eod/USDKRW.FOREX':return self.reply(404,{})
            query=parse_qs(endpoint.query)
            if query.get('api_token')!=[fixture.token] or query.get('fmt')!=['json']:return self.reply(401,{})
            try:
                start=date.fromisoformat(query['from'][0]);end=date.fromisoformat(query['to'][0])
                if end-start!=timedelta(days=14):return self.reply(400,{})
                with fixture.lock:
                    fixture.calls+=1;fixture.last=dict(start=start.isoformat(),end=end.isoformat());mode,delay=fixture.mode,fixture.delay
                if delay:time.sleep(delay)
                if mode=='failure':return self.reply(503,dict(error='fixture unavailable'))
                if mode=='empty':return self.reply(200,[])
                selected=end-timedelta(days=1) if mode=='fallback' else end
                values=[dict(date=selected.isoformat(),close=RATE)]
                if mode=='filtered':
                    values=[dict(date=(end+timedelta(days=1)).isoformat(),close=9999),dict(date=start.isoformat(),close=-1),dict(date=end.isoformat(),close=0),dict(date=(end-timedelta(days=1)).isoformat(),close=RATE),dict(date=(start-timedelta(days=1)).isoformat(),close=8888)]
                self.reply(200,values)
            except (ValueError,KeyError,TypeError):self.reply(400,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield fixture
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


def fixture_sql():
    sql="DELETE FROM portfolios WHERE member_id=940191; DELETE FROM stock_daily_prices WHERE asset_id=940191; DELETE FROM usd_krw_rates WHERE requested_date BETWEEN '2020-02-01' AND '2020-02-20';\n"
    sql+='DELETE FROM usd_krw_rates WHERE requested_date IN('+literal(D1.isoformat())+','+literal(D2.isoformat())+');\n'
    sql+="INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES(940191,'GOOGLE','fx-provider-fixture','fx@fixture.invalid','FXFixture','USER','ACTIVE',now(),now()) ON CONFLICT(id) DO UPDATE SET role='USER',status='ACTIVE',withdrawn_at=NULL;\n"
    sql+="INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES(940191,'FX Fixture America','STOCK','FXFIXTURE','NASDAQ',true,now(),now()) ON CONFLICT(id) DO UPDATE SET name=excluded.name,market=excluded.market;\n"
    sql+="INSERT INTO portfolios(id,member_id,created_at,updated_at) VALUES(940191,940191,now(),now());\n"
    for when,price in ((D1,12),(D2,14)):
        sql+='INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(940191,'+literal(when.isoformat())+','+str(price)+',now(),now());\n'
    return sql


class FXSuite(Suite):
    def client(self,member=MEMBER,token=None):return super().client(member,token)

    def run(self,name,fn):
        try:self.db.seed(fixture_sql());fn();self.results.append(dict(case=name,passed=True))
        except AssertionError as error:self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))

    def control(self,**data):
        endpoint=urlsplit(self.control_url);connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            connection.request('POST' if data else 'GET',endpoint.path,json.dumps(data) if data else None,{'Content-Type':'application/json'})
            response=connection.getresponse();require(response.status==200,'FX mock control unavailable');return json.loads(response.read(65536))
        finally:connection.close()

    def provider(self,mode='exact',delay=0):return self.control(mode=mode,delay_seconds=delay,reset=True)

    def quote(self,when,base=None,unchanged=False):
        return self.request(self.client(None),'GET',PUBLIC+when,200,expected=dict(requestedDate=when,baseDate=base or when,rate=RATE,baseCurrency='USD',quoteCurrency='KRW'),unchanged=unchanged)[0]

    def buy_data(self):return dict(assetId=ASSET,type='BUY',tradeDate=D1.isoformat(),quantity=4,unitPrice='10',fee='0',tax='0',exchangeRate='1000')

    def check_snapshot(self):
        expected=[dict(baseDate=D1.isoformat(),purchase=Decimal('40000'),evaluation=Decimal('62405.93')),
                  dict(baseDate=D2.isoformat(),purchase=Decimal('40000'),evaluation=Decimal('72806.91'))]
        actual=self.db.query("SELECT json_agg(t ORDER BY \"baseDate\") FROM(SELECT base_date AS \"baseDate\",total_purchase_amount AS purchase,total_evaluation_amount AS evaluation FROM portfolio_daily_snapshots WHERE portfolio_id=940191 AND base_date IN("+literal(D1.isoformat())+','+literal(D2.isoformat())+'))t')
        equal(actual,expected,'db.fx.historical-snapshot')

    def main(self,control_url):
        endpoint=urlsplit(control_url);validate_local_url(endpoint.scheme+'://'+endpoint.netloc)
        require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid FX control path');self.control_url=control_url
        def exact():
            self.provider();self.quote('2020-02-01')
            equal(self.db.query("SELECT to_json(rate) FROM usd_krw_rates WHERE requested_date='2020-02-01'"),RATE,'db.fx.exact-decimal')
            equal(self.control()['calls'],1,'provider.one-quote')
        self.run('fx-provider-exact-six-decimal-rate-persists',exact)
        def fallback():self.provider('fallback');self.quote('2020-02-02','2020-02-01')
        self.run('fx-provider-last-stored-business-date-fallback',fallback)
        def cache():
            self.provider();self.quote('2020-02-03');self.provider('failure');self.quote('2020-02-03',unchanged=True)
            equal(self.control()['calls'],0,'provider.cache.no-calls')
        self.run('fx-persisted-cache-survives-provider-failure-with-zero-calls',cache)
        def empty():
            self.provider('empty')
            for _ in range(2):self.request(self.client(None),'GET',PUBLIC+'2020-02-04',503,expected=dict(code='EXCHANGE_RATE_UNAVAILABLE',message='해당 날짜의 USD/KRW 환율을 가져오지 못했습니다.'),unchanged=True)
            equal(self.control()['calls'],1,'provider.unavailable.negative-cache')
        self.run('fx-empty-provider-response-unavailable-negative-cache',empty)
        def failure():
            self.provider('failure');self.request(self.client(None),'GET',PUBLIC+'2020-02-05',502,expected=dict(code='EODHD_API_REQUEST_FAILED',message='EODHD API 요청에 실패했습니다.'),unchanged=True)
        self.run('fx-upstream-503-exact-error-no-persisted-writes',failure)
        def filtered():self.provider('filtered');self.quote('2020-02-06','2020-02-05')
        self.run('fx-filter-future-out-of-window-zero-negative-unsorted-rows',filtered)
        def historical():
            self.provider();self.request(self.client(),'POST',PORTFOLIO+'/transactions',201,self.buy_data())
            self.check_snapshot();require(self.control()['calls']>=2,'Historical valuation must fetch both price dates')
        self.run('fx-usd-trade-prefetches-missing-history-rates-and-exact-snapshots',historical)
        def rollback():
            self.provider('failure');self.request(self.client(),'POST',PORTFOLIO+'/transactions',502,self.buy_data(),expected=dict(code='EODHD_API_REQUEST_FAILED',message='EODHD API 요청에 실패했습니다.'),unchanged=True)
        self.run('fx-provider-failure-rolls-back-trade-holdings-snapshots',rollback)
        def no_lock():
            self.provider(delay=1);c=self.client()
            with ThreadPoolExecutor(1) as pool:
                pending=pool.submit(c.send,'POST',PORTFOLIO+'/transactions',self.buy_data())
                deadline=time.monotonic()+8
                while not self.control()['calls']:
                    require(time.monotonic()<deadline,'Delayed FX request did not start');time.sleep(.02)
                self.db.seed("SET LOCAL lock_timeout='250ms'; UPDATE portfolios SET updated_at=updated_at WHERE id=940191;")
                status,_,_=pending.result(timeout=15)
            require(status==201,'Trade must succeed after unlocked provider wait');self.check_snapshot()
        self.run('fx-provider-wait-does-not-hold-portfolio-row-lock',no_lock)
        self.provider()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--database',required=True);parser.add_argument('--jwt-secret-file',required=True,type=Path)
    parser.add_argument('--issuer',default='daynomy');parser.add_argument('--mock-control-url',required=True);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    report=dict(contract='Independent original FX provider/cache and USD snapshot checks',results=[],passed=0,failed=0,environmentLimited=[dict(case='real-eodhd-provider',status='unverified',reason='Deterministic local fixture only; no external provider network call')])
    try:
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True);require(len(key)>=32,'JWT fixture key too short')
        suite=FXSuite(validate_local_url(args.base_url),TestDatabase(args.database),key,args.issuer);suite.main(args.mock_control_url);report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']);report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])));return int(report['failed']>0)


if __name__=='__main__':sys.exit(main())
