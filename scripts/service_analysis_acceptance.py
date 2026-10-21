#!/usr/bin/env python3
"""Independent F06 deterministic HTTP/PG contracts from original Java V1..53.

Covers validation, stored DTOs/states/history/reuse and processing exclusion with
real DB fixtures, not generated prose. External generation/refresh/trial exhaustion
need a separately coordinated mock provider and remain explicitly unverified.
IDs 940001..940099 reserved; coordinator serializes all database writers.
No server, provider, migration or model process is started by this checker.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import subprocess
import sys

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal
from service_core_acceptance import Suite, HTTP, literal

MEMBER, EMPTY = 940001, 940002
A, UNPRICED = 940001, 940002
P = '/api/users/me/portfolio/analysis'
PUBLIC = '/api/portfolio/analysis'
STAMP = '2090-01-01T00:00:00Z'
ERRORS = {
    'PORTFOLIO_ANALYSIS_ASSETS_UNAVAILABLE': '저장된 보유 자산과 가격이 있어야 분석할 수 있습니다.',
    'PORTFOLIO_ANALYSIS_ASSETS_CHANGED': '분석 대상 자산이 변경되었습니다. 다시 시도해주세요.',
    'PORTFOLIO_ANALYSIS_IN_PROGRESS': '포트폴리오 분석이 진행 중입니다.',
    'DUPLICATE_PORTFOLIO_ASSET': '포트폴리오에 중복된 종목이 있습니다.',
    'INVALID_PORTFOLIO_WEIGHT_TOTAL': '포트폴리오 보유 비중의 합은 100이어야 합니다.',
}


class AnalysisMock:
    """Loopback-only Responses fixture; never forwards a request to a provider.

    The coordinator enters start_mock() before server startup and passes its
    environment to Spring/Rust. Calls and modes are controllable without logging
    request text or credentials. The original uses developer/user message input;
    the direct JSON input form is accepted for adapter-level interoperability.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = 'supported'
        self.delay_seconds = 0
        self.counts = dict(search=0,narrative=0,errors=0)
        self.search_requests = []
        self.third_search_started = threading.Event()
        self.active_searches = 0
        self.max_active_searches = 0
        self.third_started_while_first_held = False
        self.key = base64.urlsafe_b64encode(os.urandom(24)).decode()
        self.as_of = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
        self.server = None

    @property
    def environment(self):
        return dict(AI_OPENAI_BASE_URL=self.base_url,AI_OPENAI_API_KEY=self.key,AI_OPENAI_MODEL='gpt-5-mini')

    @property
    def base_url(self):
        return 'http://127.0.0.1:'+str(self.server.server_port)+'/v1'

    @property
    def control_url(self):
        return 'http://127.0.0.1:'+str(self.server.server_port)+'/__test__/state'

    def state(self):
        with self.lock:
            return dict(mode=self.mode,counts=self.counts.copy(),as_of=self.as_of,delay_seconds=self.delay_seconds,search_requests=list(self.search_requests),
                        max_active_searches=self.max_active_searches,third_started_while_first_held=self.third_started_while_first_held)

    def respond(self, request):
        search = any(tool.get('type')=='web_search' for tool in request.get('tools',[]))
        if search:
            with self.lock:
                self.active_searches += 1
                self.max_active_searches = max(self.max_active_searches,self.active_searches)
        try:
            return self._respond(request)
        finally:
            if search:
                with self.lock: self.active_searches -= 1

    def _respond(self, request):
        search = any(tool.get('type')=='web_search' for tool in request.get('tools',[]))
        with self.lock:
            self.counts['search' if search else 'narrative'] += 1
            search_number = self.counts['search']
            mode = self.mode
            delay = self.delay_seconds
        if search and mode=='rolling-two':
            if search_number==3:
                self.third_search_started.set()
            elif search_number==1:
                # Fast batch two must free a slot for batch three without
                # waiting for batch one. Paired joins cannot satisfy this.
                observed=self.third_search_started.wait(timeout=3)
                with self.lock: self.third_started_while_first_held=observed
        if delay: time.sleep(delay)
        if mode in ('failure','rate-limit'):
            return (429 if mode=='rate-limit' else 503), dict(error=dict(code='fixture_unavailable',message='Fixture unavailable'))
        inputs = request.get('input')
        if isinstance(inputs,str): inputs=[dict(role='user',content=inputs)]
        assets=[]
        for entry in inputs or []:
            if entry.get('role')!='user': continue
            content=entry.get('content')
            try:
                value=json.loads(content) if isinstance(content,str) else content
                if isinstance(value,dict) and isinstance(value.get('assets'),list):
                    assets=value['assets']; break
            except ValueError:
                continue
        if not assets:
            with self.lock: self.counts['errors'] += 1
            return 400, dict(error=dict(code='fixture_bad_input',message='Expected assets'))
        properties=request.get('text',{}).get('format',{}).get('schema',{}).get('properties',{})
        impact_schema=properties.get('impacts',{})
        keyed=impact_schema.get('type')=='object'
        if search:
            with self.lock:
                # Only synthetic fixture names/weights and date are retained;
                # no bearer token, full prompt or provider text is recorded.
                self.search_requests.append(dict(assets=assets,as_of=value.get('asOfDate'),keyed=keyed,
                    required=impact_schema.get('required',[]),strict=request.get('text',{}).get('format',{}).get('strict')))
        sources=[]; impacts=[]
        for index,asset in enumerate(assets):
            name=asset['assetName']
            url='https://www.reuters.com/business/fixture-analysis-'+str(index)+'-'+self.as_of+'/'
            sources.append(dict(url=url,title='Fixture source'))
            impacts.append(dict(assetName=name,direction='POSITIVE' if mode!='insufficient' else None,
                impactLevel='HIGH' if mode!='insufficient' else None,
                issueSummary='회사가 신규 계약을 발표했어요.',
                expectedReaction='신규 계약은 향후 매출 증가에 도움이 될 수 있어요.',
                outlook='계약 이행과 매출 반영 여부를 확인해야 해요.',
                reason='계약 이행이 매출에 도움이 될 수 있어요.',
                sourceUrls=[url] if mode!='insufficient' else [],
                evidence=[dict(url=url,publishedOn=self.as_of,occurredOn=self.as_of,
                               excerpt='회사가 신규 계약 체결을 발표했어요.',factQuote='회사는 신규 계약 체결을 발표했다.')] if mode!='insufficient' else []))
        if search:
            for impact in impacts:
                selected=impact['assetName']=='Analysis Beta' or len(impacts)==1
                first_bad=search_number==1 and selected
                if mode in ('partial-insufficient','missing-correction-target') and first_bad:
                    impact.update(direction=None,impactLevel=None,sourceUrls=[],evidence=[])
                if mode=='partial-prose' and first_bad:
                    impact['issueSummary']='Unacceptable English prose is supplied here.'
                if (mode=='partial-date' and first_bad) or mode=='fabricated-date':
                    impact['issueSummary']='1998-02-03에 회사가 신규 계약을 발표했어요.'
                if mode=='unattached-source':
                    impact['sourceUrls']=['https://www.reuters.com/business/not-returned-by-search/']
                    impact['evidence'][0]['url']=impact['sourceUrls'][0]
                if mode=='attached-date':
                    impact['issueSummary']=self.as_of+'에 회사가 신규 계약을 발표했어요.'
                if mode=='persistent-insufficient':
                    impact.update(direction=None,impactLevel=None,sourceUrls=[],evidence=[])
            if mode=='missing-correction-target' and search_number>1:
                impacts=[]
            if keyed:
                value=dict(impacts={item['assetName']:{key:val for key,val in item.items() if key!='assetName'} for item in impacts})
            else:
                value=dict(overallImpact='확인된 계약이 매출 증가에 도움이 될 수 있어요.',impacts=impacts)
        else:
            impact='확인된 긍정 요인이 보유 자산에 도움이 될 수 있어요.'
            priority='계약 이행과 실제 매출 반영 여부를 먼저 확인해야 해요.'
            properties=request.get('text',{}).get('format',{}).get('schema',{}).get('properties',{})
            if 'impact' in properties and 'priority' in properties:
                value=dict(impact=impact,priority=priority)
            else:
                # A Responses adapter may request one composed field instead;
                # this does not alter the application's public DTO assertions.
                value=dict(overallImpact='보유 자산은 '+str(len(assets))+'개로 구성되어 있어요.\n\n'+impact+'\n\n'+priority)
        output=[]
        if search:
            output.append(dict(type='web_search_call',status='completed',action=dict(type='search',sources=sources)))
        output.append(dict(type='message',role='assistant',status='completed',content=[dict(type='output_text',text=json.dumps(value,ensure_ascii=False))]))
        return 200,dict(id='resp_localfixture',status='completed',output=output)


@contextmanager
def start_mock():
    """Yield an isolated provider with environment/control_url; caller owns usage."""
    fixture=AnalysisMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send_json(self,status,value):
            raw=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self):
            self.send_json(200,fixture.state()) if self.path=='/__test__/state' else self.send_json(404,{})

        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1000000: return self.send_json(400,{})
                value=json.loads(self.rfile.read(size))
                if self.path=='/__test__/state':
                    mode=value.get('mode',fixture.mode)
                    if mode not in ('supported','insufficient','failure','rate-limit','rolling-two','partial-insufficient','partial-prose','partial-date','missing-correction-target','fabricated-date','attached-date','unattached-source','persistent-insufficient'): return self.send_json(400,{})
                    with fixture.lock:
                        fixture.mode=mode
                        fixture.delay_seconds=max(0,min(3,float(value.get('delay_seconds',0))))
                        if value.get('reset'):
                            fixture.counts=dict(search=0,narrative=0,errors=0)
                            fixture.search_requests=[]
                            fixture.third_search_started.clear()
                            fixture.active_searches=0
                            fixture.max_active_searches=0
                            fixture.third_started_while_first_held=False
                    return self.send_json(200,fixture.state())
                if self.path!='/v1/responses': return self.send_json(404,{})
                if self.headers.get('Authorization')!='Bearer '+fixture.key: return self.send_json(401,{})
                status,result=fixture.respond(value); self.send_json(status,result)
            except (ValueError,KeyError,TypeError):
                self.send_json(400,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True; fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        yield fixture
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def empty_saved():
    return dict(status='EMPTY',lastCheckOutcome=None,analysisId=None,matchesCurrentPortfolio=False,
                lastSucceededAt=None,lastFailedAt=None,failureCode=None,changeReason=None,analysis=None)


def empty_analysis():
    return dict(totalAssetCount=0,analyzedAssetCount=0,overallDirection=None,overallScore=None,
                positiveImpactScore=0,negativeImpactScore=0,analyzedAt=None,overallImpact='',
                impacts=[],sources=[],excludedAssets=[],selectedAssetCount=0,analyzedWeight=0,coverage='INSUFFICIENT')


def snapshot():
    return dict(assets=[dict(assetName='Analysis Korea',weight=100,quantity=10)],
                summary=dict(direction='POSITIVE',score=100,positiveScore=100,negativeScore=0),overallImpact='Stored fixture summary',
                impacts=[dict(assetName='Analysis Korea',direction='POSITIVE',impactLevel='HIGH',issueSummary='Stored issue',
                              expectedReaction='Stored reaction',outlook='Stored outlook',reason='Stored reason',evidenceSentence='Stored evidence',rank=1)])


def stored_analysis():
    impact=dict(snapshot()['impacts'][0],weight=100,sources=[],evidenceStatus='SUPPORTED')
    return dict(totalAssetCount=1,analyzedAssetCount=1,overallDirection='POSITIVE',overallScore=100,
                positiveImpactScore=100,negativeImpactScore=0,analyzedAt=STAMP,overallImpact='Stored fixture summary',
                impacts=[impact],sources=[],excludedAssets=[],selectedAssetCount=1,analyzedWeight=100,coverage='COMPLETE')


def saved(status='READY',matches=True):
    return dict(status=status,lastCheckOutcome='UPDATED',analysisId=940001,matchesCurrentPortfolio=matches,
                lastSucceededAt=STAMP,lastFailedAt=None,failureCode=None,changeReason='최초 분석',analysis=stored_analysis())


def fixture_sql():
    sql="DELETE FROM portfolio_asset_analyses WHERE lower(asset_name) IN('analysis korea','analysis beta') OR lower(asset_name) LIKE 'analysis fixture %';\nDELETE FROM portfolios WHERE member_id BETWEEN 940001 AND 940099;\nDELETE FROM stock_daily_prices WHERE asset_id BETWEEN 940001 AND 940099;\n"
    for member in (MEMBER,EMPTY):
        sql += ("INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES ("+
                ','.join(map(literal,[member,'GOOGLE','analysis-'+str(member),str(member)+'@fixture.invalid','Analysis'+str(member),'USER','ACTIVE']))+
                ",now(),now()) ON CONFLICT(id) DO UPDATE SET status='ACTIVE',role='USER',withdrawn_at=NULL;\n")
    for asset,name in ((A,'Analysis Korea'),(UNPRICED,'Analysis Unpriced')):
        sql += ("INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES ("+
                ','.join(map(literal,[asset,name,'STOCK','ANALYSIS'+str(asset),'KOSPI']))+
                ",true,now(),now()) ON CONFLICT(id) DO UPDATE SET name=excluded.name;\n")
    sql += "INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(940001,'2020-01-02',100,now(),now());\n"
    sql += "INSERT INTO portfolios(id,member_id,created_at,updated_at) VALUES(940001,940001,now(),now());\n"
    sql += "INSERT INTO portfolio_holdings(id,portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES(940001,940001,940001,10,100,now(),now());\n"
    return sql


class AnalysisSuite(Suite):
    def __init__(self,*args,model='gpt-5-mini',**kwargs):
        super().__init__(*args,**kwargs); self.model=model

    def client(self,member=MEMBER,token=None):
        return super().client(member,token)

    def run(self,name,fn):
        try:
            self.db.seed(fixture_sql()); fn()
            self.results.append(dict(case=name,passed=True))
        except AssertionError as error:
            self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as error:
            self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed ('+type(error).__name__+'; details withheld)'))

    def business(self,client,path,code,data=None,status=409):
        return self.request(client,'POST',path,status,data,expected=dict(code=code,message=ERRORS[code]),unchanged=True)

    def seed_saved(self):
        self.db.seed("INSERT INTO portfolio_analyses(id,portfolio_id,schema_version,analysis_version,model,snapshot,analyzed_at,change_reason,created_at,updated_at) VALUES(940001,940001,1,'portfolio-v7-batch5',"+
                     literal(self.model)+','+literal(json.dumps(snapshot(),ensure_ascii=False))+"::jsonb,"+literal(STAMP)+",'최초 분석',now(),now());\n"+
                     "INSERT INTO portfolio_analysis_checks(portfolio_id,last_succeeded_at,last_outcome) VALUES(940001,"+literal(STAMP)+",'UPDATED');")

    def control(self, **changes):
        endpoint=urlsplit(self.mock_control_url)
        connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            raw=json.dumps(changes).encode() if changes else None
            connection.request('POST' if changes else 'GET',endpoint.path,raw,
                               {'Content-Type':'application/json'} if raw else {})
            response=connection.getresponse()
            require(response.status==200,'Mock control unavailable')
            return json.loads(response.read(65536),parse_float=Decimal)
        finally:
            connection.close()

    def provider(self, mode='supported', delay=0):
        return self.control(mode=mode,delay_seconds=delay,reset=True)

    def wait_search(self):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if self.control()['counts']['search']:
                return
            time.sleep(.02)
        raise AssertionError('Delayed provider request did not start')

    def generated(self,value,name='Analysis Korea'):
        require(isinstance(value,dict),'Generated analysis object')
        at=value.get('analyzedAt')
        require(isinstance(at,str),'Generated timestamp missing')
        instant=datetime.fromisoformat(at.replace('Z','+00:00'))
        require(abs((datetime.now(timezone.utc)-instant).total_seconds())<120,'Generated timestamp must be current')
        date=self.control()['as_of']
        source=dict(title='Fixture source',url='https://www.reuters.com/business/fixture-analysis-0-'+date+'/',
                    publishedOn=date,occurredOn=date,excerpt='회사가 신규 계약 체결을 발표했어요.',factQuote='회사는 신규 계약 체결을 발표했다.')
        expected=stored_analysis()
        expected.update(analyzedAt=at,overallImpact='현재 보유한 1개 종목 중 '+name+' 비중은 100%예요. 한 종목에 자산이 집중되어 있어요.\n\n확인된 긍정 요인이 보유 자산에 도움이 될 수 있어요.\n\n계약 이행과 실제 매출 반영 여부를 먼저 확인해야 해요.',sources=[source])
        expected['impacts']=[dict(assetName=name,weight=100,direction='POSITIVE',impactLevel='HIGH',
            issueSummary='회사가 신규 계약을 발표했어요.',expectedReaction='신규 계약은 향후 매출 증가에 도움이 될 수 있어요.',
            outlook='계약 이행과 매출 반영 여부를 확인해야 해요.',reason='계약 이행이 매출에 도움이 될 수 있어요.',
            evidenceSentence=source['excerpt'],sources=[source],rank=1,evidenceStatus='SUPPORTED')]
        equal(value,expected)

    def member_generated(self,c):
        value,_=self.request(c,'POST',P,200)
        require(isinstance(value,dict),'Saved analysis object')
        require(type(value.get('analysisId')) is int and value['analysisId']>0,'Persisted analysis ID')
        expected=saved(); expected.update(analysisId=value['analysisId'],lastSucceededAt=value.get('lastSucceededAt'),analysis=value.get('analysis'))
        equal(value,expected)
        require(isinstance(value['lastSucceededAt'],str),'Success timestamp missing')
        self.generated(value['analysis'])
        equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),1,'db.member.analysis.count')
        self.request(c,'GET',P,200,expected=value,unchanged=True)
        return value

    def provider_cases(self, control_url):
        endpoint=urlsplit(control_url)
        validate_local_url(endpoint.scheme+'://'+endpoint.netloc)
        require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid mock control path')
        self.mock_control_url=control_url
        def trial():
            self.provider(); c=self.client(None)
            body=dict(assets=[dict(assetName='Analysis Fixture Trial',weight=100)])
            value,_=self.request(c,'POST',PUBLIC,200,body,csrf=False)
            self.generated(value,'Analysis Fixture Trial')
            self.request(c,'POST',PUBLIC,403,body,expected=dict(code='PORTFOLIO_ANALYSIS_TRIAL_EXHAUSTED',message='비회원 포트폴리오 분석 체험을 이미 사용했습니다. 로그인 후 다시 이용해주세요.'),unchanged=True,csrf=False)
        self.run('provider-guest-success-then-same-session-trial-exhausted',trial)
        def retry():
            self.provider('failure'); c=self.client(None)
            body=dict(assets=[dict(assetName='Analysis Fixture Retry',weight=100)])
            self.request(c,'POST',PUBLIC,502,body,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'),csrf=False)
            self.provider()
            value,_=self.request(c,'POST',PUBLIC,200,body,csrf=False)
            self.generated(value,'Analysis Fixture Retry')
        self.run('provider-guest-failure-does-not-consume-trial-retry-succeeds',retry)
        def reuse():
            self.provider(); c=self.client(); value=self.member_generated(c)
            counts=self.control()['counts']; require(counts['search']>=1 and counts['narrative']>=1,'Generation must use both provider stages')
            self.request(c,'POST',P,200,expected=value,unchanged=True)
            equal(self.control()['counts'],counts,'provider.reuse.no-calls')
            self.request(c,'GET',P+'/history',200,expected=[dict(analysisId=value['analysisId'],previousAnalysisId=None,analyzedAt=value['analysis']['analyzedAt'],changeReason='최초 분석',analysis=value['analysis'])],unchanged=True)
        self.run('provider-member-generate-persist-read-history-and-reuse-with-zero-calls',reuse)
        def refresh():
            self.provider(); c=self.client(); old=self.member_generated(c)
            self.provider()
            value,_=self.request(c,'POST',P+'/refresh',200)
            require(self.control()['counts']['search']>=1,'Refresh must search')
            expected=dict(old,lastCheckOutcome='UNCHANGED',lastSucceededAt=value.get('lastSucceededAt'))
            equal(value,expected)
            equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),1,'db.unchanged-refresh.no-new-analysis')
        self.run('provider-refresh-identical-evidence-keeps-analysis-id-and-generation-time',refresh)
        def failed_refresh():
            self.provider(); c=self.client(); old=self.member_generated(c)
            self.provider('failure')
            self.request(c,'POST',P+'/refresh',502,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'))
            value,_=self.request(c,'GET',P,200,unchanged=True)
            expected=dict(old,status='FAILED',lastFailedAt=value.get('lastFailedAt'),failureCode='AI_PORTFOLIO_ANALYSIS_FAILED')
            equal(value,expected); require(isinstance(value['lastFailedAt'],str),'Failure timestamp missing')
        self.run('provider-refresh-failure-preserves-prior-success-analysis',failed_refresh)
        def concurrent_member():
            self.provider(delay=1); a=self.client(); b=self.client()
            with ThreadPoolExecutor(1) as pool:
                first=pool.submit(a.send,'POST',P)
                self.wait_search()
                self.business(b,P,'PORTFOLIO_ANALYSIS_IN_PROGRESS')
                status,_,value=first.result(timeout=12)
            require(status==200,'First concurrent member analysis must succeed')
            self.generated(value['analysis'])
            equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),1,'db.concurrent.single-analysis')
        self.run('provider-concurrent-member-second-request-409',concurrent_member)
        def concurrent_guest():
            self.provider('failure'); a=self.client(None); b=HTTP(self.base)
            body=dict(assets=[dict(assetName='Analysis Fixture Concurrent',weight=100)])
            # A failed attempt establishes the session without consuming its
            # trial. /auth/csrf alone need not create a servlet session.
            self.request(a,'POST',PUBLIC,502,body,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'),csrf=False)
            self.provider(delay=1)
            b.cookies=a.cookies.copy(); b.csrf=a.csrf
            with ThreadPoolExecutor(2) as pool:
                first=pool.submit(a.send,'POST',PUBLIC,body,False)
                self.wait_search()
                second=pool.submit(b.send,'POST',PUBLIC,body,False)
                results=[first.result(timeout=12),second.result(timeout=12)]
            equal(sorted(result[0] for result in results),[200,403],'guest.concurrent.single-trial')
        self.run('provider-concurrent-guest-session-allows-only-one-success',concurrent_guest)
        def withdrawal():
            self.provider(delay=1); a=self.client(); b=self.client()
            with ThreadPoolExecutor(1) as pool:
                pending=pool.submit(a.send,'POST',P)
                self.wait_search(); self.request(b,'DELETE','/api/users/me',204)
                pending.result(timeout=12)
            equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),0,'db.withdrawal.no-post-withdrawal-analysis')
        self.run('security-target-withdrawal-during-provider-wait-does-not-persist',withdrawal)
        def tiny_weight():
            self.provider()
            self.db.seed("UPDATE portfolio_holdings SET quantity=1000000 WHERE id=940001; INSERT INTO portfolio_holdings(id,portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES(940002,940001,940002,1,1,now(),now()); INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(940002,'2020-01-02',0.01,now(),now()); UPDATE assets SET name='Analysis Beta' WHERE id=940002;")
            value,_=self.request(self.client(),'POST',P,200)
            require(value['matchesCurrentPortfolio'] is True,'Tiny holding must preserve portfolio identity')
            self.request(self.client(),'GET',P,200,expected=value,unchanged=True)
            self.request(self.client(),'POST',P,200,expected=value,unchanged=True)
        self.run('provider-tiny-zero-rounded-weight-holding-stable-fingerprint-and-reuse',tiny_weight)
        self.regression_provider_cases()
        self.provider()

    def regression_provider_cases(self):
        # Original OpenAiPortfolioAnalysisClient analyzeBatch performs one
        # semantic correction and merges valid old impacts by asset name. V1
        # differs only in its weighted input/keyed output and cache bypass.
        def add_beta():
            self.db.seed("UPDATE assets SET name='Analysis Beta' WHERE id=940002; INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(940002,'2020-01-02',100,now(),now()); INSERT INTO portfolio_holdings(id,portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES(940002,940001,940002,10,100,now(),now());")

        for mode in ('partial-insufficient','partial-prose','partial-date'):
            def partial(mode=mode):
                add_beta(); self.provider(mode)
                value,_=self.request(self.client(),'POST',P,200)
                analysis=value['analysis']
                impacts={item['assetName']:item for item in analysis['impacts']}
                equal(set(impacts),{'Analysis Korea','Analysis Beta'},'partial.asset-names')
                equal(analysis['analyzedAssetCount'],2,'partial.analyzed-count')
                equal(analysis['coverage'],'COMPLETE','partial.coverage')
                for name in impacts:
                    equal(impacts[name]['evidenceStatus'],'SUPPORTED','partial.supported.'+name)
                    equal(impacts[name]['issueSummary'],'회사가 신규 계약을 발표했어요.','partial.retained-or-corrected.'+name)
                state=self.control()
                equal(state['counts']['search'],2,'partial.only-one-semantic-correction')
                targets=[[a['assetName'] for a in req['assets']] for req in state['search_requests']]
                # The external contract fixes target identity and retry scope;
                # SQL/calculation order of the first complete batch is internal.
                equal(len(targets),2,'partial.request-count')
                equal(sorted(targets[0]),['Analysis Beta','Analysis Korea'],'partial.initial-targets')
                equal(targets[1],['Analysis Beta'],'partial.only-invalid-beta-retried')
                equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),1,'partial.persisted-once')
                self.request(self.client(),'GET',P,200,expected=value,unchanged=True)
            self.run('provider-semantic-'+mode+'-retains-valid-A-corrects-only-B-once',partial)

        for mode in ('failure','rate-limit'):
            def transport(mode=mode):
                self.provider(mode)
                self.request(self.client(),'POST',P,502,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'))
                equal(self.control()['counts'],dict(search=1,narrative=0,errors=0),'transport.no-automatic-retry')
                equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),0,'transport.no-saved-analysis')
            self.run('provider-'+mode+'-single-transport-call-no-automatic-retry',transport)

        for mode in ('fabricated-date','unattached-source'):
            def rejected(mode=mode):
                self.provider(mode)
                self.request(self.client(),'POST',P,502,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'))
                equal(self.control()['counts']['search'],2,'rejected.exactly-one-correction')
                equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),0,'rejected.no-saved-analysis')
                equal(self.db.query("SELECT count(*) FROM portfolio_asset_analyses WHERE lower(asset_name)='analysis korea'"),0,'rejected.no-supported-cache')
            self.run('provider-persistent-'+mode+'-cannot-persist-supported-after-one-correction',rejected)

        def missing_correction():
            add_beta(); self.provider('missing-correction-target')
            self.request(self.client(),'POST',P,502,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'))
            equal(self.control()['counts']['search'],2,'missing-target.one-correction')
            equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),0,'missing-target.no-partial-success')
        self.run('provider-correction-omitting-invalid-B-fails-despite-valid-A',missing_correction)

        def cached_then_failure():
            self.provider(); c=self.client(); self.member_generated(c)
            add_beta(); self.provider('failure')
            self.request(c,'POST',P,502,expected=dict(code='AI_PORTFOLIO_ANALYSIS_FAILED',message='AI 포트폴리오 분석 생성에 실패했습니다.'))
            equal(self.control()['counts'],dict(search=1,narrative=0,errors=0),'cached-A.failure-B-propagates-once')
            equal(self.db.query('SELECT count(*) FROM portfolio_analyses WHERE portfolio_id=940001'),1,'cached-A.no-new-success-after-B-failure')
        self.run('provider-cached-A-does-not-hide-uncached-B-transport-failure',cached_then_failure)

        def attached_date():
            self.provider('attached-date')
            value,_=self.request(self.client(),'POST',P,200)
            state=self.control(); today=datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
            equal(state['search_requests'][0]['as_of'],today,'prompt.seoul-today')
            equal(state['as_of'],today,'fixture.seoul-today')
            impact=value['analysis']['impacts'][0]
            equal(impact['issueSummary'],today+'에 회사가 신규 계약을 발표했어요.','date.attached-issue')
            equal(impact['evidenceStatus'],'SUPPORTED','date.supported-today')
            equal(impact['sources'][0]['publishedOn'],today,'date.attached-published')
            equal(state['counts']['search'],1,'date.no-spurious-correction')
        self.run('provider-Seoul-today-date-attached-to-own-evidence-is-supported',attached_date)

        def cache_snapshot():
            return self.db.query("SELECT coalesce(json_agg(row_to_json(a) ORDER BY id),'[]'::json) FROM portfolio_asset_analyses a WHERE lower(asset_name)='analysis korea'")

        def v1():
            self.provider(); c=self.client(); self.member_generated(c)
            before=cache_snapshot(); require(bool(before),'Default must populate shared asset cache')
            self.provider()
            value,_=self.request(c,'POST','/api/v1/users/me/portfolio/analysis',200)
            state=self.control(); equal(state['counts']['search'],1,'v1.must-bypass-default-cache')
            request=state['search_requests'][0]
            equal(request['keyed'],True,'v1.keyed-schema'); equal(request['strict'],True,'v1.strict-schema')
            equal(request['required'],['Analysis Korea'],'v1.keyed-required-names')
            equal(request['assets'],[dict(assetName='Analysis Korea',weight=100)],'v1.weighted-input')
            equal(value['analysis']['impacts'][0]['evidenceStatus'],'SUPPORTED','v1.keyed-response-parsed')
            equal(self.db.query('SELECT to_json(analysis_version) FROM portfolio_analyses WHERE id='+str(value['analysisId'])),
                  'portfolio-v7-batch-price-v1','v1.saved-version')
            equal(cache_snapshot(),before,'v1.no-shared-cache-writes')
        self.run('provider-v1-weighted-keyed-direct-generation-bypasses-shared-cache-and-saves-version',v1)

        def v2():
            self.provider(); c=self.client(); self.member_generated(c)
            before=cache_snapshot(); self.provider()
            value,_=self.request(c,'POST','/api/v2/users/me/portfolio/analysis',200)
            state=self.control(); equal(state['counts']['search'],0,'v2.reuses-shared-asset-cache')
            equal(value['analysis']['impacts'][0]['evidenceStatus'],'SUPPORTED','v2.cached-supported-impact')
            equal(self.db.query('SELECT to_json(analysis_version) FROM portfolio_analyses WHERE id='+str(value['analysisId'])),
                  'portfolio-v8-select5-price-ai-v2','v2.saved-version')
            equal(cache_snapshot(),before,'v2.cache-reuse-no-mutation')
        self.run('provider-v2-reuses-default-shared-cache-and-saves-own-version',v2)

        def rolling_two():
            # Java PortfolioAnalysisBatches submits its next batch when any
            # completion frees one of the two slots (size five, four-minute
            # shared deadline). The local fixture avoids minute-long sleeps.
            self.provider('rolling-two')
            assets=[dict(assetName='Analysis Fixture Batch '+str(index).zfill(2),weight=6 if index<14 else 16)
                    for index in range(15)]
            value,_=self.request(self.client(None),'POST',PUBLIC,200,dict(assets=assets),csrf=False)
            state=self.control()
            equal(state['counts']['search'],3,'rolling.exact-three-five-asset-batches')
            equal(sorted(len(req['assets']) for req in state['search_requests']),[5,5,5],'rolling.batch-size')
            equal(state['third_started_while_first_held'],True,'rolling.third-starts-after-fast-second-before-slow-first')
            equal(state['max_active_searches'],2,'rolling.concurrency-exactly-two')
            equal(value['analyzedAssetCount'],15,'rolling.all-assets-supported')
            equal({impact['assetName'] for impact in value['impacts']},{asset['assetName'] for asset in assets},'rolling.no-lost-or-duplicate-assets')
            require(all(impact['evidenceStatus']=='SUPPORTED' for impact in value['impacts']),'Rolling batch result must retain all supported impacts')
        self.run('provider-three-batches-roll-next-work-into-free-slot-with-concurrency-two',rolling_two)

    def main(self):
        self.run('member-empty-analysis-without-portfolio',lambda:self.request(self.client(EMPTY),'GET',P,200,expected=empty_saved(),unchanged=True))
        self.run('member-empty-analysis-with-priced-portfolio',lambda:self.request(self.client(),'GET',P,200,expected=empty_saved(),unchanged=True))
        self.run('member-empty-history-read-only',lambda:self.request(self.client(),'GET',P+'/history',200,expected=[],unchanged=True))
        for suffix in ('','/history'):
            self.run('member-authentication-required'+suffix,lambda suffix=suffix:self.request(self.client(None),'GET',P+suffix,401,code='UNAUTHORIZED',unchanged=True))
        for path in (P,P+'/refresh',PUBLIC):
            self.run('no-portfolio-rejected-'+path,lambda path=path:self.business(self.client(EMPTY),path,'PORTFOLIO_ANALYSIS_ASSETS_UNAVAILABLE',dict(assets=[] ) if path==PUBLIC else None))
        def unpriced():
            self.db.seed('UPDATE portfolio_holdings SET asset_id=940002 WHERE id=940001;')
            self.business(self.client(),P,'PORTFOLIO_ANALYSIS_ASSETS_UNAVAILABLE')
        self.run('unpriced-portfolio-not-partially-analyzed',unpriced)
        self.run('member-public-request-assets-must-match-db',lambda:self.business(self.client(),PUBLIC,'PORTFOLIO_ANALYSIS_ASSETS_CHANGED',dict(assets=[dict(assetName='Other',weight=100)])))
        def ready():
            self.seed_saved()
            self.request(self.client(),'GET',P,200,expected=saved(),unchanged=True)
            self.request(self.client(EMPTY),'GET',P,200,expected=empty_saved(),unchanged=True)
        self.run('stored-ready-exact-dto-member-isolation',ready)
        def reuse():
            self.seed_saved(); c=self.client()
            self.request(c,'POST',P,200,expected=saved(),unchanged=True)
            self.request(c,'POST',PUBLIC,200,dict(assets=[dict(assetName='Analysis Korea',weight=100,quantity=999)]),expected=stored_analysis(),unchanged=True)
        self.run('saved-analysis-reuse-preserves-id-timestamps-db-ignores-request-quantity',reuse)
        def history():
            self.seed_saved()
            self.request(self.client(),'GET',P+'/history',200,expected=[dict(analysisId=940001,previousAnalysisId=None,analyzedAt=STAMP,changeReason='최초 분석',analysis=stored_analysis())],unchanged=True)
            self.request(self.client(EMPTY),'GET',P+'/history',200,expected=[],unchanged=True)
        self.run('stored-history-exact-dto-member-isolation',history)
        def changed():
            self.seed_saved(); self.db.seed('UPDATE portfolio_holdings SET quantity=11 WHERE id=940001;')
            self.request(self.client(),'GET',P,200,expected=saved('PORTFOLIO_CHANGED',False),unchanged=True)
        self.run('quantity-change-retains-prior-analysis',changed)
        def recheck():
            self.seed_saved(); self.db.seed("UPDATE portfolio_analysis_checks SET last_outcome='UNCONFIRMED' WHERE portfolio_id=940001;")
            expected=saved('RECHECK_REQUIRED'); expected['lastCheckOutcome']='UNCONFIRMED'
            self.request(self.client(),'GET',P,200,expected=expected,unchanged=True)
        self.run('unconfirmed-evidence-requires-recheck-preserving-analysis',recheck)
        def failed():
            self.seed_saved(); self.db.seed("UPDATE portfolio_analysis_checks SET last_failed_at='2090-01-02T00:00:00Z',failure_code='PORTFOLIO_ANALYSIS_FAILED' WHERE portfolio_id=940001;")
            expected=saved('FAILED'); expected.update(lastFailedAt='2090-01-02T00:00:00Z',failureCode='PORTFOLIO_ANALYSIS_FAILED')
            self.request(self.client(),'GET',P,200,expected=expected,unchanged=True)
        self.run('failed-check-retains-previous-success-result',failed)
        def processing():
            self.seed_saved()
            self.db.seed("UPDATE portfolio_analysis_checks SET request_token='00000000-0000-0000-0000-000000000001',request_expires_at=now()+interval '1 hour' WHERE portfolio_id=940001;")
            self.request(self.client(),'GET',P,200,expected=saved('PROCESSING'),unchanged=True)
            for path in (P,P+'/refresh'):
                self.business(self.client(),path,'PORTFOLIO_ANALYSIS_IN_PROGRESS')
        self.run('processing-state-and-concurrent-request-409',processing)
        def guest_empty():
            c=self.client(None)
            for _ in range(2):
                self.request(c,'POST',PUBLIC,200,dict(assets=[]),expected=empty_analysis(),unchanged=True,csrf=False)
        self.run('guest-empty-analysis-does-not-consume-trial-csrf-exempt',guest_empty)
        for name,assets,code in [('duplicate',[dict(assetName='Same',weight=50),dict(assetName=' same ',weight=50)],'DUPLICATE_PORTFOLIO_ASSET'),
                                 ('weight-total',[dict(assetName='Analysis Korea',weight=99)],'INVALID_PORTFOLIO_WEIGHT_TOTAL')]:
            self.run('guest-business-'+name,lambda assets=assets,code=code:self.business(self.client(None),PUBLIC,code,dict(assets=assets),400))
        for name,body,field,reason in [
            ('missing-assets',{},'assets','포트폴리오 자산 목록은 필수입니다.'),
            ('null-assets',dict(assets=None),'assets','포트폴리오 자산 목록은 필수입니다.'),
            ('51-assets',dict(assets=[dict(assetName='A',weight=1)]*51),'assets','포트폴리오 자산은 최대 50개까지 등록할 수 있습니다.'),
            ('blank-name',dict(assets=[dict(assetName='  ',weight=100)]),'assets[0].assetName','종목명은 필수입니다.'),
            ('long-name',dict(assets=[dict(assetName='가'*101,weight=100)]),'assets[0].assetName','종목명은 100자 이하여야 합니다.'),
            ('zero-weight',dict(assets=[dict(assetName='A',weight=0)]),'assets[0].weight','보유 비중은 0보다 커야 합니다.'),
            ('high-weight',dict(assets=[dict(assetName='A',weight=101)]),'assets[0].weight','보유 비중은 100 이하여야 합니다.'),
            ('missing-weight',dict(assets=[dict(assetName='A')]),'assets[0].weight','보유 비중은 필수입니다.'),
            ('zero-quantity',dict(assets=[dict(assetName='A',weight=100,quantity=0)]),'assets[0].quantity','수량은 0보다 커야 합니다.')]:
            self.run('guest-validation-'+name,lambda body=body,field=field,reason=reason:self.invalid(self.client(None),'POST',PUBLIC,body,field,reason))
        for path in (P,P+'/refresh',PUBLIC):
            def csrf(path=path):
                c=self.client(); c.cookies.pop('XSRF-TOKEN',None)
                self.request(c,'POST',path,403,dict(assets=[]) if path==PUBLIC else None,code='FORBIDDEN',unchanged=True,csrf=False)
            self.run('member-csrf-'+path,csrf)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True); parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',required=True,type=Path); parser.add_argument('--issuer',default='daynomy')
    parser.add_argument('--model',default='gpt-5-mini',help='Original ai.openai.model used for saved-result reuse fixture')
    parser.add_argument('--mock-control-url',help='Optional loopback start_mock() control URL; enables lifecycle and source/semantic/version regressions')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    report=dict(contract='Independent F06 original Java stored-state/validation contracts',results=[],passed=0,failed=0,
                environmentLimited=[dict(case=name,status='unverified',reason='Requires a coordinated controllable model/search provider') for name in
                                    ('generation-and-source-validation','guest-success-trial-exhaustion-and-failure-retry','refresh-new-unchanged-failed-evidence','v1-v2-provider-selection')])
    try:
        base=validate_local_url(args.base_url)
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True)
        require(len(key)>=32,'JWT fixture key must contain at least 32 bytes')
        suite=AnalysisSuite(base,TestDatabase(args.database),key,args.issuer,model=args.model)
        suite.main()
        if args.mock_control_url:
            suite.provider_cases(args.mock_control_url)
            report['environmentLimited']=[dict(case=name,status='unverified',reason=reason) for name,reason in
                (('real-external-model-and-search','Only deterministic local Responses fixture used'),
                 ('refresh-new-evidence-and-source-rejection','Same evidence/failure exercised; changed evidence and invalid source permutations remain'),
                 ('Seoul-midnight-clock-injection','Current Seoul date is checked; deterministic clock injection across midnight is unavailable'))]
        report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.TimeoutExpired):
        report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']); report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
