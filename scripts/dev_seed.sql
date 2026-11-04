-- Synthetic public data only. Not current market data or real published news.
-- Repeated runs retain existing rows and edits; no members/auth bypasses.
BEGIN;
SELECT pg_advisory_xact_lock(831472902);
INSERT INTO assets(name,category,asset_code,market,listed,created_at,updated_at)
VALUES ('삼성전자 (로컬 샘플)','STOCK','005930','KOSPI',true,now(),now()),
       ('Apple (로컬 샘플)','STOCK','AAPL.US','NASDAQ',true,now(),now())
ON CONFLICT (category,asset_code) DO NOTHING;

INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at)
SELECT id,DATE '2026-11-03',CASE asset_code WHEN '005930' THEN 70000.00 ELSE 190.00 END,now(),now()
FROM assets WHERE category='STOCK' AND asset_code IN ('005930','AAPL.US')
ON CONFLICT (asset_id,base_date) DO NOTHING;

INSERT INTO news(title,content,category,status,published_at,image_source,sources,created_at,updated_at)
SELECT '로컬 샘플: Android와 Rust 연결 확인',
       '화면 연결을 확인하기 위한 합성 뉴스입니다. 실제 보도나 투자 정보가 아닙니다.' || E'\n\n' ||
       '종목에서 삼성전자 또는 Apple을 검색하면 2026-11-03 기준의 예시 종가를 볼 수 있습니다.',
       'STOCK','PUBLISHED',now(),
       '{"name":"","url":"","author":"","license":"","licenseUrl":"","type":"NONE"}'::jsonb,
       '[{"name":"로컬 합성 데이터","url":"https://example.invalid/local-sample"}]'::jsonb,now(),now()
WHERE NOT EXISTS (SELECT 1 FROM news WHERE title='로컬 샘플: Android와 Rust 연결 확인');

INSERT INTO usd_krw_rates(requested_date,base_date,rate,fetched_at)
VALUES ('2026-11-03','2026-11-03',1400.000000,now())
ON CONFLICT (requested_date) DO NOTHING;
COMMIT;
