#!/usr/bin/env python3
"""Frozen pre-implementation mobile PKCE bridge checks over loopback HTTP/PostgreSQL.

Uses independent ephemeral RSA/JWKS Google fixture from existing auth-provider
checker. Never logs authorization codes, verifiers, cookies, JWTs or DB URLs.
Not a claim of live Google or device authentication. See spec/flutter/native-auth.md.
Run with the same arguments as service_auth_provider_acceptance.py, while the
candidate is started with that provider's environment. DB checks must serialize.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal
from service_auth_provider_acceptance import Browser, OIDCSuite, PREFIX, CLIENT_ID, REDIRECT, b64, fixture_sql, header
from service_core_acceptance import HTTP, Suite, literal

CALLBACK = ('org.daynomy.app', 'auth', '/callback')


class MobileSuite(OIDCSuite):
    def reset(self):
        # Absence is asserted by a dedicated schema test. Conditional cleanup lets
        # the unimplemented server's real 404 also reach the endpoint assertions.
        exists=self.db.query("SELECT to_json(to_regclass('public.mobile_auth_codes') IS NOT NULL)")
        self.db.seed(('DELETE FROM mobile_auth_codes;\n' if exists else '')+fixture_sql())

    def run(self,name,fn):
        try:
            self.reset(); fn(); self.results.append(dict(case=name,passed=True))
        except AssertionError as error:
            self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
            self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (sensitive details withheld)'))

    def begin_mobile(self,mode='valid',suffix='existing',extra=None):
        verifier=b64(uuid.uuid4().bytes+uuid.uuid4().bytes)
        state=b64(uuid.uuid4().bytes+uuid.uuid4().bytes)
        challenge=b64(hashlib.sha256(verifier.encode()).digest())
        c=Browser(self.base)
        params=dict(code_challenge=challenge,state=state)
        params.update(extra or {})
        status,headers,_=c.get('/api/auth/mobile/start?'+urlencode(params))
        require(status==302,'mobile start must redirect to Google authorization')
        location=header(headers,'Location')
        require(isinstance(location,str),'mobile authorization redirect missing')
        if location.startswith('/'):
            require(location.split('?')[0]=='/oauth2/authorization/google','mobile start intermediate route must be existing Google OAuth entry')
            status,headers,_=c.get(location)
            require(status==302,'Google authorization must redirect')
            location=header(headers,'Location')
        target=urlsplit(location); expected=urlsplit(self.control)
        require(target.scheme=='http' and target.hostname==expected.hostname and target.port==expected.port and target.path=='/authorize','mobile Google authorization must use isolated loopback provider')
        query=parse_qs(target.query)
        require(query.get('response_type')==['code'] and query.get('client_id')==[CLIENT_ID],'mobile Google client contract')
        require(query.get('redirect_uri')==[REDIRECT],'Google callback must remain existing server endpoint')
        require(query.get('code_challenge_method')==['S256'],'Google PKCE must also remain enabled')
        require(len(query.get('state',[''])[0])>=16 and len(query.get('nonce',[''])[0])>=16,'server OAuth state/nonce required')
        google_code=uuid.uuid4().hex
        self.provider(dict(code=google_code,nonce=query['nonce'][0],challenge=query.get('code_challenge',[''])[0],mode=mode,sub=PREFIX+suffix,email=suffix+'@fixture.invalid'))
        callback='/login/oauth2/code/google?'+urlencode(dict(code=google_code,state=query['state'][0]))
        return c,callback,verifier,state,challenge

    def issue(self,**options):
        browser,callback,verifier,state,challenge=self.begin_mobile(**options)
        status,headers,_=browser.get(callback)
        require(status==302,'mobile Google callback must redirect')
        target=urlsplit(header(headers,'Location') or '')
        equal((target.scheme,target.netloc,target.path),CALLBACK,'mobile fixed callback origin and path')
        require(not target.fragment,'mobile callback fragment prohibited')
        values=parse_qs(target.query,keep_blank_values=True)
        equal(set(values),{'code','state'},'callback may contain code/state only, never tokens')
        equal(values.get('state'),[state],'mobile callback original state')
        require(len(values.get('code',[]))==1 and bool(re.fullmatch(r'[A-Za-z0-9_-]{32,128}',values['code'][0])),'opaque code must be urlsafe and high entropy')
        require('access_token' not in browser.cookies and 'refresh_token' not in browser.cookies,'external browser must not receive app auth cookies')
        code=values['code'][0]
        digest=hashlib.sha256(code.encode()).hexdigest()
        row=self.db.query('SELECT row_to_json(t) FROM(SELECT member_id,code_hash,code_challenge,(expires_at>now() AND expires_at<=now()+interval \'61 seconds\') AS expires_correctly FROM mobile_auth_codes WHERE code_hash='+literal(digest)+')t')
        require(isinstance(row,dict),'only code hash must be persisted')
        equal(row['code_hash'],digest,'stored opaque code digest')
        equal(row['code_challenge'],challenge,'stored app PKCE challenge')
        equal(row['expires_correctly'],True,'mobile code 60 second expiry')
        require(isinstance(row['member_id'],int) and row['member_id']>0,'mobile code member binding')
        return code,verifier,row['member_id'],callback

    def exchange(self,code,verifier):
        client=HTTP(self.base)
        result=client.send('POST','/api/auth/mobile/exchange',dict(code=code,codeVerifier=verifier),csrf=False)
        return client,result

    def count_refresh(self):
        return self.db.query('SELECT count(*) FROM refresh_tokens WHERE member_id IN(SELECT id FROM members WHERE provider_id LIKE '+literal(PREFIX+'%')+')')

    def expect_success(self,code,verifier,member):
        client,(status,headers,value)=self.exchange(code,verifier)
        equal(status,204,'mobile PKCE exchange success')
        require(value is None,'exchange response must be bodyless')
        require(client.cookies.get('access_token') and client.cookies.get('refresh_token'),'exchange issues native session cookies')
        Suite(self.base,self.db,self.key,'daynomy').cookie_contract(headers)
        status,_,profile=client.send('GET','/api/users/me',csrf=False)
        equal(status,200,'exchanged native session authenticates real member')
        equal(profile['id'],member,'native session member identity')
        digest=hashlib.sha256(client.cookies['refresh_token'].encode()).hexdigest()
        equal(self.db.query('SELECT count(*) FROM refresh_tokens WHERE member_id='+str(member)+' AND token_hash='+literal(digest)),1,'native refresh token hash persisted')
        return client

    def main(self):
        def schema():
            exists=self.db.query("SELECT to_json(to_regclass('public.mobile_auth_codes') IS NOT NULL)")
            require(exists,'mobile code persistence table required')
            columns=self.db.query("SELECT json_agg(column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='mobile_auth_codes'")
            require(set(('code_hash','member_id','code_challenge','expires_at','created_at')).issubset(set(columns)),'mobile code persistence fields required')
            require(not set(('code','code_verifier','verifier','access_token','refresh_token')).intersection(set(columns)),'mobile persistence must contain no plaintext credential columns')
        self.run('mobile-code-durable-hash-schema',schema)

        def success():
            code,verifier,member,_=self.issue()
            self.expect_success(code,verifier,member)
        self.run('mobile-valid-google-pkce-exchange-profile-and-persisted-refresh',success)

        def replay():
            code,verifier,member,_=self.issue(); self.expect_success(code,verifier,member)
            before=self.count_refresh(); _,(status,_,_)=self.exchange(code,verifier)
            equal(status,401,'one-time code replay rejected'); equal(self.count_refresh(),before,'replay must not add refresh token')
        self.run('mobile-code-single-use',replay)

        def mismatch():
            code,verifier,member,_=self.issue(); before=self.count_refresh()
            _,(status,_,_)=self.exchange(code,'Z'*43)
            equal(status,401,'wrong valid-format verifier rejected'); equal(self.count_refresh(),before,'wrong verifier has no token write')
            self.expect_success(code,verifier,member)
        self.run('mobile-wrong-verifier-rejected-without-consuming-valid-code',mismatch)

        def expired():
            code,verifier,_,_=self.issue(); before=self.count_refresh()
            self.db.seed('UPDATE mobile_auth_codes SET expires_at=now()-interval \'1 second\';')
            _,(status,_,_)=self.exchange(code,verifier)
            equal(status,401,'expired code rejected'); equal(self.count_refresh(),before,'expired code no refresh write')
        self.run('mobile-code-expiry',expired)

        def concurrent():
            code,verifier,_,_=self.issue(); before=self.count_refresh()
            with ThreadPoolExecutor(max_workers=2) as pool:
                calls=[pool.submit(self.exchange,code,verifier) for _ in range(2)]
                statuses=sorted(call.result()[1][0] for call in calls)
            equal(statuses,[204,401],'concurrent exchange exactly one success')
            equal(self.count_refresh(),before+1,'concurrent exchange creates one refresh')
        self.run('mobile-atomic-concurrent-consume',concurrent)

        def withdrawn():
            code,verifier,member,_=self.issue(); before=self.count_refresh()
            self.db.seed('UPDATE members SET status=\'WITHDRAWN\',withdrawn_at=now() WHERE id='+str(member)+';')
            _,(status,_,_)=self.exchange(code,verifier)
            equal(status,401,'withdrawn member exchange rejected'); equal(self.count_refresh(),before,'withdrawal no token issue')
        self.run('mobile-member-withdrawn-after-code-issue',withdrawn)

        def hash_only():
            code,verifier,_,_=self.issue()
            encoded=self.db.query('SELECT coalesce(json_agg(t),\'[]\'::json) FROM mobile_auth_codes t')
            serialized=json.dumps(encoded)
            require(code not in serialized and verifier not in serialized,'plaintext code and verifier must not be stored')
        self.run('mobile-database-stores-no-code-or-verifier-plaintext',hash_only)

        def arbitrary_redirect():
            self.issue(extra=dict(redirect_uri='https://evil.invalid/callback',redirect='https://evil.invalid/callback'))
        self.run('mobile-fixed-callback-ignores-arbitrary-redirect',arbitrary_redirect)

        for params in ({},dict(code_challenge='x',state='S'*32),dict(code_challenge='C'*43,state='short'),dict(code_challenge='C'*43,state='S'*129),dict(code_challenge='C'*43,state='a%20b'),dict(code_challenge='+'*43,state='S'*32)):
            def invalid_start(params=params):
                status,_,_=Browser(self.base).get('/api/auth/mobile/start?'+urlencode(params))
                equal(status,400,'malformed mobile start rejected')
            self.run('mobile-start-input-'+str(len(self.results)),invalid_start)

        for payload in ({},dict(code='C'*43,codeVerifier='short'),dict(code='C'*43,codeVerifier='V'*129),dict(code='C'*43,codeVerifier='+'*43)):
            def invalid_exchange(payload=payload):
                status,_,_=HTTP(self.base).send('POST','/api/auth/mobile/exchange',payload,csrf=False)
                equal(status,400,'malformed PKCE exchange rejected')
            self.run('mobile-exchange-input-'+str(len(self.results)),invalid_exchange)

        def unknown():
            _,(status,_,_)=self.exchange('C'*43,'V'*43)
            equal(status,401,'unknown code rejected')
        self.run('mobile-unknown-code',unknown)

        def csrf_still_required():
            code,verifier,member,_=self.issue(); client=self.expect_success(code,verifier,member)
            status,_,_=client.send('PATCH','/api/users/me',dict(nickname='MustNotWrite'),csrf=False)
            equal(status,403,'mobile session ordinary writes remain CSRF protected')
        self.run('mobile-csrf-exemption-only-exchange',csrf_still_required)

        def provider_error():
            c,path,_,state,_=self.begin_mobile(mode='nonce')
            before=self.count_refresh(); status,headers,_=c.get(path)
            equal(status,302,'validated mobile error callback redirect')
            target=urlsplit(header(headers,'Location') or '')
            equal((target.scheme,target.netloc,target.path),CALLBACK,'provider error fixed callback')
            query=parse_qs(target.query); equal(set(query),{'error','state'}); equal(query['state'],[state])
            equal(self.count_refresh(),before,'provider error creates no session')
        self.run('mobile-verified-oauth-state-provider-error-callback',provider_error)

        def web_regression():
            self.success('existing')
        self.run('existing-web-oauth-login-remains-compatible',web_regression)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True); parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',type=Path,required=True); parser.add_argument('--mock-control-url',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv); args.require_pkce=True; args.failure_status=302; args.failure_redirect='/fixture-failure'
    report=dict(contract='spec/flutter/native-auth.md; independently authored before implementation',results=[],environmentLimited=['Real Google account and Android/iOS device authentication unverified'])
    try:
        control=urlsplit(args.mock_control_url); validate_local_url(control.scheme+'://'+control.netloc)
        require(control.path=='/__test__/state' and not control.query and not control.fragment,'local OIDC control endpoint required')
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True)
        require(len(key)>=32,'dedicated fixture signing key required')
        suite=MobileSuite(validate_local_url(args.base_url),TestDatabase(args.database),args.mock_control_url,key,args)
        suite.main(); report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):
        report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local setup failed (sensitive details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']); report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
