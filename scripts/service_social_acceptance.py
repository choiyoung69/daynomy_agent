#!/usr/bin/env python3
"""Independent original Java YouTube/social-search/official-profile collection gate.

Original basis: YouTubeClient, OpenAiSocialPostSearchClient,
FeaturedPersonPostCollectionService and corresponding public DTOs. Providers are
loopback fixtures; authentication and persistence use the real running service.
No app implementation reads. Reuses isolated admin fixture IDs 940101..940199.
"""
import argparse
import base64
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import parse_qs,urlsplit

from acceptance import EnvironmentFailure,require,validate_local_url
from service_acceptance import TestDatabase,equal
from service_admin_acceptance import AdminSuite,ADMIN,USER,C,PEOPLE

FROM='2020-02-10';TO='2020-02-11'
AFTER='2020-02-09T15:00:00Z';BEFORE='2020-02-11T15:00:00Z'
COLLECT=PEOPLE+'/940111/post-candidates/collect?from='+FROM+'&to='+TO
YOUTUBE=C+'/youtube-search?keyword=fixture';SOCIAL=C+'/social-search?keyword=fixture'
X='https://x.com/fixtureofficial/status/111'
THREADS='https://www.threads.net/@fixtureofficial/post/ABC123'
OTHER='https://x.com/someoneelse/status/222'
OLD='https://x.com/fixtureofficial/status/333'
V1='abcDEFghi12';V2='zyxWVUtsr98'


def social_items():
    return [dict(title='Fixture X',url=X,publishedDate=FROM),dict(title='Fixture Threads',url=THREADS,publishedDate=TO),
            dict(title='Wrong author',url=OTHER,publishedDate=FROM),dict(title='Outside period',url=OLD,publishedDate='2020-02-09')]


def video(ident,title='Fixture Video',when=AFTER,quality='high'):
    return dict(id=dict(videoId=ident),snippet=dict(title=title,channelTitle='Fixture Channel',publishedAt=when,thumbnails={quality:dict(url='https://i.ytimg.com/vi/'+ident+'/fixture.jpg')}))


class SocialMock:
    def __init__(self):
        self.lock=threading.Lock();self.mode='valid';self.counts=dict(search=0,channels=0,social=0,profile_pages=0);self.server=None
        self.key=base64.urlsafe_b64encode(os.urandom(18)).decode()

    @property
    def base_url(self):return 'http://127.0.0.1:'+str(self.server.server_port)

    @property
    def control_url(self):return self.base_url+'/__test__/state'

    @property
    def environment(self):
        return dict(YOUTUBE_BASE_URL=self.base_url+'/youtube',YOUTUBE_API_KEY=self.key,AI_OPENAI_BASE_URL=self.base_url+'/v1',AI_OPENAI_API_KEY=self.key,AI_OPENAI_MODEL='gpt-5-mini',AI_OPENAI_SOCIAL_SEARCH_MODEL='gpt-5-mini',OPENAI_SOCIAL_SEARCH_MODEL='gpt-5-mini')

    def state(self):
        with self.lock:return dict(mode=self.mode,counts=self.counts.copy())

    def youtube(self,path,q):
        with self.lock:mode=self.mode;self.counts['channels' if path.endswith('/channels') else 'search']+=1
        if mode in ('failure','youtube-failure'):return 503,{}
        if q.get('key')!=[self.key]:return 401,{}
        if path=='/youtube/channels':
            if q.get('part')!=['id'] or not(q.get('forHandle') in (['fixtureofficial'],['한국']) or q.get('forUsername')==['fixtureuser']):return 400,{}
            return 200,dict(items=[dict(id='UCfixture')])
        if path!='/youtube/search':return 404,{}
        for key,value in dict(part='snippet',type='video',order='date',safeSearch='moderate').items():
            if q.get(key)!=[value]:return 400,{}
        if 'channelId' not in q:
            if q.get('q')!=['fixture'] or q.get('maxResults')!=['10']:return 400,{}
            return 200,dict(items=[video(V1),video('',title='Missing video id'),video(V2,title='Fallback Thumbnail',quality='medium')])
        if any(q.get(k)!=[v] for k,v in dict(channelId='UCfixture',maxResults='50',publishedAfter=AFTER,publishedBefore=BEFORE).items()):return 400,{}
        with self.lock:self.counts['profile_pages']+=1
        if q.get('pageToken')==['next-fixture']:
            return 200,dict(items=[video(V2,title='Second Page',when='2020-02-11T14:59:59Z'),video(V1)])
        if 'pageToken' in q:return 400,{}
        return 200,dict(nextPageToken='next-fixture',items=[video(V1),video('outsideDATE',title='Too late',when=BEFORE)])

    def social(self,request):
        with self.lock:mode=self.mode;self.counts['social']+=1
        if mode in ('failure','social-failure'):return 503,{}
        if not any(tool.get('type')=='web_search' and tool.get('filters',{}).get('allowed_domains') for tool in request.get('tools',[])):return 400,{}
        items=social_items()+[dict(title='Uncited forged post',url='https://x.com/fixtureofficial/status/999',publishedDate=FROM),dict(title='Wrong host',url='https://evil.invalid/fixtureofficial/status/444',publishedDate=FROM),dict(title='Profile only',url='https://x.com/fixtureofficial',publishedDate=FROM)]
        # Include duplicate with changed title: original first occurrence wins.
        items.append(dict(items[0],title='Duplicate must not replace first'))
        sources=[] if mode=='uncited' else [dict(url=item['url'],title=item['title']) for item in social_items()]
        return 200,dict(id='resp_fixture_social',status='completed',output=[dict(type='web_search_call',status='completed',action=dict(sources=sources)),dict(type='message',status='completed',content=[dict(type='output_text',text=json.dumps(dict(items=items)))])])


@contextmanager
def start_mock():
    fixture=SocialMock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value):
            raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/__test__/state':return self.reply(200,fixture.state())
            endpoint=urlsplit(self.path);status,value=fixture.youtube(endpoint.path,parse_qs(endpoint.query));self.reply(status,value)
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'));require(0<size<=1000000,'Invalid fixture request length');value=json.loads(self.rfile.read(size))
                if self.path=='/__test__/state':
                    mode=value.get('mode','valid');require(mode in ('valid','failure','youtube-failure','social-failure','uncited'),'Invalid mode')
                    with fixture.lock:
                        fixture.mode=mode
                        if value.get('reset'):fixture.counts=dict(search=0,channels=0,social=0,profile_pages=0)
                    return self.reply(200,fixture.state())
                if self.path!='/v1/responses':return self.reply(404,{})
                if self.headers.get('Authorization')!='Bearer '+fixture.key:return self.reply(401,{})
                status,result=fixture.social(value);self.reply(status,result)
            except (AssertionError,ValueError,TypeError,KeyError):self.reply(400,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;fixture.server=server
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield fixture
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


class SocialSuite(AdminSuite):
    def control(self,mode=None):
        endpoint=urlsplit(self.control_url);c=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=5)
        try:
            c.request('POST' if mode else 'GET',endpoint.path,json.dumps(dict(mode=mode,reset=True)) if mode else None,{'Content-Type':'application/json'})
            response=c.getresponse();require(response.status==200,'Social mock unavailable');return json.loads(response.read(65536))
        finally:c.close()

    def profiles(self,youtube='https://www.youtube.com/@fixtureofficial',social=True):
        self.db.seed("DELETE FROM featured_person_posts WHERE person_id=940111; UPDATE featured_people SET x_profile_url="+("'https://x.com/fixtureofficial'" if social else 'NULL')+",threads_profile_url="+("'https://www.threads.net/@fixtureofficial'" if social else 'NULL')+",youtube_profile_url="+("'"+youtube+"'" if youtube else 'NULL')+" WHERE id=940111;")

    def candidates(self,value,platforms):
        require(set(value)=={'candidates'},'Candidate list exact DTO keys')
        rows=value['candidates'];equal(len(rows),len(platforms),'candidate.count')
        require(len({row['url'] for row in rows})==len(rows),'Candidate URL deduplication')
        equal(sorted(row['sourceType'] for row in rows),sorted(platforms),'candidate.platforms')
        for row in rows:
            require(set(row)=={'id','sourceType','title','url','publishedAt','status','createdAt'},'Candidate exact fields')
            equal(row['status'],'PENDING','candidate.not-auto-approved')
            equal(row['createdAt'],self.db_stamp('featured_person_posts',row['id']),'candidate.createdAt')
            expected={X:('X','Fixture X',FROM+'T00:00:00Z'),THREADS:('THREADS','Fixture Threads',TO+'T00:00:00Z'),'https://www.youtube.com/watch?v='+V1:('YOUTUBE','Fixture Video',AFTER),'https://www.youtube.com/watch?v='+V2:('YOUTUBE','Second Page','2020-02-11T14:59:59Z')}
            require(row['url'] in expected,'Only cited official in-period candidates accepted')
            kind,title,when=expected[row['url']];equal([row['sourceType'],row['title'],row['publishedAt']],[kind,title,when],'candidate.source-fields')
        equal(self.db.query("SELECT count(*) FROM featured_person_posts WHERE person_id=940111 AND status='APPROVED'"),0,'db.no-auto-approval')
        return rows

    def main(self,url):
        endpoint=urlsplit(url);validate_local_url(endpoint.scheme+'://'+endpoint.netloc);require(endpoint.path=='/__test__/state' and not endpoint.query and not endpoint.fragment,'Invalid social control URL');self.control_url=url
        for label,path,method in [('youtube',YOUTUBE,'GET'),('social',SOCIAL,'GET'),('collect',COLLECT,'POST')]:
            for member,status,code in ((None,401,'UNAUTHORIZED'),(USER,403,'FORBIDDEN')):
                self.run('social-auth-'+label+'-'+str(member),lambda path=path,method=method,member=member,status=status,code=code:self.request(self.client(member),method,path,status,code=code,unchanged=True))
        def csrf():
            c=self.client();c.cookies.pop('XSRF-TOKEN',None);self.request(c,'POST',COLLECT,403,code='FORBIDDEN',csrf=False,unchanged=True)
        self.run('social-collect-csrf-required',csrf)
        def youtube():
            self.control('valid');expected=[]
            for ident,title,quality in ((V1,'Fixture Video','high'),(V2,'Fallback Thumbnail','medium')):
                expected.append(dict(title=title,url='https://www.youtube.com/watch?v='+ident,channelTitle='Fixture Channel',publishedAt=AFTER,thumbnailUrl='https://i.ytimg.com/vi/'+ident+'/fixture.jpg'))
            self.request(self.client(),'GET',YOUTUBE,200,expected=dict(items=expected),unchanged=True)
        self.run('social-youtube-search-exact-fields-missing-id-thumbnail-fallback',youtube)
        def social():
            self.control('valid');items=[dict(sourceType='THREADS' if 'threads.net' in item['url'] else 'X',**item) for item in social_items()]
            self.request(self.client(),'GET',SOCIAL,200,expected=dict(items=items),unchanged=True)
        self.run('social-search-cited-post-only-dedup-and-exact-dto',social)
        def uncited():
            self.control('uncited');self.request(self.client(),'GET',SOCIAL,200,expected=dict(items=[]),unchanged=True)
        self.run('social-search-uncited-valid-looking-posts-rejected',uncited)
        for platform,path,code,message in [('youtube',YOUTUBE,'YOUTUBE_API_REQUEST_FAILED','YouTube API 요청에 실패했습니다.'),('social',SOCIAL,'AI_SOCIAL_SEARCH_FAILED','Threads·X 게시물 검색에 실패했습니다.')]:
            def failure(platform=platform,path=path,code=code,message=message):
                self.control(platform+'-failure');self.request(self.client(),'GET',path,502,expected=dict(code=code,message=message),unchanged=True)
            self.run('social-'+platform+'-provider-failure-no-db-writes',failure)
        def collect():
            self.control('valid');self.profiles();rows=self.candidates(self.request(self.client(),'POST',COLLECT,200)[0],['X','THREADS','YOUTUBE','YOUTUBE'])
            require(self.control()['counts']['profile_pages']==2,'Both YouTube pages fetched')
            require(self.control()['counts']['channels']==1,'Handle resolved through channels API')
            before=self.db.snapshot();again=self.request(self.client(),'POST',COLLECT,200)[0];equal(again,dict(candidates=rows));equal(self.db.snapshot(),before,'db.collection-idempotent')
        self.run('social-profile-collect-exact-author-date-pagination-pending-idempotence',collect)
        for profile in ('https://www.youtube.com/channel/UCfixture','https://www.youtube.com/user/fixtureuser'):
            def profile_case(profile=profile):
                self.control('valid');self.profiles(profile,social=False);self.candidates(self.request(self.client(),'POST',COLLECT,200)[0],['YOUTUBE','YOUTUBE'])
                equal(self.control()['counts']['channels'],0 if '/channel/' in profile else 1,'youtube.profile-resolution')
            self.run('social-youtube-profile-'+('channel' if '/channel/' in profile else 'username'),profile_case)
        # URI.getPath in the original Java decodes the profile path before
        # forHandle is query-encoded once. The mock rejects double encoding.
        for label,profile in [('literal','https://www.youtube.com/@한국'),('percent-encoded','https://www.youtube.com/@%ED%95%9C%EA%B5%AD')]:
            def unicode_handle(profile=profile):
                self.control('valid');self.profiles(profile,social=False)
                self.candidates(self.request(self.client(),'POST',COLLECT,200)[0],['YOUTUBE','YOUTUBE'])
                equal(self.control()['counts']['channels'],1,'youtube.unicode-handle-resolved')
            self.run('social-youtube-unicode-handle-'+label,unicode_handle)
        for mode,kinds in [('social-failure',['YOUTUBE','YOUTUBE']),('youtube-failure',['X','THREADS'])]:
            def partial(mode=mode,kinds=kinds):
                self.control(mode);self.profiles();self.candidates(self.request(self.client(),'POST',COLLECT,200)[0],kinds)
            self.run('social-collection-partial-'+mode+'-preserves-other-source',partial)
        def all_fail():
            self.control('failure');self.profiles();self.request(self.client(),'POST',COLLECT,502,expected=dict(code='AI_SOCIAL_SEARCH_FAILED',message='Threads·X 게시물 검색에 실패했습니다.'),unchanged=True)
        self.run('social-all-providers-failed-first-error-no-writes',all_fail)
        def invalid_period():
            self.control('valid');self.profiles();self.request(self.client(),'POST',PEOPLE+'/940111/post-candidates/collect?from=2020-02-11&to=2020-02-10',400,expected=dict(code='FEATURED_PERSON_POST_COLLECTION_PERIOD_INVALID',message='수집 기간은 시작일이 종료일보다 늦지 않은 최대 31일이어야 합니다.'),unchanged=True)
            equal(self.control()['counts'],dict(search=0,channels=0,social=0,profile_pages=0),'provider.invalid-period-zero-calls')
        self.run('social-invalid-period-rejected-before-any-provider-call',invalid_period)
        self.control('valid')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--database',required=True);parser.add_argument('--jwt-secret-file',required=True,type=Path);parser.add_argument('--issuer',default='daynomy');parser.add_argument('--mock-control-url',required=True);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    report=dict(contract='Independent original Java social and YouTube local-provider contracts',results=[],environmentLimited=[dict(case='real-external-social-providers',status='unverified',reason='Deterministic local providers; no real Google/OpenAI calls')])
    try:
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True);require(len(key)>=32,'JWT fixture key too short')
        suite=SocialSuite(validate_local_url(args.base_url),TestDatabase(args.database),key,args.issuer);suite.main(args.mock_control_url);report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.SubprocessError):report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']);report['failed']=len(report['results'])-report['passed'];args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],failed=report['failed'])));return int(report['failed']>0)


if __name__=='__main__':sys.exit(main())
