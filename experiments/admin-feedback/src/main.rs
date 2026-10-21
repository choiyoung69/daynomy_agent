#![forbid(unsafe_code)]

mod feedback_list;
mod feedback_detail;
#[allow(dead_code)]
mod api;
#[allow(dead_code)]
mod service_auth;
mod csrf;

use http_body_util::Full;
use hyper::body::{Bytes, Incoming};
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Method, Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use serde_json::{Value, json};
use std::convert::Infallible;
use std::sync::Arc;
use tokio_postgres::{Client, NoTls};

async fn rows(db:&Client)->Result<Value,()> {
 let mut values=Vec::new();
 for row in db.query("SELECT to_jsonb(t)::text FROM feedbacks t",&[]).await.map_err(|_|())? {
  let text:String=row.get(0); values.push(serde_json::from_str::<Value>(&text).map_err(|_|())?);
 }
 Ok(Value::Array(values))
}

fn reply(status: u16, body: Value) -> Response<Full<Bytes>> {
    Response::builder()
        .status(StatusCode::from_u16(status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR))
        .header("Content-Type", "application/json")
        .header("Cache-Control", "no-store")
        .body(Full::new(Bytes::from(
            serde_json::to_vec(&body).expect("JSON response"),
        )))
        .expect("valid response")
}

// URI paths use percent escaping, not form encoding: '+' stays literal.
// Spring resolves @PathVariable after a single UTF-8 path decode.
fn decoded_path_segment(raw: &str) -> Option<String> {
    let bytes = raw.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' {
            let high = char::from(*bytes.get(index + 1)?).to_digit(16)?;
            let low = char::from(*bytes.get(index + 2)?).to_digit(16)?;
            decoded.push((high * 16 + low) as u8);
            index += 3;
        } else {
            decoded.push(bytes[index]);
            index += 1;
        }
    }
    String::from_utf8(decoded).ok()
}

async fn handle(request:Request<Incoming>,db:Arc<Client>)->Result<Response<Full<Bytes>>,Infallible>{
 let path=request.uri().path();
 if path=="/api/auth/csrf" && request.method()==Method::GET {
  let token=csrf::issue(request.headers());return Ok(reply(200,json!({"token":token,"headerName":"X-XSRF-TOKEN","parameterName":"_csrf"})));
 }
 if path!="/api/admin/feedbacks" && !path.starts_with("/api/admin/feedbacks/"){return Ok(reply(404,json!({"code":"NOT_FOUND"})));}
 let principal=match service_auth::authenticate(request.headers(),&db).await {
  Ok(Some(p))=>p,
  Ok(None)=>return Ok(reply(401,json!({"code":"UNAUTHORIZED","message":"로그인이 필요합니다."}))),
  Err(e)=>return Ok(reply(e.status,e.body)),
 };
 if principal.role!="ADMIN"{return Ok(reply(403,json!({"code":"FORBIDDEN","message":"접근 권한이 없습니다."})));}
 if request.method()!=Method::GET{return Ok(reply(405,json!({"code":"METHOD_NOT_ALLOWED"})));}
 let data=match rows(&db).await {Ok(d)=>d,Err(())=>return Ok(reply(500,json!({"code":"INTERNAL_SERVER_ERROR","message":"서버 내부 오류가 발생했습니다."})))};
 let(status,body)=if path=="/api/admin/feedbacks" { feedback_list::list(request.uri().query().unwrap_or(""),&data) }
 else {
  let raw=path.strip_prefix("/api/admin/feedbacks/").expect("validated feedback route");
  let Some(id)=decoded_path_segment(raw) else {
   return Ok(reply(400,json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":[{"field":"id","reason":"타입이 올바르지 않습니다."}]})));
  };
  feedback_detail::detail(&id,&data)
 };
 Ok(reply(status,body))
}

#[tokio::main]
async fn main() {
    let url = std::env::var("DATABASE_URL").expect("DATABASE_URL is required");
    let mut config: tokio_postgres::Config = url.parse().expect("DB configuration");
    config.options("-c statement_timeout=5000");
    config.connect_timeout(std::time::Duration::from_secs(5));
    let (client, connection) = config.connect(NoTls).await.expect("test DB connection");
    tokio::spawn(async move {
        let _ = connection.await;
    });
    let db = Arc::new(client);
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "0".to_owned())
        .parse()
        .expect("port");
    let listener = tokio::net::TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, port))
        .await
        .expect("bind");
    eprintln!(
        "event=server.started address={}",
        listener.local_addr().expect("local address")
    );
    let mut terminate =
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()).expect("signal");
    loop {
        tokio::select! {
            _ = terminate.recv() => break,
            accepted = listener.accept() => {
                let (stream, _) = accepted.expect("accept");
                let db = Arc::clone(&db);
                tokio::spawn(async move {
                    let _ = http1::Builder::new().keep_alive(false)
                        .serve_connection(TokioIo::new(stream), service_fn(move |r| handle(r, Arc::clone(&db)))).await;
                });
            }
        }
    }
}

#[cfg(test)]
mod path_adapter_tests {
    use super::decoded_path_segment;

    #[test]
    fn numeric_path_forms_reach_detail_decoded() {
        for (raw, expected) in [
            ("%2B941001", "+941001"), ("%23E5BC9", "#E5BC9"),
            ("-%231", "-#1"), ("%EF%BC%99%EF%BC%94%EF%BC%91%EF%BC%90%EF%BC%90%EF%BC%91", "９４１００１"),
            ("%D9%A9%D9%A4%D9%A1%D9%A0%D9%A0%D9%A1", "٩٤١٠٠١"),
            ("9%2041001", "9 41001"), ("%09941001%09", "\t941001\t"),
            ("%E2%80%83941001%E2%80%83", "\u{2003}941001\u{2003}"),
        ] {
            assert_eq!(decoded_path_segment(raw).as_deref(), Some(expected));
        }
    }

    #[test]
    fn path_plus_is_preserved_and_percent_decoding_occurs_once() {
        assert_eq!(decoded_path_segment("+941001").as_deref(), Some("+941001"));
        assert_eq!(decoded_path_segment("%252B941001").as_deref(), Some("%2B941001"));
        assert_eq!(decoded_path_segment("%2b941001").as_deref(), Some("+941001"));
    }

    #[test]
    fn malformed_escapes_and_invalid_utf8_are_rejected() {
        for raw in ["%", "%2", "%GG", "%FF", "%C0%AF"] {
            assert_eq!(decoded_path_segment(raw), None);
        }
    }
}
