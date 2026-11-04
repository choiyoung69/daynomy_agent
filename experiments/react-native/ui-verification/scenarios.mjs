import {chromium} from '/Users/seoyeong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const out='/Users/seoyeong/develop/AI/daynomy_agent/experiments/react-native/ui-verification';
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page=await browser.newPage({viewport:{width:375,height:812},deviceScaleFactor:1});
page.setDefaultTimeout(15000);
const errors=[],consoleErrors=[],expectedHttpErrors=[],requests=[],checks=[];
const stock={assetId:910001,assetCode:'005930',name:'삼성전자',category:'STOCK',currency:'KRW',market:'KOSPI'};
page.on('pageerror',e=>errors.push(e.message));
page.on('console',e=>{if(e.type()==='error'){const text=e.text().slice(0,800);if(text.includes('401 (Unauthorized)'))expectedHttpErrors.push(text);else consoleErrors.push(text)}});
await page.route('**/api/**',async route=>{
 const u=new URL(route.request().url()),p=u.pathname,m=route.request().method(); requests.push({path:p,method:m,query:Object.fromEntries(u.searchParams)});
 let status=200,body={};
 if(m==='OPTIONS'){await route.fulfill({status:204,headers:{'access-control-allow-origin':'http://localhost:18139','access-control-allow-credentials':'true','access-control-allow-methods':'GET,POST,PATCH,DELETE,OPTIONS','access-control-allow-headers':'content-type,x-xsrf-token'}});return;}
 if(p==='/api/auth/csrf')body={headerName:'X-XSRF-TOKEN',token:'synthetic-only'};
 else if(p==='/api/users/me'||p==='/api/auth/refresh'){status=401;body={code:'UNAUTHORIZED',message:'로그인이 필요합니다.'};}
 else if(p==='/api/stocks')body={stocks:[stock]};
 else if(p==='/api/stocks/910001/price'){await new Promise(r=>setTimeout(r,1200));body={...stock,baseDate:'2026-10-27',closePrice:70000};}
 else if(p==='/api/portfolio/calculate')body={totalEvaluationAmount:140000,totalPurchaseAmount:142002,totalProfitLoss:-2002,totalReturnRate:-1.41,holdings:[{...stock,quantity:2,averagePurchasePrice:71001,evaluationAmount:140000}]};
 else if(p==='/api/news')body={items:[{id:501,title:'검증용 경제 뉴스',category:'ECONOMY',imageUrl:null,publishedAt:null}],page:1,size:20,totalPages:1,totalElements:1,hasNext:false};
 else if(p==='/api/news/501')body={id:501,title:'검증용 경제 뉴스',content:'독립 UI 검증을 위한 합성 뉴스 본문입니다.',category:'ECONOMY',publishedAt:null};
 else if(p.includes('/keywords'))body={keywords:['검증','경제']};
 else if(p.includes('/market-analysis'))body={summary:'합성 시장 분석'};
 else if(p==='/api/investment-calendar')body={events:[]};
 else if(p==='/api/people')body={items:[]};
 else {status=404;body={code:'NOT_FOUND',message:'합성 fixture 범위 밖 요청입니다.'};}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body),headers:{'access-control-allow-origin':'http://localhost:18139','access-control-allow-credentials':'true','access-control-allow-methods':'GET,POST,PATCH,DELETE,OPTIONS','access-control-allow-headers':'content-type,x-xsrf-token'}});
});
try {
 await page.goto('http://localhost:18139',{waitUntil:'networkidle',timeout:60000});
 await page.getByRole('button',{name:'+ 거래 기록',exact:true}).click();
 await page.getByLabel('종목 이름 또는 코드',{exact:true}).fill('삼성');
 await page.getByRole('button',{name:'종목 검색',exact:true}).click();
 await page.getByRole('button',{name:'삼성전자 · 005930',exact:true}).click();
 const price=page.getByLabel('단가 (KRW)',{exact:true});
 await price.fill('71000');
 await page.getByLabel('수량 (주)',{exact:true}).fill('2');
 await page.getByLabel('수수료',{exact:true}).fill('2');
 await page.waitForTimeout(1500);
 assert.equal(await price.inputValue(),'71000');checks.push({name:'manual-price-preserved-after-delayed-close',pass:true});
 await page.screenshot({path:out+'/02-trade-manual-375.png',fullPage:true});
 await page.getByRole('button',{name:'거래 저장',exact:true}).click();
 await page.locator('#root').getByText('삼성전자',{exact:true}).waitFor();checks.push({name:'guest-buy-visible',pass:true});await page.getByRole('button',{name:'거래 저장',exact:true}).waitFor({state:'hidden'});checks.push({name:'trade-modal-closed-after-save',pass:true});await page.locator('#root').getByText('2주 · KOSPI',{exact:true}).waitFor();checks.push({name:'holding-two-shares-visible-outside-modal',pass:true});await page.waitForTimeout(700);
 await page.screenshot({path:out+'/03-guest-holding-375.png',fullPage:true});
 await page.reload({waitUntil:'networkidle'});
 await page.locator('#root').getByText('삼성전자',{exact:true}).waitFor();checks.push({name:'guest-ledger-survives-browser-reload',pass:true});
 await page.getByRole('button',{name:'거래 내역',exact:true}).click();
 await page.getByText('삼성전자 · BUY',{exact:true}).waitFor();checks.push({name:'trade-history-tab',pass:true});
 await page.getByRole('tab',{name:'뉴스',exact:true}).click();
 await page.getByText('검증용 경제 뉴스',{exact:true}).waitFor();checks.push({name:'news-null-thumbnail-date-render',pass:true});
 await page.getByRole('button',{name:/검증용 경제 뉴스/}).click();
 await page.getByText('독립 UI 검증을 위한 합성 뉴스 본문입니다.',{exact:true}).waitFor();checks.push({name:'news-detail-navigation',pass:true});
 await page.getByRole('button',{name:'닫기',exact:true}).click();
 await page.getByRole('tab',{name:'탐색',exact:true}).click();
 await page.getByLabel('종목·뉴스·콘텐츠 검색',{exact:true}).fill('삼성');
 await page.getByRole('button',{name:'검색',exact:true}).click();
 await page.locator('#root').getByText('삼성전자',{exact:true}).waitFor();checks.push({name:'explore-stock-search',pass:true});
 await page.setViewportSize({width:812,height:375});await page.waitForTimeout(1000);
 await page.screenshot({path:out+'/04-explore-landscape.png',fullPage:true});
 await page.getByRole('tab',{name:'캘린더',exact:true}).click();
 await page.getByText('등록된 일정이 없어요',{exact:true}).waitFor();checks.push({name:'calendar-empty-state',pass:true});
 await page.getByRole('tab',{name:'더보기',exact:true}).click();
 await page.getByText('앱 연결 설정',{exact:true}).waitFor();checks.push({name:'more-settings-tab',pass:true});
 checks.push({name:'no-horizontal-document-overflow',pass:await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)});
} catch(e) {checks.push({name:'scenario-error',pass:false,error:e.message});await page.screenshot({path:out+'/failure.png',fullPage:true});}
await fs.writeFile(out+'/results.json',JSON.stringify({evidence:'Expo web synthetic HTTP route fixtures; NOT actual Rust integration or native OS execution',timestamp:new Date().toISOString(),checks,errors,consoleErrors,expectedHttpErrors,requests,body:await page.locator('body').innerText()},null,2));
console.log(JSON.stringify({checks,errors,consoleErrors},null,2));
await browser.close();
if(checks.some(c=>!c.pass)||errors.length)process.exitCode=1;
