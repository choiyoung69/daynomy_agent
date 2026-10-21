#!/usr/bin/env python3
"""Independent F12 local Wikimedia/OpenAI/S3 provider and native DB contracts.

Source: original WikimediaImageClient/S3ImageStorage, AdminNewsService, keyword,
market-analysis and economic-news research/writer DTOs. No Rust implementation
reads. All network endpoints bind loopback; actual S3 SigV4 is independently
verified with ephemeral fixture credentials, never accepted by a bypass flag.
"""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from urllib.parse import parse_qs,parse_qsl,quote,urlsplit
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure,require,validate_local_url
from service_acceptance import TestDatabase,equal
from service_admin_acceptance import AdminSuite,NEWS

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN2kAAAAASUVORK5CYII=')
WEBP=base64.b64decode('UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA')
BODY='기준금리 인상이 발표됐어요. 시장은 향후 자금 조달 비용과 기업의 투자 변화를 살펴보고 있어요.'
DEFINITION='중앙은행이 정하는 정책 금리예요.'
CONTEXT='기사에서 자금 조달 비용의 변화를 설명해요.'
WATCH='기업의 자금 조달 비용 변화를 확인해야 해요.'
RISK='자금 조달 비용이 높아질 수 있어요.'
MARKET_WATCH='후속 금리 발표를 확인해야 해요.'
WIKI_TITLE='File:Fixture.png'
THUMB='https://upload.wikimedia.org/wikipedia/commons/fixture.png'
SOURCE='https://commons.wikimedia.org/wiki/File:Fixture.png'
LICENSE_URL='https://creativecommons.org/licenses/by/4.0/'


def mac(key,value):return hmac.new(key,value.encode(),hashlib.sha256).digest()


def verify_sigv4(method,path,headers,body,access,secret,session):
    """Compute canonical request/signing key independently of the Rust signer."""
    try:
        authorization=headers.get('Authorization','')
        match=re.fullmatch(r'AWS4-HMAC-SHA256 Credential=([^/]+)/([^,]+),\s*SignedHeaders=([^,]+),\s*Signature=([0-9a-f]{64})',authorization)
        if not match:return False
        key_id,scope,names,signature=match.groups()
        date_scope,region,service,ending=scope.split('/')
        if (key_id,region,service,ending)!=(access,'ap-northeast-2','s3','aws4_request'):return False
        values={key.lower():' '.join(value.split()) for key,value in headers.items()}
        if values.get('x-amz-security-token')!=session:return False
        signed=names.split(';')
        if signed!=sorted(set(signed)) or not {'host','x-amz-date'}<=set(signed):return False
        if any(name not in values for name in signed):return False
        timestamp=values['x-amz-date']
        instant=datetime.strptime(timestamp,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        if timestamp[:8]!=date_scope or abs((datetime.now(timezone.utc)-instant).total_seconds())>300:return False
        payload=values.get('x-amz-content-sha256','')
        if payload!=hashlib.sha256(body).hexdigest():return False
        endpoint=urlsplit(path)
        canonical_query='&'.join(quote(k,safe='-_.~')+'='+quote(v,safe='-_.~') for k,v in sorted(parse_qsl(endpoint.query,keep_blank_values=True)))
        canonical_headers=''.join(name+':'+values[name]+'\n' for name in signed)
        canonical='\n'.join((method,endpoint.path or '/',canonical_query,canonical_headers,names,payload))
        string_to_sign='AWS4-HMAC-SHA256\n'+timestamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
        signing=mac(mac(mac(mac(('AWS4'+secret).encode(),date_scope),region),service),'aws4_request')
        return hmac.compare_digest(hmac.new(signing,string_to_sign.encode(),hashlib.sha256).hexdigest(),signature)
    except (ValueError,KeyError,TypeError):return False


class MediaMock:
    def __init__(self):
        self.lock=threading.Lock();self.mode='valid';self.objects={};self.counts=dict(put=0,delete=0,signature_rejected=0,ai=0,wiki=0,image=0)
        self.access='FIXTUREACCESS';self.secret=base64.urlsafe_b64encode(os.urandom(24)).decode();self.session='fixture-session'
        self.ai_key=base64.urlsafe_b64encode(os.urandom(18)).decode();self.server=None

    @property
    def base_url(self):return 'http://127.0.0.1:'+str(self.server.server_port)

    @property
    def control_url(self):return self.base_url+'/__test__/state'

    @property
    def environment(self):
        return dict(WIKIMEDIA_BASE_URL=self.base_url,WIKIMEDIA_IMAGE_BASE_URL=self.base_url+'/image',WIKIMEDIA_USER_AGENT='DaynomyFixture/1.0',
                    S3_REGION='ap-northeast-2',S3_BUCKET='fixture-media',S3_OBJECT_PREFIX='fixture-news',S3_PUBLIC_BASE_URL=self.base_url+'/public',
                    S3_ENDPOINT_URL=self.base_url,AWS_ACCESS_KEY_ID=self.access,AWS_SECRET_ACCESS_KEY=self.secret,AWS_SESSION_TOKEN=self.session,
                    AI_OPENAI_BASE_URL=self.base_url+'/v1',AI_OPENAI_API_KEY=self.ai_key,AI_OPENAI_MODEL='gpt-5-mini',OPENAI_BASE_URL=self.base_url+'/v1',OPENAI_API_KEY=self.ai_key)

    def state(self):
        with self.lock:
            return dict(mode=self.mode,counts=self.counts.copy(),objects={key:dict(sha256=hashlib.sha256(value['body']).hexdigest(),length=len(value['body']),contentType=value['type'],cacheControl=value['cache']) for key,value in self.objects.items()})

    def wiki(self):
        with self.lock:self.counts['wiki']+=1;mode=self.mode
        def item(title,license,url=THUMB,mime='image/png'):
            return dict(title=title,imageinfo=[dict(mime=mime,thumburl=url,width=1200,height=800,extmetadata=dict(LicenseShortName=dict(value=license),LicenseUrl=dict(value=LICENSE_URL),Artist=dict(value='<b>Fixture Artist</b>')))])
        return dict(query=dict(pages=[item(WIKI_TITLE,'CC BY 4.0' if mode!='bad-license' else 'CC BY-SA 4.0'),item('File:Excluded.gif','CC BY 4.0',mime='image/gif'),item('File:Bad-host.png','CC0',url='https://untrusted.invalid/a.png')]))

    def ai(self,request):
        with self.lock:self.counts['ai']+=1;mode=self.mode
        if mode=='ai-failure':return 503,dict(error=dict(message='Fixture unavailable'))
        name=request.get('text',{}).get('format',{}).get('name','')
        props=request.get('text',{}).get('format',{}).get('schema',{}).get('properties',{})
        sources=[]
        if name=='news_keywords' or 'keywords' in props:
            value=dict(keywords=[dict(category='POLICY',keyword='기준금리',definition=DEFINITION,context=CONTEXT,watchPoint=WATCH,evidence='기준금리 인상이 발표됐어요.')])
        elif name=='market_analysis' or 'risk' in props:
            value=dict(risk=RISK,watchPoint=MARKET_WATCH,riskEvidence='기준금리 인상이 발표됐어요.',watchPointEvidence='기준금리 인상이 발표됐어요.')
        elif name=='economic_news_research' or any(tool.get('type')=='web_search' for tool in request.get('tools',[])):
            articles=[]
            topics=[('Policy','STOCK',['기준금리 인상이 발표됐어요.','시장에서는 자금 조달 비용을 확인해요.','기업은 투자 변화를 살펴봐요.']),
                    ('Housing','REAL_ESTATE',['주택 공급 계획이 발표됐어요.','신규 주택의 공급 일정이 공개됐어요.','주택 시장에서는 공급 변화를 살펴봐요.']),
                    ('Exports','STOCK',['수출 동향 자료가 발표됐어요.','해외 수요의 변화가 공개됐어요.','기업은 수출 시장의 변화를 살펴봐요.']),
                    ('Funds','ETF',['상장지수펀드 동향이 발표됐어요.','펀드 시장의 거래 흐름이 공개됐어요.','투자자는 펀드의 자금 흐름을 살펴봐요.'])]
            for topic,category,facts in topics:
                cited=[dict(url='https://example.test/articles/'+topic.lower()+'-'+suffix,title=topic+' '+suffix) for suffix in ('one','two')]
                sources.extend(cited)
                articles.append(dict(title='Admin Fixture Media Economic News '+topic,date=datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),category=category,facts=facts,sourceUrls=[item['url'] for item in cited]))
            value=dict(articles=articles)
        else:
            paragraph=(BODY+' 확인된 발표와 후속 자료를 바탕으로 자금 조달 비용의 변화를 살펴봐야 해요. 투자와 소비에 미치는 영향을 단정하지 않고 실제 발표 자료를 확인해야 해요. ')*2
            value=dict(articles=[dict(content='\n\n'.join([paragraph]*4)) for _ in range(4)])
        output=[]
        if sources:output.append(dict(type='web_search_call',status='completed',action=dict(sources=sources)))
        output.append(dict(type='message',status='completed',content=[dict(type='output_text',text=json.dumps(value,ensure_ascii=False))]))
        return 200,dict(id='resp_fixture_media',status='completed',output=output)


@contextmanager
def start_mock():
    fixture=MediaMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,status,value=None,raw=None,media='application/json'):
            if raw is None:raw=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            if raw:self.wfile.write(raw)

        def body(self,limit=6*1024*1024):
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=limit:raise ValueError()
            return self.rfile.read(size)

        def do_GET(self):
            endpoint=urlsplit(self.path)
            if endpoint.path=='/__test__/state':return self.reply(200,fixture.state())
            if endpoint.path=='/w/api.php':return self.reply(200,fixture.wiki())
            if endpoint.path=='/image/wikipedia/commons/fixture.png':return self.reply(200,raw=PNG,media='image/png')
            if endpoint.path.startswith('/public/'):
                key='/fixture-media/fixture-news/'+endpoint.path.rsplit('/',1)[1]
                with fixture.lock:value=fixture.objects.get(key)
                if value:return self.reply(200,raw=value['body'],media=value['type'])
            self.reply(404,{})

        def do_POST(self):
            try:
                raw=self.body();value=json.loads(raw)
                if self.path=='/__test__/state':
                    mode=value.get('mode','valid')
                    if mode not in ('valid','ai-failure','s3-failure','bad-license'):return self.reply(400,{})
                    with fixture.lock:
                        fixture.mode=mode
                        if value.get('reset'):
                            fixture.objects={};fixture.counts={key:0 for key in fixture.counts}
                    return self.reply(200,fixture.state())
                if self.headers.get('Authorization')!='Bearer '+fixture.ai_key:return self.reply(401,{})
                if self.path=='/v1/images/generations':
                    with fixture.lock:fixture.counts['image']+=1;mode=fixture.mode
                    if mode=='ai-failure':return self.reply(503,{})
                    require(value.get('n')==1 and value.get('size')=='1536x1024' and value.get('quality')=='low' and value.get('output_format')=='webp','Image request contract')
                    return self.reply(200,dict(data=[dict(b64_json=base64.b64encode(WEBP).decode())]))
                if self.path=='/v1/responses':
                    status,result=fixture.ai(value);return self.reply(status,result)
                self.reply(404,{})
            except (ValueError,KeyError,TypeError,AssertionError):self.reply(400,{})

        def storage(self,method):
            try:
                raw=self.body()
                if not verify_sigv4(method,self.path,self.headers,raw,fixture.access,fixture.secret,fixture.session):
                    with fixture.lock:fixture.counts['signature_rejected']+=1
                    return self.reply(403,{})
                if not re.fullmatch(r'/fixture-media/fixture-news/[A-Za-z0-9-]+\.(png|jpg|webp)',urlsplit(self.path).path):return self.reply(400,{})
                with fixture.lock:
                    fixture.counts['put' if method=='PUT' else 'delete']+=1
                    if fixture.mode=='s3-failure':return self.reply(503,{})
                    if method=='PUT':fixture.objects[self.path]=dict(body=raw,type=self.headers.get('Content-Type'),cache=self.headers.get('Cache-Control'))
                    else:fixture.objects.pop(self.path,None)
                self.reply(200 if method=='PUT' else 204,raw=b'',media='application/xml')
            except (ValueError,KeyError,TypeError):self.reply(400,{})

        def do_PUT(self):self.storage('PUT')
        def do_DELETE(self):self.storage('DELETE')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield fixture
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


class MediaSuite(AdminSuite):
    def control(self,mode=None):
        endpoint=urlsplit(self.control_url);c=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            c.request('POST' if mode else 'GET',endpoint.path,json.dumps(dict(mode=mode,reset=True)) if mode else None,{'Content-Type':'application/json'})
            response=c.getresponse();require(response.status==200,'Media fixture control unavailable');return json.loads(response.read(65536))
        finally:c.close()

    def draft(self,**changes):
        data=dict(title='Admin Fixture Media News',content=BODY,sources=[dict(name='Fixture',url='https://example.test/source')],category='STOCK',assetIds=[])
        data.update(changes);value=self.multipart(self.client(),'POST',NEWS,data,201)
        return value,data

    def upload(self,data,status=201,image=PNG):
        c=self.client();boundary='media-fixture-upload'
        body=('--'+boundary+'\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n'+json.dumps(data,ensure_ascii=False)+'\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="image"; filename="fixture.png"\r\nContent-Type: image/png\r\n\r\n').encode()+image+('\r\n--'+boundary+'--\r\n').encode()
        endpoint=urlsplit(self.base);connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=20)
        try:
            connection.request('POST',NEWS,body,{'Content-Type':'multipart/form-data; boundary='+boundary,'Cookie':'; '.join(k+'='+v for k,v in c.cookies.items()),c.csrf[0]:c.csrf[1]})
            response=connection.getresponse();raw=response.read(1000001);require(response.status==status,'Media upload HTTP status expected '+str(status)+' got '+str(response.status));require('application/json' in response.getheader('Content-Type',''),'Media upload JSON type');return json.loads(raw)
        finally:connection.close()

    def uploaded(self,value,content,kind):
        state=self.control();require(state['counts']['signature_rejected']==0,'S3 signature verification rejected request')
        require(len(state['objects'])==1,'Exactly one managed object must exist')
        key,obj=next(iter(state['objects'].items()))
        equal(obj,dict(sha256=hashlib.sha256(content).hexdigest(),length=len(content),contentType=kind,cacheControl='public, max-age=31536000, immutable'))
        require(value['imageUrl'].endswith('/public/'+key.rsplit('/',1)[1]),'Public image URL must map to stored object')
        equal(self.db.query('SELECT to_json(image_url) FROM news WHERE id='+str(value['id'])),value['imageUrl'],'db.media.url-persisted')

    def main(self,control_url):
        endpoint=urlsplit(control_url);validate_local_url(endpoint.scheme+'://'+endpoint.netloc);require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid media control path');self.control_url=control_url
        def publish():
            self.control('valid');draft,_=self.draft();c=self.client()
            value,_=self.request(c,'POST',NEWS+'/'+str(draft['id'])+'/publish',200)
            expected=dict(draft,status='PUBLISHED',publishedAt=self.db_stamp('news',draft['id'],'published_at'));equal(value,expected)
            self.request(self.client(None),'GET','/api/news/'+str(value['id']),200,unchanged=True)
            keyword=dict(category='POLICY',keyword='기준금리',points=[DEFINITION,CONTEXT,WATCH],definition=DEFINITION,context=CONTEXT,watchPoint=WATCH)
            self.request(self.client(None),'GET','/api/news/'+str(value['id'])+'/keywords',200,expected=dict(keywords=[keyword]),unchanged=True)
            self.request(self.client(None),'GET','/api/news/'+str(value['id'])+'/market-analysis',200,expected=dict(risk=RISK,watchPoint=MARKET_WATCH),unchanged=True)
            before=self.control()['counts'];self.error('POST',NEWS+'/'+str(value['id'])+'/publish','NEWS_NOT_DRAFT',409);equal(self.control()['counts'],before,'provider.republish-no-calls')
            require(before['ai']>=2,'Publish must obtain both keyword and market analyses')
        self.run('media-news-publish-persists-ai-keywords-market-public-detail-idempotent',publish)
        def publish_failure():
            self.control('valid');draft,_=self.draft();self.control('ai-failure')
            # Original keyword/market clients surface unexpected provider errors
            # via the common sanitized 500 contract; draft/derived rows roll back.
            self.request(self.client(),'POST',NEWS+'/'+str(draft['id'])+'/publish',500,expected=dict(code='INTERNAL_SERVER_ERROR',message='서버 내부 오류가 발생했습니다.'),unchanged=True)
        self.run('media-publish-provider-failure-atomic-draft-preservation',publish_failure)
        def search():
            self.control('valid')
            item=dict(title=WIKI_TITLE,thumbnailUrl=THUMB,sourceUrl=SOURCE,author='Fixture Artist',license='CC BY 4.0',licenseUrl=LICENSE_URL,width=1200,height=800)
            self.request(self.client(),'GET',NEWS+'/image-search?keyword=fixture',200,expected=dict(items=[item]),unchanged=True)
        self.run('media-wikimedia-search-license-host-mime-filter-metadata',search)
        def license_rejected():
            self.control('bad-license');self.request(self.client(),'GET',NEWS+'/image-search?keyword=fixture',200,expected=dict(items=[]),unchanged=True)
        self.run('media-wikimedia-disallowed-sharealike-license-not-returned',license_rejected)
        def upload():
            self.control('valid');_,data=self.draft();value=self.upload(dict(data,title='Admin Fixture Media Upload'))
            self.uploaded(value,PNG,'image/png');equal(value['imageSource']['type'],'MANUAL')
            self.request(self.client(),'DELETE',NEWS+'/'+str(value['id']),204)
            state=self.control();equal(len(state['objects']),0,'s3.deleted-managed-object');require(state['counts']['delete']>=1,'Deletion must call signed S3 delete')
        self.run('media-binary-upload-real-sigv4-metadata-persistence-and-delete',upload)
        def rollback():
            self.control('valid');_,data=self.draft();data.update(title='Admin Fixture Media Rollback',assetIds=[999999999])
            before=self.db.snapshot();value=self.upload(data,404)
            equal(value,dict(code='ASSET_NOT_FOUND',message='자산을 찾을 수 없습니다.'));equal(self.db.snapshot(),before,'db.failed-upload-atomic-rollback')
            state=self.control();require(state['counts']['put']>=1 and state['counts']['delete']>=1,'Failed DB operation must clean uploaded object');equal(len(state['objects']),0,'s3.rollback-no-orphan')
        self.run('media-upload-db-failure-rolls-back-and-signed-cleanup-no-orphan',rollback)
        def storage_failure():
            self.control('valid');_,data=self.draft();self.control('s3-failure');before=self.db.snapshot()
            value=self.upload(dict(data,title='Admin Fixture Media Storage Failure'),502)
            equal(value,dict(code='S3_IMAGE_STORAGE_FAILED',message='이미지 저장소 요청에 실패했습니다.'));equal(self.db.snapshot(),before,'db.s3-failure-no-news-write')
        self.run('media-s3-provider-failure-no-news-partial-write',storage_failure)
        def import_wiki():
            self.control('valid');value,_=self.draft(imageSelection=dict(title=WIKI_TITLE))
            self.uploaded(value,PNG,'image/png')
            equal(value['imageSource'],dict(name='Wikimedia Commons',url=SOURCE,author='Fixture Artist',license='CC BY 4.0',licenseUrl=LICENSE_URL,type='WIKIMEDIA'))
        self.run('media-wikimedia-import-safe-download-signed-storage-and-attribution',import_wiki)
        def generate_image():
            self.control('valid');draft,_=self.draft();value,_=self.request(self.client(),'POST',NEWS+'/'+str(draft['id'])+'/generate-image',200)
            self.uploaded(value,WEBP,'image/webp');equal(value['imageSource'],dict(name='',url='',author='',license='',licenseUrl='',type='AI_GENERATED'))
            require(self.control()['counts']['image']==1,'Image provider called exactly once')
        self.run('media-generated-webp-signed-upload-ai-attribution',generate_image)
        for region in ('korea','us'):
            def economics(region=region):
                self.control('valid');before=self.db.query("SELECT count(*) FROM news WHERE title LIKE 'Admin Fixture Media Economic News %'")
                self.request(self.client(),'POST',NEWS+'/generate/economy/'+region,200,expected=dict(savedCount=4))
                equal(self.db.query("SELECT count(*) FROM news WHERE title LIKE 'Admin Fixture Media Economic News %' AND status='DRAFT'"),before+4,'db.generated-economic-draft')
                require(self.control()['counts']['ai']>=2,'Economic news must research then write')
            self.run('media-economic-'+region+'-research-writer-persists-draft',economics)
        self.control('valid')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--database',required=True);parser.add_argument('--jwt-secret-file',required=True,type=Path);parser.add_argument('--issuer',default='daynomy');parser.add_argument('--mock-control-url',required=True);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    report=dict(contract='Independent original media/news provider and verified SigV4 contracts',results=[],passed=0,failed=0,environmentLimited=[dict(case='real-external-media-providers',status='unverified',reason='Local deterministic Wikimedia/OpenAI/S3 fixtures only; production IAM/storage not exercised')])
    try:
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True);require(len(key)>=32,'JWT fixture key too short')
        suite=MediaSuite(validate_local_url(args.base_url),TestDatabase(args.database),key,args.issuer);suite.main(args.mock_control_url);report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']);report['failed']=len(report['results'])-report['passed'];args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],failed=report['failed'])));return int(report['failed']>0)


if __name__=='__main__':sys.exit(main())
