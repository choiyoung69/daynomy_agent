import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {ServiceClient, endpoint, decodeStocks, decodePrice, decodeNewsPage} from '../../../clients/react-native/src/core.ts';
const base='http://127.0.0.1:18129';
const fixture=new URL('./rust-fixture-04/',import.meta.url);
const cases=[];
const cookies=new Map();
const traffic=[];
const transport=async(input,init={})=>{
  const url=new URL(String(input));
  const headers=new Headers(init.headers);
  const selected=[...cookies.values()].filter(c=>url.pathname.startsWith(c.path));
  if(selected.length)headers.set('cookie',selected.map(c=>`${c.name}=${c.value}`).join('; '));
  const response=await fetch(input,{...init,headers});
  traffic.push({path:url.pathname,method:init.method??'GET',status:response.status});
  for(const value of response.headers.getSetCookie()){
    const [pair,...attrs]=value.split(';'); const index=pair.indexOf('=');
    const name=pair.slice(0,index),cookieValue=pair.slice(index+1);
    const path=attrs.find(a=>/^\s*path=/i.test(a))?.trim().slice(5)??'/';
    if(attrs.some(a=>/^\s*max-age=0$/i.test(a)))cookies.delete(name);
    else cookies.set(name,{name,value:cookieValue,path});
  }
  return response;
};
const client=new ServiceClient(base,transport);
async function run(name,operation){try{await operation();cases.push({name,pass:true});}catch(error){cases.push({name,pass:false,error:error instanceof Error?error.message:'unknown'});}}
async function call(name,options={}){const route=endpoint(name,options.id);return client.request(route.path,{method:route.method,csrf:route.csrf,body:options.body,query:options.query});}
await run('actual Rust KR stock search',async()=>{const values=decodeStocks(await client.request('/api/stocks',{query:{q:'삼성',country:'KR'}}));assert.equal(values.length,1);assert.equal(values[0].assetId,910001);});
await run('actual Rust US stock search',async()=>{const values=decodeStocks(await client.request('/api/stocks',{query:{q:'AAPL',country:'US'}}));assert.equal(values[0].assetId,910002);});
await run('actual Rust latest close price and reference date',async()=>{const value=decodePrice(await client.request('/api/stocks/910001/price'));assert.equal(value.closePrice,71000.125);assert.equal(value.baseDate,'2026-10-23');});
await run('actual Rust missing saved price surfaces 404',async()=>{await assert.rejects(client.request('/api/stocks/910003/price'),error=>error.status===404);});
await run('actual Rust public news null metadata decoder',async()=>{const value=decodeNewsPage(await call('news',{query:{page:'1',size:'10'}}));assert.equal(value.items.length,3);assert.ok(value.items.every(x=>x.imageUrl===null));});
await run('actual Rust unpublished news not exposed',async()=>{await assert.rejects(client.request('/api/news/920004'),error=>error.status===404);});
await run('actual Rust public feedback CSRF and 204',async()=>{const value=await client.request('/api/feedback',{method:'POST',csrf:true,body:{content:'React Native independent synthetic verification',pagePath:'/react-native/verification'}});assert.equal(value,null);});
await run('actual Rust CSRF invalid body remains 400',async()=>{await assert.rejects(client.request('/api/feedback',{method:'POST',csrf:true,body:{content:12}}),error=>error.status===400);});
await run('actual Rust public portfolio calculate',async()=>{const value=await call('calculate',{body:{holdings:[{assetId:910001,quantity:2,averagePurchasePrice:70000}]}});assert.equal(value.holdings[0].assetId,910001);assert.equal(value.totalPurchaseAmount,140000);});
await run('actual Rust synthetic PKCE exchange installs server cookies in host-only jar',async()=>{
 await fs.writeFile(new URL('issue-login',fixture),'');
 let material;
 for(let i=0;i<30;i++){try{material=JSON.parse(await fs.readFile(new URL('login-env.json',fixture),'utf8'));break;}catch{await new Promise(r=>setTimeout(r,100));}}
 assert.ok(material);
 const value=await client.request('/api/auth/mobile/exchange',{method:'POST',body:{code:material.ANDROID30_LOGIN_CODE,codeVerifier:material.ANDROID30_LOGIN_VERIFIER},retryUnauthorized:false});
 assert.equal(value,null);assert.ok(cookies.has('access_token'));assert.ok(cookies.has('refresh_token'));
});
await run('actual Rust authenticated member lookup',async()=>{const value=await call('profile');assert.equal(value.id,930001);assert.equal(value.role,'USER');});
await run('actual Rust member transaction create then portfolio readback',async()=>{
 const value=await call('createTrade',{body:{assetId:910001,type:'BUY',tradeDate:'2026-10-28',quantity:2,unitPrice:70000,fee:2,tax:0}});
 assert.ok(value);
 const saved=await call('portfolio');assert.equal(saved.holdings[0].quantity,2);
});
await run('actual Rust authenticated nickname patch readback',async()=>{await client.request('/api/users/me',{method:'PATCH',csrf:true,body:{nickname:'rn_verified'}});const user=await call('profile');assert.equal(user.nickname,'rn_verified');});
await run('actual Rust member cannot access admin feedback',async()=>{await assert.rejects(client.request('/api/admin/feedbacks'),error=>error.status===403);});
await run('actual Rust logout invalidates member lookup',async()=>{await call('logout');await assert.rejects(call('profile'),error=>error.status===401);});
const report={checkedAt:new Date().toISOString(),baseURL:base,boundary:'Real Rust plus disposable PostgreSQL synthetic fixture. Node-only cookie adapter; not RN OS cookie/device verification.',cases,traffic,passed:cases.filter(c=>c.pass).length,failed:cases.filter(c=>!c.pass).length};
await fs.writeFile(new URL('./live-http-result.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,failed:report.failed,cases},null,2));
process.exitCode=report.failed?1:0;
