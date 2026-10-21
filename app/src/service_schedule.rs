//! Opt-in batch runner. No HTTP routes or background work are enabled implicitly.
use crate::api::{ApiFault, Outcome, fault, internal, rows};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::Arc,
    time::Duration,
};
use tokio_postgres::{Client, Config, NoTls};
type Result<T> = std::result::Result<T, ApiFault>;

const JOBS: &[(&str, &str, &str, &str, bool)] = &[
    (
        "market-calendar",
        "MARKET_CALENDAR_SYNC_CRON",
        "0 5 6,18 * * *",
        "Asia/Seoul",
        true,
    ),
    (
        "kr-master",
        "STOCK_SYNC_CRON",
        "0 10 14 * * MON-FRI",
        "Asia/Seoul",
        false,
    ),
    (
        "kr-prices",
        "STOCK_PRICE_SYNC_CRON",
        "0 30 13,18 * * MON-FRI",
        "Asia/Seoul",
        false,
    ),
    (
        "us-stocks",
        "US_STOCK_SYNC_CRON",
        "0 15 6 * * *",
        "America/New_York",
        false,
    ),
    (
        "exchange-rate",
        "EXCHANGE_RATE_SYNC_CRON",
        "0 10 6 * * *",
        "America/New_York",
        false,
    ),
    (
        "portfolio-snapshots",
        "PORTFOLIO_SNAPSHOT_CRON",
        "0 30 7 * * TUE-SAT",
        "Asia/Seoul",
        false,
    ),
    (
        "investment-calendar",
        "INVESTMENT_CALENDAR_SYNC_CRON",
        "0 0 4 * * *",
        "Asia/Seoul",
        true,
    ),
    (
        "news-korea",
        "KOREAN_NEWS_GENERATION_CRON",
        "0 0 9 * * *",
        "Asia/Seoul",
        false,
    ),
    (
        "news-us",
        "US_NEWS_GENERATION_CRON",
        "0 0 9 * * *",
        "Asia/Seoul",
        false,
    ),
    (
        "person-posts",
        "PERSON_POST_COLLECTION_CRON",
        "0 0 6 * * *",
        "Asia/Seoul",
        false,
    ),
];
struct ConnectionTask(tokio::task::JoinHandle<()>);
impl Drop for ConnectionTask {
    fn drop(&mut self) {
        self.0.abort();
    }
}
fn enable_flag(name: &str) -> &'static str {
    match name {
        "market-calendar" => "MARKET_CALENDAR_SYNC_ENABLED",
        "kr-master" => "STOCK_SYNC_ENABLED",
        "kr-prices" => "STOCK_PRICE_SYNC_ENABLED",
        "us-stocks" => "US_STOCK_SYNC_ENABLED",
        "exchange-rate" => "EXCHANGE_RATE_SYNC_ENABLED",
        "portfolio-snapshots" => "PORTFOLIO_SNAPSHOT_ENABLED",
        "investment-calendar" => "INVESTMENT_CALENDAR_SYNC_ENABLED",
        "news-korea" => "KOREAN_NEWS_GENERATION_ENABLED",
        "news-us" => "US_NEWS_GENERATION_ENABLED",
        "person-posts" => "PERSON_POST_COLLECTION_ENABLED",
        _ => "",
    }
}
fn cron_setting(name: &str, env: &str, default: &str) -> String {
    if name == "news-korea" {
        std::env::var(env).unwrap_or_else(|_| setting("ECONOMY_NEWS_GENERATION_CRON", default))
    } else {
        setting(env, default)
    }
}
fn enabled_by_flag(name: &str) -> bool {
    let configured = std::env::var(enable_flag(name)).ok().or_else(|| {
        if name == "news-korea" {
            std::env::var("ECONOMY_NEWS_GENERATION_ENABLED").ok()
        } else {
            None
        }
    });
    configured.is_none_or(|value| value == "true")
}
fn failure(code: &str) -> ApiFault {
    fault(502, code, "외부 데이터 동기화에 실패했습니다.")
}
fn setting(name: &str, default: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| default.into())
}
fn bounded(name: &str, default: u32, max: u32) -> u32 {
    std::env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .filter(|v| *v > 0 && *v <= max)
        .unwrap_or(default)
}

#[derive(Clone)]
struct Cron {
    fields: Vec<BTreeSet<u32>>,
}
impl Cron {
    fn parse(raw: &str) -> Option<Self> {
        let fields: Vec<_> = raw.split_whitespace().collect();
        if fields.len() != 6 {
            return None;
        }
        let bounds = [(0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 7)];
        let mut sets = Vec::new();
        for (index, field) in fields.into_iter().enumerate() {
            let (min, max) = bounds[index];
            let value = |s: &str| -> Option<u32> {
                let upper = s.to_ascii_uppercase();
                if index == 5
                    && let Some(i) = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
                        .iter()
                        .position(|v| *v == upper)
                {
                    return Some(i as u32);
                }
                if index == 4
                    && let Some(i) = [
                        "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
                        "NOV", "DEC",
                    ]
                    .iter()
                    .position(|v| *v == upper)
                {
                    return Some(i as u32 + 1);
                }
                s.parse().ok()
            };
            let mut set = BTreeSet::new();
            for part in field.split(',') {
                let (range, step) = if let Some((a, b)) = part.split_once('/') {
                    (a, b.parse::<u32>().ok()?)
                } else {
                    (part, 1)
                };
                if step == 0 || step > max - min + 1 || (range == "?" && index != 3 && index != 5) {
                    return None;
                }
                let (a, b) = if matches!(range, "*" | "?") {
                    (min, max)
                } else if let Some((a, b)) = range.split_once('-') {
                    (value(a)?, value(b)?)
                } else {
                    let a = value(range)?;
                    (a, if part.contains('/') { max } else { a })
                };
                if a < min || b > max || a > b {
                    return None;
                }
                for v in (a..=b).step_by(step as usize) {
                    set.insert(if index == 5 && v == 7 { 0 } else { v });
                }
            }
            if set.is_empty() {
                return None;
            }
            sets.push(set);
        }
        Some(Self { fields: sets })
    }
    fn matches(&self, fields: [u32; 6]) -> bool {
        self.fields
            .iter()
            .zip(fields)
            .all(|(set, v)| set.contains(&v))
    }
}
/// Six Spring-style fields, including named weekdays/months. Unsupported syntax
/// is rejected; a bad schedule never falls back to a more frequent schedule.
pub(crate) fn cron_matches(expression: &str, fields: [u32; 6]) -> bool {
    Cron::parse(expression).is_some_and(|c| c.matches(fields))
}

/// UTC high-water mark prevents duplicate dispatch when the wall clock moves
/// backward. Missed seconds are coalesced into one run, capped to sixty slots.
pub(crate) fn poll_window(previous: Option<i64>, now: i64) -> Option<(i64, i64)> {
    if previous.is_some_and(|p| p >= now) {
        return None;
    }
    Some((
        previous
            .map(|p| p.saturating_add(1).max(now.saturating_sub(59)))
            .unwrap_or(now),
        now,
    ))
}

/// Global opt-in AND an explicit job allowlist are required. The handle owns all
/// child loops: aborting it also aborts the loops and drops their connections.
pub fn spawn(config: Arc<Config>) -> Option<tokio::task::JoinHandle<()>> {
    if setting("JOB_SCHEDULER_ENABLED", "false") != "true" {
        return None;
    }
    let selected: BTreeSet<_> = setting("JOB_SCHEDULER_JOBS", "")
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .collect();
    if selected.is_empty()
        || selected
            .iter()
            .any(|name| !JOBS.iter().any(|j| j.0 == name))
    {
        eprintln!("event=scheduler.invalid_job_selection");
        return None;
    }
    let mut enabled = Vec::new();
    for &(name, env, default, zone, startup) in JOBS {
        if !selected.contains(name) || !enabled_by_flag(name) {
            continue;
        }
        let cron = cron_setting(name, env, default);
        if Cron::parse(&cron).is_none() {
            eprintln!("event=scheduler.invalid_cron job={name}");
            return None;
        }
        enabled.push((name, zone, startup, cron));
    }
    Some(tokio::spawn(async move {
        let mut workers = tokio::task::JoinSet::new();
        for (name, zone, startup, cron) in enabled {
            let config = config.clone();
            workers.spawn(async move {
                let mut previous: Option<i64> = None;
                let mut first=true;
                loop {
                    // Each iteration owns its connection, including advisory locks.
                    let connected=config.connect(NoTls).await;
                    if let Ok((db, connection))=connected {
                        let connection_task=ConnectionTask(tokio::spawn(async move { let _=connection.await; }));
                        let clock=db.query_one("SELECT floor(extract(epoch from clock_timestamp()))::bigint", &[]).await;
                        if let Ok(clock)=clock {
                            let now:i64=clock.get(0);
                            let window=poll_window(previous,now);
                            let from=window.map(|w|w.0).unwrap_or(now.saturating_add(1));
                            // Catch up at most sixty seconds after process stalls. We do
                            // not replay hours of paid-provider work on restart.
                            let samples=db.query("SELECT s::bigint,extract(second from z)::int,extract(minute from z)::int,extract(hour from z)::int,extract(day from z)::int,extract(month from z)::int,extract(dow from z)::int FROM generate_series($1::bigint,$2::bigint) s CROSS JOIN LATERAL (SELECT to_timestamp(s) AT TIME ZONE $3::text z) q ORDER BY s", &[&from,&now,&zone]).await;
                            let due=samples.ok().is_some_and(|samples| samples.iter().any(|r| cron_matches(&cron,[r.get::<_,i32>(1) as u32,r.get::<_,i32>(2) as u32,r.get::<_,i32>(3) as u32,r.get::<_,i32>(4) as u32,r.get::<_,i32>(5) as u32,r.get::<_,i32>(6) as u32])));
                            previous=Some(previous.unwrap_or(now).max(now));
                            if (first && startup) || due {
                                let result=run_named(name,&db).await;
                                match result { Ok((status,_)) => eprintln!("event=scheduler.finished job={name} status={status}"), Err(err)=>eprintln!("event=scheduler.failed job={name} status={}",err.status) }
                            }
                            first=false;
                        }
                        drop(db); drop(connection_task);
                    } else { eprintln!("event=scheduler.database_unavailable job={name}"); }
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }
            });
        }
        while workers.join_next().await.is_some() {}
    }))
}

/// Explicit batch entrypoint; does not expose a new public API route. Session
/// advisory locks prevent overlapping schedulers/processes without holding a
/// transaction or row lock while providers are contacted.
pub async fn run_named(name: &str, db: &Client) -> Outcome {
    let Some(index) = JOBS.iter().position(|j| j.0 == name) else {
        return Err(fault(
            400,
            "INVALID_REQUEST",
            "지원하지 않는 배치 작업입니다.",
        ));
    };
    let key = 7_519_100_i64 + index as i64;
    let locked: bool = db
        .query_one("SELECT pg_try_advisory_lock($1)", &[&key])
        .await
        .map_err(|_| internal())?
        .get(0);
    if !locked {
        return Err(fault(
            409,
            "SYNC_ALREADY_RUNNING",
            "동기화가 이미 진행 중입니다.",
        ));
    }
    let result = match name {
        "market-calendar" => market_calendar(db).await,
        "exchange-rate" => exchange_rate(db).await,
        "portfolio-snapshots" => crate::service_portfolio::refresh_latest_snapshots(db)
            .await
            .map(|(completed, failed)| {
                (
                    if failed == 0 { 200 } else { 207 },
                    json!({"completedCount":completed,"failedCount":failed}),
                )
            }),
        "investment-calendar" => investment_calendar(db).await,
        "news-korea" | "news-us" => crate::service_admin_news::handle(
            "POST",
            if name == "news-us" {
                "/api/admin/news/generate/economy/us"
            } else {
                "/api/admin/news/generate/economy/korea"
            },
            "",
            b"",
            None,
            db,
        )
        .await
        .unwrap_or_else(|| Err(internal())),
        "person-posts" => person_posts(db).await,
        "kr-master" => sync_route("/api/admin/stocks/sync", db).await,
        "kr-prices" => sync_route("/api/admin/stocks/prices/sync", db).await,
        "us-stocks" => {
            let master = sync_route("/api/admin/stocks/us/sync", db).await;
            match master {
                Err(e) => Err(e),
                Ok((_, master)) => sync_route("/api/admin/stocks/us/prices/sync", db)
                    .await
                    .map(|(s, prices)| (s, json!({"master":master,"prices":prices}))),
            }
        }
        _ => unreachable!(),
    };
    // A failed statement may leave an aborted transaction. Roll back before
    // releasing the session lock, even when the underlying operation already did.
    if result.is_err() {
        let _ = db.batch_execute("ROLLBACK").await;
    }
    let unlocked = db.query_one("SELECT pg_advisory_unlock($1)", &[&key]).await;
    if unlocked.is_err() {
        return Err(internal());
    }
    result
}
async fn sync_route(path: &str, db: &Client) -> Outcome {
    crate::service_sync::handle("POST", path, "", b"", db)
        .await
        .ok_or_else(internal)?
}
async fn today(db: &Client, zone: &str) -> Result<String> {
    Ok(db
        .query_one(
            "SELECT (clock_timestamp() AT TIME ZONE $1)::date::text",
            &[&zone],
        )
        .await
        .map_err(|_| internal())?
        .get(0))
}
async fn exchange_rate(db: &Client) -> Outcome {
    let date = today(db, "Asia/Seoul").await?;
    crate::service_market::refresh_quote(&date, db)
        .await
        .map(|v| (200, v))
}

fn provider_url(raw: &str) -> Result<reqwest::Url> {
    let url = reqwest::Url::parse(raw).map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))?;
    if url.scheme() != "https"
        && !(url.scheme() == "http"
            && matches!(
                url.host_str(),
                Some("localhost" | "127.0.0.1" | "::1" | "[::1]")
            ))
    {
        return Err(failure("BATCH_PROVIDER_REQUEST_FAILED"));
    }
    Ok(url)
}
async fn request(
    url: &str,
    params: &[(String, String)],
    body: Option<Value>,
    form: bool,
) -> Result<(u16, String)> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(
            bounded("INVESTMENT_CALENDAR_READ_TIMEOUT_SECONDS", 15, 120) as u64,
        ))
        .connect_timeout(Duration::from_secs(3))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))?;
    let url = provider_url(url)?;
    let req = if form {
        client.post(url).form(params)
    } else if let Some(body) = body {
        client.post(url).json(&body)
    } else {
        client.get(url).query(params)
    };
    let mut response = req
        .header(
            "Referer",
            format!(
                "{}/contents/MKD/01/0110/01100305/MKD01100305.jsp",
                setting("KRX_CALENDAR_BASE_URL", "https://open.krx.co.kr").trim_end_matches('/')
            ),
        )
        .send()
        .await
        .map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))?;
    let status = response.status().as_u16();
    if status != 404 && !(200..300).contains(&status) {
        return Err(failure("BATCH_PROVIDER_REQUEST_FAILED"));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))?
    {
        if bytes.len() + chunk.len() > 8_000_000 {
            return Err(failure("BATCH_PROVIDER_REQUEST_FAILED"));
        }
        bytes.extend_from_slice(&chunk);
    }
    Ok((
        status,
        String::from_utf8(bytes).map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))?,
    ))
}
async fn get_json(url: &str, params: &[(String, String)], body: Option<Value>) -> Result<Value> {
    let (status, text) = request(url, params, body, false).await?;
    if status == 404 {
        return Err(failure("BATCH_PROVIDER_REQUEST_FAILED"));
    }
    serde_json::from_str(&text).map_err(|_| failure("BATCH_PROVIDER_REQUEST_FAILED"))
}
fn elements<'a>(html: &'a str, tag: &str) -> Vec<(&'a str, &'a str)> {
    let lower = html.to_ascii_lowercase();
    let open = format!("<{tag}");
    let close = format!("</{tag}>");
    let mut offset = 0;
    let mut out = Vec::new();
    while let Some(start) = lower[offset..].find(&open) {
        let start = offset + start;
        let boundary = start + open.len();
        if !lower
            .as_bytes()
            .get(boundary)
            .is_some_and(|c| c.is_ascii_whitespace() || *c == b'>')
        {
            offset = boundary;
            continue;
        }
        let Some(end) = lower[boundary..].find('>') else {
            break;
        };
        let end = boundary + end;
        let Some(stop) = lower[end + 1..].find(&close) else {
            break;
        };
        let stop = end + 1 + stop;
        out.push((&html[start..=end], &html[end + 1..stop]));
        offset = stop + close.len();
    }
    out
}
fn attribute(tag: &str, name: &str) -> Option<String> {
    let inside = tag.trim_start_matches('<').trim_end_matches('>');
    let bytes = inside.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        while i < bytes.len() && (bytes[i].is_ascii_whitespace() || bytes[i] == b'/') {
            i += 1;
        }
        let start = i;
        while i < bytes.len() && !bytes[i].is_ascii_whitespace() && bytes[i] != b'=' {
            i += 1;
        }
        let key = &inside[start..i];
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if bytes.get(i) != Some(&b'=') {
            continue;
        }
        i += 1;
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        let quote = bytes.get(i).copied()?;
        let value = if quote == b'\'' || quote == b'"' {
            i += 1;
            let start = i;
            while i < bytes.len() && bytes[i] != quote {
                i += 1;
            }
            let v = &inside[start..i];
            i += usize::from(i < bytes.len());
            v
        } else {
            let start = i;
            while i < bytes.len() && !bytes[i].is_ascii_whitespace() {
                i += 1;
            }
            &inside[start..i]
        };
        if key.eq_ignore_ascii_case(name) {
            return Some(value.into());
        }
    }
    None
}
fn text(html: &str) -> String {
    let mut output = String::new();
    let mut tag = false;
    for c in html.chars() {
        if c == '<' {
            tag = true;
            output.push(' ');
        } else if c == '>' {
            tag = false;
        } else if !tag {
            output.push(c);
        }
    }
    output
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace("&amp;", "&")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
fn date_shape(date: &str) -> bool {
    if date.len() != 10
        || date.as_bytes()[4] != b'-'
        || date.as_bytes()[7] != b'-'
        || !date
            .bytes()
            .enumerate()
            .all(|(i, c)| i == 4 || i == 7 || c.is_ascii_digit())
    {
        return false;
    }
    let Ok(y) = date[..4].parse::<u32>() else {
        return false;
    };
    let Ok(m) = date[5..7].parse::<u32>() else {
        return false;
    };
    let Ok(d) = date[8..].parse::<u32>() else {
        return false;
    };
    if y == 0 || !(1..=12).contains(&m) {
        return false;
    }
    let days = match m {
        2 => {
            if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) {
                29
            } else {
                28
            }
        }
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    };
    (1..=days).contains(&d)
}

async fn market_calendar(db: &Client) -> Outcome {
    let base = setting("KRX_CALENDAR_BASE_URL", "https://open.krx.co.kr");
    let (status, html) = request(
        &format!(
            "{}/contents/MKD/01/0110/01100305/MKD01100305.jsp",
            base.trim_end_matches('/')
        ),
        &[],
        None,
        false,
    )
    .await
    .map_err(|_| failure("KRX_CALENDAR_REQUEST_FAILED"))?;
    if status == 404 {
        return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));
    }
    let select = elements(&html, "select")
        .into_iter()
        .find(|(tag, _)| attribute(tag, "name").as_deref() == Some("search_bas_yy"))
        .ok_or_else(|| failure("KRX_CALENDAR_REQUEST_FAILED"))?;
    let years: BTreeSet<i32> = select
        .1
        .split('<')
        .filter(|s| s.to_ascii_lowercase().starts_with("option "))
        .filter_map(|s| attribute(&format!("<{}>", s.split('>').next().unwrap_or("")), "value"))
        .filter(|s| s.len() == 4 && s.bytes().all(|c| c.is_ascii_digit()))
        .filter_map(|s| s.parse().ok())
        .collect();
    if years.is_empty() {
        return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));
    }
    let current: i32 = today(db, "Asia/Seoul").await?[..4]
        .parse()
        .map_err(|_| internal())?;
    let mut changed = 0u64;
    let mut completed = Vec::new();
    let mut failed = Vec::new();
    for year in current - 1..=current + 1 {
        if !years.contains(&year) {
            continue;
        }
        let result:Result<u64>=async {
            let (_,code)=request(&format!("{}/contents/COM/GenerateOTP.jspx",base.trim_end_matches('/')),&[("bld".into(),"MKD/01/0110/01100305/mkd01100305_01".into()),("name".into(),"form".into())],None,false).await?;
            let code=code.trim();if code.is_empty()||code.len()>1024||!code.bytes().all(|b|b.is_ascii_alphanumeric()||b"+/=_-".contains(&b)){return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));}
            let (_,body)=request(&format!("{}/contents/OPN/99/OPN99000001.jspx",base.trim_end_matches('/')),&[("search_bas_yy".into(),year.to_string()),("gridTp".into(),"KRX".into()),("code".into(),code.into())],None,true).await?;
            let value:Value=serde_json::from_str(&body).map_err(|_|failure("KRX_CALENDAR_REQUEST_FAILED"))?;
            let entries=value["block1"].as_array().filter(|a|!a.is_empty()&&a.len()<=366).ok_or_else(||failure("KRX_CALENDAR_REQUEST_FAILED"))?;
            let mut holidays=BTreeSet::new();for entry in entries {let date=entry["calnd_dd"].as_str().ok_or_else(||failure("KRX_CALENDAR_REQUEST_FAILED"))?;if !date_shape(date)||!date.starts_with(&format!("{year}-"))||!holidays.insert(date.to_owned()){return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));}}
            let holidays=serde_json::to_string(&holidays).map_err(|_|internal())?;
            let valid:bool=db.query_one("WITH h AS (SELECT value::date d FROM jsonb_array_elements_text($1::text::jsonb)), fixed AS (SELECT make_date($2::int,1,1) d UNION ALL SELECT make_date($2,5,1) UNION ALL SELECT make_date($2,12,25) UNION ALL SELECT max(d::date) FROM generate_series(make_date($2,12,25)::timestamp,make_date($2,12,31)::timestamp,interval '1 day') d WHERE extract(isodow from d)<=5) SELECT NOT EXISTS(SELECT 1 FROM fixed WHERE extract(isodow from d)<=5 AND d NOT IN(SELECT d FROM h))",&[&holidays,&year]).await.map_err(|_|failure("KRX_CALENDAR_REQUEST_FAILED"))?.get(0);
            if !valid{return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));}
            // One atomic statement per year. Revised trading status invalidates
            // collection markers just as MarketTradingDay.reviseTrading does.
            db.execute("WITH h AS (SELECT value::date d FROM jsonb_array_elements_text($1::text::jsonb)), days AS (SELECT d::date base_date,(extract(isodow FROM d)<=5 AND d::date NOT IN(SELECT d FROM h)) trading FROM generate_series(make_date($2::int,1,1)::timestamp,make_date($2,12,31)::timestamp,interval '1 day') d) INSERT INTO market_trading_days(base_date,trading,created_at,updated_at) SELECT base_date,trading,now(),now() FROM days ON CONFLICT(base_date) DO UPDATE SET trading=excluded.trading,collected_at=NULL,last_attempted_at=NULL,updated_at=now() WHERE market_trading_days.trading IS DISTINCT FROM excluded.trading",&[&holidays,&year]).await.map_err(|_|internal())
        }.await;
        match result {
            Ok(count) => {
                changed += count;
                completed.push(year);
            }
            Err(_) => failed.push(year),
        }
    }
    if completed.is_empty() && !failed.is_empty() {
        return Err(failure("KRX_CALENDAR_REQUEST_FAILED"));
    }
    Ok((
        if failed.is_empty() { 200 } else { 207 },
        json!({"changedDays":changed,"completedYears":completed,"failedYears":failed}),
    ))
}

fn decimal(raw: &str) -> Option<String> {
    let raw = raw.trim();
    if raw.is_empty() || raw.len() > 100 {
        return None;
    }
    serde_json::from_str::<Value>(raw)
        .ok()
        .filter(Value::is_number)
        .map(|v| v.to_string())
}
fn scalar(value: &Value) -> Option<String> {
    match value {
        Value::String(s) => decimal(s),
        Value::Number(n) => decimal(&n.to_string()),
        _ => None,
    }
}
fn month(raw: &str) -> Option<u32> {
    [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    .iter()
    .position(|m| m.eq_ignore_ascii_case(raw))
    .map(|i| i as u32 + 1)
}
fn english_date(raw: &str) -> Option<String> {
    let (_, date) = raw.split_once(',')?;
    let date = date.replace(',', " ");
    let mut parts = date.split_whitespace();
    let m = month(parts.next()?)?;
    let d = parts.next()?.parse::<u32>().ok()?;
    let y = parts.next()?.parse::<i32>().ok()?;
    if parts.next().is_some() || !(1..=31).contains(&d) || !(1900..=2200).contains(&y) {
        return None;
    }
    let result = format!("{y:04}-{m:02}-{d:02}");
    if !date_shape(&result) {
        return None;
    }
    let adjusted = y - i32::from(m < 3);
    let offsets = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
    let weekday = (adjusted + adjusted / 4 - adjusted / 100
        + adjusted / 400
        + offsets[(m - 1) as usize]
        + d as i32)
        % 7;
    if raw.split_once(',')?.0
        != [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ][weekday as usize]
    {
        return None;
    }
    Some(result)
}
fn english_time(raw: &str) -> Option<String> {
    let mut parts = raw.split_whitespace();
    let (h, m) = parts.next()?.split_once(':')?;
    let mut h = h.parse::<u32>().ok()?;
    let m = m.parse::<u32>().ok()?;
    let suffix = parts.next()?;
    if parts.next().is_some() || h == 0 || h > 12 || m > 59 {
        return None;
    }
    h %= 12;
    if suffix.eq_ignore_ascii_case("PM") {
        h += 12;
    } else if !suffix.eq_ignore_ascii_case("AM") {
        return None;
    }
    Some(format!("{h:02}:{m:02}:00"))
}

async fn bls(today: &str, history: u32, db: &Client) -> Result<Vec<Value>> {
    let current = today[..4].parse::<i32>().map_err(|_| internal())?;
    let source = setting(
        "BLS_SCHEDULE_URL",
        "https://www.bls.gov/schedule/news_release/cpi.htm",
    );
    let schedule = provider_url(&source)?;
    let mut releases = BTreeMap::new();
    for year in current - history as i32..=current + 1 {
        let url = schedule
            .join(&format!("/schedule/{year}/home.htm"))
            .map_err(|_| failure("BLS_REQUEST_FAILED"))?;
        let (status, html) = request(url.as_str(), &[], None, false).await?;
        if status == 404 || html.trim().is_empty() {
            continue;
        }
        for (_, row) in elements(&html, "tr") {
            let cells: Vec<_> = elements(row, "td")
                .iter()
                .map(|(_, inner)| text(inner))
                .collect();
            if cells.len() < 3 {
                continue;
            }
            let Some(reference) = cells[2].strip_prefix("Consumer Price Index for ") else {
                continue;
            };
            let mut parts = reference.split_whitespace();
            let Some(m) = parts.next().and_then(month) else {
                continue;
            };
            let Some(y) = parts
                .next()
                .and_then(|s| s.parse::<i32>().ok())
                .filter(|y| (1900..=2200).contains(y))
            else {
                continue;
            };
            if parts.next().is_some() {
                continue;
            }
            let Some(date) = english_date(&cells[0]) else {
                continue;
            };
            let Some(time) = english_time(&cells[1]) else {
                continue;
            };
            releases.insert(format!("{y:04}-{m:02}"), format!("{date} {time}"));
        }
    }
    let base = setting("BLS_BASE_URL", "https://api.bls.gov/publicAPI/v2");
    let response=get_json(&format!("{}/timeseries/data/",base.trim_end_matches('/')),&[],Some(json!({"seriesid":["CUUR0000SA0"],"startyear":current-history as i32-2,"endyear":current+1}))).await?;
    if response["status"] != "REQUEST_SUCCEEDED" {
        return Err(failure("BLS_REQUEST_FAILED"));
    }
    let series = response["Results"]["series"]
        .as_array()
        .ok_or_else(|| failure("BLS_REQUEST_FAILED"))?;
    let mut indexes = BTreeMap::new();
    for series in series {
        let data = series["data"]
            .as_array()
            .ok_or_else(|| failure("BLS_REQUEST_FAILED"))?;
        if data.len() > 10_000 {
            return Err(failure("BLS_REQUEST_FAILED"));
        }
        for row in data {
            let Some(period) = row["period"].as_str() else {
                continue;
            };
            if period.len() != 3 || !period.starts_with('M') {
                continue;
            }
            let Some(m) = period[1..]
                .parse::<u32>()
                .ok()
                .filter(|m| (1..=12).contains(m))
            else {
                continue;
            };
            let Some(y) = row["year"]
                .as_str()
                .and_then(|s| s.parse::<i32>().ok())
                .filter(|y| (1900..=2200).contains(y))
            else {
                continue;
            };
            let Some(value) = scalar(&row["value"]) else {
                continue;
            };
            indexes.insert(format!("{y:04}-{m:02}"), value);
        }
    }
    let indexes = serde_json::to_string(&indexes).map_err(|_| internal())?;
    let encoded = serde_json::to_string(&releases).map_err(|_| internal())?;
    rows(db,"WITH r AS (SELECT key reference_month,value stamp FROM jsonb_each_text($1::text::jsonb)), i AS(SELECT key reference_month,value::numeric value FROM jsonb_each_text($2::text::jsonb)) SELECT json_build_object('type','US_CPI','title','미국 소비자물가지수 발표','announcedAt',r.stamp::timestamp AT TIME ZONE 'America/New_York','previousValue',round((p.value-py.value)*100/nullif(py.value,0),2),'actualValue',round((c.value-y.value)*100/nullif(y.value,0),2),'valueUnit','%','sourceName','미국 노동통계국(BLS)','sourceUrl',$3::text,'sourceKey','BLS-CPI-'||r.reference_month,'relatedAssetCode',NULL)::text FROM r LEFT JOIN i c ON c.reference_month=r.reference_month LEFT JOIN i y ON y.reference_month=to_char((r.reference_month||'-01')::date-interval '1 year','YYYY-MM') LEFT JOIN i p ON p.reference_month=to_char((r.reference_month||'-01')::date-interval '1 month','YYYY-MM') LEFT JOIN i py ON py.reference_month=to_char((r.reference_month||'-01')::date-interval '13 months','YYYY-MM') ORDER BY r.stamp",&[&encoded,&indexes,&source]).await
}
fn korean_month_day(raw: &str) -> Option<(u32, u32)> {
    let (before, after) = raw.split_once('월')?;
    let m = before
        .trim_end()
        .chars()
        .rev()
        .take_while(|c| c.is_ascii_digit())
        .collect::<String>()
        .chars()
        .rev()
        .collect::<String>()
        .parse::<u32>()
        .ok()?;
    let d = after
        .trim_start()
        .split_once('일')?
        .0
        .trim()
        .parse::<u32>()
        .ok()?;
    if !(1..=12).contains(&m) || !(1..=31).contains(&d) {
        return None;
    }
    Some((m, d))
}
async fn bok(today: &str, history: u32, db: &Client) -> Result<Vec<Value>> {
    let key = setting("ECOS_API_KEY", "");
    if key.trim().is_empty() {
        return Err(fault(
            503,
            "ECOS_API_NOT_CONFIGURED",
            "ECOS API 키가 설정되지 않았습니다.",
        ));
    }
    let current = today[..4].parse::<i32>().map_err(|_| internal())?;
    let base = setting("BOK_BASE_URL", "https://www.bok.or.kr");
    let mut meetings = BTreeSet::new();
    for year in current - history as i32..=current + 1 {
        let (status, html) = request(
            &format!(
                "{}/portal/singl/crncyPolicyDrcMtg/listYear.do",
                base.trim_end_matches('/')
            ),
            &[
                ("menuNo".into(), "200755".into()),
                ("mtgSe".into(), "A".into()),
                ("pYear".into(), year.to_string()),
            ],
            None,
            false,
        )
        .await?;
        if status == 404 {
            return Err(failure("BOK_REQUEST_FAILED"));
        }
        for (tag, inner) in elements(&html, "th") {
            if attribute(tag, "scope").as_deref() != Some("row") {
                continue;
            }
            if let Some((m, d)) = korean_month_day(&text(inner)) {
                meetings.insert(format!("{year:04}-{m:02}-{d:02}"));
            }
        }
    }
    let Some(first) = meetings.first() else {
        return Ok(vec![]);
    };
    let bounds = db
        .query_one(
            "SELECT to_char($1::text::date-7,'YYYYMMDD'),to_char($2::text::date+1,'YYYYMMDD')",
            &[&first, &today],
        )
        .await
        .map_err(|_| failure("BOK_REQUEST_FAILED"))?;
    let from: String = bounds.get(0);
    let to: String = bounds.get(1);
    let mut url = provider_url(&setting("ECOS_BASE_URL", "https://ecos.bok.or.kr/api"))?;
    url.path_segments_mut()
        .map_err(|_| failure("BOK_REQUEST_FAILED"))?
        .pop_if_empty()
        .extend([
            "StatisticSearch",
            key.as_str(),
            "json",
            "kr",
            "1",
            "10000",
            "722Y001",
            "D",
            &from,
            &to,
            "0101000",
        ]);
    let response = get_json(url.as_str(), &[], None).await?;
    let rate_rows = response["StatisticSearch"]["row"]
        .as_array()
        .ok_or_else(|| failure("BOK_REQUEST_FAILED"))?;
    if rate_rows.len() > 10_000 {
        return Err(failure("BOK_REQUEST_FAILED"));
    }
    let mut rates = BTreeMap::new();
    for row in rate_rows {
        let date = row["TIME"]
            .as_str()
            .filter(|s| s.len() == 8 && s.bytes().all(|b| b.is_ascii_digit()))
            .ok_or_else(|| failure("BOK_REQUEST_FAILED"))?;
        let value = scalar(&row["DATA_VALUE"]).ok_or_else(|| failure("BOK_REQUEST_FAILED"))?;
        rates.insert(
            format!("{}-{}-{}", &date[..4], &date[4..6], &date[6..]),
            value,
        );
    }
    let meetings = serde_json::to_string(&meetings).map_err(|_| internal())?;
    let rates = serde_json::to_string(&rates).map_err(|_| internal())?;
    rows(db,"WITH m AS(SELECT value::date d FROM jsonb_array_elements_text($1::text::jsonb)),r AS(SELECT key::date d,value::numeric v FROM jsonb_each_text($2::text::jsonb)) SELECT json_build_object('type','KOREA_BASE_RATE','title','한국 기준금리 결정','announcedAt',(m.d+time '09:00') AT TIME ZONE 'Asia/Seoul','previousValue',(SELECT v FROM r WHERE r.d<m.d ORDER BY r.d DESC LIMIT 1),'actualValue',(SELECT v FROM r WHERE r.d=m.d),'valueUnit','%','sourceName','한국은행','sourceUrl','https://www.bok.or.kr/portal/main/contents.do?menuNo=200755','sourceKey','BOK-BASE-RATE-'||m.d::text,'relatedAssetCode',NULL)::text FROM m ORDER BY m.d",&[&meetings,&rates]).await
}
async fn store_events(entries: Vec<Value>, db: &Client) -> Result<Value> {
    let mut unique = BTreeMap::new();
    for entry in entries {
        let key = entry["sourceKey"]
            .as_str()
            .ok_or_else(|| failure("INVESTMENT_CALENDAR_INVALID_DATA"))?
            .to_owned();
        unique.insert(key, entry);
    }
    let entries = Value::Array(unique.into_values().collect()).to_string();
    // Conflict updates retain the original event type. Only source-owned fields
    // in InvestmentEvent.synchronize are changed; user reactions remain intact.
    let result=rows(db,"WITH input AS(SELECT r->>'type' event_type,r->>'title' title,(r->>'announcedAt')::timestamptz announced_at,(r->>'previousValue')::numeric previous_value,(r->>'actualValue')::numeric actual_value,r->>'valueUnit' value_unit,r->>'sourceName' source_name,r->>'sourceUrl' source_url,r->>'sourceKey' source_key,r->>'relatedAssetCode' related_asset_code FROM jsonb_array_elements($1::text::jsonb) r), counts AS(SELECT count(*) FILTER(WHERE e.id IS NULL) created,count(*) FILTER(WHERE e.id IS NOT NULL AND ROW(e.title,e.announced_at,e.previous_value,e.actual_value,e.value_unit,e.source_name,e.source_url,e.related_asset_code) IS DISTINCT FROM ROW(i.title,i.announced_at,i.previous_value,i.actual_value,i.value_unit,i.source_name,i.source_url,i.related_asset_code)) updated,count(*) FILTER(WHERE e.id IS NOT NULL AND ROW(e.title,e.announced_at,e.previous_value,e.actual_value,e.value_unit,e.source_name,e.source_url,e.related_asset_code) IS NOT DISTINCT FROM ROW(i.title,i.announced_at,i.previous_value,i.actual_value,i.value_unit,i.source_name,i.source_url,i.related_asset_code)) unchanged FROM input i LEFT JOIN investment_events e USING(source_key)), written AS(INSERT INTO investment_events(event_type,title,announced_at,previous_value,actual_value,value_unit,source_name,source_url,source_key,related_asset_code,created_at,updated_at) SELECT event_type,title,announced_at,previous_value,actual_value,value_unit,source_name,source_url,source_key,related_asset_code,now(),now() FROM input ON CONFLICT(source_key) DO UPDATE SET title=excluded.title,announced_at=excluded.announced_at,previous_value=excluded.previous_value,actual_value=excluded.actual_value,value_unit=excluded.value_unit,source_name=excluded.source_name,source_url=excluded.source_url,related_asset_code=excluded.related_asset_code,updated_at=now() WHERE ROW(investment_events.title,investment_events.announced_at,investment_events.previous_value,investment_events.actual_value,investment_events.value_unit,investment_events.source_name,investment_events.source_url,investment_events.related_asset_code) IS DISTINCT FROM ROW(excluded.title,excluded.announced_at,excluded.previous_value,excluded.actual_value,excluded.value_unit,excluded.source_name,excluded.source_url,excluded.related_asset_code) RETURNING id) SELECT json_build_object('createdCount',created,'updatedCount',updated,'unchangedCount',unchanged)::text FROM counts",&[&entries]).await?;
    result.into_iter().next().ok_or_else(internal)
}
async fn investment_calendar(db: &Client) -> Outcome {
    let today = today(db, "Asia/Seoul").await?;
    let history = setting("INVESTMENT_CALENDAR_HISTORY_YEARS", "5")
        .parse::<u32>()
        .ok()
        .filter(|v| *v <= 10)
        .unwrap_or(5);
    let mut reports = Vec::new();
    let mut successful = 0;
    for provider in ["bls", "bok"] {
        let fetched = match provider {
            "bls" => bls(&today, history, db).await,
            _ => bok(&today, history, db).await,
        };
        let result = match fetched {
            Ok(entries) => store_events(entries, db).await,
            Err(e) => Err(e),
        };
        match result {Ok(counts)=>{successful+=1;reports.push(json!({"provider":provider,"status":"completed","counts":counts}));},Err(e)=>reports.push(json!({"provider":provider,"status":"failed","code":e.body.get("code").cloned().unwrap_or(Value::Null)}))}
    }
    let lookback = setting("INVESTMENT_CALENDAR_DART_LOOKBACK_DAYS", "30")
        .parse::<u32>()
        .ok()
        .filter(|v| *v <= 365)
        .unwrap_or(30);
    let dart = crate::service_dart::collect(&today, lookback, db).await;
    match dart {
        Ok(collection)=>{
            let partial=collection.failed_documents>0;
            let metadata=json!({"disclosureCount":collection.disclosure_count,"selectedDocuments":collection.selected_documents,"fetchedDocuments":collection.fetched_documents,"failedDocuments":collection.failed_documents,"skippedDocuments":collection.skipped_documents});
            match store_events(collection.entries,db).await {Ok(counts)=>{successful+=1;reports.push(json!({"provider":"dart","status":if partial {"partial"}else{"completed"},"counts":counts,"collection":metadata}));},Err(e)=>reports.push(json!({"provider":"dart","status":"failed","code":e.body.get("code").cloned().unwrap_or(Value::Null),"collection":metadata}))}
        },
        Err(e)=>reports.push(json!({"provider":"dart","status":"failed","code":e.body.get("code").cloned().unwrap_or(Value::Null)}))
    }

    match historical_prices(&today,history,db).await {Ok(counts)=>{let complete=counts["failedCount"].as_u64()==Some(0);reports.push(json!({"provider":"historical-prices","status":if complete {"completed"}else{"partial"},"counts":counts}));},Err(e)=>reports.push(json!({"provider":"historical-prices","status":"failed","code":e.body.get("code").cloned().unwrap_or(Value::Null)}))}

    if successful == 0 {
        return Err(failure("INVESTMENT_CALENDAR_SYNC_FAILED"));
    }
    let complete = reports.iter().all(|report| report["status"] == "completed");
    Ok((
        if complete { 200 } else { 207 },
        json!({"providers":reports,"complete":complete}),
    ))
}

async fn public_history(category: &str, code: &str, from: &str, to: &str) -> Result<Vec<Value>> {
    let key = crate::service_sync::service_key()?;
    let url = if category == "ETF" {
        setting(
            "PUBLIC_DATA_ETF_PRICE_URL",
            "https://apis.data.go.kr/1160100/GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2",
        )
    } else {
        setting(
            "PUBLIC_DATA_STOCK_PRICE_URL",
            "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo",
        )
    };
    let mut sorted = BTreeMap::new();
    let mut page = 1_i64;
    let mut expected = None;
    let mut seen = 0usize;
    loop {
        let response = get_json(
            &url,
            &[
                ("serviceKey".into(), key.clone()),
                ("resultType".into(), "json".into()),
                ("numOfRows".into(), "1000".into()),
                ("pageNo".into(), page.to_string()),
                ("likeSrtnCd".into(), code.into()),
                ("beginBasDt".into(), from.replace('-', "")),
                ("endBasDt".into(), to.replace('-', "")),
            ],
            None,
        )
        .await?;
        let head = &response["response"]["header"];
        let body = &response["response"]["body"];
        if head["resultCode"] != "00" || !body.is_object() {
            return Err(failure("PUBLIC_DATA_API_REQUEST_FAILED"));
        }
        let total = body["totalCount"]
            .as_i64()
            .or_else(|| body["totalCount"].as_str().and_then(|s| s.parse().ok()))
            .filter(|n| (0..=250_000).contains(n))
            .ok_or_else(|| failure("PUBLIC_DATA_API_REQUEST_FAILED"))?;
        if expected.is_some_and(|n| n != total) {
            return Err(failure("PUBLIC_DATA_API_REQUEST_FAILED"));
        }
        expected = Some(total);
        let items = match body.get("items").and_then(|v| v.get("item")) {
            None | Some(Value::Null) => Vec::new(),
            Some(Value::Array(v)) => v.clone(),
            _ => return Err(failure("PUBLIC_DATA_API_REQUEST_FAILED")),
        };
        if items.len() > 1000 || (items.is_empty() && seen < total as usize) {
            return Err(failure("PUBLIC_DATA_API_REQUEST_FAILED"));
        }
        seen += items.len();
        if seen > 250_000 {
            return Err(failure("PUBLIC_DATA_API_REQUEST_FAILED"));
        }
        for item in items {
            if item["srtnCd"].as_str() != Some(code) {
                continue;
            }
            let Some(raw) = item["basDt"]
                .as_str()
                .filter(|s| s.len() == 8 && s.bytes().all(|b| b.is_ascii_digit()))
            else {
                continue;
            };
            let date = format!("{}-{}-{}", &raw[..4], &raw[4..6], &raw[6..]);
            let Some(price) = scalar(&item["clpr"]) else {
                continue;
            };
            if !date_shape(&date)
                || date.as_str() < from
                || date.as_str() > to
                || price.starts_with('-')
                || !price
                    .split(['e', 'E'])
                    .next()
                    .unwrap_or("")
                    .bytes()
                    .any(|b| matches!(b, b'1'..=b'9'))
            {
                continue;
            }
            sorted.insert(date.clone(), json!({"date":date,"price":price}));
        }
        if page >= ((total + 999) / 1000).max(1) {
            break;
        }
        page += 1;
    }
    Ok(sorted.into_values().collect())
}
async fn historical_prices(today: &str, history: u32, db: &Client) -> Result<Value> {
    let history = history as i32;
    let assets=rows(db,"WITH target AS(SELECT DISTINCT a.id,a.asset_code,a.category,a.price_history_from FROM assets a JOIN portfolio_holdings h ON h.asset_id=a.id WHERE a.listed AND a.category IN('STOCK','ETF')),bounds AS(SELECT ($1::text::date-make_interval(years=>$2::int))::date requested_from,$1::text::date today) SELECT json_build_object('id',a.id,'code',a.asset_code,'category',a.category,'requestedFrom',b.requested_from,'fetchFrom',CASE WHEN p.earliest IS NULL THEN b.requested_from WHEN (a.price_history_from IS NULL OR a.price_history_from>b.requested_from) AND p.earliest>b.requested_from+10 THEN b.requested_from WHEN p.latest<b.today THEN p.latest+1 ELSE NULL END)::text FROM target a CROSS JOIN bounds b LEFT JOIN LATERAL(SELECT min(base_date) earliest,max(base_date) latest FROM stock_daily_prices WHERE asset_id=a.id AND base_date BETWEEN b.requested_from AND b.today) p ON true ORDER BY a.id",&[&today,&history]).await?;
    let mut fetched = 0_u64;
    let mut created = 0_u64;
    let mut updated = 0_u64;
    let mut unchanged = 0_u64;
    let mut failed = 0_u64;
    for asset in &assets {
        let Some(from) = asset["fetchFrom"].as_str() else {
            continue;
        };
        let result:Result<Value>=async {
            let category=asset["category"].as_str().ok_or_else(internal)?;let code=asset["code"].as_str().ok_or_else(internal)?;let id=asset["id"].as_i64().ok_or_else(internal)?;let requested=asset["requestedFrom"].as_str().ok_or_else(internal)?;
            let prices=public_history(category,code,from,today).await?;
            if prices.is_empty(){return Ok(json!({"fetched":0,"created":0,"updated":0,"unchanged":0}));}
            let encoded=Value::Array(prices).to_string();
            db.batch_execute("BEGIN").await.map_err(|_|internal())?;
            let operation:Result<Value>=async {
                // Serialize price writers only after network work is complete.
                db.query_one("SELECT pg_advisory_xact_lock(7519002)",&[]).await.map_err(|_|internal())?;
                let values=rows(db,"WITH input AS(SELECT (r->>'date')::date d,(r->>'price')::numeric p FROM jsonb_array_elements($1::text::jsonb) r),counts AS(SELECT count(*) fetched,count(*) FILTER(WHERE s.id IS NULL) created,count(*) FILTER(WHERE s.id IS NOT NULL AND s.close_price IS DISTINCT FROM i.p) updated,count(*) FILTER(WHERE s.id IS NOT NULL AND s.close_price IS NOT DISTINCT FROM i.p) unchanged FROM input i LEFT JOIN stock_daily_prices s ON s.asset_id=$2 AND s.base_date=i.d),written AS(INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) SELECT $2,d,p,now(),now() FROM input ON CONFLICT(asset_id,base_date) DO UPDATE SET close_price=excluded.close_price,updated_at=now() WHERE stock_daily_prices.close_price IS DISTINCT FROM excluded.close_price RETURNING id) SELECT json_build_object('fetched',fetched,'created',created,'updated',updated,'unchanged',unchanged)::text FROM counts",&[&encoded,&id]).await?;
                db.execute("UPDATE assets SET price_history_from=least(price_history_from,$2::text::date),updated_at=now() WHERE id=$1",&[&id,&requested]).await.map_err(|_|internal())?;
                values.into_iter().next().ok_or_else(internal)
            }.await;
            match operation {Ok(value)=>{if db.batch_execute("COMMIT").await.is_err(){let _=db.batch_execute("ROLLBACK").await;return Err(internal());}Ok(value)},Err(e)=>{let _=db.batch_execute("ROLLBACK").await;Err(e)}}
        }.await;
        match result {
            Ok(counts) => {
                fetched += counts["fetched"].as_u64().unwrap_or(0);
                created += counts["created"].as_u64().unwrap_or(0);
                updated += counts["updated"].as_u64().unwrap_or(0);
                unchanged += counts["unchanged"].as_u64().unwrap_or(0);
            }
            Err(_) => failed += 1,
        }
    }
    Ok(
        json!({"assetCount":assets.len(),"fetchedCount":fetched,"createdCount":created,"updatedCount":updated,"unchangedCount":unchanged,"failedCount":failed}),
    )
}

async fn person_posts(db: &Client) -> Outcome {
    let to = today(db, "Asia/Seoul").await?;
    let lookback = setting("PERSON_POST_COLLECTION_LOOKBACK_DAYS", "3")
        .parse::<i32>()
        .unwrap_or(3)
        .clamp(1, 31);
    let from: String = db
        .query_one(
            "SELECT ($1::text::date-($2::int-1))::text",
            &[&to, &lookback],
        )
        .await
        .map_err(|_| internal())?
        .get(0);
    let people = db
        .query("SELECT id FROM featured_people ORDER BY created_at,id", &[])
        .await
        .map_err(|_| internal())?;
    let mut completed = 0;
    let mut failed = Vec::new();
    for person in &people {
        let id: i64 = person.get(0);
        let result = crate::service_admin_content::handle(
            "POST",
            &format!("/api/admin/people/{id}/post-candidates/collect"),
            &format!("from={from}&to={to}"),
            b"",
            db,
        )
        .await
        .ok_or_else(internal)?;
        match result {
            Ok(_) => completed += 1,
            Err(error) => {
                let _ = db.batch_execute("ROLLBACK").await;
                failed.push(json!({"personId":id,"code":error.body["code"]}));
            }
        }
    }
    Ok((
        if failed.is_empty() { 200 } else { 207 },
        json!({"personCount":people.len(),"successCount":completed,"failureCount":failed.len(),"from":from,"to":to,"failures":failed}),
    ))
}

#[cfg(test)]
mod tests {
    use super::{cron_matches, date_shape, english_date, poll_window};

    #[test]
    fn default_kr_price_cron_excludes_weekends_and_wrong_seconds() {
        let cron = "0 30 13,18 * * MON-FRI";
        assert!(cron_matches(cron, [0, 30, 13, 21, 10, 3]));
        assert!(cron_matches(cron, [0, 30, 18, 23, 10, 5]));
        assert!(!cron_matches(cron, [1, 30, 13, 21, 10, 3]));
        assert!(!cron_matches(cron, [0, 30, 13, 24, 10, 6]));
        assert!(!cron_matches(cron, [0, 30, 13, 25, 10, 0]));
    }
    #[test]
    fn cron_supports_steps_named_months_and_sunday_alias() {
        assert!(cron_matches(
            "0 */15 9-10 * JAN,MAR 7",
            [0, 45, 10, 1, 3, 0]
        ));
        assert!(!cron_matches(
            "0 */15 9-10 * JAN,MAR 7",
            [0, 46, 10, 1, 3, 0]
        ));
        assert!(!cron_matches(
            "0 */15 9-10 * JAN,MAR 7",
            [0, 45, 10, 1, 2, 0]
        ));
    }
    #[test]
    fn invalid_cron_fails_closed() {
        for cron in [
            "* * * * *",
            "0 0 25 * * *",
            "0 */0 * * * *",
            "0 0 1 * * FUNDAY",
            "0 0 1 * * FRI-MON",
            "? 0 1 * * *",
            "0 0 1 0 * *",
        ] {
            assert!(
                !cron_matches(cron, [0, 0, 1, 1, 1, 0]),
                "accepted invalid cron: {cron}"
            );
        }
    }
    #[test]
    fn catch_up_is_bounded_and_does_not_revisit_seen_seconds() {
        assert_eq!(poll_window(None, 100), Some((100, 100)));
        assert_eq!(poll_window(Some(100), 101), Some((101, 101)));
        assert_eq!(poll_window(Some(100), 103), Some((101, 103)));
        assert_eq!(poll_window(Some(1), 100), Some((41, 100)));
        assert_eq!(poll_window(Some(100), 100), None);
        assert_eq!(poll_window(Some(100), 90), None);
    }
    #[test]
    fn provider_dates_reject_impossible_calendar_days() {
        assert!(date_shape("2024-02-29"));
        assert!(!date_shape("2025-02-29"));
        assert!(!date_shape("2100-02-29"));
        assert!(!date_shape("2026-04-31"));
        assert!(!date_shape("0000-01-01"));
    }
    #[test]
    fn bls_schedule_date_requires_matching_weekday() {
        assert_eq!(
            english_date("Wednesday, October 21, 2026"),
            Some("2026-10-21".into())
        );
        assert_eq!(english_date("Tuesday, October 21, 2026"), None);
        assert_eq!(english_date("Wednesday, February 30, 2026"), None);
    }
}
