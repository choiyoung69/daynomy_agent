#!/usr/bin/env python3
"""Independent loopback Google OIDC fixture and native HTTP/PostgreSQL checks.

Original basis: AuthController, CustomOidcUserService, OAuth2LoginSuccessHandler,
SecurityConfig, MemberService and TokenService. RS256 tokens are signed by an
ephemeral RSA-2048 fixture key, never a real Google credential. The coordinator
starts this mock before the candidate and serializes all DB checks.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import hmac
from http.cookies import SimpleCookie
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal
from service_core_acceptance import Suite, literal

PREFIX='auth-provider-fixture-'
CLIENT_ID='local-oidc-fixture-client'
REDIRECT='http://127.0.0.1:18086/login/oauth2/code/google'


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def der_value(data, offset=0):
    tag=data[offset]; size=data[offset+1]; offset+=2
    if size & 128:
        count=size & 127; size=int.from_bytes(data[offset:offset+count],'big'); offset+=count
    end=offset+size
    require(end<=len(data),'Malformed public-key DER')
    return tag,data[offset:end],end


class OIDCMock:
    def __init__(self,key_path):
        self.key_path=key_path
        public=subprocess.run(['openssl','pkey','-in',str(key_path),'-pubout','-outform','DER'],capture_output=True,check=True,timeout=10).stdout
        _,outer,_=der_value(public); _,_,offset=der_value(outer); _,bits,_=der_value(outer,offset)
        _,rsa,_=der_value(bits[1:]); _,modulus,offset=der_value(rsa); _,exponent,_=der_value(rsa,offset)
        self.jwks=dict(keys=[dict(kty='RSA',use='sig',alg='RS256',kid='fixture-v1',n=b64(modulus.lstrip(b'\x00')),e=b64(exponent.lstrip(b'\x00')))])
        self.codes={}; self.lock=threading.Lock(); self.server=None
        self.secret=b64(os.urandom(24)); self.counts=dict(token=0,jwks=0,rejected_form=0)

    @property
    def base_url(self):
        return 'http://127.0.0.1:'+str(self.server.server_port)

    @property
    def control_url(self):
        return self.base_url+'/__test__/state'

    @property
    def environment(self):
        return dict(GOOGLE_AUTHORIZATION_URI=self.base_url+'/authorize',GOOGLE_TOKEN_URI=self.base_url+'/token',
                    GOOGLE_JWKS_URI=self.base_url+'/jwks',GOOGLE_CLIENT_ID=CLIENT_ID,GOOGLE_CLIENT_SECRET=self.secret,
                    OAUTH_REDIRECT_URI=REDIRECT,SUCCESS_REDIRECT_URI='/fixture-success',FAILURE_REDIRECT_URI='/fixture-failure')

    def state(self):
        with self.lock: return dict(counts=self.counts.copy(),registered_codes=len(self.codes))

    def issue(self, registration):
        now=int(time.time()); mode=registration.get('mode','valid')
        claims=dict(iss='https://accounts.google.com',aud=CLIENT_ID,sub=registration['sub'],
                    nonce=registration['nonce'],iat=now,exp=now+600,email=registration['email'],
                    email_verified=True,name='Fixture Private Name')
        if mode=='nonce': claims['nonce']='wrong-nonce'
        if mode=='issuer': claims['iss']='https://untrusted.invalid'
        if mode=='audience': claims['aud']='different-client'
        if mode=='expired': claims['exp']=now-600
        if mode=='email-unverified': claims['email_verified']=False
        if mode=='missing-sub': claims.pop('sub')
        header=dict(alg='RS256',typ='JWT',kid='unknown-kid' if mode=='kid' else 'fixture-v1')
        unsigned=(b64(json.dumps(header,separators=(',',':')).encode())+'.'+b64(json.dumps(claims,separators=(',',':')).encode())).encode()
        signature=subprocess.run(['openssl','dgst','-sha256','-sign',str(self.key_path)],input=unsigned,capture_output=True,check=True,timeout=10).stdout
        if mode=='signature': signature=bytes(len(signature))
        return unsigned.decode()+'.'+b64(signature)


@contextmanager
def start_mock():
    """Create only temporary local RSA material and a loopback Google fixture."""
    with tempfile.TemporaryDirectory(prefix='oidc-fixture-') as directory:
        key=Path(directory)/'private.pem'
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key)],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=15)
        key.chmod(0o600); fixture=OIDCMock(key)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass

            def reply(self,status,value):
                data=json.dumps(value).encode(); self.send_response(status)
                self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)))
                self.end_headers(); self.wfile.write(data)

            def do_GET(self):
                if self.path=='/__test__/state': return self.reply(200,fixture.state())
                if self.path=='/jwks':
                    with fixture.lock: fixture.counts['jwks']+=1
                    return self.reply(200,fixture.jwks)
                self.reply(404,{})

            def do_POST(self):
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=65536: return self.reply(400,{})
                    raw=self.rfile.read(size)
                    if self.path=='/__test__/state':
                        registration=json.loads(raw)['register']
                        with fixture.lock: fixture.codes[registration['code']]=registration
                        return self.reply(200,fixture.state())
                    if self.path!='/token': return self.reply(404,{})
                    form=parse_qs(raw.decode(),keep_blank_values=True)
                    with fixture.lock:
                        fixture.counts['token']+=1
                        registration=fixture.codes.pop(form.get('code',[''])[0],None)
                    valid=(registration is not None and form.get('grant_type')==['authorization_code'] and
                           form.get('client_id')==[CLIENT_ID] and form.get('client_secret')==[fixture.secret] and
                           form.get('redirect_uri')==[REDIRECT])
                    if registration and registration.get('challenge'):
                        verifier=form.get('code_verifier',[''])[0]
                        valid=valid and b64(hashlib.sha256(verifier.encode()).digest())==registration['challenge']
                    if not valid:
                        with fixture.lock: fixture.counts['rejected_form']+=1
                        return self.reply(400,dict(error='invalid_grant'))
                    self.reply(200,dict(access_token='fixture-access',token_type='Bearer',expires_in=600,
                                        id_token=fixture.issue(registration),scope='openid email profile'))
                except (ValueError,KeyError,TypeError,subprocess.SubprocessError):
                    self.reply(400,dict(error='invalid_request'))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler); server.daemon_threads=True; fixture.server=server
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try: yield fixture
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


class Browser:
    def __init__(self,base): self.base=base; self.cookies={}

    def get(self,path):
        endpoint=urlsplit(self.base); connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=15)
        headers={'Accept':'application/json'}
        if self.cookies: headers['Cookie']='; '.join(k+'='+v for k,v in self.cookies.items())
        try:
            connection.request('GET',path,headers=headers); response=connection.getresponse()
            received=response.getheaders(); raw=response.read(65537)
            require(len(raw)<=65536,'OIDC response size limit')
            for name,value in received:
                if name.lower()=='set-cookie':
                    parsed=SimpleCookie(); parsed.load(value)
                    for key,cookie in parsed.items():
                        if cookie['max-age']=='0': self.cookies.pop(key,None)
                        else: self.cookies[key]=cookie.value
            media=response.getheader('Content-Type','')
            value=json.loads(raw) if raw and 'application/json' in media else None
            return response.status,received,value
        finally: connection.close()


def header(headers,name):
    return next((value for key,value in headers if key.lower()==name.lower()),None)


def fixture_sql():
    selected="SELECT id FROM members WHERE provider_id LIKE 'auth-provider-fixture-%'"
    sql='DELETE FROM refresh_tokens WHERE member_id IN('+selected+'); DELETE FROM portfolios WHERE member_id IN('+selected+'); DELETE FROM members WHERE provider_id LIKE \'auth-provider-fixture-%\';\n'
    for ident,suffix,status in ((940181,'existing','ACTIVE'),(940182,'withdrawn','WITHDRAWN')):
        sql+='INSERT INTO members(id,provider,provider_id,email,nickname,google_name,role,status,created_at,updated_at) VALUES('+','.join(map(literal,[ident,'GOOGLE',PREFIX+suffix,suffix+'@fixture.invalid','Stable'+suffix,'Old Private Name','USER',status]))+',now(),now());\n'
    return sql


class OIDCSuite:
    def __init__(self,base,db,control,key,args):
        self.base,self.db,self.control,self.key,self.args=base,db,control,key,args
        self.results=[]

    def provider(self,registration):
        endpoint=urlsplit(self.control); connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            connection.request('POST',endpoint.path,json.dumps(dict(register=registration)),{'Content-Type':'application/json'})
            response=connection.getresponse(); response.read(65536)
            require(response.status==200,'OIDC fixture registration failed')
        finally: connection.close()

    def begin(self,mode='valid',suffix='new'):
        c=Browser(self.base); status,headers,_=c.get('/api/auth/google')
        require(status==302 and header(headers,'Location')=='/oauth2/authorization/google','Google entry redirect contract')
        status,headers,_=c.get('/oauth2/authorization/google')
        require(status==302,'Google authorization redirect status')
        location=header(headers,'Location'); require(isinstance(location,str),'Authorization location missing')
        target=urlsplit(location); expected=urlsplit(self.control)
        require(target.scheme=='http' and target.hostname==expected.hostname and target.port==expected.port and target.path=='/authorize','Authorization must target local fixture')
        query=parse_qs(target.query)
        require(query.get('response_type')==['code'] and query.get('client_id')==[CLIENT_ID],'Authorization response/client contract')
        require(query.get('redirect_uri')==[REDIRECT],'Authorization callback URI')
        require('openid' in query.get('scope',[''])[0].split(),'OIDC scope missing')
        for name in ('state','nonce'):
            require(len(query.get(name,[''])[0])>=16,'OAuth '+name+' missing or weak')
        if self.args.require_pkce:
            require(query.get('code_challenge_method')==['S256'] and bool(query.get('code_challenge',[''])[0]),'PKCE S256 required')
        code=uuid.uuid4().hex
        registration=dict(code=code,nonce=query['nonce'][0],challenge=query.get('code_challenge',[''])[0],mode=mode,
                          sub=PREFIX+suffix,email=suffix+'@fixture.invalid')
        self.provider(registration)
        callback='/login/oauth2/code/google?'+urlencode(dict(code=code,state=query['state'][0]))
        return c,callback

    def business_snapshot(self):
        # Rust persists the short-lived authorization state that Spring keeps in
        # HttpSession. Consuming it on a failed matched callback is required replay
        # protection, not a member/token/business mutation.
        tables=self.db.query("SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]'::json) FROM pg_tables WHERE schemaname='public' AND tablename<>'oauth_login_states'")
        require('members' in tables and 'refresh_tokens' in tables,'OIDC business snapshot tables missing')
        parts=[]
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            parts.append("SELECT '"+table.replace("'","''")+"' AS name,md5(coalesce(string_agg(row_data,E'\\n' ORDER BY row_data),'')) AS digest FROM(SELECT row_to_json(t)::text AS row_data FROM public."+quoted+' t)s')
        rows=self.db.query('SELECT json_agg(t ORDER BY name) FROM('+' UNION ALL '.join(parts)+')t')
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

    def state_count(self):
        exists=self.db.query("SELECT to_json(to_regclass('public.oauth_login_states') IS NOT NULL)")
        return self.db.query('SELECT count(*) FROM oauth_login_states') if exists else None

    def failure(self,c,path,consume=True):
        before=self.business_snapshot(); states=self.state_count(); status,headers,value=c.get(path)
        require(status==self.args.failure_status,'OIDC failure HTTP status')
        if status==302:
            require(header(headers,'Location')==self.args.failure_redirect,'OIDC failure redirect')
        require('access_token' not in c.cookies and 'refresh_token' not in c.cookies,'Failed OIDC must not issue auth cookies')
        equal(self.business_snapshot(),before,'db.oidc.failure-no-business-writes')
        if states is not None:
            if consume: require(states>0,'Matched OAuth state must exist before callback')
            equal(self.state_count(),states-1 if consume else states,'db.oidc.state-consumed-only-for-matched-callback')

    def success(self,suffix='new'):
        c,path=self.begin(suffix=suffix); status,headers,_=c.get(path)
        require(status==302 and header(headers,'Location')=='/fixture-success','Successful login redirect')
        require(bool(c.cookies.get('access_token')) and bool(c.cookies.get('refresh_token')),'Real login token cookies missing')
        helper=Suite(self.base,self.db,self.key,'daynomy'); helper.cookie_contract(headers)
        member=self.db.query("SELECT row_to_json(t) FROM(SELECT id,email,nickname,google_name,role,status FROM members WHERE provider='GOOGLE' AND provider_id="+literal(PREFIX+suffix)+')t')
        require(member['status']=='ACTIVE' and member['role']=='USER','OIDC must create active ordinary member')
        equal(member['email'],suffix+'@fixture.invalid','db.member.email')
        equal(member['google_name'],'Fixture Private Name','db.member.private-google-name')
        require(member['nickname']!='Fixture Private Name' and member['nickname']!=suffix+'@fixture.invalid','Private Google identity must not become public nickname')
        status,_,profile=c.get('/api/users/me')
        equal(status,200); equal(profile,dict(id=member['id'],email=member['email'],name=member['google_name'],nickname=member['nickname'],role='USER'))
        digest=hashlib.sha256(c.cookies['refresh_token'].encode()).hexdigest()
        equal(self.db.query('SELECT count(*) FROM refresh_tokens WHERE member_id='+str(member['id'])+' AND token_hash='+literal(digest)),1,'db.oidc.refresh-hash-persisted')
        return c,path,member

    def run(self,name,fn):
        try:
            self.db.seed(fixture_sql()); fn(); self.results.append(dict(case=name,passed=True))
        except AssertionError as error:
            self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
            self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))

    def main(self):
        self.run('oidc-new-login-real-member-profile-and-persisted-refresh',lambda:self.success())
        def existing():
            _,_,member=self.success('existing'); equal(member['id'],940181); equal(member['nickname'],'Stableexisting')
            self.success('existing')
            equal(self.db.query("SELECT count(*) FROM members WHERE provider_id='auth-provider-fixture-existing'"),1,'db.oidc.existing-no-duplicate')
        self.run('oidc-existing-login-preserves-member-id-and-public-nickname',existing)
        for mode in ('nonce','issuer','audience','expired','signature','kid','missing-sub'):
            self.run('oidc-reject-'+mode,lambda mode=mode:self.failure(*self.begin(mode)))
        self.run('security-target-oidc-reject-unverified-email',lambda:self.failure(*self.begin('email-unverified')))
        def state():
            c,path=self.begin(); query=parse_qs(urlsplit(path).query)
            self.failure(c,'/login/oauth2/code/google?'+urlencode(dict(code=query['code'][0],state='wrong-state')),consume=False)
        self.run('oidc-reject-state-mismatch-no-member-or-token-write',state)
        def replay():
            _,path,_=self.success(); self.failure(Browser(self.base),path,consume=False)
        self.run('oidc-reject-callback-replay-without-session',replay)
        self.run('oidc-withdrawn-member-cannot-login',lambda:self.failure(*self.begin(suffix='withdrawn')))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True); parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',required=True,type=Path); parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--mock-control-url',required=True)
    parser.add_argument('--require-pkce',action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument('--failure-status',type=int,choices=(302,),default=302)
    parser.add_argument('--failure-redirect',default='/fixture-failure')
    args=parser.parse_args(argv)
    report=dict(contract='Independent real signed local Google OIDC fixture; hardened PKCE/verified-email target',results=[],passed=0,failed=0,
                environmentLimited=[dict(case='real-google-provider',status='unverified',reason='Only ephemeral local RSA/JWKS fixture; no Google network request'),
                                    dict(case='original-policy-differences',status='unverified',reason='Original failure handler redirects; verified-email/PKCE are explicit security targets, not claimed byte-identical original behavior')])
    try:
        endpoint=urlsplit(args.mock_control_url); validate_local_url(endpoint.scheme+'://'+endpoint.netloc)
        require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid OIDC control path')
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True); require(len(key)>=32,'JWT fixture key too short')
        suite=OIDCSuite(validate_local_url(args.base_url),TestDatabase(args.database),args.mock_control_url,key,args)
        suite.main(); report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):
        report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']); report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
