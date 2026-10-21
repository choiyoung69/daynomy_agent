#![forbid(unsafe_code)]
use serde_json::{Value, json};

fn invalid(errors: Vec<Value>) -> (u16, Value) {
    (400,json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":errors}))
}

fn decode(input:&str)->Option<String> {
    let mut out=Vec::new();
    let mut bytes=input.bytes();
    while let Some(byte)=bytes.next() {
        match byte {
            b'+' => out.push(b' '),
            b'%' => {
                let high=(bytes.next()? as char).to_digit(16)?;
                let low=(bytes.next()? as char).to_digit(16)?;
                out.push((high*16+low) as u8);
            }
            _=>out.push(byte),
        }
    }
    String::from_utf8(out).ok()
}

fn time_key(row:&Value)->(String,String) {
    let value=row["created_at"].as_str().unwrap_or("");
    let seconds=value.chars().take(19).collect::<String>();
    let fraction=value.get(19..).and_then(|v|v.strip_prefix('.')).unwrap_or("");
    let mut nanos=fraction.chars().take_while(char::is_ascii_digit).take(9).collect::<String>();
    while nanos.len()<9 {nanos.push('0');}
    (seconds,nanos)
}

pub fn list(query:&str,rows:&Value)->(u16,Value) {
    let mut page_raw=None;
    let mut size_raw=None;
    for pair in query.trim_start_matches('?').split('&').filter(|v|!v.is_empty()) {
        let (key,value)=pair.split_once('=').unwrap_or((pair,""));
        let Some(key)=decode(key) else {continue;};
        let slot=match key.as_str() {"page"=>&mut page_raw,"size"=>&mut size_raw,_=>continue};
        if slot.is_none() {
            let Some(value)=decode(value) else {return invalid(vec![json!({"field":key,"reason":"타입이 올바르지 않습니다."})]);};
            *slot=Some(value);
        }
    }
    let mut parsed=[1i32,15i32];
    for (index,(key,value)) in [("page",page_raw),("size",size_raw)].into_iter().enumerate() {
        if let Some(value)=value {
            if value.is_empty() {continue;}
            match value.trim().parse::<i32>() {
                Ok(number)=>parsed[index]=number,
                Err(_)=>return invalid(vec![json!({"field":key,"reason":"타입이 올바르지 않습니다."})]),
            }
        }
    }
    let [page,size]=parsed;
    let mut errors=Vec::new();
    if page<1 {errors.push(json!({"field":"page","reason":"페이지 번호는 1 이상이어야 합니다."}));}
    if size<1 {errors.push(json!({"field":"size","reason":"페이지 크기는 1 이상이어야 합니다."}));}
    if size>100 {errors.push(json!({"field":"size","reason":"페이지 크기는 100 이하여야 합니다."}));}
    if !errors.is_empty() {return invalid(errors);}
    let mut sorted=rows.as_array().map(|values|values.iter().collect::<Vec<_>>()).unwrap_or_default();
    sorted.sort_by(|a,b| time_key(b).cmp(&time_key(a)).then_with(||b["id"].as_i64().cmp(&a["id"].as_i64())));
    let total=sorted.len();
    let total_pages=total.div_ceil(size as usize);
    let offset=(page as u64-1)*size as u64;
    let items=sorted.into_iter().skip(usize::try_from(offset).unwrap_or(usize::MAX)).take(size as usize).map(|row|json!({
        "id":row["id"].clone(),"content":row["content"].clone(),"pagePath":row["page_path"].clone(),
        "status":row["status"].clone(),"createdAt":row["created_at"].clone(),"updatedAt":row["updated_at"].clone()
    })).collect::<Vec<_>>();
    (200,json!({"items":items,"page":page,"size":size,"totalPages":total_pages,"totalElements":total,"hasNext":(page as u64)<total_pages as u64}))
}
