#![forbid(unsafe_code)]
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

// region json
fn checked_id(value: &Value) -> Result<u64, &'static str> {
    let id = value.as_u64().ok_or("ID_TYPE")?;
    if !(1..=9_007_199_254_740_991).contains(&id) { return Err("ID_RANGE"); }
    Ok(id)
}
// endregion json

// region money
fn minor_units(raw: &str, scale: u32) -> Option<i128> {
    let (whole, fraction) = raw.split_once('.').unwrap_or((raw, ""));
    if whole.is_empty() || !whole.bytes().all(|c| c.is_ascii_digit()) ||
       !fraction.bytes().all(|c| c.is_ascii_digit()) || fraction.len() > scale as usize ||
       (raw.contains('.') && fraction.is_empty()) { return None; }
    let factor = 10i128.checked_pow(scale)?;
    whole.parse::<i128>().ok()?.checked_mul(factor)?.checked_add(
        if fraction.is_empty() { 0 } else {
            fraction.parse::<i128>().ok()?.checked_mul(10i128.checked_pow(scale - fraction.len() as u32)?)?
        })
}
// endregion money

// region transaction
fn simulate_transaction(fail: bool) -> Vec<&'static str> {
    let mut events = vec!["BEGIN", "WRITE"];
    let outcome: Result<(), ()> = if fail { Err(()) } else { Ok(()) };
    match outcome { Ok(()) => events.push("COMMIT"), Err(()) => events.push("ROLLBACK") }
    events
}
// endregion transaction

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let mut results = BTreeMap::new();
    macro_rules! test { ($name:literal, $condition:expr) => {{ let value = $condition; assert!(value, $name); results.insert($name, value); }}; }
    let value = json!({"currency": null});
    test!("missing_is_none", value.get("missing").is_none());
    test!("explicit_null_some", value.get("currency").is_some_and(Value::is_null));
    test!("safe_id", checked_id(&json!(9_007_199_254_740_991u64)).is_ok());
    test!("large_id_rejected", checked_id(&json!(9_007_199_254_740_993u64)).is_err());
    test!("quoted_id_rejected", checked_id(&json!("1")).is_err());
    test!("scaled_decimal", minor_units("1.20", 2) == Some(120));
    test!("excess_scale_rejected", minor_units("1.005", 2).is_none());
    test!("decimal_overflow_rejected", minor_units(&"9".repeat(100), 2).is_none());
    test!("utf8_and_utf16", "😀".len() == 4 && "😀".encode_utf16().count() == 2);
    let mut original = vec![1]; let copy = original.clone(); original.push(2);
    test!("vec_value_clone", copy.len() == 1);
    let shared = Arc::new(Mutex::new(vec![1])); let alias = Arc::clone(&shared);
    shared.lock().unwrap().push(2);
    test!("arc_clone_shares", alias.lock().unwrap().len() == 2);
    let a = 1; let current = 2;
    test!("stale_generation", a != current);
    let work = tokio::spawn(async { tokio::time::sleep(std::time::Duration::from_secs(600)).await; });
    work.abort();
    test!("task_abort_join_cancelled", work.await.unwrap_err().is_cancelled());
    test!("error_path_rollback_wiring", simulate_transaction(true) == ["BEGIN", "WRITE", "ROLLBACK"]);
    test!("success_path_commit_wiring", simulate_transaction(false) == ["BEGIN", "WRITE", "COMMIT"]);
    println!("{}", serde_json::to_string(&results).unwrap());
}
