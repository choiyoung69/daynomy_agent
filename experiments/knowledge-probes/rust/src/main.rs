#![forbid(unsafe_code)]

use serde_json::{json, Value};

fn main() {
    let value: Value = serde_json::from_str(r#"{"id":9007199254740993,"currency":null}"#).unwrap();
    let decimal: Value = serde_json::from_str("0.10000000000000000001").unwrap();
    println!("{}", json!({
        "idText": value["id"].to_string(),
        "idAfterF64Text": format!("{:.0}", value["id"].as_f64().unwrap()),
        "decimalLexeme": decimal.to_string(),
        "missingGetIsNone": value.get("missing").is_none(),
        "nullGetIsSome": value.get("currency").is_some(),
        "emojiUtf8Bytes": "😀".len(),
        "emojiScalarCount": "😀".chars().count(),
        "decomposedEqualsComposed": "e\u{301}" == "é"
    }));
}
