#!/usr/bin/env python3
"""Independent F07 real HTTP/PostgreSQL contracts, original Java V1..53 basis.

Derived from InvestmentCalendarService, InvestmentCalendarPortfolioAnalysisService,
TradingDayReactionCalculator, PortfolioReactionStatisticsCalculator, calendar DTOs,
controllers and Flyway V15/V47. No app implementation is imported or inspected.
Reserve IDs 930001..930099. The coordinator serializes all DB writers and runs the
same checker against Spring and Rust. No servers/migrations/providers start here.
Reports omit requests, cookies, tokens, SQL output and connection strings.
"""
import argparse
import base64
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from acceptance import EnvironmentFailure, require, validate_local_url
from service_acceptance import TestDatabase, equal
from service_core_acceptance import Suite, literal

MEMBER, EMPTY_MEMBER = 930001, 930002
A, B, UNPRICED = 930001, 930002, 930003
PUBLIC = '/api/investment-calendar'
MEMBER_PATH = '/api/users/me/investment-calendar'
QUERY = '?year=2090&month=6'
D = Decimal
# The three historical releases are exactly at the inclusive 15:30 Seoul close.
EVENTS = [
    (930005, 'KOREA_BASE_RATE', 'Month start', '2090-05-31T15:00:00Z', None, None, None),
    (930001, 'US_CPI', 'Calendar CPI', '2090-06-05T06:30:00Z', '3', '2', None),
    (930002, 'KOREA_BASE_RATE', 'Calendar BOK', '2090-06-06T06:30:00Z', '3.5', '3', None),
    (930003, 'CORPORATE_EARNINGS', 'Calendar A earnings', '2090-06-07T06:30:00Z', '10', None, 'CAL-A'),
    (930004, 'CORPORATE_EARNINGS', 'Calendar B earnings', '2090-06-08T06:30:00Z', '10', '10', 'CAL-B'),
    (930006, 'KOREA_BASE_RATE', 'Month end', '2090-06-30T14:59:59Z', None, None, None),
]


def insert(table, columns, rows):
    return 'INSERT INTO '+table+' ('+columns+') VALUES '+','.join('('+','.join(map(literal,row))+')' for row in rows)+';\n'


def fixture_sql():
    sql = '''DELETE FROM portfolios WHERE member_id BETWEEN 930001 AND 930099;
DELETE FROM investment_events WHERE id BETWEEN 930001 AND 930099;
DELETE FROM stock_daily_prices WHERE asset_id BETWEEN 930001 AND 930099;
'''
    for member in (MEMBER, EMPTY_MEMBER):
        sql += insert('members','id,provider,provider_id,email,nickname,role,status,created_at,updated_at',
                      [(member,'GOOGLE','calendar-'+str(member),str(member)+'@fixture.invalid','Calendar'+str(member),'USER','ACTIVE','2020-01-01T00:00:00Z','2020-01-01T00:00:00Z')]).replace(';\n'," ON CONFLICT(id) DO UPDATE SET status='ACTIVE',role='USER';\n")
    for asset, code in ((A,'CAL-A'),(B,'CAL-B'),(UNPRICED,'CAL-NOPRICE')):
        sql += insert('assets','id,name,category,asset_code,market,listed,created_at,updated_at',
                      [(asset,code,'STOCK',code,'KOSPI',True,'2020-01-01T00:00:00Z','2020-01-01T00:00:00Z')]).replace(';\n',' ON CONFLICT(id) DO UPDATE SET name=excluded.name,asset_code=excluded.asset_code;\n')
    historical = [(930011+i,'US_CPI','Historical CPI '+str(i+1),f'2089-0{i+1}-10T06:30:00Z','2','3',None) for i in range(3)]
    outside = [(930007,'KOREA_BASE_RATE','Before month','2090-05-31T14:59:59Z',None,None,None),
               (930008,'KOREA_BASE_RATE','After month','2090-06-30T15:00:00Z',None,None,None)]
    rows = [row[:6]+('%','Fixture Source','https://fixture.invalid/calendar','calendar-'+str(row[0]),row[6],'2020-01-01T00:00:00Z','2020-01-01T00:00:00Z') for row in EVENTS+historical+outside]
    sql += insert('investment_events','id,event_type,title,announced_at,previous_value,actual_value,value_unit,source_name,source_url,source_key,related_asset_code,created_at,updated_at',rows)
    prices = [(A,'2090-05-31','100'),(B,'2090-05-31','100')]
    for month in range(1,4):
        for asset, event_price in ((A,D(100+month)),(B,D(104+month))):
            prices += [(asset,f'2089-0{month}-09','100'),(asset,f'2089-0{month}-10',str(event_price)),
                       (asset,f'2089-0{month}-11',str(event_price*D('1.10')))]
    sql += insert('stock_daily_prices','asset_id,base_date,close_price,created_at,updated_at',
                  [row+('2020-01-01T00:00:00Z','2020-01-01T00:00:00Z') for row in prices])
    sql += insert('portfolios','id,member_id,created_at,updated_at',[(MEMBER,MEMBER,'2020-01-01T00:00:00Z','2020-01-01T00:00:00Z')])
    sql += insert('portfolio_holdings','id,portfolio_id,asset_id,quantity,average_purchase_price,created_at,updated_at',
                  [(930001,MEMBER,A,1,'100','2020-01-01T00:00:00Z','2020-01-01T00:00:00Z'),(930002,MEMBER,B,3,'100','2020-01-01T00:00:00Z','2020-01-01T00:00:00Z')])
    return sql


def statistics(direction, count=0, rates=None, amounts=None):
    return dict(direction=direction,sampleCount=count,medianReturnRate=None if rates is None else D(rates[0]),
                lowerReturnRate=None if rates is None else D(rates[1]),upperReturnRate=None if rates is None else D(rates[2]),
                lowerEstimatedAmount=None if amounts is None else D(amounts[0]),upperEstimatedAmount=None if amounts is None else D(amounts[1]))


def analysis(count=0,total=0,ready=None,samples=0,date='2090-05-31'):
    if not count:
        return dict(status='NO_PORTFOLIO',impactLevel='LOW',relatedAssetCount=0,totalEvaluationAmount=0,priceBaseDate=None,historicalReactions=[])
    reactions = [statistics('DECREASED'),statistics('UNCHANGED'),statistics('INCREASED',samples)]
    if ready:
        rates, amounts = ready
        reactions[2]=statistics('INCREASED',samples,rates,amounts)
    return dict(status='READY' if ready else 'INSUFFICIENT_DATA',impactLevel='HIGH' if ready else 'LOW',
                relatedAssetCount=count,totalEvaluationAmount=D(str(total)),priceBaseDate=date,historicalReactions=reactions)


def response(holdings, scope='PORTFOLIO', ready_rates=('5','5','6'), ready_amounts=('20','24'), samples=3):
    today=datetime.now(ZoneInfo('Asia/Seoul')).date()
    priced={asset:quantity for asset,quantity in holdings.items() if asset in (A,B)}
    events=[]
    for ident,kind,title,at,previous,actual,related in EVENTS:
        visible_codes={('CAL-A' if a==A else 'CAL-B' if a==B else 'CAL-NOPRICE') for a in holdings}
        if scope!='ALL' and kind=='CORPORATE_EARNINGS' and related not in visible_codes:
            continue
        relevant={asset:q for asset,q in priced.items() if kind!='CORPORATE_EARNINGS' or related==('CAL-A' if asset==A else 'CAL-B')}
        total=sum(relevant.values())*100
        impact=analysis(len(relevant),total, (ready_rates,ready_amounts) if kind=='US_CPI' and relevant and samples>=3 else None,
                        samples if kind=='US_CPI' and relevant else 0)
        date=datetime.fromisoformat(at.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul')).date()
        direction='UNAVAILABLE' if previous is None or actual is None else 'DECREASED' if D(actual)<D(previous) else 'INCREASED' if D(actual)>D(previous) else 'UNCHANGED'
        events.append(dict(id=ident,type=kind,title=title,announcedAt=at,daysUntil=(date-today).days,upcoming=date>today,
                           value=dict(previousValue=None if previous is None else D(previous),actualValue=None if actual is None else D(actual),unit='%',direction=direction),
                           source=dict(name='Fixture Source',url='https://fixture.invalid/calendar'),portfolioAnalysis=impact))
    return dict(year=2090,month=6,events=events)


class CalendarSuite(Suite):
    def client(self,member=MEMBER,token=None):
        return super().client(member,token)

    def run(self,name,fn):
        try:
            self.db.seed(fixture_sql()); fn()
            self.results.append(dict(case=name,passed=True))
        except AssertionError as error:
            self.results.append(dict(case=name,passed=False,reason=str(error)))
        except (EnvironmentFailure,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):
            self.results.append(dict(case=name,passed=False,reason='Execution/fixture dependency failed (details withheld)'))

    def calendar(self,holdings=None,scope='PORTFOLIO',member=None,expected=None,query=QUERY):
        path=(MEMBER_PATH if member is not None else PUBLIC)+query
        if scope is not None: path+='&scope='+scope
        data=None if member is not None else dict(holdings=[dict(assetId=a,quantity=q) for a,q in (holdings or {}).items()])
        return self.request(self.client(member),'GET' if member is not None else 'POST',path,200,data,expected=expected,unchanged=True)[0]

    def main(self):
        self.run('guest-empty-portfolio-exact-dto-and-month-boundaries',lambda:self.calendar({},expected=response({})))
        self.run('guest-empty-all-shows-unrelated-earnings',lambda:self.calendar({},'ALL',expected=response({},'ALL')))
        self.run('guest-ready-three-samples-current-valuation-weighted-median-percentile',lambda:self.calendar({A:1,B:3},expected=response({A:1,B:3})))
        self.run('member-ready-same-contract-as-guest',lambda:self.calendar(member=MEMBER,expected=response({A:1,B:3})))
        self.run('member-no-portfolio',lambda:self.calendar(member=EMPTY_MEMBER,expected=response({})))
        self.run('guest-one-holding-portfolio-filters-corporate',lambda:self.calendar({A:1},expected=response({A:1},ready_rates=('2','2','3'),ready_amounts=('2','3'))))
        self.run('guest-one-holding-all-unrelated-corporate-no-portfolio',lambda:self.calendar({A:1},'ALL',expected=response({A:1},'ALL',('2','2','3'),('2','3'))))
        self.run('unpriced-holding-is-no-portfolio-for-impact',lambda:self.calendar({UNPRICED:10},expected=response({UNPRICED:10})))
        self.run('unknown-asset-is-ignored',lambda:self.calendar({930099:10},expected=response({})))
        self.run('default-scope-is-portfolio',lambda:self.calendar({A:1},None,expected=response({A:1},ready_rates=('2','2','3'),ready_amounts=('2','3'))))
        self.run('member-authentication-required',lambda:self.request(self.client(None),'GET',MEMBER_PATH+QUERY,401,code='UNAUTHORIZED',unchanged=True))
        def duplicate():
            self.request(self.client(None),'POST',PUBLIC+QUERY,200,dict(holdings=[dict(assetId=A,quantity=1),dict(assetId=A,quantity=99)]),
                         expected=response({A:1},ready_rates=('2','2','3'),ready_amounts=('2','3')),unchanged=True)
        self.run('duplicate-first-quantity-wins',duplicate)
        def after_close():
            self.db.seed("UPDATE investment_events SET announced_at=announced_at+interval '1 second' WHERE id BETWEEN 930011 AND 930013;")
            self.calendar({A:1,B:3},expected=response({A:1,B:3},ready_rates=('10','10','10'),ready_amounts=('40','40')))
        self.run('after-1530-uses-next-trading-price',after_close)
        def gaps():
            self.db.seed("DELETE FROM stock_daily_prices WHERE asset_id IN(930001,930002) AND base_date IN('2089-01-10','2089-02-10','2089-03-10');")
            self.calendar({A:1,B:3},expected=response({A:1,B:3},ready_rates=('15.5','15.5','16.6'),ready_amounts=('62','66')))
        self.run('missing-release-day-selects-next-stored-trading-day',gaps)
        def insufficient():
            self.db.seed('DELETE FROM investment_events WHERE id=930013;')
            self.calendar({A:1,B:3},expected=response({A:1,B:3},samples=2))
        self.run('two-samples-return-null-statistics-insufficient-data',insufficient)
        # A .5 valuation must round HALF_UP to 101 rather than truncate to 100.
        def rounding_case():
            self.db.seed("UPDATE stock_daily_prices SET close_price=100.5 WHERE asset_id=930001 AND base_date='2090-05-31';")
            expected=response({A:1},ready_rates=('2','2','3'),ready_amounts=('2','3'))
            for event in expected['events']:
                if event['portfolioAnalysis']['relatedAssetCount']: event['portfolioAnalysis']['totalEvaluationAmount']=101
            self.calendar({A:1},expected=expected)
        self.run('valuation-half-up-rounding',rounding_case)
        for year,month in ((2000,1),(2100,12),(2090,2)):
            self.run('empty-month-'+str(year)+'-'+str(month),lambda year=year,month=month:self.calendar({},query=f'?year={year}&month={month}',expected=dict(year=year,month=month,events=[])))
        for mode in ('missing','mismatch','header-only','cookie-only'):
            def csrf_case(mode=mode):
                c=self.client(None)
                if mode in ('missing','header-only'): c.cookies.pop('XSRF-TOKEN',None)
                headers={c.csrf[0]:'mismatch'} if mode=='mismatch' else None
                self.request(c,'POST',PUBLIC+QUERY,403,dict(holdings=[]),code='FORBIDDEN',unchanged=True,csrf=mode in ('mismatch','header-only'),headers=headers)
            self.run('csrf-'+mode,csrf_case)
        for name,body,field,reason in [
            ('null-holdings',dict(holdings=None),'holdings','보유자산 목록을 입력해주세요.'),
            ('missing-holdings',{},'holdings','보유자산 목록을 입력해주세요.'),
            ('null-element',dict(holdings=[None]),None,None),
            ('zero-asset',dict(holdings=[dict(assetId=0,quantity=1)]),'holdings[0].assetId','종목 ID는 1 이상이어야 합니다.'),
            ('negative-quantity',dict(holdings=[dict(assetId=A,quantity=-1)]),'holdings[0].quantity','보유 수량은 1 이상이어야 합니다.'),
            ('null-quantity',dict(holdings=[dict(assetId=A,quantity=None)]),'holdings[0].quantity','보유 수량을 입력해주세요.'),
            ('51-holdings',dict(holdings=[dict(assetId=A,quantity=1)]*51),'holdings','보유자산은 최대 50개까지 조회할 수 있습니다.')]:
            self.run('validation-'+name,lambda body=body,field=field,reason=reason:self.invalid(self.client(None),'POST',PUBLIC+QUERY,body,field,reason))
        for name,query,field in [('year-low','?year=1999&month=6','year'),('year-high','?year=2101&month=6','year'),('month-low','?year=2090&month=0','month'),('month-high','?year=2090&month=13','month'),('year-type','?year=abc&month=6','year'),('scope','?year=2090&month=6&scope=INVALID','scope')]:
            self.run('query-'+name,lambda query=query,field=field:self.invalid(self.client(None),'POST',PUBLIC+query,dict(holdings=[]),field))
        def fifty():
            self.request(self.client(None),'POST',PUBLIC+QUERY,200,dict(holdings=[dict(assetId=A,quantity=1)]*50),expected=response({A:1},ready_rates=('2','2','3'),ready_amounts=('2','3')),unchanged=True)
        self.run('50-duplicate-holdings-accepted',fifty)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--jwt-secret-file',required=True,type=Path)
    parser.add_argument('--issuer',default='daynomy')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    report=dict(contract='Independent F07 original Java DTO/service/calculator contract',results=[],passed=0,failed=0,
                environmentLimited=[dict(case='calendar-collection-external-providers',status='unverified',reason='Stored-event query and analysis only; external collection not exercised')])
    try:
        base=validate_local_url(args.base_url)
        key=base64.b64decode(args.jwt_secret_file.read_bytes().strip(),validate=True)
        require(len(key)>=32,'JWT fixture key must contain at least 32 bytes')
        suite=CalendarSuite(base,TestDatabase(args.database),key,args.issuer)
        suite.main(); report['results']=suite.results
    except (AssertionError,EnvironmentFailure,OSError,ValueError,subprocess.TimeoutExpired):
        report['results'].append(dict(case='fixture-environment',passed=False,reason='Dedicated local environment setup failed (details withheld)'))
    report['passed']=sum(row['passed'] for row in report['results']); report['failed']=len(report['results'])-report['passed']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],failed=report['failed'])))
    return int(report['failed']>0)


if __name__=='__main__': sys.exit(main())
