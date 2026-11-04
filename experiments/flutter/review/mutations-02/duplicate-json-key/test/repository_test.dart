import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';
import 'support/fakes.dart';

class RouteCase {
  const RouteCase(this.op,this.method,this.path,this.response,{this.params=const {},this.query=const {},this.write=false,this.noContent=false});
  final UserOperation op;
  final String method,path,response;
  final Map<String,String> params,query;
  final bool write,noContent;
}

const routes = <RouteCase>[
  RouteCase(UserOperation.stocks,'GET','/api/stocks',stockBody,params:{'q':'삼성 & ETF','country':'KR'},query:{'q':'삼성 & ETF'}),
  RouteCase(UserOperation.price,'GET','/api/stocks/1/price',priceBody,params:{'assetId':'1'}),
  RouteCase(UserOperation.exchangeRate,'GET','/api/exchange-rates/usd-krw','{"baseDate":"2026-10-28","rate":1380.1250}',params:{'date':'2026-10-28'},query:{'date':'2026-10-28'}),
  RouteCase(UserOperation.assetContents,'GET','/api/assets/1/contents','{"assetId":1,"assetCode":"005930","assetName":"삼성전자","contents":[]}',params:{'assetId':'1'}),
  RouteCase(UserOperation.calculate,'POST','/api/portfolio/calculate',calculationBody,write:true),
  RouteCase(UserOperation.guestAnalysis,'POST','/api/portfolio/analysis',emptyAnalysisBody,write:true),
  RouteCase(UserOperation.portfolio,'GET','/api/users/me/portfolio',savedPortfolioBody),
  RouteCase(UserOperation.createTransaction,'POST','/api/portfolio/transactions',transactionBody,write:true),
  RouteCase(UserOperation.updateTransaction,'PATCH','/api/portfolio/transactions/11',transactionBody,params:{'transactionId':'11'},write:true),
  RouteCase(UserOperation.deleteTransaction,'DELETE','/api/portfolio/transactions/11',transactionBody,params:{'transactionId':'11'},write:true),
  RouteCase(UserOperation.updateHolding,'PATCH','/api/users/me/portfolio/holdings/1',holdingBody,params:{'assetId':'1'},write:true),
  RouteCase(UserOperation.deleteHolding,'DELETE','/api/users/me/portfolio/holdings/1','',params:{'assetId':'1'},write:true,noContent:true),
  RouteCase(UserOperation.performance,'GET','/api/users/me/portfolio/performance',performanceBody,params:{'from':'2026-10-01','to':'2026-10-28'},query:{'from':'2026-10-01','to':'2026-10-28'}),
  RouteCase(UserOperation.histories,'GET','/api/portfolio/histories','[]',params:{'from':'2026-10-01','to':'2026-10-28'},query:{'from':'2026-10-01','to':'2026-10-28'}),
  RouteCase(UserOperation.savedAnalysis,'GET','/api/users/me/portfolio/analysis',savedAnalysisBody),
  RouteCase(UserOperation.generateAnalysis,'POST','/api/users/me/portfolio/analysis',savedAnalysisBody,write:true),
  RouteCase(UserOperation.refreshAnalysis,'POST','/api/users/me/portfolio/analysis/refresh',savedAnalysisBody,write:true),
  RouteCase(UserOperation.analysisHistory,'GET','/api/users/me/portfolio/analysis/history','[]'),
  RouteCase(UserOperation.news,'GET','/api/news',newsPageBody,params:{'page':'1','size':'6','category':'ECONOMY'},query:{'page':'1','size':'6','category':'ECONOMY'}),
  RouteCase(UserOperation.todayNews,'GET','/api/news/today',newsPageBody),
  RouteCase(UserOperation.newsDetail,'GET','/api/news/3',newsDetailBody,params:{'newsId':'3'}),
  RouteCase(UserOperation.newsKeywords,'GET','/api/news/3/keywords','{"keywords":[]}',params:{'newsId':'3'}),
  RouteCase(UserOperation.newsMarketAnalysis,'GET','/api/news/3/market-analysis','{"risk":"변동성","watchPoint":"금리"}',params:{'newsId':'3'}),
  RouteCase(UserOperation.searchNews,'GET','/api/search/news','{"content":[],"page":1,"size":20,"totalElements":0,"totalPages":0}',params:{'q':'금리 & 미국','page':'1','size':'20','sort':'RELEVANCE'},query:{'q':'금리 & 미국','page':'1','size':'20','sort':'RELEVANCE'}),
  RouteCase(UserOperation.searchContents,'GET','/api/search/contents',contentsBody,params:{'q':'금리','page':'1','size':'12','source':'X'},query:{'q':'금리','page':'1','size':'12','source':'X'}),
  RouteCase(UserOperation.contents,'GET','/api/contents',contentsBody,params:{'page':'1','size':'12'},query:{'page':'1','size':'12'}),
  RouteCase(UserOperation.people,'GET','/api/people','{"people":[]}'),
  RouteCase(UserOperation.guestCalendar,'POST','/api/investment-calendar',calendarBody,params:{'year':'2026','month':'10','scope':'ALL'},query:{'year':'2026','month':'10','scope':'ALL'},write:true),
  RouteCase(UserOperation.memberCalendar,'GET','/api/users/me/investment-calendar',calendarBody,params:{'year':'2026','month':'10','scope':'PORTFOLIO'},query:{'year':'2026','month':'10','scope':'PORTFOLIO'}),
  RouteCase(UserOperation.profile,'GET','/api/users/me',profileBody),
  RouteCase(UserOperation.updateProfile,'PATCH','/api/users/me',profileBody,write:true),
  RouteCase(UserOperation.withdraw,'DELETE','/api/users/me','',write:true,noContent:true),
  RouteCase(UserOperation.logout,'POST','/api/auth/logout','',write:true,noContent:true),
  RouteCase(UserOperation.feedback,'POST','/api/feedback','',write:true,noContent:true),
];

void main() {
  for (final route in routes) {
    test('${route.op.name}: 원본 route/method/query/CSRF/DTO', () async {
      final transport = FakeTransport((request) => request.path == '/api/auth/csrf'
        ? ApiResponse(200,csrfBody) : ApiResponse(route.noContent ? 204 : 200,route.response));
      final payload = <String,Object?>{'holdings': [],'unitPrice':ExactNumber('10.2500')};
      final result = await repository(transport).invoke(route.op,params:route.params,body:route.write ? payload : null);
      final request = transport.requests.last;
      final uri = Uri.parse(request.path);
      expect(uri.path,route.path);
      expect(uri.queryParameters,route.query);
      expect(request.method,route.method);
      expect(request.credentials,isTrue);
      if (route.write) {
        expect(transport.requests.first.path,'/api/auth/csrf');
        expect(request.headers['X-XSRF-TOKEN'],'test-only-token');
        expect(request.body,encodeJsonExact(payload));
      } else {
        expect(transport.requests.length,1);
      }
      expect(result == null,route.noContent);
    });
    if (!route.noContent) {
      test('${route.op.name}: 잘못된 최상위 응답 shape 거절', () async {
        final transport = FakeTransport((r)=>r.path == '/api/auth/csrf' ? ApiResponse(200,csrfBody) : ApiResponse(200,'{}'));
        await expectLater(repository(transport).invoke(route.op,params:route.params,body:route.write ? {'holdings':[]} : null),throwsFormatException);
      });
    }
  }
  test('미국 검색은 country=US를 보내고 검색어 전체를 하나의 query로 인코딩한다',() async {
    final transport=FakeTransport((_)=>ApiResponse(200,stockBody));
    await repository(transport).invoke(UserOperation.stocks,params:{'q':'AAPL&country=KR','country':'US'});
    expect(Uri.parse(transport.requests.single.path).queryParameters,{'q':'AAPL&country=KR','country':'US'});
  });
  test('ALL category/source는 query에서 생략한다',() async {
    final transport=FakeTransport((r)=>ApiResponse(200,Uri.parse(r.path).path=='/api/news' ? newsPageBody : contentsBody));
    final repo=repository(transport);
    await repo.invoke(UserOperation.news,params:{'page':'1','size':'6','category':'ALL'});
    await repo.invoke(UserOperation.searchContents,params:{'q':'금리','page':'1','size':'12','source':'ALL'});
    expect(Uri.parse(transport.requests[0].path).queryParameters.containsKey('category'),isFalse);
    expect(Uri.parse(transport.requests[1].path).queryParameters.containsKey('source'),isFalse);
  });
  for (final assetId in ['0','-1','1.5','9007199254740993','../users/me','1?x=y']) {
    test('ID 경로 입력 거절 후 요청 없음: $assetId',() async {
      final transport=FakeTransport((_)=>ApiResponse(200,priceBody));
      await expectLater(repository(transport).invoke(UserOperation.price,params:{'assetId':assetId}),throwsFormatException);
      expect(transport.requests,isEmpty);
    });
  }
  for (final params in [{'year':'2026','month':'13','scope':'ALL'},{'year':'1999','month':'1','scope':'ALL'},{'year':'2026','month':'1','scope':'INVALID'}]) {
    test('잘못된 캘린더 입력은 전송 전에 거절: $params',() async {
      final transport=FakeTransport((_)=>ApiResponse(200,calendarBody));
      await expectLater(repository(transport).invoke(UserOperation.memberCalendar,params:params),throwsFormatException);
      expect(transport.requests,isEmpty);
    });
  }
  test('응답 금융값은 double 변환 없이 exact number다',() async {
    final transport=FakeTransport((_)=>ApiResponse(200,savedPortfolioBody));
    final result=await repository(transport).invoke(UserOperation.portfolio) as Map;
    expect((result['totalRealizedProfitLoss'] as ExactNumber).lexeme,'12.3450');
    expect(((result['holdings'] as List).single['averagePurchasePrice'] as ExactNumber).lexeme,'60000.10');
  });
  test('가격 없는 PARTIAL 계산의 null 수익률을 0으로 만들지 않는다',() async {
    final transport=FakeTransport((r)=>ApiResponse(200,r.path=='/api/auth/csrf' ? csrfBody : calculationBody));
    final result=await repository(transport).invoke(UserOperation.calculate,body:{'holdings':[]}) as Map;
    expect(result['pricingStatus'],'PARTIAL');
    expect(result['totalReturnRate'],isNull);
  });
  test('내 정보의 누락 name은 닉네임으로 추측하지 않는다',() async {
    final transport=FakeTransport((_)=>ApiResponse(200,'{"id":7,"email":"test@example.invalid","nickname":"별명","role":"USER"}'));
    final result=await repository(transport).invoke(UserOperation.profile) as Map;
    expect(result['name'],isNull);
    expect(result['nickname'],'별명');
  });
  for (final example in <(UserOperation,Map<String,String>,String)>[
    (UserOperation.portfolio,{},'{"holdings":[{}],"totalRealizedProfitLoss":0}'),
    (UserOperation.portfolio,{},'{"holdings":[],"totalRealizedProfitLoss":"0"}'),
    (UserOperation.news,{'page':'1','size':'6'},newsPageBody.replaceAll('ECONOMY','UNRECOGNIZED')),
    (UserOperation.news,{'page':'1','size':'6'},newsPageBody.replaceAll('"id":3','"id":0')),
    (UserOperation.newsDetail,{'newsId':'3'},newsDetailBody.replaceAll('"content":["금리 흐름을 확인합니다.","출처를 확인하세요."]','"content":42')),
    (UserOperation.profile,{},profileBody.replaceAll('"role":"USER"','"role":"OWNER"')),
    (UserOperation.profile,{},profileBody.replaceAll('"nickname":"투자일기"','"nickname":null')),
    (UserOperation.memberCalendar,{'year':'2026','month':'10','scope':'ALL'},calendarBody.replaceAll('"events":[]','"events":[{}]')),
    (UserOperation.savedAnalysis,{},savedAnalysisBody.replaceAll('"status":"EMPTY"','"status":"DONE"')),
    (UserOperation.savedAnalysis,{},savedAnalysisBody.replaceAll('"analysis":null','"analysis":{}')),
    (UserOperation.people,{},'{"people":[{"id":1,"name":"인물","posts":[{}]}]}'),
    (UserOperation.searchContents,{'q':'금리','page':'1','size':'12'},contentsBody.replaceAll('"items":[]','"items":[{"kind":"UNKNOWN"}]')),
    (UserOperation.exchangeRate,{'date':'2026-10-28'},'{"baseDate":"2026-10-28","rate":0}'),
  ]) {
    test('${example.$1.name} 중첩 DTO/enum/금액 타입 위반 거절: ${example.$3}',() async {
      final transport=FakeTransport((_)=>ApiResponse(200,example.$3));
      await expectLater(repository(transport).invoke(example.$1,params:example.$2),throwsFormatException);
    });
  }
}
