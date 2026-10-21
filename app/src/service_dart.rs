//! OpenDART earnings notices/results. ZIP data is read in memory with explicit
//! compressed/decompressed bounds; nothing is extracted to the filesystem.
//! Per-document skips match the Java provider and remain visible in statistics.
use crate::api::{ApiFault, fault, internal};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    io::{Cursor, Read},
    time::Duration,
};
use tokio_postgres::Client;
type Result<T> = std::result::Result<T, ApiFault>;
const MAX_ZIP: usize = 16 * 1024 * 1024;
const MAX_XML: u64 = 32 * 1024 * 1024;
const VIEWER: &str = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=";
fn failed() -> ApiFault {
    fault(
        502,
        "DART_REQUEST_FAILED",
        "OpenDART 공시 조회에 실패했습니다.",
    )
}
fn setting(name: &str, default: &str) -> String {
    std::env::var(name).unwrap_or_else(|_| default.into())
}
fn endpoint(path: &str) -> Result<reqwest::Url> {
    let base = setting("DART_BASE_URL", "https://opendart.fss.or.kr/api");
    let url = reqwest::Url::parse(&format!("{}/{}", base.trim_end_matches('/'), path))
        .map_err(|_| failed())?;
    if !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || !(url.scheme() == "https"
            || url.scheme() == "http"
                && matches!(
                    url.host_str(),
                    Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
                ))
    {
        return Err(failed());
    }
    Ok(url)
}
async fn request(path: &str, query: &[(&str, String)], key: &str) -> Result<Vec<u8>> {
    let mut url = endpoint(path)?;
    url.query_pairs_mut()
        .extend_pairs(query.iter().map(|(k, v)| (*k, v.as_str())))
        .append_pair("crtfc_key", key);
    let timeout = setting("INVESTMENT_CALENDAR_READ_TIMEOUT_SECONDS", "30")
        .parse::<u64>()
        .ok()
        .filter(|n| *n > 0 && *n <= 120)
        .unwrap_or(30);
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(3))
        .timeout(Duration::from_secs(timeout))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|_| failed())?;
    let mut response = client.get(url).send().await.map_err(|_| failed())?;
    let limit = if path == "document.xml" {
        MAX_ZIP
    } else {
        2_000_000
    };
    if !response.status().is_success()
        || response.content_length().is_some_and(|n| n > limit as u64)
    {
        return Err(failed());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| failed())? {
        if bytes.len() + chunk.len() > limit {
            return Err(failed());
        }
        bytes.extend_from_slice(&chunk);
    }
    if bytes.is_empty() {
        return Err(failed());
    }
    Ok(bytes)
}
#[derive(Default)]
pub(crate) struct DartCollection {
    pub entries: Vec<Value>,
    pub disclosure_count: u32,
    pub selected_documents: u32,
    pub fetched_documents: u32,
    pub failed_documents: u32,
    pub skipped_documents: u32,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Date {
    year: u32,
    month: u32,
    day: u32,
}
impl Date {
    fn new(year: u32, month: u32, day: u32) -> Option<Self> {
        let leap = year.is_multiple_of(400) || year.is_multiple_of(4) && !year.is_multiple_of(100);
        let days = [
            31,
            if leap { 29 } else { 28 },
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
        if year == 0 || !(1..=12).contains(&month) || day == 0 || day > days[(month - 1) as usize] {
            return None;
        }
        Some(Self { year, month, day })
    }
    fn iso(self) -> String {
        format!("{:04}-{:02}-{:02}", self.year, self.month, self.day)
    }
    fn ordinal(self) -> i64 {
        let y = i64::from(self.year) - 1;
        let mut days = y * 365 + y / 4 - y / 100 + y / 400;
        for month in 1..self.month {
            days += i64::from(match month {
                2 => {
                    if self.year.is_multiple_of(400)
                        || self.year.is_multiple_of(4) && !self.year.is_multiple_of(100)
                    {
                        29
                    } else {
                        28
                    }
                }
                4 | 6 | 9 | 11 => 30,
                _ => 31,
            });
        }
        days + i64::from(self.day)
    }
    fn basic(raw: &str) -> Option<Self> {
        if raw.len() != 8 || !raw.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        Self::new(
            raw[..4].parse().ok()?,
            raw[4..6].parse().ok()?,
            raw[6..8].parse().ok()?,
        )
    }
}
fn find_date(text: &str) -> Option<Date> {
    let bytes = text.as_bytes();
    for at in 0..bytes.len().saturating_sub(6) {
        if bytes.get(at..at + 2) != Some(b"20")
            || !bytes
                .get(at..at + 4)
                .is_some_and(|s| s.iter().all(|b| b.is_ascii_digit()))
        {
            continue;
        }
        if !bytes
            .get(at + 4)
            .is_some_and(|b| matches!(b, b'-' | b'.' | b'/'))
        {
            continue;
        }
        let start = at + 5;
        let count = bytes[start..]
            .iter()
            .take(2)
            .take_while(|b| b.is_ascii_digit())
            .count();
        if count == 0
            || !bytes
                .get(start + count)
                .is_some_and(|b| matches!(b, b'-' | b'.' | b'/'))
        {
            continue;
        }
        let day = start + count + 1;
        let n = bytes
            .get(day..)
            .unwrap_or_default()
            .iter()
            .take(2)
            .take_while(|b| b.is_ascii_digit())
            .count();
        if n == 0 {
            continue;
        }
        return Date::new(
            std::str::from_utf8(&bytes[at..at + 4]).ok()?.parse().ok()?,
            std::str::from_utf8(&bytes[start..start + count])
                .ok()?
                .parse()
                .ok()?,
            std::str::from_utf8(&bytes[day..day + n])
                .ok()?
                .parse()
                .ok()?,
        );
    }
    None
}
fn number(text: &str) -> Option<Value> {
    let raw = text.trim().replace(',', "");
    let raw = if raw.starts_with('(') && raw.ends_with(')') {
        format!("-{}", &raw[1..raw.len() - 1])
    } else {
        raw
    };
    if raw.is_empty() || raw == "-" || raw.len() > 128 {
        return None;
    }
    let (negative, unsigned) = if let Some(s) = raw.strip_prefix('-') {
        (true, s)
    } else {
        (false, raw.strip_prefix('+').unwrap_or(&raw))
    };
    let mut exponent = unsigned.split(['e', 'E']);
    let mantissa = exponent.next()?;
    let exp = exponent.next();
    if exponent.next().is_some()
        || exp.is_some_and(|e| {
            e.is_empty()
                || e.parse::<i32>()
                    .ok()
                    .is_none_or(|n| n.unsigned_abs() > 10000)
        })
    {
        return None;
    }
    let mut fields = mantissa.split('.');
    let integer = fields.next()?;
    let fraction = fields.next();
    if fields.next().is_some()
        || integer.is_empty() && fraction.is_none_or(str::is_empty)
        || !integer.bytes().all(|b| b.is_ascii_digit())
        || fraction.is_some_and(|f| !f.bytes().all(|b| b.is_ascii_digit()))
    {
        return None;
    }
    let integer = integer.trim_start_matches('0');
    let integer = if integer.is_empty() { "0" } else { integer };
    let mut numeric = format!("{}{integer}", if negative { "-" } else { "" });
    if let Some(fraction) = fraction {
        numeric.push('.');
        numeric.push_str(if fraction.is_empty() { "0" } else { fraction });
    }
    if let Some(exp) = exp {
        numeric.push('e');
        numeric.push_str(exp);
    }
    let value: Value = serde_json::from_str(&numeric).ok()?;
    value.is_number().then_some(value)
}
fn entities(raw: &str) -> String {
    let mut out = String::new();
    let mut rest = raw;
    while let Some(at) = rest.find('&') {
        out.push_str(&rest[..at]);
        rest = &rest[at..];
        let Some(end) = rest.find(';').filter(|n| *n <= 16) else {
            out.push('&');
            rest = &rest[1..];
            continue;
        };
        let key = &rest[1..end];
        let decoded = match key {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" => Some('\''),
            "nbsp" => Some(' '),
            _ => {
                if let Some(hex) = key.strip_prefix("#x").or_else(|| key.strip_prefix("#X")) {
                    u32::from_str_radix(hex, 16).ok().and_then(char::from_u32)
                } else if let Some(n) = key.strip_prefix('#') {
                    n.parse::<u32>().ok().and_then(char::from_u32)
                } else {
                    None
                }
            }
        };
        if let Some(c) = decoded {
            out.push(c);
        } else {
            out.push_str(&rest[..=end]);
        }
        rest = &rest[end + 1..];
    }
    out.push_str(rest);
    out
}
#[derive(Default, Debug)]
struct Row {
    text: String,
    cells: Vec<String>,
}
#[derive(Default, Debug)]
struct Document {
    rows: Vec<Row>,
    cells: Vec<String>,
}
fn text(raw: &str) -> String {
    entities(raw)
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
fn document(xml: &str) -> Document {
    // DART documents are HTML-like XML, including uppercase tags and partially
    // closed table markup. Only row/cell text is needed; DTDs/entities are never
    // expanded and no URI from a document is fetched.
    let xml = xml.replace("<![CDATA[", "").replace("]]>", "");
    let mut result = Document::default();
    let mut row: Option<Row> = None;
    let mut cell: Option<String> = None;
    let mut at = 0;
    while at < xml.len() {
        let Some(open) = xml[at..].find('<').map(|n| at + n) else {
            if let Some(row) = &mut row {
                row.text.push_str(&xml[at..]);
            }
            if let Some(cell) = &mut cell {
                cell.push_str(&xml[at..]);
            }
            break;
        };
        if let Some(row) = &mut row {
            row.text.push_str(&xml[at..open]);
        }
        if let Some(cell) = &mut cell {
            cell.push_str(&xml[at..open]);
        }
        if xml[open..].starts_with("<!--") {
            if let Some(end) = xml[open + 4..].find("-->") {
                at = open + 4 + end + 3;
                continue;
            }
            break;
        }
        let Some(end) = xml[open..].find('>').map(|n| open + n) else {
            break;
        };
        let tag = xml[open + 1..end].trim();
        let closing = tag.starts_with('/');
        let name = tag
            .trim_start_matches('/')
            .split([' ', '\t', '\r', '\n', '/'])
            .next()
            .unwrap_or("")
            .to_ascii_lowercase();
        if name == "tr" {
            if let Some(raw) = cell.take() {
                let value = text(&raw);
                if let Some(row) = &mut row {
                    row.cells.push(value.clone());
                }
                result.cells.push(value);
            }
            if let Some(mut row) = row.take() {
                row.text = text(&row.text);
                result.rows.push(row);
            }
            if !closing {
                row = Some(Row::default());
            }
        } else if name == "td" {
            if let Some(raw) = cell.take() {
                let value = text(&raw);
                if let Some(row) = &mut row {
                    row.cells.push(value.clone());
                }
                result.cells.push(value);
            }
            if !closing {
                cell = Some(String::new());
            }
        }
        // Jsoup separates block elements and table cells in Element.text().
        if matches!(name.as_str(), "td" | "th" | "p" | "div" | "br" | "li") {
            if let Some(row) = &mut row {
                row.text.push(' ');
            }
            if let Some(cell) = &mut cell {
                cell.push(' ');
            }
        }
        at = end + 1;
    }
    if let Some(raw) = cell {
        let value = text(&raw);
        if let Some(row) = &mut row {
            row.cells.push(value.clone());
        }
        result.cells.push(value);
    }
    if let Some(mut row) = row {
        row.text = text(&row.text);
        result.rows.push(row);
    }
    result
}
fn zip_document(bytes: Vec<u8>) -> Result<Document> {
    let mut archive = zip::ZipArchive::new(Cursor::new(bytes)).map_err(|_| failed())?;
    if archive.is_empty() {
        return Err(failed());
    }
    // Exactly the first entry is used, matching ZipInputStream.getNextEntry.
    let mut file = archive.by_index(0).map_err(|_| failed())?;
    if file.size() > MAX_XML {
        return Err(failed());
    }
    let mut raw = Vec::new();
    file.by_ref()
        .take(MAX_XML + 1)
        .read_to_end(&mut raw)
        .map_err(|_| failed())?;
    if raw.len() as u64 > MAX_XML {
        return Err(failed());
    }
    let xml = String::from_utf8(raw).map_err(|_| failed())?;
    Ok(document(&xml))
}
fn label_date(doc: &Document, label: &str) -> Option<Date> {
    doc.rows
        .iter()
        .filter(|row| row.text.contains(label))
        .find_map(|row| row.cells.iter().find_map(|cell| find_date(cell)))
}
fn parse_entry(disclosure: &Value, doc: &Document, advance: bool) -> Result<Option<Value>> {
    let (period, announced, previous, actual, unit) = if advance {
        let Some(period) = label_date(doc, "종료일") else {
            return Ok(None);
        };
        let Some(scheduled) = label_date(doc, "결산실적 공시예정일") else {
            return Ok(None);
        };
        (period, scheduled, Value::Null, Value::Null, "원")
    } else {
        let period = doc
            .rows
            .iter()
            .filter(|row| row.cells.len() >= 4 && row.cells[0].trim() == "당기실적")
            .find_map(|row| Some((find_date(&row.cells[1])?, find_date(&row.cells[3])?)));
        let Some((start, end)) = period else {
            return Ok(None);
        };
        if end.ordinal() - start.ordinal() < 70 {
            return Ok(None);
        }
        let (previous, actual) = doc
            .rows
            .iter()
            .find(|row| {
                row.cells.len() >= 4
                    && row.cells[0].trim() == "영업이익"
                    && row.cells[1].contains("당해실적")
            })
            .map(|row| {
                (
                    number(&row.cells[3]).unwrap_or(Value::Null),
                    number(&row.cells[2]).unwrap_or(Value::Null),
                )
            })
            .unwrap_or((Value::Null, Value::Null));
        let unit = doc
            .cells
            .iter()
            .find_map(|cell| {
                let cell = cell.replace(' ', "");
                if cell.contains("단위:백만원") {
                    Some("백만원")
                } else if cell.contains("단위:천원") {
                    Some("천원")
                } else if cell.contains("단위:원") {
                    Some("원")
                } else {
                    None
                }
            })
            .unwrap_or("원");
        let announced = disclosure["rcept_dt"]
            .as_str()
            .and_then(Date::basic)
            .ok_or_else(failed)?;
        (end, announced, previous, actual, unit)
    };
    let corporation = disclosure["corp_name"].as_str().ok_or_else(failed)?;
    let stock = disclosure["stock_code"].as_str().ok_or_else(failed)?;
    let receipt = disclosure["rcept_no"].as_str().ok_or_else(failed)?;
    let quarter = match period.month {
        3 => "1분기".into(),
        6 => "2분기".into(),
        9 => "3분기".into(),
        12 => "4분기".into(),
        month => format!("{month}월"),
    };
    Ok(Some(
        json!({"type":"CORPORATE_EARNINGS","title":format!("{corporation} {quarter} 실적 발표"),"announcedAt":format!("{}T00:00:00Z",announced.iso()),"previousValue":previous,"actualValue":actual,"valueUnit":unit,"sourceName":"전자공시시스템(DART)","sourceUrl":format!("{VIEWER}{receipt}"),"sourceKey":format!("DART-EARNINGS-{stock}-{}",period.iso()),"relatedAssetCode":stock}),
    ))
}
pub(crate) async fn collect(
    today: &str,
    lookback_days: u32,
    db: &Client,
) -> Result<DartCollection> {
    let key = setting("DART_API_KEY", "");
    if key.trim().is_empty() {
        return Err(fault(
            503,
            "DART_API_NOT_CONFIGURED",
            "OpenDART API 키가 설정되지 않았습니다.",
        ));
    }
    if lookback_days == 0 || lookback_days > 365 {
        return Err(failed());
    }
    let bounds = db
        .query_one(
            "SELECT to_char($1::text::date-$2::int,'YYYYMMDD'),to_char($1::text::date,'YYYYMMDD')",
            &[&today, &(lookback_days as i32)],
        )
        .await
        .map_err(|_| internal())?;
    let from: String = bounds.get(0);
    let to: String = bounds.get(1);
    let mut result = DartCollection::default();
    let mut entries = BTreeMap::<String, Value>::new();
    let mut page = 1u32;
    loop {
        let bytes = request(
            "list.json",
            &[
                ("bgn_de", from.clone()),
                ("end_de", to.clone()),
                ("pblntf_ty", "I".into()),
                ("last_reprt_at", "Y".into()),
                ("sort", "date".into()),
                ("sort_mth", "desc".into()),
                ("page_no", page.to_string()),
                ("page_count", "100".into()),
            ],
            &key,
        )
        .await?;
        let root: Value = serde_json::from_slice(&bytes).map_err(|_| failed())?;
        if root["status"] == "013" {
            result.entries = Vec::new();
            return Ok(result);
        }
        if root["status"] != "000" {
            return Err(failed());
        }
        let items = match root.get("list") {
            None | Some(Value::Null) => &[][..],
            Some(Value::Array(items)) => items.as_slice(),
            _ => return Err(failed()),
        };
        if items.len() > 100 {
            return Err(failed());
        }
        result.disclosure_count += items.len() as u32;
        for item in items {
            let Some(stock) = item["stock_code"].as_str().filter(|s| !s.trim().is_empty()) else {
                continue;
            };
            let _ = stock;
            let report = item["report_nm"]
                .as_str()
                .ok_or_else(failed)?
                .chars()
                .filter(|c| !c.is_ascii_whitespace())
                .collect::<String>();
            let advance = report.contains("결산실적공시예고");
            if !advance && !report.contains("영업(잠정)실적(공정공시)") {
                continue;
            }
            result.selected_documents += 1;
            let receipt = item["rcept_no"].as_str().ok_or_else(failed)?;
            let doc = match request("document.xml", &[("rcept_no", receipt.into())], &key).await {
                Ok(bytes) => tokio::task::spawn_blocking(move || zip_document(bytes))
                    .await
                    .map_err(|_| failed())?,
                Err(error) => Err(error),
            };
            let doc = match doc {
                Ok(doc) => {
                    result.fetched_documents += 1;
                    doc
                }
                Err(_) => {
                    result.failed_documents += 1;
                    continue;
                }
            };
            if let Some(entry) = parse_entry(item, &doc, advance)? {
                let source = entry["sourceKey"].as_str().ok_or_else(failed)?.to_owned();
                let replace = entries.get(&source).is_none_or(|old| {
                    !entry["actualValue"].is_null() || old["actualValue"].is_null()
                });
                if replace {
                    entries.insert(source, entry);
                }
            } else {
                result.skipped_documents += 1;
            }
        }
        let total = root["total_page"].as_u64().unwrap_or(1).max(1);
        // Native resource bounds are explicit; oversized pagination is a
        // provider failure rather than a silently truncated successful import.
        if total > 1000 {
            return Err(failed());
        }
        if u64::from(page) >= total {
            break;
        }
        page += 1;
    }
    result.entries = entries.into_values().collect();
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    fn disclosure() -> Value {
        json!({"corp_name":"검증기업","stock_code":"005930","rcept_no":"20260430000001","rcept_dt":"20260430"})
    }
    const ADVANCE: &str = "<HTML><TABLE><TR><TD>종료일</TD><TD><P>2026.03.31</P></TD></TR><TR><TD>결산실적 공시예정일</TD><TD>2026-4-30</TD></TR></TABLE></HTML>";
    #[test]
    fn advance_and_result_tables_preserve_values_and_event_identity() {
        let advance = parse_entry(&disclosure(), &document(ADVANCE), true)
            .unwrap()
            .unwrap();
        assert_eq!(advance["sourceKey"], "DART-EARNINGS-005930-2026-03-31");
        assert_eq!(advance["announcedAt"], "2026-04-30T00:00:00Z");
        assert_eq!(advance["title"], "검증기업 1분기 실적 발표");
        assert!(advance["actualValue"].is_null());
        let xml = "<table><tr><td>당기실적</td><td>2026/01/01</td><td>~</td><td>2026/03/31</td></tr><tr><td>영업이익</td><td>당해실적</td><td>1,234.50</td><td>&#40;200.25&#41;</td></tr><tr><td>(단위: 백만원)</td></tr></table>";
        let actual = parse_entry(&disclosure(), &document(xml), false)
            .unwrap()
            .unwrap();
        assert_eq!(actual["sourceKey"], advance["sourceKey"]);
        assert_eq!(actual["previousValue"].to_string(), "-200.25");
        assert_eq!(actual["actualValue"].to_string(), "1234.50");
        assert_eq!(actual["valueUnit"], "백만원");
        let short = xml.replace("2026/01/01", "2026/03/01");
        assert!(
            parse_entry(&disclosure(), &document(&short), false)
                .unwrap()
                .is_none()
        );
    }
    #[test]
    fn zipped_document_uses_first_deflated_entry_without_extracting_files() {
        let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
        let options = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated);
        zip.start_file("report.xml", options).unwrap();
        zip.write_all(ADVANCE.as_bytes()).unwrap();
        zip.start_file("ignored.xml", options).unwrap();
        zip.write_all(b"not a relevant report").unwrap();
        let bytes = zip.finish().unwrap().into_inner();
        let doc = zip_document(bytes).unwrap();
        assert_eq!(label_date(&doc, "종료일").unwrap().iso(), "2026-03-31");
        assert!(zip_document(b"not a ZIP".to_vec()).is_err());
    }
    #[test]
    fn decimal_and_calendar_parsers_match_representative_dart_cells() {
        assert_eq!(number("(1,234.00)").unwrap().to_string(), "-1234.00");
        assert_eq!(number("+0001.25").unwrap().to_string(), "1.25");
        assert_eq!(number(".5").unwrap().to_string(), "0.5");
        assert!(number("-").is_none());
        assert!(number("not a number").is_none());
        assert_eq!(find_date("예정일 2024.2.29").unwrap().iso(), "2024-02-29");
        assert!(find_date("예정일 2025.2.29").is_none());
    }
}
