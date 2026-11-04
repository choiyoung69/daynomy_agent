import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, writeFile, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
const root = fileURLToPath(new URL('../../../', import.meta.url));
const serverPath = resolve(root, 'clients/webview/scripts/serve-full.mjs');
const routes = JSON.parse(await (await import('node:fs/promises')).readFile(new URL('./route-contract.json', import.meta.url), 'utf8'));
const listen = async server => { server.listen(0, '127.0.0.1'); await once(server, 'listening'); return server.address().port; };
const freePort = async () => { const s = http.createServer(); const p = await listen(s); await new Promise(r => s.close(r)); return p; };
function raw(port, path, method = 'GET', headers = {}, body) {
  return new Promise((resolveResult, reject) => {
    const req = http.request({ host: '127.0.0.1', port, path, method, headers }, res => {
      const chunks = []; res.on('data', c => chunks.push(c)); res.on('end', () => resolveResult({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() }));
    }); req.on('error', reject); req.setTimeout(3000, () => req.destroy(new Error('request timed out'))); req.end(body);
  });
}
async function start(port, upstream, dist) {
  const child = spawn(process.execPath, [serverPath, '--port', String(port), '--api-origin', upstream, '--dist', dist], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = ''; child.stdout.on('data', c => { output += c; }); child.stderr.on('data', c => { output += c; });
  for (let n = 0; n < 100; n++) {
    if (child.exitCode !== null) throw new Error('serve-full exited before listening');
    try { await raw(port, '/'); return { child, output: () => output }; } catch { await new Promise(r => setTimeout(r, 25)); }
  }
  child.kill(); throw new Error('serve-full did not listen');
}
test('full WebView HTTP contract against independent fixture', { timeout: 25000 }, async t => {
  await access(serverPath); // RED must be an absent implementation, never a skipped assertion.
  const dist = await mkdtemp(join(tmpdir(), 'daynomy-full-test-'));
  const html = '<!doctype html><div id="root">independent-spa-fixture</div>';
  await mkdir(join(dist, 'assets')); await mkdir(join(dist, 'src')); await mkdir(join(dist, '.git'));
  for (const [p, value] of Object.entries({ 'index.html': html, 'assets/app.js': 'globalThis.fixture=true;', 'assets/app.css': 'body{margin:0}', 'assets/icon.svg': '<svg/>', 'robots.txt': 'User-agent: *', '.env': 'DENY_PRIVATE_FIXTURE', '.git/config': 'DENY_PRIVATE_FIXTURE', 'src/private.ts': 'DENY_PRIVATE_FIXTURE' })) await writeFile(join(dist,p),value);
  const seen = [];
  const upstream = http.createServer(async (req,res) => {
    const chunks=[]; for await(const c of req) chunks.push(c);
    seen.push({method:req.method,path:req.url,headers:req.headers,body:Buffer.concat(chunks).toString()});
    if(req.url.startsWith('/oauth2/') || req.url.startsWith('/login/oauth2/')) { res.writeHead(302,{location:'/login?result=fixture','set-cookie':['one=fixture; HttpOnly; Path=/','two=fixture; SameSite=Lax; Path=/']}); res.end(); return; }
    const code=Number(new URL(req.url,'http://fixture.invalid').searchParams.get('status'))||200;
    res.writeHead(code,{'content-type':'application/json','set-cookie':['one=fixture; HttpOnly; Path=/','two=fixture; SameSite=Lax; Path=/']}); res.end(code===204?undefined:JSON.stringify({status:code}));
  });
  const upstreamPort=await listen(upstream), port=await freePort();
  let running;
  t.after(async()=>{running?.child.kill(); upstream.closeAllConnections(); await new Promise(r=>upstream.close(r)); await rm(dist,{recursive:true,force:true});});
  running=await start(port,`http://127.0.0.1:${upstreamPort}`,dist);
  await t.test('known routes GET and HEAD return SPA only for HTML navigation',async()=>{
    for(const path of routes.serverSpaExamples){
      const r=await raw(port,path,'GET',{accept:'text/html'}); assert.equal(r.status,200,path); assert.equal(r.body,html,path); assert.match(r.headers['content-type'],/text\/html/); assert.equal(r.headers['cache-control'],'no-store'); assert.equal(r.headers['x-content-type-options'],'nosniff');
      const h=await raw(port,path,'HEAD',{accept:'text/html'}); assert.equal(h.status,200,path); assert.equal(h.body,'');
    }
    assert.equal((await raw(port,'/news','GET',{accept:'application/json'})).status,404);
    assert.equal((await raw(port,'/news','POST')).status,404);
  });
  await t.test('static MIME and missing paths never return SPA',async()=>{
    for(const [path,mime] of [['/assets/app.js',/javascript/],['/assets/app.css',/text\/css/],['/assets/icon.svg',/image\/svg\+xml/],['/robots.txt',/text\/plain/]]){const r=await raw(port,path);assert.equal(r.status,200);assert.match(r.headers['content-type'],mime);assert.equal(r.headers['x-content-type-options'],'nosniff');assert.equal(r.headers['cache-control'],'no-store');}
    for(const path of ['/assets/missing.js','/news/missing.js','/unknown-route','/api-does-not-exist']){const r=await raw(port,path,'GET',{accept:'text/html'});assert.equal(r.status,404,path);assert.notEqual(r.body,html);}
  });
  await t.test('dangerous raw request paths are denied and never reach upstream',async()=>{
    const count=seen.length;
    for(const path of ['/../index.html','/%2e%2e/index.html','/assets%2fapp.js','/assets%5capp.js','/assets\\app.js','/%00','/%ZZ','/.env','/.git/config','/src/private.ts','/api/%2e%2e/.env','http://example.invalid/api/test','//example.invalid/api/test']){const r=await raw(port,path);assert.ok([400,403,404].includes(r.status),path);assert.ok(!r.body.includes('DENY_PRIVATE_FIXTURE'),path);assert.notEqual(r.body,html,path);}
    assert.equal(seen.length,count);
  });
  await t.test('real mutating JSON requests preserve bytes CSRF cookies method and query',async()=>{
    const body=JSON.stringify({fixture:'private-body-marker',amount:13});
    for(const method of ['POST','PUT','PATCH','DELETE']){const r=await raw(port,'/api/fixture?query=a%20b',method,{'content-type':'application/json','content-length':Buffer.byteLength(body),'x-csrf-token':'private-csrf-marker',cookie:'session=private-cookie-marker',origin:'http://127.0.0.1:18082'},body);assert.equal(r.status,200);const got=seen.at(-1);assert.equal(got.method,method);assert.equal(got.path,'/api/fixture?query=a%20b');assert.equal(got.body,body);assert.equal(got.headers['x-csrf-token'],'private-csrf-marker');assert.equal(got.headers.cookie,'session=private-cookie-marker');assert.equal(got.headers['content-type'],'application/json');assert.equal(got.headers.origin,'http://127.0.0.1:18082');}
    for(const method of ['GET','OPTIONS']){assert.equal((await raw(port,'/api/fixture',method)).status,200);assert.equal(seen.at(-1).method,method);}
  });
  await t.test('upstream statuses body and separate Set-Cookie survive',async()=>{
    for(const code of [204,400,401,403,404,500]){const r=await raw(port,`/api/fixture?status=${code}`);assert.equal(r.status,code);assert.equal(r.body,code===204?'':JSON.stringify({status:code}));assert.deepEqual(r.headers['set-cookie'],['one=fixture; HttpOnly; Path=/','two=fixture; SameSite=Lax; Path=/']);}
  });
  await t.test('OAuth redirect is relayed without follow and without dropping cookies',async()=>{
    for(const path of ['/oauth2/authorization/google','/login/oauth2/code/google?code=synthetic']){const r=await raw(port,path);assert.equal(r.status,302);assert.equal(r.headers.location,'/login?result=fixture');assert.equal(r.headers['set-cookie'].length,2);assert.equal(seen.at(-1).path,path);}
  });
  await t.test('server logs exclude synthetic body CSRF and cookie values',()=>{
    for(const value of ['private-body-marker','private-csrf-marker','private-cookie-marker'])assert.ok(!running.output().includes(value),'sensitive fixture leaked');
  });
  await t.test('upstream unavailable is 502',async()=>{
    upstream.closeAllConnections(); await new Promise(r=>upstream.close(r)); const r=await raw(port,'/api/fixture');assert.equal(r.status,502);assert.notEqual(r.body,html);
  });
});
test('nonloopback or credentialed upstream configuration is rejected', {timeout:15000},async()=>{
  await access(serverPath);
  for(const origin of ['http://example.invalid:18081','http://0.0.0.0:18081','http://127.0.0.1.evil.invalid:18081','http://user:password@127.0.0.1:18081','http://127.0.0.1:18081/path','http://127.0.0.1:18081?upstream=evil']){
    const child=spawn(process.execPath,[serverPath,'--port',String(await freePort()),'--api-origin',origin],{stdio:'ignore'});
    const result=await Promise.race([once(child,'exit').then(([code])=>code),new Promise(r=>setTimeout(()=>r('still running'),1000))]); child.kill(); assert.ok(Number.isInteger(result)&&result!==0,`invalid upstream accepted: ${new URL(origin).hostname}`);
  }
});
