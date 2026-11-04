import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
const out=resolve('experiments/webview/verification'); await mkdir(join(out,'screenshots'),{recursive:true});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const mode=process.argv[2]||'android';let child,ws;const events=[];let port=9225;
const adb=(...args)=>{const r=spawnSync('/Users/seoyeong/Library/Android/sdk/platform-tools/adb',['-s','emulator-5564',...args],{encoding:'utf8'});if(r.status!==0)throw new Error(r.stderr||r.stdout);return r.stdout;};
try {
 if(mode==='desktop'){
  const profile=await mkdtemp(join(tmpdir(),'daynomy-independent-chrome-'));child=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
  for(let n=0;n<200;n++){try{port=Number((await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break}catch{}await wait(100)}
 }
 const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();ws=new WebSocket(pages.find(x=>x.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true})});
 let id=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p?.reject(new Error(JSON.stringify(m.error))):p?.resolve(m.result)}else if(['Runtime.exceptionThrown','Log.entryAdded','Network.loadingFailed'].includes(m.method))events.push(m)};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const i=++id;pending.set(i,{resolve,reject});ws.send(JSON.stringify({id:i,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 const until=async(expression,label)=>{for(let n=0;n<100;n++){if(await evaluate(expression))return;await wait(100)}throw new Error(label)};
 const screenshot=async(name,full=false)=>{let params={format:'png',captureBeyondViewport:full};if(full){const {cssContentSize}=await call('Page.getLayoutMetrics');params.clip={x:0,y:0,width:cssContentSize.width,height:cssContentSize.height,scale:1}}const r=await call('Page.captureScreenshot',params);await writeFile(join(out,'screenshots','round02-'+mode+'-'+name+'.png'),Buffer.from(r.data,'base64'))};
 await call('Runtime.enable');await call('Log.enable');await call('Network.enable');await call('Page.enable');
 if(mode==='desktop')await call('Emulation.setDeviceMetricsOverride',{width:1365,height:1000,deviceScaleFactor:1,mobile:false});
 await call('Page.navigate',{url:mode==='desktop'?'http://127.0.0.1:18082/':'http://10.0.2.2:18082/'});await until(`document.querySelector('#stock-query')`,'initial input');await wait(300);
 const result={mode,initial:await evaluate(`({visibility:document.visibilityState,text:document.body.innerText,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,userAgent:navigator.userAgent})`),checks:[]};
 await screenshot('initial');
 const query=async q=>{await evaluate(`(()=>{const e=document.querySelector('#stock-query');e.value=${JSON.stringify(q)};e.dispatchEvent(new Event('input',{bubbles:true}))})()`);};
 await query('005930');await wait(1500);result.search=await evaluate(`({text:document.body.innerText,status:document.querySelector('#search-status').textContent,results:document.querySelectorAll('.stock-result').length})`);await screenshot('search');
 if(!result.search.results){result.events=events;await writeFile(join(out,mode+'-runtime.json'),JSON.stringify(result,null,2));throw new Error('No real API search results')}
 await evaluate(`document.querySelector('.stock-result').click()`);await until(`document.querySelector('#unit-price').value==='71000.125'`,'KR quote');result.checks.push('KR recent price and date');
 result.quote=await evaluate(`({value:document.querySelector('#unit-price').value,date:document.querySelector('#base-date').textContent})`);await screenshot('quote');await screenshot('quote-full',true);
 await evaluate(`(()=>{const e=document.querySelector('#unit-price');e.value='0001.2300000000000000001';e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await screenshot('manual');
 if(mode==='android'){
  adb('shell','input','keyevent','3');await wait(500);adb('shell','am','start','-n','com.daynomy.webview/.MainActivity');await wait(1200);
  result.resumeValue=await evaluate(`document.querySelector('#unit-price').value`);if(result.resumeValue!=='0001.2300000000000000001')throw new Error('resume lost draft');
  const rotation=adb('shell','settings','get','system','user_rotation').trim(),auto=adb('shell','settings','get','system','accelerometer_rotation').trim();
  try{adb('shell','settings','put','system','accelerometer_rotation','0');adb('shell','settings','put','system','user_rotation','1');await wait(1200);result.rotationValue=await evaluate(`document.querySelector('#unit-price').value`);await screenshot('landscape');if(result.rotationValue!=='0001.2300000000000000001')throw new Error('rotation lost draft')}
  finally{adb('shell','settings','put','system','user_rotation',rotation);adb('shell','settings','put','system','accelerometer_rotation',auto)}
  await wait(800);
  await evaluate(`document.querySelector('#unit-price').scrollIntoView({block:'center'})`);await wait(200);const point=await evaluate(`(()=>{const r=document.querySelector('#unit-price').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);await call('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});await call('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await wait(800);
  const cap=spawnSync('/Users/seoyeong/Library/Android/sdk/platform-tools/adb',['-s','emulator-5564','exec-out','screencap','-p']);if(cap.status!==0)throw new Error('device screenshot failed');await writeFile(join(out,'screenshots','round02-android-keyboard-device.png'),cap.stdout);result.keyboard=adb('shell','dumpsys','input_method').includes('mInputShown=true');adb('shell','input','keyevent','4');await wait(300);
 }
 await evaluate(`(()=>{const e=document.querySelector('#unit-price');e.value='';e.dispatchEvent(new Event('input',{bubbles:true}));window.dispatchEvent(new CustomEvent('daynomy:active',{detail:false}));window.dispatchEvent(new CustomEvent('daynomy:active',{detail:true}));})()`);await wait(800);result.deletedValue=await evaluate(`document.querySelector('#unit-price').value`);if(result.deletedValue!=='')throw new Error('manual deletion overwritten');
 await evaluate(`document.querySelector('[data-country="US"]').click()`);await query('AAPL');await until(`document.querySelector('.stock-result')`,'US search');await evaluate(`document.querySelector('.stock-result').click()`);await until(`document.querySelector('#unit-price').value==='193.4'`,'US quote');result.us=await evaluate(`({value:document.querySelector('#unit-price').value,currency:document.querySelector('#currency').textContent})`);await screenshot('us-quote');
 await evaluate(`document.querySelector('[data-country="KR"]').click()`);await query('NOPRICE');await until(`document.querySelector('.stock-result')`,'missing quote search');await evaluate(`document.querySelector('.stock-result').click()`);await until(`document.querySelector('#price-status').textContent.includes('직접 입력')`,'missing quote error');result.missingPrice=await evaluate(`({status:document.querySelector('#price-status').textContent,date:document.querySelector('#base-date').textContent,retry:!document.querySelector('#retry-price').hidden})`);await screenshot('missing-price');
 result.layout=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('button,input')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({name:e.textContent.trim()||e.id,height:e.getBoundingClientRect().height,width:e.getBoundingClientRect().width})),colors:[...document.querySelectorAll('p,label,input,button,h1,h2')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({name:e.textContent.slice(0,45),color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,fontSize:getComputedStyle(e).fontSize}))})`);
 if(mode==='desktop'){await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(500);await screenshot('mobile-error');await screenshot('mobile-full',true);result.mobileLayout=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})`)}
 result.events=events;result.status='passed';await writeFile(join(out,mode+'-runtime.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);await writeFile(join(out,mode+'-failure.json'),JSON.stringify({message:e.message,events},null,2));process.exitCode=1}
finally{ws?.close();child?.kill()}
