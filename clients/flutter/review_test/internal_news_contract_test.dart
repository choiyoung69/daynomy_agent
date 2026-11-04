// Independent additional regression. No frozen v1 test/spec or currency tests
// are changed by this file.
//
// Original evidence:
// reference/2026-DAYNOMY-dev/frontend/src/features/stock-content/api.ts:25-36
// resolves URLs against https://daynomy.local and permits relative /news/<id>.
// StockContentPage.tsx:573-582 uses INTERNAL_NEWS href with target=_blank;
// App.tsx:303 maps /news/:newsId to NewsDetailPage. It does not call an in-page
// React router handler directly: the original opens a same-site detail new tab.
//
// Flutter adaptation: INTERNAL_NEWS /news/<positive-safe-integer> opens the app's
// news detail, without an external launcher. Only this canonical news route is
// mapped as a detail ID. Decoder URL acceptance keeps the original boundary:
// HTTP/HTTPS and relative URLs remain accepted; javascript/data and leading //
// links remain rejected. Other relative URLs are not redefined as news IDs.
import 'dart:convert';

import 'package:daynomy_flutter/daynomy.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../test/support/fakes.dart';

const assetId = 910001;
const newsId = 910001;
const internalTitle = '관련 내부 뉴스 회귀 제목';
const externalTitle = '관련 YouTube 회귀 영상';
const fullText = '관련 자료에서 연 DAYNOMY 뉴스의 실제 본문입니다.';

String contents({
  String internalUrl = '/news/910001',
  String externalUrl = 'https://www.youtube.com/watch?v=daynomy1234',
}) => jsonEncode({
  'assetId': assetId,
  'assetCode': 'HARNESS',
  'assetName': 'Harness Alpha',
  'contents': [
    {
      'id': 910101,
      'assetId': assetId,
      'sourceType': 'INTERNAL_NEWS',
      'title': internalTitle,
      'url': internalUrl,
      'imageUrl': null,
      'createdAt': '2026-10-28T09:00:00+09:00',
      'publishedDate': '2026-10-28',
    },
    {
      'id': 910102,
      'assetId': assetId,
      'sourceType': 'YOUTUBE',
      'title': externalTitle,
      'url': externalUrl,
      'imageUrl': null,
      'createdAt': '2026-10-28T09:00:00+09:00',
      'publishedDate': '2026-10-28',
    },
  ],
});

ApiResponse response(ApiRequest request, {String? assetContents}) {
  final path = Uri.parse(request.path).path;
  if (path == '/api/stocks') {
    return ApiResponse(
      200,
      '{"stocks":[{"assetId":910001,"assetCode":"HARNESS","name":"Harness Alpha","category":"STOCK","market":"KOSPI","currency":"KRW"}]}',
    );
  }
  if (path == '/api/stocks/910001/price') {
    return ApiResponse(
      200,
      '{"assetId":910001,"assetCode":"HARNESS","name":"Harness Alpha","baseDate":"2026-10-28","closePrice":120.00,"currency":"KRW"}',
    );
  }
  if (path == '/api/assets/910001/contents') {
    return ApiResponse(200, assetContents ?? contents());
  }
  if (path == '/api/news/910001') {
    return ApiResponse(
      200,
      jsonEncode({
        'id': newsId,
        'title': internalTitle,
        'category': 'STOCK',
        'publishedAt': '2026-10-28T09:00:00+09:00',
        'content': [fullText],
        'imageUrl': null,
        'sources': [
          {'name': '공개 출처', 'url': 'https://example.org/source'},
        ],
      }),
    );
  }
  return defaultResponse(request);
}

Future<void> selectAsset(
  WidgetTester tester,
  FakeTransport transport,
  List<Uri> opened,
) async {
  await tester.pumpWidget(
    DaynomyApp(
      repository: repository(transport),
      onOpenLink: (uri) async => opened.add(uri),
    ),
  );
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const ValueKey('stock-query')),
    'Harness',
  );
  await tester.pump(const Duration(milliseconds: 250));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const ValueKey('stock-910001')));
  await tester.pumpAndSettle();
}

void main() {
  test('정상 상대 내부뉴스와 HTTPS 외부자료 혼합 DTO를 함께 수용한다', () async {
    final transport = FakeTransport(response);
    final value = await repository(transport).invoke(
      UserOperation.assetContents,
      params: {'assetId': '$assetId'},
    ) as Map;
    final items = value['contents'] as List;
    expect(items.length, 2);
    expect(items[0]['sourceType'], 'INTERNAL_NEWS');
    expect(items[0]['url'], '/news/910001');
    expect(items[1]['sourceType'], 'YOUTUBE');
    expect(items[1]['url'], 'https://www.youtube.com/watch?v=daynomy1234');
  });

  testWidgets('선택 종목 관련 내부뉴스는 외부 launcher 없이 앱 뉴스 상세로 이동한다', (
    tester,
  ) async {
    final opened = <Uri>[];
    final transport = FakeTransport(response);
    await selectAsset(tester, transport, opened);
    expect(find.text(internalTitle), findsOneWidget);
    expect(find.text(externalTitle), findsOneWidget);
    await tester.ensureVisible(find.text(internalTitle));
    await tester.tap(find.text(internalTitle));
    await tester.pumpAndSettle();
    expect(opened, isEmpty);
    expect(
      transport.requests.where((r) => r.path == '/api/news/910001').length,
      1,
    );
    expect(find.byKey(const ValueKey('news-detail')), findsOneWidget);
    expect(find.textContaining(fullText), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('같은 혼합 목록의 HTTPS 외부자료는 원문 launcher를 사용한다', (
    tester,
  ) async {
    final opened = <Uri>[];
    final transport = FakeTransport(response);
    await selectAsset(tester, transport, opened);
    await tester.ensureVisible(find.text(externalTitle));
    await tester.tap(find.text(externalTitle));
    await tester.pumpAndSettle();
    expect(opened.map((u) => u.toString()), [
      'https://www.youtube.com/watch?v=daynomy1234',
    ]);
    expect(
      transport.requests.where((r) => r.path == '/api/news/910001'),
      isEmpty,
    );
  });

  for (final url in [
    'https://example.org/news/910001',
    'http://example.org/news/910001',
    '/help',
    '/news/910001?view=full#sources',
  ]) {
    test('원본이 허용하는 HTTP(S)/상대 URL의 decoder 경계를 임의 축소하지 않는다: $url', () async {
      final transport = FakeTransport(
        (r) => response(r, assetContents: contents(internalUrl: url)),
      );
      final value = await repository(transport).invoke(
        UserOperation.assetContents,
        params: {'assetId': '$assetId'},
      ) as Map;
      expect((value['contents'] as List).first['url'], url);
    });
  }

  for (final url in [
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    '//evil.example/news/910001',
  ]) {
    test('원본도 거절하는 INTERNAL_NEWS URL은 수용하지 않는다: $url', () async {
      final transport = FakeTransport(
        (r) => response(r, assetContents: contents(internalUrl: url)),
      );
      await expectLater(
        repository(transport).invoke(
          UserOperation.assetContents,
          params: {'assetId': '$assetId'},
        ),
        throwsFormatException,
      );
    });
  }

  for (final url in ['/news/0', '/news/not-a-number']) {
    testWidgets('유효한 URL이라도 잘못된 내부 뉴스 ID를 API나 launcher로 실행하지 않는다: $url', (
      tester,
    ) async {
      final opened = <Uri>[];
      final transport = FakeTransport(
        (r) => response(r, assetContents: contents(internalUrl: url)),
      );
      await selectAsset(tester, transport, opened);
      expect(find.text(internalTitle), findsOneWidget);
      await tester.ensureVisible(find.text(internalTitle));
      await tester.tap(find.text(internalTitle));
      await tester.pumpAndSettle();
      expect(opened, isEmpty);
      expect(
        transport.requests.where((r) => r.path.startsWith('/api/news/')),
        isEmpty,
      );
      expect(tester.takeException(), isNull);
    });
  }

  for (final url in [
    'javascript:alert(1)',
    'data:text/html,attack',
    '//evil.example/video',
  ]) {
    testWidgets('악성 외부자료는 UI로 표시하거나 launcher로 전송하지 않는다: $url', (
      tester,
    ) async {
      final opened = <Uri>[];
      final transport = FakeTransport(
        (r) => response(r, assetContents: contents(externalUrl: url)),
      );
      await selectAsset(tester, transport, opened);
      expect(find.text(externalTitle), findsNothing);
      expect(opened, isEmpty);
      expect(
        transport.requests.where((r) => r.path == '/api/news/910001'),
        isEmpty,
      );
      expect(tester.takeException(), isNull);
    });
  }
}
