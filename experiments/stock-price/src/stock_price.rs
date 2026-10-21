use serde_json::{Value, json};

fn not_found() -> (u16, Value) {
    (
        404,
        json!({
            "code": "STOCK_PRICE_NOT_FOUND",
            "message": "주식·ETF 종가를 찾을 수 없습니다."
        }),
    )
}

pub fn latest(asset_id: &str, data: &Value) -> (u16, Value) {
    let Ok(asset_id) = asset_id.parse::<i64>() else {
        return (
            400,
            json!({
                "code": "INVALID_REQUEST",
                "message": "요청값이 올바르지 않습니다.",
                "errors": [{
                    "field": "assetId",
                    "reason": "타입이 올바르지 않습니다."
                }]
            }),
        );
    };

    let Some(assets) = data.get("assets").and_then(Value::as_array) else {
        return not_found();
    };
    let Some(asset) = assets
        .iter()
        .find(|asset| asset.get("id").and_then(Value::as_i64) == Some(asset_id))
    else {
        return not_found();
    };
    let Some(prices) = data.get("stock_daily_prices").and_then(Value::as_array) else {
        return not_found();
    };
    // Database dates have YYYY-MM-DD form, so their lexical order is chronological.
    let Some((base_date, price)) = prices
        .iter()
        .filter(|price| price.get("asset_id").and_then(Value::as_i64) == Some(asset_id))
        .filter_map(|price| {
            price
                .get("base_date")
                .and_then(Value::as_str)
                .map(|date| (date, price))
        })
        .max_by(|(left, _), (right, _)| left.cmp(right))
    else {
        return not_found();
    };

    let currency = match asset.get("market").and_then(Value::as_str) {
        Some("NASDAQ" | "NYSE" | "NYSE_ARCA" | "NYSE_AMERICAN" | "BATS") => "USD",
        _ => "KRW",
    };

    (
        200,
        json!({
            "assetId": asset_id,
            "assetCode": asset["asset_code"],
            "name": asset["name"],
            "baseDate": base_date,
            "closePrice": price["close_price"],
            "currency": currency
        }),
    )
}
