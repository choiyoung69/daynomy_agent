//! Cookie authentication and member operations. No provider identity is trusted
//! without a verified OIDC exchange.
use crate::api::{ApiFault, fault, internal, invalid};
use base64::{
    Engine as _,
    engine::general_purpose::{STANDARD, URL_SAFE_NO_PAD},
};
use hmac::{Hmac, KeyInit, Mac};
use hyper::HeaderMap;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};
use subtle::ConstantTimeEq;
use tokio_postgres::Client;

pub struct Principal {
    pub id: i64,
    pub role: String,
}
pub struct AuthReply {
    pub status: u16,
    pub body: Value,
    pub headers: Vec<(String, String)>,
}

fn reply(status: u16, body: Value) -> AuthReply {
    AuthReply {
        status,
        body,
        headers: vec![],
    }
}
fn unauthorized() -> ApiFault {
    fault(401, "UNAUTHORIZED", "로그인이 필요합니다.")
}
fn invalid_token() -> ApiFault {
    fault(401, "INVALID_TOKEN", "유효하지 않은 인증 정보입니다.")
}
fn invalid_refresh() -> ApiFault {
    fault(
        401,
        "INVALID_REFRESH_TOKEN",
        "유효하지 않은 Refresh Token입니다.",
    )
}
fn now() -> Result<i64, ApiFault> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| internal())?
        .as_secs() as i64)
}
fn key() -> Result<Vec<u8>, ApiFault> {
    let secret = std::env::var("JWT_SECRET").map_err(|_| internal())?;
    let bytes = STANDARD.decode(secret).map_err(|_| internal())?;
    if bytes.len() < 32 {
        return Err(internal());
    }
    Ok(bytes)
}
fn issuer() -> String {
    std::env::var("JWT_ISSUER").unwrap_or_else(|_| "daynomy".into())
}
fn lifetime(name: &str, default_ms: i64) -> Result<i64, ApiFault> {
    let ms = std::env::var(name)
        .ok()
        .map(|s| s.parse::<i64>())
        .transpose()
        .map_err(|_| internal())?
        .unwrap_or(default_ms);
    if ms < 1000 {
        return Err(internal());
    }
    Ok(ms / 1000)
}
fn cookie(headers: &HeaderMap, name: &str) -> Option<String> {
    for header in headers.get_all(hyper::header::COOKIE) {
        let Ok(text) = header.to_str() else { continue };
        for item in text.split(';') {
            if let Some((key, value)) = item.trim().split_once('=')
                && key == name
            {
                return Some(value.to_owned());
            }
        }
    }
    None
}
fn cookie_header(name: &str, value: &str, path: &str, age: i64) -> (String, String) {
    let secure = std::env::var("COOKIE_SECURE")
        .map(|v| v != "false")
        .unwrap_or(true);
    (
        "set-cookie".into(),
        format!(
            "{name}={value}; Path={path}; Max-Age={age}; HttpOnly; SameSite=Lax{}",
            if secure { "; Secure" } else { "" }
        ),
    )
}
pub fn clear_token_cookies() -> Vec<(String, String)> {
    vec![
        cookie_header("access_token", "", "/", 0),
        cookie_header("refresh_token", "", "/api/auth", 0),
    ]
}
fn hash(token: &str) -> String {
    Sha256::digest(token.as_bytes())
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}
fn parse(token: &str, expected: &str) -> Result<Value, ApiFault> {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err(invalid_token());
    }
    let header: Value = serde_json::from_slice(
        &URL_SAFE_NO_PAD
            .decode(parts[0])
            .map_err(|_| invalid_token())?,
    )
    .map_err(|_| invalid_token())?;
    if header.get("alg").and_then(Value::as_str) != Some("HS256")
        || header.get("typ").and_then(Value::as_str) != Some("JWT")
    {
        return Err(invalid_token());
    }
    let signature = URL_SAFE_NO_PAD
        .decode(parts[2])
        .map_err(|_| invalid_token())?;
    let mut mac = Hmac::<Sha256>::new_from_slice(&key()?).map_err(|_| internal())?;
    mac.update(format!("{}.{}", parts[0], parts[1]).as_bytes());
    mac.verify_slice(&signature).map_err(|_| invalid_token())?;
    let claims: Value = serde_json::from_slice(
        &URL_SAFE_NO_PAD
            .decode(parts[1])
            .map_err(|_| invalid_token())?,
    )
    .map_err(|_| invalid_token())?;
    let current = now()?;
    if claims.get("iss").and_then(Value::as_str) != Some(issuer().as_str())
        || claims.get("token_type").and_then(Value::as_str) != Some(expected)
        || claims
            .get("exp")
            .and_then(Value::as_i64)
            .is_none_or(|e| e <= current)
        || claims
            .get("nbf")
            .is_some_and(|v| v.as_i64().is_none_or(|n| n > current))
        || claims
            .get("iat")
            .and_then(Value::as_i64)
            .is_none_or(|n| n > current)
    {
        return Err(invalid_token());
    }
    member_id(&claims)?;
    Ok(claims)
}
fn member_id(claims: &Value) -> Result<i64, ApiFault> {
    claims
        .get("sub")
        .and_then(Value::as_str)
        .and_then(|s| s.parse::<i64>().ok())
        .filter(|id| *id > 0)
        .ok_or_else(invalid_token)
}
fn encode(id: i64, role: Option<&str>, kind: &str, expiration: i64) -> Result<String, ApiFault> {
    let mut claims = json!({"iss":issuer(),"sub":id.to_string(),"iat":now()?,"exp":expiration,"jti":uuid::Uuid::new_v4().to_string(),"token_type":kind});
    if let Some(role) = role {
        claims["role"] = json!(role);
    }
    let head = URL_SAFE_NO_PAD.encode(br#"{"alg":"HS256","typ":"JWT"}"#);
    let payload = URL_SAFE_NO_PAD.encode(serde_json::to_vec(&claims).map_err(|_| internal())?);
    let message = format!("{head}.{payload}");
    let mut mac = Hmac::<Sha256>::new_from_slice(&key()?).map_err(|_| internal())?;
    mac.update(message.as_bytes());
    Ok(format!(
        "{message}.{}",
        URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes())
    ))
}

pub async fn authenticate(headers: &HeaderMap, db: &Client) -> Result<Option<Principal>, ApiFault> {
    let Some(token) = cookie(headers, "access_token") else {
        return Ok(None);
    };
    let claims = parse(&token, "access")?;
    let id = member_id(&claims)?;
    let claimed_role = claims
        .get("role")
        .and_then(Value::as_str)
        .ok_or_else(invalid_token)?;
    if !matches!(claimed_role, "USER" | "ADMIN") {
        return Err(invalid_token());
    }
    let row = db
        .query_opt(
            "SELECT role FROM members WHERE id=$1 AND status='ACTIVE'",
            &[&id],
        )
        .await
        .map_err(|_| internal())?
        .ok_or_else(invalid_token)?;
    let role: String = row.get(0);
    if role != claimed_role {
        return Err(invalid_token());
    }
    Ok(Some(Principal { id, role }))
}

async fn profile(db: &Client, id: i64) -> Result<Value, ApiFault> {
    let row = db
        .query_opt(
            "SELECT id,email,google_name,nickname,role,status FROM members WHERE id=$1",
            &[&id],
        )
        .await
        .map_err(|_| internal())?
        .ok_or_else(|| fault(404, "MEMBER_NOT_FOUND", "회원을 찾을 수 없습니다."))?;
    if row.get::<_, String>(5) != "ACTIVE" {
        return Err(fault(401, "WITHDRAWN_MEMBER", "탈퇴한 회원입니다."));
    }
    Ok(
        json!({"id":row.get::<_,i64>(0),"email":row.get::<_,String>(1),"name":row.get::<_,Option<String>>(2),"nickname":row.get::<_,String>(3),"role":row.get::<_,String>(4)}),
    )
}
// Character.isWhitespace, used by Java String.strip(), excludes the three
// non-breaking spaces that Rust's Unicode whitespace predicate includes.
fn java_whitespace(c: char) -> bool {
    matches!(c, '\u{0009}'..='\u{000d}' | '\u{001c}'..='\u{0020}' | '\u{1680}' | '\u{2000}'..='\u{2006}' | '\u{2008}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{205f}' | '\u{3000}')
}
async fn refresh(headers: &HeaderMap, db: &Client) -> Result<AuthReply, ApiFault> {
    let token = cookie(headers, "refresh_token")
        .filter(|s| !s.trim().is_empty())
        .ok_or_else(|| fault(401, "REFRESH_TOKEN_REQUIRED", "Refresh Token이 필요합니다."))?;
    let claims = parse(&token, "refresh").map_err(|e| {
        if e.status == 401 {
            invalid_refresh()
        } else {
            e
        }
    })?;
    let id = member_id(&claims).map_err(|_| invalid_refresh())?;
    db.batch_execute("BEGIN").await.map_err(|_| internal())?;
    let result = async {
        // The same member lock is acquired by withdrawal before deleting tokens.
        let member = db.query_opt("SELECT role FROM members WHERE id=$1 AND status='ACTIVE' FOR UPDATE", &[&id]).await.map_err(|_| internal())?.ok_or_else(invalid_refresh)?;
        let role: String = member.get(0);
        if !matches!(role.as_str(), "USER" | "ADMIN") { return Err(invalid_refresh()); }
        let access_age = lifetime("ACCESS_TOKEN_EXPIRATION", 1_800_000)?;
        let refresh_age = lifetime("REFRESH_TOKEN_EXPIRATION", 1_209_600_000)?;
        let timestamp = now()?;
        let access = encode(id,Some(&role),"access",timestamp + access_age)?;
        let new_refresh = encode(id,None,"refresh",timestamp + refresh_age)?;
        let old_hash = hash(&token);
        let new_hash = hash(&new_refresh);
        let expires = (timestamp + refresh_age) as f64;
        let changed = db.execute("WITH consumed AS (DELETE FROM refresh_tokens WHERE token_hash=$1 AND member_id=$2 AND expires_at>now() RETURNING member_id) INSERT INTO refresh_tokens(member_id,token_hash,expires_at,created_at) SELECT member_id,$3,to_timestamp($4),now() FROM consumed", &[&old_hash,&id,&new_hash,&expires]).await.map_err(|_| internal())?;
        if changed != 1 { return Err(invalid_refresh()); }
        let mut response = reply(204,Value::Null);
        response.headers = vec![cookie_header("access_token",&access,"/",access_age),cookie_header("refresh_token",&new_refresh,"/api/auth",refresh_age)];
        Ok(response)
    }.await;
    finish_transaction(db, result).await
}
async fn finish_transaction<T>(db: &Client, result: Result<T, ApiFault>) -> Result<T, ApiFault> {
    match result {
        Ok(value) => {
            db.batch_execute("COMMIT").await.map_err(|_| internal())?;
            Ok(value)
        }
        Err(error) => {
            db.batch_execute("ROLLBACK").await.map_err(|_| internal())?;
            Err(error)
        }
    }
}

fn oauth_unavailable() -> ApiFault {
    fault(
        503,
        "OAUTH_UNAVAILABLE",
        "Google 로그인을 사용할 수 없습니다.",
    )
}
fn oauth_invalid() -> ApiFault {
    fault(
        401,
        "INVALID_OIDC_RESPONSE",
        "Google 사용자 정보가 올바르지 않습니다.",
    )
}
struct OAuthConfig {
    client_id: String,
    client_secret: String,
    redirect: String,
    success: String,
}
fn configured_redirect(value: &str, relative: bool) -> bool {
    if value.chars().any(char::is_control) {
        return false;
    }
    if relative && value.starts_with('/') && !value.starts_with("//") {
        return true;
    }
    let Ok(url) = reqwest::Url::parse(value) else {
        return false;
    };
    if !url.username().is_empty() || url.password().is_some() || url.fragment().is_some() {
        return false;
    }
    url.scheme() == "https"
        || (url.scheme() == "http"
            && matches!(
                url.host_str(),
                Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
            ))
}
fn oauth_config() -> Result<OAuthConfig, ApiFault> {
    let get = |name: &str| {
        std::env::var(name)
            .ok()
            .filter(|s| !s.trim().is_empty())
            .ok_or_else(oauth_unavailable)
    };
    let config = OAuthConfig {
        client_id: get("GOOGLE_CLIENT_ID")?,
        client_secret: get("GOOGLE_CLIENT_SECRET")?,
        redirect: get("OAUTH_REDIRECT_URI")?,
        success: get("SUCCESS_REDIRECT_URI")?,
    };
    if !configured_redirect(&config.redirect, false) || !configured_redirect(&config.success, true)
    {
        return Err(oauth_unavailable());
    }
    let url = reqwest::Url::parse(&config.redirect).map_err(|_| oauth_unavailable())?;
    if url.path() != "/login/oauth2/code/google" || url.query().is_some() {
        return Err(oauth_unavailable());
    }
    Ok(config)
}
fn oauth_endpoint(name: &str, default: &str) -> Result<reqwest::Url, ApiFault> {
    let value = std::env::var(name).unwrap_or_else(|_| default.to_owned());
    if !configured_redirect(&value, false) {
        return Err(oauth_unavailable());
    }
    reqwest::Url::parse(&value).map_err(|_| oauth_unavailable())
}
fn random_secret() -> String {
    format!(
        "{}{}",
        uuid::Uuid::new_v4().simple(),
        uuid::Uuid::new_v4().simple()
    )
}
fn state_cookie(value: &str, age: i64) -> (String, String) {
    cookie_header("oauth_state", value, "/", age)
}
fn seal_state(value: &Value) -> Result<String, ApiFault> {
    let payload = URL_SAFE_NO_PAD.encode(serde_json::to_vec(value).map_err(|_| internal())?);
    let mut mac = Hmac::<Sha256>::new_from_slice(&key()?).map_err(|_| internal())?;
    mac.update(b"daynomy:oauth-state:");
    mac.update(payload.as_bytes());
    Ok(format!(
        "{payload}.{}",
        URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes())
    ))
}
fn unseal_state(raw: &str) -> Result<Value, ApiFault> {
    let (payload, signature) = raw.split_once('.').ok_or_else(oauth_invalid)?;
    let signature = URL_SAFE_NO_PAD
        .decode(signature)
        .map_err(|_| oauth_invalid())?;
    let mut mac = Hmac::<Sha256>::new_from_slice(&key()?).map_err(|_| internal())?;
    mac.update(b"daynomy:oauth-state:");
    mac.update(payload.as_bytes());
    mac.verify_slice(&signature).map_err(|_| oauth_invalid())?;
    let value: Value = serde_json::from_slice(
        &URL_SAFE_NO_PAD
            .decode(payload)
            .map_err(|_| oauth_invalid())?,
    )
    .map_err(|_| oauth_invalid())?;
    if value["exp"]
        .as_i64()
        .is_none_or(|e| e <= now().unwrap_or(i64::MAX))
    {
        return Err(oauth_invalid());
    }
    Ok(value)
}
async fn oauth_start(db: &Client, mobile: Option<Value>) -> Result<AuthReply, ApiFault> {
    let config = oauth_config()?;
    let state = random_secret();
    let nonce = random_secret();
    let verifier = random_secret();
    let challenge = URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()));
    let expires = now()? + 600;
    let sealed = seal_state(
        &json!({"state":state,"nonce":nonce,"verifier":verifier,"exp":expires,"mobile":mobile}),
    )?;
    // Keep server-side replay protection even when the browser keeps an old cookie.
    db.execute(
        "DELETE FROM oauth_login_states WHERE expires_at<=now()",
        &[],
    )
    .await
    .map_err(|_| internal())?;
    db.execute(
        "INSERT INTO oauth_login_states(state_hash,expires_at) VALUES($1,to_timestamp($2))",
        &[&hash(&state), &(expires as f64)],
    )
    .await
    .map_err(|_| internal())?;
    let mut target = oauth_endpoint(
        "GOOGLE_AUTHORIZATION_URI",
        "https://accounts.google.com/o/oauth2/v2/auth",
    )?;
    target.query_pairs_mut().extend_pairs([
        ("client_id", config.client_id.as_str()),
        ("redirect_uri", config.redirect.as_str()),
        ("response_type", "code"),
        ("scope", "openid email profile"),
        ("state", state.as_str()),
        ("nonce", nonce.as_str()),
        ("code_challenge", challenge.as_str()),
        ("code_challenge_method", "S256"),
    ]);
    Ok(AuthReply {
        status: 302,
        body: Value::Null,
        headers: vec![
            ("location".into(), target.into()),
            state_cookie(&sealed, 600),
        ],
    })
}
async fn limited_json(mut response: reqwest::Response) -> Result<Value, ApiFault> {
    if !response.status().is_success() || response.content_length().is_some_and(|n| n > 131_072) {
        return Err(oauth_invalid());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| oauth_unavailable())? {
        if bytes.len() + chunk.len() > 131_072 {
            return Err(oauth_invalid());
        }
        bytes.extend_from_slice(&chunk);
    }
    serde_json::from_slice(&bytes).map_err(|_| oauth_invalid())
}
fn short_text(value: Option<&str>, limit: usize) -> Option<String> {
    let value = value?.trim_matches(java_whitespace);
    if value.is_empty() {
        return None;
    }
    let mut count = 0;
    Some(
        value
            .chars()
            .take_while(|c| {
                count += c.len_utf16();
                count <= limit
            })
            .collect(),
    )
}
async fn oauth_callback(
    query: &str,
    headers: &HeaderMap,
    db: &Client,
) -> Result<AuthReply, ApiFault> {
    let config = oauth_config()?;
    let params = crate::api::query(query).map_err(|_| oauth_invalid())?;
    if params.contains_key("error") {
        return Err(oauth_invalid());
    }
    let code = params
        .get("code")
        .filter(|c| !c.is_empty() && c.len() <= 8192)
        .ok_or_else(oauth_invalid)?;
    let state = params.get("state").ok_or_else(oauth_invalid)?;
    let saved = unseal_state(&cookie(headers, "oauth_state").ok_or_else(oauth_invalid)?)?;
    let expected = saved["state"].as_str().ok_or_else(oauth_invalid)?;
    if !bool::from(state.as_bytes().ct_eq(expected.as_bytes())) {
        return Err(oauth_invalid());
    }
    let nonce = saved["nonce"].as_str().ok_or_else(oauth_invalid)?;
    let verifier = saved["verifier"].as_str().ok_or_else(oauth_invalid)?;
    let consumed = db
        .execute(
            "DELETE FROM oauth_login_states WHERE state_hash=$1 AND expires_at>now()",
            &[&hash(state)],
        )
        .await
        .map_err(|_| internal())?;
    if consumed != 1 {
        return Err(oauth_invalid());
    }
    let http = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(std::time::Duration::from_secs(5))
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|_| oauth_unavailable())?;
    let token = limited_json(
        http.post(oauth_endpoint(
            "GOOGLE_TOKEN_URI",
            "https://oauth2.googleapis.com/token",
        )?)
        .form(&[
            ("grant_type", "authorization_code"),
            ("code", code.as_str()),
            ("client_id", config.client_id.as_str()),
            ("client_secret", config.client_secret.as_str()),
            ("redirect_uri", config.redirect.as_str()),
            ("code_verifier", verifier),
        ])
        .send()
        .await
        .map_err(|_| oauth_unavailable())?,
    )
    .await?;
    let raw_id_token = token["id_token"]
        .as_str()
        .filter(|s| s.len() <= 32768)
        .ok_or_else(oauth_invalid)?;
    let jwt_header = jsonwebtoken::decode_header(raw_id_token).map_err(|_| oauth_invalid())?;
    if jwt_header.alg != jsonwebtoken::Algorithm::RS256 {
        return Err(oauth_invalid());
    }
    let kid = jwt_header.kid.as_deref().ok_or_else(oauth_invalid)?;
    let jwks_value = limited_json(
        http.get(oauth_endpoint(
            "GOOGLE_JWKS_URI",
            "https://www.googleapis.com/oauth2/v3/certs",
        )?)
        .send()
        .await
        .map_err(|_| oauth_unavailable())?,
    )
    .await?;
    let jwks: jsonwebtoken::jwk::JwkSet =
        serde_json::from_value(jwks_value).map_err(|_| oauth_invalid())?;
    let jwk = jwks.find(kid).ok_or_else(oauth_invalid)?;
    if jwk
        .common
        .public_key_use
        .as_ref()
        .is_some_and(|u| *u != jsonwebtoken::jwk::PublicKeyUse::Signature)
    {
        return Err(oauth_invalid());
    }
    let decoding_key = jsonwebtoken::DecodingKey::from_jwk(jwk).map_err(|_| oauth_invalid())?;
    let mut validation = jsonwebtoken::Validation::new(jsonwebtoken::Algorithm::RS256);
    validation.set_audience(&[&config.client_id]);
    validation.set_issuer(&["https://accounts.google.com", "accounts.google.com"]);
    validation.set_required_spec_claims(&["exp", "iss", "aud", "sub"]);
    validation.validate_nbf = true;
    validation.leeway = 30;
    let claims = jsonwebtoken::decode::<Value>(raw_id_token, &decoding_key, &validation)
        .map_err(|_| oauth_invalid())?
        .claims;
    if !bool::from(
        claims["nonce"]
            .as_str()
            .ok_or_else(oauth_invalid)?
            .as_bytes()
            .ct_eq(nonce.as_bytes()),
    ) || claims["email_verified"].as_bool() != Some(true)
        || claims["iat"]
            .as_i64()
            .is_none_or(|i| i > now().unwrap_or(0) + 30)
        || claims
            .get("azp")
            .is_some_and(|v| v.as_str() != Some(config.client_id.as_str()))
        || claims["aud"].as_array().is_some_and(|aud| {
            aud.len() > 1 && claims["azp"].as_str() != Some(config.client_id.as_str())
        })
    {
        return Err(oauth_invalid());
    }
    let subject = claims["sub"]
        .as_str()
        .filter(|s| !s.is_empty() && s.len() <= 255)
        .ok_or_else(oauth_invalid)?;
    let email = claims["email"]
        .as_str()
        .filter(|s| !s.trim().is_empty() && s.chars().count() <= 255)
        .ok_or_else(oauth_invalid)?;
    let name = short_text(claims["name"].as_str(), 255);
    let picture = short_text(claims["picture"].as_str(), 500);
    db.batch_execute("BEGIN").await.map_err(|_| internal())?;
    let result = async {
        // Match Google's immutable subject, never link users by an email claim.
        let mut member = db.query_opt("SELECT id,role,status FROM members WHERE provider='GOOGLE' AND provider_id=$1 FOR UPDATE",&[&subject]).await.map_err(|_| internal())?;
        if member.is_none() {
            for _ in 0..3 {
                let nickname = format!("회원_{}", &uuid::Uuid::new_v4().simple().to_string()[..16]);
                db.execute("INSERT INTO members(provider,provider_id,email,google_name,nickname,profile_image_url,role,status,created_at,updated_at) VALUES('GOOGLE',$1,$2,$3,$4,$5,'USER','ACTIVE',now(),now()) ON CONFLICT DO NOTHING",&[&subject,&email,&name,&nickname,&picture]).await.map_err(|_| internal())?;
                member = db.query_opt("SELECT id,role,status FROM members WHERE provider='GOOGLE' AND provider_id=$1 FOR UPDATE",&[&subject]).await.map_err(|_| internal())?;
                if member.is_some() { break; }
            }
        }
        let member = member.ok_or_else(internal)?;
        if member.get::<_,String>(2) != "ACTIVE" { return Err(fault(401,"WITHDRAWN_MEMBER","탈퇴한 회원입니다.")); }
        let id: i64 = member.get(0);
        let role: String = member.get(1);
        if !matches!(role.as_str(),"USER"|"ADMIN") { return Err(invalid_token()); }
        if let Some(name) = name { db.execute("UPDATE members SET google_name=$2,updated_at=now() WHERE id=$1",&[&id,&name]).await.map_err(|_| internal())?; }
        if let Some(mobile) = saved.get("mobile").filter(|v| !v.is_null()) {
            let challenge = mobile["challenge"].as_str().ok_or_else(oauth_invalid)?;
            let app_state = mobile["state"].as_str().ok_or_else(oauth_invalid)?;
            let code = random_secret();
            db.execute("DELETE FROM mobile_auth_codes WHERE expires_at<=now()", &[]).await.map_err(|_| internal())?;
            db.execute("INSERT INTO mobile_auth_codes(code_hash,member_id,code_challenge,expires_at,created_at) VALUES($1,$2,$3,now()+interval '60 seconds',now())", &[&hash(&code),&id,&challenge]).await.map_err(|_| internal())?;
            let mut target = reqwest::Url::parse("org.daynomy.app://auth/callback").map_err(|_| internal())?;
            target.query_pairs_mut().extend_pairs([("code",code.as_str()),("state",app_state)]);
            return Ok(AuthReply { status:302,body:Value::Null,headers:vec![("location".into(),target.into()),state_cookie("",0)] });
        }
        let access_age = lifetime("ACCESS_TOKEN_EXPIRATION",1_800_000)?;
        let refresh_age = lifetime("REFRESH_TOKEN_EXPIRATION",1_209_600_000)?;
        let timestamp = now()?;
        let access = encode(id,Some(&role),"access",timestamp+access_age)?;
        let refresh = encode(id,None,"refresh",timestamp+refresh_age)?;
        db.execute("INSERT INTO refresh_tokens(member_id,token_hash,expires_at,created_at) VALUES($1,$2,to_timestamp($3),now())",&[&id,&hash(&refresh),&((timestamp+refresh_age) as f64)]).await.map_err(|_| internal())?;
        Ok(AuthReply { status:302,body:Value::Null,headers:vec![("location".into(),config.success),cookie_header("access_token",&access,"/",access_age),cookie_header("refresh_token",&refresh,"/api/auth",refresh_age),state_cookie("",0)] })
    }.await;
    finish_transaction(db, result).await
}

fn mobile_bad_request() -> ApiFault {
    fault(
        400,
        "INVALID_REQUEST",
        "모바일 인증 요청이 올바르지 않습니다.",
    )
}
fn mobile_invalid() -> ApiFault {
    fault(
        401,
        "INVALID_MOBILE_AUTH_CODE",
        "모바일 인증 코드가 올바르지 않거나 만료되었습니다.",
    )
}
fn urlsafe(value: &str, min: usize, max: usize) -> bool {
    (min..=max).contains(&value.len())
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}
fn unique_mobile_query(raw: &str) -> Result<std::collections::BTreeMap<String, String>, ApiFault> {
    let mut result = std::collections::BTreeMap::new();
    for (key, value) in reqwest::Url::parse(&format!("https://daynomy.invalid/?{raw}"))
        .map_err(|_| mobile_bad_request())?
        .query_pairs()
    {
        if result
            .insert(key.into_owned(), value.into_owned())
            .is_some()
        {
            return Err(mobile_bad_request());
        }
    }
    Ok(result)
}
async fn mobile_start(query: &str, db: &Client) -> Result<AuthReply, ApiFault> {
    let params = unique_mobile_query(query)?;
    let challenge = params
        .get("code_challenge")
        .ok_or_else(mobile_bad_request)?;
    let state = params.get("state").ok_or_else(mobile_bad_request)?;
    if !urlsafe(challenge, 43, 43) || !urlsafe(state, 32, 128) {
        return Err(mobile_bad_request());
    }
    oauth_start(db, Some(json!({"challenge":challenge,"state":state}))).await
}
fn mobile_failure(query: &str, headers: &HeaderMap) -> Option<AuthReply> {
    let params = unique_mobile_query(query).ok()?;
    let saved = unseal_state(&cookie(headers, "oauth_state")?).ok()?;
    let expected = saved["state"].as_str()?;
    if !bool::from(params.get("state")?.as_bytes().ct_eq(expected.as_bytes())) {
        return None;
    }
    let app_state = saved["mobile"]["state"].as_str()?;
    let mut target = reqwest::Url::parse("org.daynomy.app://auth/callback").ok()?;
    target
        .query_pairs_mut()
        .extend_pairs([("error", "oauth_failed"), ("state", app_state)]);
    Some(AuthReply {
        status: 302,
        body: Value::Null,
        headers: vec![("location".into(), target.into()), state_cookie("", 0)],
    })
}
async fn mobile_exchange(body: &[u8], db: &Client) -> Result<AuthReply, ApiFault> {
    let input: Value = serde_json::from_slice(body).map_err(|_| mobile_bad_request())?;
    let code = input["code"].as_str().ok_or_else(mobile_bad_request)?;
    let verifier = input["codeVerifier"]
        .as_str()
        .ok_or_else(mobile_bad_request)?;
    if !urlsafe(code, 32, 128)
        || !(43..=128).contains(&verifier.len())
        || !verifier
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"-._~".contains(&b))
    {
        return Err(mobile_bad_request());
    }
    let code_hash = hash(code);
    let challenge = URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()));
    db.batch_execute("BEGIN").await.map_err(|_| internal())?;
    let result = async {
        // Row locking serializes simultaneous exchanges. Check PKCE before deleting.
        let row = db.query_opt("SELECT member_id,code_challenge FROM mobile_auth_codes WHERE code_hash=$1 AND expires_at>now() FOR UPDATE", &[&code_hash]).await.map_err(|_| internal())?.ok_or_else(mobile_invalid)?;
        let expected: String = row.get(1);
        if !bool::from(challenge.as_bytes().ct_eq(expected.as_bytes())) { return Err(mobile_invalid()); }
        let id: i64 = row.get(0);
        let member = db.query_opt("SELECT role,status FROM members WHERE id=$1 FOR UPDATE", &[&id]).await.map_err(|_| internal())?.ok_or_else(mobile_invalid)?;
        let role: String = member.get(0);
        if member.get::<_,String>(1) != "ACTIVE" || !matches!(role.as_str(),"USER"|"ADMIN") { return Err(mobile_invalid()); }
        let access_age = lifetime("ACCESS_TOKEN_EXPIRATION",1_800_000)?;
        let refresh_age = lifetime("REFRESH_TOKEN_EXPIRATION",1_209_600_000)?;
        let timestamp = now()?;
        let access = encode(id,Some(&role),"access",timestamp+access_age)?;
        let refresh = encode(id,None,"refresh",timestamp+refresh_age)?;
        db.execute("INSERT INTO refresh_tokens(member_id,token_hash,expires_at,created_at) VALUES($1,$2,to_timestamp($3),now())", &[&id,&hash(&refresh),&((timestamp+refresh_age) as f64)]).await.map_err(|_| internal())?;
        let consumed = db.execute("DELETE FROM mobile_auth_codes WHERE code_hash=$1", &[&code_hash]).await.map_err(|_| internal())?;
        if consumed != 1 { return Err(mobile_invalid()); }
        Ok(AuthReply { status:204,body:Value::Null,headers:vec![cookie_header("access_token",&access,"/",access_age),cookie_header("refresh_token",&refresh,"/api/auth",refresh_age)] })
    }.await;
    finish_transaction(db, result).await
}

pub async fn handle(
    method: &str,
    path: &str,
    body: &[u8],
    headers: &HeaderMap,
    principal: Option<&Principal>,
    db: &Client,
) -> Option<Result<AuthReply, ApiFault>> {
    let (path, query) = path.split_once('?').unwrap_or((path, ""));
    match (method,path) {
        ("GET","/api/auth/mobile/start") => Some(mobile_start(query,db).await),
        ("POST","/api/auth/mobile/exchange") => Some(if headers.get(hyper::header::CONTENT_TYPE).and_then(|v| v.to_str().ok()).is_some_and(|v| v.split(';').next().unwrap_or("").trim().eq_ignore_ascii_case("application/json")) { mobile_exchange(body,db).await } else { Err(fault(415,"UNSUPPORTED_MEDIA_TYPE","JSON 요청이 필요합니다.")) }),
        ("GET","/api/auth/google") => {
            let mut response = reply(302,Value::Null);
            response.headers.push(("location".into(),"/oauth2/authorization/google".into()));
            Some(Ok(response))
        },
        ("GET","/oauth2/authorization/google") => Some(oauth_start(db, None).await),
        ("GET","/login/oauth2/code/google") => Some(match oauth_callback(query,headers,db).await {
            Err(_) => {
                if let Some(response) = mobile_failure(query,headers) { return Some(Ok(response)); }
                let destination=std::env::var("FAILURE_REDIRECT_URI")
                    .unwrap_or_else(|_|"http://localhost:5173/login?error=oauth".to_owned());
                if !configured_redirect(&destination,true) { return Some(Err(oauth_unavailable())); }
                Ok(AuthReply { status:302,body:Value::Null,headers:vec![state_cookie("",0),("location".into(),destination)] })
            },
            result => result,
        }),
        ("POST","/api/auth/refresh") => {
            // ApiFault has no response headers; convert expected auth failures to
            // replies so that clearing invalid refresh cookies is never lost.
            Some(match refresh(headers,db).await {
                Err(error) if error.status == 401 && error.body["code"] == "INVALID_REFRESH_TOKEN" => Ok(AuthReply { status:error.status, body:error.body, headers:clear_token_cookies() }),
                result => result,
            })
        },
        ("POST","/api/auth/logout") => Some(async {
            if let Some(token) = cookie(headers,"refresh_token") {
                db.execute("DELETE FROM refresh_tokens WHERE token_hash=$1", &[&hash(&token)]).await.map_err(|_| internal())?;
            }
            Ok(AuthReply { status:204, body:Value::Null, headers:clear_token_cookies() })
        }.await),
        ("GET" | "PATCH" | "DELETE","/api/users/me") => Some(async {
            let id = principal.ok_or_else(unauthorized)?.id;
            if method == "GET" { return Ok(reply(200,profile(db,id).await?)); }
            let nickname = if method == "PATCH" {
                let input: Value = serde_json::from_slice(body).map_err(|_| fault(400,"INVALID_REQUEST","요청값이 올바르지 않습니다."))?;
                let raw = match input.get("nickname") {
                    Some(Value::String(value)) => value,
                    None | Some(Value::Null) => return Err(invalid("nickname","닉네임을 입력해주세요.")),
                    _ => return Err(invalid("nickname","타입이 올바르지 않습니다.")),
                };
                let nickname = raw.trim_matches(java_whitespace);
                if nickname.is_empty() { return Err(invalid("nickname","닉네임을 입력해주세요.")); }
                if nickname.encode_utf16().count() > 20 { return Err(invalid("nickname","닉네임은 20자 이하여야 합니다.")); }
                Some(nickname.to_owned())
            } else { None };
            db.batch_execute("BEGIN").await.map_err(|_| internal())?;
            let result = async {
                let member = db.query_opt("SELECT status FROM members WHERE id=$1 FOR UPDATE", &[&id]).await.map_err(|_| internal())?.ok_or_else(|| fault(404,"MEMBER_NOT_FOUND","회원을 찾을 수 없습니다."))?;
                if member.get::<_,String>(0) != "ACTIVE" { return Err(fault(401,"WITHDRAWN_MEMBER","탈퇴한 회원입니다.")); }
                if let Some(nickname) = nickname {
                    db.execute("UPDATE members SET nickname=$2,updated_at=now() WHERE id=$1", &[&id,&nickname]).await.map_err(|e| {
                        if e.as_db_error().is_some_and(|d| d.code().code() == "23505" && d.constraint() == Some("uk_members_nickname")) { fault(409,"NICKNAME_ALREADY_EXISTS","이미 사용 중인 닉네임입니다.") } else { internal() }
                    })?;
                    Ok(reply(200,profile(db,id).await?))
                } else {
                    db.execute("DELETE FROM refresh_tokens WHERE member_id=$1", &[&id]).await.map_err(|_| internal())?;
                    db.execute("UPDATE members SET status='WITHDRAWN',withdrawn_at=now(),updated_at=now() WHERE id=$1", &[&id]).await.map_err(|_| internal())?;
                    Ok(AuthReply { status:204,body:Value::Null,headers:clear_token_cookies() })
                }
            }.await;
            finish_transaction(db,result).await
        }.await),
        _ => None,
    }
}
