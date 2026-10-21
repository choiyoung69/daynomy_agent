#!/usr/bin/env python3
"""Initialize an isolated local service database without running Java/Flyway."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from acceptance import Database, EnvironmentFailure

ROOT = Path(__file__).resolve().parents[1]


def migrations(app):
    manifest = json.loads((app / 'migrations/reference/manifest.json').read_text())
    result = []
    for record in manifest['migrations']:
        path = app / 'migrations/reference' / record['file']
        if path.name != record['file'] or not path.is_file():
            raise ValueError('Invalid bundled migration path')
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != record['sha256']:
            raise ValueError('Bundled migration checksum mismatch')
        result.append(('reference:' + str(record['version']), checksum,
                       path.read_text(), record['transactional']))
    for path in sorted((app / 'migrations').glob('*.sql')):
        if path.name.startswith('001_'):
            continue  # V25 already creates the identical feedback table.
        result.append(('rust:' + path.stem, hashlib.sha256(path.read_bytes()).hexdigest(),
                       path.read_text(), True))
    return result


def apply(database_url, app=ROOT / 'app'):
    db = Database(database_url)  # Requires loopback and a dedicated *_test database.
    env = db.env.copy()
    env['PGOPTIONS'] = '-c statement_timeout=60000 -c lock_timeout=10000'
    entries = migrations(app)
    sql = """SELECT pg_advisory_lock(831472901);
DO $$ BEGIN
IF to_regclass('public.rust_schema_history') IS NULL AND EXISTS
 (SELECT 1 FROM pg_tables WHERE schemaname='public') THEN
 RAISE EXCEPTION 'Refusing to initialize an existing schema without migration history';
END IF;
END $$;
CREATE TABLE IF NOT EXISTS rust_schema_history(
 version text PRIMARY KEY, checksum char(64) NOT NULL,
 installed_at timestamptz NOT NULL DEFAULT clock_timestamp());
"""
    for version, checksum, content, transactional in entries:
        # Identifiers/checksums come only from the bundled, validated manifest.
        if not all(c.isalnum() or c in ':_-' for c in version):
            raise ValueError('Invalid migration version')
        sql += ("\nSELECT EXISTS(SELECT 1 FROM rust_schema_history WHERE version='" + version + "') AS applied \\gset\n"
                "\\if :applied\nDO $$ BEGIN IF EXISTS(SELECT 1 FROM rust_schema_history WHERE version='" + version +
                "' AND checksum <> '" + checksum + "') THEN RAISE EXCEPTION 'Applied migration checksum mismatch'; END IF; END $$;\n\\else\n")
        if transactional:
            sql += 'BEGIN;\n'
        sql += content + "\nINSERT INTO rust_schema_history(version,checksum) VALUES('" + version + "','" + checksum + "');\n"
        if transactional:
            sql += 'COMMIT;\n'
        sql += '\\endif\n'
    sql += 'SELECT pg_advisory_unlock(831472901);\n'
    try:
        result = subprocess.run(['psql', '-X', '-w', '-v', 'ON_ERROR_STOP=1'],
                                input=sql, env=env, text=True, capture_output=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        raise EnvironmentFailure('Schema initialization unavailable/timed out') from None
    if result.returncode:
        raise EnvironmentFailure('Schema initialization failed; SQL/connection details withheld. '
                                 'A failed nontransactional index migration needs inspection before retry.')
    return {'status': 'passed', 'migrations': len(entries),
            'schema': 'original V1-V53 plus Rust OAuth/guest-session tables',
            'nontransactional': [version for version, _, _, transactional in entries if not transactional]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-env', default='DATABASE_URL')
    parser.add_argument('--app', type=Path, default=ROOT / 'app')
    args = parser.parse_args()
    postgres = '/opt/homebrew/opt/postgresql@18/bin'
    if not shutil.which('psql'):
        os.environ['PATH'] = postgres + ':' + os.environ.get('PATH', '')
    try:
        result = apply(os.environ.get(args.database_env, ''), args.app)
    except (EnvironmentFailure, ValueError, OSError, KeyError):
        print(json.dumps({'status': 'failed', 'reason': 'Local schema initialization failed; connection/SQL details withheld'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
