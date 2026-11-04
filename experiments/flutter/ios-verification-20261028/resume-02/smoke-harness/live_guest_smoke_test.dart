// Additional live-device verification; frozen v1 criteria stay unchanged.
// Fixture contract: scripts/service_acceptance.py and flutter_backend_fixture.py.
// Calls the unchanged production main: no fake repository, transport, auth, or API.
import 'package:daynomy_flutter/main.dart' as production;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
final checkpoints = <String>[];

Finder keyed(String key) => find.byKey(ValueKey<String>(key));

Future<void> waitFor(
  WidgetTester tester,
  bool Function() ready,
  String condition, {
  Duration timeout = const Duration(seconds: 35),
}) async {
  final end = DateTime.now().add(timeout);
  while (!ready() && DateTime.now().isBefore(end)) {
    await tester.pump(const Duration(milliseconds: 100));
    await Future<void>.delayed(const Duration(milliseconds: 100));
  }
  expect(ready(), isTrue, reason: condition);
  expect(tester.takeException(), isNull, reason: condition);
}

Future<void> visibleTap(WidgetTester tester, Finder finder) async {
  expect(finder, findsOneWidget);
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle(const Duration(milliseconds: 100));
  await tester.tap(finder);
  await tester.pump(const Duration(milliseconds: 150));
}

Future<void> enter(WidgetTester tester, Finder finder, String value) async {
  expect(finder, findsOneWidget);
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle(const Duration(milliseconds: 100));
  await tester.enterText(finder, value);
  // Dismiss keyboard without simulating any external OS input.
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pumpAndSettle(const Duration(milliseconds: 100));
}

String fieldValue(WidgetTester tester, String key) =>
    tester.widget<TextFormField>(keyed(key)).controller!.text;

Future<void> tab(WidgetTester tester, String name) async {
  await visibleTap(tester, keyed('nav-$name'));
  await waitFor(tester, () => keyed('page-$name').evaluate().isNotEmpty,
      '$name page must open');
}

Future<void> record(String name, {bool screenshot = true}) async {
  checkpoints.add(name);
  binding.reportData ??= <String, dynamic>{};
  binding.reportData!['checkpoints'] = List<String>.of(checkpoints);
  if (screenshot) await binding.takeScreenshot(name);
}

void main() {
  testWidgets('real iOS guest app and Rust fixture journey', (tester) async {
    const base = String.fromEnvironment('API_BASE_URL');
    expect(base, 'http://127.0.0.1:18087',
        reason: 'This destructive synthetic smoke only targets the owned fixture');
    production.main();
    await waitFor(tester, () => keyed('page-search').evaluate().isNotEmpty,
        'production app must boot');

    for (final name in ['search', 'portfolio', 'news', 'calendar', 'profile']) {
      await tab(tester, name);
    }
    await waitFor(tester, () => keyed('login-button').evaluate().isNotEmpty,
        'fresh native cookie jar must be a guest');
    await record('01-five-tabs-guest');

    await tab(tester, 'search');
    await enter(tester, keyed('stock-query'), 'Harness');
    await waitFor(tester, () => keyed('stock-910001').evaluate().isNotEmpty,
        'real HTTP stock search must return fixture Alpha');
    await visibleTap(tester, keyed('stock-910001'));
    await waitFor(
      tester,
      () => keyed('price-input').evaluate().isNotEmpty &&
          fieldValue(tester, 'price-input') == '120.2500',
      'real saved close must fill the exact decimal field',
    );
    expect(find.text('최근 저장 종가 · 2020-01-03 · KRW'), findsOneWidget);
    await tester.ensureVisible(keyed('price-input'));
    await tester.pumpAndSettle();
    await record('02-real-search-stored-close');

    await enter(tester, keyed('holding-quantity'), '2');
    await enter(tester, keyed('price-input'), '100.00');
    await visibleTap(tester, keyed('holding-add'));
    await waitFor(
      tester,
      () => find.text('이 기기의 게스트 초안에 추가했습니다. 포트폴리오에서 확인하세요.')
          .evaluate().isNotEmpty,
      'guest holding must be added in the production app',
    );

    // Mixed relative INTERNAL_NEWS and external HTTP contents must stay visible.
    await waitFor(tester, () => find.text('Harness internal').evaluate().isNotEmpty,
        'mixed related contents must decode');
    expect(find.text('Harness external video'), findsOneWidget);
    await visibleTap(tester, find.text('Harness internal'));
    await waitFor(tester, () => find.text('Harness body').evaluate().isNotEmpty,
        'internal related news must open the real news body');
    expect(keyed('news-detail'), findsOneWidget);
    expect(find.text('Fixture'), findsWidgets);
    await record('03-real-internal-news-body');
    await tester.pageBack();
    await waitFor(tester, () => keyed('page-search').evaluate().isNotEmpty,
        'news back must return to the production search page');
    expect(fieldValue(tester, 'stock-query'), 'Harness');
    expect(fieldValue(tester, 'price-input'), '100.00');

    await tab(tester, 'portfolio');
    expect(keyed('holding-910001'), findsOneWidget);
    await visibleTap(tester, keyed('guest-calculate'));
    await waitFor(tester, () => find.text('평가 240.50원').evaluate().isNotEmpty,
        'real Rust evaluation must be 2 * 120.25');
    expect(find.text('매입 200.00원'), findsOneWidget);
    expect(find.text('손익 40.50 · 수익률 20.25'), findsOneWidget);
    await tester.ensureVisible(find.text('평가 240.50원'));
    await tester.pumpAndSettle();
    await record('04-real-guest-calculation');

    // Exercise edit, but keep a real holding for the calendar until the end.
    await visibleTap(tester, find.text('보유 수정'));
    await waitFor(tester, () => find.byType(AlertDialog).evaluate().isNotEmpty,
        'guest edit dialog must open');
    final dialog = find.byType(AlertDialog);
    final fields = find.descendant(of: dialog, matching: find.byType(TextFormField));
    expect(fields, findsNWidgets(2));
    await enter(tester, fields.at(0), '3');
    await enter(tester, fields.at(1), '105.50');
    await visibleTap(
      tester,
      find.descendant(of: dialog,
          matching: find.text('보유 수정')),
    );
    await waitFor(tester, () => find.text('3주 · 평균 105.50 KRW').evaluate().isNotEmpty,
        'guest edit must update quantity and KRW average');
    await record('05-guest-holding-edited');

    await tab(tester, 'news');
    await waitFor(tester, () => keyed('news-910001').evaluate().isNotEmpty,
        'real news list must return published fixture');
    await visibleTap(tester, keyed('news-910001'));
    await waitFor(tester, () => find.text('Harness body').evaluate().isNotEmpty,
        'news list must open real news detail');
    await waitFor(tester, () => find.text('Harness rate').evaluate().isNotEmpty,
        'real keywords must load');
    await waitFor(tester, () => find.text('위험 요인: Fixture risk').evaluate().isNotEmpty,
        'real market analysis must load');
    expect(find.text('확인할 점: Fixture watch'), findsOneWidget);
    await record('06-real-news-detail');
    await tester.pageBack();
    await waitFor(tester, () => keyed('page-news').evaluate().isNotEmpty,
        'news detail must return to news list');

    await tab(tester, 'calendar');
    await waitFor(tester, () => find.text('검증용 CPI 일정').evaluate().isNotEmpty,
        'real current-month calendar must return synthetic CPI');
    await visibleTap(tester, find.text('검증용 CPI 일정'));
    await waitFor(tester, () => find.textContaining('표본 0').evaluate().isNotEmpty,
        'calendar must disclose missing historical reaction samples');
    expect(find.textContaining('중앙 수익률 확인되지 않음%'), findsWidgets);
    expect(find.textContaining('Synthetic fixture'), findsWidgets);
    await record('07-real-calendar-missing-samples');

    await tab(tester, 'portfolio');
    await visibleTap(tester, find.text('보유 삭제'));
    await waitFor(tester, () => find.byType(AlertDialog).evaluate().isNotEmpty,
        'guest holding delete must require confirmation');
    await visibleTap(tester, find.widgetWithText(FilledButton, '삭제'));
    await waitFor(tester, () => keyed('holding-910001').evaluate().isEmpty,
        'confirmed guest holding must be removed');
    expect(find.text('보유 자산이 없습니다. 검색에서 종목을 선택해주세요.'), findsOneWidget);
    await record('08-guest-holding-deleted');

    await tab(tester, 'profile');
    expect(keyed('login-button'), findsOneWidget);
    // Do not capture, print, or include this synthetic request body in reportData.
    await enter(tester, keyed('feedback-input'), 'iOS synthetic fixture verification');
    await visibleTap(tester, keyed('feedback-submit'));
    await waitFor(tester, () => keyed('feedback-success').evaluate().isNotEmpty,
        'real cookie/CSRF feedback POST must succeed');
    expect(fieldValue(tester, 'feedback-input').isEmpty, isTrue,
        reason: 'successful feedback must clear the input');
    expect(keyed('feedback-error'), findsNothing);
    await record('09-real-feedback-success-input-cleared');
  }, timeout: const Timeout(Duration(minutes: 7)));
}
