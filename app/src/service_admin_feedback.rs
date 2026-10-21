#![forbid(unsafe_code)]
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query, rows};
use serde_json::{Value, json};
use tokio_postgres::Client;

fn missing() -> ApiFault {
    fault(404, "FEEDBACK_NOT_FOUND", "피드백을 찾을 수 없습니다.")
}
fn invalid_body() -> ApiFault {
    fault(400, "INVALID_REQUEST", "요청값이 올바르지 않습니다.")
}
fn page(raw: &str) -> Result<(i64, i64), ApiFault> {
    let q = query(raw)?;
    let bind = |key: &str, default: i64| -> Result<i64, ApiFault> {
        let Some(raw) = q.get(key).filter(|v| !v.is_empty()) else {
            return Ok(default);
        };
        crate::java_binding::integer(raw)
            .filter(|v| i32::try_from(*v).is_ok())
            .ok_or_else(|| invalid(key, "타입이 올바르지 않습니다."))
    };
    let p = bind("page", 1)?;
    let s = bind("size", 15)?;
    let mut errors = vec![];
    if p < 1 {
        errors.push(json!({"field":"page","reason":"페이지 번호는 1 이상이어야 합니다."}));
    }
    if s < 1 {
        errors.push(json!({"field":"size","reason":"페이지 크기는 1 이상이어야 합니다."}));
    }
    if s > 100 {
        errors.push(json!({"field":"size","reason":"페이지 크기는 100 이하여야 합니다."}));
    }
    if !errors.is_empty() {
        return Err(ApiFault {
            status: 400,
            body: json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":errors}),
        });
    }
    Ok((p, s))
}
fn ident(raw: &str) -> Result<i64, ApiFault> {
    let encoded = raw
        .replace('+', "%2B")
        .replace('&', "%26")
        .replace('=', "%3D");
    let decoded = query(&format!("id={encoded}"))?;
    let id = decoded
        .get("id")
        .and_then(|v| crate::java_binding::integer(v))
        .ok_or_else(|| invalid("id", "타입이 올바르지 않습니다."))?;
    if id <= 0 {
        return Err(invalid("id", "0보다 커야 합니다"));
    }
    Ok(id)
}
const DTO: &str = "jsonb_build_object('id',id,'content',content,'pagePath',page_path,'status',status,'createdAt',rtrim(rtrim(to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US'),'0'),'.')||'Z','updatedAt',rtrim(rtrim(to_char(updated_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US'),'0'),'.')||'Z')";
async fn one(id: i64, db: &Client) -> Result<Value, ApiFault> {
    rows(
        db,
        &format!("SELECT ({DTO})::text FROM feedbacks WHERE id=$1"),
        &[&id],
    )
    .await?
    .pop()
    .ok_or_else(missing)
}
pub async fn handle(
    method: &str,
    path: &str,
    raw: &str,
    body: &[u8],
    db: &Client,
) -> Option<Outcome> {
    if path != "/api/admin/feedbacks" && !path.starts_with("/api/admin/feedbacks/") {
        return None;
    }
    Some(dispatch(method, path, raw, body, db).await)
}
async fn dispatch(method: &str, path: &str, raw: &str, body: &[u8], db: &Client) -> Outcome {
    if path == "/api/admin/feedbacks" {
        if method != "GET" {
            return Err(fault(
                405,
                "METHOD_NOT_ALLOWED",
                "지원하지 않는 HTTP 메서드입니다.",
            ));
        }
        let (p, s) = page(raw)?;
        let offset = (p - 1) * s;
        let sql = format!(
            "WITH selected AS (SELECT * FROM feedbacks ORDER BY created_at DESC,id DESC LIMIT $1 OFFSET $2), totals AS (SELECT count(*) n FROM feedbacks) SELECT jsonb_build_object('items',(SELECT coalesce(jsonb_agg({DTO} ORDER BY created_at DESC,id DESC),'[]'::jsonb) FROM selected),'page',$3::bigint,'size',$1::bigint,'totalPages',(n+$1-1)/$1,'totalElements',n,'hasNext',$3::bigint<(n+$1-1)/$1)::text FROM totals"
        );
        return Ok((
            200,
            rows(db, &sql, &[&s, &offset, &p])
                .await?
                .pop()
                .ok_or_else(internal)?,
        ));
    }
    let id = ident(path.trim_start_matches("/api/admin/feedbacks/"))?;
    match method {
        "GET" => Ok((200, one(id, db).await?)),
        "DELETE" => {
            if db
                .execute("DELETE FROM feedbacks WHERE id=$1", &[&id])
                .await
                .map_err(|_| internal())?
                == 0
            {
                return Err(missing());
            }
            Ok((204, Value::Null))
        }
        "PATCH" => {
            let value: Value = serde_json::from_slice(body).map_err(|_| invalid_body())?;
            if !value.is_object() {
                return Err(invalid_body());
            }
            let status = value
                .get("status")
                .filter(|v| !v.is_null())
                .ok_or_else(|| invalid("status", "피드백 상태를 선택해주세요."))?
                .as_str()
                .filter(|s| matches!(*s, "PENDING" | "RESOLVED"))
                .ok_or_else(invalid_body)?;
            let sql = format!(
                "UPDATE feedbacks SET status=$2::text,updated_at=CASE WHEN status IS DISTINCT FROM $2::text THEN clock_timestamp() ELSE updated_at END WHERE id=$1 RETURNING ({DTO})::text"
            );
            let value = rows(db, &sql, &[&id, &status])
                .await?
                .pop()
                .ok_or_else(missing)?;
            Ok((200, value))
        }
        _ => Err(fault(
            405,
            "METHOD_NOT_ALLOWED",
            "지원하지 않는 HTTP 메서드입니다.",
        )),
    }
}
