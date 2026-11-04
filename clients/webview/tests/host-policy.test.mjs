import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root=resolve(fileURLToPath(new URL('../../..',import.meta.url)));
const work=mkdtempSync(join(tmpdir(),'daynomy-webview-policy-'));
function run(command,args,env=process.env) {
  const result=spawnSync(command,args,{cwd:root,env,encoding:'utf8',timeout:120000});
  assert.equal(result.status,0,`${command} failed: ${result.error||''}\n${result.stdout}\n${result.stderr}`);
  return result.stdout;
}
test('actual Kotlin policy executes shared trust/port/user-gesture cases',()=>{
  const source='clients/webview/android/app/src/main/java/com/daynomy/webview/NavigationPolicy.kt';
  assert.ok(existsSync(resolve(root,source)),`Missing implementation ${source}`);
  const sdk=resolve(root,'.local/knowledge-sdks');
  const jdkCandidates=[join(sdk,'jdk','Contents','Home'),join(sdk,'jdk'),...readdirSync(sdk).filter(x=>/jdk|java/.test(x)).map(x=>join(sdk,x,'Contents','Home'))];
  const javaHome=process.env.JAVA_HOME || jdkCandidates.find(x=>existsSync(join(x,'bin','java')));
  const env={...process.env,...(javaHome?{JAVA_HOME:javaHome}:{})};
  run(resolve(root,'.local/knowledge-sdks/kotlin/kotlinc/bin/kotlinc'),[source,'clients/webview/tests/NavigationPolicyTest.kt','-include-runtime','-d',join(work,'policy.jar')],env);
  const output=run(javaHome?join(javaHome,'bin/java'):'java',['-jar',join(work,'policy.jar')],env);
  assert.match(output,/assertions passed/);
});
test('actual Swift policy executes shared trust/port/user-gesture cases',()=>{
  const source='clients/webview/ios/DaynomyWebView/NavigationPolicy.swift';
  assert.ok(existsSync(resolve(root,source)),`Missing implementation ${source}`);
  run('swiftc',['-module-cache-path',join(work,'swift-cache'),source,'clients/webview/tests/main.swift','-o',join(work,'swift-policy')]);
  assert.match(run(join(work,'swift-policy'),[]),/assertions passed/);
});
