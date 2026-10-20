use hyper::HeaderMap;
use subtle::ConstantTimeEq;
use uuid::Uuid;

pub const HEADER: &str = "X-XSRF-TOKEN";
pub const COOKIE: &str = "XSRF-TOKEN";

fn valid_format(value: &str) -> bool {
    value.len() == 36
        && Uuid::parse_str(value).is_ok_and(|id| id.get_version_num() == 4)
        && value.bytes().all(|b| b.is_ascii_hexdigit() || b == b'-')
}

fn cookie_token(headers: &HeaderMap) -> Option<&str> {
    let mut token = None;
    for header in headers.get_all(hyper::header::COOKIE) {
        let value = header.to_str().ok()?;
        for pair in value.split(';') {
            let Some((name, value)) = pair.trim().split_once('=') else {
                continue;
            };
            if name == COOKIE {
                if token.is_some() || !valid_format(value) {
                    return None;
                }
                token = Some(value);
            }
        }
    }
    token
}

pub fn issue(headers: &HeaderMap) -> String {
    cookie_token(headers)
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string())
}

pub fn valid(headers: &HeaderMap) -> bool {
    let Some(cookie) = cookie_token(headers) else {
        return false;
    };
    let mut values = headers.get_all(HEADER).iter();
    let Some(header) = values.next().and_then(|value| value.to_str().ok()) else {
        return false;
    };
    values.next().is_none()
        && valid_format(header)
        && bool::from(cookie.as_bytes().ct_eq(header.as_bytes()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use hyper::header::{COOKIE as COOKIE_HEADER, HeaderValue};

    #[test]
    fn requires_matching_cookie_and_header() {
        let token = issue(&HeaderMap::new());
        let mut headers = HeaderMap::new();
        headers.insert(HEADER, HeaderValue::from_str(&token).unwrap());
        assert!(!valid(&headers));
        headers.insert(
            COOKIE_HEADER,
            HeaderValue::from_str(&format!("{COOKIE}={token}")).unwrap(),
        );
        assert!(valid(&headers));
        assert_eq!(issue(&headers), token);
        headers.insert(
            HEADER,
            HeaderValue::from_str(&Uuid::new_v4().to_string()).unwrap(),
        );
        assert!(!valid(&headers));
    }

    #[test]
    fn rejects_duplicate_cookie_and_header() {
        let token = issue(&HeaderMap::new());
        let mut headers = HeaderMap::new();
        headers.insert(HEADER, HeaderValue::from_str(&token).unwrap());
        headers.insert(
            COOKIE_HEADER,
            HeaderValue::from_str(&format!("{COOKIE}={token}; {COOKIE}={token}")).unwrap(),
        );
        assert!(!valid(&headers));
        headers.insert(
            COOKIE_HEADER,
            HeaderValue::from_str(&format!("{COOKIE}={token}")).unwrap(),
        );
        headers.append(HEADER, HeaderValue::from_str(&token).unwrap());
        assert!(!valid(&headers));
    }

    #[test]
    fn fresh_clients_receive_random_tokens() {
        let first = issue(&HeaderMap::new());
        let second = issue(&HeaderMap::new());
        assert!(valid_format(&first));
        assert_ne!(first, second);
    }
}
