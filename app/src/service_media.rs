//! Configured external media transports. No default credentials, SDK credential
//! discovery, response fabrication or payload logging. HTTP test endpoints must
//! be explicit loopback addresses; production transports require HTTPS.
use crate::api::{ApiFault, fault};
use base64::{Engine as _, engine::general_purpose::STANDARD};
use hmac::{Hmac, KeyInit, Mac};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::time::Duration;
use tokio_postgres::Client;
type Result<T> = std::result::Result<T, ApiFault>;
const MAX_IMAGE: usize = 5 * 1024 * 1024;
fn fail(code: &str) -> ApiFault {
    fault(
        502,
        code,
        match code {
            "WIKIMEDIA_IMAGE_REQUEST_FAILED" => "Wikimedia Commons 이미지 요청에 실패했습니다.",
            "AI_IMAGE_GENERATION_FAILED" => "AI 이미지 생성에 실패했습니다.",
            "AI_NEWS_GENERATION_FAILED" => "AI 뉴스 생성에 실패했습니다.",
            _ => "이미지 저장소 요청에 실패했습니다.",
        },
    )
}
fn env(name: &str) -> Option<String> {
    std::env::var(name).ok().filter(|s| !s.trim().is_empty())
}
fn configured(primary: &str, alias: &str) -> Option<String> {
    env(primary).or_else(|| env(alias))
}
pub(crate) fn endpoint(raw: &str, code: &str) -> Result<reqwest::Url> {
    let url = reqwest::Url::parse(raw).map_err(|_| fail(code))?;
    if !url.username().is_empty()
        || url.password().is_some()
        || url.fragment().is_some()
        || url.query().is_some()
        || url.host_str().is_none()
        || !(url.scheme() == "https"
            || url.scheme() == "http"
                && matches!(
                    url.host_str(),
                    Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
                ))
    {
        return Err(fail(code));
    }
    Ok(url)
}
fn client(code: &str, seconds: u64) -> Result<reqwest::Client> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(3))
        .timeout(Duration::from_secs(seconds))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| fail(code))
}
pub(crate) async fn bounded(
    mut response: reqwest::Response,
    max: usize,
    code: &str,
) -> Result<Vec<u8>> {
    if !response.status().is_success() || response.content_length().is_some_and(|n| n > max as u64)
    {
        return Err(fail(code));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| fail(code))? {
        if bytes.len() + chunk.len() > max {
            return Err(fail(code));
        }
        bytes.extend_from_slice(&chunk);
    }
    if bytes.is_empty() {
        return Err(fail(code));
    }
    Ok(bytes)
}
pub(crate) async fn openai(path: &str, request: &Value, code: &str, max: usize) -> Result<Value> {
    let key = configured("AI_OPENAI_API_KEY", "OPENAI_API_KEY").ok_or_else(|| fail(code))?;
    let base = env("AI_OPENAI_BASE_URL").unwrap_or_else(|| "https://api.openai.com/v1".into());
    let url = endpoint(&format!("{}/{}", base.trim_end_matches('/'), path), code)?;
    let seconds = env("AI_OPENAI_TIMEOUT_SECONDS")
        .and_then(|s| s.parse::<u64>().ok())
        .filter(|n| *n > 0 && *n <= 240)
        .unwrap_or(120);
    let response = client(code, seconds)?
        .post(url)
        .bearer_auth(key)
        .json(request)
        .send()
        .await
        .map_err(|_| fail(code))?;
    let value: Value =
        serde_json::from_slice(&bounded(response, max, code).await?).map_err(|_| fail(code))?;
    if value.get("error").is_some_and(|e| !e.is_null())
        || value.get("status").is_some_and(|s| s != "completed")
    {
        return Err(fail(code));
    }
    Ok(value)
}
pub(crate) fn output_json(root: &Value, code: &str) -> Result<Value> {
    let mut text = String::new();
    for item in root["output"].as_array().ok_or_else(|| fail(code))? {
        if item["type"] == "message"
            && let Some(content) = item["content"].as_array()
        {
            for part in content {
                if part["type"] == "output_text" {
                    text.push_str(part["text"].as_str().ok_or_else(|| fail(code))?);
                }
            }
        }
    }
    serde_json::from_str(&text).map_err(|_| fail(code))
}
fn metadata<'a>(info: &'a Value, key: &str) -> &'a str {
    info["extmetadata"][key]["value"].as_str().unwrap_or("")
}
fn clean_html(raw: &str) -> String {
    let mut text = String::new();
    let mut in_tag = false;
    for c in raw.chars() {
        if c == '<' {
            in_tag = true;
        } else if c == '>' {
            in_tag = false;
        } else if !in_tag {
            text.push(c);
        }
    }
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}
fn license_allowed(raw: &str) -> bool {
    let lower = raw.trim().to_ascii_lowercase();
    if lower == "public domain" {
        return true;
    }
    let words: Vec<&str> = lower.split(' ').collect();
    let (rest, allow_locale) = if words.first() == Some(&"cc0") {
        (&words[1..], false)
    } else if words.get(..2) == Some(&["cc", "by"]) {
        (&words[2..], true)
    } else {
        return false;
    };
    if rest.is_empty() {
        return true;
    }
    let version = rest[0];
    if version.split('.').count() > 2
        || version.is_empty()
        || !version
            .split('.')
            .all(|v| !v.is_empty() && v.bytes().all(|b| b.is_ascii_digit()))
    {
        return false;
    }
    rest.len() == 1
        || allow_locale
            && rest.len() == 2
            && rest[1].len() == 2
            && rest[1].bytes().all(|b| b.is_ascii_lowercase())
}
fn download_url(raw: &str) -> bool {
    let Ok(url) = reqwest::Url::parse(raw) else {
        return false;
    };
    url.scheme() == "https"
        && url.username().is_empty()
        && url.password().is_none()
        && url.port().is_none()
        && matches!(
            url.host_str(),
            Some("commons.wikimedia.org" | "upload.wikimedia.org" | "thumb.wikimedia.org")
        )
}
fn candidates(value: &Value) -> Result<Vec<Value>> {
    let code = "WIKIMEDIA_IMAGE_REQUEST_FAILED";
    if value.get("error").is_some() {
        return Err(fail(code));
    }
    let pages = match value.get("query").and_then(|q| q.get("pages")) {
        None => return Ok(Vec::new()),
        Some(Value::Array(pages)) => pages,
        _ => return Err(fail(code)),
    };
    let mut result = Vec::new();
    for page in pages {
        let info = &page["imageinfo"][0];
        let mime = info["mime"].as_str().unwrap_or("");
        let title = page["title"].as_str().unwrap_or("");
        let thumbnail = info["thumburl"].as_str().unwrap_or("");
        let license = metadata(info, "LicenseShortName");
        if !matches!(mime, "image/jpeg" | "image/png" | "image/webp")
            || !license_allowed(license)
            || !download_url(thumbnail)
            || title.is_empty()
        {
            continue;
        }
        result.push(json!({"title":title,"thumbnailUrl":thumbnail,"sourceUrl":format!("https://commons.wikimedia.org/wiki/{}",title.replace(' ',"_")),"author":clean_html(metadata(info,"Artist")),"license":license,"licenseUrl":metadata(info,"LicenseUrl"),"width":info["width"].as_i64().unwrap_or(0),"height":info["height"].as_i64().unwrap_or(0)}));
    }
    Ok(result)
}
async fn wiki_query(key: &str, value: &str) -> Result<Vec<Value>> {
    let code = "WIKIMEDIA_IMAGE_REQUEST_FAILED";
    // Explicit configuration keeps local runs from accidentally contacting the
    // public provider. Its production value is https://commons.wikimedia.org.
    let base = env("WIKIMEDIA_BASE_URL").ok_or_else(|| fail(code))?;
    let mut url = endpoint(&format!("{}/w/api.php", base.trim_end_matches('/')), code)?;
    url.query_pairs_mut().extend_pairs([
        ("action", "query"),
        ("prop", "imageinfo"),
        ("iiprop", "url|mime|size|extmetadata"),
        ("iiurlwidth", "1200"),
        ("format", "json"),
        ("formatversion", "2"),
        (key, value),
    ]);
    if key == "gsrsearch" {
        url.query_pairs_mut().extend_pairs([
            ("generator", "search"),
            ("gsrnamespace", "6"),
            ("gsrlimit", "50"),
        ]);
    }
    let ua = env("WIKIMEDIA_USER_AGENT").unwrap_or_else(|| "daynomy/1.0".into());
    let response = client(code, 15)?
        .get(url)
        .header("user-agent", ua)
        .send()
        .await
        .map_err(|_| fail(code))?;
    let json: Value = serde_json::from_slice(&bounded(response, 2_000_000, code).await?)
        .map_err(|_| fail(code))?;
    candidates(&json)
}
pub(crate) async fn wiki_search(keyword: &str) -> Result<Vec<Value>> {
    wiki_query("gsrsearch", keyword).await
}
fn detected(bytes: &[u8]) -> Option<(&'static str, &'static str)> {
    if bytes.starts_with(&[0xff, 0xd8, 0xff]) {
        Some(("image/jpeg", "jpg"))
    } else if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        Some(("image/png", "png"))
    } else if bytes.starts_with(b"RIFF") && bytes.get(8..12) == Some(b"WEBP") {
        Some(("image/webp", "webp"))
    } else {
        None
    }
}
pub(crate) struct StoredImage {
    pub url: String,
    pub source: Value,
}
fn image_transport(raw: &str) -> Result<reqwest::Url> {
    let code = "WIKIMEDIA_IMAGE_REQUEST_FAILED";
    if !download_url(raw) {
        return Err(fail(code));
    }
    let original = reqwest::Url::parse(raw).map_err(|_| fail(code))?;
    let Some(base) = env("WIKIMEDIA_IMAGE_BASE_URL") else {
        return Ok(original);
    };
    // Deterministic local transport substitution only. The candidate must
    // still pass the production Wikimedia HTTPS host policy above. No URL
    // supplied by an administrator can authorize a loopback download.
    let mut target = endpoint(&base, code)?;
    if !matches!(
        target.host_str(),
        Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
    ) {
        return Err(fail(code));
    }
    let path = format!("{}{}", target.path().trim_end_matches('/'), original.path());
    target.set_path(&path);
    target.set_query(original.query());
    Ok(target)
}
pub(crate) async fn wiki_import(title: &str, db: &Client) -> Result<StoredImage> {
    let code = "WIKIMEDIA_IMAGE_REQUEST_FAILED";
    let candidate = wiki_query("titles", title)
        .await?
        .into_iter()
        .find(|c| c["title"] == title)
        .ok_or_else(|| fail(code))?;
    let response = client(code, 15)?
        .get(image_transport(
            candidate["thumbnailUrl"]
                .as_str()
                .ok_or_else(|| fail(code))?,
        )?)
        .header(
            "user-agent",
            env("WIKIMEDIA_USER_AGENT").unwrap_or_else(|| "daynomy/1.0".into()),
        )
        .send()
        .await
        .map_err(|_| fail(code))?;
    let header = response
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .split(';')
        .next()
        .unwrap_or("")
        .to_owned();
    let bytes = bounded(response, MAX_IMAGE, code).await?;
    let (mime, extension) = detected(&bytes)
        .or(match header.as_str() {
            "image/jpeg" => Some(("image/jpeg", "jpg")),
            "image/png" => Some(("image/png", "png")),
            "image/webp" => Some(("image/webp", "webp")),
            _ => None,
        })
        .ok_or_else(|| fail(code))?;
    let mut stored = upload(&bytes, mime, extension, db).await?;
    stored.source = json!({"name":"Wikimedia Commons","url":candidate["sourceUrl"],"author":candidate["author"],"license":candidate["license"],"licenseUrl":candidate["licenseUrl"],"type":"WIKIMEDIA"});
    Ok(stored)
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn hmac(key: &[u8], message: &str) -> Result<Vec<u8>> {
    let mut mac =
        Hmac::<Sha256>::new_from_slice(key).map_err(|_| fail("S3_IMAGE_STORAGE_FAILED"))?;
    mac.update(message.as_bytes());
    Ok(mac.finalize().into_bytes().to_vec())
}
fn aws_uri(raw: &str) -> Result<String> {
    let mut bytes = Vec::new();
    let mut input = raw.bytes();
    while let Some(b) = input.next() {
        if b == b'%' {
            let hi = input.next().and_then(|b| (b as char).to_digit(16));
            let lo = input.next().and_then(|b| (b as char).to_digit(16));
            let (Some(hi), Some(lo)) = (hi, lo) else {
                return Err(fail("S3_IMAGE_STORAGE_FAILED"));
            };
            bytes.push((hi * 16 + lo) as u8);
        } else {
            bytes.push(b);
        }
    }
    Ok(bytes
        .into_iter()
        .map(|b| {
            if b.is_ascii_alphanumeric() || matches!(b, b'-' | b'.' | b'_' | b'~' | b'/') {
                (b as char).to_string()
            } else {
                format!("%{b:02X}")
            }
        })
        .collect())
}
fn s3_signature(
    method: &str,
    uri: &str,
    payload: &str,
    headers: &BTreeMap<String, String>,
    region: &str,
    secret: &str,
    date: &str,
) -> Result<(String, String, String)> {
    let signed = headers
        .keys()
        .map(String::as_str)
        .collect::<Vec<_>>()
        .join(";");
    let canonical_headers = headers
        .iter()
        .map(|(k, v)| {
            format!(
                "{k}:{}\n",
                v.split_whitespace().collect::<Vec<_>>().join(" ")
            )
        })
        .collect::<String>();
    let canonical = format!(
        "{method}\n{}\n\n{canonical_headers}\n{signed}\n{payload}",
        aws_uri(uri)?.as_str()
    );
    let scope = format!("{}/{region}/s3/aws4_request", &date[..8]);
    let to_sign = format!(
        "AWS4-HMAC-SHA256\n{date}\n{scope}\n{}",
        hex(&Sha256::digest(canonical.as_bytes()))
    );
    let day_key = hmac(format!("AWS4{secret}").as_bytes(), &date[..8])?;
    let region_key = hmac(&day_key, region)?;
    let service_key = hmac(&region_key, "s3")?;
    let signing_key = hmac(&service_key, "aws4_request")?;
    Ok((scope, signed, hex(&hmac(&signing_key, &to_sign)?)))
}
async fn s3_request(
    method: &str,
    name: &str,
    bytes: &[u8],
    mime: Option<&str>,
    db: &Client,
) -> Result<()> {
    let code = "S3_IMAGE_STORAGE_FAILED";
    if name.is_empty() || name.contains(['/', '\\']) || matches!(name, "." | "..") {
        return Err(fail(code));
    }
    let region = configured("S3_REGION", "AWS_REGION").ok_or_else(|| fail(code))?;
    let bucket = configured("S3_BUCKET", "AWS_S3_BUCKET").ok_or_else(|| fail(code))?;
    let prefix =
        configured("S3_OBJECT_PREFIX", "AWS_S3_OBJECT_PREFIX").ok_or_else(|| fail(code))?;
    if prefix.starts_with('/')
        || prefix.ends_with('/')
        || prefix.contains("//")
        || prefix.contains('\\')
        || prefix.split('/').any(|s| matches!(s, "." | ".."))
        || !bucket
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-'))
    {
        return Err(fail(code));
    }
    let access = env("AWS_ACCESS_KEY_ID").ok_or_else(|| fail(code))?;
    let secret = env("AWS_SECRET_ACCESS_KEY").ok_or_else(|| fail(code))?;
    let base =
        env("S3_ENDPOINT_URL").unwrap_or_else(|| format!("https://s3.{region}.amazonaws.com"));
    let mut url = endpoint(&base, code)?;
    {
        let mut path = url.path_segments_mut().map_err(|_| fail(code))?;
        path.pop_if_empty().push(&bucket);
        for segment in prefix.split('/') {
            path.push(segment);
        }
        path.push(name);
    }
    let date: String = db
        .query_one(
            "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYYMMDD\"T\"HH24MISS\"Z\"')",
            &[],
        )
        .await
        .map_err(|_| fail(code))?
        .get(0);
    let payload = hex(&Sha256::digest(bytes));
    let host = match url.port() {
        Some(port) => format!("{}:{port}", url.host_str().ok_or_else(|| fail(code))?),
        None => url.host_str().ok_or_else(|| fail(code))?.to_owned(),
    };
    let mut headers = BTreeMap::from([
        ("host".to_owned(), host),
        ("x-amz-content-sha256".to_owned(), payload.clone()),
        ("x-amz-date".to_owned(), date.clone()),
    ]);
    if let Some(mime) = mime {
        headers.insert("content-type".into(), mime.into());
        headers.insert(
            "cache-control".into(),
            "public, max-age=31536000, immutable".into(),
        );
    }
    if let Some(token) = env("AWS_SESSION_TOKEN") {
        headers.insert("x-amz-security-token".into(), token);
    }
    let (scope, signed, signature) = s3_signature(
        method,
        url.path(),
        &payload,
        &headers,
        &region,
        &secret,
        &date,
    )?;
    let authorization = format!(
        "AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed}, Signature={}",
        signature
    );
    let method = reqwest::Method::from_bytes(method.as_bytes()).map_err(|_| fail(code))?;
    let mut request = client(code, 30)?
        .request(method, url)
        .header("authorization", authorization);
    for (name, value) in headers {
        request = request.header(name, value);
    }
    let response = request
        .body(bytes.to_vec())
        .send()
        .await
        .map_err(|_| fail(code))?;
    if !response.status().is_success() {
        return Err(fail(code));
    }
    Ok(())
}
pub(crate) async fn upload(
    bytes: &[u8],
    mime: &str,
    extension: &str,
    db: &Client,
) -> Result<StoredImage> {
    let code = "S3_IMAGE_STORAGE_FAILED";
    if bytes.is_empty()
        || bytes.len() > MAX_IMAGE
        || !matches!(
            (mime, extension),
            ("image/jpeg", "jpg") | ("image/png", "png") | ("image/webp", "webp")
        )
    {
        return Err(fail(code));
    }
    let base =
        configured("S3_PUBLIC_BASE_URL", "AWS_S3_PUBLIC_BASE_URL").ok_or_else(|| fail(code))?;
    let mut public = endpoint(&base, code)?;
    let name = format!("{}.{}", uuid::Uuid::new_v4(), extension);
    public
        .path_segments_mut()
        .map_err(|_| fail(code))?
        .pop_if_empty()
        .push(&name);
    s3_request("PUT", &name, bytes, Some(mime), db).await?;
    Ok(StoredImage {
        url: public.to_string(),
        source: json!({"name":"","url":"","author":"","license":"","licenseUrl":"","type":"MANUAL"}),
    })
}
pub(crate) async fn delete_managed(raw: Option<&str>, db: &Client) -> Result<()> {
    let Some(raw) = raw.filter(|s| !s.is_empty()) else {
        return Ok(());
    };
    let Some(base) = configured("S3_PUBLIC_BASE_URL", "AWS_S3_PUBLIC_BASE_URL") else {
        return Ok(());
    };
    let prefix = format!("{}/", base.trim_end_matches('/'));
    let Some(name) = raw.strip_prefix(&prefix) else {
        return Ok(());
    };
    s3_request("DELETE", name, &[], None, db).await
}
pub(crate) async fn ai_image(
    title: &str,
    content: &str,
    category: &str,
    db: &Client,
) -> Result<StoredImage> {
    let code = "AI_IMAGE_GENERATION_FAILED";
    let prompt = IMAGE_PROMPT
        .replacen("%s", category, 1)
        .replacen("%s", title, 1)
        .replacen("%s", content, 1);
    let model = configured("AI_OPENAI_IMAGE_MODEL", "OPENAI_IMAGE_MODEL")
        .unwrap_or_else(|| "gpt-image-1-mini".into());
    let request = json!({"model":model,"prompt":prompt,"n":1,"size":"1536x1024","quality":"low","output_format":"webp"});
    let root = openai("images/generations", &request, code, 8_000_000).await?;
    let encoded = root["data"]
        .as_array()
        .and_then(|v| v.iter().find_map(|x| x["b64_json"].as_str()))
        .filter(|s| !s.is_empty())
        .ok_or_else(|| fail(code))?;
    let bytes = STANDARD.decode(encoded).map_err(|_| fail(code))?;
    if detected(&bytes) != Some(("image/webp", "webp")) || bytes.len() > MAX_IMAGE {
        return Err(fail(code));
    }
    let mut stored = upload(&bytes, "image/webp", "webp", db).await?;
    stored.source =
        json!({"name":"","url":"","author":"","license":"","licenseUrl":"","type":"AI_GENERATED"});
    Ok(stored)
}

const IMAGE_PROMPT: &str = r###"Create a clean editorial finance news image for a Korean financial news app.

Absolute text policy: the image must contain no visible text by default. Do not include words,
letters, Korean characters, numbers, prices, dates, logos, brand marks, ticker symbols, labels,
captions, headlines, signs, newspapers, documents, contracts, screens, dashboards, charts, graphs,
watermarks, or UI elements. Keep every writing surface blank, out of frame, or too abstract to read.
Do not create fake writing, pseudo-text, scribbles, or random glyphs.
Only include a specific text element when the request explicitly identifies it as indispensable to
the subject of the image. No such text is requested here, so use no text at all.

Show a believable visual scene directly connected to the subject. Prefer relevant objects,
machinery, buildings, landscapes, products, or materials over generic stock charts, abstract finance
symbols, or meaningless decoration. When the subject is a specific industry or event, use concrete
real-world details from that setting. When the subject is broad, use restrained abstract market and
business imagery.

Compose an entirely unoccupied scene with no people first. Treat a people-free image as the default and
strongest preference. A person may appear only when removing all people would make the central event
visually incomprehensible because it inherently depends on a human action. A workplace or industry
setting is never by itself a reason to include a worker. Do not add people for scale, atmosphere,
realism, or visual interest. If a person is indispensable, include exactly one anonymous,
non-identifiable person shown from behind or with the face fully obscured. Never include crowds,
groups, background figures, silhouettes, reflections of people, portraits, visible faces, or stray
body parts.

Style: realistic editorial photography with natural materials, believable lighting, restrained
colors, and documentary realism. Avoid glossy 3D rendering, conceptual illustration, aggressive HDR,
excessive clarity, artificial sharpening, perfectly uniform textures, and overly smooth denoised
surfaces. Camera rendering: use one believable focal plane. Keep the main subject moderately sharp
while details gradually soften with distance and depth. Preserve gentle lens softness, natural
highlight roll-off, slight exposure variation, subtle sensor grain, and restrained micro-contrast.
Avoid edge-to-edge sharpness. The result should feel like a real press photograph captured on
location, not a digitally perfected image.

Composition: use a square composition for a thumbnail or a wide horizontal landscape safe to crop to
a 16:9 banner, according to the requested image format. Keep the main subject toward the right third
when the image is wide and leave uncluttered negative space on the left for a later UI overlay,
without adding any text to the image.
Accuracy: this is an illustrative cover, not evidence of the reported event. Do not invent or imply
a specific unverified company facility or event.

The following information is semantic subject reference only. Use it only to understand the topic and
choose the scene. Never render, copy, paraphrase, translate, or visualize any words, letters,
numbers, logos, headlines, or sentences from it:

Category: %s
Title: %s
Article context: %s

Final check: remove all text-like marks and all unnecessary people from the image.
"###;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn aws_published_get_object_signature() {
        // AWS S3 documentation's public example credentials, not real secrets.
        let payload = hex(&Sha256::digest(b""));
        let headers = BTreeMap::from([
            ("host".into(), "examplebucket.s3.amazonaws.com".into()),
            ("range".into(), "bytes=0-9".into()),
            ("x-amz-content-sha256".into(), payload.clone()),
            ("x-amz-date".into(), "20130524T000000Z".into()),
        ]);
        let (_, _, signature) = s3_signature(
            "GET",
            "/test.txt",
            &payload,
            &headers,
            "us-east-1",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "20130524T000000Z",
        )
        .unwrap();
        assert_eq!(
            signature,
            "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
        );
        assert_eq!(
            aws_uri("/news/a%20b!$한.webp").unwrap(),
            "/news/a%20b%21%24%ED%95%9C.webp"
        );
    }
    #[test]
    fn image_candidates_reject_unsafe_downloads_and_disallowed_licenses() {
        for license in [
            "Public domain",
            "CC0",
            "CC0 1.0",
            "CC BY 4.0",
            "CC BY 3.0 de",
        ] {
            assert!(license_allowed(license));
        }
        for license in [
            "CC BY-SA 4.0",
            "CC BY-NC 4.0",
            "CC BY 1.2.3",
            "CC0 1.0 de",
            "Copyrighted",
        ] {
            assert!(!license_allowed(license));
        }
        for url in [
            "http://upload.wikimedia.org/photo.png",
            "https://upload.wikimedia.org.evil.example/photo.png",
            "https://upload.wikimedia.org:444/photo.png",
            "https://user@upload.wikimedia.org/photo.png",
        ] {
            assert!(!download_url(url));
        }
        assert!(download_url(
            "https://upload.wikimedia.org/commons/a/photo.png"
        ));
    }
}
