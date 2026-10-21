#![forbid(unsafe_code)]

mod api;
mod csrf;
mod feedback;
mod java_binding;
mod multipart;
mod service_admin_content;
mod service_admin_feedback;
mod service_admin_news;
mod service_analysis;
mod service_auth;
mod service_calendar;
mod service_dart;
mod service_discovery;
mod service_market;
mod service_media;
mod service_portfolio;
mod service_schedule;
mod service_social;
mod service_sync;

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

fn protected(path: &str) -> bool {
    path.starts_with("/api/admin/")
        || path.starts_with("/api/users/")
        || path.starts_with("/api/v1/users/")
        || path.starts_with("/api/v2/users/")
        || ((path == "/api/portfolio" || path.starts_with("/api/portfolio/"))
            && !matches!(path, "/api/portfolio/calculate" | "/api/portfolio/analysis"))
}

fn outcome_reply(result: api::Outcome) -> Reply {
    let (status, body) = match result {
        Ok(pair) => pair,
        Err(error) => (error.status, error.body),
    };
    if status == 204 {
        let mut response = Response::new(Full::new(Bytes::new()));
        *response.status_mut() = StatusCode::NO_CONTENT;
        response
    } else {
        json_reply(
            StatusCode::from_u16(status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
            body,
        )
    }
}

async fn private_request(request: Request<Incoming>, config: Arc<tokio_postgres::Config>) -> Reply {
    let path = request.uri().path().to_owned();
    let query = request.uri().query().unwrap_or("").to_owned();
    let auth_path = request
        .uri()
        .path_and_query()
        .map(|p| p.as_str())
        .unwrap_or(&path)
        .to_owned();
    let method = request.method().as_str().to_owned();
    let headers = request.headers().clone();
    let unsafe_method = matches!(method.as_str(), "POST" | "PATCH" | "PUT" | "DELETE");
    let guest_analysis = path == "/api/portfolio/analysis"
        && !headers
            .get_all(hyper::header::COOKIE)
            .iter()
            .filter_map(|v| v.to_str().ok())
            .flat_map(|v| v.split(';'))
            .any(|pair| {
                pair.trim()
                    .split_once('=')
                    .is_some_and(|(name, _)| name == "access_token")
            });
    if unsafe_method && !guest_analysis && !csrf::valid(&headers) {
        return outcome_reply(Err(api::fault(403, "FORBIDDEN", "접근 권한이 없습니다.")));
    }
    let (db, connection) = match config.connect(NoTls).await {
        Ok(pair) => pair,
        Err(_) => return outcome_reply(Err(api::internal())),
    };
    tokio::spawn(async move {
        if connection.await.is_err() {
            eprintln!("event=database.connection_failed");
        }
    });
    let timezone = env::var("APP_TIMEZONE").unwrap_or_else(|_| "Asia/Seoul".to_owned());
    if db
        .query_one("SELECT set_config('TimeZone',$1,false)", &[&timezone])
        .await
        .is_err()
    {
        return outcome_reply(Err(api::internal()));
    }
    let principal = match service_auth::authenticate(&headers, &db).await {
        Ok(principal) => principal,
        Err(error) if protected(&path) || error.status != 401 => return outcome_reply(Err(error)),
        Err(_) => None,
    };
    if protected(&path) && principal.is_none() {
        return outcome_reply(Err(api::fault(401, "UNAUTHORIZED", "로그인이 필요합니다.")));
    }
    if path.starts_with("/api/admin/") && principal.as_ref().is_some_and(|p| p.role != "ADMIN") {
        return outcome_reply(Err(api::fault(403, "FORBIDDEN", "접근 권한이 없습니다.")));
    }
    let mut body = Bytes::new();
    let news_mutation = (method == "POST" && path == "/api/admin/news")
        || (method == "PUT" && path.starts_with("/api/admin/news/"));
    let mut uploaded_image = None;
    if unsafe_method {
        body = match tokio::time::timeout(
            Duration::from_secs(5),
            Limited::new(
                request.into_body(),
                if news_mutation {
                    6 * 1024 * 1024
                } else {
                    MAX_BODY_BYTES
                },
            )
            .collect(),
        )
        .await
        {
            Ok(Ok(body)) => body.to_bytes(),
            Ok(Err(_)) => return json_reply(StatusCode::BAD_REQUEST, ApiError::unreadable_body()),
            Err(_) => {
                return error_reply(
                    StatusCode::REQUEST_TIMEOUT,
                    "REQUEST_TIMEOUT",
                    "요청 시간이 초과되었습니다.",
                );
            }
        };
        if !body.is_empty()
            && !news_mutation
            && matches!(method.as_str(), "POST" | "PUT" | "PATCH")
            && !path.starts_with("/api/auth/")
            && !headers
                .get(CONTENT_TYPE)
                .and_then(|v| v.to_str().ok())
                .is_some_and(|v| {
                    v.split(';')
                        .next()
                        .unwrap_or("")
                        .trim()
                        .eq_ignore_ascii_case("application/json")
                })
        {
            return error_reply(
                StatusCode::UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                "JSON 요청이 필요합니다.",
            );
        }
        if news_mutation {
            let content_type = headers
                .get(CONTENT_TYPE)
                .and_then(|v| v.to_str().ok())
                .unwrap_or("");
            match multipart::news(content_type, &body) {
                Ok((json, image)) => {
                    body = Bytes::from(json);
                    uploaded_image = image;
                }
                Err(error) => return outcome_reply(Err(error)),
            }
        }
    }
    if let Some(result) = service_auth::handle(
        &method,
        &auth_path,
        &body,
        &headers,
        principal.as_ref(),
        &db,
    )
    .await
    {
        return match result {
            Err(error) => outcome_reply(Err(error)),
            Ok(reply) => {
                let mut response = outcome_reply(Ok((reply.status, reply.body)));
                for (name, value) in reply.headers {
                    let Ok(name) = hyper::header::HeaderName::from_bytes(name.as_bytes()) else {
                        return outcome_reply(Err(api::internal()));
                    };
                    let Ok(value) = HeaderValue::from_str(&value) else {
                        return outcome_reply(Err(api::internal()));
                    };
                    response.headers_mut().append(name, value);
                }
                response
            }
        };
    }
    if let Some(result) = service_sync::handle(&method, &path, &query, &body, &db).await {
        return outcome_reply(result);
    }
    if let Some(result) =
        service_admin_news::handle(&method, &path, &query, &body, uploaded_image.as_ref(), &db)
            .await
    {
        return outcome_reply(result);
    }
    if let Some(result) = service_admin_feedback::handle(&method, &path, &query, &body, &db).await {
        return outcome_reply(result);
    }
    if let Some(result) = service_admin_content::handle(&method, &path, &query, &body, &db).await {
        return outcome_reply(result);
    }
    if let Some(result) = service_analysis::handle(
        &method,
        &path,
        &query,
        &body,
        principal.as_ref(),
        &headers,
        &db,
    )
    .await
    {
        return match result {
            Err(error) => outcome_reply(Err(error)),
            Ok(reply) => {
                let mut response = outcome_reply(Ok((reply.status, reply.body)));
                for (name, value) in reply.headers {
                    let Ok(name) = hyper::header::HeaderName::from_bytes(name.as_bytes()) else {
                        return outcome_reply(Err(api::internal()));
                    };
                    let Ok(value) = HeaderValue::from_str(&value) else {
                        return outcome_reply(Err(api::internal()));
                    };
                    response.headers_mut().append(name, value);
                }
                response
            }
        };
    }
    if let Some(result) =
        service_calendar::handle(&method, &path, &query, &body, principal.as_ref(), &db).await
    {
        return outcome_reply(result);
    }
    if let Some(principal) = principal
        && let Some(result) =
            service_portfolio::handle(&method, &path, &query, &body, &principal, &db).await
    {
        return outcome_reply(result);
    }
    outcome_reply(Err(api::fault(
        404,
        "NOT_FOUND_OR_METHOD_NOT_ALLOWED",
        "지원하지 않는 요청입니다.",
    )))
}

async fn handle(
    request: Request<Incoming>,
    db: Arc<Client>,
    config: Arc<tokio_postgres::Config>,
) -> Result<Reply, Infallible> {
    let origin = match request.headers().get(hyper::header::ORIGIN) {
        None => None,
        Some(value) => match value.to_str() {
            Ok(value) => Some(value.to_owned()),
            Err(_) => {
                return Ok(error_reply(
                    StatusCode::FORBIDDEN,
                    "FORBIDDEN",
                    "접근 권한이 없습니다.",
                ));
            }
        },
    };
    if let Some(origin) = &origin {
        let allowed = env::var("APP_CORS_ALLOWED_ORIGIN")
            .unwrap_or_else(|_| "http://localhost:5173".to_owned());
        if origin != &allowed || allowed == "*" {
            return Ok(error_reply(
                StatusCode::FORBIDDEN,
                "FORBIDDEN",
                "접근 권한이 없습니다.",
            ));
        }
        if request.method() == Method::OPTIONS {
            let method = request
                .headers()
                .get("access-control-request-method")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("");
            let headers = request
                .headers()
                .get("access-control-request-headers")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("");
            if !matches!(
                method,
                "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "OPTIONS"
            ) || headers
                .split(',')
                .filter(|v| !v.trim().is_empty())
                .any(|v| {
                    !matches!(
                        v.trim().to_ascii_lowercase().as_str(),
                        "content-type" | "accept" | "x-xsrf-token"
                    )
                })
            {
                return Ok(error_reply(
                    StatusCode::FORBIDDEN,
                    "FORBIDDEN",
                    "접근 권한이 없습니다.",
                ));
            }
            let mut response = Response::new(Full::new(Bytes::new()));
            response.headers_mut().insert(
                "access-control-allow-origin",
                HeaderValue::from_str(origin).expect("validated request header"),
            );
            response.headers_mut().insert(
                "access-control-allow-credentials",
                HeaderValue::from_static("true"),
            );
            response.headers_mut().insert(
                "access-control-allow-methods",
                HeaderValue::from_static("GET,POST,PUT,PATCH,DELETE,OPTIONS"),
            );
            response.headers_mut().insert(
                "access-control-allow-headers",
                HeaderValue::from_static("Content-Type,Accept,X-XSRF-TOKEN"),
            );
            response.headers_mut().insert(
                "vary",
                HeaderValue::from_static(
                    "Origin,Access-Control-Request-Method,Access-Control-Request-Headers",
                ),
            );
            return Ok(response);
        }
    }
    let mut response = handle_inner(request, db, config).await?;
    if let Some(origin) = origin {
        response.headers_mut().insert(
            "access-control-allow-origin",
            HeaderValue::from_str(&origin).expect("validated request header"),
        );
        response.headers_mut().insert(
            "access-control-allow-credentials",
            HeaderValue::from_static("true"),
        );
        response
            .headers_mut()
            .append("vary", HeaderValue::from_static("Origin"));
    }
    Ok(response)
}

async fn handle_inner(
    request: Request<Incoming>,
    db: Arc<Client>,
    config: Arc<tokio_postgres::Config>,
) -> Result<Reply, Infallible> {
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
    if protected(path)
        || path == "/api/portfolio/analysis"
        || path.starts_with("/api/auth/")
        || path.starts_with("/oauth2/")
        || path.starts_with("/login/oauth2/")
    {
        return Ok(private_request(request, config).await);
    }
    if path != "/api/feedback" {
        let path = path.to_owned();
        let query = request.uri().query().unwrap_or("").to_owned();
        let method = request.method().as_str().to_owned();
        let mut bytes = Bytes::new();
        if matches!(method.as_str(), "POST" | "PUT" | "PATCH" | "DELETE") {
            let guest_analysis = path == "/api/portfolio/analysis"
                && !request
                    .headers()
                    .get_all(hyper::header::COOKIE)
                    .iter()
                    .filter_map(|v| v.to_str().ok())
                    .flat_map(|v| v.split(';'))
                    .any(|pair| {
                        pair.trim()
                            .split_once('=')
                            .is_some_and(|(name, _)| name == "access_token")
                    });
            if !guest_analysis && !csrf::valid(request.headers()) {
                return Ok(error_reply(
                    StatusCode::FORBIDDEN,
                    "FORBIDDEN",
                    "접근 권한이 없습니다.",
                ));
            }
            if !request
                .headers()
                .get(CONTENT_TYPE)
                .and_then(|v| v.to_str().ok())
                .is_some_and(|v| {
                    v.split(';')
                        .next()
                        .unwrap_or("")
                        .trim()
                        .eq_ignore_ascii_case("application/json")
                })
            {
                return Ok(error_reply(
                    StatusCode::UNSUPPORTED_MEDIA_TYPE,
                    "UNSUPPORTED_MEDIA_TYPE",
                    "JSON 요청이 필요합니다.",
                ));
            }
            bytes = match tokio::time::timeout(
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
        }
        let result = match service_calendar::handle(&method, &path, &query, &bytes, None, &db).await
        {
            Some(result) => Some(result),
            None => match service_market::handle(&method, &path, &query, &bytes, &db).await {
                Some(result) => Some(result),
                None => service_discovery::handle(&method, &path, &query, &bytes, &db).await,
            },
        };
        if let Some(result) = result {
            let (status, body) = match result {
                Ok(pair) => pair,
                Err(error) => (error.status, error.body),
            };
            return Ok(json_reply(
                StatusCode::from_u16(status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
                body,
            ));
        }
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
    let arguments: Vec<String> = env::args().skip(1).collect();
    let job = match arguments.as_slice() {
        [] => None,
        [flag, name] if flag == "--job" => Some(name.as_str()),
        _ => return Err("Usage: daynomy-feedback [--job NAME]"),
    };
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
    let shared_config = Arc::new(config.clone());
    let (client, connection) = config
        .connect(NoTls)
        .await
        .map_err(|_| "Database connection failed")?;
    let db_task = tokio::spawn(async move {
        if connection.await.is_err() {
            eprintln!("event=database.connection_failed");
        }
    });
    let timezone = env::var("APP_TIMEZONE").unwrap_or_else(|_| "Asia/Seoul".to_owned());
    client
        .query_one("SELECT set_config('TimeZone',$1,false)", &[&timezone])
        .await
        .map_err(|_| "Invalid APP_TIMEZONE")?;
    client
        .simple_query("SELECT id FROM feedbacks LIMIT 0")
        .await
        .map_err(
            |_| "Feedback schema is missing/inaccessible; apply migrations/001_feedbacks.sql",
        )?;
    if let Some(name) = job {
        let result = service_schedule::run_named(name, &client).await;
        let (status, body) = match result {
            Ok(reply) => reply,
            Err(error) => (error.status, error.body),
        };
        println!("{}", json!({"status":status,"result":body}));
        drop(client);
        db_task.abort();
        return if (200..300).contains(&status) && status != 207 {
            Ok(())
        } else {
            Err("Batch job failed or partially completed; see structured result")
        };
    }
    let scheduler = service_schedule::spawn(Arc::clone(&shared_config));
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
                let config=Arc::clone(&shared_config);
                connections.spawn(async move {
                    let _permit = permit;
                    let mut builder = http1::Builder::new();
                    builder.keep_alive(false).timer(TokioTimer::new())
                        .header_read_timeout(Duration::from_secs(5));
                    if builder.serve_connection(TokioIo::new(stream),
                        service_fn(move |request| handle(request, Arc::clone(&db),Arc::clone(&config))))
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
    if let Some(task) = scheduler {
        task.abort();
        let _ = task.await;
    }
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
