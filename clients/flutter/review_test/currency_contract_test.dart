// Additional independent regression contract, authored after the v1 baseline.
// Frozen v1 test/** and spec files are deliberately untouched.
//
// Source basis:
// - reference/.../portfolio/components/PortfolioEditor.tsx:116-145: average
//   purchase price input is explicitly denominated in won, including US stocks.
// - reference/.../portfolio/dto/{PortfolioHoldingResponse,
//   SavedPortfolioHoldingResponse}.java: averagePurchasePriceCurrency() = KRW.
// - reference/.../portfolio/dto/SavedPortfolioHoldingUpdateRequest.java:15:
//   "원화(KRW) 기준 평균 매입가".
// - app/src/service_market.rs CALCULATE_SQL: avg*qty is purchase amount; only
//   USD close price is converted by the rate. The server must receive KRW cost.
//
// Selected UX: USD price-input is a reference USD close quote. A distinct,
// initially empty holding-average-krw input is mandatory for guest KRW cost.
// No implicit USD-as-KRW substitution or invented exchange rate is permitted.
import 'package:daynomy_flutter/daynomy.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../test/support/fakes.dart';

const usdStocks =
    '{"stocks":[{"assetId":1,"assetCode":"AAPL.US","name":"Apple","category":"STOCK","market":"NASDAQ","currency":"USD"}]}';
const usdQuote =
    '{"assetId":1,"assetCode":"AAPL.US","name":"Apple","baseDate":"2026-10-28","closePrice":123.45,"currency":"USD"}';
const usdHolding =
    '{"assetId":1,"assetCode":"AAPL.US","name":"Apple","category":"STOCK","market":"NASDAQ","currency":"USD","quantity":2,"averagePurchasePrice":170000.10,"averagePurchasePriceCurrency":"KRW"}';
const usdCalculation =
    '{"baseDate":"2026-10-28","pricingStatus":"COMPLETE","pricedHoldingCount":1,"unpricedHoldingCount":0,"totalPurchaseAmount":340000.20,"totalEvaluationAmount":345660,"dailyProfitLoss":null,"dailyReturnRate":null,"totalProfitLoss":5659.80,"totalReturnRate":1.66,"holdings":[{"assetId":1,"assetCode":"AAPL.US","name":"Apple","category":"STOCK","market":"NASDAQ","currency":"USD","quantity":2,"averagePurchasePrice":170000.10,"averagePurchasePriceCurrency":"KRW","evaluationCurrency":"KRW","priceAvailable":true,"baseDate":"2026-10-28","closePrice":123.45,"purchaseAmount":340000.20,"evaluationAmount":345660,"profitLoss":5659.80,"returnRate":1.66,"weight":100}],"marketAllocations":[{"market":"NASDAQ","evaluationAmount":345660,"weight":100}]}';

ApiResponse respond(ApiRequest request, {bool member = false}) {
  final path = Uri.parse(request.path).path;
  if (path == '/api/stocks') return ApiResponse(200, usdStocks);
  if (path == '/api/stocks/1/price') return ApiResponse(200, usdQuote);
  if (path == '/api/assets/1/contents') {
    return ApiResponse(
      200,
      '{"assetId":1,"assetCode":"AAPL.US","assetName":"Apple","contents":[]}',
    );
  }
  if (path == '/api/users/me/portfolio') {
    return ApiResponse(
      200,
      '{"holdings":[$usdHolding],"totalRealizedProfitLoss":0}',
    );
  }
  if (path == '/api/portfolio/calculate') {
    return ApiResponse(200, usdCalculation);
  }
  return defaultResponse(request, member: member);
}

Future<void> selectUsd(WidgetTester tester, FakeTransport transport) async {
  await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const ValueKey('stock-query')), 'Apple');
  await tester.pump(const Duration(milliseconds: 250));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const ValueKey('stock-1')));
  await tester.pumpAndSettle();
}

Future<void> portfolioTab(WidgetTester tester) async {
  await tester.tap(find.byKey(const ValueKey('nav-portfolio')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('USD 참고 종가를 게스트 원화 평균 매입가로 자동 저장하지 않는다', (
    tester,
  ) async {
    final transport = FakeTransport(respond);
    await selectUsd(tester, transport);
    final quote = tester.widget<TextFormField>(
      find.byKey(const ValueKey('price-input')),
    );
    expect(quote.controller?.text, '123.45');
    final quoteInput = tester.widget<TextField>(find.descendant(
      of: find.byKey(const ValueKey('price-input')),
      matching: find.byType(TextField),
    ));
    expect(quoteInput.decoration?.labelText, contains('USD'));

    final krwFinder = find.byKey(const ValueKey('holding-average-krw'));
    expect(krwFinder, findsOneWidget);
    final krw = tester.widget<TextFormField>(krwFinder);
    expect(krw.controller?.text, isEmpty);
    final krwInput = tester.widget<TextField>(find.descendant(
      of: krwFinder,
      matching: find.byType(TextField),
    ));
    expect(krwInput.decoration?.labelText, contains('KRW'));

    // Missing explicit KRW cost may disable the button or show validation. It
    // must never create a holding with the quote's USD number as KRW cost.
    await tester.ensureVisible(find.byKey(const ValueKey('holding-add')));
    await tester.tap(find.byKey(const ValueKey('holding-add')));
    await tester.pumpAndSettle();
    await portfolioTab(tester);
    expect(find.byKey(const ValueKey('holding-1')), findsNothing);
    expect(
      transport.requests.where(
        (r) => r.path == '/api/portfolio/transactions',
      ),
      isEmpty,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('미국 종목은 명시 입력한 KRW 원가를 exact 계산 body와 보유 행에 사용한다', (
    tester,
  ) async {
    final transport = FakeTransport(respond);
    await selectUsd(tester, transport);
    await tester.enterText(
      find.byKey(const ValueKey('holding-quantity')),
      '2',
    );
    await tester.enterText(
      find.byKey(const ValueKey('holding-average-krw')),
      '170000.10',
    );
    await tester.ensureVisible(find.byKey(const ValueKey('holding-add')));
    await tester.tap(find.byKey(const ValueKey('holding-add')));
    await tester.pumpAndSettle();
    await portfolioTab(tester);

    final row = find.byKey(const ValueKey('holding-1'));
    expect(row, findsOneWidget);
    expect(
      find.descendant(of: row, matching: find.textContaining('170000.10 KRW')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: row, matching: find.textContaining('170000.10 USD')),
      findsNothing,
    );
    await tester.ensureVisible(find.byKey(const ValueKey('guest-calculate')));
    await tester.tap(find.byKey(const ValueKey('guest-calculate')));
    await tester.pumpAndSettle();
    final calculation = transport.requests.lastWhere(
      (r) => r.path == '/api/portfolio/calculate',
    );
    final body = decodeJsonExact(calculation.body!) as Map;
    final holding = (body['holdings'] as List).single as Map;
    expect(checkedId(holding['assetId']), 1);
    expect(checkedId(holding['quantity']), 2);
    expect(
      (holding['averagePurchasePrice'] as ExactNumber).lexeme,
      '170000.10',
    );
    expect(
      (holding['averagePurchasePrice'] as ExactNumber).lexeme,
      isNot('123.45'),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('회원 미국 종목 보유의 평균 원가는 종목 통화와 구분하여 KRW로 표시한다', (
    tester,
  ) async {
    final transport = FakeTransport((r) => respond(r, member: true));
    await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
    await tester.pumpAndSettle();
    await portfolioTab(tester);
    final row = find.byKey(const ValueKey('holding-1'));
    expect(row, findsOneWidget);
    expect(
      find.descendant(of: row, matching: find.textContaining('170000.10 KRW')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: row, matching: find.textContaining('170000.10 USD')),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });
}
