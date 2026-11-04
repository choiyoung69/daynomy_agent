#!/usr/bin/env python3
"""Run the shared Rust API on the host with a persistent local Docker test DB."""
import argparse
import base64
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from urllib.parse import quote

from acceptance import Database, EnvironmentFailure
from service_migrate import apply

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'


def initialize(path=ENV_FILE):
    """Create private local credentials once; never replace an existing .env."""
    text = (ROOT / '.env.example').read_text()
    text = text.replace('CHANGE_ME', secrets.token_hex(24))
    text = text.replace('GENERATE_BASE64_SECRET', base64.b64encode(secrets.token_bytes(32)).decode())
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
    return True


def load_config(path=ENV_FILE):
    """Read literal KEY=value entries, without shell execution or interpolation."""
    config = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in config:
            raise ValueError(f'Invalid or duplicate .env setting on line {number}; values withheld')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Unclosed .env quote on line {number}')
            value = value[1:-1]
        config[key] = value
    required = ('POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'POSTGRES_PORT',
                'DATABASE_URL', 'PORT', 'JWT_SECRET', 'COOKIE_SECURE', 'JOB_SCHEDULER_ENABLED')
    if any(not config.get(key) for key in required):
        raise ValueError('Required local settings missing; compare .env.example')
    for key in ('POSTGRES_PORT', 'PORT'):
        if not config[key].isascii() or not config[key].isdigit() or not 1024 <= int(config[key]) <= 65535:
            raise ValueError(f'{key} must be a port in 1024..65535')
    if config['PORT'] == config['POSTGRES_PORT']:
        raise ValueError('HTTP and database ports must differ')
    if not re.fullmatch(r'[a-z][a-z0-9_]*_test', config['POSTGRES_DB']):
        raise ValueError('Use a dedicated local database ending in _test')
    expected = ('postgresql://' + quote(config['POSTGRES_USER'], safe='') + ':' +
                quote(config['POSTGRES_PASSWORD'], safe='') + '@127.0.0.1:' +
                config['POSTGRES_PORT'] + '/' + config['POSTGRES_DB'])
    if config['DATABASE_URL'] != expected or config['POSTGRES_PASSWORD'] == 'CHANGE_ME':
        raise ValueError('DATABASE_URL must match the local Docker settings; values withheld')
    try:
        valid_secret = len(base64.b64decode(config['JWT_SECRET'], validate=True)) >= 32
    except ValueError:
        valid_secret = False
    if not valid_secret:
        raise ValueError('JWT_SECRET requires at least 32 base64-encoded random bytes; use init')
    if config['JOB_SCHEDULER_ENABLED'] != 'false' or config['COOKIE_SECURE'] != 'false':
        raise ValueError('Local HTTP requires COOKIE_SECURE=false and JOB_SCHEDULER_ENABLED=false')
    return config


def compose(arguments, config):
    env = os.environ.copy()
    env.update(config)
    result = subprocess.run(['docker', 'compose', '--project-name', 'daynomy-local',
                             '--env-file', str(ENV_FILE),
                             '-f', str(ROOT / 'compose.yaml'), *arguments],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        raise EnvironmentFailure('Docker Compose failed; check Docker Desktop, image access, '
                                 'and the configured port. Output withheld to protect settings.')


def seed(config):
    db = Database(config['DATABASE_URL'])
    if db.query("SELECT to_json(to_regclass('public.local_public_import_sources') IS NOT NULL)::text"):
        raise EnvironmentFailure('Real public data already imported; omit --seed to preserve the real-data environment')
    env = db.env.copy()
    env['PGOPTIONS'] = '-c statement_timeout=10000 -c lock_timeout=10000'
    result = subprocess.run(['psql', '-X', '-w', '-v', 'ON_ERROR_STOP=1'],
                            input=(ROOT / 'scripts/dev_seed.sql').read_text(),
                            env=env, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise EnvironmentFailure('Local sample insertion failed; SQL/connection details withheld')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'prepare', 'start', 'stop'))
    parser.add_argument('--seed', action='store_true', help='Insert labeled synthetic display data once')
    args = parser.parse_args()
    if args.seed and args.command not in ('prepare', 'start'):
        parser.error('--seed requires prepare or start')
    try:
        created = initialize()
        if args.command == 'init':
            print('.env created (private local secrets).' if created else '.env exists; preserved.')
            return 0
        config = load_config()
        if not shutil.which('docker'):
            raise EnvironmentFailure('Docker Desktop with Compose is required')
        if args.command == 'stop':
            compose(['stop', 'db'], config)
            print('Docker DB stopped; volume and .env preserved.')
            return 0
        postgres = '/opt/homebrew/opt/postgresql@18/bin'
        if not shutil.which('psql'):
            os.environ['PATH'] = postgres + os.pathsep + os.environ.get('PATH', '')
        if not shutil.which('psql') or (args.command == 'start' and not shutil.which('cargo')):
            raise EnvironmentFailure('Install PostgreSQL client (psql) and Rust/Cargo first')
        print('Starting local Docker PostgreSQL...', flush=True)
        compose(['up', '-d', '--wait', '--wait-timeout', '60', 'db'], config)
        result = apply(config['DATABASE_URL'])
        print(f"Schema ready ({result['migrations']} migration entries; checksums verified).", flush=True)
        if args.seed:
            seed(config)
            print('Synthetic samples ready; example prices/FX are dated 2026-11-03.', flush=True)
        if args.command == 'prepare':
            return 0
        env = os.environ.copy()
        env.update(config)
        env.setdefault('CARGO_HOME', str(ROOT / '.local/cargo'))
        env.setdefault('CARGO_TARGET_DIR', str(ROOT / '.local/service-target'))
        print('Shared API: http://127.0.0.1:' + config['PORT'] +
              ' | Android emulator: http://10.0.2.2:' + config['PORT'] + '/', flush=True)
        print('Ctrl-C stops the API. DB data persists; stop DB with: python3 scripts/dev_backend.py stop', flush=True)
        return subprocess.call(['cargo', 'run', '--locked', '--manifest-path', str(ROOT / 'app/Cargo.toml')],
                               cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 130
    except (ValueError, EnvironmentFailure) as failure:
        # These errors are produced by the local validators with fixed messages.
        print('Local backend setup failed: ' + str(failure), file=sys.stderr)
        return 1
    except (OSError, subprocess.TimeoutExpired):
        print('Local backend setup failed: a required file/command is unavailable or timed out. '
              'Check Docker Desktop, psql, Cargo, and .env. Details withheld.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
