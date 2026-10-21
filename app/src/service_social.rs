//! YouTube and cited Threads/X search transports. Configuration is explicit;
//! no provider call is replaced by a successful synthetic result.
use crate::api::{ApiFault, fault};
use crate::{service_admin_content, service_media};
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashSet};
use tokio_postgres::Client;
type Result<T> = std::result::Result<T, ApiFault>;
fn fail(code: &str) -> ApiFault {
    let (status, message) = match code {
        "YOUTUBE_API_NOT_CONFIGURED" => (503, "YouTube API 키가 설정되지 않았습니다."),
        "YOUTUBE_API_REQUEST_FAILED" => (502, "YouTube API 요청에 실패했습니다."),
        _ => (502, "Threads·X 게시물 검색에 실패했습니다."),
    };
    fault(status, code, message)
}
fn java_space(c: char) -> bool {
    matches!(c,'\u{0009}'..='\u{000d}'|'\u{001c}'..='\u{0020}'|'\u{1680}'|'\u{2000}'..='\u{2006}'|'\u{2008}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{205f}'|'\u{3000}')
}
fn env(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .filter(|s| !s.trim_matches(java_space).is_empty())
}
async fn youtube(path: &str, params: &[(&str, &str)]) -> Result<Value> {
    let code = "YOUTUBE_API_REQUEST_FAILED";
    let key = env("YOUTUBE_API_KEY").ok_or_else(|| fail("YOUTUBE_API_NOT_CONFIGURED"))?;
    let base =
        env("YOUTUBE_BASE_URL").unwrap_or_else(|| "https://www.googleapis.com/youtube/v3".into());
    let mut url =
        service_media::endpoint(&format!("{}/{}", base.trim_end_matches('/'), path), code)
            .map_err(|_| fail(code))?;
    url.query_pairs_mut()
        .extend_pairs(params.iter().copied())
        .append_pair("key", &key);
    let client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(3))
        .timeout(std::time::Duration::from_secs(10))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| fail(code))?;
    let response = client.get(url).send().await.map_err(|_| fail(code))?;
    let root: Value = serde_json::from_slice(
        &service_media::bounded(response, 2_000_000, code)
            .await
            .map_err(|_| fail(code))?,
    )
    .map_err(|_| fail(code))?;
    if root.get("error").is_some_and(|e| !e.is_null()) || !root["items"].is_array() {
        return Err(fail(code));
    }
    Ok(root)
}
fn videos(root: &Value) -> Vec<Value> {
    root["items"].as_array().into_iter().flatten().filter_map(|item|{
        let id=item["id"]["videoId"].as_str().filter(|s|!s.trim_matches(java_space).is_empty())?;
        let snippet=&item["snippet"];let title=snippet["title"].as_str().filter(|s|!s.trim_matches(java_space).is_empty())?;
        let thumbnail=["high","medium","default"].into_iter().find_map(|quality|snippet["thumbnails"][quality]["url"].as_str().filter(|s|!s.trim_matches(java_space).is_empty())).unwrap_or("");
        Some(json!({"title":title,"url":format!("https://www.youtube.com/watch?v={id}"),"channelTitle":snippet["channelTitle"].as_str().unwrap_or(""),"publishedAt":snippet["publishedAt"].as_str().unwrap_or(""),"thumbnailUrl":thumbnail}))
    }).collect()
}
pub(crate) async fn youtube_search(keyword: &str) -> Result<Vec<Value>> {
    if keyword.trim_matches(java_space).is_empty() {
        return Ok(Vec::new());
    }
    let root = youtube(
        "search",
        &[
            ("part", "snippet"),
            ("q", keyword.trim_matches(java_space)),
            ("type", "video"),
            ("order", "date"),
            ("maxResults", "10"),
            ("safeSearch", "moderate"),
        ],
    )
    .await?;
    Ok(videos(&root))
}
pub(crate) async fn youtube_profile(
    profile: &str,
    from: &str,
    to: &str,
    db: &Client,
) -> Result<Vec<Value>> {
    if profile.trim_matches(java_space).is_empty() {
        return Ok(Vec::new());
    }
    if env("YOUTUBE_API_KEY").is_none() {
        return Err(fail("YOUTUBE_API_NOT_CONFIGURED"));
    }
    let url = reqwest::Url::parse(profile).map_err(|_| fail("YOUTUBE_API_REQUEST_FAILED"))?;
    let decoded_path =
        crate::api::path_text(url.path()).ok_or_else(|| fail("YOUTUBE_API_REQUEST_FAILED"))?;
    let segments: Vec<&str> = decoded_path
        .trim_start_matches('/')
        .trim_end_matches('/')
        .split('/')
        .collect();
    let channel = if segments.len() == 2 && segments[0] == "channel" {
        Some(segments[1].to_owned())
    } else {
        let filter = if segments.len() == 1 && segments[0].starts_with('@') {
            Some(("forHandle", &segments[0][1..]))
        } else if segments.len() == 2 && segments[0] == "user" {
            Some(("forUsername", segments[1]))
        } else {
            None
        };
        if let Some((key, value)) = filter {
            let root = youtube("channels", &[("part", "id"), (key, value)]).await?;
            root["items"]
                .as_array()
                .and_then(|items| items.first())
                .and_then(|item| item["id"].as_str())
                .filter(|s| !s.trim_matches(java_space).is_empty())
                .map(str::to_owned)
        } else {
            None
        }
    };
    let Some(channel) = channel else {
        return Ok(Vec::new());
    };
    let bounds=db.query_one("SELECT to_char($1::text::date::timestamp AT TIME ZONE 'Asia/Seoul' AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),to_char(($2::text::date+1)::timestamp AT TIME ZONE 'Asia/Seoul' AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')",&[&from,&to]).await.map_err(|_|fail("YOUTUBE_API_REQUEST_FAILED"))?;
    let after: String = bounds.get(0);
    let before: String = bounds.get(1);
    let mut result = Vec::new();
    let mut page = String::new();
    for _ in 0..10 {
        let mut params = vec![
            ("part", "snippet"),
            ("channelId", channel.as_str()),
            ("type", "video"),
            ("order", "date"),
            ("publishedAfter", after.as_str()),
            ("publishedBefore", before.as_str()),
            ("maxResults", "50"),
            ("safeSearch", "moderate"),
        ];
        if !page.is_empty() {
            params.push(("pageToken", &page));
        }
        let root = youtube("search", &params).await?;
        for video in videos(&root) {
            let time = video["publishedAt"].as_str().unwrap_or("");
            if !service_admin_content::instant_valid(time) {
                continue;
            }
            let inside=db.query_one("SELECT $1::text::timestamptz>=$2::text::timestamptz AND $1::text::timestamptz<$3::text::timestamptz",&[&time,&after,&before]).await.map(|row|row.get::<_,bool>(0)).unwrap_or(false);
            if inside {
                result.push(video);
            }
        }
        page = root["nextPageToken"].as_str().unwrap_or("").to_owned();
        if page.is_empty() {
            break;
        }
    }
    Ok(result)
}
fn social_candidate(title: &str, raw: &str) -> Option<Value> {
    if raw.chars().any(|c| {
        c.is_ascii_whitespace()
            || c.is_ascii_control()
            || matches!(
                c,
                '\\' | '"' | '<' | '>' | '[' | ']' | '^' | '`' | '{' | '|' | '}'
            )
    }) {
        return None;
    }
    for (i, b) in raw.bytes().enumerate() {
        if b == b'%'
            && (i + 2 >= raw.len()
                || !raw.as_bytes()[i + 1].is_ascii_hexdigit()
                || !raw.as_bytes()[i + 2].is_ascii_hexdigit())
        {
            return None;
        }
    }
    let parsed = reqwest::Url::parse(raw).ok()?;
    if !matches!(parsed.scheme(), "http" | "https") {
        return None;
    }
    let host = parsed.host_str()?.to_ascii_lowercase();
    // Match Java URI's raw path, before browser URL parsing can normalize dot
    // segments or backslashes into an otherwise admissible account post.
    let rest = raw.split_once("://")?.1;
    let start = rest.find(['/', '?', '#']).unwrap_or(rest.len());
    let path = rest[start..].split(['?', '#']).next().unwrap_or("");
    let path = path.strip_suffix('/').unwrap_or(path);
    let segments: Vec<&str> = path.strip_prefix('/')?.split('/').collect();
    let source = if matches!(
        host.as_str(),
        "x.com" | "www.x.com" | "twitter.com" | "www.twitter.com"
    ) && segments.len() == 3
        && !segments[0].is_empty()
        && segments[1].eq_ignore_ascii_case("status")
        && !segments[2].is_empty()
        && segments[2].bytes().all(|b| b.is_ascii_digit())
    {
        "X"
    } else if matches!(
        host.as_str(),
        "threads.net" | "www.threads.net" | "threads.com" | "www.threads.com"
    ) && ((segments.len() == 3
        && segments[0].starts_with('@')
        && segments[0].len() > 1
        && segments[1].eq_ignore_ascii_case("post")
        && !segments[2].is_empty())
        || (segments.len() == 2
            && segments[0].eq_ignore_ascii_case("t")
            && !segments[1].is_empty()))
    {
        "THREADS"
    } else {
        return None;
    };
    let fallback = if source == "X" {
        "X 게시물"
    } else {
        "Threads 게시물"
    };
    let raw_title = if title.trim_matches(java_space).is_empty() {
        fallback
    } else {
        title.trim_matches(java_space)
    };
    let mut title = String::new();
    let mut length = 0;
    for c in raw_title
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
    {
        if length + c.len_utf16() > 255 {
            break;
        }
        length += c.len_utf16();
        title.push(c);
    }
    Some(
        json!({"sourceType":source,"title":title,"url":format!("https://{host}{}",path.replace('%',"%25")),"publishedDate":""}),
    )
}
fn social_results(root: &Value) -> Result<Vec<Value>> {
    let code = "AI_SOCIAL_SEARCH_FAILED";
    let output = root["output"].as_array().ok_or_else(|| fail(code))?;
    let mut sources = BTreeMap::new();
    for item in output {
        if item["type"] == "web_search_call"
            && let Some(found) = item["action"]["sources"].as_array()
        {
            for source in found {
                if let Some(candidate) = social_candidate(
                    source["title"].as_str().unwrap_or(""),
                    source["url"].as_str().unwrap_or(""),
                ) {
                    sources
                        .entry(candidate["url"].as_str().unwrap_or("").to_owned())
                        .or_insert(candidate);
                }
            }
        }
    }
    let text = service_media::output_json(root, code).map_err(|_| fail(code))?;
    let items = text["items"].as_array().ok_or_else(|| fail(code))?;
    let mut used = HashSet::new();
    let mut result = Vec::new();
    for item in items {
        if let Some(mut candidate) = social_candidate(
            item["title"].as_str().unwrap_or(""),
            item["url"].as_str().unwrap_or(""),
        ) {
            let url = candidate["url"].as_str().unwrap_or("").to_owned();
            if !sources.contains_key(&url) || !used.insert(url) {
                continue;
            }
            let date = item["publishedDate"]
                .as_str()
                .unwrap_or("")
                .trim_matches(java_space);
            if service_admin_content::date_valid(date) {
                candidate["publishedDate"] = json!(date);
            }
            result.push(candidate);
        }
    }
    Ok(result)
}
async fn social_execute(input: &str) -> Result<Vec<Value>> {
    let code = "AI_SOCIAL_SEARCH_FAILED";
    let model = env("AI_OPENAI_SOCIAL_SEARCH_MODEL")
        .or_else(|| env("OPENAI_SOCIAL_SEARCH_MODEL"))
        .unwrap_or_else(|| "gpt-5-mini".into());
    let schema = json!({"type":"object","additionalProperties":false,"required":["items"],"properties":{"items":{"type":"array","maxItems":10,"items":{"type":"object","additionalProperties":false,"required":["title","url","publishedDate"],"properties":{"title":{"type":"string"},"url":{"type":"string"},"publishedDate":{"type":"string"}}}}}});
    let request = json!({"model":model,"tools":[{"type":"web_search","filters":{"allowed_domains":["threads.net","threads.com","x.com","twitter.com"]}}],"tool_choice":"required","include":["web_search_call.action.sources"],"input":input,"text":{"format":{"type":"json_schema","name":"social_post_search","strict":true,"schema":schema}}});
    let root = service_media::openai("responses", &request, code, 2_000_000)
        .await
        .map_err(|_| fail(code))?;
    social_results(&root)
}
pub(crate) async fn social_search(keyword: &str) -> Result<Vec<Value>> {
    if keyword.trim_matches(java_space).is_empty() {
        return Ok(Vec::new());
    }
    let input = format!(
        "Find up to 10 public Threads and X posts directly related to this search target: {}. The target may be a person, company, topic, or include official profile URLs. Search both platforms and prioritize posts from the supplied profile URLs when present. Do not return profiles, search pages, or home pages. For each post, return publishedDate as YYYY-MM-DD only when the date is clearly confirmed; otherwise return an empty string. Never guess a date.",
        keyword.trim_matches(java_space)
    );
    social_execute(&input).await
}
pub(crate) async fn social_profiles(
    x: Option<&str>,
    threads: Option<&str>,
    from: &str,
    to: &str,
) -> Result<Vec<Value>> {
    if x.is_none() && threads.is_none() {
        return Ok(Vec::new());
    }
    let target = [x, threads]
        .into_iter()
        .flatten()
        .collect::<Vec<_>>()
        .join(" ");
    let input = format!(
        "Find up to 10 public posts authored only by these exact official profiles: {target}. Return a post only when the author handle in its URL exactly matches one of the supplied profiles. Do not return mentions, reposts from other accounts, profiles, search pages, or home pages. For each post, return publishedDate as YYYY-MM-DD only when clearly confirmed. Search only posts published from {from} through {to} inclusive. Never guess a date, and exclude posts whose date cannot be confirmed."
    );
    let candidates = social_execute(&input).await?;
    Ok(candidates
        .into_iter()
        .filter(|post| {
            let Some(date) = post["publishedDate"]
                .as_str()
                .filter(|date| !date.is_empty() && *date >= from && *date <= to)
            else {
                return false;
            };
            let _ = date;
            let profile = if post["sourceType"] == "X" {
                x
            } else {
                threads
            };
            let Some(expected) = profile
                .and_then(|raw| reqwest::Url::parse(raw).ok())
                .and_then(|url| {
                    url.path_segments()
                        .and_then(|mut p| p.next())
                        .map(|s| s.trim_start_matches('@').to_owned())
                })
            else {
                return false;
            };
            let Some(url) = post["url"]
                .as_str()
                .and_then(|raw| reqwest::Url::parse(raw).ok())
            else {
                return false;
            };
            let parts: Vec<&str> = url.path().trim_start_matches('/').split('/').collect();
            parts.len() == 3
                && parts[0]
                    .trim_start_matches('@')
                    .eq_ignore_ascii_case(&expected)
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn social_search_requires_real_post_source_and_normalizes_dates() {
        let payload = json!({"items":[{"title":"First post","url":"https://x.com/official/status/123?utm_source=search","publishedDate":"2026-02-30"},{"title":"Uncited","url":"https://x.com/official/status/456","publishedDate":"2026-02-01"},{"title":"Profile","url":"https://x.com/official","publishedDate":"2026-02-01"},{"title":"Duplicate","url":"http://x.com/official/status/123/","publishedDate":"2026-02-01"}]});
        let root = json!({"output":[{"type":"web_search_call","status":"completed","action":{"sources":[{"title":"Source","url":"https://x.com/official/status/123"},{"title":"Profile","url":"https://x.com/official"}]}},{"type":"message","content":[{"type":"output_text","text":payload.to_string()}]}]});
        let result = social_results(&root).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["url"], "https://x.com/official/status/123");
        assert_eq!(result[0]["publishedDate"], "");
        for url in [
            "https://x.com.evil.example/official/status/123",
            "https://x.com//official/status/123",
            "https://x.com/official/status/123//",
            "https://x.com/official/../official/status/123",
            "https://threads.net/@official",
            "https://x.com/official/status/not-a-number",
        ] {
            assert!(social_candidate("title", url).is_none());
        }
    }
    #[test]
    fn youtube_video_filter_and_thumbnail_precedence() {
        let root = json!({"items":[{"id":{"videoId":"abcdefghijk"},"snippet":{"title":"Official video","channelTitle":"Channel","publishedAt":"2026-02-01T00:00:00Z","thumbnails":{"default":{"url":"default"},"medium":{"url":"medium"},"high":{"url":"high"}}}},{"id":{"videoId":""},"snippet":{"title":"Missing ID"}},{"id":{"videoId":"abcdefghijl"},"snippet":{"title":" "}}]});
        let result = videos(&root);
        assert_eq!(result.len(), 1);
        assert_eq!(
            result[0]["url"],
            "https://www.youtube.com/watch?v=abcdefghijk"
        );
        assert_eq!(result[0]["thumbnailUrl"], "high");
        assert_eq!(result[0]["publishedAt"], "2026-02-01T00:00:00Z");
    }
}
