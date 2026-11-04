#!/usr/bin/env python3
"""Prepare an isolated instrumented Flutter app; never run Flutter or change product."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
PRODUCT = ROOT / 'clients/flutter'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    files = list((PRODUCT / 'lib').rglob('*.dart'))
    files += [PRODUCT / 'pubspec.yaml', PRODUCT / 'pubspec.lock']
    files += [p for p in (PRODUCT / 'ios').rglob('*') if p.is_file()
              and not any(part in {'ephemeral', 'Pods', '.symlinks', 'xcuserdata'}
                          for part in p.relative_to(PRODUCT).parts)
              and p.name not in {'Generated.xcconfig', 'flutter_export_environment.sh'}]
    return {str(p.relative_to(PRODUCT)): sha(p) for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.local'):
        parser.error('output must be a fresh repository .local path')
    output.mkdir(parents=True, exist_ok=False)
    before = sources()
    shadow = output / 'app'
    shutil.copytree(PRODUCT, shadow, symlinks=True,
                    ignore=shutil.ignore_patterns('build', '.dart_tool', '.gradle',
                                                 'ephemeral', 'Pods', '.symlinks',
                                                 'xcuserdata', '.git'))
    original = (shadow / 'pubspec.yaml').read_text()
    if original.count('dev_dependencies:\n') != 1:
        raise RuntimeError('Unexpected product pubspec shape; no implicit edits')
    instrumented = original.replace('dev_dependencies:\n',
        'dev_dependencies:\n  integration_test:\n    sdk: flutter\n'
        '  flutter_driver:\n    sdk: flutter\n', 1)
    (shadow / 'pubspec.yaml').write_text(instrumented)
    (shadow / 'integration_test').mkdir(exist_ok=True)
    (shadow / 'test_driver').mkdir(exist_ok=True)
    shutil.copyfile(HERE / 'live_guest_smoke_test.dart',
                    shadow / 'integration_test/live_guest_smoke_test.dart')
    shutil.copyfile(HERE / 'smoke_driver.dart', shadow / 'test_driver/smoke_driver.dart')
    after = sources()
    if after != before:
        raise RuntimeError('Product sources changed during preparation')
    for relative, digest in before.items():
        if relative not in {'pubspec.yaml', 'pubspec.lock'}:
            if sha(shadow / relative) != digest:
                raise RuntimeError('Shadow differs from product source: ' + relative)
    report = {
        'production_unchanged': before == after,
        'production_hashes': before,
        'shadow': str(shadow),
        'only_intentional_shadow_modifications': [
            'pubspec.yaml: SDK integration_test/flutter_driver dev dependencies',
            'integration_test/live_guest_smoke_test.dart: additional test target',
            'test_driver/smoke_driver.dart: screenshot/result collector',
        ],
        'harness_hashes': {name: sha(HERE / name) for name in
            ['live_guest_smoke_test.dart', 'smoke_driver.dart', 'prepare_shadow.py']},
        'execution': 'not performed by test author; verifier owns Flutter build/device',
        'scope_limit': 'instrumented production code; not release signing, real Google or AI',
    }
    (output / 'preparation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(shadow)


if __name__ == '__main__':
    main()
