//! Explicit administrator stock synchronisation. No scheduler starts here.
//! Providers are bounded and configurable for local fixtures; writes use the
//! original schema and NUMERIC text, and provider I/O precedes DB transactions.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query};
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tokio_postgres::Client;
type Result<T> = std::result::Result<T, ApiFault>;
const US: &str = "('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS')";
static KR_MASTER: AtomicBool = AtomicBool::new(false);
static KR_PRICES: AtomicBool = AtomicBool::new(false);
static US_SYNC: AtomicBool = AtomicBool::new(false);
struct Guard(&'static AtomicBool);
impl Drop for Guard {
    fn drop(&mut self) {
        self.0.store(false, Ordering::Release);
    }
}
fn acquire(flag: &'static AtomicBool, code: &str) -> Result<Guard> {
    flag.compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .map_err(|_| error(code))?;
    Ok(Guard(flag))
}
fn error(code: &str) -> ApiFault {
    let (status, message) = match code {
        "US_STOCK_SYNC_ALREADY_RUNNING" => {
            (409, "미국 종목 또는 종가 동기화가 이미 진행 중입니다.")
        }
        "US_STOCK_MASTER_DATA_NOT_FOUND" => {
            (502, "동기화할 미국 종목 데이터를 확인하지 못했습니다.")
        }
        "US_STOCK_PRICE_DATA_NOT_FOUND" => {
            (502, "동기화할 미국 종가 데이터를 확인하지 못했습니다.")
        }
        "US_STOCK_MASTER_REQUIRED" => (409, "미국 종목 목록을 먼저 동기화해주세요."),
        "INVALID_US_STOCK_PRICE_DATE" => {
            (400, "미국 종가는 뉴욕 기준 오늘 이전 날짜로 요청해주세요.")
        }
        "STOCK_SYNC_ALREADY_RUNNING" => (409, "국내 주식 종목 동기화가 이미 진행 중입니다."),
        "STOCK_MASTER_DATA_NOT_FOUND" => (502, "동기화할 국내 주식 종목 데이터를 찾지 못했습니다."),
        "STOCK_PRICE_SYNC_ALREADY_RUNNING" => (409, "국내 주식 종가 동기화가 이미 진행 중입니다."),
        "INVALID_STOCK_PRICE_BACKFILL_RANGE" => (400, "종가 백필 기간은 31일 이내여야 합니다."),
        "STOCK_PRICE_DATA_NOT_FOUND" => (502, "동기화할 국내 주식 종가 데이터를 찾지 못했습니다."),
        "EODHD_API_NOT_CONFIGURED" => (503, "EODHD API 키가 설정되지 않았습니다."),
        "EODHD_API_REQUEST_FAILED" => (502, "EODHD API 요청에 실패했습니다."),
        "PUBLIC_DATA_API_REQUEST_FAILED" => (502, "공공데이터 API 요청에 실패했습니다."),
        _ => return internal(),
    };
    fault(status, code, message)
}
fn trim(value: &str) -> &str {
    value.trim_matches(|c: char| c <= '\u{0020}')
}
fn text(row: &Value, key: &str) -> Option<String> {
    match row.get(key) {
        Some(Value::String(value)) => Some(value.clone()),
        Some(value) if value.is_number() || value.is_boolean() => Some(value.to_string()),
        _ => None,
    }
}
fn string(row: &Value, key: &str) -> String {
    text(row, key).unwrap_or_default()
}
fn date_valid(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() != 10
        || b[4] != b'-'
        || b[7] != b'-'
        || b.iter()
            .enumerate()
            .any(|(i, c)| i != 4 && i != 7 && !c.is_ascii_digit())
    {
        return false;
    }
    let y = value[..4].parse::<u32>().unwrap_or(0);
    let m = value[5..7].parse::<usize>().unwrap_or(0);
    let d = value[8..].parse::<u32>().unwrap_or(0);
    let days = [
        31,
        if y % 400 == 0 || y % 4 == 0 && y % 100 != 0 {
            29
        } else {
            28
        },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    y > 0 && (1..=12).contains(&m) && d > 0 && d <= days[m - 1]
}
fn basic_date(value: &str) -> Option<String> {
    let v = trim(value);
    if v.len() != 8 || !v.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let out = format!("{}-{}-{}", &v[..4], &v[4..6], &v[6..]);
    date_valid(&out).then_some(out)
}
async fn today(zone: &str, db: &Client) -> Result<String> {
    Ok(db
        .query_one(
            "SELECT (clock_timestamp() AT TIME ZONE $1)::date::text",
            &[&zone],
        )
        .await
        .map_err(|_| internal())?
        .get(0))
}
async fn shift(date: &str, days: i32, db: &Client) -> Result<String> {
    Ok(db
        .query_one("SELECT ($1::text::date+$2::integer)::text", &[&date, &days])
        .await
        .map_err(|_| internal())?
        .get(0))
}

pub async fn handle(
    method: &str,
    path: &str,
    raw: &str,
    _body: &[u8],
    db: &Client,
) -> Option<Outcome> {
    if !matches!(
        path,
        "/api/admin/stocks/sync"
            | "/api/admin/stocks/prices/sync"
            | "/api/admin/stocks/prices/backfill"
            | "/api/admin/stocks/us/sync"
            | "/api/admin/stocks/us/prices/sync"
    ) {
        return None;
    }
    if method != "POST" {
        return Some(Err(fault(
            405,
            "METHOD_NOT_ALLOWED",
            "지원하지 않는 HTTP 메서드입니다.",
        )));
    }
    Some(match path {
        "/api/admin/stocks/sync" => kr_master(db).await,
        "/api/admin/stocks/prices/sync" => kr_price_sync(db).await,
        "/api/admin/stocks/prices/backfill" => kr_backfill(raw, db).await,
        "/api/admin/stocks/us/sync" => us_master(db).await,
        _ => us_prices(raw, db).await,
    })
}
async fn fetch(url: &str, params: &[(String, String)], us: bool) -> Result<Value> {
    let code = if us {
        "EODHD_API_REQUEST_FAILED"
    } else {
        "PUBLIC_DATA_API_REQUEST_FAILED"
    };
    let parsed = reqwest::Url::parse(url).map_err(|_| error(code))?;
    if parsed.scheme() != "https"
        && !(parsed.scheme() == "http"
            && matches!(
                parsed.host_str(),
                Some("localhost" | "127.0.0.1" | "::1" | "[::1]")
            ))
    {
        return Err(error(code));
    }
    let timeout = std::env::var(if us {
        "EODHD_TIMEOUT_SECONDS"
    } else {
        "PUBLIC_DATA_TIMEOUT_SECONDS"
    })
    .ok()
    .and_then(|v| v.parse::<u64>().ok())
    .filter(|v| *v > 0 && *v <= 120)
    .unwrap_or(if us { 60 } else { 10 });
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(timeout))
        .connect_timeout(Duration::from_secs(3))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| error(code))?;
    let mut response = client
        .get(parsed)
        .query(params)
        .send()
        .await
        .map_err(|_| error(code))?;
    if !response.status().is_success() || response.content_length().is_some_and(|n| n > 32_000_000)
    {
        return Err(error(code));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| error(code))? {
        if bytes.len() + chunk.len() > 32_000_000 {
            return Err(error(code));
        }
        bytes.extend_from_slice(&chunk);
    }
    serde_json::from_slice(&bytes).map_err(|_| error(code))
}
async fn eodhd(endpoint: &str, date: Option<&str>) -> Result<Vec<Value>> {
    let key = std::env::var("EODHD_API_TOKEN").unwrap_or_default();
    if key.trim().is_empty() {
        return Err(error("EODHD_API_NOT_CONFIGURED"));
    }
    let base = std::env::var("EODHD_BASE_URL").unwrap_or_else(|_| "https://eodhd.com/api".into());
    let mut params = vec![("api_token".into(), key), ("fmt".into(), "json".into())];
    if let Some(date) = date {
        params.push(("date".into(), date.into()));
    }
    let result = fetch(
        &format!("{}/{}", base.trim_end_matches('/'), endpoint),
        &params,
        true,
    )
    .await?;
    let rows = result
        .as_array()
        .ok_or_else(|| error("EODHD_API_REQUEST_FAILED"))?;
    if rows.len() > 250_000 || rows.iter().any(|row| !row.is_object()) {
        return Err(error("EODHD_API_REQUEST_FAILED"));
    }
    let fields: &[&str] = if endpoint == "exchange-symbol-list/US" {
        &["Code", "Name", "Exchange", "Currency", "Type", "Isin"]
    } else {
        &["code", "exchange"]
    };
    if rows.iter().any(|row| {
        fields.iter().any(|field| {
            row.get(*field)
                .is_some_and(|value| value.is_array() || value.is_object())
        })
    }) {
        return Err(error("EODHD_API_REQUEST_FAILED"));
    }
    Ok(rows.clone())
}
pub(crate) fn service_key() -> Result<String> {
    let key = std::env::var("PUBLIC_DATA_SERVICE_KEY").unwrap_or_default();
    if key.is_empty() {
        return Err(error("PUBLIC_DATA_API_REQUEST_FAILED"));
    }
    if !key.contains('%') {
        return Ok(key);
    }
    let mut bytes = Vec::new();
    let mut raw = key.bytes();
    while let Some(byte) = raw.next() {
        match byte {
            b'%' => {
                let high = raw
                    .next()
                    .and_then(|v| (v as char).to_digit(16))
                    .ok_or_else(internal)?;
                let low = raw
                    .next()
                    .and_then(|v| (v as char).to_digit(16))
                    .ok_or_else(internal)?;
                bytes.push((high * 16 + low) as u8);
            }
            b'+' => bytes.push(b' '),
            _ => bytes.push(byte),
        }
    }
    String::from_utf8(bytes).map_err(|_| internal())
}
async fn public_page(
    kind: &str,
    date: &str,
    market: Option<&str>,
    page: i64,
) -> Result<(i64, Vec<Value>)> {
    let (env, default) = match kind {
        "master" => (
            "PUBLIC_DATA_LISTED_STOCK_URL",
            "https://apis.data.go.kr/1160100/GetKrxListedInfoService_V2/getItemInfo_V2",
        ),
        "etf" => (
            "PUBLIC_DATA_ETF_PRICE_URL",
            "https://apis.data.go.kr/1160100/GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2",
        ),
        _ => (
            "PUBLIC_DATA_STOCK_PRICE_URL",
            "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo",
        ),
    };
    let params = vec![
        ("serviceKey".into(), service_key()?),
        ("numOfRows".into(), "1000".into()),
        ("pageNo".into(), page.to_string()),
        ("resultType".into(), "json".into()),
        ("basDt".into(), date.replace('-', "")),
    ];
    let mut params = params;
    if let Some(market) = market {
        params.push(("mrktCls".into(), market.into()));
    }
    let response = fetch(
        &std::env::var(env).unwrap_or_else(|_| default.into()),
        &params,
        false,
    )
    .await?;
    let header = &response["response"]["header"];
    let body = &response["response"]["body"];
    if !header.is_object() || !body.is_object() || string(header, "resultCode") != "00" {
        return Err(error("PUBLIC_DATA_API_REQUEST_FAILED"));
    }
    let total = match body.get("totalCount") {
        None | Some(Value::Null) => 0,
        Some(Value::Number(n)) => n
            .as_i64()
            .ok_or_else(|| error("PUBLIC_DATA_API_REQUEST_FAILED"))?,
        Some(Value::String(s)) => s
            .parse::<i64>()
            .map_err(|_| error("PUBLIC_DATA_API_REQUEST_FAILED"))?,
        _ => return Err(error("PUBLIC_DATA_API_REQUEST_FAILED")),
    };
    if !(0..=250_000).contains(&total) {
        return Err(error("PUBLIC_DATA_API_REQUEST_FAILED"));
    }
    let items = match body.get("items").and_then(|items| items.get("item")) {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(rows)) => rows.clone(),
        _ => return Err(error("PUBLIC_DATA_API_REQUEST_FAILED")),
    };
    let fields: &[&str] = match kind {
        "master" => &[
            "basDt", "srtnCd", "isinCd", "mrktCtg", "itmsNm", "crno", "corpNm",
        ],
        "etf" => &["basDt", "srtnCd", "isinCd", "itmsNm", "clpr"],
        _ => &["basDt", "srtnCd", "itmsNm", "mrktCtg", "clpr", "mrktTotAmt"],
    };
    if items.iter().any(|row| {
        !row.is_null()
            && (!row.is_object()
                || fields.iter().any(|field| {
                    row.get(*field)
                        .is_some_and(|value| value.is_array() || value.is_object())
                }))
    }) {
        return Err(error("PUBLIC_DATA_API_REQUEST_FAILED"));
    }
    Ok((total, items))
}
async fn public_all(
    kind: &str,
    date: &str,
    market: Option<&str>,
    missing: &str,
) -> Result<Vec<Value>> {
    let (total, mut items) = public_page(kind, date, market, 1).await?;
    if total == 0 || items.is_empty() {
        return Ok(Vec::new());
    }
    for page in 2..=(total + 999) / 1000 {
        let (_, next) = public_page(kind, date, market, page).await?;
        if next.is_empty() {
            return Err(error(missing));
        }
        items.extend(next);
    }
    if items.len() < total as usize {
        return Err(error(missing));
    }
    Ok(items)
}

#[derive(Clone)]
struct Master {
    code: String,
    name: String,
    category: String,
    market: String,
    isin: Option<String>,
    date: String,
}
#[derive(Clone)]
struct Price {
    code: String,
    category: String,
    value: String,
}
fn us_market(raw: &str) -> Option<&'static str> {
    match trim(raw).to_uppercase().as_str() {
        "NASDAQ" => Some("NASDAQ"),
        "NYSE" => Some("NYSE"),
        "NYSE ARCA" | "NYSEARCA" | "ARCA" => Some("NYSE_ARCA"),
        "NYSE MKT" | "NYSE AMERICAN" | "AMEX" => Some("NYSE_AMERICAN"),
        "BATS" | "CBOE" => Some("BATS"),
        _ => None,
    }
}
fn decimal(value: &Value) -> Option<String> {
    let raw = if let Some(raw) = value.as_str() {
        trim(raw).to_owned()
    } else if value.is_number() {
        value.to_string()
    } else {
        return None;
    };
    let (sign, raw) = if let Some(raw) = raw.strip_prefix('-') {
        ("-", raw)
    } else {
        ("", raw.strip_prefix('+').unwrap_or(&raw))
    };
    let mut parts = raw.split(['e', 'E']);
    let mantissa = parts.next()?;
    let exponent = parts.next();
    if parts.next().is_some() {
        return None;
    }
    if let Some(e) = exponent {
        e.parse::<i32>().ok()?;
    }
    let (whole, fraction) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    if whole.is_empty() && fraction.is_empty()
        || !whole
            .bytes()
            .chain(fraction.bytes())
            .all(|b| b.is_ascii_digit())
    {
        return None;
    }
    let whole = whole.trim_start_matches('0');
    let whole = if whole.is_empty() { "0" } else { whole };
    let fraction = if mantissa.contains('.') {
        format!(".{}", if fraction.is_empty() { "0" } else { fraction })
    } else {
        String::new()
    };
    let exponent = exponent.map(|e| format!("e{e}")).unwrap_or_default();
    let normalized = format!("{sign}{whole}{fraction}{exponent}");
    serde_json::from_str::<serde_json::Number>(&normalized).ok()?;
    Some(normalized)
}
fn positive(value: &str) -> bool {
    !value.starts_with('-')
        && value
            .split(['e', 'E'])
            .next()
            .is_some_and(|v| v.bytes().any(|b| matches!(b, b'1'..=b'9')))
}
fn kr_master_entry(row: &Value, date: &str, etf: bool) -> Option<Master> {
    if !row.is_object() {
        return None;
    }
    let code = string(row, "srtnCd");
    let code = trim(&code).to_uppercase();
    let code = code.strip_prefix('A').unwrap_or(&code);
    let name = string(row, "itmsNm");
    let name = trim(&name);
    let isin = string(row, "isinCd");
    let isin = trim(&isin);
    if code.len() != 6
        || !code.bytes().all(|b| b.is_ascii_digit())
        || name.is_empty()
        || isin.is_empty()
        || basic_date(&string(row, "basDt")).as_deref() != Some(date)
    {
        return None;
    }
    let market = if etf {
        "KOSPI".to_owned()
    } else {
        let upper = name.to_uppercase();
        let preferred = upper.ends_with('우')
            || upper.chars().last().is_some_and(|last| {
                last.is_ascii_uppercase() && upper.chars().rev().nth(1) == Some('우')
            });
        if upper.contains("스팩") || upper.contains("SPAC") || upper.contains("우선주") || preferred
        {
            return None;
        }
        let market = trim(&string(row, "mrktCtg")).to_uppercase();
        if !matches!(
            market.as_str(),
            "KOSPI" | "KOSDAQ" | "NASDAQ" | "NYSE" | "NYSE_ARCA" | "NYSE_AMERICAN" | "BATS"
        ) {
            return None;
        }
        market
    };
    Some(Master {
        code: code.into(),
        name: name.into(),
        category: if etf { "ETF" } else { "STOCK" }.into(),
        market,
        isin: Some(isin.into()),
        date: date.into(),
    })
}
async fn kr_master(db: &Client) -> Outcome {
    let _guard = acquire(&KR_MASTER, "STOCK_SYNC_ALREADY_RUNNING")?;
    let today = today("Asia/Seoul", db).await?;
    for offset in 0..=10 {
        let date = shift(&today, -offset, db).await?;
        let items = public_all("master", &date, None, "STOCK_MASTER_DATA_NOT_FOUND").await?;
        if items.is_empty() {
            continue;
        }
        let etfs = public_all("etf", &date, None, "STOCK_MASTER_DATA_NOT_FOUND").await?;
        let mut entries = BTreeMap::new();
        for (etf, items) in [(false, items), (true, etfs)] {
            for row in items {
                if let Some(entry) = kr_master_entry(&row, &date, etf) {
                    entries.insert((entry.category.clone(), entry.code.clone()), entry);
                }
            }
        }
        if !entries.is_empty() {
            return persist_master(&date, entries.into_values().collect(), false, db).await;
        }
    }
    Err(error("STOCK_MASTER_DATA_NOT_FOUND"))
}
async fn us_master(db: &Client) -> Outcome {
    let _guard = acquire(&US_SYNC, "US_STOCK_SYNC_ALREADY_RUNNING")?;
    let date = today("America/New_York", db).await?;
    let rows = eodhd("exchange-symbol-list/US", None).await?;
    let mut entries = BTreeMap::new();
    for row in rows {
        let category = match string(&row, "Type").as_str() {
            "Common Stock" => "STOCK",
            "ETF" => "ETF",
            _ => continue,
        };
        let Some(market) = us_market(&string(&row, "Exchange")) else {
            continue;
        };
        let name = string(&row, "Name");
        let code = string(&row, "Code");
        let ticker = trim(&code).to_uppercase();
        if string(&row, "Currency") != "USD"
            || trim(&name).is_empty()
            || ticker.is_empty()
            || ticker.len() > 40
            || !ticker.as_bytes()[0].is_ascii_alphanumeric()
            || !ticker
                .bytes()
                .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || matches!(b, b'.' | b'-'))
        {
            return Err(error("US_STOCK_MASTER_DATA_NOT_FOUND"));
        }
        let isin = string(&row, "Isin");
        let isin = trim(&isin);
        let valid_isin = isin.len() == 12
            && isin.as_bytes()[..2].iter().all(|b| b.is_ascii_uppercase())
            && isin.as_bytes()[2..11]
                .iter()
                .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit())
            && isin.as_bytes()[11].is_ascii_digit();
        let entry = Master {
            code: format!("{ticker}.US"),
            name: trim(&name).into(),
            category: category.into(),
            market: market.into(),
            isin: valid_isin.then(|| isin.into()),
            date: date.clone(),
        };
        if entries.insert(entry.code.clone(), entry).is_some() {
            return Err(error("US_STOCK_MASTER_DATA_NOT_FOUND"));
        }
    }
    if !entries.values().any(|e| e.category == "STOCK")
        || !entries.values().any(|e| e.category == "ETF")
    {
        return Err(error("US_STOCK_MASTER_DATA_NOT_FOUND"));
    }
    persist_master(&date, entries.into_values().collect(), true, db).await
}
async fn end(result: Outcome, db: &Client) -> Outcome {
    if result.is_err() {
        let _ = db.batch_execute("ROLLBACK").await;
        return result;
    }
    if db.batch_execute("COMMIT").await.is_err() {
        let _ = db.batch_execute("ROLLBACK").await;
        return Err(internal());
    }
    result
}
async fn persist_master(date: &str, entries: Vec<Master>, us: bool, db: &Client) -> Outcome {
    if entries.iter().any(|entry| {
        if us {
            !matches!(
                entry.market.as_str(),
                "NASDAQ" | "NYSE" | "NYSE_ARCA" | "NYSE_AMERICAN" | "BATS"
            )
        } else {
            !matches!(entry.market.as_str(), "KOSPI" | "KOSDAQ")
        }
    }) {
        return Err(internal());
    }
    db.batch_execute("BEGIN; SELECT pg_advisory_xact_lock(7519001)")
        .await
        .map_err(|_| internal())?;
    let result=async {
        let scope=if us{format!("market IN {US}")}else{"(market IN ('KOSPI','KOSDAQ') OR market IS NULL)".into()};
        let records=db.query(&format!("SELECT id,category,asset_code,listed FROM assets WHERE category IN ('STOCK','ETF') AND {scope} FOR UPDATE"),&[]).await.map_err(|_|internal())?;
        let existing:HashMap<(String,String),(i64,bool)>=records.into_iter().map(|r|((r.get(1),r.get(2)),(r.get(0),r.get(3)))).collect();
        let mut synchronized=HashSet::new();let mut categories=HashSet::new();let mut created=0;let mut updated=0;
        for entry in &entries {
            let key=(entry.category.clone(),entry.code.clone());synchronized.insert(key.clone());categories.insert(entry.category.clone());
            if let Some((aid,_))=existing.get(&key) {
                updated+=db.execute("UPDATE assets SET name=$2,market=$3,isin_code=$4,listed=true,stock_base_date=$5::text::date,updated_at=clock_timestamp() WHERE id=$1 AND (name,market,isin_code,listed,stock_base_date) IS DISTINCT FROM ($2::varchar,$3::varchar,$4::varchar,true,$5::text::date)",&[aid,&entry.name,&entry.market,&entry.isin,&entry.date]).await.map_err(|_|internal())?;
            }else{
                db.execute("INSERT INTO assets(name,category,asset_code,market,isin_code,listed,stock_base_date,created_at,updated_at) VALUES($1,$2,$3,$4,$5,true,$6::text::date,clock_timestamp(),clock_timestamp())",&[&entry.name,&entry.category,&entry.code,&entry.market,&entry.isin,&entry.date]).await.map_err(|_|internal())?;created+=1;
            }
        }
        let mut delisted=0;for ((category,code),(aid,listed)) in existing{if listed&&categories.contains(&category)&&!synchronized.contains(&(category,code)){delisted+=db.execute("UPDATE assets SET listed=false,updated_at=clock_timestamp() WHERE id=$1",&[&aid]).await.map_err(|_|internal())?;}}
        Ok((200,json!({"baseDate":date,"syncedCount":entries.len(),"createdCount":created,"updatedCount":updated,"delistedCount":delisted})))
    }.await;
    end(result, db).await
}

async fn persist_prices(date: &str, entries: &[Price], us: bool, db: &Client) -> Outcome {
    db.batch_execute("BEGIN; SELECT pg_advisory_xact_lock(7519002)")
        .await
        .map_err(|_| internal())?;
    let result=async {
        let scope=if us{format!("market IN {US}")}else{"(market IN ('KOSPI','KOSDAQ') OR market IS NULL)".into()};
        let listed=db.query(&format!("SELECT id,category,asset_code FROM assets WHERE listed=true AND category IN ('STOCK','ETF') AND {scope}"),&[]).await.map_err(|_|internal())?;
        let assets:HashMap<(String,String),i64>=listed.into_iter().map(|r|((r.get(1),r.get(2)),r.get(0))).collect();
        let mut created=0u64;let mut updated=0u64;let mut skipped=0u64;
        for entry in entries {
            let Some(aid)=assets.get(&(entry.category.clone(),entry.code.clone()))else{skipped+=1;continue;};
            let previous=db.query_opt("SELECT id FROM stock_daily_prices WHERE asset_id=$1 AND base_date=$2::text::date FOR UPDATE",&[aid,&date]).await.map_err(|_|internal())?;
            if let Some(previous)=previous {
                let id:i64=previous.get(0);
                let changed=db.execute("UPDATE stock_daily_prices SET close_price=$2::text::numeric,updated_at=clock_timestamp() WHERE id=$1 AND close_price<>$2::text::numeric",&[&id,&entry.value]).await.map_err(|_|internal())?;
                if changed>0{updated+=1;}else{skipped+=1;}
            }else{
                db.execute("INSERT INTO stock_daily_prices(asset_id,base_date,close_price,created_at,updated_at) VALUES($1,$2::text::date,$3::text::numeric,clock_timestamp(),clock_timestamp())",&[aid,&date,&entry.value]).await.map_err(|_|internal())?;created+=1;
            }
        }
        if !us {
            // Never infer a closure from missing prices. A successful complete
            // provider snapshot marks an existing trading day only after close.
            db.execute("UPDATE market_trading_days SET collected_at=clock_timestamp(),updated_at=clock_timestamp() WHERE base_date=$1::text::date AND trading=true AND clock_timestamp()>=((base_date+time '15:30') AT TIME ZONE 'Asia/Seoul')",&[&date]).await.map_err(|_|internal())?;
        }
        Ok((200,json!({"baseDate":date,"receivedCount":entries.len(),"createdCount":created,"updatedCount":updated,"skippedCount":skipped,"synchronizedDateCount":1,"pendingDateCount":0,"failedDateCount":0})))
    }.await;
    let result = end(result, db).await;
    if result.is_ok()
        && !us
        && crate::service_portfolio::refresh_latest_snapshots(db)
            .await
            .is_err()
    {
        eprintln!("event=portfolio.price_sync_snapshot_hook_failed");
    }
    result
}
async fn us_prices(raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let requested = params.get("date").filter(|v| !v.is_empty());
    if requested.is_some_and(|date| !date_valid(date)) {
        return Err(invalid("date", "타입이 올바르지 않습니다."));
    }
    let today = today("America/New_York", db).await?;
    if requested.is_some_and(|date| date >= &today) {
        return Err(error("INVALID_US_STOCK_PRICE_DATE"));
    }
    let _guard = acquire(&US_SYNC, "US_STOCK_SYNC_ALREADY_RUNNING")?;
    let listed=db.query(&format!("SELECT asset_code,category FROM assets WHERE listed=true AND category IN ('STOCK','ETF') AND market IN {US}"),&[]).await.map_err(|_|internal())?;
    let assets: HashMap<String, String> =
        listed.into_iter().map(|r| (r.get(0), r.get(1))).collect();
    if assets.is_empty() {
        return Err(error("US_STOCK_MASTER_REQUIRED"));
    }
    let first = if let Some(date) = requested {
        date.clone()
    } else {
        shift(&today, -1, db).await?
    };
    for offset in 0..if requested.is_some() { 1 } else { 10 } {
        let date = shift(&first, -offset, db).await?;
        let items = eodhd("eod-bulk-last-day/US", Some(&date)).await?;
        if items.is_empty() {
            continue;
        }
        let mut entries = BTreeMap::new();
        for row in items {
            // Record decoding happens before universe filtering in Java.
            let row_date = match row.get("date") {
                None | Some(Value::Null) => None,
                Some(Value::String(value)) if date_valid(value) => Some(value.as_str()),
                _ => return Err(error("EODHD_API_REQUEST_FAILED")),
            };
            let price = match row.get("close") {
                None | Some(Value::Null) => None,
                Some(value) => {
                    Some(decimal(value).ok_or_else(|| error("EODHD_API_REQUEST_FAILED"))?)
                }
            };
            let code = string(&row, "code");
            if trim(&code).is_empty() {
                continue;
            }
            let code = format!("{}.US", trim(&code).to_uppercase());
            let Some(category) = assets.get(&code) else {
                continue;
            };
            if row_date != Some(date.as_str()) {
                return Err(error("US_STOCK_PRICE_DATA_NOT_FOUND"));
            }
            let Some(price) = price.filter(|value| positive(value)) else {
                continue;
            };
            let entry = Price {
                code: code.clone(),
                category: category.clone(),
                value: price,
            };
            if entries.insert(code, entry).is_some() {
                return Err(error("US_STOCK_PRICE_DATA_NOT_FOUND"));
            }
        }
        if entries.is_empty() {
            return Err(error("US_STOCK_PRICE_DATA_NOT_FOUND"));
        }
        return persist_prices(&date, &entries.into_values().collect::<Vec<_>>(), true, db).await;
    }
    Err(error("US_STOCK_PRICE_DATA_NOT_FOUND"))
}
fn kr_price_entry(row: &Value, date: &str, category: &str) -> Option<Price> {
    let code = string(row, "srtnCd");
    let code = trim(&code);
    if code.len() != 6
        || !code.bytes().all(|b| b.is_ascii_digit())
        || basic_date(&string(row, "basDt")).as_deref() != Some(date)
    {
        return None;
    }
    let value = decimal(row.get("clpr")?)?;
    if !positive(&value) {
        return None;
    }
    Some(Price {
        code: code.into(),
        category: category.into(),
        value,
    })
}
async fn kr_snapshot(date: &str) -> Result<Option<Vec<Price>>> {
    let mut items = Vec::new();
    for market in ["KOSPI", "KOSDAQ"] {
        let records =
            public_all("prices", date, Some(market), "STOCK_PRICE_DATA_NOT_FOUND").await?;
        if records.is_empty() {
            return Ok(None);
        }
        items.extend(records);
    }
    let etfs = public_all("etf", date, None, "STOCK_PRICE_DATA_NOT_FOUND").await?;
    if etfs.is_empty() {
        return Ok(None);
    }
    let mut entries = BTreeMap::new();
    for (category, items) in [("STOCK", items), ("ETF", etfs)] {
        for row in items {
            if let Some(entry) = kr_price_entry(&row, date, category) {
                entries.insert((entry.category.clone(), entry.code.clone()), entry);
            }
        }
    }
    Ok((!entries.is_empty()).then(|| entries.into_values().collect()))
}
async fn kr_backfill(raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let from = params
        .get("from")
        .ok_or_else(|| invalid("from", "필수 요청 파라미터입니다."))?;
    let to = params
        .get("to")
        .ok_or_else(|| invalid("to", "필수 요청 파라미터입니다."))?;
    for (key, value) in [("from", from), ("to", to)] {
        if !date_valid(value) {
            return Err(invalid(key, "타입이 올바르지 않습니다."));
        }
    }
    let valid: bool = db
        .query_one(
            "SELECT $1::text::date<=$2::text::date AND $2::text::date-$1::text::date<=30",
            &[&from, &to],
        )
        .await
        .map_err(|_| internal())?
        .get(0);
    if !valid {
        return Err(error("INVALID_STOCK_PRICE_BACKFILL_RANGE"));
    }
    let _guard = acquire(&KR_PRICES, "STOCK_PRICE_SYNC_ALREADY_RUNNING")?;
    let dates=db.query("SELECT day::date::text FROM generate_series($1::text::date,$2::text::date,interval '1 day') day",&[&from,&to]).await.map_err(|_|internal())?;
    let mut totals = [0u64; 4];
    let mut synchronized = 0;
    for record in dates {
        let date: String = record.get(0);
        let Some(entries) = kr_snapshot(&date).await? else {
            continue;
        };
        let (_, result) = persist_prices(&date, &entries, false, db).await?;
        for (index, key) in [
            "receivedCount",
            "createdCount",
            "updatedCount",
            "skippedCount",
        ]
        .iter()
        .enumerate()
        {
            totals[index] += result[key].as_u64().ok_or_else(internal)?;
        }
        synchronized += 1;
    }
    Ok((
        200,
        json!({"from":from,"to":to,"synchronizedDateCount":synchronized,"receivedCount":totals[0],"createdCount":totals[1],"updatedCount":totals[2],"skippedCount":totals[3]}),
    ))
}
async fn pending_dates(db: &Client) -> Result<i64> {
    Ok(db.query_one("SELECT count(*) FROM market_trading_days WHERE trading=true AND collected_at IS NULL AND base_date<=(clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date",&[]).await.map_err(|_|internal())?.get(0))
}
async fn kr_price_sync(db: &Client) -> Outcome {
    let _guard = acquire(&KR_PRICES, "STOCK_PRICE_SYNC_ALREADY_RUNNING")?;
    let dates=db.query(r#"
        WITH calendar AS (
          SELECT base_date,collected_at,last_attempted_at,lead(base_date) OVER(ORDER BY base_date) next_date
          FROM market_trading_days WHERE trading=true AND base_date<=(clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date
        ), eligible AS (
          SELECT * FROM calendar WHERE collected_at IS NULL AND next_date IS NOT NULL
          AND (clock_timestamp() AT TIME ZONE 'Asia/Seoul')>=(next_date+time '13:00')
        ) SELECT base_date::text FROM eligible ORDER BY
          CASE WHEN base_date=(SELECT max(base_date) FROM eligible) THEN 0 ELSE 1 END,
          last_attempted_at ASC NULLS FIRST,base_date DESC LIMIT 10
        "#,&[]).await.map_err(|_|internal())?;
    if dates.is_empty() {
        let row=db.query_one("SELECT max(base_date)::text FROM market_trading_days WHERE trading=true AND collected_at IS NOT NULL AND base_date<=(clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date",&[]).await.map_err(|_|internal())?;
        let base: Option<String> = row.get(0);
        return Ok((
            200,
            json!({"baseDate":base,"receivedCount":0,"createdCount":0,"updatedCount":0,"skippedCount":0,"synchronizedDateCount":0,"pendingDateCount":pending_dates(db).await?,"failedDateCount":0}),
        ));
    }
    let selected = dates.len();
    let mut snapshots = BTreeMap::new();
    let mut first_error = None;
    for record in dates {
        let date: String = record.get(0);
        let result = kr_snapshot(&date).await;
        db.execute("UPDATE market_trading_days SET last_attempted_at=clock_timestamp(),updated_at=clock_timestamp() WHERE base_date=$1::text::date",&[&date]).await.map_err(|_|internal())?;
        match result {
            Ok(Some(entries)) => {
                snapshots.insert(date, entries);
            }
            Ok(None) => {}
            Err(error) => {
                if first_error.is_none() {
                    first_error = Some(error);
                }
            }
        }
    }
    if snapshots.is_empty() {
        return Err(first_error.unwrap_or_else(|| error("STOCK_PRICE_DATA_NOT_FOUND")));
    }
    let mut failed = selected - snapshots.len();
    let mut totals = [0u64; 4];
    let mut synchronized = 0;
    let mut latest = None;
    let mut persistence_error = None;
    for (date, entries) in snapshots {
        match persist_prices(&date, &entries, false, db).await {
            Ok((_, result)) => {
                for (index, key) in [
                    "receivedCount",
                    "createdCount",
                    "updatedCount",
                    "skippedCount",
                ]
                .iter()
                .enumerate()
                {
                    totals[index] += result[key].as_u64().ok_or_else(internal)?;
                }
                synchronized += 1;
                latest = Some(date);
            }
            Err(error) => {
                failed += 1;
                if persistence_error.is_none() {
                    persistence_error = Some(error);
                }
            }
        }
    }
    let latest = latest.ok_or_else(|| persistence_error.unwrap_or_else(internal))?;
    Ok((
        200,
        json!({"baseDate":latest,"receivedCount":totals[0],"createdCount":totals[1],"updatedCount":totals[2],"skippedCount":totals[3],"synchronizedDateCount":synchronized,"pendingDateCount":pending_dates(db).await?,"failedDateCount":failed}),
    ))
}
