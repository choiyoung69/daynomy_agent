#!/usr/bin/env python3
"""Own a disposable Rust/PostgreSQL fixture for Flutter verification only."""
import argparse
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from admin_feedback_gate import _deadline_gate_lock
from agent_workflow import clean_env
from service_acceptance import fixture_sql
from service_migrate import apply

ROOT = Path(__file__).resolve().parents[1]
PG = Path('/opt/homebrew/opt/postgresql@18/bin')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18081)
    parser.add_argument('--verify-feedback', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / '.local'):
        parser.error('output must be repository-local .local')
    out.mkdir(parents=True, exist_ok=False)
    candidate = out / 'candidate'
    shutil.copytree(ROOT / 'app', candidate, ignore=shutil.ignore_patterns('target'))
    source = {str(p.relative_to(candidate)): digest(p) for p in candidate.rglob('*') if p.is_file()}
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    env = clean_env()
    env.update(CARGO_HOME=str(ROOT / '.local/cargo'), CARGO_TARGET_DIR=str(out / 'target'),
               CARGO_NET_OFFLINE='true')
    db = 'daynomy_flutter_' + uuid.uuid4().hex[:10] + '_test'
    dbargs = ['-h', '127.0.0.1', '-p', '55439', '-U', 'pilot']
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), status='preparing',
                  base_url=f'http://127.0.0.1:{args.port}', source_hashes=source,
                  database_name=db, commands=[], data='synthetic fixture only; no real accounts/providers')

    def save():
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def command(label, command_args, environment=None, input=None):
        started = time.monotonic()
        with (out / (label + '.log')).open('w') as log:
            result = subprocess.run(command_args, cwd=ROOT, env=environment or env, input=input,
                                    text=True, stdout=log, stderr=log, timeout=180)
        report['commands'].append(dict(name=label, exit_code=result.returncode, seconds=time.monotonic() - started))
        save()
        if result.returncode:
            raise RuntimeError(label + ' failed; details withheld')

    save()
    server = None
    created = owned_db = False
    try:
        command('rust-build', ['cargo', 'build', '--locked', '--offline', '--manifest-path', str(candidate / 'Cargo.toml')])
        binary = out / 'target/debug/daynomy-feedback'
        report['binary_sha256'] = digest(binary)
        save()
        with _deadline_gate_lock(time.monotonic() + 3600):
            try:
                owned_db = subprocess.run([str(PG / 'pg_ctl'), '-D', str(ROOT / '.local/pgdata'), 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
                command('local-db-start', ['bash', 'scripts/local-db.sh', 'start'])
                command('fixture-db-create', [str(PG / 'createdb'), *dbargs, db])
                created = True
                runtime = env.copy()
                runtime.update(DATABASE_URL=f'postgresql://pilot@127.0.0.1:55439/{db}', PORT=str(args.port),
                               JWT_SECRET=base64.b64encode(os.urandom(32)).decode(), JWT_ISSUER='daynomy',
                               COOKIE_SECURE='false', JOB_SCHEDULER_ENABLED='false',
                               APP_CORS_ALLOWED_ORIGIN='http://127.0.0.1:18300', APP_TIMEZONE='Asia/Seoul')
                previous_path = os.environ.get('PATH', '')
                os.environ['PATH'] = str(PG) + ':' + previous_path
                try:
                    report['migrations'] = apply(runtime['DATABASE_URL'], candidate)
                finally:
                    os.environ['PATH'] = previous_path
                today = datetime.now(ZoneInfo('Asia/Seoul')).replace(hour=12, minute=0, second=0, microsecond=0)
                sql, _, _ = fixture_sql(today)
                sql += "INSERT INTO investment_events(id,event_type,title,announced_at,previous_value,actual_value,value_unit,source_name,source_url,source_key,created_at,updated_at) VALUES(960001,'US_CPI','검증용 CPI 일정',date_trunc('month',now())+interval '15 days 5 hours',3,2.5,'%','Synthetic fixture','https://fixture.invalid/calendar','flutter-fixture-cpi',now(),now());\n"
                command('synthetic-seed', [str(PG / 'psql'), '-X', '-w', '-v', 'ON_ERROR_STOP=1', *dbargs, '-d', db], input=sql)
                with (out / 'server.log').open('w') as log:
                    server = subprocess.Popen([str(binary)], cwd=ROOT, env=runtime, stdout=log, stderr=log)
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Rust fixture server exited')
                    try:
                        with urllib.request.urlopen(report['base_url'] + '/api/stocks?q=Harness', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Rust fixture readiness timeout')
                if args.verify_feedback:
                    regression = runtime.copy()
                    regression.update(PILOT_BASE_URL=report['base_url'],
                                      PILOT_TEST_DB_URL=runtime['DATABASE_URL'],
                                      CARGO_TARGET_DIR=str(ROOT / '.local/flutter-feedback-target'))
                    command('feedback-verify', [sys.executable, 'scripts/check.py', 'verify'], regression)
                    report['feedback_verified'] = True
                report.update(status='serving', server_started_at=datetime.now(timezone.utc).isoformat())
                save()
                print('Flutter Rust/DB fixture ready at ' + report['base_url'], flush=True)
                while not stopped.wait(.25) and not (out / 'stop').exists():
                    if server.poll() is not None:
                        raise RuntimeError('Rust fixture server exited')
                report['status'] = 'stopped'
            finally:
                if server:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
                if created:
                    command('fixture-db-drop', [str(PG / 'dropdb'), '--force', *dbargs, db])
                if owned_db:
                    command('local-db-stop', ['bash', 'scripts/local-db.sh', 'stop'])
        if any(digest(candidate / path) != value for path, value in source.items()) or digest(binary) != report['binary_sha256']:
            raise RuntimeError('Frozen fixture source/binary changed')
    except Exception as failure:
        report.update(status='failed', failure_type=type(failure).__name__)
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
