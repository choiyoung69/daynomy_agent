#!/usr/bin/env python3
"""Run Flutter checks, preserving criteria/source hashes and actual command logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'clients/flutter'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def criteria():
    paths = list((APP / 'test').rglob('*.dart'))
    paths += list((APP / 'integration_test').rglob('*.dart'))
    paths += list((ROOT / 'spec/flutter').glob('*.md'))
    paths += list((ROOT / 'scripts').glob('flutter_*acceptance.py'))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def sources():
    paths = list((APP / 'lib').rglob('*.dart'))
    paths += [p for p in (ROOT / 'app/src').glob('*.rs')]
    paths += [p for p in (ROOT / 'app/migrations').glob('*.sql')]
    paths += [p for p in (APP / 'pubspec.yaml', APP / 'pubspec.lock') if p.exists()]
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def supplemental_criteria():
    return {str(p.relative_to(ROOT)): digest(p) for folder in ('review_test', 'verification_test')
            for p in sorted((APP / folder).rglob('*.dart'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['red', 'verify'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / '.local'):
        parser.error('output must be repository-local .local')
    out.mkdir(parents=True, exist_ok=False)
    frozen = criteria()
    supplemental = supplemental_criteria()
    if not frozen:
        parser.error('no test criteria to freeze')
    if args.phase == 'verify':
        if not args.baseline:
            parser.error('verify requires a red baseline')
        previous = json.loads(args.baseline.read_text())
        if previous.get('phase') != 'red' or previous.get('status') != 'expected_failure':
            parser.error('baseline must record an actual implementation-before failure')
        if frozen != previous['criteria_hashes']:
            parser.error('frozen criteria changed; record a justified new baseline instead')
    for relative in frozen | supplemental:
        destination = out / 'criteria' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    report = dict(phase=args.phase, started_at=datetime.now(timezone.utc).isoformat(),
                  status='running', criteria_hashes=frozen, source_hashes=sources(), commands=[])
    report['supplemental_criteria_hashes'] = supplemental

    def save():
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    save()
    commands = [('test', ['test', '--reporter', 'expanded'])]
    if supplemental:
        folders = [folder for folder in ('review_test', 'verification_test') if (APP / folder).is_dir()]
        commands = [('test', ['test', '--reporter', 'expanded', 'test', *folders])]
    if args.phase == 'verify':
        commands = [('analyze', ['analyze']), *commands, ('build-web', ['build', 'web', '--release'])]
    try:
        for name, tail in commands:
            started = time.monotonic()
            with (out / (name + '.log')).open('w') as log:
                result = subprocess.run(['bash', str(ROOT / 'scripts/flutter.sh'), *tail],
                                        cwd=APP, env=os.environ.copy(), stdout=log, stderr=log, timeout=600)
            report['commands'].append(dict(name=name, exit_code=result.returncode,
                                           seconds=time.monotonic() - started))
            save()
            if result.returncode:
                break
        current_supplemental = supplemental_criteria()
        stable = criteria() == frozen and current_supplemental == supplemental and sources() == report['source_hashes']
        failed = any(item['exit_code'] != 0 for item in report['commands'])
        report['criteria_and_sources_unchanged'] = stable
        report['status'] = ('expected_failure' if failed else 'unexpected_pass') if args.phase == 'red' else ('failed' if failed else 'passed')
        if not stable:
            report['status'] = 'inputs_changed'
    except (OSError, subprocess.TimeoutExpired) as failure:
        report.update(status='blocked', failure_type=type(failure).__name__)
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({k: report[k] for k in ('phase', 'status', 'commands')}))
    return 0 if report['status'] in ('passed', 'expected_failure') else 1


if __name__ == '__main__':
    sys.exit(main())
