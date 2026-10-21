//! Saved portfolios: durable ledger replay, locked mutations, and historical snapshots.
//! PostgreSQL NUMERIC performs all money arithmetic; no binary floating point is used.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query, rows};
use crate::service_auth::Principal;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use tokio_postgres::Client;

const US: &str = "('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS')";

type Result<T> = std::result::Result<T, ApiFault>;

fn business(code: &str) -> ApiFault {
    let (status, message) = match code {
        "PORTFOLIO_NOT_FOUND" => (404, "포트폴리오를 찾을 수 없습니다."),
        "PORTFOLIO_HOLDING_NOT_FOUND" => (404, "포트폴리오 보유자산을 찾을 수 없습니다."),
        "PORTFOLIO_TRANSACTION_NOT_FOUND" => (404, "포트폴리오 거래를 찾을 수 없습니다."),
        "ASSET_NOT_FOUND" => (404, "자산을 찾을 수 없습니다."),
        "MEMBER_NOT_FOUND" => (404, "회원을 찾을 수 없습니다."),
        "INVALID_TRANSACTION_EXCHANGE_RATE" => (
            400,
            "미국 거래는 1 USD당 원화 환율이 필요하며, 국내 거래의 환율은 1이어야 합니다.",
        ),
        "INSUFFICIENT_PORTFOLIO_QUANTITY" => {
            (400, "매도 수량이 해당 시점의 보유 수량보다 많습니다.")
        }
        "INVALID_PORTFOLIO_TRADE_DATE" => (
            400,
            "거래일은 해당 종목의 마지막 보유 수량 등록·조정일보다 이를 수 없습니다.",
        ),
        "INVALID_PORTFOLIO_PERIOD" => (400, "조회 시작일은 종료일보다 늦을 수 없습니다."),
        _ => return internal(),
    };
    fault(status, code, message)
}

pub async fn handle(
    method: &str,
    path: &str,
    raw_query: &str,
    body: &[u8],
    principal: &Principal,
    db: &Client,
) -> Option<Outcome> {
    let v2 = path == "/api/v2/users/me/portfolio/transactions";
    let suffix = if v2 {
        "/transactions"
    } else {
        path.strip_prefix("/api/users/me/portfolio")
            .or_else(|| path.strip_prefix("/api/portfolio"))?
    };
    let transaction_id = suffix
        .strip_prefix("/transactions/")
        .filter(|v| !v.is_empty() && !v.contains('/'));
    let holding_id = suffix
        .strip_prefix("/holdings/")
        .filter(|v| !v.is_empty() && !v.contains('/'));
    if !matches!(suffix, "" | "/transactions" | "/histories" | "/performance")
        && transaction_id.is_none()
        && holding_id.is_none()
    {
        return None;
    }
    if (v2 && method != "POST")
        || match suffix {
            "" | "/histories" | "/performance" => method != "GET",
            "/transactions" => method != "POST",
            _ => !matches!(method, "PATCH" | "DELETE"),
        }
    {
        return Some(Err(fault(
            405,
            "METHOD_NOT_ALLOWED",
            "지원하지 않는 HTTP 메서드입니다.",
        )));
    }
    let operation = async {
        if method == "GET" {
            return match suffix {
                "" => get(principal.id, db).await,
                "/histories" => histories(principal.id, raw_query, db).await,
                "/performance" => performance(principal.id, raw_query, db).await,
                _ => Err(internal()),
            };
        }
        let id = transaction_id
            .or(holding_id)
            .map(|id| {
                crate::api::path_integer(id).ok_or_else(|| {
                    invalid(
                        if transaction_id.is_some() {
                            "transactionId"
                        } else {
                            "assetId"
                        },
                        "타입이 올바르지 않습니다.",
                    )
                })
            })
            .transpose()?;
        let request = if method == "DELETE" {
            Value::Null
        } else {
            validate(body, suffix == "/transactions", holding_id.is_some(), db).await?
        };
        // Java resolves historical reference FX before opening its mutation
        // transaction. Provider failures must not occur while holding a member
        // or portfolio lock, and must leave the ledger untouched.
        let rates = if holding_id.is_none() {
            prefetch_transaction_rates(principal.id, suffix == "/transactions", id, &request, db)
                .await?
        } else {
            BTreeMap::new()
        };
        // READ COMMITTED plus a member row lock serializes every mutation before
        // the first ledger read, including creation of the first portfolio.
        // A fresh request client is required: the dispatcher supplies one.
        db.batch_execute("BEGIN ISOLATION LEVEL READ COMMITTED")
            .await
            .map_err(|_| internal())?;
        let result = mutate(method, suffix, id, &request, principal.id, &rates, db).await;
        if result.is_ok() {
            if db.batch_execute("COMMIT").await.is_err() {
                let _ = db.batch_execute("ROLLBACK").await;
                return Err(internal());
            }
        } else {
            let _ = db.batch_execute("ROLLBACK").await;
        }
        result
    }
    .await;
    Some(operation)
}

/// Match PortfolioExchangeRateService.forMember/forTransaction: use every
/// historical member asset plus the new asset, select USD closing dates from
/// the earliest affected date, and include the immediately preceding USD date.
/// This function is called before BEGIN and returns an immutable quote snapshot.
async fn prefetch_transaction_rates(
    mid: i64,
    create: bool,
    transaction_id: Option<i64>,
    request: &Value,
    db: &Client,
) -> Result<BTreeMap<String, Value>> {
    let new_date = request.get("tradeDate").and_then(Value::as_str);
    let (additional_asset, from) = if create {
        (
            request.get("assetId").and_then(Value::as_i64),
            new_date.ok_or_else(internal)?.to_owned(),
        )
    } else {
        let transaction_id = transaction_id.ok_or_else(internal)?;
        let previous = db.query_opt(
            "SELECT h.effective_date::text FROM portfolio_holding_histories h JOIN portfolios p ON p.id=h.portfolio_id WHERE h.id=$1 AND p.member_id=$2",
            &[&transaction_id, &mid],
        ).await.map_err(|_| internal())?;
        let Some(previous) = previous else {
            // Ownership/not-found errors are resolved by the locked mutation.
            return Ok(BTreeMap::new());
        };
        let old_date: String = previous.get(0);
        let from = new_date
            .map(|date| date.min(old_date.as_str()))
            .unwrap_or(&old_date)
            .to_owned();
        (None, from)
    };
    if from >= today(db).await? {
        return Ok(BTreeMap::new());
    }
    let sql = format!(
        r#"
        WITH assets_to_price AS (
            SELECT h.asset_id FROM portfolio_holding_histories h
            JOIN portfolios p ON p.id=h.portfolio_id WHERE p.member_id=$1
            UNION SELECT $2::bigint WHERE $2::bigint IS NOT NULL
        ), dates AS (
            SELECT DISTINCT p.base_date FROM stock_daily_prices p
            JOIN assets a ON a.id=p.asset_id
            WHERE p.asset_id IN (SELECT asset_id FROM assets_to_price)
              AND a.market IN {US}
              AND p.base_date<(now() AT TIME ZONE 'Asia/Seoul')::date
        )
        SELECT base_date::text FROM dates WHERE base_date>=$3::text::date
          OR base_date=(SELECT max(base_date) FROM dates WHERE base_date<$3::text::date)
        ORDER BY base_date
        "#
    );
    let dates = db
        .query(&sql, &[&mid, &additional_asset, &from])
        .await
        .map_err(|_| internal())?;
    let mut rates = BTreeMap::new();
    for row in dates {
        let date: String = row.get(0);
        match crate::service_market::load_quote(&date, db).await {
            Ok(quote) => {
                let rate = quote
                    .get("rate")
                    .filter(|rate| rate.is_number())
                    .ok_or_else(internal)?;
                rates.insert(date, rate.clone());
            }
            // Java ratesForDates skips this one business error only. HTTP,
            // configuration, invalid-date and database failures propagate.
            Err(error) if error.body["code"] == "EXCHANGE_RATE_UNAVAILABLE" => {}
            Err(error) => return Err(error),
        }
    }
    Ok(rates)
}

fn date_valid(date: &str) -> bool {
    let b = date.as_bytes();
    if b.len() != 10
        || b[4] != b'-'
        || b[7] != b'-'
        || b.iter()
            .enumerate()
            .any(|(i, c)| i != 4 && i != 7 && !c.is_ascii_digit())
    {
        return false;
    }
    let y = date[..4].parse::<u32>().unwrap_or(0);
    let m = date[5..7].parse::<usize>().unwrap_or(0);
    let d = date[8..].parse::<u32>().unwrap_or(0);
    let leap = y % 400 == 0 || y % 4 == 0 && y % 100 != 0;
    let days = [
        31,
        if leap { 29 } else { 28 },
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

async fn today(db: &Client) -> Result<String> {
    Ok(db
        .query_one("SELECT (now() AT TIME ZONE 'Asia/Seoul')::date::text", &[])
        .await
        .map_err(|_| internal())?
        .get(0))
}

// BigDecimal-style digit constraints, including exponent notation, without f64.
fn decimal_shape(raw: &str) -> Option<(bool, bool, i64, i64)> {
    let negative = raw.starts_with('-');
    let raw = raw.trim_start_matches(['-', '+']);
    let mut exp = raw.split(['e', 'E']);
    let mantissa = exp.next()?;
    let exponent = exp
        .next()
        .map(|v| v.parse::<i64>().ok())
        .unwrap_or(Some(0))?;
    let (whole, fraction) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    let digits = format!("{whole}{fraction}");
    let nonzero = digits.trim_start_matches('0');
    let scale = (fraction.len() as i64).saturating_sub(exponent);
    Some((
        negative,
        nonzero.is_empty(),
        (nonzero.len().max(1) as i64).saturating_sub(scale),
        scale,
    ))
}

async fn validate(body: &[u8], create: bool, holding: bool, db: &Client) -> Result<Value> {
    let req: Value = serde_json::from_slice(body)
        .map_err(|_| invalid("requestBody", "요청 본문을 읽을 수 없습니다."))?;
    if !req.is_object() {
        return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
    }
    let mut errors = Vec::new();
    for key in if create {
        vec!["assetId", "quantity"]
    } else {
        vec!["quantity"]
    } {
        let value = &req[key];
        if value.is_null() {
            errors.push(json!({"field":key,"reason":"널이어서는 안됩니다"}));
        } else if let Some(n) = value.as_i64() {
            if n <= 0 {
                errors.push(json!({"field":key,"reason":"0보다 커야 합니다"}));
            }
        } else {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        }
    }
    if !holding {
        if create {
            if req["type"].is_null() {
                errors.push(json!({"field":"type","reason":"널이어서는 안됩니다"}));
            } else if !matches!(req["type"].as_str(), Some("BUY" | "SELL")) {
                return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
            }
        }
        if req["tradeDate"].is_null() {
            errors.push(json!({"field":"tradeDate","reason":"널이어서는 안됩니다"}));
        } else {
            let date = req["tradeDate"]
                .as_str()
                .filter(|v| date_valid(v))
                .ok_or_else(|| invalid("requestBody", "요청 본문을 읽을 수 없습니다."))?;
            if date > today(db).await?.as_str() {
                errors
                    .push(json!({"field":"tradeDate","reason":"과거 또는 현재의 날짜여야 합니다"}));
            }
        }
    }
    let specs = if holding {
        vec![("averagePurchasePrice", 15, 2, "0.01", false)]
    } else {
        vec![
            ("unitPrice", 15, 4, "0.0001", false),
            ("fee", 15, 2, "0.00", false),
            ("tax", 15, 2, "0.00", false),
            ("exchangeRate", 10, 6, "0.000001", true),
        ]
    };
    for (key, integer, fraction, minimum, optional) in specs {
        let value = &req[key];
        if value.is_null() {
            if !optional {
                errors.push(json!({"field":key,"reason":"널이어서는 안됩니다"}));
            }
            continue;
        }
        // Jackson accepts numeric strings for BigDecimal as well as numbers.
        let raw = if value.is_number() {
            value.to_string()
        } else if let Some(raw) = value.as_str() {
            raw.to_owned()
        } else {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        };
        if serde_json::from_str::<serde_json::Number>(&raw).is_err() {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        }
        let Some((negative, zero, digits, scale)) = decimal_shape(&raw) else {
            return Err(invalid("requestBody", "요청 본문을 읽을 수 없습니다."));
        };
        let bad_digits = digits > integer || scale > fraction;
        if bad_digits {
            errors.push(json!({"field":key,"reason":format!("허용되는 숫자 범위를 벗어났습니다 (<정수 {integer} 자리>.<소수 {fraction} 자리> 예상)")}));
        }
        // Numeric SQL only receives bounded exponents; don't allocate arbitrarily
        // large PostgreSQL numbers from adversarial scientific notation.
        let below = if negative && !zero {
            true
        } else if zero {
            minimum != "0.00"
        } else if digits < 1 - fraction {
            true
        } else if bad_digits {
            false
        } else {
            db.query_one(
                "SELECT $1::text::numeric < $2::text::numeric",
                &[&raw, &minimum],
            )
            .await
            .map_err(|_| internal())?
            .get(0)
        };
        if below {
            errors.push(json!({"field":key,"reason":format!("{minimum} 이상이어야 합니다")}));
        }
    }
    if !errors.is_empty() {
        return Err(ApiFault {
            status: 400,
            body: json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":errors}),
        });
    }
    Ok(req)
}

fn decimal(req: &Value, key: &str) -> String {
    req[key]
        .as_str()
        .map(str::to_owned)
        .unwrap_or_else(|| req[key].to_string())
}

#[derive(Clone)]
struct Position {
    quantity: i64,
    average: String,
}
struct Ledger {
    positions: BTreeMap<i64, Position>,
    realized: String,
}

async fn replay(pid: i64, through: Option<&str>, db: &Client) -> Result<Ledger> {
    let records=db.query("SELECT asset_id,change_type,quantity,average_purchase_price::text,transaction_quantity,unit_price::text,fee::text,tax::text,exchange_rate::text FROM portfolio_holding_histories WHERE portfolio_id=$1 AND ($2::text IS NULL OR effective_date<=$2::text::date) ORDER BY effective_date,created_at,id",&[&pid,&through]).await.map_err(|_|internal())?;
    let mut positions: BTreeMap<i64, Position> = BTreeMap::new();
    let mut realized = "0.00".to_owned();
    for h in records {
        let aid: i64 = h.get(0);
        let kind: String = h.get(1);
        match kind.as_str() {
            "REMOVED" => {
                positions.remove(&aid);
            }
            "BUY" | "SELL" => {
                let qty: i64 = h
                    .try_get::<_, Option<i64>>(4)
                    .map_err(|_| internal())?
                    .ok_or_else(internal)?;
                let unit: String = h
                    .try_get::<_, Option<String>>(5)
                    .map_err(|_| internal())?
                    .ok_or_else(internal)?;
                let fee: String = h.get(6);
                let tax: String = h.get(7);
                let rate: String = h.get(8);
                let current = positions.get(&aid).cloned().unwrap_or(Position {
                    quantity: 0,
                    average: "0.00".into(),
                });
                if kind == "BUY" {
                    let next = current.quantity.checked_add(qty).ok_or_else(internal)?;
                    let avg:String=db.query_one("SELECT round(($1::text::numeric*$2::bigint + ($3::text::numeric*$4::bigint+$5::text::numeric+$6::text::numeric)*$7::text::numeric)/$8::bigint,2)::text",&[&current.average,&current.quantity,&unit,&qty,&fee,&tax,&rate,&next]).await.map_err(|_|internal())?.get(0);
                    positions.insert(
                        aid,
                        Position {
                            quantity: next,
                            average: avg,
                        },
                    );
                } else {
                    if current.quantity < qty {
                        return Err(business("INSUFFICIENT_PORTFOLIO_QUANTITY"));
                    }
                    realized=db.query_one("SELECT ($1::text::numeric+($2::text::numeric*$3::text::numeric-$4::text::numeric)*$5::bigint-($6::text::numeric+$7::text::numeric)*$3::text::numeric)::text",&[&realized,&unit,&rate,&current.average,&qty,&fee,&tax]).await.map_err(|_|internal())?.get(0);
                    if current.quantity == qty {
                        positions.remove(&aid);
                    } else {
                        positions.insert(
                            aid,
                            Position {
                                quantity: current.quantity - qty,
                                average: current.average,
                            },
                        );
                    }
                }
            }
            _ => {
                positions.insert(
                    aid,
                    Position {
                        quantity: h.get(2),
                        average: h.get(3),
                    },
                );
            }
        }
    }
    realized = db
        .query_one("SELECT round($1::text::numeric,2)::text", &[&realized])
        .await
        .map_err(|_| internal())?
        .get(0);
    Ok(Ledger {
        positions,
        realized,
    })
}

async fn portfolio(mid: i64, db: &Client) -> Result<Option<i64>> {
    Ok(db
        .query_opt("SELECT id FROM portfolios WHERE member_id=$1", &[&mid])
        .await
        .map_err(|_| internal())?
        .map(|r| r.get(0)))
}

async fn holding(pid: i64, aid: i64, db: &Client) -> Result<Option<Value>> {
    let sql = format!(
        "SELECT json_build_object('assetId',a.id,'assetCode',a.asset_code,'name',a.name,'category',a.category,'market',a.market,'quantity',h.quantity,'averagePurchasePrice',h.average_purchase_price,'averagePurchasePriceCurrency','KRW','currency',CASE WHEN a.market IN {US} THEN 'USD' ELSE 'KRW' END)::text FROM portfolio_holdings h JOIN assets a ON a.id=h.asset_id WHERE h.portfolio_id=$1 AND h.asset_id=$2"
    );
    Ok(rows(db, &sql, &[&pid, &aid]).await?.pop())
}

async fn get(mid: i64, db: &Client) -> Outcome {
    let Some(pid) = portfolio(mid, db).await? else {
        return Ok((200, json!({"holdings":[],"totalRealizedProfitLoss":0.00})));
    };
    let ledger = replay(pid, None, db).await?;
    let sql = format!(
        "SELECT json_build_object('assetId',a.id,'assetCode',a.asset_code,'name',a.name,'category',a.category,'market',a.market,'quantity',h.quantity,'averagePurchasePrice',h.average_purchase_price,'averagePurchasePriceCurrency','KRW','currency',CASE WHEN a.market IN {US} THEN 'USD' ELSE 'KRW' END)::text FROM portfolio_holdings h JOIN assets a ON a.id=h.asset_id WHERE h.portfolio_id=$1 ORDER BY h.id"
    );
    Ok((
        200,
        json!({"holdings":rows(db,&sql,&[&pid]).await?,"totalRealizedProfitLoss":number(&ledger.realized)?}),
    ))
}

fn number(raw: &str) -> Result<Value> {
    serde_json::from_str(raw).map_err(|_| internal())
}

async fn mutate(
    method: &str,
    suffix: &str,
    id: Option<i64>,
    req: &Value,
    mid: i64,
    rates: &BTreeMap<String, Value>,
    db: &Client,
) -> Outcome {
    let member = db
        .query_opt("SELECT status FROM members WHERE id=$1 FOR UPDATE", &[&mid])
        .await
        .map_err(|_| internal())?
        .ok_or_else(|| business("MEMBER_NOT_FOUND"))?;
    // Authentication can precede a concurrent withdrawal; recheck the committed
    // status after obtaining the same member lock used by withdrawal.
    if member.get::<_, String>(0) != "ACTIVE" {
        return Err(fault(401, "WITHDRAWN_MEMBER", "탈퇴한 회원입니다."));
    }
    let create = suffix == "/transactions";
    let pid=match portfolio(mid,db).await? {
        Some(pid)=>pid,
        None if create=>db.query_one("INSERT INTO portfolios(member_id,created_at,updated_at) VALUES($1,clock_timestamp(),clock_timestamp()) RETURNING id",&[&mid]).await.map_err(|_|internal())?.get(0),
        None=>return Err(business("PORTFOLIO_NOT_FOUND")),
    };
    db.query_one("SELECT id FROM portfolios WHERE id=$1 FOR UPDATE", &[&pid])
        .await
        .map_err(|_| internal())?;
    if suffix.starts_with("/holdings/") {
        return mutate_holding(method, pid, id.ok_or_else(internal)?, req, db).await;
    }
    let (aid, tid, old_date) = if create {
        (req["assetId"].as_i64().ok_or_else(internal)?, 0, None)
    } else {
        let tid = id.ok_or_else(internal)?;
        let row=db.query_opt("SELECT asset_id,effective_date::text FROM portfolio_holding_histories WHERE id=$1 AND portfolio_id=$2 AND change_type IN ('BUY','SELL')",&[&tid,&pid]).await.map_err(|_|internal())?.ok_or_else(||business("PORTFOLIO_TRANSACTION_NOT_FOUND"))?;
        (row.get(0), tid, Some(row.get::<_, String>(1)))
    };
    let mut refresh_from = old_date.clone();
    let tid = if method == "DELETE" {
        db.execute(
            "DELETE FROM portfolio_holding_histories WHERE id=$1 AND portfolio_id=$2",
            &[&tid, &pid],
        )
        .await
        .map_err(|_| internal())?;
        tid
    } else {
        let date = req["tradeDate"].as_str().ok_or_else(internal)?;
        refresh_from = Some(
            old_date
                .as_deref()
                .map(|d| d.min(date))
                .unwrap_or(date)
                .to_owned(),
        );
        let invalid_date:bool=db.query_one("SELECT EXISTS(SELECT 1 FROM portfolio_holding_histories WHERE portfolio_id=$1 AND asset_id=$2 AND change_type IN ('OPENING_BALANCE','ADJUSTED','ADDED','UPDATED') AND effective_date>$3::text::date)",&[&pid,&aid,&date]).await.map_err(|_|internal())?.get(0);
        if invalid_date {
            return Err(business("INVALID_PORTFOLIO_TRADE_DATE"));
        }
        let sql = format!("SELECT coalesce(market IN {US},false) FROM assets WHERE id=$1");
        let usd: bool = db
            .query_opt(&sql, &[&aid])
            .await
            .map_err(|_| internal())?
            .ok_or_else(|| business("ASSET_NOT_FOUND"))?
            .get(0);
        let supplied = !req["exchangeRate"].is_null();
        let rate = if supplied {
            decimal(req, "exchangeRate")
        } else {
            "1".to_owned()
        };
        let is_one: bool = db
            .query_one("SELECT $1::text::numeric=1", &[&rate])
            .await
            .map_err(|_| internal())?
            .get(0);
        if usd && !supplied || !usd && !is_one {
            return Err(business("INVALID_TRANSACTION_EXCHANGE_RATE"));
        }
        let qty = req["quantity"].as_i64().ok_or_else(internal)?;
        let unit = decimal(req, "unitPrice");
        let fee = decimal(req, "fee");
        let tax = decimal(req, "tax");
        if create {
            let kind = req["type"].as_str().ok_or_else(internal)?;
            db.query_one("INSERT INTO portfolio_holding_histories(portfolio_id,asset_id,change_type,quantity,average_purchase_price,effective_date,transaction_quantity,unit_price,fee,tax,exchange_rate,created_at,updated_at) SELECT $1,$2,$3,coalesce(h.quantity,0),coalesce(h.average_purchase_price,0),$4::text::date,$5,$6::text::numeric,$7::text::numeric,$8::text::numeric,$9::text::numeric,clock_timestamp(),clock_timestamp() FROM (SELECT 1) x LEFT JOIN portfolio_holdings h ON h.portfolio_id=$1 AND h.asset_id=$2 RETURNING id",&[&pid,&aid,&kind,&date,&qty,&unit,&fee,&tax,&rate]).await.map_err(|_|internal())?.get(0)
        } else {
            db.execute("UPDATE portfolio_holding_histories SET effective_date=$3::text::date,transaction_quantity=$4,unit_price=$5::text::numeric,fee=$6::text::numeric,tax=$7::text::numeric,exchange_rate=$8::text::numeric,updated_at=clock_timestamp() WHERE id=$1 AND portfolio_id=$2",&[&tid,&pid,&date,&qty,&unit,&fee,&tax,&rate]).await.map_err(|_|internal())?;
            tid
        }
    };
    let ledger = replay(pid, None, db).await?;
    if let Some(position) = ledger.positions.get(&aid) {
        db.execute("INSERT INTO portfolio_holdings(portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at) VALUES($1,$2,$3,$4::text::numeric,clock_timestamp(),clock_timestamp()) ON CONFLICT(portfolio_id,asset_id) DO UPDATE SET quantity=excluded.quantity,average_purchase_price=excluded.average_purchase_price,updated_at=clock_timestamp() WHERE (portfolio_holdings.quantity,portfolio_holdings.average_purchase_price) IS DISTINCT FROM (excluded.quantity,excluded.average_purchase_price)",&[&pid,&aid,&position.quantity,&position.average]).await.map_err(|_|internal())?;
    } else {
        db.execute(
            "DELETE FROM portfolio_holdings WHERE portfolio_id=$1 AND asset_id=$2",
            &[&pid, &aid],
        )
        .await
        .map_err(|_| internal())?;
    }
    refresh_snapshots(
        pid,
        refresh_from.as_deref().ok_or_else(internal)?,
        rates,
        db,
    )
    .await?;
    Ok((
        if create { 201 } else { 200 },
        json!({"transactionId":tid,"holding":holding(pid,aid,db).await?,"totalRealizedProfitLoss":number(&ledger.realized)?}),
    ))
}

async fn mutate_holding(method: &str, pid: i64, aid: i64, req: &Value, db: &Client) -> Outcome {
    let current=db.query_opt("SELECT quantity,average_purchase_price::text FROM portfolio_holdings WHERE portfolio_id=$1 AND asset_id=$2",&[&pid,&aid]).await.map_err(|_|internal())?.ok_or_else(||business("PORTFOLIO_HOLDING_NOT_FOUND"))?;
    let old_qty: i64 = current.get(0);
    let old_avg: String = current.get(1);
    let qty = if method == "DELETE" {
        old_qty
    } else {
        req["quantity"].as_i64().ok_or_else(internal)?
    };
    let avg = if method == "DELETE" {
        old_avg.clone()
    } else {
        decimal(req, "averagePurchasePrice")
    };
    let unchanged: bool = db
        .query_one(
            "SELECT $1::bigint=$2::bigint AND $3::text::numeric=$4::text::numeric",
            &[&qty, &old_qty, &avg, &old_avg],
        )
        .await
        .map_err(|_| internal())?
        .get(0);
    if method == "DELETE" || !unchanged {
        let kind = if method == "DELETE" {
            "REMOVED"
        } else {
            "ADJUSTED"
        };
        db.execute("INSERT INTO portfolio_holding_histories(portfolio_id,asset_id,change_type,quantity,average_purchase_price,effective_date,created_at,updated_at) VALUES($1,$2,$3,$4,$5::text::numeric,(now() AT TIME ZONE 'Asia/Seoul')::date,clock_timestamp(),clock_timestamp())",&[&pid,&aid,&kind,&qty,&avg]).await.map_err(|_|internal())?;
    }
    if method == "DELETE" {
        db.execute(
            "DELETE FROM portfolio_holdings WHERE portfolio_id=$1 AND asset_id=$2",
            &[&pid, &aid],
        )
        .await
        .map_err(|_| internal())?;
        Ok((204, Value::Null))
    } else {
        if !unchanged {
            db.execute("UPDATE portfolio_holdings SET quantity=$3,average_purchase_price=$4::text::numeric,updated_at=clock_timestamp() WHERE portfolio_id=$1 AND asset_id=$2",&[&pid,&aid,&qty,&avg]).await.map_err(|_|internal())?;
        }
        Ok((200, holding(pid, aid, db).await?.ok_or_else(internal)?))
    }
}

async fn period(raw: &str, db: &Client) -> Result<(String, String)> {
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
    if from > to {
        return Err(business("INVALID_PORTFOLIO_PERIOD"));
    }
    let _ = db;
    Ok((from.clone(), to.clone()))
}

async fn histories(mid: i64, raw: &str, db: &Client) -> Outcome {
    let (from, to) = period(raw, db).await?;
    let pid = portfolio(mid, db)
        .await?
        .ok_or_else(|| business("PORTFOLIO_NOT_FOUND"))?;
    let sql = format!(
        "SELECT json_build_object('historyId',h.id,'assetId',a.id,'assetCode',a.asset_code,'name',a.name,'changeType',h.change_type,'quantity',h.quantity,'averagePurchasePrice',h.average_purchase_price,'effectiveDate',h.effective_date,'transactionQuantity',h.transaction_quantity,'unitPrice',h.unit_price,'fee',h.fee,'tax',h.tax,'occurredAt',h.created_at,'currency',CASE WHEN a.market IN {US} THEN 'USD' ELSE 'KRW' END,'exchangeRate',h.exchange_rate,'averagePurchasePriceCurrency','KRW')::text FROM portfolio_holding_histories h JOIN assets a ON a.id=h.asset_id WHERE h.portfolio_id=$1 AND h.effective_date BETWEEN $2::text::date AND $3::text::date ORDER BY h.effective_date DESC,h.created_at DESC,h.id DESC"
    );
    Ok((
        200,
        Value::Array(rows(db, &sql, &[&pid, &from, &to]).await?),
    ))
}

fn positions_json(ledger: &Ledger) -> Result<String> {
    let mut holdings = Vec::new();
    for (aid, p) in &ledger.positions {
        holdings.push(
            json!({"assetId":aid,"quantity":p.quantity,"averagePurchasePrice":number(&p.average)?}),
        );
    }
    Ok(Value::Array(holdings).to_string())
}

/// Price collection is committed before this hook. Refresh failures are isolated
/// per member and cannot undo prices or other members' historical snapshots.
pub(crate) async fn refresh_latest_snapshots(db: &Client) -> Result<(u64, u64)> {
    let portfolios=db.query("SELECT p.id,p.member_id,min(h.effective_date)::text FROM portfolios p JOIN members m ON m.id=p.member_id AND m.status='ACTIVE' JOIN portfolio_holding_histories h ON h.portfolio_id=p.id GROUP BY p.id,p.member_id ORDER BY p.id",&[]).await.map_err(|_|internal())?;
    let mut completed = 0;
    let mut failed = 0;
    for row in portfolios {
        let pid: i64 = row.get(0);
        let mid: i64 = row.get(1);
        let from: String = row.get(2);
        let result: Result<()> = async {
            let rates =
                prefetch_transaction_rates(mid, true, None, &json!({"tradeDate":from}), db).await?;
            db.batch_execute("BEGIN").await.map_err(|_| internal())?;
            let operation: Result<()> = async {
                let active = db
                    .query_opt(
                        "SELECT id FROM members WHERE id=$1 AND status='ACTIVE' FOR UPDATE",
                        &[&mid],
                    )
                    .await
                    .map_err(|_| internal())?;
                if active.is_none() {
                    return Ok(());
                }
                let portfolio = db
                    .query_opt(
                        "SELECT id FROM portfolios WHERE id=$1 AND member_id=$2 FOR UPDATE",
                        &[&pid, &mid],
                    )
                    .await
                    .map_err(|_| internal())?;
                if portfolio.is_some() {
                    refresh_snapshots(pid, &from, &rates, db).await?;
                }
                Ok(())
            }
            .await;
            if operation.is_ok() {
                if db.batch_execute("COMMIT").await.is_err() {
                    let _ = db.batch_execute("ROLLBACK").await;
                    return Err(internal());
                }
            } else {
                let _ = db.batch_execute("ROLLBACK").await;
            }
            operation
        }
        .await;
        if result.is_ok() {
            completed += 1;
        } else {
            failed += 1;
            eprintln!("event=portfolio.snapshot_refresh_failed");
        }
    }
    Ok((completed, failed))
}

async fn refresh_snapshots(
    pid: i64,
    from: &str,
    rates: &BTreeMap<String, Value>,
    db: &Client,
) -> Result<()> {
    // Match the original union of trading dates for any historical/current asset
    // and already persisted snapshot dates. Today's value is never persisted.
    let candidates=db.query(r#"
        WITH price_dates AS (
          SELECT DISTINCT p.base_date FROM stock_daily_prices p WHERE
          p.asset_id IN (SELECT asset_id FROM portfolio_holding_histories WHERE portfolio_id=$1
                        UNION SELECT asset_id FROM portfolio_holdings WHERE portfolio_id=$1)
        ), candidates AS (
          SELECT base_date FROM price_dates UNION
          SELECT base_date FROM portfolio_daily_snapshots WHERE portfolio_id=$1
        ) SELECT c.base_date::text,(SELECT max(base_date)::text FROM price_dates p WHERE p.base_date<c.base_date)
          FROM candidates c WHERE c.base_date>=$2::text::date
          AND c.base_date<(now() AT TIME ZONE 'Asia/Seoul')::date ORDER BY c.base_date
        "#,&[&pid,&from]).await.map_err(|_|internal())?;
    let rates_json = serde_json::to_string(rates).map_err(|_| internal())?;
    for candidate in candidates {
        let date: String = candidate.get(0);
        let previous: Option<String> = candidate.get(1);
        let ledger = replay(pid, Some(&date), db).await?;
        if ledger.positions.is_empty() {
            db.execute("DELETE FROM portfolio_daily_snapshots WHERE portfolio_id=$1 AND base_date=$2::text::date",&[&pid,&date]).await.map_err(|_|internal())?;
            continue;
        }
        let positions = positions_json(&ledger)?;
        let amounts = rows(
            db,
            SNAPSHOT_AMOUNTS_SQL,
            &[&positions, &date, &previous, &rates_json],
        )
        .await?
        .pop()
        .ok_or_else(internal)?;
        if amounts["invalidRateDate"].as_bool() == Some(true) {
            return Err(fault(
                400,
                "INVALID_EXCHANGE_RATE_DATE",
                "환율 조회일은 2000-01-01부터 오늘까지여야 합니다.",
            ));
        }
        // As in the source, incomplete historical pricing or unavailable cached
        // FX skips this candidate rather than manufacturing a valuation.
        if amounts["complete"].as_bool() != Some(true) {
            continue;
        }
        let payload = amounts.to_string();
        db.execute(r#"
            INSERT INTO portfolio_daily_snapshots(portfolio_id,base_date,total_purchase_amount,total_evaluation_amount,total_profit_loss,total_return_rate,daily_profit_loss,daily_return_rate,created_at,updated_at)
            SELECT $1,$2::text::date,(v->>'totalPurchaseAmount')::numeric,(v->>'totalEvaluationAmount')::numeric,
            (v->>'totalProfitLoss')::numeric,(v->>'totalReturnRate')::numeric,
            (v->>'dailyProfitLoss')::numeric,(v->>'dailyReturnRate')::numeric,clock_timestamp(),clock_timestamp()
            FROM (SELECT $3::text::jsonb AS v) x
            ON CONFLICT(portfolio_id,base_date) DO UPDATE SET
            total_purchase_amount=excluded.total_purchase_amount,total_evaluation_amount=excluded.total_evaluation_amount,
            total_profit_loss=excluded.total_profit_loss,total_return_rate=excluded.total_return_rate,
            daily_profit_loss=excluded.daily_profit_loss,daily_return_rate=excluded.daily_return_rate,updated_at=clock_timestamp()
            WHERE (portfolio_daily_snapshots.total_purchase_amount,portfolio_daily_snapshots.total_evaluation_amount,
                   portfolio_daily_snapshots.total_profit_loss,portfolio_daily_snapshots.total_return_rate,
                   portfolio_daily_snapshots.daily_profit_loss,portfolio_daily_snapshots.daily_return_rate)
             IS DISTINCT FROM (excluded.total_purchase_amount,excluded.total_evaluation_amount,excluded.total_profit_loss,
                               excluded.total_return_rate,excluded.daily_profit_loss,excluded.daily_return_rate)
            "#,&[&pid,&date,&payload]).await.map_err(|_|internal())?;
    }
    Ok(())
}

const SNAPSHOT_AMOUNTS_SQL: &str = r#"
WITH input AS (
 SELECT (h->>'assetId')::bigint aid,(h->>'quantity')::bigint qty,(h->>'averagePurchasePrice')::numeric avg
 FROM jsonb_array_elements($1::text::jsonb) h
), prices AS (
 SELECT i.*,a.market IN ('NASDAQ','NYSE','NYSE_ARCA','NYSE_AMERICAN','BATS') usd,
 p.close_price,p2.close_price previous_price,r.rate,r2.rate previous_rate
 FROM input i JOIN assets a ON a.id=i.aid
 LEFT JOIN stock_daily_prices p ON p.asset_id=i.aid AND p.base_date=$2::text::date
 LEFT JOIN stock_daily_prices p2 ON p2.asset_id=i.aid AND p2.base_date=$3::text::date
 LEFT JOIN LATERAL (SELECT ($4::text::jsonb->>p.base_date::text)::numeric AS rate) r ON true
 LEFT JOIN LATERAL (SELECT ($4::text::jsonb->>p2.base_date::text)::numeric AS rate) r2 ON true
), totals AS (
 SELECT bool_and(close_price IS NOT NULL AND (NOT coalesce(usd,false) OR rate IS NOT NULL)
   AND ($3::text IS NULL OR previous_price IS NOT NULL AND (NOT coalesce(usd,false) OR previous_rate IS NOT NULL))) complete,
 bool_or(coalesce(usd,false) AND ($2::text::date<DATE '2000-01-01' OR $3::text::date<DATE '2000-01-01')) invalid_rate_date,
 round(sum(qty*avg),2) purchase,
 round(sum(qty*close_price*CASE WHEN coalesce(usd,false) THEN rate ELSE 1 END),2) evaluation,
 round(sum(qty*previous_price*CASE WHEN coalesce(usd,false) THEN previous_rate ELSE 1 END),2) previous
 FROM prices
)
SELECT json_build_object('complete',complete,'invalidRateDate',invalid_rate_date,
 'totalPurchaseAmount',purchase,'totalEvaluationAmount',evaluation,'totalProfitLoss',evaluation-purchase,
 'totalReturnRate',CASE WHEN purchase=0 THEN 0.00 ELSE round((evaluation-purchase)*100/purchase,2) END,
 'dailyProfitLoss',CASE WHEN $3::text IS NOT NULL THEN evaluation-previous END,
 'dailyReturnRate',CASE WHEN $3::text IS NOT NULL THEN CASE WHEN previous=0 THEN 0.00 ELSE round((evaluation-previous)*100/previous,2) END END
)::text FROM totals
"#;

async fn performance(mid: i64, raw: &str, db: &Client) -> Outcome {
    let (from, to) = period(raw, db).await?;
    let today = today(db).await?;
    let pid = portfolio(mid, db).await?;
    let points = if let Some(pid) = pid {
        rows(db,r#"SELECT json_build_object('baseDate',base_date,'totalPurchaseAmount',total_purchase_amount,
        'totalEvaluationAmount',total_evaluation_amount,'totalProfitLoss',total_profit_loss,'totalReturnRate',total_return_rate,
        'dailyProfitLoss',daily_profit_loss,'dailyReturnRate',daily_return_rate)::text
        FROM portfolio_daily_snapshots WHERE portfolio_id=$1 AND base_date BETWEEN $2::text::date AND $3::text::date
        AND base_date<(now() AT TIME ZONE 'Asia/Seoul')::date ORDER BY base_date"#,&[&pid,&from,&to]).await?
    } else {
        Vec::new()
    };
    let current = if from <= today && today <= to {
        if let Some(pid) = pid {
            current_point(pid, &today, db).await?
        } else {
            Value::Null
        }
    } else {
        Value::Null
    };
    let ready = points.len() >= 2;
    let base = points
        .last()
        .map(|p| p["baseDate"].clone())
        .unwrap_or(Value::Null);
    let previous = if ready {
        points[points.len() - 2]["baseDate"].clone()
    } else {
        Value::Null
    };
    Ok((
        200,
        json!({"status":if ready {"READY"} else {"INSUFFICIENT_DATA"},"reason":if ready {Value::Null} else {json!("SNAPSHOT_DATA_INSUFFICIENT")},"baseDate":base,"previousBaseDate":previous,"points":points,"currentPoint":current}),
    ))
}

async fn current_point(pid: i64, date: &str, db: &Client) -> Result<Value> {
    let holdings=rows(db,"SELECT json_build_object('assetId',asset_id,'quantity',quantity,'averagePurchasePrice',average_purchase_price)::text FROM portfolio_holdings WHERE portfolio_id=$1 ORDER BY id",&[&pid]).await?;
    if holdings.is_empty() {
        return Ok(
            json!({"baseDate":date,"priceBaseDate":null,"totalPurchaseAmount":0.00,"totalEvaluationAmount":0.00,"totalProfitLoss":0.00,"totalReturnRate":0.00,"dailyProfitLoss":null,"dailyReturnRate":null}),
        );
    }
    let (_, calculation) = crate::service_market::calculate_saved(holdings, db).await?;
    if calculation["pricingStatus"] != "COMPLETE" {
        return Ok(Value::Null);
    }
    Ok(
        json!({"baseDate":date,"priceBaseDate":calculation["baseDate"],"totalPurchaseAmount":calculation["totalPurchaseAmount"],"totalEvaluationAmount":calculation["totalEvaluationAmount"],"totalProfitLoss":calculation["totalProfitLoss"],"totalReturnRate":calculation["totalReturnRate"],"dailyProfitLoss":null,"dailyReturnRate":null}),
    )
}
