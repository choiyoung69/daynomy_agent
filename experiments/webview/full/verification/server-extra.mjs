import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,writeFile,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {once} from 'node:events';
const listen=async s=>{s.listen(0,'127.0.0.1');await once(s,'listening');return s.address().port};
const get=(p,path)=>new Promise((resolve,reject)=>{http.get({hostname:'127.0.0.1',port:p,path},r=>{let b='';r.on('data',c=>b+=c);r.on('end',()=>resolve({status:r.statusCode,body:b}));}).on('error',reject)});
test('independent symlink containment and client cancellation',{timeout:15000},async t=>{
 const scratch=await mkdtemp(join(tmpdir(),'daynomy-full-extra-')); const dist=join(scratch,'dist');await mkdir(dist);await mkdir(join(dist,'assets'));await mkdir(join(dist,'src'));await writeFile(join(dist,'index.html'),'fixture');await writeFile(join(scratch,'outside.txt'),'OUTSIDE');await writeFile(join(dist,'src/private.ts'),'PRIVATE');await symlink(join(scratch,'outside.txt'),join(dist,'assets/outside.txt'));await symlink(join(dist,'src/private.ts'),join(dist,'assets/inside.txt'));
 let aborted=false,seen=false;
 const upstream=http.createServer((req,res)=>{seen=true;req.on('aborted',()=>{aborted=true});res.on('close',()=>{aborted=true});});const up=await listen(upstream);
 const temp=http.createServer();const port=await listen(temp);await new Promise(r=>temp.close(r));
 const child=spawn(process.execPath,[resolve('clients/webview/scripts/serve-full.mjs'),'--port',String(port),'--api-origin',`http://127.0.0.1:${up}`,'--dist',dist],{stdio:'ignore'});
 t.after(async()=>{child.kill();upstream.closeAllConnections();await new Promise(r=>upstream.close(r));await rm(scratch,{recursive:true,force:true})});
 for(let i=0;i<100;i++){try{await get(port,'/');break}catch{await new Promise(r=>setTimeout(r,30))}}
 for(const path of ['/assets/outside.txt','/assets/inside.txt']) {const result=await get(port,path);assert.equal(result.status,404);assert.ok(!/OUTSIDE|PRIVATE/.test(result.body))}
 const req=http.request({hostname:'127.0.0.1',port,path:'/api/long',method:'POST',headers:{'content-length':'99999'}});req.on('error',()=>{});req.write('synthetic');
 for(let i=0;i<100&&!seen;i++)await new Promise(r=>setTimeout(r,20)); assert.ok(seen);req.destroy();
 for(let i=0;i<100&&!aborted;i++)await new Promise(r=>setTimeout(r,20));assert.ok(aborted,'client abort should close upstream');
});
