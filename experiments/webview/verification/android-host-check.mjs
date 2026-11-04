import {spawnSync} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
const adb=(...args)=>{const r=spawnSync('/Users/seoyeong/Library/Android/sdk/platform-tools/adb',['-s','emulator-5564',...args],{encoding:'utf8'});if(r.status)throw new Error(r.stderr||r.stdout);return r.stdout};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const pages=await(await fetch('http://127.0.0.1:9225/json/list')).json();const ws=new WebSocket(pages[0].webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));let id=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result)}};
const call=(method,params={})=>new Promise((resolve,reject)=>{const i=++id;pending.set(i,{resolve,reject});ws.send(JSON.stringify({id:i,method,params}))});const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value};const result={checks:[]};
try {
 const base=await evaluate('location.href');
 for(const target of ['javascript:window.__policyBypass=1','data:text/html,blocked','file:///sdcard/Download/example.html','http://10.0.2.2:18083/','http://10.0.2.2.evil.invalid:18082/','http://user@10.0.2.2:18082/']){
  await evaluate(`location.assign(${JSON.stringify(target)})`);await wait(300);const url=await evaluate('location.href');if(url!==base)throw new Error('blocked URL navigated '+target);result.checks.push({target,blocked:true});
 }
 result.javascriptExecuted=await evaluate('window.__policyBypass===1');
 await evaluate(`document.cookie='daynomy_fixture_cookie=synthetic; SameSite=Lax; path=/'`);adb('shell','input','keyevent','3');await wait(300);adb('shell','am','start','-n','com.daynomy.webview/.MainActivity');await wait(600);result.cookieRetained=await evaluate(`document.cookie.includes('daynomy_fixture_cookie=synthetic')`);await evaluate(`document.cookie='daynomy_fixture_cookie=; Max-Age=0; path=/'`);
 await evaluate(`location.assign('/?verification-history=1')`);await wait(600);result.internal=await evaluate('location.search');adb('shell','input','keyevent','4');await wait(600);result.afterBack=await evaluate('location.search');if(result.internal!=='?verification-history=1'||result.afterBack!=='')throw new Error('native back history mismatch');
 await evaluate(`(()=>{const a=document.createElement('a');a.href='https://example.invalid/webview-verification';a.textContent='검증 외부 링크';a.id='verification-link';document.body.append(a);a.click()})()`);await wait(900);result.externalForeground=adb('shell','dumpsys','activity','activities').split('\n').filter(x=>x.includes('topResumedActivity'));adb('shell','am','start','-n','com.daynomy.webview/.MainActivity');await wait(600);result.externalStayedInWebview=await evaluate(`location.origin==='http://10.0.2.2:18082'`);await evaluate(`document.querySelector('#verification-link')?.remove()`);
 result.status='passed';console.log(JSON.stringify(result,null,2));await writeFile('experiments/webview/verification/round02-android-host.json',JSON.stringify(result,null,2));
}finally{ws.close()}
