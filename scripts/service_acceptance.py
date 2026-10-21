#!/usr/bin/env python3
"""Independent F03/F04/F08/F09/F10 HTTP + real PostgreSQL acceptance cases.

Expectations come from original Java DTOs/services/repositories and Flyway V1..53,
not the Rust implementation. Only a loopback database named *_service_test is
accepted. The controller must serialize this checker with other DB writers.
Fixture IDs 910001..910099 are reserved here; fixtures remain for inspection.
No server, migration, external provider or production database is started here.
"""
import argparse
from datetime import datetime, time, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

from acceptance import Client, Database, EnvironmentFailure, require, validate_local_url

FIRST = 910001
INVALID = "요청값이 올바르지 않습니다."


def equal(actual, expected, path="body"):
    """Exact object fields, array order, JSON types and decimal numeric value.

    ISO Instant strings are compared as instants (Z and +00:00 are equivalent).
    Assertion messages name fields only: response values never reach reports.
    """
    if isinstance(expected, dict):
        require(isinstance(actual, dict), path + ": expected object")
        require(actual.keys() == expected.keys(), path + ": field set differs")
        for key in expected:
            equal(actual[key], expected[key], path + "." + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list), path + ": expected array")
        require(len(actual) == len(expected), path + ": array length differs")
        for index, (left, right) in enumerate(zip(actual, expected)):
            equal(left, right, path + "[" + str(index) + "]")
    elif isinstance(expected, (int, Decimal)) and not isinstance(expected, bool):
        require(isinstance(actual, (int, Decimal)) and not isinstance(actual, bool),
                path + ": expected JSON number")
        require(actual == expected, path + ": numeric value differs")
    elif isinstance(expected, str) and "T" in expected and expected.endswith("Z"):
        try:
            require(isinstance(actual, str), path + ": expected instant string")
            left = datetime.fromisoformat(actual.replace("Z", "+00:00"))
            right = datetime.fromisoformat(expected.replace("Z", "+00:00"))
            require(left == right, path + ": instant differs")
        except ValueError:
            raise AssertionError(path + ": invalid instant") from None
    else:
        require(type(actual) is type(expected) and actual == expected, path + ": value/type differs")


class TestDatabase(Database):
    __test__ = False

    def __init__(self, url):
        endpoint = urlsplit(validate_local_url(url, database=True))
        require(endpoint.path.endswith("_service_test"), "Dedicated *_service_test DB required")
        super().__init__(url)
        require(self.query("SELECT to_json(current_database())") == self.env["PGDATABASE"],
                "Connected database name mismatch")

    def query(self, sql):
        # PostgreSQL NUMERIC arrives as JSON numbers. Keep its decimal text exact
        # before equal() checks it; converting an already parsed float is too late.
        try:
            result = subprocess.run(
                ["psql", "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1"],
                input=sql, text=True, capture_output=True, env=self.env, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise EnvironmentFailure("Database command unavailable/timed out") from None
        if result.returncode:
            raise EnvironmentFailure("Read-only test DB query failed (details withheld)")
        try:
            return json.loads(result.stdout, parse_float=Decimal)
        except json.JSONDecodeError:
            raise EnvironmentFailure("Unexpected DB result format") from None

    def seed(self, sql):
        env = self.env.copy()
        env["PGOPTIONS"] = "-c statement_timeout=10000"
        result = subprocess.run(
            ["psql", "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1"],
            input="BEGIN;\n" + sql + "\nCOMMIT;", env=env, text=True,
            capture_output=True, timeout=20,
        )
        if result.returncode:
            raise EnvironmentFailure("Fixture transaction failed (SQL output withheld)")

    def snapshot(self):
        tables = self.query("SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]'::json) "
                            "FROM pg_tables WHERE schemaname='public'")
        # All public tables, including member/ledger tables, must stay unchanged.
        parts = []
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            name = "'" + table.replace("'", "''") + "'"
            parts.append("SELECT " + name + " AS name, md5(coalesce(string_agg(row_data, E'\\n' "
                         "ORDER BY row_data),'')) AS digest FROM (SELECT row_to_json(t)::text "
                         "AS row_data FROM public." + quoted + " t) s")
        rows = self.query("SELECT coalesce(json_agg(t ORDER BY name),'[]'::json) FROM (" +
                          " UNION ALL ".join(parts) + ") t") if parts else []
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def fixture_sql(today):
    # Dates are pinned before all requests. Today uses explicitly configured
    # Java/system-equivalent timezone; noon avoids incidental midnight ambiguity.
    # Run with server TZ matching --timezone. No naive UTC/Seoul conversion.
    t = today.isoformat().replace("+00:00", "Z")
    old = "2020-01-02T03:04:05Z"
    assets = [
        (910001, "Harness Alpha", "STOCK", "HARNESS", "KOSPI", True),
        (910002, "Harness Beta", "ETF", "HARNESS2", "KOSDAQ", True),
        (910003, "Harness America", "STOCK", "HARNESSUS", "NASDAQ", True),
        (910004, "Harness Delisted", "STOCK", "HARNESSOLD", "KOSPI", False),
        (910005, "Harness No Price", "STOCK", "HARNESSNONE", "KOSPI", True),
        (910006, "Harness 100% literal", "ETF", "HARNESSPC", "KOSPI", True),
        (910007, "Harness Mixed", "STOCK", "HARNESSMIX", "KOSPI", True),
    ]
    def literal(v):
        if v is None: return "NULL"
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, int): return str(v)
        return "'" + v.replace("'", "''") + "'"
    def insert(table, columns, rows):
        return "INSERT INTO " + table + " (" + columns + ") VALUES\n" + ",\n".join(
            "(" + ",".join(literal(v) for v in row) + ")" for row in rows) + ";\n"
    sql = """
DELETE FROM news_keyword WHERE news_id BETWEEN 910001 AND 910099;
DELETE FROM news_market_analysis WHERE news_id BETWEEN 910001 AND 910099;
DELETE FROM stock_related_contents WHERE id BETWEEN 910001 AND 910099;
DELETE FROM featured_person_posts WHERE id BETWEEN 910001 AND 910099;
DELETE FROM featured_people WHERE id BETWEEN 910001 AND 910099;
DELETE FROM stock_daily_prices WHERE asset_id BETWEEN 910001 AND 910099;
DELETE FROM news WHERE id BETWEEN 910001 AND 910099;
DELETE FROM assets WHERE id BETWEEN 910001 AND 910099;
"""
    sql += insert("assets", "id,name,category,asset_code,market,listed,created_at,updated_at",
                  [a + (old, old) for a in assets])
    price_rows = [(910001, "2020-01-03", "120.25"), (910001, "2020-01-02", "100.00"),
                  (910002, "2020-01-03", "20.35"), (910002, "2020-01-02", "20.00"),
                  (910003, "2020-01-03", "10.1234"),
                  (910004, "2020-01-03", "5.00"),
                  (910007, "2020-01-02", "10.00")]
    sql += insert("stock_daily_prices", "asset_id,base_date,close_price,created_at,updated_at",
                  [row + (old, old) for row in price_rows])
    news_rows = [
        (910001, "Harness alpha rates", "Harness body", "STOCK", "PUBLISHED", t),
        (910002, "Harness beta", "Harness alpha rates body", "ETF", "PUBLISHED", t),
        (910003, "Harness older alpha", "Harness rates body", "STOCK", "PUBLISHED", old),
        (910004, "Harness secret alpha rates", "Harness hidden", "STOCK", "DRAFT", t),
        (910005, "Harness rejected alpha rates", "Harness hidden", "STOCK", "REJECTED", t),
    ]
    sql += insert("news", "id,title,content,category,status,published_at,image_url,sources,image_source,created_at,updated_at",
                  [row + ("https://example.test/image.png", '[{"name":"Fixture","url":"https://example.test/source"}]',
                           '{"name":"Fixture Image","url":"https://example.test/image-source","author":"Fixture Author","license":"CC0","licenseUrl":"https://example.test/license","type":"WIKIMEDIA"}', old, old)
                   for row in news_rows])
    sql += insert("news_keyword", "id,news_id,category,keyword,point1,point2,point3,created_at,updated_at",
                  [(910001,910001,"POLICY","Harness rate","definition","context","watch",old,old),
                   (910002,910004,"TERM","Hidden","hidden","hidden","hidden",old,old)])
    sql += insert("news_market_analysis", "id,news_id,summary,risk,watch_point,created_at,updated_at",
                  [(910001,910001,"legacy","Fixture risk","Fixture watch",old,old),
                   (910002,910004,"legacy","Hidden","Hidden",old,old),
                   (910003,910003,"legacy"," ","Blank risk",old,old)])
    sql += insert("featured_people", "id,name,x_profile_url,created_at,updated_at",
                  [(910001,"Harness Person","https://x.com/harness",old,old),
                   (910002,"Harness Empty",None,t,t)])
    sql += insert("featured_person_posts", "id,person_id,source_type,title,url,published_at,status,created_at,updated_at",
                  [(910001,910001,"X","Harness approved","https://x.com/harness/status/123",old,"APPROVED",old,old),
                   (910002,910001,"THREADS","Harness pending","https://threads.com/@harness/post/a",t,"PENDING",t,t),
                   (910003,910001,"X","Harness rejected","https://x.com/harness/status/124",t,"REJECTED",t,t),
                   (910004,910001,"YOUTUBE","Harness no original date","https://youtu.be/abcdefghijk",None,"APPROVED",t,t)])
    sql += insert("stock_related_contents", "id,asset_id,source_type,title,url,news_id,image_url,published_date,created_at,updated_at",
                  [(910001,910001,"YOUTUBE","Harness external video","https://youtu.be/zzzzzzzzzzz",None,None,"2020-01-02",old,old),
                   (910002,910001,"INTERNAL_NEWS","Harness internal","/news/910001",910001,None,"2020-01-02",old,old),
                   (910003,910001,"INTERNAL_NEWS","Harness draft internal","/news/910004",910004,None,"2020-01-02",old,old),
                   (910004,910002,"X","Harness duplicate person","https://twitter.com/harness/status/123?tracking=a",None,None,"2020-01-02",t,t),
                   (910005,910002,"YOUTUBE","Harness duplicate video","https://www.youtube.com/watch?v=zzzzzzzzzzz",None,None,"2020-01-02",old,old)])
    return sql, t, old


def page(items, current=1, size=15, total=None, kind="normal"):
    total = len(items) if total is None else total
    result = {"items" if kind != "news_search" else "content": items,
              "page": current, "size": size, "totalPages": (total + size - 1) // size,
              "totalElements": total}
    if kind == "normal": result["hasNext"] = current * size < total
    return result


def cases(t, old):
    result = []
    def add(name, path, expected=None, *, status=200, data=None, check=None, csrf=True):
        result.append(dict(name=name, path=path, expected=expected, status=status,
                           data=data, check=check, csrf=csrf))
    def business(code, message): return {"code":code,"message":message}
    def invalid(value):
        require(isinstance(value,dict), "Validation must be an object")
        require(value.get("code") == "INVALID_REQUEST" and value.get("message") == INVALID,
                "Validation error contract differs")
        require(isinstance(value.get("errors"),list) and bool(value["errors"]),
                "Validation error fields missing")
        for entry in value["errors"]:
            require(isinstance(entry,dict) and set(entry)=={"field","reason"} and
                    all(isinstance(v,str) and bool(v) for v in entry.values()),
                    "Validation field/reason malformed")
    def stock(i,name,code,category="STOCK",market="KOSPI",currency="KRW"):
        return dict(assetId=i,name=name,assetCode=code,category=category,market=market,currency=currency)
    add("stock-exact-code-priority", "/api/stocks?q=HARNESS", {"stocks":[
        stock(910001,"Harness Alpha","HARNESS"),
        stock(910006,"Harness 100% literal","HARNESSPC","ETF"),
        stock(910002,"Harness Beta","HARNESS2","ETF","KOSDAQ"),
        stock(910007,"Harness Mixed","HARNESSMIX"),
        stock(910005,"Harness No Price","HARNESSNONE")]})
    add("stock-us-only","/api/stocks?q=harness&country=US",{"stocks":[
        stock(910003,"Harness America","HARNESSUS",market="NASDAQ",currency="USD")]})
    add("stock-empty","/api/stocks?q=NONEXISTENT987654",{"stocks":[]})
    add("stock-percent-is-literal","/api/stocks?q="+quote("Harness 100%"),{"stocks":[
        stock(910006,"Harness 100% literal","HARNESSPC","ETF")]})
    for suffix in ("", "?q=", "?q=%20%20", "?q=%25%21", "?q="+"a"*51, "?q=harness&country=CN"):
        add("stock-validation-"+str(len(result)),"/api/stocks"+suffix,status=400,check=invalid)
    for i, name, code, price, curr in [(910001,"Harness Alpha","HARNESS","120.25","KRW"),
                                      (910003,"Harness America","HARNESSUS","10.1234","USD"),
                                      (910004,"Harness Delisted","HARNESSOLD","5","KRW")]:
        add("price-"+str(i),f"/api/stocks/{i}/price",dict(assetId=i,assetCode=code,name=name,
            baseDate="2020-01-03",closePrice=Decimal(price),currency=curr))
    for val in ("910005","919999","0","-1"):
        add("price-missing-"+val,f"/api/stocks/{val}/price",
            business("STOCK_PRICE_NOT_FOUND","주식·ETF 종가를 찾을 수 없습니다."),status=404)
    for val in ("abc","1.5","9223372036854775808"):
        add("price-invalid-"+val,f"/api/stocks/{val}/price",status=400,check=invalid)
    def news(i,title,category,when):
        return dict(id=i,title=title,imageUrl="https://example.test/image.png",category=category,publishedAt=when)
    n1=news(910001,"Harness alpha rates","STOCK",t)
    n2=news(910002,"Harness beta","ETF",t)
    n3=news(910003,"Harness older alpha","STOCK",old)
    add("news-published-order","/api/news",page([n2,n1,n3]))
    add("news-page-boundary","/api/news?page=2&size=2",page([n3],current=2,size=2,total=3))
    add("news-empty-page","/api/news?page=3&size=2",page([],current=3,size=2,total=3))
    add("news-category","/api/news?category=STOCK",page([n1,n3]))
    add("news-today-timezone","/api/news/today",page([n2,n1],size=9))
    detail=dict(n1,content="Harness body",imageSource={"name":"Fixture Image","url":"https://example.test/image-source",
                "author":"Fixture Author","license":"CC0","licenseUrl":"https://example.test/license","type":"WIKIMEDIA"},
                sources=[{"name":"Fixture","url":"https://example.test/source"}])
    add("news-detail","/api/news/910001",detail)
    for val in (910004,910005,919999):
        add("news-hidden-"+str(val),f"/api/news/{val}",business("NEWS_NOT_FOUND","해당 뉴스를 찾을 수 없습니다."),status=404)
    for suffix in ("?page=0","?size=0","?size=101","?category=INVALID"):
        add("news-validation-"+suffix,"/api/news"+suffix,status=400,check=invalid)
    keyword=dict(category="POLICY",keyword="Harness rate",points=["definition","context","watch"],
                 definition="definition",context="context",watchPoint="watch")
    add("keywords-fields","/api/news/910001/keywords",{"keywords":[keyword]})
    add("keywords-empty","/api/news/910002/keywords",{"keywords":[]})
    add("keywords-hidden","/api/news/910004/keywords",business("NEWS_NOT_FOUND","해당 뉴스를 찾을 수 없습니다."),status=404)
    add("market-fields","/api/news/910001/market-analysis",{"risk":"Fixture risk","watchPoint":"Fixture watch"})
    for val in (910002,910003,910004,919999):
        add("market-unavailable-"+str(val),f"/api/news/{val}/market-analysis",
            business("MARKET_ANALYSIS_NOT_FOUND","해당 뉴스의 시장 분석을 찾을 수 없습니다."),status=404)
    add("news-search-normalized-and","/api/search/news?q="+quote(" ALPHA  rates alpha "),
        page([n2,n1,n3],size=20,kind="news_search"))
    add("news-search-relevance","/api/search/news?q=alpha%20rates&sort=RELEVANCE",
        page([n1,n3,n2],size=20,kind="news_search"))
    add("news-search-category","/api/search/news?q=harness&category=ETF",page([n2],size=20,kind="news_search"))
    add("news-search-percent-literal","/api/search/news?q=Harness%25",page([],size=20,kind="news_search"))
    for suffix in ("", "?q=", "?q=%25%21", "?q="+"a"*101,"?q=harness&page=0",
                   "?q=harness&size=101", "?q=harness&sort=UNKNOWN"):
        add("search-validation-"+str(len(result)),"/api/search/news"+suffix,status=400,check=invalid)
    def content(i,a,source,title,url,date=old,pub="2020-01-02",image=None):
        return dict(id=i,assetId=a,sourceType=source,title=title,url=url,imageUrl=image,createdAt=date,publishedDate=pub)
    c1=content(910001,910001,"YOUTUBE","Harness external video","https://youtu.be/zzzzzzzzzzz")
    c2=content(910002,910001,"INTERNAL_NEWS","Harness internal","/news/910001",image="https://example.test/image.png")
    c4=content(910004,910002,"X","Harness duplicate person","https://twitter.com/harness/status/123?tracking=a",date=t)
    c5=content(910005,910002,"YOUTUBE","Harness duplicate video","https://www.youtube.com/watch?v=zzzzzzzzzzz")
    add("public-contents-external-only","/api/contents",page([c4,c5,c1],size=12))
    add("asset-contents-hidden-excluded","/api/assets/910001/contents",
        dict(assetId=910001,assetCode="HARNESS",assetName="Harness Alpha",contents=[c2,c1]))
    add("asset-contents-empty","/api/assets/910005/contents",
        dict(assetId=910005,assetCode="HARNESSNONE",assetName="Harness No Price",contents=[]))
    add("asset-contents-missing","/api/assets/919999/contents",business("ASSET_NOT_FOUND","자산을 찾을 수 없습니다."),status=404)
    for path in ("/api/assets/0/contents","/api/contents?page=0","/api/contents?size=101"):
        add("contents-validation-"+str(len(result)),path,status=400,check=invalid)
    p1=dict(id=910001,sourceType="X",title="Harness approved",url="https://x.com/harness/status/123",publishedAt=old,createdAt=old)
    p4=dict(id=910004,sourceType="YOUTUBE",title="Harness no original date",url="https://youtu.be/abcdefghijk",publishedAt=None,createdAt=t)
    add("people-only-approved-date-order","/api/people",{"people":[
        dict(id=910001,name="Harness Person",xProfileUrl="https://x.com/harness",threadsProfileUrl=None,
             youtubeProfileUrl=None,profileImageUrl=None,createdAt=old,posts=[p1,p4]),
        dict(id=910002,name="Harness Empty",xProfileUrl=None,threadsProfileUrl=None,
             youtubeProfileUrl=None,profileImageUrl=None,createdAt=t,posts=[])]})
    def search_item(kind,i,source,title,when,**extra):
        item=dict(kind=kind,id=i,source=source,title=title,date=when,url=None,personId=None,
                  personName=None,assetId=None,imageUrl=None,category=None,publishedDate=None)
        return dict(item,**extra)
    s1=search_item("NEWS",910001,"DAYNOMY",n1["title"],t,imageUrl=n1["imageUrl"],category="STOCK")
    s2=search_item("NEWS",910002,"DAYNOMY",n2["title"],t,imageUrl=n2["imageUrl"],category="ETF")
    s3=search_item("NEWS",910003,"DAYNOMY",n3["title"],old,imageUrl=n3["imageUrl"],category="STOCK")
    sp1=search_item("PERSON_POST",910001,"X",p1["title"],old,url=p1["url"],personId=910001,personName="Harness Person")
    sp4=search_item("PERSON_POST",910004,"YOUTUBE",p4["title"],t,url=p4["url"],personId=910001,personName="Harness Person")
    sc5=search_item("ASSET_CONTENT",910005,"YOUTUBE",c5["title"],old,url=c5["url"],assetId=910002,publishedDate="2020-01-02")
    add("content-search-cross-source-dedup","/api/search/contents?q=harness",
        page([s1,s2,sp4,sc5,s3,sp1],size=12,kind="content_search"))
    add("content-search-source-filter","/api/search/contents?q=harness&source=X",page([sp1],size=12,kind="content_search"))
    add("content-search-page","/api/search/contents?q=harness&page=2&size=2",
        page([sp4,sc5],current=2,size=2,total=6,kind="content_search"))
    for suffix in ("", "?q=%25%21", "?q=harness&source=UNKNOWN","?q=harness&size=0"):
        add("content-search-validation-"+str(len(result)),"/api/search/contents"+suffix,status=400,check=invalid)
    def holding(i,q=2,price="100.00"):
        return dict(assetId=i,quantity=q,averagePurchasePrice=price)
    request_body={"holdings":[holding(910001)]}
    def calculation(expected):
        def check(value):
            require(isinstance(value,dict),"Calculation must be an object")
            require(set(value)=={"baseDate","pricingStatus","pricedHoldingCount","unpricedHoldingCount",
                "totalPurchaseAmount","totalEvaluationAmount","dailyProfitLoss","dailyReturnRate",
                "totalProfitLoss","totalReturnRate","holdings","marketAllocations"},"Calculation field set differs")
            for key,val in expected.items(): equal(value.get(key),val,"body."+key)
        return check
    h=dict(assetId=910001,assetCode="HARNESS",name="Harness Alpha",category="STOCK",market="KOSPI",
           priceAvailable=True,baseDate="2020-01-03",quantity=2,averagePurchasePrice=Decimal("100"),
           closePrice=Decimal("120.25"),purchaseAmount=Decimal("200"),evaluationAmount=Decimal("240.50"),
           profitLoss=Decimal("40.50"),returnRate=Decimal("20.25"),weight=Decimal("100"),
           currency="KRW",evaluationCurrency="KRW",averagePurchasePriceCurrency="KRW")
    add("calculate-complete-exact","/api/portfolio/calculate",data=request_body,expected=dict(
        baseDate="2020-01-03",pricingStatus="COMPLETE",pricedHoldingCount=1,unpricedHoldingCount=0,
        totalPurchaseAmount=Decimal("200"),totalEvaluationAmount=Decimal("240.50"),
        dailyProfitLoss=Decimal("40.50"),dailyReturnRate=Decimal("20.25"),totalProfitLoss=Decimal("40.50"),
        totalReturnRate=Decimal("20.25"),holdings=[h],marketAllocations=[dict(market="KOSPI",evaluationAmount=Decimal("240.50"),weight=Decimal("100"))]))
    add("calculate-partial-nulls","/api/portfolio/calculate",data={"holdings":[holding(910001),holding(910005)]},
        check=calculation(dict(baseDate="2020-01-03",pricingStatus="PARTIAL",pricedHoldingCount=1,
            unpricedHoldingCount=1,totalPurchaseAmount=Decimal("400"),totalEvaluationAmount=Decimal("240.50"),
            dailyProfitLoss=None,dailyReturnRate=None,totalProfitLoss=None,totalReturnRate=None)))
    add("calculate-mixed-dates","/api/portfolio/calculate",data={"holdings":[holding(910001),holding(910007)]},
        check=calculation(dict(baseDate="2020-01-02",pricingStatus="MIXED_DATES",pricedHoldingCount=2,
            unpricedHoldingCount=0,totalEvaluationAmount=Decimal("260.50"),dailyProfitLoss=None,dailyReturnRate=None)))
    add("calculate-no-price","/api/portfolio/calculate",data={"holdings":[holding(910005)]},
        check=calculation(dict(baseDate=None,pricingStatus="PARTIAL",pricedHoldingCount=0,unpricedHoldingCount=1,
            totalPurchaseAmount=Decimal("200"),totalEvaluationAmount=Decimal("0"),totalProfitLoss=None,marketAllocations=[])))
    add("calculate-large-integer-precision","/api/portfolio/calculate",
        data={"holdings":[holding(910001,q=9007199254740993,price="0.01")]},
        check=calculation(dict(totalPurchaseAmount=Decimal("90071992547409.93"),
                              totalEvaluationAmount=Decimal("1083115710382604408.25"))))
    add("calculate-duplicate","/api/portfolio/calculate",data={"holdings":[holding(910001),holding(910001)]},status=400,
        expected=business("DUPLICATE_PORTFOLIO_ASSET","포트폴리오에 중복된 종목이 있습니다."))
    add("calculate-missing-asset","/api/portfolio/calculate",data={"holdings":[holding(919999)]},status=404,
        expected=business("ASSET_NOT_FOUND","자산을 찾을 수 없습니다."))
    for body in ({"holdings":[]},{"holdings":[None]},{"holdings":[holding(0)]},
                 {"holdings":[holding(910001,q=0)]},{"holdings":[holding(910001,price="0")]},
                 {"holdings":[holding(910001,price="0.001")]},{"holdings":[holding(910001)]*51}):
        add("calculate-validation-"+str(len(result)),"/api/portfolio/calculate",data=body,status=400,check=invalid)
    add("calculate-csrf-required","/api/portfolio/calculate",data=request_body,status=403,csrf=False)
    return result


def execute_case(case, client, db, csrf):
    before=db.snapshot()
    headers={}
    if case["data"] is not None:
        headers["Content-Type"]="application/json"
        if case["csrf"]:
            require(csrf is not None,"CSRF setup failed; protected POST cannot be verified")
            headers[csrf[0]]=csrf[1]
    payload=None if case["data"] is None else json.dumps(case["data"]).encode()
    status,headers,raw=client.send(case["path"],data=payload,headers=headers)
    after=db.snapshot()
    require(before==after,"Public request unexpectedly changed persistent DB state")
    require(status==case["status"],"HTTP status differs")
    if case["expected"] is not None or case["check"] is not None:
        require("application/json" in headers.get("Content-Type",""),"Expected JSON media type")
        require(len(raw)<=65536,"Response exceeds checker limit")
        try: value=json.loads(raw,parse_float=Decimal)
        except (ValueError,UnicodeError): raise AssertionError("Invalid response JSON") from None
        if case["expected"] is not None: equal(value,case["expected"])
        if case["check"] is not None: case["check"](value)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",required=True)
    parser.add_argument("--database",required=True,help="Loopback postgres URL, *_service_test DB")
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--timezone",default="Asia/Seoul",help="Must match HTTP server system timezone")
    args=parser.parse_args(argv)
    report={"contract":"F03/F04/F08/F09/F10 independent original-code cases","results":[],
            "passed":0,"failed":0,"environmentFailures":0,"fixtureTimezone":args.timezone}
    def record(name,passed,reason=None):
        row={"case":name,"passed":passed}
        if reason: row["reason"]=reason
        report["results"].append(row)
        report["passed" if passed else "failed"]+=1
    try:
        base=validate_local_url(args.base_url)
        db=TestDatabase(args.database)
        zone=ZoneInfo(args.timezone)
        today=datetime.combine(datetime.now(zone).date(),time(12),zone).astimezone(timezone.utc)
        sql,t,old=fixture_sql(today)
        db.seed(sql)
        client=Client(base)
        csrf=None
        try:
            csrf=client.csrf()
            record("csrf-setup",True)
        except (AssertionError,EnvironmentFailure,ValueError):
            record("csrf-setup",False,"CSRF endpoint/cookie/token contract failed")
        for case in cases(t,old):
            try:
                execute_case(case,client,db,csrf)
                record(case["name"],True)
            except AssertionError as exc:
                record(case["name"],False,str(exc))
            except (EnvironmentFailure,OSError,subprocess.TimeoutExpired):
                report["environmentFailures"]+=1
                record(case["name"],False,"HTTP/DB execution unavailable (details withheld)")
    except (EnvironmentFailure,AssertionError,OSError,ValueError,subprocess.TimeoutExpired):
        report["environmentFailures"]+=1
        record("fixture-environment",False,"Dedicated local test setup failed (details withheld)")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("passed","failed","environmentFailures")}))
    return 0 if report["failed"]==0 else 1


if __name__=="__main__":
    sys.exit(main())
