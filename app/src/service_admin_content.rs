//! Administrator content and featured-people persistence. Authentication/CSRF is
//! enforced by the parent dispatcher. Configured YouTube, cited social search,
//! and media adapters return real provider results or typed provider failures.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, query, rows};
use crate::{service_media, service_social};
use serde_json::{Value, json};
use std::collections::HashSet;
use tokio_postgres::Client;

type Result<T> = std::result::Result<T, ApiFault>;

fn error(code: &str) -> ApiFault {
    let (status, message) = match code {
        "ASSET_NOT_FOUND" => (404, "자산을 찾을 수 없습니다."),
        "ASSET_CONTENT_NOT_FOUND" => (404, "종목 관련 자료를 찾을 수 없습니다."),
        "ASSET_CONTENT_ALREADY_EXISTS" => (409, "이미 등록된 URL입니다."),
        "FEATURED_PERSON_NOT_FOUND" => (404, "주요 인물을 찾을 수 없습니다."),
        "FEATURED_PERSON_ALREADY_EXISTS" => (409, "이미 등록된 인물입니다."),
        "FEATURED_PERSON_POST_NOT_FOUND" => (404, "주요 인물 게시물을 찾을 수 없습니다."),
        "FEATURED_PERSON_POST_ALREADY_EXISTS" => (409, "이미 등록된 게시물 URL입니다."),
        "FEATURED_PERSON_POST_CANDIDATE_NOT_FOUND" => {
            (404, "수집한 게시물 후보를 찾을 수 없습니다.")
        }
        "FEATURED_PERSON_POST_CANDIDATE_NOT_PENDING" => {
            (409, "대기 중인 게시물 후보만 검토할 수 있습니다.")
        }
        "FEATURED_PERSON_POST_COLLECTION_PERIOD_INVALID" => (
            400,
            "수집 기간은 시작일이 종료일보다 늦지 않은 최대 31일이어야 합니다.",
        ),
        "FEATURED_PERSON_INVALID_SOCIAL_URL" => (400, "계정 또는 게시물 URL이 올바르지 않습니다."),
        "YOUTUBE_API_NOT_CONFIGURED" => (503, "YouTube API 키가 설정되지 않았습니다."),
        "YOUTUBE_API_REQUEST_FAILED" => (502, "YouTube API 요청에 실패했습니다."),
        "AI_SOCIAL_SEARCH_FAILED" => (502, "Threads·X 게시물 검색에 실패했습니다."),
        "WIKIMEDIA_IMAGE_REQUEST_FAILED" => (502, "Wikimedia Commons 이미지 요청에 실패했습니다."),
        "S3_IMAGE_STORAGE_FAILED" => (502, "이미지 저장소 요청에 실패했습니다."),
        _ => return internal(),
    };
    fault(status, code, message)
}
fn method_error() -> ApiFault {
    fault(
        405,
        "METHOD_NOT_ALLOWED",
        "지원하지 않는 HTTP 메서드입니다.",
    )
}
fn body_error() -> ApiFault {
    invalid("requestBody", "요청 본문을 읽을 수 없습니다.")
}
fn java_space(c: char) -> bool {
    matches!(c,'\u{0009}'..='\u{000d}'|'\u{001c}'..='\u{0020}'|'\u{1680}'|'\u{2000}'..='\u{2006}'|'\u{2008}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{205f}'|'\u{3000}')
}
fn strip(value: &str) -> &str {
    value.trim_matches(java_space)
}
fn len(value: &str) -> usize {
    value.encode_utf16().count()
}
fn optional(req: &Value, key: &str) -> Result<Option<String>> {
    match req.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s.clone())),
        _ => Err(body_error()),
    }
}
fn stripped(value: Option<String>) -> Option<String> {
    value.and_then(|s| {
        let v = strip(&s);
        (!v.is_empty()).then(|| v.to_owned())
    })
}
fn parse_body(body: &[u8]) -> Result<Value> {
    let value: Value = serde_json::from_slice(body).map_err(|_| body_error())?;
    if value.is_object() {
        Ok(value)
    } else {
        Err(body_error())
    }
}
fn id(raw: &str, field: &str) -> Result<i64> {
    let value =
        crate::api::path_integer(raw).ok_or_else(|| invalid(field, "타입이 올바르지 않습니다."))?;
    if value > 0 {
        Ok(value)
    } else {
        Err(invalid(field, "0보다 커야 합니다"))
    }
}
fn add(errors: &mut Vec<Value>, field: &str, reason: &str) {
    errors.push(json!({"field":field,"reason":reason}));
}
fn finish(errors: Vec<Value>) -> Result<()> {
    if errors.is_empty() {
        Ok(())
    } else {
        Err(ApiFault {
            status: 400,
            body: json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":errors}),
        })
    }
}
fn url_pattern(value: &str) -> bool {
    (value.starts_with("http://") || value.starts_with("https://"))
        && value
            .split_once("://")
            .is_some_and(|(_, rest)| !rest.is_empty())
        && !value
            .chars()
            .any(|c| matches!(c, ' ' | '\t' | '\n' | '\r' | '\u{000b}' | '\u{000c}'))
}
fn string_rules(
    errors: &mut Vec<Value>,
    field: &str,
    value: Option<&str>,
    required: Option<&str>,
    max: usize,
    size_reason: &str,
    url_reason: Option<&str>,
) {
    if required.is_some() && value.is_none_or(|v| v.chars().all(java_space)) {
        add(errors, field, required.unwrap_or(""));
    }
    if let Some(value) = value {
        if len(value) > max {
            add(errors, field, size_reason);
        }
        if let Some(reason) = url_reason
            && !url_pattern(value)
        {
            add(errors, field, reason);
        }
    }
}
fn source(req: &Value, errors: &mut Vec<Value>) -> Result<String> {
    match req.get("sourceType") {
        None | Some(Value::Null) => {
            add(errors, "sourceType", "출처를 선택해주세요.");
            Ok(String::new())
        }
        Some(Value::String(s))
            if matches!(
                s.as_str(),
                "YOUTUBE" | "THREADS" | "X" | "INTERNAL_NEWS" | "OTHER"
            ) =>
        {
            Ok(s.clone())
        }
        _ => Err(body_error()),
    }
}
fn sql_error(failure: tokio_postgres::Error, duplicate: &str) -> ApiFault {
    if failure
        .as_db_error()
        .is_some_and(|e| e.code().code() == "23505")
    {
        error(duplicate)
    } else {
        internal()
    }
}

pub async fn handle(
    method: &str,
    path: &str,
    raw_query: &str,
    body: &[u8],
    db: &Client,
) -> Option<Outcome> {
    let pieces: Vec<&str> = path.trim_matches('/').split('/').collect();
    if pieces.starts_with(&["api", "admin", "assets"])
        && pieces.len() >= 5
        && pieces[4] == "contents"
    {
        return Some(content_route(method, &pieces, raw_query, body, db).await);
    }
    if pieces.starts_with(&["api", "admin", "people"]) {
        return Some(people_route(method, &pieces[3..], raw_query, body, db).await);
    }
    None
}

async fn asset_exists(aid: i64, db: &Client) -> Result<Value> {
    rows(db,"SELECT json_build_object('assetId',id,'assetCode',asset_code,'assetName',name)::text FROM assets WHERE id=$1",&[&aid]).await?.pop().ok_or_else(||error("ASSET_NOT_FOUND"))
}
const CONTENT_DTO: &str = "json_build_object('id',c.id,'assetId',c.asset_id,'sourceType',c.source_type,'title',c.title,'url',c.url,'imageUrl',CASE WHEN c.news_id IS NULL THEN c.image_url ELSE n.image_url END,'createdAt',c.created_at,'publishedDate',c.published_date)::text";
async fn content_route(
    method: &str,
    pieces: &[&str],
    raw_query: &str,
    body: &[u8],
    db: &Client,
) -> Outcome {
    let aid = id(pieces[3], "assetId")?;
    if pieces.len() == 5 {
        match method {
            "GET" => {
                let mut response = asset_exists(aid, db).await?;
                let sql = format!(
                    "SELECT {CONTENT_DTO} FROM stock_related_contents c LEFT JOIN news n ON n.id=c.news_id WHERE c.asset_id=$1 AND (c.news_id IS NULL OR n.status='PUBLISHED') ORDER BY c.created_at DESC,c.id DESC"
                );
                response["contents"] = Value::Array(rows(db, &sql, &[&aid]).await?);
                return Ok((200, response));
            }
            "POST" => return create_content(aid, body, db).await,
            _ => return Err(method_error()),
        }
    }
    if pieces.len() != 6 {
        return Err(fault(404, "NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."));
    }
    if matches!(pieces[5], "youtube-search" | "social-search") {
        if method != "GET" {
            return Err(method_error());
        }
        let params = query(raw_query)?;
        let keyword = params
            .get("keyword")
            .ok_or_else(|| invalid("keyword", "필수 요청 파라미터입니다."))?;
        if !(2..=100).contains(&len(keyword)) {
            return Err(invalid("keyword", "크기가 2에서 100 사이여야 합니다"));
        }
        asset_exists(aid, db).await?;
        let items = if pieces[5] == "youtube-search" {
            service_social::youtube_search(strip(keyword)).await?
        } else {
            service_social::social_search(strip(keyword)).await?
        };
        return Ok((200, json!({"items":items})));
    }
    let cid = id(pieces[5], "contentId")?;
    if method != "DELETE" {
        return Err(method_error());
    }
    asset_exists(aid, db).await?;
    let changed = db
        .execute(
            "DELETE FROM stock_related_contents WHERE id=$1 AND asset_id=$2",
            &[&cid, &aid],
        )
        .await
        .map_err(|_| internal())?;
    if changed == 0 {
        return Err(error("ASSET_CONTENT_NOT_FOUND"));
    }
    Ok((204, Value::Null))
}
async fn create_content(aid: i64, body: &[u8], db: &Client) -> Outcome {
    let req = parse_body(body)?;
    let mut errors = Vec::new();
    let kind = source(&req, &mut errors)?;
    let title = optional(&req, "title")?;
    let url = optional(&req, "url")?;
    let image = optional(&req, "imageUrl")?;
    let date = optional(&req, "publishedDate")?;
    string_rules(
        &mut errors,
        "title",
        title.as_deref(),
        Some("제목을 입력해주세요."),
        255,
        "제목은 255자 이하여야 합니다.",
        None,
    );
    string_rules(
        &mut errors,
        "url",
        url.as_deref(),
        Some("URL을 입력해주세요."),
        2000,
        "URL은 2000자 이하여야 합니다.",
        Some("http 또는 https URL을 입력해주세요."),
    );
    string_rules(
        &mut errors,
        "imageUrl",
        image.as_deref(),
        None,
        2000,
        "이미지 URL은 2000자 이하여야 합니다.",
        Some("http 또는 https 이미지 URL을 입력해주세요."),
    );
    if let Some(date) = &date
        && !date_valid(date)
    {
        return Err(body_error());
    }
    finish(errors)?;
    asset_exists(aid, db).await?;
    let title = strip(title.as_deref().ok_or_else(body_error)?);
    let url = strip(url.as_deref().ok_or_else(body_error)?);
    let image = stripped(image);
    let inserted=db.query_one("INSERT INTO stock_related_contents(asset_id,source_type,title,url,image_url,published_date,created_at,updated_at) VALUES($1,$2,$3,$4,$5,coalesce($6::text::date,(clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date),clock_timestamp(),clock_timestamp()) RETURNING id",&[&aid,&kind,&title,&url,&image,&date]).await.map_err(|e|sql_error(e,"ASSET_CONTENT_ALREADY_EXISTS"))?;
    let cid: i64 = inserted.get(0);
    let sql = format!(
        "SELECT {CONTENT_DTO} FROM stock_related_contents c LEFT JOIN news n ON n.id=c.news_id WHERE c.id=$1"
    );
    Ok((
        201,
        rows(db, &sql, &[&cid]).await?.pop().ok_or_else(internal)?,
    ))
}
const POST_DTO: &str = "json_build_object('id',p.id,'sourceType',p.source_type,'title',p.title,'url',p.url,'publishedAt',p.published_at,'createdAt',p.created_at)";
const CANDIDATE_DTO: &str = "json_build_object('id',p.id,'sourceType',p.source_type,'title',p.title,'url',p.url,'publishedAt',p.published_at,'status',p.status,'createdAt',p.created_at)";
async fn person_exists(pid: i64, db: &Client) -> Result<Value> {
    rows(db,"SELECT json_build_object('id',id,'name',name,'xProfileUrl',x_profile_url,'threadsProfileUrl',threads_profile_url,'youtubeProfileUrl',youtube_profile_url,'profileImageUrl',profile_image_url,'createdAt',created_at)::text FROM featured_people WHERE id=$1",&[&pid]).await?.pop().ok_or_else(||error("FEATURED_PERSON_NOT_FOUND"))
}
async fn person_response(pid: i64, db: &Client) -> Result<Value> {
    let mut person = person_exists(pid, db).await?;
    let sql = format!(
        "SELECT {POST_DTO}::text FROM featured_person_posts p WHERE person_id=$1 AND status='APPROVED' ORDER BY published_at DESC NULLS LAST,created_at DESC,id DESC"
    );
    person["posts"] = Value::Array(rows(db, &sql, &[&pid]).await?);
    Ok(person)
}
async fn people_route(
    method: &str,
    path: &[&str],
    raw_query: &str,
    body: &[u8],
    db: &Client,
) -> Outcome {
    if path.is_empty() {
        return match method {
            "GET" => {
                let records = db
                    .query("SELECT id FROM featured_people ORDER BY created_at,id", &[])
                    .await
                    .map_err(|_| internal())?;
                let mut people = Vec::new();
                for record in records {
                    people.push(person_response(record.get(0), db).await?);
                }
                Ok((200, json!({"people":people})))
            }
            "POST" => save_person(None, body, db).await,
            _ => Err(method_error()),
        };
    }
    if path[0] == "post-candidates" {
        return match path {
            [_] if method == "GET" => inbox(raw_query, db).await,
            [_, "bulk-approve"] if method == "POST" => bulk(None, true, body, db).await,
            [_, "bulk-reject"] if method == "POST" => bulk(None, false, body, db).await,
            [_] | [_, "bulk-approve"] | [_, "bulk-reject"] => Err(method_error()),
            _ => Err(fault(404, "NOT_FOUND", "요청한 리소스를 찾을 수 없습니다.")),
        };
    }
    let pid = id(path[0], "personId")?;
    match path {
        [_] => match method {
            "PUT" => save_person(Some(pid), body, db).await,
            "DELETE" => delete_person(pid, db).await,
            _ => Err(method_error()),
        },
        [_, "posts"] => {
            if method == "POST" {
                create_post(pid, body, db).await
            } else {
                Err(method_error())
            }
        }
        [_, "posts", "search"] => {
            if method == "GET" {
                let person = person_exists(pid, db).await?;
                let target = [
                    person["name"].as_str(),
                    person["xProfileUrl"].as_str(),
                    person["threadsProfileUrl"].as_str(),
                ]
                .into_iter()
                .flatten()
                .filter(|s| !strip(s).is_empty())
                .collect::<Vec<_>>()
                .join(" ");
                Ok((
                    200,
                    json!({"items":service_social::social_search(&target).await?}),
                ))
            } else {
                Err(method_error())
            }
        }
        [_, "posts", post] => {
            let post = id(post, "postId")?;
            if method != "DELETE" {
                return Err(method_error());
            }
            person_exists(pid, db).await?;
            let count = db
                .execute(
                    "DELETE FROM featured_person_posts WHERE id=$1 AND person_id=$2",
                    &[&post, &pid],
                )
                .await
                .map_err(|_| internal())?;
            if count == 0 {
                return Err(error("FEATURED_PERSON_POST_NOT_FOUND"));
            }
            Ok((204, Value::Null))
        }
        [_, "post-candidates"] => {
            if method == "GET" {
                pending(pid, db).await
            } else {
                Err(method_error())
            }
        }
        [_, "post-candidates", "collect"] => {
            if method == "POST" {
                collect(pid, raw_query, db).await
            } else {
                Err(method_error())
            }
        }
        [_, "post-candidates", "bulk-approve"] => {
            if method == "POST" {
                bulk(Some(pid), true, body, db).await
            } else {
                Err(method_error())
            }
        }
        [_, "post-candidates", "bulk-reject"] => {
            if method == "POST" {
                bulk(Some(pid), false, body, db).await
            } else {
                Err(method_error())
            }
        }
        [_, "post-candidates", candidate, action] if matches!(*action, "approve" | "reject") => {
            let cid = id(candidate, "candidateId")?;
            if method != "POST" {
                return Err(method_error());
            }
            let result = transition(Some(pid), cid, *action == "approve", db).await?;
            Ok((if *action == "approve" { 200 } else { 204 }, result))
        }
        _ => Err(fault(404, "NOT_FOUND", "요청한 리소스를 찾을 수 없습니다.")),
    }
}
async fn delete_person(pid: i64, db: &Client) -> Outcome {
    db.batch_execute("BEGIN").await.map_err(|_| internal())?;
    let result = async {
        db.query_opt(
            "SELECT id FROM featured_people WHERE id=$1 FOR UPDATE",
            &[&pid],
        )
        .await
        .map_err(|_| internal())?
        .ok_or_else(|| error("FEATURED_PERSON_NOT_FOUND"))?;
        let person = person_exists(pid, db).await?;
        db.execute("DELETE FROM featured_people WHERE id=$1", &[&pid])
            .await
            .map_err(|_| internal())?;
        service_media::delete_managed(person["profileImageUrl"].as_str(), db).await?;
        Ok((204, Value::Null))
    }
    .await;
    finish_transaction(result, db).await
}
async fn finish_transaction(result: Outcome, db: &Client) -> Outcome {
    if result.is_err() {
        let _ = db.batch_execute("ROLLBACK").await;
        return result;
    }
    if db.batch_execute("COMMIT").await.is_err() {
        let _ = db.batch_execute("ROLLBACK").await;
        return Err(internal());
    }
    result
}
async fn cleanup_profile_image(url: Option<&str>, db: &Client) {
    if service_media::delete_managed(url, db).await.is_err() {
        eprintln!("event=media.cleanup_failed provider=s3");
    }
}
async fn save_person(pid: Option<i64>, body: &[u8], db: &Client) -> Outcome {
    let req = parse_body(body)?;
    let mut errors = Vec::new();
    let name = optional(&req, "name")?;
    string_rules(
        &mut errors,
        "name",
        name.as_deref(),
        Some("인물 이름을 입력해주세요."),
        100,
        "인물 이름은 100자 이하여야 합니다.",
        None,
    );
    let x = optional(&req, "xProfileUrl")?;
    let threads = optional(&req, "threadsProfileUrl")?;
    let youtube = optional(&req, "youtubeProfileUrl")?;
    for (key, value, size, pattern) in [
        (
            "xProfileUrl",
            x.as_deref(),
            "X 프로필 URL은 2000자 이하여야 합니다.",
            "올바른 X 프로필 URL을 입력해주세요.",
        ),
        (
            "threadsProfileUrl",
            threads.as_deref(),
            "Threads 프로필 URL은 2000자 이하여야 합니다.",
            "올바른 Threads 프로필 URL을 입력해주세요.",
        ),
        (
            "youtubeProfileUrl",
            youtube.as_deref(),
            "YouTube 채널 URL은 2000자 이하여야 합니다.",
            "올바른 YouTube 채널 URL을 입력해주세요.",
        ),
    ] {
        string_rules(&mut errors, key, value, None, 2000, size, Some(pattern));
    }
    if let Some(selection) = req.get("profileImageSelection").filter(|v| !v.is_null()) {
        if !selection.is_object() {
            return Err(body_error());
        }
        let title = optional(selection, "title")?;
        string_rules(
            &mut errors,
            "profileImageSelection.title",
            title.as_deref(),
            Some("Wikimedia Commons 이미지 파일 제목은 필수입니다."),
            500,
            "Wikimedia Commons 이미지 파일 제목은 500자 이하여야 합니다.",
            None,
        );
    }
    finish(errors)?;
    let old = if let Some(pid) = pid {
        Some(person_exists(pid, db).await?)
    } else {
        None
    };
    let name = strip(name.as_deref().ok_or_else(body_error)?);
    let exists:bool=db.query_one("SELECT EXISTS(SELECT 1 FROM featured_people WHERE name=$1 AND ($2::bigint IS NULL OR id<>$2))",&[&name,&pid]).await.map_err(|_|internal())?.get(0);
    if exists {
        return Err(error("FEATURED_PERSON_ALREADY_EXISTS"));
    }
    let x = normalize_optional(x, "X")?;
    let threads = normalize_optional(threads, "THREADS")?;
    let youtube = normalize_optional(youtube, "YOUTUBE")?;
    let selection = req
        .get("profileImageSelection")
        .filter(|v| !v.is_null())
        .and_then(|v| v["title"].as_str());
    let uploaded = if let Some(title) = selection {
        Some(service_media::wiki_import(title, db).await?)
    } else {
        None
    };
    let mut previous_image = old
        .as_ref()
        .and_then(|p| p["profileImageUrl"].as_str())
        .map(str::to_owned);
    let result=async{
        db.batch_execute("BEGIN").await.map_err(|_|internal())?;
        let result=async{
            if let Some(pid)=pid{
                let current=db.query_opt("SELECT profile_image_url FROM featured_people WHERE id=$1 FOR UPDATE",&[&pid]).await.map_err(|_|internal())?.ok_or_else(||error("FEATURED_PERSON_NOT_FOUND"))?;
                previous_image=current.get::<_,Option<String>>(0);
            }
            let image=uploaded.as_ref().map(|i|i.url.clone()).or_else(||previous_image.clone());
            let pid=if let Some(pid)=pid{
                db.execute("UPDATE featured_people SET name=$2,x_profile_url=$3,threads_profile_url=$4,youtube_profile_url=$5,profile_image_url=$6,updated_at=clock_timestamp() WHERE id=$1",&[&pid,&name,&x,&threads,&youtube,&image]).await.map_err(|e|sql_error(e,"FEATURED_PERSON_ALREADY_EXISTS"))?;pid
            }else{
                db.query_one("INSERT INTO featured_people(name,x_profile_url,threads_profile_url,youtube_profile_url,profile_image_url,created_at,updated_at) VALUES($1,$2,$3,$4,$5,clock_timestamp(),clock_timestamp()) RETURNING id",&[&name,&x,&threads,&youtube,&image]).await.map_err(|e|sql_error(e,"FEATURED_PERSON_ALREADY_EXISTS"))?.get(0)
            };
            Ok((if old.is_some(){200}else{201},person_response(pid,db).await?))
        }.await;
        finish_transaction(result,db).await
    }.await;
    if let Some(uploaded) = &uploaded {
        if result.is_err() {
            cleanup_profile_image(Some(&uploaded.url), db).await;
        } else {
            cleanup_profile_image(previous_image.as_deref(), db).await;
        }
    }
    result
}
async fn create_post(pid: i64, body: &[u8], db: &Client) -> Outcome {
    let req = parse_body(body)?;
    let mut errors = Vec::new();
    let kind = source(&req, &mut errors)?;
    let title = optional(&req, "title")?;
    let url = optional(&req, "url")?;
    let published = optional(&req, "publishedAt")?;
    string_rules(
        &mut errors,
        "title",
        title.as_deref(),
        None,
        255,
        "제목은 255자 이하여야 합니다.",
        None,
    );
    string_rules(
        &mut errors,
        "url",
        url.as_deref(),
        Some("게시물 URL을 입력해주세요."),
        2000,
        "게시물 URL은 2000자 이하여야 합니다.",
        Some("올바른 게시물 URL을 입력해주세요."),
    );
    if let Some(published) = &published
        && (!instant_valid(published)
            || db
                .query_one("SELECT $1::text::timestamptz::text", &[&published])
                .await
                .is_err())
    {
        return Err(body_error());
    }
    finish(errors)?;
    let person = person_exists(pid, db).await?;
    let url = normalize_url(url.as_deref().ok_or_else(body_error)?, &kind, false)?;
    let label = match kind.as_str() {
        "X" => "X",
        "THREADS" => "Threads",
        "YOUTUBE" => "YouTube",
        _ => return Err(error("FEATURED_PERSON_INVALID_SOCIAL_URL")),
    };
    let title = stripped(title)
        .unwrap_or_else(|| format!("{} {label} 게시물", person["name"].as_str().unwrap_or("")));
    let record=db.query_one("INSERT INTO featured_person_posts(person_id,source_type,title,url,published_at,status,created_at,updated_at) VALUES($1,$2,$3,$4,$5::text::timestamptz,'APPROVED',clock_timestamp(),clock_timestamp()) RETURNING id",&[&pid,&kind,&title,&url,&published]).await.map_err(|e|sql_error(e,"FEATURED_PERSON_POST_ALREADY_EXISTS"))?;
    let post: i64 = record.get(0);
    let sql = format!("SELECT {POST_DTO}::text FROM featured_person_posts p WHERE id=$1");
    Ok((
        201,
        rows(db, &sql, &[&post]).await?.pop().ok_or_else(internal)?,
    ))
}

fn normalize_optional(value: Option<String>, kind: &str) -> Result<Option<String>> {
    stripped(value)
        .map(|v| normalize_url(&v, kind, true))
        .transpose()
}
fn decoded_path(value: &str) -> Result<String> {
    let mut output = Vec::new();
    let mut bytes = value.bytes();
    while let Some(byte) = bytes.next() {
        if byte == b'%' {
            let high = bytes
                .next()
                .and_then(|v| (v as char).to_digit(16))
                .ok_or_else(|| error("FEATURED_PERSON_INVALID_SOCIAL_URL"))?;
            let low = bytes
                .next()
                .and_then(|v| (v as char).to_digit(16))
                .ok_or_else(|| error("FEATURED_PERSON_INVALID_SOCIAL_URL"))?;
            output.push((high * 16 + low) as u8);
        } else {
            output.push(byte);
        }
    }
    String::from_utf8(output).map_err(|_| error("FEATURED_PERSON_INVALID_SOCIAL_URL"))
}
fn encode_path(path: &str) -> String {
    let mut output = String::new();
    for c in path.chars() {
        if c.is_ascii()
            && (c.is_ascii_control()
                || matches!(
                    c,
                    ' ' | '"' | '<' | '>' | '#' | '%' | '?' | '\\' | '^' | '`' | '{' | '|' | '}'
                ))
        {
            output.push_str(&format!("%{:02X}", c as u32));
        } else {
            output.push(c);
        }
    }
    output
}
fn normalize_url(value: &str, kind: &str, profile: bool) -> Result<String> {
    let invalid = || error("FEATURED_PERSON_INVALID_SOCIAL_URL");
    let value = strip(value);
    if value.chars().any(|c| {
        c.is_ascii_control()
            || matches!(
                c,
                ' ' | '\\' | '"' | '<' | '>' | '[' | ']' | '^' | '`' | '{' | '|' | '}'
            )
    }) {
        return Err(invalid());
    }
    let bytes = value.as_bytes();
    for (index, byte) in bytes.iter().enumerate() {
        if *byte == b'%'
            && (index + 2 >= bytes.len()
                || !bytes[index + 1].is_ascii_hexdigit()
                || !bytes[index + 2].is_ascii_hexdigit())
        {
            return Err(invalid());
        }
    }
    let parsed = reqwest::Url::parse(value).map_err(|_| invalid())?;
    if !parsed.scheme().eq_ignore_ascii_case("https") {
        return Err(invalid());
    }
    let host = parsed.host_str().ok_or_else(invalid)?.to_ascii_lowercase();
    let after = value.split_once("://").ok_or_else(invalid)?.1;
    let raw = after
        .find(['/', '?', '#'])
        .map(|index| &after[index..])
        .unwrap_or("");
    let path = raw.split(['?', '#']).next().unwrap_or("");
    let path = decoded_path(path)?;
    let stripped = path.strip_suffix('/').unwrap_or(&path);
    let segments: Vec<&str> = stripped
        .strip_prefix('/')
        .unwrap_or(stripped)
        .split('/')
        .collect();
    let nonempty = |s: &&str| !s.is_empty();
    let xhost = matches!(
        host.as_str(),
        "x.com" | "www.x.com" | "twitter.com" | "www.twitter.com"
    );
    let threadshost = matches!(
        host.as_str(),
        "threads.net" | "www.threads.net" | "threads.com" | "www.threads.com"
    );
    let youtubehost = matches!(host.as_str(), "youtube.com" | "www.youtube.com");
    let video_id = |s: &str| {
        s.len() == 11
            && s.bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
    };
    let mut watch_id = None;
    if let Some((_, query)) = raw.split_once('?') {
        let query = query.split('#').next().unwrap_or("");
        watch_id = query.split('&').find_map(|pair| {
            pair.strip_prefix("v=")
                .filter(|v| video_id(v))
                .map(str::to_owned)
        });
    }
    let valid = match (profile, kind) {
        (true, "X") => {
            xhost && segments.len() == 1 && segments.iter().all(nonempty) && path.starts_with('/')
        }
        (true, "THREADS") => {
            threadshost
                && segments.len() == 1
                && segments[0].starts_with('@')
                && segments[0].len() > 1
        }
        (true, "YOUTUBE") => {
            youtubehost
                && ((segments.len() == 1 && segments[0].starts_with('@') && segments[0].len() > 1)
                    || (segments.len() == 2
                        && matches!(segments[0], "channel" | "c" | "user")
                        && !segments[1].is_empty()))
        }
        (false, "X") => {
            xhost
                && segments.len() == 3
                && !segments[0].is_empty()
                && segments[1] == "status"
                && !segments[2].is_empty()
                && segments[2].bytes().all(|b| b.is_ascii_digit())
        }
        (false, "THREADS") => {
            threadshost
                && ((segments.len() == 3
                    && segments[0].starts_with('@')
                    && segments[0].len() > 1
                    && segments[1].eq_ignore_ascii_case("post")
                    && !segments[2].is_empty())
                    || (segments.len() == 2
                        && segments[0].eq_ignore_ascii_case("t")
                        && !segments[1].is_empty()))
        }
        (false, "YOUTUBE") => {
            (matches!(host.as_str(), "youtu.be" | "www.youtu.be")
                && segments.len() == 1
                && video_id(segments[0]))
                || (youtubehost
                    && ((segments.len() == 2
                        && matches!(segments[0], "embed" | "shorts" | "live")
                        && video_id(segments[1]))
                        || (path == "/watch" && watch_id.is_some())))
        }
        _ => false,
    };
    if !valid {
        return Err(invalid());
    }
    if !profile && kind == "YOUTUBE" && path == "/watch" {
        return Ok(format!(
            "https://www.youtube.com/watch?v={}",
            watch_id.ok_or_else(invalid)?
        ));
    }
    Ok(format!("https://{host}{}", encode_path(stripped)))
}
pub(crate) fn instant_valid(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.len() < 20
        || !date_valid(value.get(..10).unwrap_or(""))
        || !matches!(bytes[10], b'T' | b't')
        || bytes[13] != b':'
        || bytes[16] != b':'
    {
        return false;
    }
    let fields = [(11, 13, 23), (14, 16, 59), (17, 19, 60)];
    for (from, to, max) in fields {
        let Some(field) = value.get(from..to) else {
            return false;
        };
        if !field.bytes().all(|byte| byte.is_ascii_digit())
            || field.parse::<u32>().map_or(true, |number| number > max)
        {
            return false;
        }
    }
    let mut suffix = &value[19..];
    if let Some(fraction) = suffix.strip_prefix('.') {
        let count = fraction
            .bytes()
            .take_while(|byte| byte.is_ascii_digit())
            .count();
        if !(1..=9).contains(&count) {
            return false;
        }
        suffix = &fraction[count..];
    }
    if matches!(suffix, "Z" | "z") {
        return true;
    }
    let zone = suffix.as_bytes();
    if zone.len() != 6
        || !matches!(zone[0], b'+' | b'-')
        || zone[3] != b':'
        || !zone[1..3]
            .iter()
            .chain(zone[4..6].iter())
            .all(|byte| byte.is_ascii_digit())
    {
        return false;
    }
    let hours = suffix[1..3].parse::<u32>().unwrap_or(99);
    let minutes = suffix[4..6].parse::<u32>().unwrap_or(99);
    hours <= 18 && minutes <= 59 && (hours != 18 || minutes == 0)
}

pub(crate) fn date_valid(date: &str) -> bool {
    let bytes = date.as_bytes();
    if bytes.len() != 10
        || bytes[4] != b'-'
        || bytes[7] != b'-'
        || bytes
            .iter()
            .enumerate()
            .any(|(i, b)| i != 4 && i != 7 && !b.is_ascii_digit())
    {
        return false;
    }
    let y = date[..4].parse::<u32>().unwrap_or(0);
    let m = date[5..7].parse::<usize>().unwrap_or(0);
    let d = date[8..].parse::<u32>().unwrap_or(0);
    let days = [
        31,
        if y % 400 == 0 || y % 4 == 0 && y % 100 != 0 {
            29
        } else {
            28
        },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    y > 0 && (1..=12).contains(&m) && d > 0 && d <= days[m - 1]
}
async fn pending(pid: i64, db: &Client) -> Outcome {
    person_exists(pid, db).await?;
    let sql = format!(
        "SELECT {CANDIDATE_DTO}::text FROM featured_person_posts p WHERE person_id=$1 AND status='PENDING' ORDER BY created_at DESC,id DESC"
    );
    Ok((200, json!({"candidates":rows(db,&sql,&[&pid]).await?})))
}
async fn collect(pid: i64, raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let from = params
        .get("from")
        .ok_or_else(|| invalid("from", "필수 요청 파라미터입니다."))?;
    let to = params
        .get("to")
        .ok_or_else(|| invalid("to", "필수 요청 파라미터입니다."))?;
    for (field, value) in [("from", from), ("to", to)] {
        if !date_valid(value) {
            return Err(invalid(field, "타입이 올바르지 않습니다."));
        }
    }
    let valid: bool = db
        .query_one(
            "SELECT $1::text::date<=$2::text::date AND $2::text::date-$1::text::date<31",
            &[&from, &to],
        )
        .await
        .map_err(|_| internal())?
        .get(0);
    if !valid {
        return Err(error("FEATURED_PERSON_POST_COLLECTION_PERIOD_INVALID"));
    }
    let person = person_exists(pid, db).await?;
    let mut collected = Vec::new();
    let mut failure = None;
    if person["xProfileUrl"].as_str().is_some() || person["threadsProfileUrl"].as_str().is_some() {
        match service_social::social_profiles(
            person["xProfileUrl"].as_str(),
            person["threadsProfileUrl"].as_str(),
            from,
            to,
        )
        .await
        {
            Ok(items) => {
                for item in items {
                    let date = item["publishedDate"]
                        .as_str()
                        .filter(|s| !s.is_empty())
                        .map(|s| format!("{s}T00:00:00Z"));
                    collected.push((
                        item["sourceType"].as_str().unwrap_or("").to_owned(),
                        item["title"].as_str().unwrap_or("").to_owned(),
                        item["url"].as_str().unwrap_or("").to_owned(),
                        date,
                    ));
                }
            }
            Err(error) => failure = Some(error),
        }
    }
    if let Some(profile) = person["youtubeProfileUrl"].as_str() {
        match service_social::youtube_profile(profile, from, to, db).await {
            Ok(items) => {
                for item in items {
                    collected.push((
                        "YOUTUBE".into(),
                        item["title"].as_str().unwrap_or("").to_owned(),
                        item["url"].as_str().unwrap_or("").to_owned(),
                        item["publishedAt"]
                            .as_str()
                            .filter(|s| !s.is_empty())
                            .map(str::to_owned),
                    ));
                }
            }
            Err(error) => {
                if failure.is_none() {
                    failure = Some(error);
                }
            }
        }
    }
    if collected.is_empty() {
        if let Some(failure) = failure {
            return Err(failure);
        }
        return pending(pid, db).await;
    }
    db.batch_execute("BEGIN").await.map_err(|_| internal())?;
    let result=async{
        db.query_opt("SELECT id FROM featured_people WHERE id=$1 FOR UPDATE",&[&pid]).await.map_err(|_|internal())?.ok_or_else(||error("FEATURED_PERSON_NOT_FOUND"))?;
        for (kind,title,url,published) in collected{
            let Ok(url)=normalize_url(&url,&kind,false)else{continue};
            db.execute("INSERT INTO featured_person_posts(person_id,source_type,title,url,published_at,status,created_at,updated_at) VALUES($1,$2,$3,$4,$5::text::timestamptz,'PENDING',clock_timestamp(),clock_timestamp()) ON CONFLICT(person_id,url) DO NOTHING",&[&pid,&kind,&title,&url,&published]).await.map_err(|_|internal())?;
        }
        pending(pid,db).await
    }.await;
    finish_transaction(result, db).await
}
async fn transition(pid: Option<i64>, cid: i64, approve: bool, db: &Client) -> Result<Value> {
    // Each call is its own atomic statement. Bulk intentionally commits each
    // successful candidate independently and retains per-ID business failures.
    let sql = format!(
        "WITH changed AS (UPDATE featured_person_posts SET status=CASE WHEN $3::boolean THEN 'APPROVED' ELSE 'REJECTED' END,reviewed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=$1 AND ($2::bigint IS NULL OR person_id=$2) AND status='PENDING' RETURNING *) SELECT {POST_DTO}::text FROM changed p"
    );
    if let Some(post) = rows(db, &sql, &[&cid, &pid, &approve]).await?.pop() {
        return Ok(if approve { post } else { Value::Null });
    }
    let exists=db.query_opt("SELECT status FROM featured_person_posts WHERE id=$1 AND ($2::bigint IS NULL OR person_id=$2)",&[&cid,&pid]).await.map_err(|_|internal())?;
    if exists.is_none() {
        Err(error("FEATURED_PERSON_POST_CANDIDATE_NOT_FOUND"))
    } else {
        Err(error("FEATURED_PERSON_POST_CANDIDATE_NOT_PENDING"))
    }
}
fn bulk_ids(body: &[u8]) -> Result<Vec<i64>> {
    let req = parse_body(body)?;
    let Some(array) = req.get("candidateIds").filter(|v| !v.is_null()) else {
        return Err(invalid(
            "candidateIds",
            "처리할 게시물 후보를 선택해주세요.",
        ));
    };
    let array = array.as_array().ok_or_else(body_error)?;
    let mut ids = Vec::new();
    let mut seen = HashSet::new();
    for value in array {
        // The original compact constructor uses List.copyOf, rejecting null
        // entries during binding, before element constraint validation.
        let value = value.as_i64().ok_or_else(body_error)?;
        if seen.insert(value) {
            ids.push(value);
        }
    }
    let mut errors = Vec::new();
    if ids.is_empty() {
        add(
            &mut errors,
            "candidateIds",
            "처리할 게시물 후보를 선택해주세요.",
        );
    }
    if ids.len() > 100 {
        add(
            &mut errors,
            "candidateIds",
            "게시물 후보는 한 번에 최대 100개까지 처리할 수 있습니다.",
        );
    }
    for (index, value) in ids.iter().enumerate() {
        if *value <= 0 {
            add(
                &mut errors,
                &format!("candidateIds[{index}]"),
                "0보다 커야 합니다",
            );
        }
    }
    finish(errors)?;
    Ok(ids)
}
async fn bulk(pid: Option<i64>, approve: bool, body: &[u8], db: &Client) -> Outcome {
    let ids = bulk_ids(body)?;
    let mut succeeded = Vec::new();
    let mut failed = Vec::new();
    for cid in ids {
        match transition(pid, cid, approve, db).await {
            Ok(post) => succeeded.push(json!({"candidateId":cid,"post":post})),
            Err(problem) => {
                if problem.status == 500 {
                    failed.push(json!({"candidateId":cid,"errorCode":"INTERNAL_ERROR","message":if approve{"게시물 후보를 승인하지 못했습니다."}else{"게시물 후보를 거절하지 못했습니다."}}));
                } else {
                    failed.push(json!({"candidateId":cid,"errorCode":problem.body["code"],"message":problem.body["message"]}));
                }
            }
        }
    }
    Ok((200, json!({"succeeded":succeeded,"failed":failed})))
}
async fn inbox(raw: &str, db: &Client) -> Outcome {
    let params = query(raw)?;
    let parse = |field: &str, default: i32| -> Result<i32> {
        match params.get(field).filter(|v| !v.is_empty()) {
            None => Ok(default),
            Some(value) => crate::java_binding::integer(value)
                .and_then(|number| i32::try_from(number).ok())
                .ok_or_else(|| invalid(field, "타입이 올바르지 않습니다.")),
        }
    };
    let page = parse("page", 1)?;
    let size = parse("size", 20)?;
    let mut errors = Vec::new();
    if page < 1 {
        add(&mut errors, "page", "1 이상이어야 합니다");
    }
    if size < 1 {
        add(&mut errors, "size", "1 이상이어야 합니다");
    }
    if size > 100 {
        add(&mut errors, "size", "100 이하여야 합니다");
    }
    let pid = params
        .get("personId")
        .filter(|v| !v.is_empty())
        .map(|v| id(v, "personId"))
        .transpose()?;
    let kind = params.get("sourceType").filter(|v| !v.is_empty());
    if kind.is_some_and(|v| {
        !matches!(
            v.as_str(),
            "YOUTUBE" | "THREADS" | "X" | "INTERNAL_NEWS" | "OTHER"
        )
    }) {
        return Err(invalid("sourceType", "지원하지 않는 값입니다."));
    }
    finish(errors)?;
    let total:i64=db.query_one("SELECT count(*) FROM featured_person_posts WHERE status='PENDING' AND ($1::bigint IS NULL OR person_id=$1) AND ($2::text IS NULL OR source_type=$2)",&[&pid,&kind]).await.map_err(|_|internal())?.get(0);
    let offset = (i64::from(page) - 1) * i64::from(size);
    let limit = i64::from(size);
    let sql = "SELECT json_build_object('id',p.id,'personId',person.id,'personName',person.name,'personProfileImageUrl',person.profile_image_url,'sourceType',p.source_type,'title',p.title,'url',p.url,'publishedAt',p.published_at,'status',p.status,'createdAt',p.created_at)::text FROM featured_person_posts p JOIN featured_people person ON person.id=p.person_id WHERE p.status='PENDING' AND ($1::bigint IS NULL OR person_id=$1) AND ($2::text IS NULL OR source_type=$2) ORDER BY p.created_at DESC,p.id DESC LIMIT $3 OFFSET $4";
    Ok((
        200,
        json!({"candidates":rows(db,sql,&[&pid,&kind,&limit,&offset]).await?,"page":page,"size":size,"totalElements":total,"totalPages":(total+i64::from(size)-1)/i64::from(size)}),
    ))
}
