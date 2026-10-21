use serde_json::{Number, Value, json};
use std::{
    collections::{HashMap, HashSet},
    str::FromStr,
};
#[derive(Clone, Copy)]
struct D {
    i: i128,
    s: u32,
}
impl D {
    fn parse(v: &Value) -> Option<Self> {
        let x = match v {
            Value::Number(n) => n.to_string(),
            _ => return None,
        };
        let neg = x.starts_with('-');
        let x = x.trim_start_matches(['-', '+']);
        let mut exponent_parts = x.split(['e', 'E']);
        let mantissa = exponent_parts.next()?;
        let exponent = exponent_parts
            .next()
            .map(|value| value.parse::<i64>().ok())
            .unwrap_or(Some(0))?;
        if exponent_parts.next().is_some() {
            return None;
        }
        let (a, b) = mantissa.split_once('.').unwrap_or((mantissa, ""));
        if a.is_empty()
            || !a.bytes().all(|c| c.is_ascii_digit())
            || !b.bytes().all(|c| c.is_ascii_digit())
        {
            return None;
        }
        let scale = i64::try_from(b.len()).ok()?.checked_sub(exponent)?;
        let mut digits = format!("{}{}", a, b);
        let s = if scale < 0 {
            let zero_count = usize::try_from(scale.checked_neg()?).ok()?;
            if zero_count > 38 {
                return None;
            }
            digits.reserve(zero_count);
            digits.extend(std::iter::repeat_n('0', zero_count));
            0
        } else {
            if scale > 38 {
                return None;
            }
            u32::try_from(scale).ok()?
        };
        let mut i = digits.parse::<i128>().ok()?;
        if neg {
            i = -i
        }
        Some(D { i, s })
    }
    fn pow(n: u32) -> i128 {
        (0..n).fold(1, |x, _| x * 10)
    }
    fn at(self, s: u32) -> i128 {
        self.i * Self::pow(s - self.s)
    }
    fn add(self, o: D) -> D {
        let s = self.s.max(o.s);
        D {
            i: self.at(s) + o.at(s),
            s,
        }
    }
    fn sub(self, o: D) -> D {
        self.add(D { i: -o.i, s: o.s })
    }
    fn mul(self, o: D) -> D {
        D {
            i: self.i * o.i,
            s: self.s + o.s,
        }
    }
    fn round(self, s: u32) -> D {
        if self.s <= s {
            return D {
                i: self.i * Self::pow(s - self.s),
                s,
            };
        }
        let p = Self::pow(self.s - s);
        let (q, r) = (self.i / p, self.i % p);
        D {
            i: q + if r.abs() * 2 >= p { self.i.signum() } else { 0 },
            s,
        }
    }
    fn pct(self, t: D) -> D {
        if t.i == 0 {
            return D { i: 0, s: 2 };
        }
        let numerator = self.i.unsigned_abs();
        let denominator = t.i.unsigned_abs();
        let shift = i64::from(t.s) + 4 - i64::from(self.s);
        let mut quotient = numerator / denominator;
        let mut remainder = numerator % denominator;
        if shift >= 0 {
            for _ in 0..shift {
                // Long division: 10*remainder without overflowing even near u128::MAX.
                let mut next_remainder = 0_u128;
                let mut digit = 0_u128;
                for _ in 0..10 {
                    if next_remainder >= denominator - remainder {
                        next_remainder -= denominator - remainder;
                        digit += 1;
                    } else {
                        next_remainder += remainder;
                    }
                }
                quotient = quotient
                    .checked_mul(10)
                    .and_then(|q| q.checked_add(digit))
                    .expect("final percentage is within the sample numeric domain");
                remainder = next_remainder;
            }
            if remainder >= denominator - remainder {
                quotient += 1;
            }
        } else {
            let places = u32::try_from(-shift).unwrap_or(u32::MAX);
            if places > 38 {
                return D { i: 0, s: 2 };
            }
            let divisor = 10_u128.pow(places);
            let residual = quotient % divisor;
            quotient /= divisor;
            if residual >= divisor / 2 {
                quotient += 1;
            }
        }
        let absolute =
            i128::try_from(quotient).expect("final percentage fits sample numeric domain");
        D {
            i: if self.i.signum() == t.i.signum() {
                absolute
            } else {
                -absolute
            },
            s: 2,
        }
    }
    fn val(self) -> Value {
        let neg = self.i < 0;
        let n = self.i.abs().to_string();
        let t = if self.s == 0 {
            format!("{}{}", if neg { "-" } else { "" }, n)
        } else {
            let w = self.s as usize;
            let p = format!("{:0>width$}", n, width = w + 1);
            let k = p.len() - w;
            format!("{}{}.{}", if neg { "-" } else { "" }, &p[..k], &p[k..])
        };
        Value::Number(Number::from_str(&t).unwrap())
    }
}
fn f<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.get(k).unwrap_or(&Value::Null)
}
fn invalid(e: Vec<Value>) -> (u16, Value) {
    (
        400,
        json!({"code":"INVALID_REQUEST","message":"요청값이 올바르지 않습니다.","errors":e}),
    )
}
fn biz(s: u16, c: &str, m: &str) -> (u16, Value) {
    (s, json!({"code":c,"message":m}))
}
// Validate decimal shape before bounded arithmetic, like BigDecimal DTO validation.
// This does not expand exponent-sized strings or parse a value through f64.
fn price_constraints(value: &Value) -> Option<(bool, bool)> {
    let text = value.as_number()?.to_string();
    let negative = text.starts_with('-');
    let unsigned = text.trim_start_matches(['-', '+']);
    let mut parts = unsigned.split(['e', 'E']);
    let mantissa = parts.next()?;
    let exponent = match parts.next() {
        Some(e) => e.parse::<i64>().ok()?,
        None => 0,
    };
    let (whole, fraction) = mantissa.split_once('.').unwrap_or((mantissa, ""));
    let coefficient = format!("{whole}{fraction}");
    let significant = coefficient.trim_start_matches('0');
    let zero = significant.is_empty();
    let precision = significant.len().max(1) as i64;
    let scale = (fraction.len() as i64).saturating_sub(exponent);
    let integer_digits = precision.saturating_sub(scale);
    let below_minimum = negative || zero || integer_digits < -1;
    let too_many_digits = integer_digits > 15 || scale > 2;
    Some((below_minimum, too_many_digits))
}
struct H {
    a: Value,
    d: Option<String>,
    q: i64,
    avg: D,
    c: Option<D>,
    p: D,
    e: Option<D>,
    pl: Option<D>,
    r: Option<D>,
}
pub fn calculate(body: &[u8], data: &Value) -> (u16, Value) {
    let req: Value = match serde_json::from_slice(body) {
        Ok(v) => v,
        Err(_) => {
            return invalid(vec![
                json!({"field":"requestBody","reason":"요청 본문을 읽을 수 없습니다."}),
            ]);
        }
    };
    if !req.is_object() {
        return invalid(vec![
            json!({"field":"requestBody","reason":"요청 본문을 읽을 수 없습니다."}),
        ]);
    }
    let Some(hs) = req.get("holdings").and_then(Value::as_array) else {
        if req.get("holdings").is_some_and(|v| !v.is_null()) {
            return invalid(vec![
                json!({"field":"requestBody","reason":"요청 본문을 읽을 수 없습니다."}),
            ]);
        }
        return invalid(vec![
            json!({"field":"holdings","reason":"보유자산을 한 개 이상 입력해주세요."}),
        ]);
    };
    let mut es = vec![];
    if hs.is_empty() {
        es.push(json!({"field":"holdings","reason":"보유자산을 한 개 이상 입력해주세요."}))
    }
    if hs.len() > 50 {
        es.push(json!({"field":"holdings","reason":"보유자산은 최대 50개까지 계산할 수 있습니다."}))
    }
    let mut input = vec![];
    for (i, h) in hs.iter().enumerate() {
        if h.is_null() {
            es.push(
                json!({"field":format!("holdings[{}]",i),"reason":"보유자산 정보를 입력해주세요."}),
            );
            continue;
        }
        if !h.is_object()
            || ["assetId", "quantity"].iter().any(|k| {
                h.get(k)
                    .is_some_and(|v| !v.is_null() && v.as_i64().is_none())
            })
            || h.get("averagePurchasePrice")
                .is_some_and(|v| !v.is_null() && !v.is_number())
        {
            return invalid(vec![
                json!({"field":"requestBody","reason":"요청 본문을 읽을 수 없습니다."}),
            ]);
        }
        let (a, q, p) = (
            f(h, "assetId").as_i64(),
            f(h, "quantity").as_i64(),
            D::parse(f(h, "averagePurchasePrice")),
        );
        match a {
            None => es.push(json!({"field":format!("holdings[{}].assetId",i),"reason":"종목 ID를 입력해주세요."})),
            Some(value) if value <= 0 => es.push(json!({"field":format!("holdings[{}].assetId",i),"reason":"종목 ID는 1 이상이어야 합니다."})),
            Some(_) => {}
        }
        match q {
            None => es.push(json!({"field":format!("holdings[{}].quantity",i),"reason":"보유 수량을 입력해주세요."})),
            Some(value) if value <= 0 => es.push(json!({"field":format!("holdings[{}].quantity",i),"reason":"보유 수량은 1 이상이어야 합니다."})),
            Some(_) => {}
        }
        let price = f(h, "averagePurchasePrice");
        if price.is_null() {
            es.push(json!({"field":format!("holdings[{}].averagePurchasePrice",i),"reason":"평균 매수가를 입력해주세요."}));
        } else if let Some((below_minimum, too_many_digits)) = price_constraints(price) {
            if below_minimum {
                es.push(json!({"field":format!("holdings[{}].averagePurchasePrice",i),"reason":"평균 매수가는 0보다 커야 합니다."}));
            }
            if too_many_digits {
                es.push(json!({"field":format!("holdings[{}].averagePurchasePrice",i),"reason":"평균 매수가는 정수 15자리, 소수 2자리 이하여야 합니다."}));
            }
        } else {
            return invalid(vec![
                json!({"field":"requestBody","reason":"요청 본문을 읽을 수 없습니다."}),
            ]);
        }
        if let (Some(a), Some(q), Some(p)) = (a, q, p) {
            input.push((a, q, p))
        }
    }
    if !es.is_empty() {
        return invalid(es);
    }
    let mut seen = HashSet::new();
    if input.iter().any(|x| !seen.insert(x.0)) {
        return biz(
            400,
            "DUPLICATE_PORTFOLIO_ASSET",
            "포트폴리오에 중복된 종목이 있습니다.",
        );
    }
    let assets: HashMap<i64, Value> = f(data, "assets")
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|a| Some((f(a, "id").as_i64()?, a.clone())))
        .collect();
    let mut rates = HashMap::new();
    for r in f(data, "usd_krw_rates").as_array().into_iter().flatten() {
        if let (Some(d), Some(x)) = (f(r, "requested_date").as_str(), D::parse(f(r, "rate"))) {
            rates.insert(d.to_string(), x);
        }
    }
    let (mut out, mut tp, mut te, mut prev) =
        (vec![], D { i: 0, s: 0 }, D { i: 0, s: 0 }, D { i: 0, s: 0 });
    let (mut cd, mut pd) = (HashSet::new(), HashSet::new());
    let (mut allprev, mut un) = (true, 0usize);
    for (aid, q, avg) in input {
        let Some(a) = assets.get(&aid).cloned() else {
            return biz(404, "ASSET_NOT_FOUND", "자산을 찾을 수 없습니다.");
        };
        let mut ps: Vec<&Value> = f(data, "stock_daily_prices")
            .as_array()
            .into_iter()
            .flatten()
            .filter(|p| f(p, "asset_id").as_i64() == Some(aid))
            .collect();
        ps.sort_by(|a, b| f(b, "base_date").as_str().cmp(&f(a, "base_date").as_str()));
        ps.truncate(2);
        let usd = matches!(
            f(&a, "market").as_str(),
            Some("NASDAQ" | "NYSE" | "NYSE_ARCA" | "NYSE_AMERICAN" | "BATS")
        );
        let cv = |p: &Value| -> Option<D> {
            let x = D::parse(f(p, "close_price"))?;
            if usd {
                Some(x.mul(*rates.get(f(p, "base_date").as_str()?)?))
            } else {
                Some(x)
            }
        };
        let pa = avg.mul(D { i: q as i128, s: 0 }).round(2);
        tp = tp.add(pa);
        let Some(cur) = ps.first().and_then(|p| cv(p)) else {
            un += 1;
            allprev = false;
            out.push(H {
                a,
                d: None,
                q,
                avg: avg.round(2),
                c: None,
                p: pa,
                e: None,
                pl: None,
                r: None,
            });
            continue;
        };
        let p = ps[0];
        let ev = cur.mul(D { i: q as i128, s: 0 }).round(2);
        let pl = ev.sub(pa).round(2);
        te = te.add(ev);
        let date = f(p, "base_date").as_str().unwrap().to_string();
        cd.insert(date.clone());
        if ps.len() < 2 || f(ps[1], "base_date").as_str() >= Some(date.as_str()) {
            allprev = false
        } else if let Some(x) = cv(ps[1]) {
            pd.insert(f(ps[1], "base_date").as_str().unwrap().to_string());
            prev = prev.add(x.mul(D { i: q as i128, s: 0 }))
        } else {
            allprev = false
        }
        out.push(H {
            a,
            d: Some(date),
            q,
            avg: avg.round(2),
            c: D::parse(f(p, "close_price")),
            p: pa,
            e: Some(ev),
            pl: Some(pl),
            r: Some(pl.pct(pa)),
        })
    }
    tp = tp.round(2);
    te = te.round(2);
    let complete = un == 0;
    let totalpl = if complete {
        Some(te.sub(tp).round(2))
    } else {
        None
    };
    let daily = if complete && allprev && cd.len() == 1 && pd.len() == 1 {
        let p = prev.round(2);
        let d = te.sub(p).round(2);
        Some((d, d.pct(p)))
    } else {
        None
    };
    let base = out
        .iter()
        .filter_map(|h| h.d.as_deref())
        .min()
        .map(str::to_string);
    let mut allocations = vec![];
    for m in [
        "KOSPI",
        "KOSDAQ",
        "NASDAQ",
        "NYSE",
        "NYSE_ARCA",
        "NYSE_AMERICAN",
        "BATS",
    ] {
        let x = out
            .iter()
            .filter(|h| f(&h.a, "market") == m)
            .filter_map(|h| h.e)
            .fold(D { i: 0, s: 0 }, |a, b| a.add(b));
        if x.i != 0 {
            allocations.push(
                json!({"market":m,"evaluationAmount":x.round(2).val(),"weight":x.pct(te).val()}),
            )
        }
    }
    let holdings:Vec<Value>=out.iter().map(|h|{let m=f(&h.a,"market");json!({"assetId":f(&h.a,"id"),"assetCode":f(&h.a,"asset_code"),"name":f(&h.a,"name"),"category":f(&h.a,"category"),"market":m,"priceAvailable":h.c.is_some(),"baseDate":h.d,"quantity":h.q,"averagePurchasePrice":h.avg.val(),"closePrice":h.c.map(D::val),"purchaseAmount":h.p.val(),"evaluationAmount":h.e.map(D::val),"profitLoss":h.pl.map(D::val),"returnRate":h.r.map(D::val),"weight":h.e.map(|x|x.pct(te).val()),"averagePurchasePriceCurrency":"KRW","currency":if matches!(m.as_str(),Some("NASDAQ"|"NYSE"|"NYSE_ARCA"|"NYSE_AMERICAN"|"BATS")){"USD"}else{"KRW"},"evaluationCurrency":"KRW"})}).collect();
    let status = if un > 0 {
        "PARTIAL"
    } else if cd.len() > 1 {
        "MIXED_DATES"
    } else {
        "COMPLETE"
    };
    (
        200,
        json!({"baseDate":base,"pricingStatus":status,"pricedHoldingCount":out.len()-un,"unpricedHoldingCount":un,"totalPurchaseAmount":tp.val(),"totalEvaluationAmount":te.val(),"dailyProfitLoss":daily.map(|x|x.0.val()),"dailyReturnRate":daily.map(|x|x.1.val()),"totalProfitLoss":totalpl.map(D::val),"totalReturnRate":totalpl.map(|x|x.pct(tp).val()),"holdings":holdings,"marketAllocations":allocations}),
    )
}
