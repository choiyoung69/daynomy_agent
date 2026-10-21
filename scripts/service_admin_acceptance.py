#!/usr/bin/env python3
"""Independent F12 native HTTP/PG tests from original Java controllers/DTOs/services.

Basis: feedback/content/person/news admin controllers, services, domain URL
normalization and Flyway V1..53. No app implementation reads or imports.
Reserve 940101..940199 (within the coordinator's 940001..940199 allocation).
No server/provider/DB startup. Coordinator serializes native DB execution.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import http.client
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal, page
from service_core_acceptance import Suite, literal

ADMIN, USER, A, B = 940101,940102,940101,940102
F='/api/admin/feedbacks'; C='/api/admin/assets/940101/contents'; PEOPLE='/api/admin/people'; NEWS='/api/admin/news'
T='2090-01-01T00:00:00Z'
ERRORS={'FEEDBACK_NOT_FOUND':'피드백을 찾을 수 없습니다.','ASSET_NOT_FOUND':'자산을 찾을 수 없습니다.',
        'ASSET_CONTENT_NOT_FOUND':'종목 관련 자료를 찾을 수 없습니다.','ASSET_CONTENT_ALREADY_EXISTS':'이미 등록된 URL입니다.',
        'FEATURED_PERSON_NOT_FOUND':'주요 인물을 찾을 수 없습니다.','FEATURED_PERSON_ALREADY_EXISTS':'이미 등록된 인물입니다.',
        'FEATURED_PERSON_POST_NOT_FOUND':'주요 인물 게시물을 찾을 수 없습니다.','FEATURED_PERSON_POST_ALREADY_EXISTS':'이미 등록된 게시물 URL입니다.',
        'FEATURED_PERSON_INVALID_SOCIAL_URL':'계정 또는 게시물 URL이 올바르지 않습니다.',
        'FEATURED_PERSON_POST_CANDIDATE_NOT_FOUND':'수집한 게시물 후보를 찾을 수 없습니다.',
        'FEATURED_PERSON_POST_CANDIDATE_NOT_PENDING':'대기 중인 게시물 후보만 검토할 수 있습니다.',
        'NEWS_NOT_FOUND':'해당 뉴스를 찾을 수 없습니다.','NEWS_NOT_DRAFT':'초안 상태의 뉴스만 발행 또는 거절할 수 있습니다.'}


def fixture_sql():
    sql="""DELETE FROM stock_related_contents WHERE asset_id IN(940101,940102) OR news_id IN(SELECT id FROM news WHERE title LIKE 'Admin Fixture%');
DELETE FROM news_keyword WHERE news_id IN(SELECT id FROM news WHERE title LIKE 'Admin Fixture%');
DELETE FROM news_market_analysis WHERE news_id IN(SELECT id FROM news WHERE title LIKE 'Admin Fixture%');
DELETE FROM news WHERE title LIKE 'Admin Fixture%';
DELETE FROM featured_people WHERE id BETWEEN 940101 AND 940199 OR name LIKE 'Admin Fixture%';
DELETE FROM feedbacks WHERE id BETWEEN 940101 AND 940199;
"""
    for member,role in ((ADMIN,'ADMIN'),(USER,'USER')):
        sql += ("INSERT INTO members(id,provider,provider_id,email,nickname,role,status,created_at,updated_at) VALUES("+
                ','.join(map(literal,[member,'GOOGLE','admin-fixture-'+str(member),str(member)+'@fixture.invalid','AdminFixture'+str(member),role,'ACTIVE']))+
                ",now(),now()) ON CONFLICT(id) DO UPDATE SET role=excluded.role,status='ACTIVE',withdrawn_at=NULL;\n")
    for asset in (A,B):
        sql += ("INSERT INTO assets(id,name,category,asset_code,market,listed,created_at,updated_at) VALUES("+
                ','.join(map(literal,[asset,'Admin Fixture Asset '+str(asset),'STOCK','ADMIN'+str(asset),'KOSPI']))+
                ",true,now(),now()) ON CONFLICT(id) DO UPDATE SET name=excluded.name;\n")
    for ident in (940101,940102,940103):
        sql += ("INSERT INTO feedbacks(id,content,page_path,status,created_at,updated_at) VALUES("+
                ','.join(map(literal,[ident,'Admin fixture '+str(ident),'/fixture','PENDING',T,T]))+");\n")
    for ident in (940111,940112):
        sql += ("INSERT INTO featured_people(id,name,created_at,updated_at) VALUES("+
                ','.join(map(literal,[ident,'Admin Fixture Person '+str(ident),T,T]))+");\n")
    for ident,person,status in ((940121,940111,'PENDING'),(940122,940111,'APPROVED'),(940123,940112,'PENDING')):
        sql += ("INSERT INTO featured_person_posts(id,person_id,source_type,title,url,published_at,status,created_at,updated_at) VALUES("+
                ','.join(map(literal,[ident,person,'X','Candidate '+str(ident),'https://x.com/adminfixture/status/'+str(ident),T,status,T,T]))+");\n")
    return sql


def feedback(ident=940101,status='PENDING',updated=T):
    return dict(id=ident,content='Admin fixture '+str(ident),pagePath='/fixture',status=status,createdAt=T,updatedAt=updated)


def post(ident=940121):
    return dict(id=ident,sourceType='X',title='Candidate '+str(ident),url='https://x.com/adminfixture/status/'+str(ident),publishedAt=T,createdAt=T)


class AdminSuite(Suite):
    def client(self,member=ADMIN,token=None):
        client=super().client(member,token)
        if member==ADMIN: client.cookies['access_token']=token or self.jwt(ADMIN,role='ADMIN')
        return client

    def run(self,name,fn):
        try:
            self.db.seed(fixture_sql()); fn(); self.results.append(dict(case=name,passed=True))
        except AssertionError as error:
            self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):
            self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))

    def error(self,method,path,code,status=404,data=None):
        return self.request(self.client(),method,path,status,data,expected=dict(code=code,message=ERRORS[code]),unchanged=True)

    def db_stamp(self,table,ident,column='created_at'):
        value=self.db.query('SELECT to_json('+column+') FROM '+table+' WHERE id='+str(int(ident)))
        return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')

    def content(self,asset=A,**changes):
        data=dict(sourceType='X',title='  Admin Fixture Content  ',url='https://example.test/admin-fixture',publishedDate='2020-01-02')
        data.update(changes)
        value,_=self.request(self.client(),'POST',f'/api/admin/assets/{asset}/contents',201,data)
        require(type(value.get('id')) is int and value['id']>0,'Created content ID')
        expected=dict(id=value['id'],assetId=asset,sourceType=data['sourceType'],title=data['title'].strip(),url=data['url'],imageUrl=data.get('imageUrl'),createdAt=self.db_stamp('stock_related_contents',value['id']),publishedDate=data.get('publishedDate') or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat())
        require(isinstance(expected['createdAt'],str),'Content creation timestamp')
        equal(value,expected)
        equal(self.db.query('SELECT to_json(title) FROM stock_related_contents WHERE id='+str(value['id'])),expected['title'],'db.content.title')
        return value

    def person(self):
        value,_=self.request(self.client(),'POST',PEOPLE,201,dict(name='  Admin Fixture Created  ',xProfileUrl='https://x.com/adminfixture/?tracking=yes'))
        require(type(value.get('id')) is int and value['id']>0,'Created person ID')
        equal(value,dict(id=value['id'],name='Admin Fixture Created',xProfileUrl='https://x.com/adminfixture',threadsProfileUrl=None,youtubeProfileUrl=None,profileImageUrl=None,createdAt=self.db_stamp('featured_people',value['id']),posts=[]))
        require(isinstance(value['createdAt'],str),'Person creation timestamp')
        return value

    def feedback_cases(self):
        self.run('feedback-admin-detail-exact-dto-read-only',lambda:self.request(self.client(),'GET',F+'/940101',200,expected=feedback(),unchanged=True))
        def listing():
            total=self.db.query('SELECT count(*) FROM feedbacks')
            self.request(self.client(),'GET',F+'?page=1&size=2',200,expected=page([feedback(940103),feedback(940102)],size=2,total=total),unchanged=True)
        self.run('feedback-page-created-tie-id-desc-and-db-total',listing)
        def update():
            value,_=self.request(self.client(),'PATCH',F+'/940101',200,dict(status='RESOLVED'))
            require(isinstance(value.get('updatedAt'),str),'Feedback updated timestamp')
            equal(value,feedback(status='RESOLVED',updated=self.db_stamp('feedbacks',940101,'updated_at')))
            equal(self.db.query('SELECT to_json(status) FROM feedbacks WHERE id=940101'),'RESOLVED','db.feedback.status')
            self.request(self.client(),'GET',F+'/940101',200,expected=value,unchanged=True)
        self.run('feedback-update-status-persists-and-detail-matches',update)
        def delete():
            self.request(self.client(),'DELETE',F+'/940101',204)
            equal(self.db.query('SELECT count(*) FROM feedbacks WHERE id=940101'),0,'db.feedback.deleted')
            self.error('GET',F+'/940101','FEEDBACK_NOT_FOUND')
        self.run('feedback-delete-persists-404-afterward',delete)
        self.run('feedback-missing-404-exact-error',lambda:self.error('PATCH',F+'/940199','FEEDBACK_NOT_FOUND',data=dict(status='RESOLVED')))
        self.run('feedback-null-status-validation',lambda:self.invalid(self.client(),'PATCH',F+'/940101',dict(status=None),'status','피드백 상태를 선택해주세요.'))
        for query,field,reason in [('?page=0','page','페이지 번호는 1 이상이어야 합니다.'),('?size=101','size','페이지 크기는 100 이하여야 합니다.'),('?page=abc','page','타입이 올바르지 않습니다.')]:
            self.run('feedback-query-'+query,lambda query=query,field=field,reason=reason:self.invalid(self.client(),'GET',F+query,None,field,reason))
        self.run('feedback-nonpositive-id',lambda:self.invalid(self.client(),'GET',F+'/0',None,'id'))

    def security_cases(self):
        for path in (F,C,PEOPLE,NEWS):
            for member,status,code in ((None,401,'UNAUTHORIZED'),(USER,403,'FORBIDDEN')):
                self.run('admin-auth-'+str(member)+'-'+path,lambda path=path,member=member,status=status,code=code:self.request(self.client(member),'GET',path,status,code=code,unchanged=True))
        for mode in ('missing','mismatch'):
            def csrf(mode=mode):
                c=self.client()
                if mode=='missing': c.cookies.pop('XSRF-TOKEN',None)
                self.request(c,'PATCH',F+'/940101',403,dict(status='RESOLVED'),code='FORBIDDEN',unchanged=True,csrf=mode=='mismatch',headers={c.csrf[0]:'bad'} if mode=='mismatch' else None)
            self.run('admin-feedback-csrf-'+mode,csrf)

    def content_cases(self):
        def create_list():
            item=self.content()
            self.request(self.client(),'GET',C,200,expected=dict(assetId=A,assetCode='ADMIN940101',assetName='Admin Fixture Asset 940101',contents=[item]),unchanged=True)
        self.run('content-create-trim-persist-and-list-full-dto',create_list)
        self.run('content-published-date-default-seoul-registration-date',lambda:self.content(publishedDate=None))
        def duplicate():
            self.content(); self.error('POST',C,'ASSET_CONTENT_ALREADY_EXISTS',409,dict(sourceType='X',title='Other title',url='https://example.test/admin-fixture'))
            self.content(B)
        self.run('content-duplicate-per-asset-and-same-url-other-asset-allowed',duplicate)
        def ownership():
            item=self.content()
            self.error('DELETE',f'/api/admin/assets/{B}/contents/'+str(item['id']),'ASSET_CONTENT_NOT_FOUND')
            self.request(self.client(),'DELETE',C+'/'+str(item['id']),204)
            equal(self.db.query('SELECT count(*) FROM stock_related_contents WHERE id='+str(item['id'])),0,'db.content.deleted')
        self.run('content-delete-asset-ownership-and-persistent-delete',ownership)
        self.run('content-unknown-asset',lambda:self.error('GET','/api/admin/assets/940199/contents','ASSET_NOT_FOUND'))
        for name,change,field,reason in [('title',dict(title=' '),'title','제목을 입력해주세요.'),('url',dict(url='ftp://example.test/a'),'url','http 또는 https URL을 입력해주세요.'),('source',dict(sourceType=None),'sourceType','출처를 선택해주세요.')]:
            data=dict(sourceType='X',title='Valid',url='https://example.test/valid'); data.update(change)
            self.run('content-validation-'+name,lambda data=data,field=field,reason=reason:self.invalid(self.client(),'POST',C,data,field,reason))

    def people_cases(self):
        def create_update():
            old=self.person()
            body=dict(name='Admin Fixture Updated',xProfileUrl='https://twitter.com/adminfixture/',threadsProfileUrl='https://threads.net/@adminfixture/')
            value,_=self.request(self.client(),'PUT',PEOPLE+'/'+str(old['id']),200,body)
            equal(value,dict(old,name=body['name'],xProfileUrl='https://twitter.com/adminfixture',threadsProfileUrl='https://threads.net/@adminfixture'))
            self.request(self.client(),'DELETE',PEOPLE+'/'+str(old['id']),204)
            equal(self.db.query('SELECT count(*) FROM featured_people WHERE id='+str(old['id'])),0,'db.person.deleted')
        self.run('people-create-normalize-update-delete-full-dto',create_update)
        self.run('people-duplicate-name',lambda:self.error('POST',PEOPLE,'FEATURED_PERSON_ALREADY_EXISTS',409,dict(name='Admin Fixture Person 940111')))
        self.run('people-invalid-social-host',lambda:self.error('POST',PEOPLE,'FEATURED_PERSON_INVALID_SOCIAL_URL',400,dict(name='Admin Fixture Invalid',xProfileUrl='https://evil.example/profile')))
        self.run('people-name-required',lambda:self.invalid(self.client(),'POST',PEOPLE,dict(name=' '),'name','인물 이름을 입력해주세요.'))
        def create_post():
            value,_=self.request(self.client(),'POST',PEOPLE+'/940111/posts',201,dict(sourceType='X',url='https://x.com/adminfixture/status/123456/?ref=1',publishedAt=T))
            equal(value,dict(id=value['id'],sourceType='X',title='Admin Fixture Person 940111 X 게시물',url='https://x.com/adminfixture/status/123456',publishedAt=T,createdAt=self.db_stamp('featured_person_posts',value['id'])))
            self.error('DELETE',PEOPLE+'/940112/posts/'+str(value['id']),'FEATURED_PERSON_POST_NOT_FOUND')
            self.request(self.client(),'DELETE',PEOPLE+'/940111/posts/'+str(value['id']),204)
        self.run('people-post-default-title-url-normalization-ownership-delete',create_post)
        def pending():
            self.request(self.client(),'GET',PEOPLE+'/940111/post-candidates',200,expected=dict(candidates=[dict(post(),status='PENDING')]),unchanged=True)
        self.run('candidate-list-pending-only-exact-dto',pending)
        def approve():
            self.request(self.client(),'POST',PEOPLE+'/940111/post-candidates/940121/approve',200,expected=post())
            equal(self.db.query('SELECT to_json(status) FROM featured_person_posts WHERE id=940121'),'APPROVED','db.candidate.approved')
            self.error('POST',PEOPLE+'/940111/post-candidates/940121/approve','FEATURED_PERSON_POST_CANDIDATE_NOT_PENDING',409)
        self.run('candidate-approve-persists-and-repeat-conflict',approve)
        def reject():
            self.request(self.client(),'POST',PEOPLE+'/940111/post-candidates/940121/reject',204)
            equal(self.db.query('SELECT to_json(status) FROM featured_person_posts WHERE id=940121'),'REJECTED','db.candidate.rejected')
        self.run('candidate-reject-persists',reject)
        self.run('candidate-person-ownership',lambda:self.error('POST',PEOPLE+'/940111/post-candidates/940123/approve','FEATURED_PERSON_POST_CANDIDATE_NOT_FOUND'))
        for operation in ('approve','reject'):
            def bulk(operation=operation):
                code='FEATURED_PERSON_POST_CANDIDATE_NOT_FOUND'
                expected=dict(succeeded=[dict(candidateId=940121,post=post() if operation=='approve' else None)],failed=[dict(candidateId=940123,errorCode=code,message=ERRORS[code]),dict(candidateId=940199,errorCode=code,message=ERRORS[code])])
                self.request(self.client(),'POST',PEOPLE+'/940111/post-candidates/bulk-'+operation,200,dict(candidateIds=[940121,940121,940123,940199]),expected=expected)
                equal(self.db.query('SELECT to_json(status) FROM featured_person_posts WHERE id=940121'),'APPROVED' if operation=='approve' else 'REJECTED','db.bulk.partial-success')
                equal(self.db.query('SELECT to_json(status) FROM featured_person_posts WHERE id=940123'),'PENDING','db.bulk.other-person-unchanged')
            self.run('candidate-bulk-'+operation+'-deduplicate-partial-success-ownership',bulk)

    def multipart(self,c,method,path,data,status):
        boundary='admin-fixture-boundary'
        body=('--'+boundary+'\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n'+json.dumps(data,ensure_ascii=False)+'\r\n--'+boundary+'--\r\n').encode()
        endpoint=urlsplit(self.base); connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port or 80,timeout=15)
        headers={'Content-Type':'multipart/form-data; boundary='+boundary,'Cookie':'; '.join(k+'='+v for k,v in c.cookies.items()),c.csrf[0]:c.csrf[1]}
        try:
            connection.request(method,path,body,headers); response=connection.getresponse(); raw=response.read(1000001)
            require(response.status==status,'Multipart HTTP status expected '+str(status)+' got '+str(response.status))
            require('application/json' in response.getheader('Content-Type',''),'Multipart JSON media type')
            require(len(raw)<=1000000,'Multipart response size limit')
            return json.loads(raw,parse_float=Decimal)
        finally: connection.close()

    def news_create(self):
        data=dict(title='Admin Fixture News',content='Admin fixture body',sources=[dict(name='Fixture',url='https://example.test/source')],category='STOCK',assetIds=[A])
        value=self.multipart(self.client(),'POST',NEWS,data,201)
        expected=dict(id=value['id'],title=data['title'],content=data['content'],imageUrl=None,imageSource=dict(name='',url='',author='',license='',licenseUrl='',type='NONE'),sources=data['sources'],category='STOCK',publishedAt=None,status='DRAFT',relatedAssets=[dict(assetId=A,assetCode='ADMIN940101',name='Admin Fixture Asset 940101',category='STOCK',market='KOSPI',currency='KRW')])
        equal(value,expected); return value,data

    def news_cases(self):
        def create_read():
            value,_=self.news_create()
            self.request(self.client(),'GET',NEWS+'/'+str(value['id']),200,expected=value,unchanged=True)
            self.request(self.client(None),'GET','/api/news/'+str(value['id']),404,expected=dict(code='NEWS_NOT_FOUND',message=ERRORS['NEWS_NOT_FOUND']),unchanged=True)
        self.run('news-multipart-draft-create-admin-detail-public-hidden',create_read)
        def listing():
            value,_=self.news_create()
            item={key:value[key] for key in ('id','title','imageUrl','sources','category','publishedAt','status')}
            item['createdAt']=self.db_stamp('news',value['id'])
            self.request(self.client(),'GET',NEWS+'?q=Admin%20Fixture%20News&status=DRAFT&category=STOCK',200,expected=page([item]),unchanged=True)
        self.run('news-admin-list-filters-draft-category-keywords-full-dto',listing)
        def update():
            value,data=self.news_create(); data.update(title='Admin Fixture Updated News',content='Updated body',category='ETF',assetIds=[])
            actual=self.multipart(self.client(),'PUT',NEWS+'/'+str(value['id']),data,200)
            equal(actual,dict(value,title=data['title'],content=data['content'],category='ETF',relatedAssets=[]))
            equal(self.db.query('SELECT count(*) FROM stock_related_contents WHERE news_id='+str(value['id'])),0,'db.news.related-assets-cleared')
        self.run('news-multipart-update-clears-related-assets',update)
        def reject():
            value,_=self.news_create()
            self.request(self.client(),'POST',NEWS+'/'+str(value['id'])+'/reject',200,expected=dict(value,status='REJECTED'))
            self.error('POST',NEWS+'/'+str(value['id'])+'/reject','NEWS_NOT_DRAFT',409)
        self.run('news-reject-and-repeated-reject-conflict',reject)
        def delete():
            value,_=self.news_create(); self.request(self.client(),'DELETE',NEWS+'/'+str(value['id']),204)
            equal(self.db.query('SELECT to_json(status) FROM news WHERE id='+str(value['id'])),'DELETED','db.news.soft-delete')
            self.request(self.client(None),'GET','/api/news/'+str(value['id']),404,expected=dict(code='NEWS_NOT_FOUND',message=ERRORS['NEWS_NOT_FOUND']),unchanged=True)
        self.run('news-delete-persists-deleted-status-and-public-hidden',delete)

    def main(self,sections):
        self.security_cases()
        for section in sections:
            getattr(self,section+'_cases')()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True); parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',required=True,type=Path); parser.add_argument('--issuer',default='daynomy')
    parser.add_argument('--sections',default='feedback,content,people,news',help='Comma-separated domain sections; authentication checks always run')
    parser.add_argument('--output',required=True,type=Path); args=parser.parse_args(argv)
    report=dict(contract='Independent F12 original Java CRUD/security contract',results=[],passed=0,failed=0,environmentLimited=[dict(case='admin-provider-operations',status='unverified',reason='Publish, image storage/generation, external searches/collection require separate provider fixtures')])
    try:
        sections=args.sections.split(','); require(bool(sections) and set(sections)<=set(('feedback','content','people','news')),'Unknown admin test section')
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True); require(len(key)>=32,'JWT fixture key too short')
        suite=AdminSuite(validate_local_url(args.base_url),TestDatabase(args.database),key,args.issuer)
        suite.main(sections); report['results']=suite.results
        for section in set(('feedback','content','people','news'))-set(sections):
            report['environmentLimited'].append(dict(case=section,status='unverified',reason='Section not selected for this run'))
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.TimeoutExpired):
        report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']); report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
