#!/usr/bin/env python3
"""Independent F13 native synchronization contracts from original Java V1..53.

Five admin routes, real provider wire/DB persistence, isolated loopback mocks.
No app implementation imported/read. Coordinator serializes all database use.
Reserve 950001..950099 and feed codes 986001..986006/SYNC*.US. Master feeds
intentionally delist absent securities in their own market, as the original does.
"""
import argparse
import base64
from contextlib import contextmanager
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure,require,validate_local_url
from sample_feature_gate import encode
from service_acceptance import TestDatabase,equal
from service_core_acceptance import Suite,literal

ADMIN,USER=950001,950002
KR_MASTER='/api/admin/stocks/sync';KR_PRICE='/api/admin/stocks/prices/sync';BACKFILL='/api/admin/stocks/prices/backfill'
US_MASTER='/api/admin/stocks/us/sync';US_PRICE='/api/admin/stocks/us/prices/sync'
TODAY=datetime.now(ZoneInfo('Asia/Seoul')).date();NY_TODAY=datetime.now(ZoneInfo('America/New_York')).date()
_closed=[];_cursor=TODAY-timedelta(days=1)
while len(_closed)<2:
    if _cursor.weekday()<5:_closed.append(_cursor)
    _cursor-=timedelta(days=1)
DAY,NEXT=sorted(_closed);US_DAY='2020-02-10'
ROUTES=[KR_MASTER,KR_PRICE,BACKFILL+'?from='+DAY.isoformat()+'&to='+DAY.isoformat(),US_MASTER,US_PRICE+'?date='+US_DAY]


class SyncMock:
    def __init__(self):
        self.lock=threading.Lock();self.mode='valid';self.calls={};self.server=None
        self.key=base64.urlsafe_b64encode(os.urandom(18)).decode()

    @property
    def base_url(self):return 'http://127.0.0.1:'+str(self.server.server_port)

    @property
    def control_url(self):return self.base_url+'/__test__/state'

    @property
    def environment(self):
        return dict(EODHD_BASE_URL=self.base_url,EODHD_API_TOKEN=self.key,PUBLIC_DATA_SERVICE_KEY=self.key,
                    PUBLIC_DATA_LISTED_STOCK_URL=self.base_url+'/kr/listed',PUBLIC_DATA_STOCK_PRICE_URL=self.base_url+'/kr/prices',PUBLIC_DATA_ETF_PRICE_URL=self.base_url+'/kr/etf')

    def state(self):
        with self.lock:return dict(mode=self.mode,calls=self.calls.copy())

    def payload(self,path,query):
        with self.lock:self.calls[path]=self.calls.get(path,0)+1;mode=self.mode
        if mode=='failure' or (mode=='fail-later' and query.get('basDt')==[NEXT.strftime('%Y%m%d')]):return 503,dict(error='fixture unavailable')
        if path.startswith('/kr/'):
            valid=(query.get('serviceKey')==[self.key] and query.get('numOfRows')==['1000'] and query.get('pageNo')==['1'] and query.get('resultType')==['json'])
            if not valid:return 400,{}
            when=query['basDt'][0]
            if path=='/kr/listed':
                rows=[dict(basDt=when,srtnCd=code,isinCd='KR7'+code.lstrip('A')+'001',mrktCtg=market,itmsNm=name) for code,market,name in [('A986001','KOSPI','Sync Korea'),('986002','KOSDAQ','Sync Kosdaq'),('986006','KOSPI','Sync New'),('986004','KOSPI','Sync 우'),('986005','KOSPI','Sync SPAC')]]
            elif path=='/kr/etf':rows=[dict(basDt=when,srtnCd='986003',isinCd='KR7986003001',itmsNm='Sync ETF',clpr='20.2500')]
            elif path=='/kr/prices':
                market=query.get('mrktCls',[''])[0]
                if market not in ('KOSPI','KOSDAQ'):return 400,{}
                code='986001' if market=='KOSPI' else '986002'
                rows=[dict(basDt=when,srtnCd=code,itmsNm='Sync stock',mrktCtg=market,clpr=('111.1250' if mode=='revised' else '101.1250') if market=='KOSPI' else '55.5000'),
                      dict(basDt=when,srtnCd='INVALID',itmsNm='Invalid code',mrktCtg=market,clpr='999'),
                      dict(basDt=when,srtnCd='986009',itmsNm='Zero price',mrktCtg=market,clpr='0')]
            else:return 404,{}
            return 200,dict(response=dict(header=dict(resultCode='99' if mode=='bad-header' else '00',resultMsg='Fixture'),body=dict(numOfRows=1000,pageNo=1,totalCount=len(rows),items=dict(item=rows))))
        if query.get('api_token')!=[self.key] or query.get('fmt')!=['json']:return 401,{}
        if path=='/exchange-symbol-list/US':
            rows=[dict(Code=code,Name=name,Exchange=exchange,Currency='USD',Type=kind,Isin='') for code,name,exchange,kind in [('SYNCSTOCK','Sync America','NASDAQ','Common Stock'),('SYNCETF','Sync US ETF','NYSE ARCA','ETF'),('SYNCNEW','Sync US New','NYSE','Common Stock'),('EXCLUDE','Excluded fund','NASDAQ','Mutual Fund'),('OTCFEED','Excluded OTC','OTC','Common Stock')]]
            if mode=='duplicate':rows.append(rows[0].copy())
            return 200,rows
        if path=='/eod-bulk-last-day/US':
            when=query['date'][0]
            return 200,[dict(code='SYNCSTOCK',date=when,close=Decimal('12.3456'),adjusted_close=999),dict(code='SYNCETF',date=when,close=Decimal('25.1250')),
                        dict(code='UNKNOWN',date=when,close=99),dict(code='SYNCNEW',date=when,close=0)]
        return 404,{}


@contextmanager
def start_mock():
    fixture=SyncMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,status,value):
            raw=encode(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

        def do_GET(self):
            if self.path=='/__test__/state':return self.reply(200,fixture.state())
            endpoint=urlsplit(self.path)
            try:status,value=fixture.payload(endpoint.path,parse_qs(endpoint.query));self.reply(status,value)
            except (ValueError,KeyError,TypeError):self.reply(400,{})

        def do_POST(self):
            try:
                if self.path!='/__test__/state':return self.reply(404,{})
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=10000:return self.reply(400,{})
                value=json.loads(self.rfile.read(size));mode=value.get('mode','valid')
                if mode not in ('valid','failure','bad-header','duplicate','revised','fail-later'):return self.reply(400,{})
                with fixture.lock:
                    fixture.mode=mode
                    if value.get('reset'):fixture.calls={}
                self.reply(200,fixture.state())
            except (ValueError,KeyError,TypeError):self.reply(400,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield fixture
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


def fixture_sql():
    sql="DELETE FROM portfolios WHERE member_id=950002; DELETE FROM stock_daily_prices WHERE asset_id IN(SELECT id FROM assets WHERE asset_code IN('986001','986002','986003','986006','SYNCSTOCK.US','SYNCETF.US','SYNCNEW.US')); DELETE FROM assets WHERE asset_code IN('986006','SYNCNEW.US');\n"
    for member,role in ((ADMIN,'ADMIN'),(USER,'USER')):
        sql+='INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES('+','.join(map(literal,[member,'GOOGLE','sync-fixture-'+str(member),str(member)+'@fixture.invalid','Sync'+str(member),role,'ACTIVE']))+",now(),now()) ON CONFLICT(id) DO UPDATE SET role=excluded.role,status='ACTIVE',withdrawn_at=NULL;\n"
    for ident,code,category,market in [(950011,'986001','STOCK','KOSPI'),(950012,'986002','STOCK','KOSDAQ'),(950013,'986003','ETF','KOSPI'),(950014,'SYNCSTOCK.US','STOCK','NASDAQ'),(950015,'SYNCETF.US','ETF','NYSE_ARCA')]:
        sql+='INSERT INTO assets(id,name,category,asset_code,market,listed,stock_base_date,created_at,updated_at) VALUES('+','.join(map(literal,[ident,'Old Sync '+code,category,code,market]))+",true,'2000-01-01',now(),now()) ON CONFLICT(id) DO UPDATE SET name=excluded.name,listed=true,stock_base_date='2000-01-01',isin_code=NULL;\n"
    for when in (DAY,NEXT):
        sql+='INSERT INTO market_trading_days(base_date,trading,collected_at,last_attempted_at) VALUES('+literal(when.isoformat())+',true,NULL,NULL) ON CONFLICT(base_date) DO UPDATE SET trading=true,collected_at=NULL,last_attempted_at=NULL;\n'
    return sql


def prices_result(when,received,created=0,updated=0,skipped=0,dates=1,pending=0):
    return dict(baseDate=when,receivedCount=received,createdCount=created,updatedCount=updated,skippedCount=skipped,synchronizedDateCount=dates,pendingDateCount=pending,failedDateCount=0)


class SyncSuite(Suite):
    def client(self,member=ADMIN,token=None):
        c=super().client(member,token)
        if member==ADMIN:c.cookies['access_token']=token or self.jwt(ADMIN,role='ADMIN')
        return c

    def run(self,name,fn):
        try:self.db.seed(fixture_sql());fn();self.results.append(dict(case=name,passed=True))
        except AssertionError as error:self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))

    def provider(self,mode='valid'):
        endpoint=urlsplit(self.control_url);c=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:c.request('POST',endpoint.path,json.dumps(dict(mode=mode,reset=True)),{'Content-Type':'application/json'});r=c.getresponse();r.read(65536);require(r.status==200,'Sync mock control unavailable')
        finally:c.close()

    def error(self,path,code,message,status=502,unchanged=True):
        self.request(self.client(),'POST',path,status,expected=dict(code=code,message=message),unchanged=unchanged)

    def market_hash(self,us):
        condition="market IN('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS')" if us else "(market IN('KOSPI','KOSDAQ') OR market IS NULL)"
        return self.db.query("SELECT to_json(md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'[]'))) FROM(SELECT * FROM assets WHERE "+condition+')t')

    def kr_master(self):
        self.provider();other=self.market_hash(True)
        delisted=self.db.query("SELECT count(*) FROM assets WHERE listed AND category IN('STOCK','ETF') AND(market IN('KOSPI','KOSDAQ') OR market IS NULL) AND asset_code NOT IN('986001','986002','986003','986006')")
        expected=dict(baseDate=TODAY.isoformat(),syncedCount=4,createdCount=1,updatedCount=3,delistedCount=delisted)
        self.request(self.client(),'POST',KR_MASTER,200,expected=expected)
        equal(self.market_hash(True),other,'db.kr-master.other-market-immutable')
        rows=self.db.query("SELECT json_agg(t ORDER BY asset_code) FROM(SELECT asset_code,name,category,market,listed FROM assets WHERE asset_code IN('986001','986002','986003','986006'))t")
        equal(rows,[dict(asset_code='986001',name='Sync Korea',category='STOCK',market='KOSPI',listed=True),dict(asset_code='986002',name='Sync Kosdaq',category='STOCK',market='KOSDAQ',listed=True),dict(asset_code='986003',name='Sync ETF',category='ETF',market='KOSPI',listed=True),dict(asset_code='986006',name='Sync New',category='STOCK',market='KOSPI',listed=True)])
        equal(self.db.query("SELECT count(*) FROM assets WHERE asset_code IN('986004','986005')"),0,'db.preferred-spac-filter')
        self.request(self.client(),'POST',KR_MASTER,200,expected=dict(expected,createdCount=0,updatedCount=0,delistedCount=0),unchanged=True)

    def us_master(self):
        self.provider();other=self.market_hash(False)
        delisted=self.db.query("SELECT count(*) FROM assets WHERE listed AND category IN('STOCK','ETF') AND market IN('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS') AND asset_code NOT IN('SYNCSTOCK.US','SYNCETF.US','SYNCNEW.US')")
        expected=dict(baseDate=NY_TODAY.isoformat(),syncedCount=3,createdCount=1,updatedCount=2,delistedCount=delisted)
        self.request(self.client(),'POST',US_MASTER,200,expected=expected)
        equal(self.market_hash(False),other,'db.us-master.other-market-immutable')
        equal(self.db.query("SELECT count(*) FROM assets WHERE asset_code IN('EXCLUDE.US','OTCFEED.US')"),0,'db.us-feed-category-market-filter')
        self.request(self.client(),'POST',US_MASTER,200,expected=dict(expected,createdCount=0,updatedCount=0,delistedCount=0),unchanged=True)

    def price_rows(self,when,us=False):
        codes=['SYNCSTOCK.US','SYNCETF.US'] if us else ['986001','986002','986003']
        expected=[dict(asset_code=code,close_price=value) for code,value in zip(codes,[Decimal('12.3456'),Decimal('25.1250')] if us else [Decimal('101.1250'),Decimal('55.5000'),Decimal('20.2500')])]
        expected.sort(key=lambda row:row['asset_code'])
        actual=self.db.query("SELECT json_agg(t ORDER BY asset_code) FROM(SELECT a.asset_code,p.close_price FROM stock_daily_prices p JOIN assets a ON a.id=p.asset_id WHERE p.base_date="+literal(when)+" AND a.asset_code IN("+','.join(map(literal,codes))+'))t')
        equal(actual,expected,'db.sync.actual-close-not-adjusted')

    def us_prices(self):
        self.provider();path=US_PRICE+'?date='+US_DAY
        self.request(self.client(),'POST',path,200,expected=prices_result(US_DAY,2,created=2))
        self.price_rows(US_DAY,True)
        self.request(self.client(),'POST',path,200,expected=prices_result(US_DAY,2,skipped=2),unchanged=True)

    def backfill(self):
        self.provider();path=BACKFILL+'?from='+DAY.isoformat()+'&to='+DAY.isoformat()
        expected=dict(from_=DAY.isoformat(),to=DAY.isoformat(),synchronizedDateCount=1,receivedCount=3,createdCount=3,updatedCount=0,skippedCount=0);expected['from']=expected.pop('from_')
        self.request(self.client(),'POST',path,200,expected=expected);self.price_rows(DAY.isoformat())
        self.request(self.client(),'POST',path,200,expected=dict(expected,createdCount=0,skippedCount=3))
        equal(self.db.query('SELECT to_json(collected_at IS NOT NULL) FROM market_trading_days WHERE base_date='+literal(DAY.isoformat())),True,'db.backfill.collected')

    def kr_prices(self):
        self.provider()
        selected=self.db.query("SELECT coalesce(json_agg(t ORDER BY base_date),'[]'::json) FROM(SELECT d.base_date,d.last_attempted_at FROM(SELECT base_date,collected_at,last_attempted_at,lead(base_date) OVER(ORDER BY base_date) AS next_day FROM market_trading_days WHERE trading AND base_date<="+literal(TODAY.isoformat())+")d WHERE collected_at IS NULL AND next_day IS NOT NULL AND now()>=(next_day+time '13:00') AT TIME ZONE 'Asia/Seoul' ORDER BY base_date)t")
        require(bool(selected),'Fixture requires at least one fully closed pending trading date')
        latest=selected[-1];older=sorted(selected[:-1],key=lambda row:(row['last_attempted_at'] is not None,row['last_attempted_at'] or '',-date.fromisoformat(row['base_date']).toordinal()))[:9]
        dates=sorted([latest['base_date']]+[row['base_date'] for row in older]);count=len(dates)
        pending=self.db.query('SELECT count(*) FROM market_trading_days WHERE trading AND collected_at IS NULL AND base_date<='+literal(TODAY.isoformat()))-count
        self.request(self.client(),'POST',KR_PRICE,200,expected=prices_result(dates[-1],3*count,created=3*count,dates=count,pending=pending))
        for when in dates:self.price_rows(when)

    def snapshot_fixture(self):
        self.provider()
        self.request(self.client(USER),'POST','/api/users/me/portfolio/transactions',201,
                     dict(assetId=950011,type='BUY',tradeDate=(DAY-timedelta(days=1)).isoformat(),quantity=2,unitPrice='80',fee='0',tax='0'))
        equal(self.db.query("SELECT count(*) FROM portfolio_daily_snapshots s JOIN portfolios p ON p.id=s.portfolio_id WHERE p.member_id=950002"),0,'db.pre-sync-no-price-no-snapshot')

    def snapshot_point(self,when,price):
        rows=self.db.query("SELECT json_agg(t) FROM(SELECT s.total_purchase_amount AS purchase,s.total_evaluation_amount AS evaluation,s.total_profit_loss AS profit FROM portfolio_daily_snapshots s JOIN portfolios p ON p.id=s.portfolio_id WHERE p.member_id=950002 AND s.base_date="+literal(when.isoformat())+")t")
        evaluation=(Decimal(price)*2).quantize(Decimal('0.01'))
        equal(rows,[dict(purchase=Decimal('160'),evaluation=evaluation,profit=evaluation-160)],'db.sync-refresh-historical-snapshot')

    def snapshot_hooks(self):
        one=BACKFILL+'?from='+DAY.isoformat()+'&to='+DAY.isoformat()
        def creates():
            self.snapshot_fixture();self.request(self.client(),'POST',one,200)
            self.snapshot_point(DAY,'101.1250')
        self.run('sync-kr-price-commit-creates-existing-buy-historical-point',creates)
        def revises():
            self.snapshot_fixture();self.request(self.client(),'POST',one,200);self.snapshot_point(DAY,'101.1250')
            self.provider('revised');self.request(self.client(),'POST',one,200)
            self.snapshot_point(DAY,'111.1250')
            equal(self.db.query("SELECT to_json(close_price) FROM stock_daily_prices WHERE asset_id=950011 AND base_date="+literal(DAY.isoformat())),Decimal('111.1250'),'db.revised-committed-price')
        self.run('sync-kr-corrected-close-revises-existing-historical-point',revises)
        def snapshot_failure():
            self.snapshot_fixture()
            # Original refreshAfterPriceSync catches snapshot failures after the
            # price transaction commits. Scope injection to this fixture member.
            self.db.seed("CREATE OR REPLACE FUNCTION fixture_sync_snapshot_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF EXISTS(SELECT 1 FROM portfolios WHERE id=NEW.portfolio_id AND member_id=950002) THEN RAISE EXCEPTION 'fixture snapshot failure'; END IF; RETURN NEW; END $$; CREATE TRIGGER fixture_sync_snapshot_fail BEFORE INSERT OR UPDATE ON portfolio_daily_snapshots FOR EACH ROW EXECUTE FUNCTION fixture_sync_snapshot_fail();")
            try:
                self.request(self.client(),'POST',one,200);self.price_rows(DAY.isoformat())
                equal(self.db.query("SELECT count(*) FROM portfolio_daily_snapshots s JOIN portfolios p ON p.id=s.portfolio_id WHERE p.member_id=950002"),0,'db.failed-snapshot-no-partial-row')
            finally:self.db.seed('DROP TRIGGER IF EXISTS fixture_sync_snapshot_fail ON portfolio_daily_snapshots; DROP FUNCTION IF EXISTS fixture_sync_snapshot_fail();')
        self.run('sync-snapshot-sql-failure-preserves-committed-prices',snapshot_failure)
        def partial():
            self.snapshot_fixture();self.provider('fail-later')
            self.error(BACKFILL+'?from='+DAY.isoformat()+'&to='+NEXT.isoformat(),'PUBLIC_DATA_API_REQUEST_FAILED','공공데이터 API 요청에 실패했습니다.',unchanged=False)
            self.price_rows(DAY.isoformat());self.snapshot_point(DAY,'101.1250')
            equal(self.db.query("SELECT count(*) FROM stock_daily_prices WHERE asset_id IN(950011,950012,950013) AND base_date="+literal(NEXT.isoformat())),0,'db.failed-later-date-uncommitted')
        self.run('sync-partial-backfill-finally-refreshes-first-committed-date',partial)

    def main(self,control_url):
        endpoint=urlsplit(control_url);validate_local_url(endpoint.scheme+'://'+endpoint.netloc);require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid sync control path');self.control_url=control_url
        for index,path in enumerate(ROUTES):
            for member,status,code in ((None,401,'UNAUTHORIZED'),(USER,403,'FORBIDDEN')):
                self.run('sync-auth-'+str(index)+'-'+str(member),lambda path=path,member=member,status=status,code=code:self.request(self.client(member),'POST',path,status,code=code,unchanged=True))
            def csrf(path=path):
                c=self.client();c.cookies.pop('XSRF-TOKEN',None);self.request(c,'POST',path,403,code='FORBIDDEN',unchanged=True,csrf=False)
            self.run('sync-csrf-'+str(index),csrf)
        self.run('sync-kr-master-filters-upserts-idempotent-market-coverage',self.kr_master)
        self.run('sync-us-master-filters-upserts-idempotent-market-coverage',self.us_master)
        self.run('sync-us-prices-exact-close-and-idempotent-upsert',self.us_prices)
        self.run('sync-kr-prices-eligible-calendar-batch-and-coverage',self.kr_prices)
        self.run('sync-kr-backfill-counts-prices-and-collected-state',self.backfill)
        self.run('sync-us-future-date-rejected',lambda:self.error(US_PRICE+'?date='+NY_TODAY.isoformat(),'INVALID_US_STOCK_PRICE_DATE','미국 종가는 뉴욕 기준 오늘 이전 날짜로 요청해주세요.',400))
        self.run('sync-backfill-reversed-period-rejected',lambda:self.error(BACKFILL+'?from=2020-02-02&to=2020-02-01','INVALID_STOCK_PRICE_BACKFILL_RANGE','종가 백필 기간은 31일 이내여야 합니다.',400))
        def duplicate():
            self.provider('duplicate');self.error(US_MASTER,'US_STOCK_MASTER_DATA_NOT_FOUND','동기화할 미국 종목 데이터를 확인하지 못했습니다.')
        self.run('sync-us-duplicate-symbol-invalid-no-writes',duplicate)
        def bad_header():
            self.provider('bad-header');self.error(KR_MASTER,'PUBLIC_DATA_API_REQUEST_FAILED','공공데이터 API 요청에 실패했습니다.')
        self.run('sync-kr-provider-error-header-not-success',bad_header)
        def failure():
            self.provider('failure');self.error(US_MASTER,'EODHD_API_REQUEST_FAILED','EODHD API 요청에 실패했습니다.')
        self.run('sync-us-upstream-failure-not-success',failure)
        self.snapshot_hooks()
        self.provider()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--database',required=True);parser.add_argument('--jwt-secret-file',required=True,type=Path);parser.add_argument('--issuer',default='daynomy');parser.add_argument('--mock-control-url',required=True);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    report=dict(contract='Independent original Java five-route sync provider/DB contracts',results=[],passed=0,failed=0,environmentLimited=[dict(case='real-external-collection',status='unverified',reason='Local deterministic EODHD/public-data fixtures only')])
    try:
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True);require(len(key)>=32,'JWT fixture key too short')
        suite=SyncSuite(validate_local_url(args.base_url),TestDatabase(args.database),key,args.issuer);suite.main(args.mock_control_url);report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']);report['failed']=len(report['results'])-report['passed'];args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],failed=report['failed'])));return int(report['failed']>0)


if __name__=='__main__':sys.exit(main())
