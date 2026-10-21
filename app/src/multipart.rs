#![forbid(unsafe_code)]
//! Bounded multipart decoding for the original admin news request/image parts.
use crate::api::{ApiFault, fault};

fn invalid() -> ApiFault {
    fault(400, "INVALID_REQUEST", "요청값이 올바르지 않습니다.")
}
fn find(bytes: &[u8], needle: &[u8]) -> Option<usize> {
    bytes.windows(needle.len()).position(|v| v == needle)
}
pub fn news(
    content_type: &str,
    body: &[u8],
) -> Result<(Vec<u8>, Option<crate::service_admin_news::UploadedImage>), ApiFault> {
    if !content_type
        .split(';')
        .next()
        .is_some_and(|v| v.trim().eq_ignore_ascii_case("multipart/form-data"))
    {
        return Err(fault(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "JSON 요청이 필요합니다.",
        ));
    }
    let boundary = content_type
        .split(';')
        .skip(1)
        .filter_map(|v| v.trim().split_once('='))
        .find(|(key, _)| key.eq_ignore_ascii_case("boundary"))
        .map(|(_, v)| v.trim().trim_matches('"'))
        .ok_or_else(invalid)?;
    if boundary.is_empty()
        || boundary.len() > 70
        || !boundary.bytes().all(|b| b.is_ascii_graphic() && b != b'"')
    {
        return Err(invalid());
    }
    let delimiter = format!("--{boundary}").into_bytes();
    let next = [b"\r\n".as_slice(), &delimiter].concat();
    if !body.starts_with(&delimiter) {
        return Err(invalid());
    }
    let mut offset = delimiter.len();
    let mut request = None;
    let mut image = None;
    let mut image_seen = false;
    let mut parts = 0;
    loop {
        if body.get(offset..offset + 2) == Some(b"--") {
            break;
        }
        if body.get(offset..offset + 2) != Some(b"\r\n") {
            return Err(invalid());
        }
        offset += 2;
        let headers_end = find(&body[offset..], b"\r\n\r\n")
            .filter(|n| *n <= 8192)
            .ok_or_else(invalid)?;
        let headers =
            std::str::from_utf8(&body[offset..offset + headers_end]).map_err(|_| invalid())?;
        if headers.contains('\0') {
            return Err(invalid());
        }
        offset += headers_end + 4;
        let length = body[offset..]
            .windows(next.len())
            .enumerate()
            .find(|(at, value)| {
                *value == next
                    && matches!(
                        body.get(offset + at + next.len()..offset + at + next.len() + 2),
                        Some(b"\r\n" | b"--")
                    )
            })
            .map(|(at, _)| at)
            .ok_or_else(invalid)?;
        let data = &body[offset..offset + length];
        offset += length + next.len();
        parts += 1;
        if parts > 32 {
            return Err(invalid());
        }
        let disposition = headers
            .split("\r\n")
            .filter_map(|line| line.split_once(':'))
            .find(|(k, _)| k.eq_ignore_ascii_case("content-disposition"))
            .map(|(_, v)| v.trim())
            .ok_or_else(invalid)?;
        let name = disposition
            .split(';')
            .skip(1)
            .filter_map(|v| v.trim().split_once('='))
            .find(|(k, _)| k.eq_ignore_ascii_case("name"))
            .map(|(_, v)| v.trim().trim_matches('"'))
            .ok_or_else(invalid)?;
        match name {
            "request" if request.is_none() => {
                let media = headers
                    .split("\r\n")
                    .filter_map(|line| line.split_once(':'))
                    .find(|(k, _)| k.eq_ignore_ascii_case("content-type"))
                    .map(|(_, v)| v.trim().split(';').next().unwrap_or(""))
                    .unwrap_or("");
                if !media.eq_ignore_ascii_case("application/json")
                    && !media.to_ascii_lowercase().ends_with("+json")
                {
                    return Err(fault(
                        415,
                        "UNSUPPORTED_MEDIA_TYPE",
                        "JSON 요청이 필요합니다.",
                    ));
                }
                if data.len() > 64 * 1024 {
                    return Err(invalid());
                }
                request = Some(data.to_vec());
            }
            "image" if !image_seen => {
                image_seen = true;
                if data.len() > 5 * 1024 * 1024 {
                    return Err(fault(
                        400,
                        "INVALID_IMAGE_FILE",
                        "지원하지 않는 이미지 파일입니다.",
                    ));
                }
                if !data.is_empty() {
                    let media = headers
                        .split("\r\n")
                        .filter_map(|line| line.split_once(':'))
                        .find(|(key, _)| key.eq_ignore_ascii_case("content-type"))
                        .map(|(_, value)| {
                            value
                                .trim()
                                .split(';')
                                .next()
                                .unwrap_or("")
                                .to_ascii_lowercase()
                        })
                        .unwrap_or_default();
                    image = Some(crate::service_admin_news::UploadedImage {
                        bytes: data.to_vec(),
                        content_type: media,
                    });
                }
            }
            _ => {}
        }
    }
    Ok((request.ok_or_else(invalid)?, image))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn preserves_json_and_binary_image() {
        let mut body=b"--bound\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n{\"title\":\"x\"}\r\n--bound\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.png\"\r\nContent-Type: image/png\r\n\r\n".to_vec();
        body.extend_from_slice(&[0, 255, 254, 1]);
        body.extend_from_slice(b"\r\n--bound--\r\n");
        let (request, image) = news("multipart/form-data; boundary=bound", &body).unwrap();
        assert_eq!(request, b"{\"title\":\"x\"}");
        let image = image.unwrap();
        assert_eq!(image.bytes, [0, 255, 254, 1]);
        assert_eq!(image.content_type, "image/png");
    }
    #[test]
    fn rejects_missing_terminal_boundary() {
        assert!(news("multipart/form-data; boundary=bound",b"--bound\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n{}").is_err());
    }
    #[test]
    fn rejects_oversized_request_part() {
        let body=[b"--b\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n".as_slice(),&vec![b'x';65537],b"\r\n--b--"].concat();
        assert!(news("multipart/form-data; boundary=b", &body).is_err());
    }
}
