#!/usr/bin/env python3
"""Compare Spring integer binding to Rust over real HTTP, without assuming answers."""
import argparse
from datetime import datetime, time, timezone
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from acceptance import Client, EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal, fixture_sql


def cases():
    routes = ('/api/news/{id}', '/api/news/{id}/keywords',
              '/api/news/{id}/market-analysis', '/api/stocks/{id}/price',
              '/api/assets/{id}/contents')
    values = ('910001', '+910001', '0910001', hex(910001), '#' + hex(910001)[2:],
              '+0x1', '-0x1', ' 910 001 ', '９１０００１', '\u2003910001\u2003',
              '\u00a0910001', str(2**63-1), str(2**63), '--1')
    for route in routes:
        for value in values:
            yield route.format(id=quote(value, safe=''))
    for route in ('/api/news', '/api/contents', '/api/search/news?q=Harness',
                  '/api/search/contents?q=Harness'):
        for field in ('page', 'size'):
            for value in ('1', '+1', '0x1', '#1', '+0x1', ' 1 ', '１', '\u20031',
                          '\u00a01', '0', '-1', str(2**31), 'bad'):
                yield route + ('&' if '?' in route else '?') + urlencode({field: value})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--reference-url', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'contract': 'Observed Spring/Rust integer binding; all response fields and unchanged DB',
              'results': [], 'passed': 0, 'failed': 0}
    try:
        clients = [Client(validate_local_url(value)) for value in (args.reference_url, args.base_url)]
        db = TestDatabase(args.database)
        zone = ZoneInfo('Asia/Seoul')
        today = datetime.combine(datetime.now(zone).date(), time(12), zone).astimezone(timezone.utc)
        sql, _, _ = fixture_sql(today)
        db.seed(sql)
        before = db.snapshot()
        for path in cases():
            try:
                replies = []
                for client in clients:
                    status, headers, raw = client.send(path)
                    require('application/json' in headers.get('Content-Type', ''), 'Expected JSON response')
                    replies.append((status, json.loads(raw, parse_float=Decimal)))
                equal(replies[1][0], replies[0][0], 'HTTP.status')
                equal(replies[1][1], replies[0][1], 'response')
                report['results'].append({'case': path, 'passed': True})
            except (AssertionError, EnvironmentFailure, ValueError) as exc:
                report['results'].append({'case': path, 'passed': False, 'reason': str(exc)})
        equal(db.snapshot(), before, 'db.read-only')
    except (AssertionError, EnvironmentFailure, ValueError, OSError):
        report['results'].append({'case': 'environment-or-readonly', 'passed': False,
                                  'reason': 'Isolated fixture setup/read-only assertion failed'})
    report['passed'] = sum(row['passed'] for row in report['results'])
    report['failed'] = len(report['results']) - report['passed']
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('passed', 'failed')}))
    return int(report['failed'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
