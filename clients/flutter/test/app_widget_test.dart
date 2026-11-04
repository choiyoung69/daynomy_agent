import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';
import 'support/fakes.dart';

Future<void> launch(WidgetTester tester,FakeTransport transport) async {
  await tester.pumpWidget(DaynomyApp(repository:repository(transport)));
  await tester.pumpAndSettle();
}
Future<void> tab(WidgetTester tester,String name) async {
  await tester.tap(find.byKey(ValueKey('nav-$name')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('작은 휴대폰에서 전체 사용자 5탭이 열리고 overflow 없다',(tester) async {
    tester.view.physicalSize=const Size(390,844);
    tester.view.devicePixelRatio=1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    for (final name in ['search','portfolio','news','calendar','profile']) {
      expect(find.byKey(ValueKey('nav-$name')),findsOneWidget);
      await tab(tester,name);
      expect(find.byKey(ValueKey('page-$name')),findsOneWidget);
      expect(tester.takeException(),isNull);
    }
  });
  testWidgets('검색 debounce 후 실 repository의 결과를 보여주고 선택하면 종가 표시',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tester.enterText(find.byKey(const ValueKey('stock-query')),'삼성');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pumpAndSettle();
    expect(find.text('삼성전자'),findsWidgets);
    await tester.tap(find.byKey(const ValueKey('stock-1')).first);
    await tester.pumpAndSettle();
    expect(transport.requests.any((r)=>r.path=='/api/stocks/1/price'),isTrue);
    expect(find.byKey(const ValueKey('price-input')),findsOneWidget);
    final field=tester.widget<TextFormField>(find.byKey(const ValueKey('price-input')));
    expect(field.controller?.text,'71234.1250');
  });
  testWidgets('검색 로딩·오류·재시도 후 빈 상태를 구별한다',(tester) async {
    final pending=Completer<ApiResponse>();
    var failed=true;
    final transport=FakeTransport((r) {
      if (Uri.parse(r.path).path=='/api/stocks') return failed ? pending.future : ApiResponse(200,'{"stocks":[]}');
      return defaultResponse(r);
    });
    await launch(tester,transport);
    await tester.enterText(find.byKey(const ValueKey('stock-query')),'없는종목');
    await tester.pump(const Duration(milliseconds:250));
    expect(find.byKey(const ValueKey('search-loading')),findsOneWidget);
    pending.complete(ApiResponse(503,'{"code":"UNAVAILABLE","message":"잠시 후 다시 시도해주세요."}'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('search-error')),findsOneWidget);
    failed=false;
    await tester.tap(find.byKey(const ValueKey('search-retry')));
    await tester.pump(const Duration(milliseconds:250));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('search-empty')),findsOneWidget);
    expect(find.byKey(const ValueKey('search-error')),findsNothing);
  });
  testWidgets('게스트 포트폴리오가 회원 저장 완료로 표시되지 않는다',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'portfolio');
    expect(find.byKey(const ValueKey('guest-portfolio')),findsOneWidget);
    expect(find.byKey(const ValueKey('guest-calculate')),findsOneWidget);
    expect(find.byKey(const ValueKey('guest-analysis')),findsOneWidget);
    expect(transport.requests.any((r)=>r.path=='/api/portfolio/transactions'),isFalse);
  });
  testWidgets('뉴스 목록 → 상세에서 본문과 출처 표시, 보조 분석404는 본문을 숨기지 않는다',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'news');
    await tester.tap(find.byKey(const ValueKey('news-3')).first);
    await tester.pumpAndSettle();
    expect(find.textContaining('금리 흐름을 확인합니다.'),findsWidgets);
    expect(find.textContaining('한국은행'),findsWidgets);
    expect(find.byKey(const ValueKey('news-detail')),findsOneWidget);
    expect(transport.requests.any((r)=>r.path=='/api/news/3/market-analysis'),isTrue);
    expect(tester.takeException(),isNull);
  });
  testWidgets('캘린더는 guest holdings를 POST하고 빈 일정을 표시한다',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'calendar');
    final request=transport.requests.lastWhere((r)=>Uri.parse(r.path).path=='/api/investment-calendar');
    expect(request.method,'POST');
    expect(decodeJsonExact(request.body!) as Map,contains('holdings'));
    expect(find.byKey(const ValueKey('calendar-empty')),findsOneWidget);
  });
  testWidgets('게스트 내정보는 Google 로그인 진입을 제공한다',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'profile');
    expect(find.byKey(const ValueKey('login-button')),findsOneWidget);
    expect(find.byKey(const ValueKey('nickname-input')),findsNothing);
  });
  testWidgets('회원 내정보는 서버 nickname을 사용하고 수정은 CSRF PATCH다',(tester) async {
    final transport=FakeTransport((r) {
      if (r.path=='/api/users/me' && r.method=='PATCH') return ApiResponse(200,profileBody.replaceAll('투자일기','새별명'));
      return defaultResponse(r,member:true);
    });
    await launch(tester,transport);
    await tab(tester,'profile');
    await tester.enterText(find.byKey(const ValueKey('nickname-input')),'새별명');
    await tester.ensureVisible(find.byKey(const ValueKey('nickname-save')));
    await tester.tap(find.byKey(const ValueKey('nickname-save')));
    await tester.pumpAndSettle();
    final request=transport.requests.lastWhere((r)=>r.path=='/api/users/me' && r.method=='PATCH');
    expect(decodeJsonExact(request.body!),{'nickname':'새별명'});
    expect(request.headers['X-XSRF-TOKEN'],'test-only-token');
    expect(find.text('새별명'),findsWidgets);
  });
  testWidgets('빈 nickname은 서버에 PATCH하지 않는다',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r,member:true));
    await launch(tester,transport);
    await tab(tester,'profile');
    await tester.enterText(find.byKey(const ValueKey('nickname-input')),'   ');
    await tester.ensureVisible(find.byKey(const ValueKey('nickname-save')));
    await tester.tap(find.byKey(const ValueKey('nickname-save')));
    await tester.pumpAndSettle();
    expect(transport.requests.where((r)=>r.path=='/api/users/me' && r.method=='PATCH'),isEmpty);
    expect(find.byKey(const ValueKey('nickname-error')),findsOneWidget);
  });
  testWidgets('피드백 204는 성공 표시, body content와 pagePath 보존',(tester) async {
    final transport=FakeTransport((r)=>defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'profile');
    await tester.ensureVisible(find.byKey(const ValueKey('feedback-input')));
    await tester.enterText(find.byKey(const ValueKey('feedback-input')),'화면이 잘 보여요');
    await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
    await tester.tap(find.byKey(const ValueKey('feedback-submit')));
    await tester.pumpAndSettle();
    final request=transport.requests.lastWhere((r)=>r.path=='/api/feedback');
    final body=decodeJsonExact(request.body!) as Map;
    expect(body['content'],'화면이 잘 보여요');
    expect(body['pagePath'],isA<String>().having((s)=>s.isNotEmpty,'nonempty',true));
    expect(find.byKey(const ValueKey('feedback-success')),findsOneWidget);
  });
  testWidgets('피드백 실패는 입력을 남기며 성공 표시하지 않는다',(tester) async {
    final transport=FakeTransport((r)=>r.path=='/api/feedback' ? ApiResponse(503,'{"code":"UNAVAILABLE","message":"다시 시도해주세요."}') : defaultResponse(r));
    await launch(tester,transport);
    await tab(tester,'profile');
    await tester.ensureVisible(find.byKey(const ValueKey('feedback-input')));
    await tester.enterText(find.byKey(const ValueKey('feedback-input')),'보존할 피드백');
    await tester.ensureVisible(find.byKey(const ValueKey('feedback-submit')));
    await tester.tap(find.byKey(const ValueKey('feedback-submit')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('feedback-error')),findsOneWidget);
    expect(find.byKey(const ValueKey('feedback-success')),findsNothing);
    expect(find.text('보존할 피드백'),findsWidgets);
    expect(transport.requests.where((r)=>r.path=='/api/feedback').length,1);
  });
  testWidgets('게스트 검색선택 → 보유추가 → 서버계산은 exact holdings를 전송하고 부분가격을 표시한다',(tester) async {
    const partial = '{"baseDate":null,"pricingStatus":"PARTIAL","pricedHoldingCount":0,"unpricedHoldingCount":1,"totalPurchaseAmount":120000.20,"totalEvaluationAmount":0,"dailyProfitLoss":null,"dailyReturnRate":null,"totalProfitLoss":null,"totalReturnRate":null,"holdings":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","quantity":2,"averagePurchasePrice":60000.10,"purchaseAmount":120000.20,"priceAvailable":false,"baseDate":null,"closePrice":null,"evaluationAmount":null,"profitLoss":null,"returnRate":null,"weight":null}],"marketAllocations":[]}';
    final transport=FakeTransport((r)=>r.path=='/api/portfolio/calculate' ? ApiResponse(200,partial) : defaultResponse(r));
    await launch(tester,transport);
    await tester.enterText(find.byKey(const ValueKey('stock-query')),'삼성');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('stock-1')).first);
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('holding-quantity')),'2');
    await tester.enterText(find.byKey(const ValueKey('price-input')),'60000.10');
    await tester.ensureVisible(find.byKey(const ValueKey('holding-add')));
    await tester.tap(find.byKey(const ValueKey('holding-add')));
    await tester.pumpAndSettle();
    await tab(tester,'portfolio');
    expect(find.byKey(const ValueKey('holding-1')),findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('guest-calculate')));
    await tester.tap(find.byKey(const ValueKey('guest-calculate')));
    await tester.pumpAndSettle();
    final request=transport.requests.lastWhere((r)=>r.path=='/api/portfolio/calculate');
    final body=decodeJsonExact(request.body!) as Map;
    final holding=(body['holdings'] as List).single as Map;
    expect(checkedId(holding['assetId']),1);
    expect(checkedId(holding['quantity']),2);
    expect((holding['averagePurchasePrice'] as ExactNumber).lexeme,'60000.10');
    expect(find.byKey(const ValueKey('pricing-partial')),findsOneWidget);
    expect(transport.requests.where((r)=>r.path=='/api/portfolio/transactions'),isEmpty);
  });
  testWidgets('회원 매수 등록 → 서버 보유 재조회 → 거래 이력 수정·삭제 UI',(tester) async {
    var phase=0;
    const history='[{"historyId":11,"assetId":1,"assetCode":"005930","name":"삼성전자","changeType":"BUY","quantity":3,"averagePurchasePrice":61666.9000,"effectiveDate":"2026-10-28","occurredAt":"2026-10-28T09:00:00+09:00","transactionQuantity":1,"unitPrice":65000.5000,"fee":10,"tax":0}]';
    final transport=FakeTransport((r) {
      final path=Uri.parse(r.path).path;
      if (path=='/api/portfolio/transactions' && r.method=='POST') {
        phase=1;
        return ApiResponse(200,transactionBody.replaceAll('"quantity":2','"quantity":3'));
      }
      if (path=='/api/portfolio/transactions/11' && r.method=='PATCH') {
        phase=2;
        return ApiResponse(200,transactionBody.replaceAll('"quantity":2','"quantity":4'));
      }
      if (path=='/api/portfolio/transactions/11' && r.method=='DELETE') {
        phase=3;
        return ApiResponse(200,transactionBody);
      }
      if (path=='/api/users/me/portfolio') return ApiResponse(200,savedPortfolioBody.replaceAll('"quantity":2','"quantity":${phase==1 ? 3 : phase==2 ? 4 : 2}'));
      if (path.endsWith('/histories')) return ApiResponse(200,phase>0 && phase<3 ? history : '[]');
      return defaultResponse(r,member:true);
    });
    await launch(tester,transport);
    await tester.enterText(find.byKey(const ValueKey('stock-query')),'삼성');
    await tester.pump(const Duration(milliseconds:250));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('stock-1')).first);
    await tester.pumpAndSettle();
    await tab(tester,'portfolio');
    await tester.ensureVisible(find.byKey(const ValueKey('transaction-add')));
    await tester.tap(find.byKey(const ValueKey('transaction-add')));
    await tester.pumpAndSettle();
    for (final field in {'transaction-quantity':'1','transaction-unit-price':'65000.5000','transaction-fee':'10','transaction-tax':'0','transaction-date':'2026-10-28'}.entries) {
      await tester.enterText(find.byKey(ValueKey(field.key)),field.value);
    }
    await tester.ensureVisible(find.byKey(const ValueKey('transaction-submit')));
    await tester.tap(find.byKey(const ValueKey('transaction-submit')));
    await tester.pumpAndSettle();
    final create=transport.requests.lastWhere((r)=>r.path=='/api/portfolio/transactions' && r.method=='POST');
    final body=decodeJsonExact(create.body!) as Map;
    expect(checkedId(body['assetId']),1);
    expect(body['type'],'BUY');
    expect(checkedId(body['quantity']),1);
    expect((body['unitPrice'] as ExactNumber).lexeme,'65000.5000');
    expect((body['fee'] as ExactNumber).lexeme,'10');
    expect((body['tax'] as ExactNumber).lexeme,'0');
    expect(body['tradeDate'],'2026-10-28');
    final createIndex=transport.requests.indexOf(create);
    expect(transport.requests.skip(createIndex+1).any((r)=>r.path=='/api/users/me/portfolio'),isTrue);
    await tester.ensureVisible(find.byKey(const ValueKey('transaction-edit-11')));
    await tester.tap(find.byKey(const ValueKey('transaction-edit-11')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('transaction-quantity')),'2');
    await tester.ensureVisible(find.byKey(const ValueKey('transaction-submit')));
    await tester.tap(find.byKey(const ValueKey('transaction-submit')));
    await tester.pumpAndSettle();
    final update=transport.requests.lastWhere((r)=>r.path=='/api/portfolio/transactions/11' && r.method=='PATCH');
    expect(checkedId((decodeJsonExact(update.body!) as Map)['quantity']),2);
    await tester.ensureVisible(find.byKey(const ValueKey('transaction-delete-11')));
    await tester.tap(find.byKey(const ValueKey('transaction-delete-11')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('transaction-delete-confirm')));
    await tester.pumpAndSettle();
    expect(transport.requests.where((r)=>r.path=='/api/portfolio/transactions/11' && r.method=='DELETE').length,1);
    expect(find.byKey(const ValueKey('transaction-edit-11')),findsNothing);
    expect(tester.takeException(),isNull);
  });
}
