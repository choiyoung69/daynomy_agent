import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../../../',import.meta.url));
async function listen(server){server.listen(0,'127.0.0.1');await once(server,'listening');return server.address().port;}
async function request(port,path){return new Promise((resolve,reject)=>{const req=http.request({host:'127.0.0.1',port,path,headers:{accept:'text/html'}},res=>{let body='';res.on('data',c=>body+=c);res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body}));});req.setTimeout(2000,()=>req.destroy(new Error('fixture timeout')));req.on('error',reject);req.end();});}
test('query separators preserve original navigation/API/OAuth without allowing path separators',{timeout:12000},async t=>{
  const dist=await mkdtemp(join(tmpdir(),'webview-query-regression-'));
  const html='<!doctype html><main>query regression fixture</main>';
  await writeFile(join(dist,'index.html'),html);
  const seen=[];
  const upstream=http.createServer((req,res)=>{seen.push(req.url);if(req.url.startsWith('/login/oauth2/')){res.writeHead(302,{location:'/login?result=fixture'});res.end();}else{res.writeHead(200,{'content-type':'application/json'});res.end('{"stocks":[]}');}});
  const upstreamPort=await listen(upstream);
  const reserve=http.createServer();const port=await listen(reserve);await new Promise(r=>reserve.close(r));
  const child=spawn(process.execPath,['clients/webview/scripts/serve-full.mjs','--port',String(port),'--api-origin',`http://127.0.0.1:${upstreamPort}`,'--dist',dist],{cwd:root,stdio:'ignore'});
  t.after(async()=>{child.kill();upstream.closeAllConnections();await new Promise(r=>upstream.close(r));await rm(dist,{recursive:true,force:true});});
  let ready=false;
  for(let n=0;n<100;n++){if(child.exitCode!==null)throw new Error('server exited before ready');try{await request(port,'/');ready=true;break;}catch{await new Promise(r=>setTimeout(r,20));}}
  assert.ok(ready,'server must listen');
  for(const path of ['/login?returnTo=%2Fmypage','/search?q=foo%2Fbar']){
    await t.test(`SPA query ${path}`,async()=>{const r=await request(port,path);assert.equal(r.status,200);assert.equal(r.body,html);});
  }
  for(const [path,status] of [['/api/stocks?q=foo%2Fbar',200],['/login/oauth2/code/google?scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email',302]]){
    await t.test(`proxy query ${path}`,async()=>{const r=await request(port,path);assert.equal(r.status,status);assert.equal(seen.at(-1),path,'raw query bytes must reach fixed upstream unchanged');if(status===302)assert.equal(r.headers.location,'/login?result=fixture');});
  }
  await t.test('encoded slash and backslash in pathname stay denied',async()=>{
    const count=seen.length;
    for(const path of ['/assets%2Fsecret.js?x=allowed','/assets%5Csecret.js?x=allowed','/api%2Fstocks?q=ok','/api/%2e%2e/secret','/api%5cstocks?q=ok']){const r=await request(port,path);assert.ok([400,403,404].includes(r.status));assert.notEqual(r.body,html);}
    assert.equal(seen.length,count,'hostile path must not reach upstream');
  });
  await t.test('CSP allows original local uploaded image blob preview',async()=>{
    const r=await request(port,'/admin/news/new');assert.equal(r.status,200);
    const directive=r.headers['content-security-policy']?.split(';').map(s=>s.trim()).find(s=>s.startsWith('img-src '));
    assert.ok(directive,'explicit image policy required');assert.ok(directive.split(/\s+/).includes('blob:'),'URL.createObjectURL upload preview requires blob: image source');
  });
});
