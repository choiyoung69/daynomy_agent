#!/usr/bin/env python3
"""Explicit local import: selected real stocks/daily closes and official RSS metadata.

No API key, AI generation, scheduling, article-body scraping, or authentication bypass.
"""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from acceptance import Database
from dev_backend import ROOT, load_config

KR = ('005930', '000660', '035420', '035720', '005380', '000270', '051910', '006400', '068270', '105560')
US = ('AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'AMD', 'NFLX')
RSS = 'https://www.hankyung.com/feed/finance'


def parse_article_image(data, article_url):
    class Metadata(HTMLParser):
        image = None
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag.lower() == 'meta' and values.get('property', '').lower() == 'og:image':
                self.image = values.get('content')
    parser = Metadata()
    parser.feed(data.decode('utf-8', errors='replace'))
    if not parser.image:
        return None
    url = urlsplit(parser.image)
    if url.scheme != 'https' or url.hostname not in ('img.hankyung.com', 'hkimage.hankyung.com') or url.username or url.port:
        return None
    return {'image_url': parser.image, 'image_source': {'name': '한국경제', 'url': article_url,
            'author': '', 'license': '', 'licenseUrl': '', 'type': 'MANUAL'}}


def enrich_news_images(news, sources):
    failures = 0
    for row in news:
        try:
            body = fetch(row['url'])
            image = parse_article_image(body, row['url'])
            if image:
                row.update(image)
            sources.append({'kind': 'article-image', 'key': row['url'], 'url': row['url'],
                            'sha256': hashlib.sha256(body).hexdigest()})
        except Exception:
            failures += 1
        time.sleep(0.15)
    return failures


def backfill_news_images(config):
    db = Database(config['DATABASE_URL'])
    news = db.query("""SELECT coalesce(json_agg(json_build_object('title',n.title,'url',s->>'url',
        'published_at',n.published_at)),'[]'::json) FROM news n,
        LATERAL jsonb_array_elements(n.sources) s
        WHERE n.status='PUBLISHED' AND coalesce(n.image_url,'')=''
        AND s->>'name'='한국경제' AND s->>'url' LIKE 'https://www.hankyung.com/article/%'""")
    sources = []
    failures = enrich_news_images(news, sources)
    payload = {'assets': [], 'news': news, 'sources': sources, 'fetched_at': datetime.now(timezone.utc).isoformat()}
    persist(config, payload)
    report = {'processed': len(news), 'with_image': sum(bool(n.get('image_url')) for n in news), 'failed': failures,
              'missing_image': sum(not n.get('image_url') for n in news) - failures, 'sources': sources}
    out = ROOT / '.local/public-data'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'news-images.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'sources'}))
    return 1 if failures else 0


def positive(value):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError('Provider price must be finite and positive')
    return format(number, 'f')


def xml(data, encoding='utf-8'):
    text = data.decode(encoding)
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('XML entities/DTDs are not accepted')
    return ET.fromstring(text)


def parse_naver(data, code, before):
    chart = xml(data, 'euc-kr').find('.//chartdata')
    if chart is None or chart.get('symbol') != code or not chart.get('name'):
        raise ValueError('Invalid Korean chart identity')
    prices = []
    for item in chart.findall('item'):
        fields = item.get('data', '').split('|')
        if len(fields) != 6:
            raise ValueError('Invalid Korean daily bar')
        day = datetime.strptime(fields[0], '%Y%m%d').date()
        if day < before:
            prices.append({'date': day.isoformat(), 'close': positive(fields[4])})
    if not prices:
        raise ValueError('No completed Korean daily bars')
    return {'code': code, 'name': chart.get('name'), 'market': 'KOSPI', 'prices': prices}


def parse_yahoo(data, symbol, before):
    envelope = json.loads(data, parse_float=Decimal)['chart']
    if envelope.get('error') or not envelope.get('result'):
        raise ValueError('US chart provider error')
    result = envelope['result'][0]
    meta = result['meta']
    markets = {'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ', 'NYQ': 'NYSE', 'PCX': 'NYSE_ARCA'}
    if meta.get('symbol') != symbol or meta.get('currency') != 'USD' or meta.get('exchangeName') not in markets:
        raise ValueError('Invalid US chart identity/currency/market')
    stamps = result['timestamp']
    closes = result['indicators']['quote'][0]['close']
    if len(stamps) != len(closes):
        raise ValueError('US daily bar length mismatch')
    prices = []
    for stamp, close in zip(stamps, closes):
        day = datetime.fromtimestamp(stamp, ZoneInfo('America/New_York')).date()
        if close is not None and day < before:
            prices.append({'date': day.isoformat(), 'close': positive(close)})
    name = meta.get('longName') or meta.get('shortName')
    if not prices or not name:
        raise ValueError('No US stock name/completed daily bars')
    return {'code': symbol + '.US', 'name': name, 'market': markets[meta['exchangeName']], 'prices': prices}


def parse_rss(data):
    result = {}
    for item in xml(data).findall('./channel/item')[:50]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        parsed = urlsplit(link)
        if not title or len(title) > 255 or parsed.scheme != 'https' or parsed.hostname not in ('www.hankyung.com', 'hankyung.com') or parsed.username or parsed.port:
            raise ValueError('Invalid publisher headline/link')
        published = parsedate_to_datetime(item.findtext('pubDate') or '')
        if published.tzinfo is None:
            raise ValueError('RSS publication timezone is required')
        result[link] = {'title': title, 'url': link, 'published_at': published.astimezone(timezone.utc).isoformat()}
    if not result:
        raise ValueError('No RSS news items')
    return list(result.values())


def fetch(url):
    request = Request(url, headers={'User-Agent': 'DAYNOMY-local-development/1.0'})
    with urlopen(request, timeout=20) as response:
        data = response.read(2_000_001)
        if response.status != 200 or len(data) > 2_000_000:
            raise ValueError('Provider response too large/unsuccessful')
        return data


def sql_literal(value):
    if '\x00' in value:
        raise ValueError('NUL is not accepted')
    return "'" + value.replace("'", "''") + "'"


def persist(config, payload):
    # All provider I/O and parsing complete before one atomic DB transaction.
    db = Database(config['DATABASE_URL'])
    env = db.env.copy()
    env['PGOPTIONS'] = '-c statement_timeout=30000 -c lock_timeout=10000'
    sql = (ROOT / 'scripts/import_public_data.sql').read_text().replace(
        '__PAYLOAD__', sql_literal(json.dumps(payload, ensure_ascii=False)))
    result = subprocess.run(['psql', '-X', '-w', '-v', 'ON_ERROR_STOP=1', '-v', 'VERBOSITY=sqlstate'], input=sql,
                            text=True, capture_output=True, env=env, timeout=90)
    if result.returncode:
        state = re.search(r'ERROR:\s+([0-9A-Z]{5})\b', result.stderr)
        raise ValueError('Import transaction failed; SQLSTATE=' + (state[1] if state else 'unknown'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--news-images', action='store_true', help='Fill missing representative images for imported publisher news only')
    args = parser.parse_args()
    stage = 'local configuration'
    try:
        config = load_config()
        if args.news_images:
            stage = 'article image backfill'
            return backfill_news_images(config)
        now = datetime.now(timezone.utc)
        assets, sources = [], []
        for country, codes, endpoint, parse in (
            ('Asia/Seoul', KR, 'https://fchart.stock.naver.com/sise.nhn?symbol={}&timeframe=day&count=20&requestType=0', parse_naver),
            ('America/New_York', US, 'https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=1mo', parse_yahoo),
        ):
            for code in codes:
                stage = 'stock ' + code
                url = endpoint.format(code)
                body = fetch(url)
                asset = parse(body, code, now.astimezone(ZoneInfo(country)).date())
                assets.append(asset)
                sources.append({'kind': 'stock', 'key': asset['code'], 'url': url,
                                'sha256': hashlib.sha256(body).hexdigest()})
                print('Fetched real daily data: ' + asset['code'], flush=True)
                time.sleep(0.2)
        stage = 'publisher RSS'
        body = fetch(RSS)
        news = parse_rss(body)
        sources.append({'kind': 'rss', 'key': RSS, 'url': RSS, 'sha256': hashlib.sha256(body).hexdigest()})
        image_failures = enrich_news_images(news, sources)
        payload = {'assets': assets, 'news': news, 'sources': sources, 'fetched_at': now.isoformat()}
        out = ROOT / '.local/public-data'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'snapshot.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        stage = 'DB transaction'
        persist(config, payload)
        report = {'imported_at': now.isoformat(), 'stocks': len(assets), 'daily_prices': sum(len(a['prices']) for a in assets),
                  'news': len(news), 'news_images': sum(bool(n.get('image_url')) for n in news), 'image_failures': image_failures, 'sources': sources,
                  'latest_dates': {a['code']: max(p['date'] for p in a['prices']) for a in assets}}
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: report[k] for k in ('stocks', 'daily_prices', 'news', 'news_images', 'image_failures')}, ensure_ascii=False))
        return 1 if image_failures else 0
    except Exception as failure:
        # urllib errors can embed URLs; do not print exception text.
        detail = str(failure) if stage == 'DB transaction' and isinstance(failure, ValueError) else type(failure).__name__
        print('Public import failed at ' + stage + ' (' + detail + '); response bodies/credentials withheld.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
