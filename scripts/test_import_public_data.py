"""Synthetic parser tests; no network or DB."""
from datetime import date
import json
import unittest

from import_public_data import parse_naver, parse_yahoo, parse_rss, sql_literal, parse_article_image


class PublicDataParsingTest(unittest.TestCase):
    def test_article_image_keeps_publisher_attribution(self):
        result = parse_article_image(b'<meta content="https://img.hankyung.com/photo/real.jpg?a=1&amp;b=2" property="og:image">', 'https://www.hankyung.com/article/123')
        self.assertEqual('https://img.hankyung.com/photo/real.jpg?a=1&b=2', result['image_url'])
        self.assertEqual('MANUAL', result['image_source']['type'])
        self.assertEqual('https://www.hankyung.com/article/123', result['image_source']['url'])

    def test_article_image_rejects_insecure_or_unrelated_hosts(self):
        for url in ('http://img.hankyung.com/a.jpg', 'https://evil.example/a.jpg',
                    'https://img.hankyung.com.evil.example/a.jpg', 'https://user@img.hankyung.com/a.jpg'):
            with self.subTest(url=url):
                self.assertIsNone(parse_article_image(('<meta property="og:image" content="'+url+'">').encode(), 'https://www.hankyung.com/article/123'))
        self.assertIsNone(parse_article_image(b'<title>No photo</title>', 'https://www.hankyung.com/article/123'))

    def test_korean_encoding_and_completed_days(self):
        data = '''<?xml version="1.0" encoding="EUC-KR"?><protocol><chartdata symbol="005930" name="삼성전자">
        <item data="20261103|1|2|1|222000|100"/><item data="20261104|1|2|1|218500|100"/>
        </chartdata></protocol>'''.encode('euc-kr')
        asset = parse_naver(data, '005930', date(2026, 11, 4))
        self.assertEqual('삼성전자', asset['name'])
        self.assertEqual([{'date': '2026-11-03', 'close': '222000'}], asset['prices'])

    def yahoo(self, close=123.4567):
        return json.dumps({'chart': {'error': None, 'result': [{
            'meta': {'symbol': 'AAPL', 'longName': 'Apple Inc.', 'currency': 'USD', 'exchangeName': 'NMS'},
            'timestamp': [1793716200], 'indicators': {'quote': [{'close': [close]}]}
        }]}}).encode()

    def test_us_decimal_and_market(self):
        asset = parse_yahoo(self.yahoo(), 'AAPL', date(2026, 11, 4))
        self.assertEqual('AAPL.US', asset['code'])
        self.assertEqual('NASDAQ', asset['market'])
        self.assertEqual('123.4567', asset['prices'][0]['close'])
        self.assertEqual('2026-11-03', asset['prices'][0]['date'])

    def test_provider_errors_invalid_prices_and_wrong_symbol_fail(self):
        for data in (b'{"chart":{"error":{"code":"missing"},"result":null}}',
                     self.yahoo(-1), self.yahoo().replace(b'AAPL', b'MSFT')):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_yahoo(data, 'AAPL', date(2026, 11, 4))

    def test_rss_date_publisher_and_url_deduplication(self):
        item = '<item><title>기업 실적 발표</title><link>https://www.hankyung.com/article/123</link><pubDate>Wed, 04 Nov 2026 09:00:00 +0900</pubDate></item>'
        data = ('<rss><channel>' + item * 2 + '</channel></rss>').encode()
        rows = parse_rss(data)
        self.assertEqual(1, len(rows))
        self.assertEqual('2026-11-04T00:00:00+00:00', rows[0]['published_at'])
        for replacement in ('https://evil.example/article/123', 'javascript:alert(1)'):
            with self.subTest(url=replacement), self.assertRaises(ValueError):
                parse_rss(data.replace(b'https://www.hankyung.com/article/123', replacement.encode()))
        with self.assertRaises(ValueError):
            parse_rss(data.replace(b'Wed, 04 Nov 2026 09:00:00 +0900', b'unknown'))

    def test_empty_and_entity_documents_fail(self):
        for data in (b'<rss><channel/></rss>', b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_rss(data)

    def test_sql_headline_escaping(self):
        self.assertEqual("'기업''s \\ report'", sql_literal("기업's \\ report"))
        with self.assertRaises(ValueError):
            sql_literal('bad\x00data')


if __name__ == '__main__':
    unittest.main()
