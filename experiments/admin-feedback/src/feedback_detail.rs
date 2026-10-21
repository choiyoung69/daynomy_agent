#![forbid(unsafe_code)]

use serde_json::{json, Value};

fn invalid(reason: &str) -> (u16, Value) {
    (
        400,
        json!({
            "code": "INVALID_REQUEST",
            "message": "요청값이 올바르지 않습니다.",
            "errors": [{"field": "id", "reason": reason}]
        }),
    )
}

/// Pure projection of a stored feedback row; authorization belongs to the HTTP layer.
pub fn detail(id: &str, rows: &Value) -> (u16, Value) {
    let id = match id.parse::<i64>() {
        Ok(value) => value,
        Err(_) => return invalid("타입이 올바르지 않습니다."),
    };
    if id <= 0 {
        // Hibernate Validator's Korean default for jakarta.validation.constraints.Positive.
        return invalid("0보다 커야 합니다");
    }
    let row = rows
        .as_array()
        .and_then(|rows| rows.iter().find(|row| row["id"].as_i64() == Some(id)));
    match row {
        Some(row) => (
            200,
            json!({
                "id": row["id"],
                "content": row["content"],
                "pagePath": row["page_path"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"]
            }),
        ),
        None => (
            404,
            json!({"code": "FEEDBACK_NOT_FOUND", "message": "피드백을 찾을 수 없습니다."}),
        ),
    }
}
