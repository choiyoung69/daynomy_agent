// Run against built app: WEBVIEW_FULL_ORIGIN=http://127.0.0.1:18082 node browser-smoke.mjs
// Playwright is supplied by the verification environment, not by the app dependency lock.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const origin=process.env.WEBVIEW_FULL_ORIGIN;
assert.ok(origin,'WEBVIEW_FULL_ORIGIN required (browser checks must not silently skip)');
assert.ok(['127.0.0.1','localhost'].includes(new URL(origin).hostname),'local test origin required');
const browser=await chromium.launch({headless:true});
try {
  const context=await browser.newContext({viewport:{width:390,height:844}});
  await context.addInitScript(()=>localStorage.setItem('daynomy:service-started:v1','1'));
  let role='guest'; const adminCalls=[];
  await context.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.startsWith('/api/admin/')) adminCalls.push(path);
    if(path==='/api/users/me') return route.fulfill({status:role==='guest'?401:200,contentType:'application/json',body:JSON.stringify(role==='guest'?{code:'UNAUTHORIZED',message:'로그인이 필요합니다.'}:{id:1,email:'fixture@example.invalid',name:null,nickname:'검증회원',role:'USER'})});
    if(path==='/api/auth/refresh') return route.fulfill({status:401,contentType:'application/json',body:'{"code":"UNAUTHORIZED"}'});
    // Deliberate failures exercise actual UI error/empty state, not fabricated happy data.
    return route.fulfill({status:503,contentType:'application/json',body:'{"code":"FIXTURE_UNAVAILABLE","message":"검증용 일시 오류"}'});
  });
  const page=await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  for(const [path,heading] of [['/login','DAYNOMY 로그인'],['/','내 포트폴리오'],['/news','소식'],['/news/contents','전체 콘텐츠'],['/search','소식 검색'],['/people','인물의 글']]){
    await page.goto(origin+path); await page.getByRole('heading',{name:heading,exact:true}).waitFor();
    assert.ok(!(await page.getByRole('link',{name:/리그/}).count()),'excluded league must not remain active navigation');
  }
  await page.goto(origin+'/mypage'); await page.waitForURL(/\/login\?/); assert.equal(new URL(page.url()).searchParams.get('returnTo'),'/mypage');
  await page.goto(origin+'/admin/news'); await page.waitForURL(/\/login\?/); assert.equal(new URL(page.url()).searchParams.get('returnTo'),'/admin/news');
  role='user'; await page.goto(origin+'/admin/news'); await page.getByRole('heading',{name:'관리자 권한이 필요합니다.'}).waitFor(); assert.equal(adminCalls.length,0);
  await page.goto(origin+'/'); await page.getByRole('button',{name:'피드백 보내기',exact:true}).click(); await page.getByRole('textbox',{name:'피드백 내용'}).waitFor();
  assert.deepEqual(errors,[],'unhandled client exceptions');
  console.log('PASS browser core route/gate/error-state smoke (synthetic API; not Rust/DB or native-host integration)');
} finally {await browser.close();}
