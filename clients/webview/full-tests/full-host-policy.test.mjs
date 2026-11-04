import test from 'node:test';
import assert from 'node:assert/strict';
import { access, mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../../../',import.meta.url));
const android='clients/webview/android-full/app/src/main/java/com/daynomy/webview/';
const ios='clients/webview/ios-full/DaynomyWebView/';
function run(command,args,env=process.env){const r=spawnSync(command,args,{cwd:root,env,encoding:'utf8',timeout:120000});assert.equal(r.status,0,`${command} failed: ${r.error??''}\n${r.stdout}\n${r.stderr}`);return r.stdout;}
test('new full Android pure resource/image policy executes',async()=>{
  await access(resolve(root,android+'FullResourcePolicy.kt'));
  const work=await mkdtemp(join(tmpdir(),'webview-full-kotlin-'));
  try{const javaHome=process.env.JAVA_HOME||run('/usr/libexec/java_home',[]).trim();const env={...process.env,JAVA_HOME:javaHome};run(resolve(root,'.local/knowledge-sdks/kotlin/kotlinc/bin/kotlinc'),[android+'NavigationPolicy.kt',android+'FullResourcePolicy.kt','clients/webview/full-tests/FullResourcePolicyTest.kt','-include-runtime','-d',join(work,'policy.jar')],env);assert.match(run(join(javaHome,'bin/java'),['-jar',join(work,'policy.jar')],env),/assertions passed/);}finally{await rm(work,{recursive:true,force:true});}
});
test('new full iOS pure resource/image policy executes',async()=>{
  await access(resolve(root,ios+'FullResourcePolicy.swift'));
  const work=await mkdtemp(join(tmpdir(),'webview-full-swift-'));
  try{run('swiftc',['-module-cache-path',join(work,'cache'),ios+'NavigationPolicy.swift',ios+'FullResourcePolicy.swift','clients/webview/full-tests/full-resource-swift/main.swift','-o',join(work,'policy')]);assert.match(run(join(work,'policy'),[]),/assertions passed/);}finally{await rm(work,{recursive:true,force:true});}
});
async function sources(path,ext){const out=[];for(const item of await readdir(path,{withFileTypes:true})){if(item.isDirectory())out.push(...await sources(join(path,item.name),ext));else if(item.name.endsWith(ext))out.push(await readFile(join(path,item.name),'utf8'));}return out.join('\n').replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'');}
test('new full hosts add no camera permission or privileged JS bridge',async()=>{
  const manifest=await readFile(resolve(root,'clients/webview/android-full/app/src/main/AndroidManifest.xml'),'utf8');
  assert.doesNotMatch(manifest,/android\.permission\.CAMERA/);
  assert.doesNotMatch(await sources(resolve(root,android),'.kt'),/addJavascriptInterface\s*\(/);
  assert.doesNotMatch(await sources(resolve(root,ios),'.swift'),/WKScriptMessageHandler|addScriptMessageHandler/);
});
