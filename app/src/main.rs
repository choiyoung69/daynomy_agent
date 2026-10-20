#![forbid(unsafe_code)]

mod csrf;
mod feedback;

use feedback::ApiError;
use http_body_util::{BodyExt, Full, Limited};
use hyper::body::{Bytes, Incoming};
use hyper::header::{CACHE_CONTROL, CONTENT_TYPE, HeaderValue, SET_COOKIE};
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Method, Request, Response, StatusCode};
use hyper_util::rt::{TokioIo, TokioTimer};
use serde::Serialize;
use serde_json::json;
use std::convert::Infallible;
use std::env;
use std::net::{Ipv4Addr, SocketAddr};
use std::sync::Arc;
use std::time::Duration;
use tokio::net::TcpListener;
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tokio_postgres::{Client, NoTls};

type Reply = Response<Full<Bytes>>;
const MAX_BODY_BYTES: usize = 64 * 1024;

fn json_reply(status: StatusCode, value: impl Serialize) -> Reply {
    // Only our own JSON objects/structs reach this function; never serialize DB errors.
    let body = serde_json::to_vec(&value).expect("response consists only of JSON-safe fields");
    let mut response = Response::new(Full::new(Bytes::from(body)));
    *response.status_mut() = status;
    response
        .headers_mut()
        .insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
    response
        .headers_mut()
        .insert(CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

fn error_reply(status: StatusCode, code: &'static str, message: &'static str) -> Reply {
    json_reply(status, ApiError::new(code, message))
}

async fn handle(request: Request<Incoming>, db: Arc<Client>) -> Result<Reply, Infallible> {
    let path = request.uri().path();
    if path == "/api/auth/csrf" && request.method() == Method::GET {
        let token = csrf::issue(request.headers());
        let mut response = json_reply(
            StatusCode::OK,
            json!({
                "headerName":csrf::HEADER, "parameterName":"_csrf", "token":token
            }),
        );
        // Local HTTP pilot. No Domain attribute; HttpOnly=false matches the reference.
        let cookie = format!("{}={token}; Path=/; SameSite=Lax", csrf::COOKIE);
        response.headers_mut().insert(
            SET_COOKIE,
            HeaderValue::from_str(&cookie).expect("UUID cookie is a valid header"),
        );
        return Ok(response);
    }
    if path != "/api/feedback" {
        let status = if path == "/api/auth/csrf" {
            StatusCode::METHOD_NOT_ALLOWED
        } else {
            StatusCode::NOT_FOUND
        };
        return Ok(error_reply(
            status,
            "NOT_FOUND_OR_METHOD_NOT_ALLOWED",
            "지원하지 않는 요청입니다.",
        ));
    }
    if request.method() != Method::POST {
        return Ok(error_reply(
            StatusCode::METHOD_NOT_ALLOWED,
            "METHOD_NOT_ALLOWED",
            "지원하지 않는 요청입니다.",
        ));
    }
    // Public endpoint does not mean CSRF-exempt.
    if !csrf::valid(request.headers()) {
        return Ok(error_reply(
            StatusCode::FORBIDDEN,
            "FORBIDDEN",
            "접근 권한이 없습니다.",
        ));
    }
    let json_content = request
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|h| h.to_str().ok())
        .is_some_and(|s| {
            s.split(';')
                .next()
                .unwrap_or("")
                .trim()
                .eq_ignore_ascii_case("application/json")
        });
    if !json_content {
        return Ok(error_reply(
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_MEDIA_TYPE",
            "JSON 요청이 필요합니다.",
        ));
    }
    let body = match tokio::time::timeout(
        Duration::from_secs(5),
        Limited::new(request.into_body(), MAX_BODY_BYTES).collect(),
    )
    .await
    {
        Ok(Ok(body)) => body.to_bytes(),
        Ok(Err(_)) => {
            return Ok(json_reply(
                StatusCode::BAD_REQUEST,
                ApiError::unreadable_body(),
            ));
        }
        Err(_) => {
            return Ok(error_reply(
                StatusCode::REQUEST_TIMEOUT,
                "REQUEST_TIMEOUT",
                "요청 시간이 초과되었습니다.",
            ));
        }
    };
    let input = match feedback::parse(&body) {
        Ok(input) => input,
        Err(error) => return Ok(json_reply(StatusCode::BAD_REQUEST, error)),
    };
    // One parameterized statement is atomic. The server-side statement timeout is configured at startup.
    let saved = db
        .query_one(
            "INSERT INTO feedbacks (content,page_path,status,created_at,updated_at) \
         VALUES ($1,$2,'PENDING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING id",
            &[&input.content, &input.page_path],
        )
        .await;
    match saved {
        Ok(row) => {
            let id: i64 = row.get(0);
            eprintln!("event=feedback.created feedback_id={id}");
            let mut response = Response::new(Full::new(Bytes::new()));
            *response.status_mut() = StatusCode::NO_CONTENT;
            Ok(response)
        }
        Err(_) => {
            eprintln!("event=feedback.save_failed");
            Ok(error_reply(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_SERVER_ERROR",
                "서버 내부 오류가 발생했습니다.",
            ))
        }
    }
}

async fn run() -> Result<(), &'static str> {
    let database_url = env::var("DATABASE_URL").map_err(|_| "DATABASE_URL is required")?;
    let port: u16 = env::var("PORT")
        .unwrap_or_else(|_| "8080".into())
        .parse()
        .map_err(|_| "PORT must be a valid port number")?;
    let mut config: tokio_postgres::Config = database_url
        .parse()
        .map_err(|_| "Invalid DB configuration")?;
    config.connect_timeout(Duration::from_secs(5));
    config.options("-c statement_timeout=5000");
    let (client, connection) = config
        .connect(NoTls)
        .await
        .map_err(|_| "Database connection failed")?;
    let db_task = tokio::spawn(async move {
        if connection.await.is_err() {
            eprintln!("event=database.connection_failed");
        }
    });
    client
        .simple_query("SELECT id FROM feedbacks LIMIT 0")
        .await
        .map_err(
            |_| "Feedback schema is missing/inaccessible; apply migrations/001_feedbacks.sql",
        )?;
    let db = Arc::new(client);
    let listener = TcpListener::bind(SocketAddr::from((Ipv4Addr::LOCALHOST, port)))
        .await
        .map_err(|_| "Cannot bind HTTP port")?;
    eprintln!(
        "event=server.started address={}",
        listener.local_addr().map_err(|_| "Cannot read port")?
    );
    let limit = Arc::new(Semaphore::new(64));
    let mut connections = JoinSet::new();
    let mut terminate = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .map_err(|_| "Cannot register termination signal")?;
    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => break,
            _ = terminate.recv() => break,
            Some(_) = connections.join_next(), if !connections.is_empty() => {},
            accepted = listener.accept() => {
                let (stream, _) = accepted.map_err(|_| "HTTP accept failed")?;
                let Ok(permit) = Arc::clone(&limit).try_acquire_owned() else { continue };
                let db = Arc::clone(&db);
                connections.spawn(async move {
                    let _permit = permit;
                    let mut builder = http1::Builder::new();
                    builder.keep_alive(false).timer(TokioTimer::new())
                        .header_read_timeout(Duration::from_secs(5));
                    if builder.serve_connection(TokioIo::new(stream),
                        service_fn(move |request| handle(request, Arc::clone(&db))))
                        .await.is_err() {
                        eprintln!("event=http.connection_failed");
                    }
                });
            }
        }
    }
    // Accepted requests finish before shutdown; keep-alive is disabled for this small pilot.
    let _ = tokio::time::timeout(Duration::from_secs(15), async {
        while connections.join_next().await.is_some() {}
    })
    .await;
    connections.abort_all();
    drop(db);
    db_task.abort();
    eprintln!("event=server.stopped");
    Ok(())
}

#[tokio::main]
async fn main() {
    if let Err(message) = run().await {
        eprintln!("Startup failed: {message}");
        std::process::exit(1);
    }
}
