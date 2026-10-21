//! Public news, search, asset content and people queries.
//! SQL follows the original Java repositories and DTOs; all user values are parameters.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query, rows};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use tokio_postgres::{Client, types::ToSql};

pub async fn handle(
    method: &str,
    path: &str,
    raw_query: &str,
    _body: &[u8],
    db: &Client,
) -> Option<Outcome> {
    if method != "GET" {
        return None;
    }
    let parts: Vec<&str> = path.trim_matches('/').split('/').collect();
    let route = match parts.as_slice() {
        ["api", "news"] => 0,
        ["api", "news", "today"] => 1,
        ["api", "news", _] => 2,
        ["api", "news", _, "keywords"] => 3,
        ["api", "news", _, "market-analysis"] => 4,
        ["api", "search", "news"] => 5,
        ["api", "search", "contents"] => 6,
        ["api", "contents"] => 7,
        ["api", "assets", _, "contents"] => 8,
        ["api", "people"] => 9,
        _ => return None,
    };
    Some(dispatch(route, &parts, raw_query, db).await)
}

async fn dispatch(route: u8, parts: &[&str], raw: &str, db: &Client) -> Outcome {
    // Unknown query parameters are ignored, as in the original controllers.
    let q = query(raw)?;
    let result = match route {
        0 | 1 => {
            let (page, size) = if route == 1 {
                (1, 9)
            } else {
                pagination(&q, 15, true)?
            };
            let category = if route == 1 { None } else { category(&q)? };
            let today = route == 1;
            let offset = (page - 1) * size;
            let dto = news_item("n");
            let sql = format!(
                r#"WITH matched AS (
                SELECT * FROM news WHERE status='PUBLISHED'
                  AND ($1::text IS NULL OR category=$1)
                  AND (NOT $2::boolean OR (published_at >= current_date::timestamptz AND published_at < (current_date + 1)::timestamptz))
            ), selected AS (SELECT {dto} AS item FROM matched n ORDER BY published_at DESC,id DESC LIMIT $3 OFFSET $4)
            SELECT jsonb_build_object('items',coalesce((SELECT jsonb_agg(item) FROM selected),'[]'::jsonb),
              'page',$5::bigint,'size',$3::bigint,'totalElements',count(*),'totalPages',(count(*)+$3-1)/$3,
              'hasNext',count(*)>$4+$3)::text FROM matched"#
            );
            one(db, &sql, &[&category, &today, &size, &offset, &page]).await?
        }
        2..=4 => {
            let field = if route == 2 { "id" } else { "newsId" };
            let id = parse_id(parts[2], field)?;
            if route == 4 {
                let result = rows(db, "SELECT jsonb_build_object('risk',m.risk,'watchPoint',m.watch_point)::text FROM news_market_analysis m JOIN news n ON n.id=m.news_id WHERE n.id=$1 AND n.status='PUBLISHED' AND m.risk IS NOT NULL AND m.watch_point IS NOT NULL AND m.risk ~ '[^[:space:]]' AND m.watch_point ~ '[^[:space:]]'", &[&id]).await?;
                return result.into_iter().next().map(|v| (200, v)).ok_or_else(|| {
                    fault(
                        404,
                        "MARKET_ANALYSIS_NOT_FOUND",
                        "해당 뉴스의 시장 분석을 찾을 수 없습니다.",
                    )
                });
            }
            if route == 3 {
                if rows(
                    db,
                    "SELECT to_json(id)::text FROM news WHERE id=$1 AND status='PUBLISHED'",
                    &[&id],
                )
                .await?
                .is_empty()
                {
                    return Err(news_missing());
                }
                let keywords = rows(db,"SELECT jsonb_build_object('category',category,'keyword',keyword,'points',jsonb_build_array(point1,point2,point3),'definition',point1,'context',point2,'watchPoint',point3)::text FROM news_keyword WHERE news_id=$1 ORDER BY id ASC",&[&id]).await?;
                json!({"keywords": keywords})
            } else {
                let sql = format!(
                    "SELECT {} || jsonb_build_object('content',n.content,'imageSource',jsonb_build_object('name',coalesce(n.image_source->>'name',''),'url',coalesce(n.image_source->>'url',''),'author',coalesce(n.image_source->>'author',''),'license',coalesce(n.image_source->>'license',''),'licenseUrl',coalesce(n.image_source->>'licenseUrl',''),'type',coalesce(n.image_source->>'type','NONE')),'sources',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',s->'name','url',s->'url')),'[]'::jsonb) FROM jsonb_array_elements(n.sources) s)) AS item FROM news n WHERE n.id=$1 AND n.status='PUBLISHED'",
                    news_item("n")
                );
                // rows expects exactly one text column, not PostgreSQL jsonb's binary wire representation.
                let sql = format!("SELECT item::text FROM ({sql}) detail");
                rows(db, &sql, &[&id])
                    .await?
                    .into_iter()
                    .next()
                    .ok_or_else(news_missing)?
            }
        }
        5 => news_search(db, &q).await?,
        6 => content_search(db, &q).await?,
        7 => {
            let (page, size) = pagination(&q, 12, false)?;
            let offset = (page - 1) * size;
            let dto = content_item("c");
            let sql = format!(
                r#"WITH matched AS (SELECT * FROM stock_related_contents WHERE news_id IS NULL AND source_type IN ('YOUTUBE','THREADS','X')),
                selected AS (SELECT {dto} item FROM matched c LEFT JOIN news n ON n.id=c.news_id ORDER BY c.published_date DESC,c.created_at DESC,c.id DESC LIMIT $1 OFFSET $2)
                SELECT jsonb_build_object('items',coalesce((SELECT jsonb_agg(item) FROM selected),'[]'::jsonb),'page',$3::bigint,'size',$1::bigint,
                'totalElements',count(*),'totalPages',(count(*)+$1-1)/$1,'hasNext',count(*)>$2+$1)::text FROM matched"#
            );
            one(db, &sql, &[&size, &offset, &page]).await?
        }
        8 => {
            let id = parse_id(parts[2], "assetId")?;
            if id <= 0 {
                return Err(invalid("assetId", "0보다 커야 합니다"));
            }
            let dto = content_item("c");
            let sql = format!(
                "SELECT jsonb_build_object('assetId',a.id,'assetCode',a.asset_code,'assetName',a.name,'contents',coalesce((SELECT jsonb_agg(z.item) FROM (SELECT {dto} AS item FROM stock_related_contents c LEFT JOIN news n ON n.id=c.news_id WHERE c.asset_id=a.id AND (c.news_id IS NULL OR n.status='PUBLISHED') ORDER BY c.created_at DESC,c.id DESC) z),'[]'::jsonb))::text FROM assets a WHERE a.id=$1"
            );
            rows(db, &sql, &[&id])
                .await?
                .into_iter()
                .next()
                .ok_or_else(|| fault(404, "ASSET_NOT_FOUND", "자산을 찾을 수 없습니다."))?
        }
        9 => {
            let created = utc("p.created_at");
            let post_created = utc("x.created_at");
            let published = utc("x.published_at");
            let sql = format!(
                r#"SELECT jsonb_build_object('id',p.id,'name',p.name,'xProfileUrl',p.x_profile_url,'threadsProfileUrl',p.threads_profile_url,
               'youtubeProfileUrl',p.youtube_profile_url,'profileImageUrl',p.profile_image_url,'createdAt',{created},
               'posts',coalesce((SELECT jsonb_agg(post) FROM (SELECT jsonb_build_object('id',x.id,'sourceType',x.source_type,'title',x.title,'url',x.url,'publishedAt',{published},'createdAt',{post_created}) post
               FROM featured_person_posts x WHERE x.person_id=p.id AND x.status='APPROVED' ORDER BY x.published_at DESC NULLS LAST,x.created_at DESC,x.id DESC) ordered),'[]'::jsonb))::text
               FROM featured_people p ORDER BY p.created_at ASC,p.id ASC"#
            );
            json!({"people":rows(db,&sql,&[]).await?})
        }
        _ => return Err(internal()),
    };
    Ok((200, result))
}

fn parse_id(raw: &str, field: &str) -> Result<i64, ApiFault> {
    crate::api::path_integer(raw).ok_or_else(|| invalid(field, "타입이 올바르지 않습니다."))
}
fn pagination(
    q: &BTreeMap<String, String>,
    default_size: i64,
    named: bool,
) -> Result<(i64, i64), ApiFault> {
    let number = |key: &str, default: i64| -> Result<i64, ApiFault> {
        match q.get(key).filter(|v| !v.is_empty()) {
            None => Ok(default),
            Some(raw) => crate::java_binding::integer(raw)
                .and_then(|number| i32::try_from(number).ok())
                .map(i64::from)
                .ok_or_else(|| invalid(key, "타입이 올바르지 않습니다.")),
        }
    };
    let page = number("page", 1)?;
    let size = number("size", default_size)?;
    if page < 1 {
        return Err(invalid(
            "page",
            if named {
                "페이지 번호는 1 이상이어야 합니다."
            } else {
                "1 이상이어야 합니다"
            },
        ));
    }
    if size < 1 {
        return Err(invalid(
            "size",
            if named {
                "페이지 크기는 1 이상이어야 합니다."
            } else {
                "1 이상이어야 합니다"
            },
        ));
    }
    if size > 100 {
        return Err(invalid(
            "size",
            if named {
                "페이지 크기는 100 이하여야 합니다."
            } else {
                "100 이하여야 합니다."
            },
        ));
    }
    Ok((page, size))
}
fn category(q: &BTreeMap<String, String>) -> Result<Option<String>, ApiFault> {
    match q.get("category").filter(|v| !v.is_empty()) {
        None => Ok(None),
        Some(c) if matches!(c.as_str(), "REAL_ESTATE" | "STOCK" | "ETF") => Ok(Some(c.clone())),
        _ => Err(invalid("category", "지원하지 않는 값입니다.")),
    }
}
fn search_terms(q: &BTreeMap<String, String>) -> Result<Vec<String>, ApiFault> {
    let raw = q
        .get("q")
        .ok_or_else(|| invalid("keyword", "검색어를 입력해주세요."))?;
    if raw.trim().is_empty() {
        return Err(invalid("keyword", "검색어를 입력해주세요."));
    }
    if raw.encode_utf16().count() > 100 {
        return Err(invalid("keyword", "검색어는 100자 이하여야 합니다."));
    }
    if raw
        .chars()
        .any(|c| matches!(c, '\n' | '\r' | '\u{0085}' | '\u{2028}' | '\u{2029}'))
        || !raw.chars().any(char::is_alphanumeric)
    {
        return Err(invalid("keyword", "올바른 검색어를 입력해주세요."));
    }
    let mut result = Vec::new();
    for term in raw.split_whitespace().map(str::to_lowercase) {
        if !result.contains(&term) {
            result.push(term);
        }
    }
    Ok(result)
}
fn patterns(terms: &[String]) -> Vec<String> {
    terms
        .iter()
        .map(|t| {
            format!(
                "%{}%",
                t.replace('!', "!!").replace('%', "!%").replace('_', "!_")
            )
        })
        .collect()
}
fn news_missing() -> ApiFault {
    fault(404, "NEWS_NOT_FOUND", "해당 뉴스를 찾을 수 없습니다.")
}
async fn one(db: &Client, sql: &str, args: &[&(dyn ToSql + Sync)]) -> Result<Value, ApiFault> {
    rows(db, sql, args)
        .await?
        .into_iter()
        .next()
        .ok_or_else(internal)
}
// Java Instant.toString uses 0/3/6 fractional digits for PostgreSQL microseconds.
fn utc(col: &str) -> String {
    format!(
        "CASE WHEN {col} IS NULL THEN NULL ELSE to_char({col} AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS') || CASE WHEN to_char({col} AT TIME ZONE 'UTC','US')='000000' THEN '' WHEN right(to_char({col} AT TIME ZONE 'UTC','US'),3)='000' THEN '.' || left(to_char({col} AT TIME ZONE 'UTC','US'),3) ELSE '.' || to_char({col} AT TIME ZONE 'UTC','US') END || 'Z' END"
    )
}
fn news_item(n: &str) -> String {
    format!(
        "jsonb_build_object('id',{n}.id,'title',{n}.title,'imageUrl',{n}.image_url,'category',{n}.category,'publishedAt',{})",
        utc(&format!("{n}.published_at"))
    )
}
fn content_item(c: &str) -> String {
    format!(
        "jsonb_build_object('id',{c}.id,'assetId',{c}.asset_id,'sourceType',{c}.source_type,'title',{c}.title,'url',{c}.url,'imageUrl',CASE WHEN {c}.news_id IS NULL THEN {c}.image_url ELSE n.image_url END,'createdAt',{},'publishedDate',{c}.published_date)",
        utc(&format!("{c}.created_at"))
    )
}

async fn news_search(db: &Client, q: &BTreeMap<String, String>) -> Result<Value, ApiFault> {
    let terms = patterns(&search_terms(q)?);
    let category = category(q)?;
    let (page, size) = pagination(q, 20, true)?;
    let sort = q
        .get("sort")
        .filter(|v| !v.is_empty())
        .map(String::as_str)
        .unwrap_or("LATEST");
    if !matches!(sort, "LATEST" | "RELEVANCE") {
        return Err(invalid("sort", "지원하지 않는 값입니다."));
    }
    let relevance = sort == "RELEVANCE";
    let offset = (page - 1) * size;
    let dto = news_item("n");
    let sql = format!(
        r#"WITH matched AS (
       SELECT n.*, (SELECT count(*) FROM unnest($1::text[]) term WHERE lower(n.title) LIKE term ESCAPE '!') score
       FROM news n WHERE n.status='PUBLISHED' AND ($2::text IS NULL OR n.category=$2)
       AND NOT EXISTS (SELECT 1 FROM unnest($1::text[]) term WHERE NOT (lower(n.title) LIKE term ESCAPE '!' OR lower(n.content) LIKE term ESCAPE '!'))
    ), selected AS (SELECT {dto} AS item FROM matched n ORDER BY CASE WHEN $3::boolean THEN score ELSE 0 END DESC,published_at DESC,id DESC LIMIT $4 OFFSET $5)
    SELECT jsonb_build_object('content',coalesce((SELECT jsonb_agg(item) FROM selected),'[]'::jsonb),'page',$6::bigint,'size',$4::bigint,'totalElements',count(*),'totalPages',(count(*)+$4-1)/$4)::text FROM matched"#
    );
    one(
        db,
        &sql,
        &[&terms, &category, &relevance, &size, &offset, &page],
    )
    .await
}

async fn content_search(db: &Client, q: &BTreeMap<String, String>) -> Result<Value, ApiFault> {
    let terms = patterns(&search_terms(q)?);
    let (page, size) = pagination(q, 12, false)?;
    let source = q
        .get("source")
        .filter(|v| !v.is_empty())
        .map(String::as_str)
        .unwrap_or("ALL");
    if !matches!(source, "ALL" | "DAYNOMY" | "X" | "THREADS" | "YOUTUBE") {
        return Err(invalid("source", "지원하지 않는 값입니다."));
    }
    let offset = (page - 1) * size;
    let prefix = CONTENT_SEARCH_CTE;
    let date = utc("m.occurred_at");
    let sql = format!(
        r#"{prefix}
       , selected AS (SELECT jsonb_build_object('kind',m.kind,'id',m.id,'source',m.source,'title',m.title,'date',{date},'url',m.url,'personId',m.person_id,'personName',m.person_name,'assetId',m.asset_id,'imageUrl',m.image_url,'category',m.category,'publishedDate',m.published_date) AS item
          FROM matched m ORDER BY occurred_at DESC NULLS LAST,kind,id LIMIT $3 OFFSET $4)
       SELECT jsonb_build_object('items',coalesce((SELECT jsonb_agg(item) FROM selected),'[]'::jsonb),'page',$5::bigint,'size',$3::bigint,'totalElements',count(*),'totalPages',(count(*)+$3-1)/$3)::text FROM matched"#
    );
    one(db, &sql, &[&terms, &source, &size, &offset, &page]).await
}

const CONTENT_SEARCH_CTE: &str = r#"
      WITH external_raw AS (
        SELECT 'PERSON_POST' AS kind, p.id, p.source_type AS source, p.title,
               CAST(NULL AS text) AS body, p.created_at AS occurred_at, p.url,
               p.person_id, person.name AS person_name, CAST(NULL AS bigint) AS asset_id,
               CAST(NULL AS text) AS image_url, CAST(NULL AS text) AS category,
               CAST(NULL AS date) AS published_date
        FROM featured_person_posts p
        JOIN featured_people person ON person.id = p.person_id
        WHERE p.status = 'APPROVED'
        UNION ALL
        SELECT 'ASSET_CONTENT', c.id, c.source_type, c.title, CAST(NULL AS text),
               c.created_at, c.url, CAST(NULL AS bigint), CAST(NULL AS text), c.asset_id,
               c.image_url, CAST(NULL AS text), c.published_date
        FROM stock_related_contents c
        WHERE c.news_id IS NULL AND c.source_type IN ('YOUTUBE', 'THREADS', 'X')
      ),
      external_cleaned AS (
        SELECT e.*,
               regexp_replace(
                 split_part(split_part(e.url, '?', 1), '#', 1),
                 '^https?://(www\.)?', '', 'i'
               ) AS stripped_url
        FROM external_raw e
      ),
      external_normalized AS (
        SELECT e.*,
               replace(
                 replace(lower(split_part(e.stripped_url, '/', 1)), 'twitter.com', 'x.com'),
                 'threads.net', 'threads.com'
               ) ||
               regexp_replace(
                 substr(e.stripped_url, length(split_part(e.stripped_url, '/', 1)) + 1),
                 '/$', ''
               ) AS plain_url
        FROM external_cleaned e
      ),
      external_keys AS (
        SELECT e.*,
               CASE
                 WHEN e.url ~* '^https?://(www\.|m\.)?youtu\.be/' THEN
                   coalesce(
                     'youtube:' || substring(e.url FROM
                       '^https?://(?:www\.|m\.)?youtu\.be/([A-Za-z0-9_-]{11})(?:[/#?]|$)'),
                     e.plain_url
                   )
                 WHEN e.url ~* '^https?://(www\.|m\.)?youtube\.com/' THEN
                   coalesce(
                     'youtube:' || substring(e.url FROM '[?&]v=([A-Za-z0-9_-]{11})(?:[&#]|$)'),
                     'youtube:' || substring(e.url FROM
                       '/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})(?:[/#?]|$)'),
                     e.plain_url
                   )
                 ELSE e.plain_url
               END AS url_key
        FROM external_normalized e
      ),
      external_ranked AS (
        SELECT e.*,
               row_number() OVER (
                 PARTITION BY e.url_key
                 ORDER BY CASE WHEN e.kind = 'PERSON_POST' THEN 0 ELSE 1 END,
                          e.occurred_at DESC, e.id DESC
               ) AS duplicate_rank
        FROM external_keys e
      ),
      all_contents AS (
        SELECT e.kind, e.id, e.source, e.title, e.body, e.occurred_at, e.url,
               e.person_id, e.person_name, e.asset_id, e.image_url, e.category,
               e.published_date
        FROM external_ranked e
        WHERE e.kind = 'PERSON_POST' OR e.duplicate_rank = 1
        UNION ALL
        SELECT 'NEWS', n.id, 'DAYNOMY', n.title, n.content, n.published_at,
               CAST(NULL AS text), CAST(NULL AS bigint), CAST(NULL AS text),
               CAST(NULL AS bigint), n.image_url, n.category, CAST(NULL AS date)
        FROM news n
        WHERE n.status = 'PUBLISHED'
      ),
      matched AS (
        SELECT *
        FROM all_contents
        WHERE ($2::text = 'ALL' OR source = $2::text)
        AND NOT EXISTS (SELECT 1 FROM unnest($1::text[]) term WHERE NOT coalesce((lower(title) LIKE term ESCAPE '!' OR lower(body) LIKE term ESCAPE '!'),false))
      )
"#;
