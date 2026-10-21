#![forbid(unsafe_code)]

mod stock_price;

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

async fn rows(db: &Client, table: &str) -> Result<Value, ()> {
    let query = match table {
        "assets" => "SELECT to_jsonb(t)::text FROM assets t ORDER BY id",
        "stock_daily_prices" => {
            "SELECT to_jsonb(t)::text FROM stock_daily_prices t ORDER BY asset_id,base_date"
        }
        _ => return Err(()),
    };
    let mut values = Vec::new();
    for row in db.query(query, &[]).await.map_err(|_| ())? {
        let text: String = row.get(0);
        values.push(serde_json::from_str::<Value>(&text).map_err(|_| ())?);
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

async fn handle(
    request: Request<Incoming>,
    db: Arc<Client>,
) -> Result<Response<Full<Bytes>>, Infallible> {
    let path = request.uri().path();
    let Some(id) = path
        .strip_prefix("/api/stocks/")
        .and_then(|p| p.strip_suffix("/price"))
    else {
        return Ok(reply(404, json!({"code":"NOT_FOUND"})));
    };
    if request.method() != Method::GET {
        return Ok(reply(405, json!({"code":"METHOD_NOT_ALLOWED"})));
    }
    let mut data = serde_json::Map::new();
    for table in ["assets", "stock_daily_prices"] {
        match rows(&db, table).await {
            Ok(value) => {
                data.insert(table.to_owned(), value);
            }
            Err(()) => {
                return Ok(reply(
                    500,
                    json!({"code":"INTERNAL_SERVER_ERROR","message":"서버 내부 오류가 발생했습니다."}),
                ));
            }
        }
    }
    let (status, body) = stock_price::latest(id, &Value::Object(data));
    Ok(reply(status, body))
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
