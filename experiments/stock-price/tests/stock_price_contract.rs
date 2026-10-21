#![forbid(unsafe_code)]

#[path = "../src/stock_price.rs"]
mod stock_price;

use serde_json::{json, Value};
use stock_price::latest;

fn data(source: &str) -> Value {
    serde_json::from_str(source).expect("계약 fixture는 유효한 JSON이어야 한다")
}

fn not_found() -> Value {
    json!({
        "code": "STOCK_PRICE_NOT_FOUND",
        "message": "주식·ETF 종가를 찾을 수 없습니다."
    })
}

fn invalid_id() -> Value {
    json!({
        "code": "INVALID_REQUEST",
        "message": "요청값이 올바르지 않습니다.",
        "errors": [{
            "field": "assetId",
            "reason": "타입이 올바르지 않습니다."
        }]
    })
}

#[test]
fn returns_exact_success_shape_for_domestic_stock() {
    let fixture = data(r#"{
        "assets":[{"id":1,"asset_code":"005930","name":"삼성전자","market":"KOSPI","category":"STOCK","listed":true}],
        "stock_daily_prices":[{"asset_id":1,"base_date":"2026-03-18","close_price":58400}]
    }"#);

    let (status, body) = latest("1", &fixture);

    assert_eq!(status, 200);
    assert_eq!(body, data(r#"{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-03-18","closePrice":58400,"currency":"KRW"}"#));
    assert_eq!(body.as_object().expect("성공 응답은 객체").len(), 6);
}

#[test]
fn chooses_latest_date_from_unsorted_prices_and_ignores_other_assets() {
    let fixture = data(r#"{
        "assets":[
            {"id":7,"asset_code":"AAPL","name":"Apple","market":"NASDAQ","category":"STOCK","listed":true},
            {"id":8,"asset_code":"MSFT","name":"Microsoft","market":"NASDAQ","category":"STOCK","listed":true}
        ],
        "stock_daily_prices":[
            {"asset_id":7,"base_date":"2026-01-03","close_price":203.25},
            {"asset_id":8,"base_date":"2026-12-31","close_price":999.99},
            {"asset_id":7,"base_date":"2025-12-31","close_price":190.00},
            {"asset_id":7,"base_date":"2026-02-01","close_price":211.75}
        ]
    }"#);

    let (status, body) = latest("7", &fixture);

    assert_eq!(status, 200);
    assert_eq!(body["baseDate"], "2026-02-01");
    assert_eq!(body["closePrice"], data("211.75"));
    assert_eq!(body["assetCode"], "AAPL");
}

#[test]
fn maps_every_us_market_to_usd_without_converting_price() {
    for (id, market) in [
        (11_i64, "NASDAQ"),
        (12, "NYSE"),
        (13, "NYSE_ARCA"),
        (14, "NYSE_AMERICAN"),
        (15, "BATS"),
    ] {
        let fixture = json!({
            "assets": [{"id": id, "asset_code": format!("US{id}"), "name": market, "market": market, "category": "ETF", "listed": true}],
            "stock_daily_prices": [{"asset_id": id, "base_date": "2026-04-09", "close_price": 73}]
        });
        let (status, body) = latest(&id.to_string(), &fixture);
        assert_eq!(status, 200, "market={market}");
        assert_eq!(body["currency"], "USD", "market={market}");
        assert_eq!(body["closePrice"], 73, "market={market}");
    }
}

#[test]
fn maps_kosdaq_and_null_market_to_krw() {
    let fixture = data(r#"{
        "assets":[
            {"id":21,"asset_code":"247540","name":"에코프로비엠","market":"KOSDAQ","category":"STOCK","listed":true},
            {"id":22,"asset_code":"LOCAL","name":"시장 미지정","market":null,"category":"ETF","listed":true}
        ],
        "stock_daily_prices":[
            {"asset_id":22,"base_date":"2026-05-02","close_price":1010},
            {"asset_id":21,"base_date":"2026-05-02","close_price":98000}
        ]
    }"#);

    let (kosdaq_status, kosdaq) = latest("21", &fixture);
    let (null_status, null_market) = latest("22", &fixture);

    assert_eq!((kosdaq_status, &kosdaq["currency"]), (200, &json!("KRW")));
    assert_eq!((null_status, &null_market["currency"]), (200, &json!("KRW")));
}

#[test]
fn returns_stored_price_for_delisted_etf() {
    let fixture = data(r#"{
        "assets":[{"id":31,"asset_code":"OLD","name":"상장폐지 ETF","market":"NYSE_ARCA","category":"ETF","listed":false}],
        "stock_daily_prices":[{"asset_id":31,"base_date":"2020-07-17","close_price":12.50}]
    }"#);

    let (status, body) = latest("31", &fixture);

    assert_eq!(status, 200);
    assert_eq!(body["name"], "상장폐지 ETF");
    assert_eq!(body["baseDate"], "2020-07-17");
    assert_eq!(body["currency"], "USD");
}

#[test]
fn existing_asset_without_price_returns_exact_404_without_errors() {
    let fixture = data(r#"{
        "assets":[{"id":41,"asset_code":"EMPTY","name":"가격 없음","market":"KOSPI","category":"STOCK","listed":true}],
        "stock_daily_prices":[{"asset_id":42,"base_date":"2026-01-01","close_price":1}]
    }"#);

    let (status, body) = latest("41", &fixture);

    assert_eq!(status, 404);
    assert_eq!(body, not_found());
    assert!(body.get("errors").is_none());
}

#[test]
fn nonexistent_asset_returns_same_exact_404() {
    let fixture = data(r#"{
        "assets":[{"id":51,"asset_code":"KNOWN","name":"Known","market":"NYSE","category":"STOCK","listed":true}],
        "stock_daily_prices":[{"asset_id":999,"base_date":"2026-01-01","close_price":77}]
    }"#);

    let (status, body) = latest("999", &fixture);

    assert_eq!((status, body), (404, not_found()));
}

#[test]
fn accepts_signed_decimal_leading_zero_and_i64_max_paths() {
    let fixture = data(r#"{
        "assets":[{"id":9223372036854775807,"asset_code":"MAX","name":"Max Id","market":null,"category":"STOCK","listed":true}],
        "stock_daily_prices":[{"asset_id":9223372036854775807,"base_date":"2026-06-30","close_price":1}]
    }"#);

    for spelling in ["9223372036854775807", "+9223372036854775807", "09223372036854775807"] {
        let (status, body) = latest(spelling, &fixture);
        assert_eq!(status, 200, "path spelling={spelling}");
        assert_eq!(body["assetId"], json!(9223372036854775807_i64));
    }
}

#[test]
fn zero_and_negative_ids_are_valid_types_but_not_found() {
    let fixture = data(r#"{"assets":[],"stock_daily_prices":[]}"#);

    for id in ["0", "-1", "-9223372036854775808", "+0", "000"] {
        let (status, body) = latest(id, &fixture);
        assert_eq!((status, body), (404, not_found()), "id={id}");
    }
}

#[test]
fn rejects_non_integer_and_out_of_i64_range_ids_with_exact_400() {
    let fixture = data(r#"{"assets":[],"stock_daily_prices":[]}"#);

    for id in ["abc", "1.0", "9223372036854775808", "-9223372036854775809"] {
        let (status, body) = latest(id, &fixture);
        assert_eq!(status, 400, "id={id}");
        assert_eq!(body, invalid_id(), "id={id}");
    }
}

#[test]
fn preserves_arbitrary_precision_decimal_as_json_number() {
    let fixture = data(r#"{
        "assets":[{"id":61,"asset_code":"PRECISE","name":"Precision","market":"NASDAQ","category":"STOCK","listed":true}],
        "stock_daily_prices":[{"asset_id":61,"base_date":"2026-08-20","close_price":12345678901234567890.123456789012345678901234567890}]
    }"#);
    let expected_number = data("12345678901234567890.123456789012345678901234567890");

    let (status, body) = latest("61", &fixture);

    assert_eq!(status, 200);
    assert!(body["closePrice"].is_number());
    assert_eq!(body["closePrice"], expected_number);
}
