use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
pub struct FieldError {
    pub field: &'static str,
    pub reason: &'static str,
}

#[derive(Debug, Serialize)]
pub struct ApiError {
    pub code: &'static str,
    pub message: &'static str,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub errors: Vec<FieldError>,
}

impl ApiError {
    pub fn new(code: &'static str, message: &'static str) -> Self {
        Self {
            code,
            message,
            errors: Vec::new(),
        }
    }

    fn invalid(errors: Vec<FieldError>) -> Self {
        Self {
            code: "INVALID_REQUEST",
            message: "요청값이 올바르지 않습니다.",
            errors,
        }
    }

    pub fn unreadable_body() -> Self {
        Self::invalid(vec![FieldError {
            field: "requestBody",
            reason: "요청 본문을 읽을 수 없습니다.",
        }])
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateRequest {
    content: Option<String>,
    page_path: Option<String>,
}

pub struct Feedback {
    pub content: String,
    pub page_path: String,
}

// Java 21 Character.isWhitespace used by String.isBlank/strip.
// Rust char::is_whitespace additionally includes nonbreaking spaces and U+0085.
fn java_whitespace(c: char) -> bool {
    matches!(
        c,
        '\u{0009}'..='\u{000d}'
            | '\u{001c}'..='\u{0020}'
            | '\u{1680}'
            | '\u{2000}'..='\u{2006}'
            | '\u{2008}'..='\u{200a}'
            | '\u{2028}'..='\u{2029}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

fn validate_field(
    value: Option<&str>,
    field: &'static str,
    limit: usize,
    blank_reason: &'static str,
    long_reason: &'static str,
    errors: &mut Vec<FieldError>,
) {
    if value.is_none_or(|s| s.chars().all(java_whitespace)) {
        errors.push(FieldError {
            field,
            reason: blank_reason,
        });
    }
    if value.is_some_and(|s| s.encode_utf16().count() > limit) {
        errors.push(FieldError {
            field,
            reason: long_reason,
        });
    }
}

pub fn parse(body: &[u8]) -> Result<Feedback, ApiError> {
    let request: CreateRequest =
        serde_json::from_slice(body).map_err(|_| ApiError::unreadable_body())?;
    let mut errors = Vec::new();
    validate_field(
        request.content.as_deref(),
        "content",
        1000,
        "피드백 내용을 입력해주세요.",
        "피드백은 1000자 이하여야 합니다.",
        &mut errors,
    );
    validate_field(
        request.page_path.as_deref(),
        "pagePath",
        2048,
        "작성 화면 경로가 필요합니다.",
        "작성 화면 경로는 2048자 이하여야 합니다.",
        &mut errors,
    );
    if !errors.is_empty() {
        return Err(ApiError::invalid(errors));
    }
    // Validation precedes normalization, as in @Valid -> FeedbackService.create.
    Ok(Feedback {
        content: request
            .content
            .unwrap_or_default()
            .trim_matches(java_whitespace)
            .to_owned(),
        page_path: request
            .page_path
            .unwrap_or_default()
            .trim_matches(java_whitespace)
            .to_owned(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn validates_original_utf16_length_before_stripping() {
        for value in [
            "가".repeat(1001),
            "😀".repeat(501),
            " ".to_owned() + &"a".repeat(1000),
        ] {
            let input = serde_json::to_vec(&json!({"content":value,"pagePath":"/"})).unwrap();
            assert!(parse(&input).is_err());
        }
        let input =
            serde_json::to_vec(&json!({"content":"😀".repeat(500),"pagePath":"/"})).unwrap();
        assert!(parse(&input).is_ok());
    }

    #[test]
    fn preserves_nonbreaking_spaces_and_internal_whitespace() {
        let input = serde_json::to_vec(&json!({
            "content":"\u{2003}\u{a0}a  b\nc\u{a0}\u{2003}",
            "pagePath":" relative "
        }))
        .unwrap();
        let parsed = parse(&input).unwrap();
        assert_eq!(parsed.content, "\u{a0}a  b\nc\u{a0}");
        assert_eq!(parsed.page_path, "relative");
        for c in ['\u{a0}', '\u{2007}', '\u{202f}', '\u{85}'] {
            assert!(!java_whitespace(c));
        }
    }

    #[test]
    fn reports_both_invalid_fields_without_echoing_input() {
        let error = match parse(br#"{"content":null,"pagePath":" "}"#) {
            Ok(_) => panic!("invalid input accepted"),
            Err(error) => error,
        };
        assert_eq!(error.errors.len(), 2);
        let serialized = serde_json::to_value(error).unwrap();
        assert!(serialized["errors"][0].get("rejectedValue").is_none());
    }

    #[test]
    fn unreadable_input_is_not_silently_coerced() {
        for input in [
            b"".as_slice(),
            b"{",
            b"null",
            br#"{"content":1,"pagePath":"/"}"#,
        ] {
            let error = match parse(input) {
                Ok(_) => panic!("invalid JSON/type accepted"),
                Err(error) => error,
            };
            assert_eq!(error.errors[0].field, "requestBody");
        }
    }
}
