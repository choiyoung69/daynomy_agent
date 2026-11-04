import {chromium} from '../../../../clients/webview/fullweb/node_modules/playwright/index.mjs';
import {writeFile,mkdir} from 'node:fs/promises';
const base=process.env.WEBVIEW_FULL_ORIGIN||'http://127.0.0.1:18082';const out=new URL('./screenshots/',import.meta.url);await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const report={browser:browser.version(),base,routes:[],requests:[],pageErrors:[]};
try{for(const [label,viewport] of [['mobile',{width:390,height:844}],['desktop',{width:1440,height:1000}]]){
const ctx=await browser.newContext({viewport});await ctx.addInitScript(()=>localStorage.setItem('daynomy:service-started:v1','1'));const page=await ctx.newPage();page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('response',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))report.requests.push({path:new URL(r.url()).pathname,status:r.status()})});
for(const path of ['/','/news','/news/1','/search','/people','/stocks/1','/investment-calendar','/login','/mypage','/admin/news']){await page.goto(base+path);await page.waitForTimeout(850);const key=path==='/'?'portfolio':path.slice(1).replaceAll('/','-');await page.screenshot({path:new URL(`${label}-${key}.png`,out).pathname,fullPage:true});report.routes.push({viewport:label,path,url:page.url(),headings:await page.locator('h1,h2').allTextContents(),text:(await page.locator('body').innerText()).slice(0,4500),overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)});}
await ctx.close();}
}finally{await browser.close();await writeFile(new URL('./browser-inspect.json',import.meta.url),JSON.stringify(report,null,2));}
console.log(JSON.stringify({routes:report.routes.length,pageErrors:report.pageErrors,requests:report.requests.length}));
