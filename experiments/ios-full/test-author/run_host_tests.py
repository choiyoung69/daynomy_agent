#!/usr/bin/env python3
"""Run canonical tests without broken CLT Swift Testing runtime. Does not alter tests."""
import pathlib, re, subprocess, tempfile, time, json, sys
root = pathlib.Path(__file__).resolve().parents[3]
start = time.monotonic()
with tempfile.TemporaryDirectory(prefix='ios-author-harness-') as directory:
    temp = pathlib.Path(directory)
    sources = list((root/'clients/ios/Sources/DaynomyCore').glob('*.swift'))
    invocations = []
    for path in sorted((root/'clients/ios/Tests/DaynomyCoreTests').glob('*.swift')):
        text = path.read_text()
        suite = re.search(r'(?:@MainActor )?struct (\w+Tests)', text).group(1)
        for block in re.finditer(r'struct (\w+Tests).*?(?=struct \w+Tests|\Z)', text, re.S):
            invocations += [(block.group(1), name) for name in re.findall(r'@Test func (\w+)\(', block.group(0))]
        text = text.replace('import Testing\n', '').replace('@testable import DaynomyCore\n', '')
        text = text.replace('@Test ', '').replace('#expect', 'expect').replace('#require', 'require').replace('Issue.record', 'record')
        text = re.sub(r'(?<!@MainActor )struct (\w+Tests)', r'@MainActor struct \1', text)
        output = temp/path.name; output.write_text(text); sources.append(output)
    if not invocations: raise RuntimeError('no test functions discovered')
    support = temp/'Harness.swift'
    support.write_text('''import Foundation
@MainActor var failures = 0
@MainActor func record(_ message: String, file: StaticString = #filePath, line: UInt = #line) { failures += 1; print("FAIL \\(file):\\(line) \\(message)") }
@MainActor func expect(_ value: Bool, file: StaticString = #filePath, line: UInt = #line) { if !value { record("expectation false", file:file,line:line) } }
@MainActor func require<T>(_ value:T?) throws -> T { guard let value else { throw MarketError.invalidResponse }; return value }
@MainActor func expect<T>(throws expected: MarketError, _ operation: () async throws -> T, file: StaticString = #filePath, line: UInt = #line) async { do { _ = try await operation(); record("expected error \\(expected)",file:file,line:line) } catch { if (error as? MarketError) != expected { record("expected \\(expected), got \\(error)",file:file,line:line) } } }
@main struct Runner { @MainActor static func main() async {
''' + '\n'.join(f'do {{ try await {suite}().{name}(); print("RAN {suite}.{name}") }} catch {{ record("{name}: \\(error)") }}' for suite,name in invocations) + f'\nprint("HOST TESTS {len(invocations)}; FAILURES \\(failures)"); exit(failures == 0 ? 0 : 1)\n}}}}\n')
    sources.append(support)
    command = ['swiftc','-swift-version','6','-parse-as-library','-module-cache-path','/tmp/ios-author-direct-cache', *map(str,sources),'-o',str(temp/'tests')]
    result = subprocess.run(command, cwd=root)
    if result.returncode == 0: result = subprocess.run([str(temp/'tests')],cwd=root)
    print(json.dumps({'exit_code':result.returncode,'elapsed_seconds':round(time.monotonic()-start,3),'canonical_test_count':len(invocations)}))
    sys.exit(result.returncode)
