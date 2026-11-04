import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root=resolve(fileURLToPath(new URL('../../..',import.meta.url)));
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const listen=server=>new Promise(r=>server.listen(0,'127.0.0.1',()=>r(server.address().port)));
const close=server=>new Promise(r=>server.close(r));
const stock={assetId:1,assetCode:'005930',name:'삼성전자 <img src=x onerror="window.__injected=1">',category:'STOCK',market:'KOSPI'};
async function start() {
  const script=join(root,'clients/webview/scripts/serve.mjs'); assert.ok(existsSync(script),`Missing implementation ${script}`);
  const requests=[];
  const backend=http.createServer((req,res)=>{
    requests.push({url:req.url,cookie:req.headers.cookie}); res.setHeader('Content-Type','application/json');
    if(req.url.startsWith('/api/stocks/1/price')) {res.end(JSON.stringify({assetId:1,assetCode:'005930',name:stock.name,baseDate:'2026-10-27',closePrice:71000})); return;}
    if(req.url.startsWith('/api/stocks?')) {res.end(JSON.stringify({stocks:[stock,{assetId:2,assetCode:'069500',name:'KODEX ETF',category:'ETF',market:'KOSPI'}]})); return;}
    res.statusCode=404;res.end('{}');
  });
  const apiPort=await listen(backend);
  const reservation=http.createServer();const port=await listen(reservation);await close(reservation);
  const child=spawn(process.execPath,[script,'--port',String(port),'--api-origin',`http://127.0.0.1:${apiPort}`],{cwd:root,stdio:['ignore','pipe','pipe']});
  let output='';child.stdout.on('data',x=>output+=x);child.stderr.on('data',x=>output+=x);
  const origin=`http://127.0.0.1:${port}`;
  try {
    for(let n=0;n<100;n++) {if(child.exitCode!==null) throw new Error(`Web server exited ${child.exitCode}: ${output}`);try{const r=await fetch(origin);if(r.ok)return {origin,requests,stop:async()=>{child.kill();await close(backend);}};}catch{}await wait(30);}
    throw new Error(`Web server did not start: ${output}`);
  }catch(e){child.kill();await close(backend);throw e;}
}
test('real web HTTP serves ESM and proxies same-origin API query, cookies and errors',async()=>{
  const server=await start();try{
    const html=await fetch(server.origin);assert.match(html.headers.get('content-type'),/text\/html/);assert.match(await html.text(),/type=["']module["']/);
    const js=await fetch(server.origin+'/dist/market.js');assert.equal(js.status,200);assert.match(js.headers.get('content-type'),/javascript/);
    const r=await fetch(server.origin+'/api/stocks?q='+encodeURIComponent('삼성 & A'),{headers:{cookie:'pilot_fixture=local'}});assert.equal(r.status,200);assert.equal((await r.json()).stocks[0].assetId,1);
    assert.equal(new URL(server.requests[0].url,'http://fixture').searchParams.get('q'),'삼성 & A');assert.equal(server.requests[0].cookie,'pilot_fixture=local');
    assert.equal((await fetch(server.origin+'/api/not-found')).status,404);
    const before=server.requests.length;
    for(const path of ['/not-api','/http://example.org/api/stocks','/api/../package.json','/%2e%2e/%2e%2e/spec/service.md','/api%2Fstocks']) {
      const response=await fetch(server.origin+path);assert.ok(response.status>=400,`${path} must not expose files or proxy arbitrary paths`);
    }
    assert.equal(server.requests.length,before);
  }finally{await server.stop();}
});

async function chromePage() {
  const chrome=process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';assert.ok(existsSync(chrome),'Chrome binary needed for actual DOM test');
  const profile=await mkdtemp(join(tmpdir(),'daynomy-webview-browser-'));
  const child=spawn(chrome,['--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
  let error='';child.stderr.on('data',x=>error+=x);
  try {
    let port;
    for(let n=0;n<100;n++){try{port=Number((await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{}if(child.exitCode!==null)throw new Error(`Chrome exited ${child.exitCode}: ${error}`);await wait(50);}
    assert.ok(port,`Chrome DevTools unavailable: ${error}`);
    const pages=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();const ws=new WebSocket(pages.find(x=>x.type==='page').webSocketDebuggerUrl);
    await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
    let sequence=0;const pending=new Map();ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.id){const p=pending.get(x.id);pending.delete(x.id);x.error?p.reject(new Error(JSON.stringify(x.error))):p.resolve(x.result);}});
    const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
    const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
    return {call,evaluate,stop:()=>{ws.close();child.kill();}};
  }catch(e){child.kill();throw e;}
}
test('actual Chromium DOM search → select → price → exact manual deletion, filters and lifecycle', {timeout:30000},async()=>{
  const server=await start();let browser;
  try{
    browser=await chromePage();await browser.call('Page.navigate',{url:server.origin});
    async function until(expression,message){for(let n=0;n<100;n++){if(await browser.evaluate(expression))return;await wait(30);}throw new Error(message);}
    await until(`document.querySelector('input[type="search"]') !== null`,'Accessible search input missing');
    assert.equal(await browser.evaluate(`(()=>{const e=document.querySelector('input[type="search"]');return Boolean(e.labels?.length || e.getAttribute('aria-label'));})()`),true,'search needs Korean accessible label');
    assert.equal(await browser.evaluate(`/로그인/.test(document.body.textContent)`),true,'login unavailable status must be visible');
    await browser.evaluate(`(()=>{const e=document.querySelector('input[type="search"]');e.value='삼성';e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await until(`Array.from(document.querySelectorAll('button')).some(e=>e.textContent.includes('삼성전자'))`,'Search results missing');
    assert.equal(await browser.evaluate(`window.__injected || 0`),0);assert.equal(await browser.evaluate(`document.querySelectorAll('img[src="x"]').length`),0,'response names must render as text, not HTML');
    const count=server.requests.length;
    await browser.evaluate(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent.trim()==='ETF').click()`);
    await until(`!Array.from(document.querySelectorAll('button')).some(e=>e.textContent.includes('삼성전자'))`,'ETF filter did not remove stock');
    assert.equal(server.requests.length,count,'filter must be local');
    await browser.evaluate(`Array.from(document.querySelectorAll('button')).find(e=>/전체/.test(e.textContent)).click()`);
    await browser.evaluate(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent.includes('삼성전자')).click()`);
    const input=`Array.from(document.querySelectorAll('input')).find(e=>e.type!=='search' && (Array.from(e.labels||[]).some(l=>/단가/.test(l.textContent)) || /단가/.test(e.getAttribute('aria-label')||'')))`;
    await until(`(()=>{const e=${input};return e?.value==='71000'})()`,'latest quote not shown in labeled unit-price input');
    assert.equal(await browser.evaluate(`document.body.textContent.includes('2026-10-27')`),true);
    await browser.evaluate(`(()=>{const e=${input};e.value='0001.2300000000000000001';e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    assert.equal(await browser.evaluate(`(${input}).value`),'0001.2300000000000000001');
    await browser.evaluate(`(()=>{const e=${input};e.value='';e.dispatchEvent(new Event('input',{bubbles:true}));window.dispatchEvent(new PageTransitionEvent('pagehide'));})()`);
    const suspended=server.requests.length;await wait(350);assert.equal(server.requests.length,suspended);
    await browser.evaluate(`window.dispatchEvent(new PageTransitionEvent('pageshow'));`);
    for(let n=0;n<50 && server.requests.length===suspended;n++) await wait(30);
    assert.ok(server.requests.length>suspended,'pageshow must re-query selected price');
    await wait(100);assert.equal(await browser.evaluate(`(${input}).value`),'');
    const nativeBefore=server.requests.length;
    await browser.evaluate(`window.dispatchEvent(new CustomEvent('daynomy:active',{detail:false}));window.dispatchEvent(new CustomEvent('daynomy:active',{detail:'true'}));`);
    await wait(100); assert.equal(server.requests.length,nativeBefore,'nonboolean native event must not activate');
    await browser.evaluate(`window.dispatchEvent(new CustomEvent('daynomy:active',{detail:true}));window.dispatchEvent(new CustomEvent('daynomy:active',{detail:true}));`);
    for(let n=0;n<50 && server.requests.length===nativeBefore;n++) await wait(30);
    assert.equal(server.requests.length,nativeBefore+1,'native resume fetches once');
    assert.equal(await browser.evaluate(`(${input}).value`),'');
    assert.equal(await browser.evaluate(`typeof window.Android === 'undefined' && typeof window.webkit?.messageHandlers === 'undefined'`),true);
  }finally{browser?.stop();await server.stop();}
});
