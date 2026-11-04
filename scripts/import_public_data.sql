-- Local development DB only; fetch and validate all sources before this transaction.
BEGIN;
SET LOCAL standard_conforming_strings = on;
SELECT pg_advisory_xact_lock(831472902);
CREATE TEMP TABLE public_import_payload ON COMMIT DROP AS SELECT __PAYLOAD__::jsonb AS value;

-- Remove only the known synthetic seed values while keeping stable asset IDs.
DELETE FROM stock_daily_prices p USING assets a
WHERE p.asset_id=a.id AND a.name IN ('삼성전자 (로컬 샘플)','Apple (로컬 샘플)')
AND p.created_at=a.created_at AND p.base_date='2026-11-03'
AND p.close_price=CASE a.asset_code WHEN '005930' THEN 70000 WHEN 'AAPL.US' THEN 190 ELSE -1 END;
DELETE FROM usd_krw_rates f USING news n
WHERE f.requested_date='2026-11-03' AND f.rate=1400 AND f.fetched_at=n.created_at
AND n.title='로컬 샘플: Android와 Rust 연결 확인'
AND n.sources @> '[{"url":"https://example.invalid/local-sample"}]'::jsonb;
DELETE FROM news WHERE title='로컬 샘플: Android와 Rust 연결 확인'
AND sources @> '[{"url":"https://example.invalid/local-sample"}]'::jsonb;

INSERT INTO assets(name,category,asset_code,market,listed,created_at,updated_at)
SELECT a->>'name','STOCK',a->>'code',a->>'market',true,now(),now()
FROM public_import_payload, jsonb_array_elements(value->'assets') a
ON CONFLICT(category,asset_code) DO UPDATE SET name=EXCLUDED.name,market=EXCLUDED.market,listed=true,updated_at=now()
WHERE (assets.name,assets.market,assets.listed) IS DISTINCT FROM (EXCLUDED.name,EXCLUDED.market,true);

INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at)
SELECT asset.id,(p->>'date')::date,(p->>'close')::numeric,now(),now()
FROM public_import_payload, jsonb_array_elements(value->'assets') a
JOIN assets asset ON asset.asset_code=a->>'code' AND asset.category='STOCK',
jsonb_array_elements(a->'prices') p
ON CONFLICT(asset_id,base_date) DO UPDATE SET close_price=EXCLUDED.close_price,updated_at=now()
WHERE stock_daily_prices.close_price<>EXCLUDED.close_price;

INSERT INTO news(title,content,category,status,published_at,image_url,image_source,sources,created_at,updated_at)
SELECT n->>'title','한국경제 공식 RSS에서 제공한 기사 정보입니다.' || E'\n\n' ||
'기사 전문은 아래 한국경제 원문 링크에서 확인하세요.',
'STOCK','PUBLISHED',(n->>'published_at')::timestamptz,n->>'image_url',
coalesce(n->'image_source','{"name":"","url":"","type":"NONE"}'::jsonb),
jsonb_build_array(jsonb_build_object('name','한국경제','url',n->>'url')),now(),now()
FROM public_import_payload, jsonb_array_elements(value->'news') n
WHERE NOT EXISTS (SELECT 1 FROM news existing WHERE existing.sources @>
jsonb_build_array(jsonb_build_object('url',n->>'url')));

UPDATE news existing SET image_url=n->>'image_url',image_source=n->'image_source',updated_at=now()
FROM public_import_payload,jsonb_array_elements(value->'news') n
WHERE nullif(n->>'image_url','') IS NOT NULL AND coalesce(existing.image_url,'')=''
AND existing.sources @> jsonb_build_array(jsonb_build_object('url',n->>'url'));

CREATE TABLE IF NOT EXISTS local_public_import_sources(
 kind text NOT NULL,external_key text NOT NULL,source_url text NOT NULL,
 source_sha256 char(64) NOT NULL,fetched_at timestamptz NOT NULL,
 PRIMARY KEY(kind,external_key));
INSERT INTO local_public_import_sources(kind,external_key,source_url,source_sha256,fetched_at)
SELECT s->>'kind',s->>'key',s->>'url',s->>'sha256',(public_import_payload.value->>'fetched_at')::timestamptz
FROM public_import_payload,jsonb_array_elements(value->'sources') s
ON CONFLICT(kind,external_key) DO UPDATE SET source_url=EXCLUDED.source_url,
source_sha256=EXCLUDED.source_sha256,fetched_at=EXCLUDED.fetched_at;
COMMIT;
