import test from 'node:test';
import assert from 'node:assert/strict';
import { access, mkdtemp, rm } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const android = 'clients/webview/android-full/app/src/main/java/com/daynomy/webview/NativeAuthSession.kt';
const swift = 'clients/webview/ios-full/DaynomyWebView/NativeAuthSession.swift';
const tests = 'clients/webview/full-tests/native-auth/';
function run(command, args, env = process.env) {
  const result = spawnSync(command, args, { cwd: root, env, encoding: 'utf8', timeout: 120000 });
  assert.equal(result.status, 0, `${command} failed: ${result.error ?? ''}\n${result.stdout}\n${result.stderr}`);
  return result.stdout;
}
test('Android native OAuth session executes frozen Kotlin cases', async t => {
  await access(resolve(root, android));
  const work = await mkdtemp(join(tmpdir(), 'webview-native-auth-kotlin-'));
  try {
    const javaHome = process.env.JAVA_HOME || run('/usr/libexec/java_home', []).trim();
    const env = { ...process.env, JAVA_HOME: javaHome };
    run(resolve(root, '.local/knowledge-sdks/kotlin/kotlinc/bin/kotlinc'), [android, tests + 'NativeAuthSessionTest.kt', '-include-runtime', '-d', join(work, 'tests.jar')], env);
    const output = run(join(javaHome, 'bin/java'), ['-jar', join(work, 'tests.jar')], env);
    assert.match(output, /NativeAuthSession Kotlin: \d+ assertions passed/);
    t.diagnostic(output.trim());
  } finally { await rm(work, { recursive: true, force: true }); }
});
test('iOS native OAuth session executes frozen host Swift cases', async t => {
  await access(resolve(root, swift));
  const work = await mkdtemp(join(tmpdir(), 'webview-native-auth-swift-'));
  try {
    run('swiftc', ['-module-cache-path', join(work, 'cache'), swift, tests + 'swift/main.swift', '-o', join(work, 'tests')]);
    const output = run(join(work, 'tests'), []);
    assert.match(output, /NativeAuthSession Swift: \d+ assertions passed/);
    t.diagnostic(output.trim());
  } finally { await rm(work, { recursive: true, force: true }); }
});
