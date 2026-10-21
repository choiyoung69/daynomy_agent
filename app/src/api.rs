use serde_json::{Value, json};
use std::collections::BTreeMap;
use tokio_postgres::{Client, types::ToSql};

#[derive(Debug)]
pub struct ApiFault {
    pub status: u16,
    pub body: Value,
}

pub type Outcome = Result<(u16, Value), ApiFault>;

pub fn fault(status: u16, code: &str, message: &str) -> ApiFault {
    ApiFault {
        status,
        body: json!({"code":code,"message":message}),
    }
}

pub fn internal() -> ApiFault {
    fault(
        500,
        "INTERNAL_SERVER_ERROR",
        "서버 내부 오류가 발생했습니다.",
    )
}

pub fn invalid(field: &str, reason: &str) -> ApiFault {
    ApiFault {
        status: 400,
        body: json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":[{"field":field,"reason":reason}]}),
    }
}

fn decode(raw: &str) -> Result<String, ApiFault> {
    let mut bytes = Vec::with_capacity(raw.len());
    let mut input = raw.bytes();
    while let Some(byte) = input.next() {
        match byte {
            b'+' => bytes.push(b' '),
            b'%' => {
                let a = input.next().and_then(|b| (b as char).to_digit(16));
                let b = input.next().and_then(|b| (b as char).to_digit(16));
                match (a, b) {
                    (Some(a), Some(b)) => bytes.push((a * 16 + b) as u8),
                    _ => return Err(invalid("query", "타입이 올바르지 않습니다.")),
                }
            }
            byte => bytes.push(byte),
        }
    }
    String::from_utf8(bytes).map_err(|_| invalid("query", "타입이 올바르지 않습니다."))
}

pub fn query(raw: &str) -> Result<BTreeMap<String, String>, ApiFault> {
    let mut out = BTreeMap::new();
    for pair in raw.split('&').filter(|p| !p.is_empty()) {
        let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
        // Spring resolves the first value for single-valued query parameters.
        out.entry(decode(key)?).or_insert(decode(value)?);
    }
    Ok(out)
}

/// A path segment preserves '+'; form/query decoding turns it into a space.
pub fn path_text(raw: &str) -> Option<String> {
    decode(&raw.replace('+', "%2B")).ok()
}

pub fn path_integer(raw: &str) -> Option<i64> {
    path_text(raw).and_then(|value| crate::java_binding::integer(&value))
}

pub async fn rows(
    db: &Client,
    sql: &str,
    params: &[&(dyn ToSql + Sync)],
) -> Result<Vec<Value>, ApiFault> {
    let records = db.query(sql, params).await.map_err(|_| internal())?;
    records
        .into_iter()
        .map(|r| {
            let text: String = r.try_get(0).map_err(|_| internal())?;
            serde_json::from_str(&text).map_err(|_| internal())
        })
        .collect()
}
