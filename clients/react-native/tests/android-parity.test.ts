import test from 'node:test';
import assert from 'node:assert/strict';
import {APIClient} from '../src/api.ts';

const item = {id:1,title:'합성 뉴스',category:'STOCK',imageUrl:null,publishedAt:null};
const page = {items:[item],page:1,size:9,totalPages:1,totalElements:1,hasNext:false};
function fixture(body:unknown, status=200) {
  const calls:{url:URL;init:RequestInit}[]=[];
  const api=new APIClient({baseURL:'http://localhost:18081',fetchImpl:(async (url:any,init:RequestInit)=>{
    calls.push({url:new URL(String(url)),init});
    return new Response(JSON.stringify(String(url).endsWith('/csrf') ? {headerName:'X-CSRF-TOKEN',token:'synthetic'} : body),{status:String(url).endsWith('/csrf')?200:status});
  }) as typeof fetch});
  return {api,calls};
}
test('오늘 뉴스는 query 없이 기존 page DTO와 nullable 이미지를 읽는다',async()=>{
  const {api,calls}=fixture(page);
  assert.deepEqual(await api.todayNews(),page);
  assert.equal(calls[0].url.pathname,'/api/news/today');
  assert.equal(calls[0].url.search,'');
});
test('오늘 뉴스의 잘못된 DTO는 빈 성공으로 바꾸지 않는다',async()=>{
  for(const raw of [{...page,items:[{...item,id:0}]},{...page,totalElements:-1},{...page,items:[{...item,imageUrl:23}]}]) {
    await assert.rejects(fixture(raw).api.todayNews());
  }
});
test('검색 content DTO를 page로 변환하고 서버 페이지로 다음 여부를 구한다',async()=>{
  const {api,calls}=fixture({content:[item],page:2,size:20,totalPages:3,totalElements:41});
  const result=await api.searchNews('금리 & ETF+',{page:2,category:'ETF',sort:'RELEVANCE'});
  assert.equal(result.hasNext,true);assert.deepEqual(result.items,[item]);
  assert.deepEqual(Object.fromEntries(calls[0].url.searchParams),{q:'금리 & ETF+',page:'2',size:'20',sort:'RELEVANCE',category:'ETF'});
});
test('검색 마지막 페이지와 빈 검색 응답',async()=>{
  const {api}=fixture({content:[],page:1,size:20,totalPages:0,totalElements:0});
  assert.deepEqual((await api.searchNews('없음')).items,[]);
  assert.equal((await api.searchNews('없음')).hasNext,false);
});
test('검색 입력 오류는 전송 전에 거절한다',async()=>{
  const {api,calls}=fixture(page);
  for(const q of ['', '   ', '!!!', 'a\nb', 'a\rb', 'a\u0085b', 'a\u2028b', '한'.repeat(101)]) await assert.rejects(api.searchNews(q));
  await assert.rejects(api.searchNews('삼성',{page:0}));
  await assert.rejects(api.searchNews('삼성',{sort:'UNKNOWN' as any}));
  assert.equal(calls.length,0);
});
test('잘못된 검색 content와 페이지는 거절한다',async()=>{
  for(const raw of [{items:[item],page:1,size:20,totalPages:1,totalElements:1},{content:[item],page:0,size:20,totalPages:1,totalElements:1}]) await assert.rejects(fixture(raw).api.searchNews('삼성'));
});
test('회원 보유 조정은 KRW 소수 원문과 CSRF를 보존한다',async()=>{
  const {api,calls}=fixture({assetId:7,quantity:2,averagePurchasePrice:70000});
  await api.updateHolding(7,'2','900719925474099.12');
  assert.equal(calls.length,2);assert.equal(calls[0].url.pathname,'/api/auth/csrf');
  assert.equal(calls[1].url.pathname,'/api/users/me/portfolio/holdings/7');
  assert.equal(calls[1].init.method,'PATCH');
  assert.equal(calls[1].init.body,'{"quantity":2,"averagePurchasePrice":900719925474099.12}');
  assert.equal(new Headers(calls[1].init.headers).get('X-CSRF-TOKEN'),'synthetic');
});
test('보유 수량과 평균가 오류는 전송하지 않는다',async()=>{
  const {api,calls}=fixture({});
  for(const q of ['0','-1','1.5','1e2','9007199254740992']) await assert.rejects(api.updateHolding(1,q,'100'));
  for(const price of ['0','-1','0.001','1.234','1e2','1000000000000000','NaN']) await assert.rejects(api.updateHolding(1,'1',price));
  await assert.rejects(api.updateHolding(0,'1','100'));assert.equal(calls.length,0);
});
test('보유 삭제는 CSRF DELETE 한 번만 전송한다',async()=>{
  const {api,calls}=fixture({},401);
  await assert.rejects(api.deleteHolding(7));
  assert.equal(calls.length,2);assert.equal(calls[1].init.method,'DELETE');
  assert.equal(calls[1].init.body,undefined);
  assert.equal(calls.filter(c=>c.url.pathname.includes('/refresh')).length,0);
});
test('조정401도 자동 재전송하지 않는다',async()=>{
  const {api,calls}=fixture({},401);await assert.rejects(api.updateHolding(7,'2','100'));
  assert.equal(calls.filter(c=>c.init.method==='PATCH').length,1);assert.equal(calls.length,2);
});
