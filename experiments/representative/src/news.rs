use serde_json::{Value, json};
fn invalid(field: &str, reason: &str) -> (u16, Value) {
    (
        400,
        json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":[{"field":field,"reason":reason}]}),
    )
}
fn decode(s: &str) -> String {
    let b = s.as_bytes();
    let (mut o, mut i) = (Vec::new(), 0);
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let Ok(v) = u8::from_str_radix(&s[i + 1..i + 3], 16) {
                o.push(v);
                i += 3;
                continue;
            }
        }
        o.push(if b[i] == b'+' { b' ' } else { b[i] });
        i += 1
    }
    String::from_utf8_lossy(&o).into_owned()
}
fn param(q: &str, n: &str) -> Option<String> {
    q.trim_start_matches('?')
        .split('&')
        .filter_map(|p| p.split_once('='))
        .find(|(k, _)| decode(k) == n)
        .map(|(_, v)| decode(v))
        .filter(|value| !value.is_empty())
}
fn f<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.get(k).unwrap_or(&Value::Null)
}
pub fn list(query: &str, rows: &Value) -> (u16, Value) {
    let page = match param(query, "page") {
        None => 1,
        Some(v) => match v.parse::<i32>() {
            Ok(n) => n,
            Err(_) => return invalid("page", "타입이 올바르지 않습니다."),
        },
    };
    let size = match param(query, "size") {
        None => 15,
        Some(v) => match v.parse::<i32>() {
            Ok(n) => n,
            Err(_) => return invalid("size", "타입이 올바르지 않습니다."),
        },
    };
    if page < 1 {
        return invalid("page", "페이지 번호는 1 이상이어야 합니다.");
    }
    if size < 1 {
        return invalid("size", "페이지 크기는 1 이상이어야 합니다.");
    }
    if size > 100 {
        return invalid("size", "페이지 크기는 100 이하여야 합니다.");
    }
    let cat = param(query, "category");
    if let Some(c) = &cat {
        if !matches!(c.as_str(), "REAL_ESTATE" | "STOCK" | "ETF") {
            return invalid("category", "지원하지 않는 값입니다.");
        }
    }
    let mut a: Vec<&Value> = rows
        .as_array()
        .into_iter()
        .flatten()
        .filter(|r| {
            f(r, "status") == "PUBLISHED" && cat.as_ref().is_none_or(|c| f(r, "category") == c)
        })
        .collect();
    a.sort_by(|x, y| {
        f(y, "published_at")
            .as_str()
            .cmp(&f(x, "published_at").as_str())
            .then_with(|| f(y, "id").as_i64().cmp(&f(x, "id").as_i64()))
    });
    let total = a.len();
    let start = ((page - 1) as usize).saturating_mul(size as usize);
    let items:Vec<Value>=a.into_iter().skip(start).take(size as usize).map(|r|json!({"id":f(r,"id"),"title":f(r,"title"),"imageUrl":f(r,"image_url"),"category":f(r,"category"),"publishedAt":f(r,"published_at")})).collect();
    let pages = if total == 0 {
        0
    } else {
        total.div_ceil(size as usize)
    };
    (
        200,
        json!({"items":items,"page":page,"size":size,"totalPages":pages,"totalElements":total,"hasNext":(page as usize)<pages}),
    )
}
pub fn detail(id: &str, rows: &Value) -> (u16, Value) {
    let id = match id.parse::<i64>() {
        Ok(v) => v,
        Err(_) => return invalid("id", "타입이 올바르지 않습니다."),
    };
    let Some(r) = rows
        .as_array()
        .into_iter()
        .flatten()
        .find(|r| f(r, "id").as_i64() == Some(id) && f(r, "status") == "PUBLISHED")
    else {
        return (
            404,
            json!({"code":"NEWS_NOT_FOUND","message":"해당 뉴스를 찾을 수 없습니다."}),
        );
    };
    let image = f(r, "image_source");
    let image = if image.is_null() {
        json!({"name":"","url":"","author":"","license":"","licenseUrl":"","type":"NONE"})
    } else {
        json!({"name":image.get("name").and_then(Value::as_str).unwrap_or(""),"url":image.get("url").and_then(Value::as_str).unwrap_or(""),"author":image.get("author").and_then(Value::as_str).unwrap_or(""),"license":image.get("license").and_then(Value::as_str).unwrap_or(""),"licenseUrl":image.get("licenseUrl").or_else(||image.get("license_url")).and_then(Value::as_str).unwrap_or(""),"type":image.get("type").and_then(Value::as_str).unwrap_or("NONE")})
    };
    let sources: Vec<Value> = f(r, "sources")
        .as_array()
        .into_iter()
        .flatten()
        .map(|s| json!({"name":f(s,"name"),"url":f(s,"url")}))
        .collect();
    (
        200,
        json!({"id":f(r,"id"),"title":f(r,"title"),"content":f(r,"content"),"imageUrl":f(r,"image_url"),"imageSource":image,"sources":sources,"category":f(r,"category"),"publishedAt":f(r,"published_at")}),
    )
}
