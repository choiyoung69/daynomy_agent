#!/usr/bin/env python3
"""Independent F01/F02/F05 real HTTP/PostgreSQL contract checks.

Only dedicated loopback *_service_test databases; reserve fixture IDs 920001..920099.
Requires original V1..53 schema. Controller serializes all DB users. JWTs are
cryptographically signed fixtures, never a development authentication bypass.
No implementation modules are read. No requests, cookies, token hashes or SQL
connection strings are included in reports. Google live OIDC is explicitly outside
this checker; an unconfigured start endpoint is separately environment-limited.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
from http.cookies import SimpleCookie
import http.client
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal

M1, M2, WITHDRAWN = 920001, 920002, 920003
KR, US = 920001, 920002
P = '/api/users/me/portfolio'
TODAY = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
YESTERDAY = (datetime.now(ZoneInfo('Asia/Seoul')).date()-timedelta(days=1)).isoformat()
PREVIOUS = (datetime.now(ZoneInfo('Asia/Seoul')).date()-timedelta(days=2)).isoformat()
MESSAGES = {
    'UNAUTHORIZED':'로그인이 필요합니다.',
    'INVALID_TOKEN':'유효하지 않은 인증 정보입니다.',
    'FORBIDDEN':'접근 권한이 없습니다.',
    'REFRESH_TOKEN_REQUIRED':'Refresh Token이 필요합니다.',
    'INVALID_REFRESH_TOKEN':'유효하지 않은 Refresh Token입니다.',
    'NICKNAME_ALREADY_EXISTS':'이미 사용 중인 닉네임입니다.',
    'PORTFOLIO_NOT_FOUND':'포트폴리오를 찾을 수 없습니다.',
    'PORTFOLIO_HOLDING_NOT_FOUND':'포트폴리오 보유자산을 찾을 수 없습니다.',
    'PORTFOLIO_TRANSACTION_NOT_FOUND':'포트폴리오 거래를 찾을 수 없습니다.',
    'INSUFFICIENT_PORTFOLIO_QUANTITY':'매도 수량이 해당 시점의 보유 수량보다 많습니다.',
    'INVALID_PORTFOLIO_PERIOD':'조회 시작일은 종료일보다 늦을 수 없습니다.',
    'INVALID_PORTFOLIO_TRADE_DATE':'거래일은 해당 종목의 마지막 보유 수량 등록·조정일보다 이를 수 없습니다.',
    'INVALID_TRANSACTION_EXCHANGE_RATE':'미국 거래는 1 USD당 원화 환율이 필요하며, 국내 거래의 환율은 1이어야 합니다.',
    'ASSET_NOT_FOUND':'자산을 찾을 수 없습니다.',
}


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, int): return str(value)
    return "'"+str(value).replace("'", "''")+"'"


def fixture_sql():
    sql = '''DELETE FROM refresh_tokens WHERE member_id BETWEEN 920001 AND 920099;
DELETE FROM portfolios WHERE member_id BETWEEN 920001 AND 920099;
'''
    for member, nickname, status in [(M1,'CoreAlpha','ACTIVE'),(M2,'CoreBeta','ACTIVE'),(WITHDRAWN,'CoreWithdrawn','WITHDRAWN')]:
        vals=[member,'GOOGLE','core-'+str(member),str(member)+'@fixture.invalid',nickname,'USER',status,'Private '+str(member)]
        sql += ('INSERT INTO members (id,provider,provider_id,email,nickname,role,status,google_name,created_at,updated_at) VALUES ('+
                ','.join(map(literal,vals))+",now(),now()) ON CONFLICT(id) DO UPDATE SET nickname=excluded.nickname,status=excluded.status,withdrawn_at=NULL,role='USER';\n")
    for asset, name, code, market in [(KR,'Core Korea','COREKR','KOSPI'),(US,'Core America','COREUS','NASDAQ')]:
        sql += ('INSERT INTO assets (id,name,category,asset_code,market,listed,created_at,updated_at) VALUES ('+
                ','.join(map(literal,[asset,name,'STOCK',code,market]))+",true,now(),now()) ON CONFLICT(id) DO UPDATE SET name=excluded.name,market=excluded.market;\n")
    for date, price in [(PREVIOUS,'110.00'),(YESTERDAY,'120.00')]:
        sql += ("INSERT INTO stock_daily_prices (asset_id,base_date,close_price,created_at,updated_at) VALUES (920001,"+
                literal(date)+","+literal(price)+",now(),now()) ON CONFLICT(asset_id,base_date) DO UPDATE SET close_price=excluded.close_price;\n")
    return sql


class HTTP:
    def __init__(self, base):
        self.base=base
        self.cookies={}
        self.csrf=None

    def send(self, method, path, data=None, csrf=True, headers=None):
        endpoint=urlsplit(self.base)
        conn=http.client.HTTPConnection(endpoint.hostname, endpoint.port or 80, timeout=15)
        hs={'Accept':'application/json'}
        if self.cookies: hs['Cookie']='; '.join(k+'='+v for k,v in self.cookies.items())
        if csrf and self.csrf and method not in ('GET','HEAD','OPTIONS'): hs[self.csrf[0]]=self.csrf[1]
        if data is not None:
            hs['Content-Type']='application/json'
            data=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
        hs.update(headers or {})
        try:
            conn.request(method,path,body=data,headers=hs)
            response=conn.getresponse()
            status=response.status
            received=response.getheaders()
            raw=response.read(65537)
        except (OSError,http.client.HTTPException):
            raise EnvironmentFailure('HTTP unavailable (details withheld)') from None
        finally: conn.close()
        require(len(raw)<=65536,'Response checker size limit exceeded')
        for name,value in received:
            if name.lower()=='set-cookie':
                parsed=SimpleCookie(); parsed.load(value)
                for key,cookie in parsed.items():
                    if cookie['max-age']=='0': self.cookies.pop(key,None)
                    else: self.cookies[key]=cookie.value
        if raw:
            require(any(k.lower()=='content-type' and 'application/json' in v for k,v in received),'Expected JSON response media type')
            try: value=json.loads(raw,parse_float=Decimal)
            except (ValueError,UnicodeError): raise AssertionError('Invalid response JSON') from None
        else: value=None
        return status,received,value

    def prepare_csrf(self):
        s,_,value=self.send('GET','/api/auth/csrf')
        require(s==200,'CSRF setup status')
        require(isinstance(value,dict),'CSRF setup object')
        require(set(value)=={'token','parameterName','headerName'},'CSRF field set')
        require(value['headerName']=='X-XSRF-TOKEN' and value['parameterName']=='_csrf','CSRF parameter/header contract')
        require(isinstance(value['token'],str) and bool(value['token']),'CSRF token missing')
        require(self.cookies.get('XSRF-TOKEN')==value['token'],'CSRF cookie/token mismatch')
        self.csrf=(value['headerName'],value['token'])


class Suite:
    def __init__(self,base,db,key,issuer):
        self.base,self.db,self.key,self.issuer=base,db,key,issuer
        self.results=[]
        self.environment_limited=[]

    def jwt(self, member=M1, kind='access', **overrides):
        now=int(time.time())
        claims=dict(iss=self.issuer,sub=str(member),iat=now,exp=now+3600,jti=str(uuid.uuid4()),token_type=kind)
        if kind=='access': claims['role']='USER'
        claims.update(overrides)
        def b64(v): return base64.urlsafe_b64encode(v).rstrip(b'=')
        head=b64(json.dumps({'alg':'HS256','typ':'JWT'},separators=(',',':')).encode())
        body=b64(json.dumps(claims,separators=(',',':')).encode())
        payload=head+b'.'+body
        return (payload+b'.'+b64(hmac.new(self.key,payload,hashlib.sha256).digest())).decode()

    def client(self,member=M1,token=None):
        c=HTTP(self.base); c.prepare_csrf()
        if member is not None: c.cookies['access_token']=token or self.jwt(member)
        return c

    def refresh(self, member=M1, **claims):
        token=self.jwt(member,'refresh',**claims)
        digest=hashlib.sha256(token.encode()).hexdigest()
        self.db.seed('INSERT INTO refresh_tokens (member_id,token_hash,expires_at,created_at) VALUES ('+
                     str(member)+','+literal(digest)+",now()+interval '1 hour',now());")
        return token

    def assert_count(self, table, count, member=M1):
        where='member_id='+str(member) if table in ('refresh_tokens','portfolios') else 'portfolio_id IN (SELECT id FROM portfolios WHERE member_id='+str(member)+')'
        equal(self.db.query('SELECT count(*) FROM '+table+' WHERE '+where), count, 'db.'+table+'.count')

    def request(self,c,method,path,status,data=None,code=None,expected=None,unchanged=False,csrf=True,headers=None):
        before=self.db.snapshot() if unchanged else None
        actual,received,value=c.send(method,path,data,csrf=csrf,headers=headers)
        require(actual==status,'HTTP status expected '+str(status)+' got '+str(actual))
        if status==204: require(value is None,'204 body must be empty')
        if code: equal(value,{'code':code,'message':MESSAGES[code]})
        if expected is not None: equal(value,expected)
        if unchanged: equal(self.db.snapshot(),before,'db.rollback/read-only')
        return value,received

    def invalid(self,c,method,path,data,field=None,reason=None):
        v,_=self.request(c,method,path,400,data,unchanged=True)
        require(isinstance(v,dict) and set(v)=={'code','message','errors'},'Validation field set')
        equal(v['code'],'INVALID_REQUEST','body.code'); equal(v['message'],'요청값이 올바르지 않습니다.','body.message')
        require(isinstance(v['errors'],list) and bool(v['errors']),'Validation errors missing')
        for e in v['errors']:
            require(isinstance(e,dict) and set(e)=={'field','reason'} and all(isinstance(x,str) and x for x in e.values()),'Validation errors field/reason')
        if field: require(any(e['field']==field and (reason is None or e['reason']==reason) for e in v['errors']),'Validation expected field/reason absent')

    def run(self,name,fn):
        try:
            self.db.seed(fixture_sql())
            fn()
            self.results.append({'case':name,'passed':True})
        except AssertionError as e:
            self.results.append({'case':name,'passed':False,'reason':str(e)})
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):
            self.results.append({'case':name,'passed':False,'reason':'Execution/fixture dependency failed (details withheld)'})

    def buy(self,c,**change):
        data=dict(assetId=KR,type='BUY',tradeDate=TODAY,quantity=10,unitPrice='100',fee='2',tax='0')
        data.update(change)
        v,_=self.request(c,'POST',P+'/transactions',201,data)
        require(isinstance(v,dict) and set(v)=={'transactionId','holding','totalRealizedProfitLoss'},'Transaction DTO fields')
        require(type(v['transactionId']) is int and v['transactionId']>0,'Generated transaction ID')
        return v

    def holding(self,q=10,price='100.20',asset=KR):
        return dict(assetId=asset,assetCode='COREKR' if asset==KR else 'COREUS',name='Core Korea' if asset==KR else 'Core America',category='STOCK',market='KOSPI' if asset==KR else 'NASDAQ',quantity=q,averagePurchasePrice=Decimal(price),averagePurchasePriceCurrency='KRW',currency='KRW' if asset==KR else 'USD')

    def portfolio(self,c,holdings,realized='0'):
        return self.request(c,'GET',P,200,expected=dict(holdings=holdings,totalRealizedProfitLoss=Decimal(realized)),unchanged=True)[0]

    def main(self):
        self.run('csrf-contract',lambda:self.client(None))
        for path in ('/api/users/me',P,'/api/portfolio',P+'/performance?from='+TODAY+'&to='+TODAY,'/api/v1/users/me/portfolio/analysis','/api/v2/users/me/portfolio/transactions'):
            method='POST' if '/v' in path else 'GET'
            self.run('unauthenticated-'+path,lambda path=path,method=method:self.request(self.client(None),method,path,401,{} if method=='POST' else None,code='UNAUTHORIZED',unchanged=True))
        for name,changes in [('expired',{'exp':int(time.time())-600}),('issuer',{'iss':'other'}),('future-nbf',{'nbf':int(time.time())+600}),('subject',{'sub':'invalid'}),('role',{'role':'ROOT'}),('token-type',{'token_type':'refresh'})]:
            self.run('jwt-reject-'+name,lambda changes=changes:self.request(self.client(token=self.jwt(**changes)),'GET','/api/users/me',401,code='INVALID_TOKEN',unchanged=True))
        def signature():
            token=self.jwt(); parts=token.split('.'); parts[2]=base64.urlsafe_b64encode(bytes(32)).rstrip(b'=').decode()
            self.request(self.client(token='.'.join(parts)),'GET','/api/users/me',401,code='INVALID_TOKEN',unchanged=True)
        self.run('jwt-reject-signature',signature)
        self.run('jwt-reject-withdrawn',lambda:self.request(self.client(WITHDRAWN),'GET','/api/users/me',401,code='INVALID_TOKEN',unchanged=True))
        self.run('jwt-reject-unknown-member',lambda:self.request(self.client(920099),'GET','/api/users/me',401,code='INVALID_TOKEN',unchanged=True))
        self.run('user-admin-denied',lambda:self.request(self.client(),'GET','/api/admin/feedbacks',403,code='FORBIDDEN',unchanged=True))
        for mode in ('missing','mismatch','cookie-only','header-only'):
            def csrf_case(mode=mode):
                c=self.client()
                if mode=='header-only': c.cookies.pop('XSRF-TOKEN',None)
                headers={c.csrf[0]:'mismatch'} if mode=='mismatch' else None
                if mode=='missing': c.cookies.pop('XSRF-TOKEN',None)
                self.request(c,'PATCH','/api/users/me',403,{'nickname':'Changed'},code='FORBIDDEN',unchanged=True,csrf=mode in ('mismatch','header-only'),headers=headers)
            self.run('csrf-write-'+mode,csrf_case)
        self.run('csrf-before-authentication',lambda:self.request(HTTP(self.base),'PATCH','/api/users/me',403,{},code='FORBIDDEN',unchanged=True,csrf=False))
        def member_profile():
            for member,nick in [(M1,'CoreAlpha'),(M2,'CoreBeta')]:
                self.request(self.client(member),'GET','/api/users/me',200,expected=dict(id=member,email=str(member)+'@fixture.invalid',name='Private '+str(member),nickname=nick,role='USER'),unchanged=True)
        self.run('member-profile-two-user-isolation',member_profile)
        def nickname(value,wanted):
            c=self.client(); v,_=self.request(c,'PATCH','/api/users/me',200,{'nickname':value})
            require(v.get('nickname')==wanted and v.get('id')==M1,'Member PATCH response mismatch')
            equal(self.db.query('SELECT to_json(nickname) FROM members WHERE id=920001'),wanted,'db.nickname')
            self.request(self.client(M2),'GET','/api/users/me',200,unchanged=True)
        for name,value,wanted in [('strip','\u2003 NewNick \n','NewNick'),('max','가'*20,'가'*20),('utf16-max','😀'*10,'😀'*10),('nbsp','\u00a0Name\u00a0','\u00a0Name\u00a0')]:
            self.run('nickname-'+name,lambda value=value,wanted=wanted:nickname(value,wanted))
        for name,value,reason in [('blank',' \u2003\n','닉네임을 입력해주세요.'),('null',None,'닉네임을 입력해주세요.'),('too-long','가'*21,'닉네임은 20자 이하여야 합니다.'),('utf16-too-long','😀'*11,'닉네임은 20자 이하여야 합니다.')]:
            self.run('nickname-invalid-'+name,lambda value=value,reason=reason:self.invalid(self.client(),'PATCH','/api/users/me',{'nickname':value},'nickname',reason))
        self.run('nickname-duplicate-rollback',lambda:self.request(self.client(),'PATCH','/api/users/me',409,{'nickname':'CoreBeta'},code='NICKNAME_ALREADY_EXISTS',unchanged=True))
        def nickname_race():
            cs=[self.client(M1),self.client(M2)]; barrier=threading.Barrier(2)
            def change(c): barrier.wait(); return c.send('PATCH','/api/users/me',{'nickname':'CoreRace'})[0]
            with ThreadPoolExecutor(2) as pool: statuses=list(pool.map(change,cs))
            equal(sorted(statuses),[200,409],'nickname.concurrent.statuses')
            equal(self.db.query("SELECT count(*) FROM members WHERE nickname='CoreRace'"),1,'db.nickname.unique')
        self.run('nickname-concurrent-unique',nickname_race)
        self.auth_cases()
        self.portfolio_cases()

    def auth_cases(self):
        self.run('refresh-required',lambda:self.request(self.client(None),'POST','/api/auth/refresh',401,code='REFRESH_TOKEN_REQUIRED',unchanged=True))
        def bad_refresh(kind):
            c=self.client(None)
            if kind=='absent-store': token=self.jwt(M1,'refresh')
            elif kind=='access-type': token=self.refresh(token_type='access')
            elif kind=='expired-jwt': token=self.refresh(exp=int(time.time())-600)
            elif kind=='withdrawn': token=self.refresh(WITHDRAWN)
            else:
                token=self.refresh()
                self.db.seed("UPDATE refresh_tokens SET expires_at=now()-interval '1 hour' WHERE member_id=920001;")
            c.cookies['refresh_token']=token
            _,hs=self.request(c,'POST','/api/auth/refresh',401,code='INVALID_REFRESH_TOKEN',unchanged=True)
            self.cookie_contract(hs,clear=True)
        for kind in ('absent-store','access-type','expired-jwt','expired-store','withdrawn'):
            self.run('refresh-reject-'+kind,lambda kind=kind:bad_refresh(kind))
        def rotation(concurrent=False):
            token=self.refresh(); c=self.client(None); c.cookies['refresh_token']=token
            if concurrent:
                d=self.client(None); d.cookies['refresh_token']=token; barrier=threading.Barrier(2)
                def go(client): barrier.wait(); return client.send('POST','/api/auth/refresh')
                with ThreadPoolExecutor(2) as pool: results=list(pool.map(go,[c,d]))
                equal(sorted(r[0] for r in results),[204,401],'refresh.concurrent.statuses')
                winner=next(r for r in results if r[0]==204)
                self.cookie_contract(winner[1])
            else:
                _,hs=self.request(c,'POST','/api/auth/refresh',204)
                self.cookie_contract(hs)
                require(c.cookies.get('refresh_token')!=token,'Refresh token did not rotate')
                self.request(c,'GET','/api/users/me',200,unchanged=True)
            self.assert_count('refresh_tokens',1)
            digest=hashlib.sha256(token.encode()).hexdigest()
            equal(self.db.query('SELECT count(*) FROM refresh_tokens WHERE token_hash='+literal(digest)),0,'db.old-refresh-revoked')
            old=self.client(None); old.cookies['refresh_token']=token
            self.request(old,'POST','/api/auth/refresh',401,code='INVALID_REFRESH_TOKEN',unchanged=True)
        self.run('refresh-atomic-rotation-replay',rotation)
        self.run('refresh-concurrent-single-use',lambda:rotation(True))
        def logout(has_token):
            c=self.client(); token=self.refresh()
            if has_token: c.cookies['refresh_token']=token
            _,hs=self.request(c,'POST','/api/auth/logout',204)
            self.cookie_contract(hs,clear=True)
            self.assert_count('refresh_tokens',0 if has_token else 1)
            if has_token:
                c.cookies['refresh_token']=token
                self.request(c,'POST','/api/auth/refresh',401,code='INVALID_REFRESH_TOKEN',unchanged=True)
        self.run('logout-invalidates-refresh',lambda:logout(True))
        self.run('logout-no-refresh-idempotent',lambda:logout(False))
        def withdraw():
            c=self.client(); old=c.cookies['access_token']; token=self.refresh(); self.refresh()
            self.refresh(M2)
            self.buy(c)
            _,hs=self.request(c,'DELETE','/api/users/me',204)
            self.cookie_contract(hs,clear=True)
            equal(self.db.query('SELECT to_json(status) FROM members WHERE id=920001'),'WITHDRAWN','db.member.status')
            self.assert_count('refresh_tokens',0); self.assert_count('refresh_tokens',1,M2)
            c.cookies['access_token']=old
            self.request(c,'GET','/api/users/me',401,code='INVALID_TOKEN',unchanged=True)
            c.cookies.pop('access_token',None); c.cookies['refresh_token']=token
            self.request(c,'POST','/api/auth/refresh',401,code='INVALID_REFRESH_TOKEN',unchanged=True)
        self.run('withdraw-revokes-all-session-tokens',withdraw)

    def cookie_contract(self,headers,clear=False):
        found={}
        for k,v in headers:
            if k.lower()=='set-cookie':
                parsed=SimpleCookie(); parsed.load(v); found.update(parsed)
        for name,path in [('access_token','/'),('refresh_token','/api/auth')]:
            require(name in found,'Missing auth Set-Cookie '+name)
            cookie=found[name]
            require(cookie['httponly'] and cookie['samesite'].lower()=='lax' and cookie['path']==path,'Auth cookie attributes differ')
            if clear: require(cookie['max-age']=='0','Auth cookie not cleared')
            else: require(bool(cookie.value) and int(cookie['max-age'])>0,'Auth cookie lifetime/value missing')

    def portfolio_cases(self):
        self.run('portfolio-empty-does-not-create',lambda:self.portfolio(self.client(),[]))
        def aliases():
            c=self.client(); buy=self.buy(c)
            equal(buy['holding'],self.holding())
            self.portfolio(c,[self.holding()])
            self.request(c,'GET','/api/portfolio',200,expected=dict(holdings=[self.holding()],totalRealizedProfitLoss=Decimal('0')),unchanged=True)
            self.portfolio(self.client(M2),[])
            self.assert_count('portfolios',1); self.assert_count('portfolio_holdings',1); self.assert_count('portfolio_holding_histories',1)
        self.run('portfolio-buy-persistence-alias-isolation',aliases)
        def buy_sell():
            c=self.client(); self.buy(c)
            self.buy(c,quantity=10,unitPrice='120',fee='0')
            self.portfolio(c,[self.holding(20,'110.10')])
            sold=self.buy(c,type='SELL',quantity=5,unitPrice='150',fee='1',tax='2')
            equal(sold['holding'],self.holding(15,'110.10')); equal(sold['totalRealizedProfitLoss'],Decimal('196.50'))
            self.portfolio(c,[self.holding(15,'110.10')],'196.50')
            full=self.buy(c,type='SELL',quantity=15,unitPrice='110.10',fee='0',tax='0')
            equal(full['holding'],None); self.portfolio(c,[],'196.50')
            self.assert_count('portfolio_holding_histories',4); self.assert_count('portfolio_holdings',0)
        self.run('ledger-buy-add-partial-full-sell-costs',buy_sell)
        def oversell(first=False):
            c=self.client()
            if not first: self.buy(c)
            self.request(c,'POST',P+'/transactions',400,dict(assetId=KR,type='SELL',tradeDate=TODAY,quantity=11,unitPrice='100',fee='0',tax='0'),code='INSUFFICIENT_PORTFOLIO_QUANTITY',unchanged=True)
        self.run('oversell-rolls-back-all-tables',oversell)
        self.run('first-oversell-does-not-create-portfolio',lambda:oversell(True))
        def mutate_transaction(delete=False,invalid=False):
            c=self.client(); first=self.buy(c)
            sell=self.buy(c,type='SELL',quantity=5,unitPrice='150',fee='0')
            path=P+'/transactions/'+str(first['transactionId'])
            if invalid:
                if delete: self.request(c,'DELETE',path,400,code='INSUFFICIENT_PORTFOLIO_QUANTITY',unchanged=True)
                else: self.request(c,'PATCH',path,400,dict(tradeDate=TODAY,quantity=4,unitPrice='100',fee='0',tax='0'),code='INSUFFICIENT_PORTFOLIO_QUANTITY',unchanged=True)
            elif delete:
                self.request(c,'DELETE',P+'/transactions/'+str(sell['transactionId']),200)
                self.portfolio(c,[self.holding()])
                self.assert_count('portfolio_holding_histories',1)
            else:
                v,_=self.request(c,'PATCH',path,200,dict(tradeDate=TODAY,quantity=20,unitPrice='80',fee='0',tax='0'))
                equal(v['transactionId'],first['transactionId']); self.portfolio(c,[self.holding(15,'80')],'350')
                self.assert_count('portfolio_holding_histories',2)
        for delete in (False,True):
            for invalid in (False,True): self.run('transaction-'+('delete' if delete else 'patch')+('-rollback' if invalid else '-replay'),lambda delete=delete,invalid=invalid:mutate_transaction(delete,invalid))
        def other_owner(method):
            a=self.client(); tx=self.buy(a); b=self.client(M2); self.buy(b,quantity=1)
            self.request(b,method,P+'/transactions/'+str(tx['transactionId']),404,dict(tradeDate=TODAY,quantity=1,unitPrice='1',fee='0',tax='0') if method=='PATCH' else None,code='PORTFOLIO_TRANSACTION_NOT_FOUND',unchanged=True)
        for method in ('PATCH','DELETE'): self.run('transaction-owner-isolation-'+method,lambda method=method:other_owner(method))
        def adjust(remove=False):
            c=self.client(); self.buy(c)
            if remove:
                self.request(c,'DELETE','/api/portfolio/holdings/'+str(KR),204)
                self.portfolio(c,[]); self.assert_count('portfolio_holding_histories',2)
            else:
                v,_=self.request(c,'PATCH','/api/portfolio/holdings/'+str(KR),200,{'quantity':7,'averagePurchasePrice':'88.88'})
                equal(v,self.holding(7,'88.88')); self.portfolio(c,[self.holding(7,'88.88')]); self.assert_count('portfolio_holding_histories',2)
                self.request(c,'PATCH',P+'/holdings/'+str(KR),200,{'quantity':7,'averagePurchasePrice':'88.88'},unchanged=True)
                self.request(c,'POST',P+'/transactions',400,dict(assetId=KR,type='BUY',tradeDate=YESTERDAY,quantity=1,unitPrice='1',fee='0',tax='0'),code='INVALID_PORTFOLIO_TRADE_DATE',unchanged=True)
        self.run('holding-adjust-history-idempotence-date-boundary',adjust)
        self.run('holding-delete-alias-persists-history',lambda:adjust(True))
        def usd():
            c=self.client(); tx=self.buy(c,assetId=US,quantity=3,unitPrice='10.1234',fee='0.25',tax='0.01',exchangeRate='1300.123456')
            # (10.1234*3+.25+.01)*1300.123456/3 -> 13274.35 HALF_UP
            equal(tx['holding'],self.holding(3,'13274.35',US))
            equal(self.db.query('SELECT json_build_object(\'price\',unit_price::text,\'rate\',exchange_rate::text) FROM portfolio_holding_histories WHERE portfolio_id IN (SELECT id FROM portfolios WHERE member_id=920001)'),{'price':'10.1234','rate':'1300.123456'},'db.usd.precision')
        self.run('usd-four-decimal-price-six-decimal-rate',usd)
        for asset,rate in [(US,None),(KR,'1300')]:
            self.run('exchange-rate-business-rule-'+str(asset),lambda asset=asset,rate=rate:self.request(self.client(),'POST',P+'/transactions',400,dict(assetId=asset,type='BUY',tradeDate=TODAY,quantity=1,unitPrice='1',fee='0',tax='0',exchangeRate=rate),code='INVALID_TRANSACTION_EXCHANGE_RATE',unchanged=True))
        for field,value in [('assetId',0),('type','HOLD'),('tradeDate','2099-01-01'),('quantity',0),('quantity',1.5),('unitPrice','0.00001'),('unitPrice','1.12345'),('fee','-1'),('fee','0.001'),('tax','-1'),('exchangeRate','1.0000001')]:
            def bad(field=field,value=value):
                data=dict(assetId=KR,type='BUY',tradeDate=TODAY,quantity=1,unitPrice='1',fee='0',tax='0'); data[field]=value
                self.invalid(self.client(),'POST',P+'/transactions',data)
            self.run('transaction-invalid-'+field+'-'+str(value),bad)
        def history():
            c=self.client(); first=self.buy(c,tradeDate=YESTERDAY); second=self.buy(c,quantity=2)
            v,_=self.request(c,'GET',P+'/histories?from='+YESTERDAY+'&to='+TODAY,200,unchanged=True)
            require(isinstance(v,list) and len(v)==2,'History list/count')
            fields={'historyId','assetId','assetCode','name','changeType','quantity','averagePurchasePrice','effectiveDate','transactionQuantity','unitPrice','fee','tax','occurredAt','currency','exchangeRate','averagePurchasePriceCurrency'}
            for row in v: require(set(row)==fields,'History DTO field set')
            equal([r['historyId'] for r in v],[second['transactionId'],first['transactionId']],'history.order')
            equal([r['effectiveDate'] for r in v],[TODAY,YESTERDAY],'history.date')
            equal(v[0]['transactionQuantity'],2,'history.transactionQuantity')
            filtered,_=self.request(c,'GET','/api/portfolio/histories?from='+TODAY+'&to='+TODAY,200,unchanged=True)
            equal([r['historyId'] for r in filtered],[second['transactionId']],'history.date-filter')
        self.run('history-fields-effective-date-order-filter',history)
        for kind in ('performance','histories'):
            self.run(kind+'-invalid-period',lambda kind=kind:self.request(self.client(),'GET',P+'/'+kind+'?from='+TODAY+'&to='+YESTERDAY,400,code='INVALID_PORTFOLIO_PERIOD',unchanged=True))
        def perf():
            c=self.client(); self.request(c,'GET',P+'/performance?from=2020-01-01&to=2020-01-02',200,expected=dict(status='INSUFFICIENT_DATA',reason='SNAPSHOT_DATA_INSUFFICIENT',baseDate=None,previousBaseDate=None,points=[],currentPoint=None),unchanged=True)
            self.buy(c)
            self.request(c,'GET',P+'/performance?from='+TODAY+'&to='+TODAY,200,unchanged=True)
        self.run('performance-insufficient-today-read-only',perf)
        def sell_race():
            a=self.client(); self.buy(a,quantity=1,fee='0'); b=self.client(); barrier=threading.Barrier(2)
            data=dict(assetId=KR,type='SELL',tradeDate=TODAY,quantity=1,unitPrice='100',fee='0',tax='0')
            def sell(c): barrier.wait(); return c.send('POST',P+'/transactions',data)[0]
            with ThreadPoolExecutor(2) as pool: statuses=list(pool.map(sell,[a,b]))
            equal(sorted(statuses),[201,400],'sell.concurrent.statuses')
            self.portfolio(a,[]); self.assert_count('portfolio_holding_histories',2)
        self.run('concurrent-sell-no-double-spend',sell_race)
        def snapshots():
            c=self.client(); tx=self.buy(c,tradeDate=PREVIOUS,quantity=2,fee='0')
            self.assert_count('portfolio_daily_snapshots',2)
            def point(date,evaluation,profit,rate,daily=None,daily_rate=None):
                return dict(baseDate=date,totalPurchaseAmount=Decimal('200'),totalEvaluationAmount=Decimal(evaluation),totalProfitLoss=Decimal(profit),totalReturnRate=Decimal(rate),dailyProfitLoss=None if daily is None else Decimal(daily),dailyReturnRate=None if daily_rate is None else Decimal(daily_rate))
            expected=dict(status='READY',reason=None,baseDate=YESTERDAY,previousBaseDate=PREVIOUS,points=[point(PREVIOUS,'220','20','10'),point(YESTERDAY,'240','40','20','20','9.09')],currentPoint=None)
            self.request(c,'GET',P+'/performance?from='+PREVIOUS+'&to='+YESTERDAY,200,expected=expected,unchanged=True)
            self.request(c,'PATCH',P+'/transactions/'+str(tx['transactionId']),200,dict(tradeDate=PREVIOUS,quantity=3,unitPrice='100',fee='0',tax='0'))
            equal(self.db.query("SELECT coalesce(json_agg(total_purchase_amount ORDER BY base_date),'[]'::json) FROM portfolio_daily_snapshots WHERE portfolio_id IN (SELECT id FROM portfolios WHERE member_id=920001)"),[300,300],'db.snapshot.replay')
            self.request(c,'DELETE',P+'/transactions/'+str(tx['transactionId']),200)
            self.assert_count('portfolio_daily_snapshots',0)
        self.run('snapshot-create-patch-delete-replay-ready-performance',snapshots)
        def v2():
            c=self.client()
            v,_=self.request(c,'POST','/api/v2/users/me/portfolio/transactions',201,dict(assetId=KR,type='BUY',tradeDate=TODAY,quantity=2,unitPrice='100',fee='0',tax='0'))
            require(set(v)=={'transactionId','holding','totalRealizedProfitLoss'},'V2 transaction field set')
            self.portfolio(c,[self.holding(2,'100')]); self.assert_count('portfolio_holding_histories',1)
        self.run('v2-transaction-persists-shared-portfolio',v2)
        # Original PortfolioSnapshotService calls the calculation service directly;
        # controller-only @Valid limits must not reject valid saved DB holdings.
        # Reserve independent regression member/assets 960001..960199.
        def regression_member(member):
            self.db.seed('DELETE FROM portfolios WHERE member_id='+str(member)+';\n'+
                'INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES ('+
                ','.join(map(literal,[member,'GOOGLE','performance-regression-'+str(member),str(member)+'@fixture.invalid','Performance'+str(member),'USER','ACTIVE']))+
                ",now(),now()) ON CONFLICT(id) DO UPDATE SET status='ACTIVE',withdrawn_at=NULL;\n")
        def performance_expected(purchase,evaluation,profit,rate):
            return dict(status='INSUFFICIENT_DATA',reason='SNAPSHOT_DATA_INSUFFICIENT',baseDate=None,previousBaseDate=None,points=[],
                currentPoint=dict(baseDate=TODAY,priceBaseDate=YESTERDAY,totalPurchaseAmount=Decimal(purchase),totalEvaluationAmount=Decimal(evaluation),
                    totalProfitLoss=Decimal(profit),totalReturnRate=Decimal(rate),dailyProfitLoss=None,dailyReturnRate=None))
        def saved_fifty_one():
            member=960001; regression_member(member)
            sql='INSERT INTO portfolios(id,member_id,created_at,updated_at) VALUES(960001,960001,now(),now());\n'
            holdings=[]
            for asset in range(960001,960052):
                sql+='INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES('+str(asset)+','+literal('Performance '+str(asset))+",'STOCK',"+literal('PERF'+str(asset))+",'KOSPI',true,now(),now()) ON CONFLICT(id) DO UPDATE SET market='KOSPI';\n"
                sql+='INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES('+str(asset)+','+literal(YESTERDAY)+",100,now(),now()) ON CONFLICT(asset_id,base_date) DO UPDATE SET close_price=100;\n"
                sql+='INSERT INTO portfolio_holdings(portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES(960001,'+str(asset)+',1,80,now(),now());\n'
                holdings.append(dict(assetId=asset,quantity=1,averagePurchasePrice=80))
            self.db.seed(sql); c=self.client(member)
            self.request(c,'GET',P+'/performance?from='+TODAY+'&to='+TODAY,200,expected=performance_expected('4080','5100','1020','25'),unchanged=True)
            self.invalid(self.client(None),'POST','/api/portfolio/calculate',dict(holdings=holdings),'holdings')
            equal(self.db.query('SELECT count(*) FROM portfolio_holdings WHERE portfolio_id=960001'),51,'db.saved-51-holdings-preserved')
        self.run('saved-performance-51-holdings-allowed-public-calculate-still-limited',saved_fifty_one)
        def saved_large_krw_average():
            member=960002;asset=960101;regression_member(member)
            self.db.seed("INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES(960101,'Performance USD','STOCK','PERFUSD','NASDAQ',true,now(),now()) ON CONFLICT(id) DO UPDATE SET market='NASDAQ';\n"+
                'INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES(960101,'+literal(YESTERDAY)+",1000000000000,now(),now()) ON CONFLICT(asset_id,base_date) DO UPDATE SET close_price=1000000000000;\n"+
                'INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at) VALUES('+literal(YESTERDAY)+','+literal(YESTERDAY)+',1000,now()) ON CONFLICT(requested_date) DO UPDATE SET base_date=excluded.base_date,rate=excluded.rate,fetched_at=excluded.fetched_at;')
            c=self.client(member)
            value,_=self.request(c,'POST',P+'/transactions',201,dict(assetId=asset,type='BUY',tradeDate=TODAY,quantity=1,unitPrice='1000000000000',fee='0',tax='0',exchangeRate='1000'))
            equal(value['holding']['averagePurchasePrice'],Decimal('1000000000000000.00'),'transaction.valid-16-digit-krw-average')
            equal(self.db.query('SELECT to_json(average_purchase_price) FROM portfolio_holdings WHERE asset_id=960101 AND portfolio_id IN(SELECT id FROM portfolios WHERE member_id=960002)'),Decimal('1000000000000000.00'),'db.valid-16-digit-krw-average')
            self.request(c,'GET',P+'/performance?from='+TODAY+'&to='+TODAY,200,expected=performance_expected('1000000000000000','1000000000000000','0','0'),unchanged=True)
            self.invalid(self.client(None),'POST','/api/portfolio/calculate',dict(holdings=[dict(assetId=asset,quantity=1,averagePurchasePrice='1000000000000000.00')]),'holdings[0].averagePurchasePrice')
        self.run('saved-performance-valid-usd-trade-16-digit-krw-average-public-limit-preserved',saved_large_krw_average)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',required=True,type=Path)
    parser.add_argument('--issuer',default='daynomy')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    report={'contract':'Independent F01/F02/F05 original DTO/service contract; member nickname policy',
            'results':[],'passed':0,'failed':0,'environmentLimited':[
                {'case':'google-real-oidc-login-callback','status':'unverified','reason':'External Google key/provider integration is not exercised by signed local JWT fixtures'},
                {'case':'restart-and-database-outage','status':'unverified','reason':'Controller must run lifecycle verification against the same candidate'}]}
    try:
        base=validate_local_url(args.base_url)
        require(args.jwt_secret_file.is_file(),'JWT fixture key file missing')
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True)
        require(len(key)>=32,'JWT fixture key must contain at least 32 bytes')
        suite=Suite(base,TestDatabase(args.database),key,args.issuer)
        suite.main(); report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.TimeoutExpired):
        report['results'].append({'case':'fixture-environment','passed':False,'reason':'Dedicated local environment setup failed (details withheld)'})
    report['passed']=sum(r['passed'] for r in report['results'])
    report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','failed')}))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
