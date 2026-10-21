//! Monthly calendar and historical portfolio reactions, using the original
//! InvestmentCalendarService / TradingDayReactionCalculator contracts.
use crate::api::{ApiFault, Outcome, fault, internal, invalid, rows};
use crate::service_auth::Principal;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use tokio_postgres::Client;

pub async fn handle(
    method: &str,
    path: &str,
    query: &str,
    body: &[u8],
    principal: Option<&Principal>,
    db: &Client,
) -> Option<Outcome> {
    let member = match (method, path) {
        ("POST", "/api/investment-calendar") => None,
        ("GET", "/api/users/me/investment-calendar") => match principal {
            Some(p) => Some(p.id),
            None => return Some(Err(fault(401, "UNAUTHORIZED", "로그인이 필요합니다."))),
        },
        _ => return None,
    };
    Some(calendar(query, body, member, db).await)
}

fn positive(input: &Value, name: &str, index: usize) -> Result<i64, ApiFault> {
    let field = format!("holdings[{index}].{name}");
    let (missing, range) = if name == "assetId" {
        ("종목 ID를 입력해주세요.", "종목 ID는 1 이상이어야 합니다.")
    } else {
        (
            "보유 수량을 입력해주세요.",
            "보유 수량은 1 이상이어야 합니다.",
        )
    };
    let value = input
        .get(name)
        .filter(|v| !v.is_null())
        .ok_or_else(|| invalid(&field, missing))?;
    let number = value
        .as_i64()
        .ok_or_else(|| invalid(&field, "타입이 올바르지 않습니다."))?;
    if number < 1 {
        return Err(invalid(&field, range));
    }
    Ok(number)
}

fn guest_holdings(body: &[u8]) -> Result<String, ApiFault> {
    let input: Value = serde_json::from_slice(body)
        .map_err(|_| fault(400, "INVALID_REQUEST", "요청값이 올바르지 않습니다."))?;
    let raw = input
        .get("holdings")
        .filter(|v| !v.is_null())
        .ok_or_else(|| invalid("holdings", "보유자산 목록을 입력해주세요."))?;
    let holdings = raw
        .as_array()
        .ok_or_else(|| invalid("holdings", "타입이 올바르지 않습니다."))?;
    if holdings.len() > 50 {
        return Err(invalid(
            "holdings",
            "보유자산은 최대 50개까지 조회할 수 있습니다.",
        ));
    }
    let mut unique = BTreeMap::new();
    for (index, holding) in holdings.iter().enumerate() {
        if holding.is_null() {
            return Err(invalid(
                &format!("holdings[{index}]"),
                "보유자산 정보를 입력해주세요.",
            ));
        }
        if !holding.is_object() {
            return Err(invalid("holdings", "타입이 올바르지 않습니다."));
        }
        // Validate all entries, including duplicates, before selecting the first.
        let asset = positive(holding, "assetId", index)?;
        let quantity = positive(holding, "quantity", index)?;
        unique.entry(asset).or_insert(quantity);
    }
    Ok(Value::Array(
        unique
            .into_iter()
            .map(|(asset_id, quantity)| json!({"asset_id":asset_id,"quantity":quantity}))
            .collect(),
    )
    .to_string())
}

async fn calendar(raw: &str, body: &[u8], member: Option<i64>, db: &Client) -> Outcome {
    let query = crate::api::query(raw)?;
    let integer = |name: &str, lower: i32, upper: i32| -> Result<i32, ApiFault> {
        let raw = query
            .get(name)
            .ok_or_else(|| invalid(name, "필수 요청 파라미터입니다."))?;
        let value = crate::java_binding::integer(raw)
            .and_then(|value| i32::try_from(value).ok())
            .ok_or_else(|| invalid(name, "타입이 올바르지 않습니다."))?;
        if !(lower..=upper).contains(&value) {
            return Err(invalid(name, "허용 범위를 벗어났습니다."));
        }
        Ok(value)
    };
    let year = integer("year", 2000, 2100)?;
    let month = integer("month", 1, 12)?;
    let scope = query
        .get("scope")
        .filter(|s| !s.is_empty())
        .map(String::as_str)
        .unwrap_or("PORTFOLIO");
    if !matches!(scope, "PORTFOLIO" | "ALL") {
        return Err(invalid("scope", "타입이 올바르지 않습니다."));
    }
    let holdings = if member.is_none() {
        guest_holdings(body)?
    } else {
        "[]".into()
    };
    let mut result = rows(
        db,
        CALENDAR_SQL,
        &[&year, &month, &scope, &holdings, &member],
    )
    .await?;
    Ok((200, result.pop().ok_or_else(internal)?))
}

// Round at the same intermediate stages as the Java BigDecimal calculator.
// Unknown guest asset IDs are ignored, as AssetRepository.findAllById does.
const CALENDAR_SQL: &str = r#"
WITH holdings AS (
    SELECT a.id AS asset_id,a.asset_code,g.quantity
    FROM jsonb_to_recordset($4::text::jsonb) AS g(asset_id bigint,quantity bigint)
    JOIN assets a ON a.id=g.asset_id WHERE $5::bigint IS NULL
    UNION ALL
    SELECT a.id,a.asset_code,h.quantity FROM portfolios p
    JOIN portfolio_holdings h ON h.portfolio_id=p.id
    JOIN assets a ON a.id=h.asset_id WHERE p.member_id=$5::bigint
), current_holdings AS (
    SELECT h.*,p.close_price*h.quantity AS evaluation,p.base_date
    FROM holdings h JOIN LATERAL (
        SELECT close_price,base_date FROM stock_daily_prices WHERE asset_id=h.asset_id
        ORDER BY base_date DESC LIMIT 1
    ) p ON true
), selected AS (
    SELECT e.* FROM investment_events e
    WHERE e.announced_at >= (make_date($1::integer,$2::integer,1)::timestamp AT TIME ZONE 'Asia/Seoul')
    AND e.announced_at < ((make_date($1::integer,$2::integer,1)+interval '1 month')::timestamp AT TIME ZONE 'Asia/Seoul')
    AND ($3::text='ALL' OR e.event_type<>'CORPORATE_EARNINGS'
         OR EXISTS (SELECT 1 FROM holdings h WHERE h.asset_code=e.related_asset_code))
), related AS (
    SELECT e.id AS selected_id,h.* FROM selected e JOIN current_holdings h
    ON e.event_type<>'CORPORATE_EARNINGS' OR e.related_asset_code IS NULL OR e.related_asset_code=h.asset_code
), evaluations AS (
    SELECT selected_id,count(*) AS asset_count,sum(evaluation) AS total,min(base_date) AS price_date
    FROM related GROUP BY selected_id
), history AS (
    SELECT e.id AS selected_id,h.id AS history_id,h.announced_at,
      (h.announced_at AT TIME ZONE 'Asia/Seoul')::date AS event_date,
      (h.announced_at AT TIME ZONE 'Asia/Seoul')::time <= time '15:30' AS before_close,
      CASE WHEN h.previous_value IS NULL THEN 'UNAVAILABLE'
           WHEN h.actual_value>h.previous_value THEN 'INCREASED'
           WHEN h.actual_value<h.previous_value THEN 'DECREASED' ELSE 'UNCHANGED' END AS direction
    FROM selected e JOIN investment_events h ON h.event_type=e.event_type
      AND h.actual_value IS NOT NULL AND h.announced_at<e.announced_at
      AND (e.event_type<>'CORPORATE_EARNINGS' OR h.related_asset_code IS NOT DISTINCT FROM e.related_asset_code)
    WHERE EXISTS (SELECT 1 FROM related r WHERE r.selected_id=e.id)
), reactions AS (
    SELECT h.selected_id,h.history_id,h.direction,r.evaluation,
        round((reaction.close_price-base.close_price)*100/base.close_price,4) AS rate
    FROM history h JOIN related r ON r.selected_id=h.selected_id
    -- For announcements at/before 15:30 the reaction is the first trading day
    -- on/after that date. Later announcements use the last day on/before it.
    JOIN LATERAL (
        SELECT p.base_date,p.close_price FROM stock_daily_prices p
        WHERE p.asset_id=r.asset_id AND p.base_date BETWEEN h.event_date-10 AND h.event_date+10
          AND CASE WHEN h.before_close THEN p.base_date>=h.event_date ELSE p.base_date<=h.event_date END
        ORDER BY CASE WHEN h.before_close THEN p.base_date END ASC,
                 CASE WHEN NOT h.before_close THEN p.base_date END DESC LIMIT 1
    ) anchor ON true
    JOIN LATERAL (
        SELECT p.close_price FROM stock_daily_prices p
        WHERE p.asset_id=r.asset_id AND p.base_date BETWEEN h.event_date-10 AND h.event_date+10
          AND CASE WHEN h.before_close THEN p.base_date<anchor.base_date ELSE p.base_date=anchor.base_date END
        ORDER BY p.base_date DESC LIMIT 1
    ) base ON true
    JOIN LATERAL (
        SELECT p.close_price FROM stock_daily_prices p
        WHERE p.asset_id=r.asset_id AND p.base_date BETWEEN h.event_date-10 AND h.event_date+10
          AND CASE WHEN h.before_close THEN p.base_date=anchor.base_date ELSE p.base_date>anchor.base_date END
        ORDER BY p.base_date ASC LIMIT 1
    ) reaction ON true
), covered AS (
    SELECT *,sum(evaluation) OVER (PARTITION BY selected_id,history_id) AS covered_evaluation FROM reactions
), portfolio_returns AS (
    SELECT selected_id,history_id,direction,sum(round(rate*evaluation/covered_evaluation,8)) AS rate
    FROM covered WHERE covered_evaluation<>0 GROUP BY selected_id,history_id,direction
), grouped AS (
    SELECT selected_id,direction,array_agg(rate ORDER BY rate) AS rates,count(*)::integer AS n
    FROM portfolio_returns GROUP BY selected_id,direction
), directions AS (
    SELECT * FROM (VALUES ('DECREASED',1),('UNCHANGED',2),('INCREASED',3)) AS d(direction,ordinal)
), quantiles AS (
    SELECT e.selected_id,d.direction,d.ordinal,coalesce(g.n,0) AS n,e.total,
      CASE WHEN g.n>=3 THEN CASE WHEN g.n%2=1 THEN g.rates[(g.n+1)/2]
           ELSE round((g.rates[g.n/2]+g.rates[g.n/2+1])/2,8) END END AS median,
      CASE WHEN g.n>=3 THEN g.rates[floor((g.n-1)*0.25+0.5)::integer+1] END AS lower,
      CASE WHEN g.n>=3 THEN g.rates[floor((g.n-1)*0.75+0.5)::integer+1] END AS upper
    FROM evaluations e CROSS JOIN directions d LEFT JOIN grouped g
      ON g.selected_id=e.selected_id AND g.direction=d.direction
), statistics AS (
    SELECT selected_id,bool_or(n>=3) AS ready,coalesce(max(abs(round(median,2))),0) AS max_median,
      jsonb_agg(jsonb_build_object('direction',direction,'sampleCount',n,
        'medianReturnRate',round(median,2),'lowerReturnRate',round(lower,2),'upperReturnRate',round(upper,2),
        'lowerEstimatedAmount',round(round(total*lower/100,8),0),
        'upperEstimatedAmount',round(round(total*upper/100,8),0)) ORDER BY ordinal) AS items
    FROM quantiles GROUP BY selected_id
), events AS (
    SELECT e.announced_at,e.id,jsonb_build_object(
      'id',e.id,'type',e.event_type,'title',e.title,
      'announcedAt',rtrim(rtrim(to_char(e.announced_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US'),'0'),'.')||'Z',
      'daysUntil',(e.announced_at AT TIME ZONE 'Asia/Seoul')::date-(current_timestamp AT TIME ZONE 'Asia/Seoul')::date,
      'upcoming',(e.announced_at AT TIME ZONE 'Asia/Seoul')::date>(current_timestamp AT TIME ZONE 'Asia/Seoul')::date,
      'value',jsonb_build_object('previousValue',e.previous_value,'actualValue',e.actual_value,'unit',e.value_unit,
        'direction',CASE WHEN e.previous_value IS NULL OR e.actual_value IS NULL THEN 'UNAVAILABLE'
          WHEN e.actual_value>e.previous_value THEN 'INCREASED'
          WHEN e.actual_value<e.previous_value THEN 'DECREASED' ELSE 'UNCHANGED' END),
      'source',jsonb_build_object('name',e.source_name,'url',e.source_url),
      'portfolioAnalysis',jsonb_build_object(
        'status',CASE WHEN v.asset_count IS NULL THEN 'NO_PORTFOLIO' WHEN s.ready THEN 'READY' ELSE 'INSUFFICIENT_DATA' END,
        'impactLevel',CASE WHEN s.max_median>=1 THEN 'HIGH' WHEN s.max_median>=0.50 THEN 'MEDIUM' ELSE 'LOW' END,
        'relatedAssetCount',coalesce(v.asset_count,0),'totalEvaluationAmount',coalesce(round(v.total,0),0),
        'priceBaseDate',v.price_date,'historicalReactions',coalesce(s.items,'[]'::jsonb))) AS item
    FROM selected e LEFT JOIN evaluations v ON v.selected_id=e.id LEFT JOIN statistics s ON s.selected_id=e.id
)
SELECT jsonb_build_object('year',$1::integer,'month',$2::integer,
    'events',coalesce(jsonb_agg(item ORDER BY announced_at,id),'[]'::jsonb))::text FROM events
"#;
