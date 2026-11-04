import 'dart:async';
import 'package:daynomy_flutter/daynomy.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../test/support/fakes.dart';

void main() {
  for (final scenario in [
    (size: const Size(375, 812), scale: 1.0, dark: false),
    (size: const Size(375, 812), scale: 2.0, dark: true),
    (size: const Size(812, 375), scale: 1.0, dark: true),
    (size: const Size(1280, 800), scale: 2.0, dark: false),
  ]) {
    testWidgets('all tabs render ${scenario.size} scale ${scenario.scale} dark ${scenario.dark}', (tester) async {
      tester.view.physicalSize = scenario.size;
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.platformBrightnessTestValue = scenario.dark ? Brightness.dark : Brightness.light;
      tester.platformDispatcher.textScaleFactorTestValue = scenario.scale;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final transport = FakeTransport((r) => defaultResponse(r, member: true));
      await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
      await tester.pumpAndSettle();
      for (final name in ['search', 'portfolio', 'news', 'calendar', 'profile']) {
        await tester.tap(find.byKey(ValueKey('nav-$name')));
        await tester.pumpAndSettle();
        expect(find.byKey(ValueKey('page-$name')), findsOneWidget);
        expect(tester.takeException(), isNull);
      }
    });
  }

  testWidgets('tab switch cancels a request and late completion cannot show stale stock', (tester) async {
    final pending = Completer<ApiResponse>();
    final transport = FakeTransport((r) => Uri.parse(r.path).path == '/api/stocks'
      ? pending.future : defaultResponse(r));
    await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('stock-query')), 'stale');
    await tester.pump(const Duration(milliseconds: 250));
    final request = transport.requests.lastWhere((r) => Uri.parse(r.path).path == '/api/stocks');
    await tester.tap(find.byKey(const ValueKey('nav-profile')));
    await tester.pumpAndSettle();
    expect(request.cancel!.isCancelled, isTrue);
    pending.complete(ApiResponse(200, stockBody));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('nav-search')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('stock-1')), findsNothing);
    expect(tester.widget<TextFormField>(find.byKey(const ValueKey('stock-query'))).controller!.text, 'stale');
    expect(tester.takeException(), isNull);
  });

  testWidgets('abandoning guest analysis cancels calculation and does not start downstream AI', (tester) async {
    final calculation = Completer<ApiResponse>();
    final transport = FakeTransport((r) => Uri.parse(r.path).path == '/api/portfolio/calculate'
      ? calculation.future : defaultResponse(r));
    await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('nav-portfolio')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('guest-analysis')));
    await tester.pump();
    final request = transport.requests.lastWhere((r) => r.path == '/api/portfolio/calculate');
    await tester.tap(find.byKey(const ValueKey('nav-profile')));
    await tester.pumpAndSettle();
    final cancelled = request.cancel?.isCancelled == true;
    calculation.complete(ApiResponse(200, calculationBody));
    await tester.pumpAndSettle();
    expect(transport.requests.where((r) => r.path == '/api/portfolio/analysis'), isEmpty,
      reason: 'A disposed screen must not start a new downstream AI request.');
    expect(cancelled, isTrue, reason: 'The abandoned calculation must receive a cancellation token.');
    expect(tester.takeException(), isNull);
  });

  testWidgets('logout completion after a tab switch clears parent member state', (tester) async {
    final logout = Completer<ApiResponse>();
    var member = true;
    final transport = FakeTransport((r) => r.path == '/api/auth/logout'
      ? logout.future : defaultResponse(r, member: member));
    await tester.pumpWidget(DaynomyApp(repository: repository(transport)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('nav-profile')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('로그아웃'));
    await tester.tap(find.text('로그아웃'));
    await tester.pump();
    expect(transport.requests.where((r) => r.path == '/api/auth/logout'), hasLength(1));
    await tester.tap(find.byKey(const ValueKey('nav-search')));
    await tester.pumpAndSettle();
    member = false;
    logout.complete(ApiResponse(204, ''));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('nav-profile')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('login-button')), findsOneWidget);
    expect(find.byKey(const ValueKey('nickname-input')), findsNothing);
    expect(find.text('투자일기'), findsNothing);
  });
}
