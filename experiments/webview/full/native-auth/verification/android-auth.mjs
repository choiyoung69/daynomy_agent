import {chromium} from '../../../../../clients/webview/fullweb/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';

const origin='http://127.0.0.1:18082';
const device='emulator-5576';
const adbPath='/Users/seoyeong/Library/Android/sdk/platform-tools/adb';
const adb=(...args)=>execFileSync(adbPath,['-s',device,...args],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:15000});
const metadata=JSON.parse(await readFile(new URL('../../runtime/oidc.json',import.meta.url),'utf8'));
const report={device,provider:'ephemeral locally signed OIDC; not real Google',mode:'actual full Android WebView and external Chrome with real Rust/private DB',steps:[],api:[],cookieProperties:[]};
let step='connect-webview',webBrowser,externalBrowser,callbackLocation;
const save=()=>writeFile(new URL('./android-auth.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
const mark=value=>{report.steps.push(value);console.log(value)};
const shellQuote=value=>"'"+value.replace(/'/g,"'\\''")+"'";
async function connect(port){return chromium.connectOverCDP('http://127.0.0.1:'+port,{noDefaults:true,timeout:15000})}
async function browserOpenConfirmation(){
  // Capture UI only in memory: full browser URLs may contain authorization data.
  let xml='';try{xml=adb('exec-out','uiautomator','dump','/dev/tty')}catch{return false}
  for(const node of xml.matchAll(/<node\b[^>]*>/g)){
    if(!/text="(?:Open|열기|Continue|계속)"/.test(node[0]))continue;
    const bounds=node[0].match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);if(!bounds)continue;
    adb('shell','input','tap',String(Math.floor((+bounds[1]+ +bounds[3])/2)),String(Math.floor((+bounds[2]+ +bounds[4])/2)));return true;
  }return false;
}
async function pressNativeRetry(){
  adb('shell','am','start','-W','-n','com.daynomy.webview.full/com.daynomy.webview.MainActivity');
  const xml=adb('exec-out','uiautomator','dump','/dev/tty');
  for(const node of xml.matchAll(/<node\b[^>]*>/g)){
    if(!/text="다시 시도"/.test(node[0]))continue;
    const bounds=node[0].match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);if(!bounds)continue;
    adb('shell','input','tap',String(Math.floor((+bounds[1]+ +bounds[3])/2)),String(Math.floor((+bounds[2]+ +bounds[4])/2)));return;
  }throw new Error('Native retry unavailable');
}
try{
  webBrowser=await connect(Number(process.env.WEBVIEW_CDP_PORT||19276));
  const context=webBrowser.contexts()[0],page=context.pages()[0];assert.ok(page);
  page.setDefaultTimeout(20000);page.setDefaultNavigationTimeout(20000);
  page.on('response',response=>{const u=new URL(response.url());if(u.origin===origin&&u.pathname.startsWith('/api/'))report.api.push({path:u.pathname,status:response.status(),method:response.request().method()})});
  await page.goto(origin+'/mypage');await page.waitForURL(u=>u.origin===origin&&u.pathname==='/login');
  mark('actual guest protected MyPage redirects to login');
  step='external-browser-launch';
  adb('shell','am','start','-W','-a','android.intent.action.VIEW','-d','about:blank','com.android.chrome');
  externalBrowser=await connect(Number(process.env.CHROME_CDP_PORT||19376));
  adb('shell','am','start','-W','-n','com.daynomy.webview.full/com.daynomy.webview.MainActivity');
  const previousStates=new Set(externalBrowser.contexts().flatMap(c=>c.pages()).map(p=>{try{return new URL(p.url()).searchParams.get('state')}catch{return null}}));
  await page.getByRole('link',{name:'Google로 시작하기'}).click({noWaitAfter:true});
  // External Chrome must be preconfigured/forwarded by the verifier, never by source changes.
  for(let attempt=0;attempt<20;attempt++){
    try{externalBrowser=await connect(Number(process.env.CHROME_CDP_PORT||19376));break}catch{await new Promise(resolve=>setTimeout(resolve,500))}
  }
  assert.ok(externalBrowser);let externalPage;
  for(let attempt=0;attempt<30;attempt++){
    externalPage=externalBrowser.contexts().flatMap(c=>c.pages()).find(p=>{try{const u=new URL(p.url());return u.origin===metadata.base_url&&u.pathname==='/authorize'&&!previousStates.has(u.searchParams.get('state'))}catch{return false}});
    if(externalPage)break;await new Promise(resolve=>setTimeout(resolve,500));
  }
  assert.ok(externalPage);report.externalEngine=await externalPage.evaluate(()=>navigator.userAgent);
  assert.equal(new URL(page.url()).origin,origin);mark('original login link launches external Chrome while WebView stays trusted');
  step='cancel-and-retry';
  const cancelledStates=new Set(externalBrowser.contexts().flatMap(c=>c.pages()).map(p=>{try{return new URL(p.url()).searchParams.get('state')}catch{return null}}));
  await pressNativeRetry();await page.getByRole('link',{name:'Google로 시작하기'}).waitFor();
  await page.getByRole('link',{name:'Google로 시작하기'}).click({noWaitAfter:true});
  for(let attempt=0;attempt<30;attempt++){
    externalPage=externalBrowser.contexts().flatMap(c=>c.pages()).find(p=>{try{const u=new URL(p.url());return u.origin===metadata.base_url&&u.pathname==='/authorize'&&!cancelledStates.has(u.searchParams.get('state'))}catch{return false}});
    if(externalPage)break;await new Promise(resolve=>setTimeout(resolve,500));
  }
  assert.ok(externalPage);mark('return from unfinished browser login; native retry cancels and unlocks a fresh login');
  step='register-local-authorization';
  const query=new URL(externalPage.url()).searchParams;
  assert.equal(query.get('redirect_uri'),metadata.callback);assert.ok(query.get('state')&&query.get('nonce'));
  const code=randomUUID(),identity=randomUUID();
  const registered=await fetch(metadata.control_url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({register:{code,nonce:query.get('nonce'),challenge:query.get('code_challenge')||'',sub:'webview-native-auth-'+identity,email:'native-auth-'+identity+'@fixture.invalid',mode:'valid'}})});
  assert.equal(registered.status,200);
  const serverCallback=metadata.callback+'?'+new URLSearchParams({code,state:query.get('state')});
  step='retrieve-real-server-callback';
  const callbackResponse=await externalPage.request.get(serverCallback,{maxRedirects:0});
  report.serverCallbackStatus=callbackResponse.status();assert.equal(callbackResponse.status(),302);
  callbackLocation=callbackResponse.headers()['location'];assert.ok(callbackLocation?.startsWith('org.daynomy.app://auth/callback?'));
  report.delivery='Real Rust callback302 retrieved with external Chrome context cookies through verification APIRequestContext; same Chrome page then opens the returned app URI by a user-gesture link. Automatic HTTP302-to-app dispatch is not claimed by this adaptation.';
  step='wrong-state-callback';
  const wrong=new URL(callbackLocation);wrong.searchParams.set('state',randomUUID().replaceAll('-',''));
  adb('shell','am','start','-W','-n','com.daynomy.webview.full/com.daynomy.webview.MainActivity','-a','android.intent.action.VIEW','-d',shellQuote(wrong.href));
  const denied=await page.evaluate(async()=> (await fetch('/api/users/me',{credentials:'include'})).status);assert.equal(denied,401);
  mark('wrong-state app callback installs no session before legitimate completion');
  adb('shell','am','start','-W','-n','com.android.chrome/com.google.android.apps.chrome.Main');
  // This synthetic provider completion link preserves an actual browser user gesture.
  await externalPage.evaluate(url=>{document.body.replaceChildren();const link=document.createElement('a');link.textContent='로컬 테스트 인증 완료';link.href=url;document.body.append(link)},callbackLocation);
  step='provider-callback-and-os-return';
  await externalPage.getByRole('link',{name:'로컬 테스트 인증 완료'}).click({noWaitAfter:true});
  for(let attempt=0;attempt<20;attempt++){
    try{if(await page.getByRole('link',{name:'마이페이지',exact:true}).isVisible())break}catch{}
    if(attempt===3||attempt===8)await browserOpenConfirmation();
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  assert.ok(callbackLocation,'real Rust callback must issue the app-scheme redirect');
  await page.goto(origin+'/mypage');await page.getByRole('button',{name:'닉네임 변경',exact:true}).waitFor();
  mark('external browser callback returns to app; native exchange installs session; actual protected MyPage loads');
  step='cookie-boundaries';
  const inspector=await context.newCDPSession(page);
  const cookies=(await inspector.send('Network.getCookies',{urls:[origin+'/',origin+'/api/auth']})).cookies;
  report.cookieProperties=cookies.map(({name,path,domain,httpOnly,secure,sameSite})=>({name,path,domain,httpOnly,secure,sameSite}));
  for(const name of ['access_token','refresh_token'])assert.ok(cookies.some(cookie=>cookie.name===name&&cookie.httpOnly));
  const names=await page.evaluate(()=>document.cookie.split(';').map(part=>part.trim().split('=')[0]));
  assert.ok(!names.includes('access_token')&&!names.includes('refresh_token'));mark('OS cookie store retains HttpOnly access and refresh; JavaScript cannot read them');
  step='nickname-and-role';
  await page.getByRole('button',{name:'닉네임 변경',exact:true}).click();await page.getByLabel('새 닉네임').fill('웹뷰기기'+Date.now().toString().slice(-5));
  const nickname=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/users/me'&&r.request().method()==='PATCH');
  await page.getByRole('button',{name:'닉네임 저장',exact:true}).click();assert.equal((await nickname).status(),200);
  await page.goto(origin+'/admin/news');await page.getByRole('heading',{name:'관리자 권한이 필요합니다.'}).waitFor();
  mark('actual member nickname PATCH200 and USER/admin boundary pass');
  step='logout';await page.goto(origin+'/mypage');await page.getByRole('button',{name:'로그아웃',exact:true}).click();await page.waitForURL(u=>u.origin===origin&&u.pathname==='/news');
  await page.goto(origin+'/mypage');await page.waitForURL(u=>u.origin===origin&&u.pathname==='/login');mark('actual logout204 removes protected access');
  step='replay-callback';
  // Explicit delivery is only a negative replay check, never the successful OS-return claim.
  adb('shell','am','start','-n','com.daynomy.webview.full/com.daynomy.webview.MainActivity','-a','android.intent.action.VIEW','-d',shellQuote(callbackLocation));
  await page.waitForTimeout(800);await page.goto(origin+'/mypage');await page.waitForURL(u=>u.origin===origin&&u.pathname==='/login');
  mark('replayed callback after logout does not restore authentication');
  report.status='passed';await page.goto(origin+'/login');await page.screenshot({path:new URL('./android-login-after-logout.png',import.meta.url).pathname});
}catch(error){report.status='failed';const message=String(error?.message||'');report.failure={step,name:error?.name||'Error',code:error?.code||null,classification:{timeout:message.includes('Timeout')||message.includes('ETIMEDOUT'),unsupportedBrowserContext:message.includes('Browser context management is not supported'),protocolError:message.includes('Protocol error'),targetClosed:message.includes('Target closed')}};console.log(JSON.stringify(report.failure));process.exitCode=1}
finally{await save();await Promise.race([Promise.allSettled([externalBrowser?.close(),webBrowser?.close()]),new Promise(resolve=>setTimeout(resolve,5000))]);process.exit(process.exitCode||0)}
