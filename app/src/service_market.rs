//! Public securities, stored FX quotes and exact-decimal portfolio valuation.
//! Monetary arithmetic is delegated to PostgreSQL NUMERIC, never binary floats.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query, rows};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};
use tokio_postgres::Client;

const US: &str = "('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS')";

pub async fn handle(
    method: &str,
    path: &str,
    raw_query: &str,
    body: &[u8],
    db: &Client,
) -> Option<Outcome> {
    if path == "/api/stocks" {
        return Some(if method == "GET" {
            search(raw_query, db).await
        } else {
            Err(fault(
                405,
                "METHOD_NOT_ALLOWED",
                "지원하지 않는 HTTP 메서드입니다.",
            ))
        });
    }
    if let Some(id) = path
        .strip_prefix("/api/stocks/")
        .and_then(|p| p.strip_suffix("/price"))
        && !id.contains('/')
    {
        return Some(if method == "GET" {
            latest(id, db).await
        } else {
            Err(fault(
                405,
                "METHOD_NOT_ALLOWED",
                "지원하지 않는 HTTP 메서드입니다.",
            ))
        });
    }
    if path == "/api/exchange-rates/usd-krw" {
        return Some(if method == "GET" {
            quote(raw_query, db).await
        } else {
            Err(fault(
                405,
                "METHOD_NOT_ALLOWED",
                "지원하지 않는 HTTP 메서드입니다.",
            ))
        });
    }
    if path == "/api/portfolio/calculate" {
        return Some(if method == "POST" {
            calculate(body, db).await
        } else {
            Err(fault(
                405,
                "METHOD_NOT_ALLOWED",
                "지원하지 않는 HTTP 메서드입니다.",
            ))
        });
    }
    None
}

async fn search(raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let keyword = params.get("q").map(String::as_str).unwrap_or("");
    if keyword.trim().is_empty() {
        return Err(invalid("q", "검색어를 입력해주세요."));
    }
    if keyword.encode_utf16().count() > 50 {
        return Err(invalid("q", "검색어는 50자 이하여야 합니다."));
    }
    if !keyword.chars().any(char::is_alphanumeric) {
        return Err(invalid("q", "올바른 검색어를 입력해주세요."));
    }
    let country = params
        .get("country")
        .filter(|v| !v.is_empty())
        .map(String::as_str)
        .unwrap_or("KR");
    if !matches!(country, "KR" | "US") {
        return Err(invalid("country", "국가는 KR 또는 US여야 합니다."));
    }
    let keyword = keyword
        .trim()
        .replace('!', "!!")
        .replace('%', "!%")
        .replace('_', "!_");
    let markets = if country == "KR" {
        "('KOSPI','KOSDAQ')"
    } else {
        US
    };
    let sql = format!(
        "SELECT json_build_object('assetId',id,'assetCode',asset_code,'name',name,'category',category,'market',market,'currency',CASE WHEN market IN {US} THEN 'USD' ELSE 'KRW' END)::text FROM assets WHERE listed=true AND category IN ('STOCK','ETF') AND market IN {markets} AND (lower(name) LIKE '%'||lower($1)||'%' ESCAPE '!' OR lower(asset_code) LIKE '%'||lower($1)||'%' ESCAPE '!') ORDER BY CASE WHEN lower(asset_code)=lower($1) THEN 0 WHEN lower(name)=lower($1) THEN 1 WHEN lower(asset_code) LIKE lower($1)||'%' ESCAPE '!' THEN 2 WHEN lower(name) LIKE lower($1)||'%' ESCAPE '!' THEN 3 ELSE 4 END,name,id LIMIT 20"
    );
    Ok((200, json!({"stocks":rows(db,&sql,&[&keyword]).await?})))
}

async fn latest(raw_id: &str, db: &Client) -> Outcome {
    let id = crate::api::path_integer(raw_id)
        .ok_or_else(|| invalid("assetId", "타입이 올바르지 않습니다."))?;
    let sql = format!(
        "SELECT json_build_object('assetId',a.id,'assetCode',a.asset_code,'name',a.name,'baseDate',p.base_date,'closePrice',p.close_price,'currency',CASE WHEN a.market IN {US} THEN 'USD' ELSE 'KRW' END)::text FROM assets a JOIN stock_daily_prices p ON p.asset_id=a.id WHERE a.id=$1 ORDER BY p.base_date DESC LIMIT 1"
    );
    let mut values = rows(db, &sql, &[&id]).await?;
    values.pop().map(|v| (200, v)).ok_or_else(|| {
        fault(
            404,
            "STOCK_PRICE_NOT_FOUND",
            "주식·ETF 종가를 찾을 수 없습니다.",
        )
    })
}

fn valid_date(date: &str) -> bool {
    let bytes = date.as_bytes();
    if bytes.len() != 10
        || bytes[4] != b'-'
        || bytes[7] != b'-'
        || bytes
            .iter()
            .enumerate()
            .any(|(i, b)| i != 4 && i != 7 && !b.is_ascii_digit())
    {
        return false;
    }
    let Ok(y) = date[..4].parse::<u32>() else {
        return false;
    };
    let Ok(m) = date[5..7].parse::<usize>() else {
        return false;
    };
    let Ok(d) = date[8..].parse::<u32>() else {
        return false;
    };
    let days = [
        31,
        if y % 400 == 0 || (y % 4 == 0 && y % 100 != 0) {
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

fn acquire_quote_budget() -> Result<(), ApiFault> {
    static REQUESTS: OnceLock<Mutex<VecDeque<Instant>>> = OnceLock::new();
    let mut requests = REQUESTS
        .get_or_init(|| Mutex::new(VecDeque::new()))
        .lock()
        .map_err(|_| internal())?;
    let now = Instant::now();
    while requests
        .front()
        .is_some_and(|t| now.duration_since(*t) >= Duration::from_secs(60))
    {
        requests.pop_front();
    }
    if requests.len() >= 120 {
        return Err(fault(
            429,
            "EXCHANGE_RATE_RATE_LIMITED",
            "환율 조회 요청이 많습니다. 잠시 후 다시 시도해 주세요.",
        ));
    }
    requests.push_back(now);
    Ok(())
}

async fn quote(raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let date = params
        .get("date")
        .ok_or_else(|| invalid("date", "필수 요청 파라미터입니다."))?;
    if !valid_date(date) {
        return Err(invalid("date", "타입이 올바르지 않습니다."));
    }
    acquire_quote_budget()?;
    let boundary=rows(db,"SELECT json_build_object('valid',$1::text::date>=DATE '2000-01-01' AND $1::text::date<=(now() AT TIME ZONE 'Asia/Seoul')::date)::text",&[&date]).await?;
    if boundary.first().and_then(|v| v["valid"].as_bool()) != Some(true) {
        return Err(fault(
            400,
            "INVALID_EXCHANGE_RATE_DATE",
            "환율 조회일은 2000-01-01부터 오늘까지여야 합니다.",
        ));
    }
    load_quote(date, db).await.map(|value| (200, value))
}

fn provider_failed() -> ApiFault {
    fault(
        502,
        "EODHD_API_REQUEST_FAILED",
        "EODHD API 요청에 실패했습니다.",
    )
}

fn rate_unavailable() -> ApiFault {
    fault(
        503,
        "EXCHANGE_RATE_UNAVAILABLE",
        "해당 날짜의 USD/KRW 환율을 가져오지 못했습니다.",
    )
}

fn unavailable_dates() -> &'static Mutex<HashMap<String, Instant>> {
    static CACHE: OnceLock<Mutex<HashMap<String, Instant>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

// Decode exact decimal text accepted by Java BigDecimal without binary floats.
fn decimal_number(raw: &str) -> Option<Value> {
    let raw = raw.trim();
    let (negative, raw) = if let Some(raw) = raw.strip_prefix('-') {
        ("-", raw)
    } else {
        ("", raw.strip_prefix('+').unwrap_or(raw))
    };
    let mut parts = raw.split(['e', 'E']);
    let mantissa = parts.next()?;
    let exponent = parts.next();
    if parts.next().is_some() {
        return None;
    }
    if let Some(exponent) = exponent {
        exponent.parse::<i32>().ok()?;
    }
    let (whole, fraction) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    if whole.is_empty() && fraction.is_empty() {
        return None;
    }
    if !whole
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
    let exponent = exponent
        .map(|value| format!("e{value}"))
        .unwrap_or_default();
    let value: Value =
        serde_json::from_str(&format!("{negative}{whole}{fraction}{exponent}")).ok()?;
    value.is_number().then_some(value)
}

pub(crate) async fn load_quote(date: &str, db: &Client) -> Result<Value, ApiFault> {
    load_quote_with_refresh(date, false, db).await
}

pub(crate) async fn refresh_quote(date: &str, db: &Client) -> Result<Value, ApiFault> {
    load_quote_with_refresh(date, true, db).await
}

async fn load_quote_with_refresh(
    date: &str,
    refresh: bool,
    db: &Client,
) -> Result<Value, ApiFault> {
    if !valid_date(date) {
        return Err(fault(
            400,
            "INVALID_EXCHANGE_RATE_DATE",
            "환율 조회일은 2000-01-01부터 오늘까지여야 합니다.",
        ));
    }
    let bounds = rows(db, "SELECT json_build_object('valid',$1::text::date>=DATE '2000-01-01' AND $1::text::date<=(now() AT TIME ZONE 'Asia/Seoul')::date,'through',least($1::text::date,(now() AT TIME ZONE 'America/New_York')::date-1),'from',least($1::text::date,(now() AT TIME ZONE 'America/New_York')::date-1)-14)::text", &[&date]).await?;
    let boundary = bounds.first().ok_or_else(internal)?;
    if boundary["valid"].as_bool() != Some(true) {
        return Err(fault(
            400,
            "INVALID_EXCHANGE_RATE_DATE",
            "환율 조회일은 2000-01-01부터 오늘까지여야 합니다.",
        ));
    }
    let sql = "SELECT json_build_object('requestedDate',requested_date,'baseDate',base_date,'rate',rate,'baseCurrency','USD','quoteCurrency','KRW')::text FROM usd_krw_rates WHERE requested_date=$1::text::date AND (requested_date<(fetched_at AT TIME ZONE 'America/New_York')::date-1 OR fetched_at>now()-INTERVAL '6 hours')";
    if !refresh && let Some(value) = rows(db, sql, &[&date]).await?.pop() {
        return Ok(value);
    }
    if !refresh
        && unavailable_dates()
            .lock()
            .map_err(|_| internal())?
            .get(date)
            .is_some_and(|until| *until > Instant::now())
    {
        return Err(rate_unavailable());
    }
    let token = std::env::var("EODHD_API_TOKEN").unwrap_or_default();
    if token.trim().is_empty() {
        return Err(fault(
            503,
            "EODHD_API_NOT_CONFIGURED",
            "EODHD API 키가 설정되지 않았습니다.",
        ));
    }
    // Explicit override permits a local HTTP fixture. Production defaults to HTTPS.
    let base =
        std::env::var("EODHD_BASE_URL").unwrap_or_else(|_| "https://eodhd.com/api".to_owned());
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(3))
        .read_timeout(Duration::from_secs(60))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| provider_failed())?;
    // Errors can contain the token-bearing URL: discard them without logging.
    let response = client
        .get(format!("{}/eod/USDKRW.FOREX", base.trim_end_matches('/')))
        .query(&[
            ("api_token", token.as_str()),
            ("fmt", "json"),
            ("from", boundary["from"].as_str().ok_or_else(internal)?),
            ("to", boundary["through"].as_str().ok_or_else(internal)?),
        ])
        .send()
        .await
        .map_err(|_| provider_failed())?
        .error_for_status()
        .map_err(|_| provider_failed())?;
    let payload: Value = response.json().await.map_err(|_| provider_failed())?;
    let entries = payload.as_array().ok_or_else(provider_failed)?;
    let mut candidates = Vec::new();
    for row in entries {
        if !row.is_object() {
            return Err(provider_failed());
        }
        let row_date = match row.get("date") {
            None | Some(Value::Null) => continue,
            Some(Value::String(value)) if valid_date(value) => value,
            _ => return Err(provider_failed()),
        };
        let number = match row.get("close") {
            None | Some(Value::Null) => continue,
            Some(value) if value.is_number() => value.clone(),
            Some(Value::String(value)) => decimal_number(value).ok_or_else(provider_failed)?,
            _ => return Err(provider_failed()),
        };
        candidates.push(json!({"date":row_date,"close":number}));
    }
    let encoded = Value::Array(candidates).to_string();
    let selected = rows(db, "SELECT json_build_object('date',r->>'date','rate',(r->>'close')::numeric)::text FROM jsonb_array_elements($1::text::jsonb) r WHERE (r->>'date')::date BETWEEN $2::text::date AND $3::text::date AND (r->>'close')::numeric>0 ORDER BY r->>'date' DESC LIMIT 1", &[&encoded,&boundary["from"].as_str().ok_or_else(internal)?,&boundary["through"].as_str().ok_or_else(internal)?]).await?;
    let Some(selected) = selected.first() else {
        let mut unavailable = unavailable_dates().lock().map_err(|_| internal())?;
        let now = Instant::now();
        unavailable.retain(|_, until| *until > now);
        if unavailable.len() >= 1024 {
            unavailable.clear();
        }
        unavailable.insert(date.to_owned(), now + Duration::from_secs(6 * 60 * 60));
        return Err(rate_unavailable());
    };
    let base_date = selected["date"].as_str().ok_or_else(internal)?;
    let rate = selected["rate"].to_string();
    let result = rows(db, "INSERT INTO usd_krw_rates (requested_date,base_date,rate,fetched_at) VALUES ($1::text::date,$2::text::date,round($3::text::numeric,6),now()) ON CONFLICT (requested_date) DO UPDATE SET base_date=EXCLUDED.base_date,rate=EXCLUDED.rate,fetched_at=EXCLUDED.fetched_at RETURNING json_build_object('requestedDate',requested_date,'baseDate',base_date,'rate',rate,'baseCurrency','USD','quoteCurrency','KRW')::text", &[&date,&base_date,&rate]).await?;
    unavailable_dates()
        .lock()
        .map_err(|_| internal())?
        .remove(date);
    result.into_iter().next().ok_or_else(internal)
}

fn decimal_constraints(value: &Value) -> Option<(bool, bool)> {
    let text = value.as_number()?.to_string();
    let negative = text.starts_with('-');
    let mut parts = text.trim_start_matches(['-', '+']).split(['e', 'E']);
    let mantissa = parts.next()?;
    let exponent = parts
        .next()
        .map(|s| s.parse::<i64>().ok())
        .unwrap_or(Some(0))?;
    let (whole, fraction) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    let digits = format!("{whole}{fraction}");
    let significant = digits.trim_start_matches('0');
    let precision = significant.len().max(1) as i64;
    let scale = (fraction.len() as i64).saturating_sub(exponent);
    let integer_digits = precision.saturating_sub(scale);
    Some((
        negative || significant.is_empty() || integer_digits < -1,
        integer_digits > 15 || scale > 2,
    ))
}

fn validate_calculation(body: &[u8]) -> Result<Value, ApiFault> {
    let mut req: Value = serde_json::from_slice(body)
        .map_err(|_| invalid("requestBody", "요청 본문을 읽을 수 없습니다."))?;
    if !req.is_object() {
        return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
    }
    // Jackson's BigDecimal binding accepts decimal strings as well as numbers.
    // Normalize using serde's arbitrary-precision representation, never f64.
    if let Some(holdings) = req.get_mut("holdings").and_then(Value::as_array_mut) {
        for holding in holdings {
            if let Some(price) = holding.get_mut("averagePurchasePrice")
                && let Some(raw) = price.as_str()
            {
                *price = decimal_number(raw)
                    .ok_or_else(|| invalid("requestBody", "요청 본문을 읽을 수 없습니다."))?;
            }
        }
    }
    let Some(holdings) = req.get("holdings").and_then(Value::as_array) else {
        if req.get("holdings").is_some_and(|v| !v.is_null()) {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        }
        return Err(invalid("holdings", "보유자산을 한 개 이상 입력해주세요."));
    };
    let mut errors = vec![];
    if holdings.is_empty() {
        errors.push(json!({"field":"holdings","reason":"보유자산을 한 개 이상 입력해주세요."}));
    }
    if holdings.len() > 50 {
        errors.push(
            json!({"field":"holdings","reason":"보유자산은 최대 50개까지 계산할 수 있습니다."}),
        );
    }
    let mut ids = HashSet::new();
    let mut duplicate = false;
    for (i, h) in holdings.iter().enumerate() {
        if h.is_null() {
            errors.push(
                json!({"field":format!("holdings[{i}]"),"reason":"보유자산 정보를 입력해주세요."}),
            );
            continue;
        }
        if !h.is_object()
            || ["assetId", "quantity"].iter().any(|k| {
                h.get(k)
                    .is_some_and(|v| !v.is_null() && v.as_i64().is_none())
            })
            || h.get("averagePurchasePrice")
                .is_some_and(|v| !v.is_null() && !v.is_number())
        {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        }
        for (key, missing, positive) in [
            (
                "assetId",
                "종목 ID를 입력해주세요.",
                "종목 ID는 1 이상이어야 합니다.",
            ),
            (
                "quantity",
                "보유 수량을 입력해주세요.",
                "보유 수량은 1 이상이어야 합니다.",
            ),
        ] {
            let reason = match h[key].as_i64() {
                None => Some(missing),
                Some(x) if x <= 0 => Some(positive),
                _ => None,
            };
            if let Some(reason) = reason {
                errors.push(json!({"field":format!("holdings[{i}].{key}"),"reason":reason}));
            }
        }
        if let Some(id) = h["assetId"].as_i64()
            && !ids.insert(id)
        {
            duplicate = true;
        }
        let price = &h["averagePurchasePrice"];
        if price.is_null() {
            errors.push(json!({"field":format!("holdings[{i}].averagePurchasePrice"),"reason":"평균 매수가를 입력해주세요."}));
        } else if let Some((below, digits)) = decimal_constraints(price) {
            if below {
                errors.push(json!({"field":format!("holdings[{i}].averagePurchasePrice"),"reason":"평균 매수가는 0보다 커야 합니다."}));
            }
            if digits {
                errors.push(json!({"field":format!("holdings[{i}].averagePurchasePrice"),"reason":"평균 매수가는 정수 15자리, 소수 2자리 이하여야 합니다."}));
            }
        } else {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        }
    }
    if !errors.is_empty() {
        return Err(ApiFault {
            status: 400,
            body: json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":errors}),
        });
    }
    if duplicate {
        return Err(fault(
            400,
            "DUPLICATE_PORTFOLIO_ASSET",
            "포트폴리오에 중복된 종목이 있습니다.",
        ));
    }
    Ok(req)
}

pub(crate) async fn calculate(body: &[u8], db: &Client) -> Outcome {
    calculate_request(validate_calculation(body)?, db).await
}

// Saved holdings already satisfy ledger constraints. Public request size/price
// limits do not constrain a member's accumulated portfolio.
pub(crate) async fn calculate_saved(holdings: Vec<Value>, db: &Client) -> Outcome {
    calculate_request(json!({"holdings":holdings}), db).await
}

async fn calculate_request(request: Value, db: &Client) -> Outcome {
    let req = request.to_string();
    let dates = rows(db, "SELECT DISTINCT to_json(p.base_date::text)::text FROM jsonb_array_elements($1::text::jsonb->'holdings') h JOIN assets a ON a.id=(h->>'assetId')::bigint CROSS JOIN LATERAL (SELECT base_date FROM stock_daily_prices WHERE asset_id=a.id ORDER BY base_date DESC LIMIT 2) p WHERE a.market IN ('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS') ORDER BY 1", &[&req]).await?;
    for date in dates {
        if let Err(error) = load_quote(date.as_str().ok_or_else(internal)?, db).await
            && error.body["code"] != "EXCHANGE_RATE_UNAVAILABLE"
        {
            return Err(error);
        }
    }
    let mut result = rows(db, CALCULATE_SQL, &[&req]).await?;
    let mut value = result.pop().ok_or_else(internal)?;
    let missing = value
        .get("_missingAsset")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    if value.get("_invalidRateDate").and_then(Value::as_bool) == Some(true) {
        return Err(fault(
            400,
            "INVALID_EXCHANGE_RATE_DATE",
            "환율 조회일은 2000-01-01부터 오늘까지여야 합니다.",
        ));
    }
    if missing {
        return Err(fault(404, "ASSET_NOT_FOUND", "자산을 찾을 수 없습니다."));
    }
    if let Some(obj) = value.as_object_mut() {
        obj.remove("_missingAsset");
        obj.remove("_invalidRateDate");
    }
    Ok((200, value))
}

const CALCULATE_SQL: &str = r#"
WITH input AS (
 SELECT (h->>'assetId')::bigint AS aid,(h->>'quantity')::bigint AS qty,
 (h->>'averagePurchasePrice')::numeric AS avg,ord
 FROM jsonb_array_elements($1::text::jsonb->'holdings') WITH ORDINALITY AS x(h,ord)
), prices AS (
 SELECT i.*,a.id,a.asset_code,a.name,a.category,a.market,
 a.market IN ('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS') AS usd,
 p.base_date AS cdate,p.close_price AS close,p2.base_date AS pdate,p2.close_price AS pclose
 FROM input i LEFT JOIN assets a ON a.id=i.aid
 LEFT JOIN LATERAL (SELECT base_date,close_price FROM stock_daily_prices WHERE asset_id=i.aid ORDER BY base_date DESC LIMIT 1) p ON true
 LEFT JOIN LATERAL (SELECT base_date,close_price FROM stock_daily_prices WHERE asset_id=i.aid ORDER BY base_date DESC OFFSET 1 LIMIT 1) p2 ON true
), converted AS (
 SELECT p.*,CASE WHEN coalesce(usd,false) THEN close*r.rate ELSE close END AS current_krw,
 CASE WHEN coalesce(usd,false) THEN pclose*r2.rate ELSE pclose END AS previous_krw
 FROM prices p
 LEFT JOIN usd_krw_rates r ON r.requested_date=p.cdate AND (r.requested_date<(r.fetched_at AT TIME ZONE 'America/New_York')::date-1 OR r.fetched_at>now()-INTERVAL '6 hours')
 LEFT JOIN usd_krw_rates r2 ON r2.requested_date=p.pdate AND (r2.requested_date<(r2.fetched_at AT TIME ZONE 'America/New_York')::date-1 OR r2.fetched_at>now()-INTERVAL '6 hours')
), amounts AS (
 SELECT *,round(avg*qty,2) AS purchase,round(current_krw*qty,2) AS evaluation,
 CASE WHEN current_krw IS NOT NULL THEN cdate ELSE NULL END AS priced_date
 FROM converted
), holding AS (
 SELECT *,round(evaluation-purchase,2) AS profit,
 CASE WHEN current_krw IS NULL THEN NULL WHEN purchase=0 THEN 0.00 ELSE round((evaluation-purchase)*100/purchase,2) END AS return_rate
 FROM amounts
), totals AS (
 SELECT bool_or(id IS NULL) AS missing,
 bool_or(coalesce(usd,false) AND (cdate<DATE '2000-01-01' OR cdate>(now() AT TIME ZONE 'Asia/Seoul')::date OR pdate<DATE '2000-01-01' OR pdate>(now() AT TIME ZONE 'Asia/Seoul')::date)) AS invalid_rate_date,
 count(*)::int AS n,count(evaluation)::int AS priced,
 round(sum(purchase),2) AS purchase,round(coalesce(sum(evaluation),0),2) AS evaluation,
 min(priced_date) AS date,count(DISTINCT priced_date) AS dates,
 bool_and(current_krw IS NOT NULL AND previous_krw IS NOT NULL AND pdate<cdate) AND count(DISTINCT pdate)=1 AND count(DISTINCT priced_date)=1 AS daily,
 round(coalesce(sum(previous_krw*qty),0),2) AS previous
 FROM holding
), markets AS (
 SELECT market,sum(evaluation) AS amount FROM holding WHERE evaluation IS NOT NULL GROUP BY market
)
SELECT json_build_object(
 '_missingAsset',t.missing,'_invalidRateDate',t.invalid_rate_date,'baseDate',t.date,
 'pricingStatus',CASE WHEN t.priced<t.n THEN 'PARTIAL' WHEN t.dates>1 THEN 'MIXED_DATES' ELSE 'COMPLETE' END,
 'pricedHoldingCount',t.priced,'unpricedHoldingCount',t.n-t.priced,
 'totalPurchaseAmount',t.purchase,'totalEvaluationAmount',t.evaluation,
 'dailyProfitLoss',CASE WHEN t.daily THEN round(t.evaluation-t.previous,2) END,
 'dailyReturnRate',CASE WHEN t.daily THEN CASE WHEN t.previous=0 THEN 0.00 ELSE round((t.evaluation-t.previous)*100/t.previous,2) END END,
 'totalProfitLoss',CASE WHEN t.priced=t.n THEN round(t.evaluation-t.purchase,2) END,
 'totalReturnRate',CASE WHEN t.priced=t.n THEN CASE WHEN t.purchase=0 THEN 0.00 ELSE round((t.evaluation-t.purchase)*100/t.purchase,2) END END,
 'holdings',(SELECT coalesce(json_agg(json_build_object(
 'assetId',h.aid,'assetCode',h.asset_code,'name',h.name,'category',h.category,'market',h.market,
 'priceAvailable',h.current_krw IS NOT NULL,'baseDate',h.priced_date,'quantity',h.qty,
 'averagePurchasePrice',round(h.avg,2),'closePrice',CASE WHEN h.current_krw IS NOT NULL THEN h.close END,
 'purchaseAmount',h.purchase,'evaluationAmount',h.evaluation,'profitLoss',h.profit,'returnRate',h.return_rate,
 'weight',CASE WHEN h.evaluation IS NULL THEN NULL WHEN t.evaluation=0 THEN 0.00 ELSE round(h.evaluation*100/t.evaluation,2) END,
 'averagePurchasePriceCurrency','KRW','currency',CASE WHEN coalesce(h.usd,false) THEN 'USD' ELSE 'KRW' END,'evaluationCurrency','KRW'
 ) ORDER BY h.ord),'[]'::json) FROM holding h),
 'marketAllocations',(SELECT coalesce(json_agg(json_build_object('market',m.market,'evaluationAmount',round(m.amount,2),'weight',CASE WHEN t.evaluation=0 THEN 0.00 ELSE round(m.amount*100/t.evaluation,2) END) ORDER BY array_position(ARRAY['KOSPI','KOSDAQ','NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS'],m.market)),'[]'::json) FROM markets m)
)::text FROM totals t
"#;
