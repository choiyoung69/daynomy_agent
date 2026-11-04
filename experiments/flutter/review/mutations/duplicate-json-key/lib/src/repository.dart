import 'api.dart';
import 'exact_json.dart';

Map<String, Object?> object(Object? v) {
  if (v is! Map<String, Object?>) throw const FormatException('응답 객체가 필요합니다.');
  return v;
}

List<Object?> array(Object? v) {
  if (v is! List<Object?>) throw const FormatException('응답 목록이 필요합니다.');
  return v;
}

void require(bool ok) {
  if (!ok) throw const FormatException('응답 필드 형식이 올바르지 않습니다.');
}

void strings(Map v, List<String> keys, {bool nullable = false}) {
  for (final key in keys) {
    require(
      v.containsKey(key) && (v[key] is String || nullable && v[key] == null),
    );
  }
}

void numbers(Map v, List<String> keys, {bool nullable = false}) {
  for (final key in keys) {
    require(
      v.containsKey(key) &&
          (v[key] is ExactNumber || nullable && v[key] == null),
    );
  }
}

void oneOf(Object? value, List<String> values, {bool nullable = false}) =>
    require(
      nullable && value == null || value is String && values.contains(value),
    );
void integers(Map v, List<String> keys, {bool nonnegative = true}) {
  for (final key in keys) {
    final n = integerValue(v[key]);
    require(!nonnegative || n >= BigInt.zero);
    require(n <= BigInt.parse('9007199254740991'));
  }
}

void entries(Object? v, void Function(Map<String, Object?>) check) {
  for (final item in array(v)) {
    check(object(item));
  }
}

const categories = [
  'REAL_ESTATE',
  'DEPOSIT_SAVINGS',
  'STOCK',
  'ECONOMY',
  'ETF',
  'BOND',
  'PENSION',
  'FOREIGN_EXCHANGE',
  'VIRTUAL_ASSET',
  'GOLD',
];
const markets = [
  'KOSPI',
  'KOSDAQ',
  'NASDAQ',
  'NYSE',
  'NYSE_ARCA',
  'NYSE_AMERICAN',
  'BATS',
];
String stockCurrency(Map v) => ['KRW', 'USD'].contains(v['currency'])
    ? v['currency'] as String
    : '${v['assetCode']}'.endsWith('.US')
    ? 'USD'
    : 'KRW';

class Stock {
  Stock(Map<String, Object?> data)
    : assetId = checkedId(data['assetId']),
      assetCode = data['assetCode'] as String,
      name = data['name'] as String,
      category = data['category'] as String,
      market = data['market'] as String,
      currency = stockCurrency(data);
  final int assetId;
  final String assetCode, name, category, market, currency;
  Map<String, Object?> toJson() => {
    'assetId': assetId,
    'assetCode': assetCode,
    'name': name,
    'category': category,
    'market': market,
    'currency': currency,
  };
}

void stock(Map<String, Object?> v) {
  checkedId(v['assetId']);
  strings(v, ['assetCode', 'name']);
  oneOf(v['category'], ['STOCK', 'ETF']);
  oneOf(v['market'], markets);
}

List<Stock> decodeStocks(String source) {
  final data = object(decodeJsonExact(source));
  return array(data['stocks']).map((v) {
    final m = object(v);
    stock(m);
    return Stock(m);
  }).toList();
}

class PriceQuote {
  PriceQuote(Map<String, Object?> data)
    : assetId = checkedId(data['assetId']),
      assetCode = data['assetCode'] as String,
      name = data['name'] as String,
      baseDate = data['baseDate'] as String,
      closePrice = data['closePrice'] as ExactNumber,
      currency = stockCurrency(data);
  final int assetId;
  final String assetCode, name, baseDate, currency;
  final ExactNumber closePrice;
}

PriceQuote decodePrice(String source) {
  final data = object(decodeJsonExact(source));
  checkedId(data['assetId']);
  strings(data, ['assetCode', 'name', 'baseDate']);
  numbers(data, ['closePrice']);
  return PriceQuote(data);
}

void holding(Map<String, Object?> v) {
  stock(v);
  checkedId(v['quantity']);
  numbers(v, ['averagePurchasePrice']);
  require(double.parse('${v['averagePurchasePrice']}') > 0);
}

void source(Map<String, Object?> v) {
  strings(v, ['title', 'url']);
  require(safeUrl(v['url']) != null);
  for (final k in ['publishedOn', 'occurredOn', 'factQuote', 'excerpt']) {
    if (v[k] != null) strings(v, [k]);
  }
}

void analysis(Map<String, Object?> v) {
  integers(v, ['totalAssetCount', 'analyzedAssetCount']);
  oneOf(v['overallDirection'], [
    'POSITIVE',
    'NEGATIVE',
    'NEUTRAL',
  ], nullable: true);
  numbers(v, ['overallScore'], nullable: true);
  numbers(v, ['positiveImpactScore', 'negativeImpactScore']);
  strings(v, ['analyzedAt'], nullable: true);
  strings(v, ['overallImpact']);
  if (v.containsKey('coverage'))
    oneOf(v['coverage'], ['COMPLETE', 'PARTIAL', 'INSUFFICIENT']);
  if (v.containsKey('analyzedWeight')) numbers(v, ['analyzedWeight']);
  entries(v['sources'], source);
  entries(v['impacts'], (a) {
    strings(a, [
      'assetName',
      'issueSummary',
      'expectedReaction',
      'outlook',
      'reason',
      'evidenceSentence',
    ]);
    numbers(a, ['weight']);
    oneOf(a['direction'], ['POSITIVE', 'NEGATIVE', 'NEUTRAL'], nullable: true);
    oneOf(a['impactLevel'], ['HIGH', 'MEDIUM', 'LOW'], nullable: true);
    require((a['direction'] == null) == (a['impactLevel'] == null));
    integers(a, ['rank']);
    entries(a['sources'], source);
  });
}

void savedAnalysis(Map<String, Object?> v) {
  oneOf(v['status'], [
    'EMPTY',
    'READY',
    'PORTFOLIO_CHANGED',
    'PROCESSING',
    'RECHECK_REQUIRED',
    'FAILED',
  ]);
  oneOf(v['lastCheckOutcome'], [
    'UPDATED',
    'UNCHANGED',
    'UNCONFIRMED',
  ], nullable: true);
  if (v['analysisId'] != null) checkedId(v['analysisId']);
  require(v['matchesCurrentPortfolio'] is bool);
  strings(v, [
    'lastSucceededAt',
    'lastFailedAt',
    'failureCode',
    'changeReason',
  ], nullable: true);
  require(v.containsKey('analysis'));
  if (v['analysis'] != null) analysis(object(v['analysis']));
}

void point(Map<String, Object?> v) {
  strings(v, ['baseDate']);
  numbers(v, [
    'totalPurchaseAmount',
    'totalEvaluationAmount',
    'totalProfitLoss',
    'totalReturnRate',
  ]);
  numbers(v, ['dailyProfitLoss', 'dailyReturnRate'], nullable: true);
}

void history(Map<String, Object?> v) {
  checkedId(v['historyId']);
  checkedId(v['assetId']);
  strings(v, ['assetCode', 'name', 'effectiveDate', 'occurredAt']);
  oneOf(v['changeType'], [
    'ADDED',
    'UPDATED',
    'REMOVED',
    'OPENING_BALANCE',
    'ADJUSTED',
    'BUY',
    'SELL',
  ]);
  numbers(v, ['quantity', 'averagePurchasePrice', 'fee', 'tax']);
  if (['BUY', 'SELL'].contains(v['changeType'])) {
    checkedId(v['transactionQuantity']);
    numbers(v, ['unitPrice']);
  } else {
    numbers(v, ['transactionQuantity', 'unitPrice'], nullable: true);
  }
  if ('${v['assetCode']}'.endsWith('.US')) {
    require(v['currency'] == 'USD');
    numbers(v, ['exchangeRate']);
    require(double.parse('${v['exchangeRate']}') > 0);
  }
}

void newsItem(Map<String, Object?> v) {
  checkedId(v['id']);
  strings(v, ['title']);
  oneOf(v['category'], categories);
  strings(v, ['imageUrl', 'publishedAt'], nullable: true);
}

void page(
  Map<String, Object?> v, {
  String key = 'items',
  required void Function(Map<String, Object?>) item,
  bool hasNext = false,
}) {
  entries(v[key], item);
  integers(v, ['page', 'size', 'totalElements', 'totalPages']);
  if (hasNext) require(v['hasNext'] is bool);
}

void contentItem(Map<String, Object?> v) {
  checkedId(v['id']);
  strings(v, ['title']);
  strings(v, ['date'], nullable: true);
  switch (v['kind']) {
    case 'NEWS':
      require(v['source'] == 'DAYNOMY');
      oneOf(v['category'], categories);
      strings(v, ['imageUrl'], nullable: true);
    case 'PERSON_POST':
      oneOf(v['source'], ['X', 'THREADS']);
      strings(v, ['url', 'personName']);
      checkedId(v['personId']);
    case 'ASSET_CONTENT':
      oneOf(v['source'], ['X', 'THREADS', 'YOUTUBE']);
      strings(v, ['url']);
      checkedId(v['assetId']);
      strings(v, ['imageUrl', 'publishedDate'], nullable: true);
    default:
      throw const FormatException('알 수 없는 콘텐츠입니다.');
  }
}

Uri? safeUrl(Object? raw) {
  if (raw is! String) return null;
  final u = Uri.tryParse(raw);
  return u != null &&
          ['http', 'https'].contains(u.scheme) &&
          u.host.isNotEmpty &&
          u.userInfo.isEmpty
      ? u
      : null;
}

void calendar(Map<String, Object?> v) {
  integers(v, ['year', 'month']);
  entries(v['events'], (e) {
    checkedId(e['id']);
    oneOf(e['type'], ['US_CPI', 'KOREA_BASE_RATE', 'CORPORATE_EARNINGS']);
    strings(e, ['title', 'announcedAt']);
    numbers(e, ['daysUntil']);
    require(e['upcoming'] is bool);
    final value = object(e['value']);
    numbers(value, ['previousValue', 'actualValue'], nullable: true);
    strings(value, ['unit']);
    oneOf(value['direction'], [
      'DECREASED',
      'UNCHANGED',
      'INCREASED',
      'UNAVAILABLE',
    ]);
    strings(object(e['source']), ['name', 'url']);
    final a = object(e['portfolioAnalysis']);
    oneOf(a['status'], ['READY', 'NO_PORTFOLIO', 'INSUFFICIENT_DATA']);
    oneOf(a['impactLevel'], ['LOW', 'MEDIUM', 'HIGH']);
    integers(a, ['relatedAssetCount']);
    numbers(a, ['totalEvaluationAmount']);
    strings(a, ['priceBaseDate'], nullable: true);
    entries(a['historicalReactions'], (r) {
      oneOf(r['direction'], ['DECREASED', 'UNCHANGED', 'INCREASED']);
      integers(r, ['sampleCount']);
      numbers(r, [
        'medianReturnRate',
        'lowerReturnRate',
        'upperReturnRate',
        'lowerEstimatedAmount',
        'upperEstimatedAmount',
      ], nullable: true);
    });
  });
}

enum UserOperation {
  stocks,
  price,
  exchangeRate,
  assetContents,
  calculate,
  guestAnalysis,
  portfolio,
  createTransaction,
  updateTransaction,
  deleteTransaction,
  updateHolding,
  deleteHolding,
  performance,
  histories,
  savedAnalysis,
  generateAnalysis,
  refreshAnalysis,
  analysisHistory,
  news,
  todayNews,
  newsDetail,
  newsKeywords,
  newsMarketAnalysis,
  searchNews,
  searchContents,
  contents,
  people,
  guestCalendar,
  memberCalendar,
  profile,
  updateProfile,
  withdraw,
  logout,
  feedback,
}

class AppRepository {
  AppRepository(this.client);
  final ApiClient client;
  Future<Object?> invoke(
    UserOperation op, {
    Map<String, String> params = const {},
    Object? body,
    CancellationToken? cancel,
  }) async {
    final query = <String, String>{};
    String method = 'GET';
    String path;
    String id(String key) {
      final raw = params[key];
      if (raw == null || !RegExp(r'^[1-9][0-9]*$').hasMatch(raw))
        throw const FormatException('잘못된 ID');
      return checkedId(ExactNumber(raw)).toString();
    }

    void add(List<String> names) {
      for (final k in names) {
        final v = params[k];
        if (v != null && v != 'ALL') query[k] = v;
      }
    }

    void range() {
      add(['from', 'to']);
      for (final k in ['from', 'to']) {
        if (query[k] != null) validDate(query[k]!);
      }
      if (query['from'] != null && query['to'] != null)
        require(query['from']!.compareTo(query['to']!) <= 0);
    }

    switch (op) {
      case UserOperation.stocks:
        path = '/api/stocks';
        add(['q']);
        if (params['country'] == 'US') query['country'] = 'US';
      case UserOperation.price:
        path = '/api/stocks/${id('assetId')}/price';
      case UserOperation.exchangeRate:
        path = '/api/exchange-rates/usd-krw';
        add(['date']);
        if (query['date'] != null) validDate(query['date']!);
      case UserOperation.assetContents:
        path = '/api/assets/${id('assetId')}/contents';
      case UserOperation.calculate:
        path = '/api/portfolio/calculate';
        method = 'POST';
      case UserOperation.guestAnalysis:
        path = '/api/portfolio/analysis';
        method = 'POST';
      case UserOperation.portfolio:
        path = '/api/users/me/portfolio';
      case UserOperation.createTransaction:
        path = '/api/portfolio/transactions';
        method = 'POST';
      case UserOperation.updateTransaction:
        path = '/api/portfolio/transactions/${id('transactionId')}';
        method = 'PATCH';
      case UserOperation.deleteTransaction:
        path = '/api/portfolio/transactions/${id('transactionId')}';
        method = 'DELETE';
      case UserOperation.updateHolding:
        path = '/api/users/me/portfolio/holdings/${id('assetId')}';
        method = 'PATCH';
      case UserOperation.deleteHolding:
        path = '/api/users/me/portfolio/holdings/${id('assetId')}';
        method = 'DELETE';
      case UserOperation.performance:
        path = '/api/users/me/portfolio/performance';
        range();
      case UserOperation.histories:
        path = '/api/portfolio/histories';
        range();
      case UserOperation.savedAnalysis:
        path = '/api/users/me/portfolio/analysis';
      case UserOperation.generateAnalysis:
        path = '/api/users/me/portfolio/analysis';
        method = 'POST';
      case UserOperation.refreshAnalysis:
        path = '/api/users/me/portfolio/analysis/refresh';
        method = 'POST';
      case UserOperation.analysisHistory:
        path = '/api/users/me/portfolio/analysis/history';
      case UserOperation.news:
        path = '/api/news';
        add(['page', 'size', 'category']);
      case UserOperation.todayNews:
        path = '/api/news/today';
      case UserOperation.newsDetail:
        path = '/api/news/${id('newsId')}';
      case UserOperation.newsKeywords:
        path = '/api/news/${id('newsId')}/keywords';
      case UserOperation.newsMarketAnalysis:
        path = '/api/news/${id('newsId')}/market-analysis';
      case UserOperation.searchNews:
        path = '/api/search/news';
        add(['q', 'page', 'size', 'sort']);
      case UserOperation.searchContents:
        path = '/api/search/contents';
        add(['q', 'page', 'size', 'source']);
      case UserOperation.contents:
        path = '/api/contents';
        add(['page', 'size', 'source']);
      case UserOperation.people:
        path = '/api/people';
      case UserOperation.guestCalendar:
      case UserOperation.memberCalendar:
        path = op == UserOperation.guestCalendar
            ? '/api/investment-calendar'
            : '/api/users/me/investment-calendar';
        method = op == UserOperation.guestCalendar ? 'POST' : 'GET';
        final year = int.tryParse(params['year'] ?? ''),
            month = int.tryParse(params['month'] ?? '');
        require(
          year != null &&
              year >= 2000 &&
              year <= 2100 &&
              month != null &&
              month >= 1 &&
              month <= 12,
        );
        oneOf(params['scope'], ['ALL', 'PORTFOLIO']);
        add(['year', 'month']);
        query['scope'] = params['scope']!;
      case UserOperation.profile:
        path = '/api/users/me';
      case UserOperation.updateProfile:
        path = '/api/users/me';
        method = 'PATCH';
      case UserOperation.withdraw:
        path = '/api/users/me';
        method = 'DELETE';
      case UserOperation.logout:
        path = '/api/auth/logout';
        method = 'POST';
      case UserOperation.feedback:
        path = '/api/feedback';
        method = 'POST';
    }
    for (final key in ['page', 'size']) {
      if (query.containsKey(key))
        require(
          int.tryParse(query[key]!) != null && int.parse(query[key]!) > 0,
        );
    }
    final route = Uri(
      path: path,
      queryParameters: query.isEmpty ? null : query,
    ).toString();
    String? response;
    try {
      response = await client.request(
        route,
        method: method,
        body: body,
        csrf: method != 'GET',
        cancel: cancel,
      );
    } on ApiException catch (error) {
      if (op == UserOperation.histories &&
          error.status == 404 &&
          error.code == 'PORTFOLIO_NOT_FOUND')
        return <Object?>[];
      rethrow;
    }
    if ([
      UserOperation.deleteHolding,
      UserOperation.withdraw,
      UserOperation.logout,
      UserOperation.feedback,
    ].contains(op)) {
      require(response == null);
      return null;
    }
    if (response == null) throw const FormatException('응답 본문 누락');
    final value = decodeJsonExact(response);
    switch (op) {
      case UserOperation.stocks:
        decodeStocks(response);
      case UserOperation.price:
        decodePrice(response);
      case UserOperation.exchangeRate:
        final v = object(value);
        strings(v, ['baseDate']);
        numbers(v, ['rate']);
        require(double.parse('${v['rate']}') > 0);
      case UserOperation.portfolio:
        final v = object(value);
        entries(v['holdings'], holding);
        numbers(v, ['totalRealizedProfitLoss']);
      case UserOperation.updateHolding:
        holding(object(value));
      case UserOperation.createTransaction:
      case UserOperation.updateTransaction:
      case UserOperation.deleteTransaction:
        final v = object(value);
        checkedId(v['transactionId']);
        require(v.containsKey('holding'));
        if (v['holding'] != null) holding(object(v['holding']));
        numbers(v, ['totalRealizedProfitLoss']);
      case UserOperation.calculate:
        final v = object(value);
        strings(v, ['baseDate'], nullable: true);
        oneOf(v['pricingStatus'], ['COMPLETE', 'MIXED_DATES', 'PARTIAL']);
        integers(v, ['pricedHoldingCount', 'unpricedHoldingCount']);
        numbers(v, ['totalPurchaseAmount', 'totalEvaluationAmount']);
        numbers(v, [
          'dailyProfitLoss',
          'dailyReturnRate',
          'totalProfitLoss',
          'totalReturnRate',
        ], nullable: true);
        entries(v['holdings'], (h) {
          holding(h);
          numbers(h, ['purchaseAmount']);
          require(h['priceAvailable'] is bool);
          strings(h, ['baseDate'], nullable: h['priceAvailable'] == false);
          numbers(h, [
            'closePrice',
            'evaluationAmount',
            'profitLoss',
            'returnRate',
            'weight',
          ], nullable: h['priceAvailable'] == false);
          if (h['priceAvailable'] == false)
            require(
              [
                'baseDate',
                'closePrice',
                'evaluationAmount',
                'profitLoss',
                'returnRate',
                'weight',
              ].every((k) => h[k] == null),
            );
        });
        entries(v['marketAllocations'], (a) {
          oneOf(a['market'], markets);
          numbers(a, ['evaluationAmount', 'weight']);
        });
      case UserOperation.guestAnalysis:
        analysis(object(value));
      case UserOperation.savedAnalysis:
      case UserOperation.generateAnalysis:
      case UserOperation.refreshAnalysis:
        savedAnalysis(object(value));
      case UserOperation.analysisHistory:
        entries(value, (v) {
          checkedId(v['analysisId']);
          strings(v, ['analyzedAt']);
          strings(v, ['changeReason'], nullable: true);
          if (v['previousAnalysisId'] != null)
            checkedId(v['previousAnalysisId']);
          if (v['analysis'] != null) analysis(object(v['analysis']));
        });
      case UserOperation.performance:
        final v = object(value);
        oneOf(v['status'], ['READY', 'INSUFFICIENT_DATA']);
        oneOf(v['reason'], ['SNAPSHOT_DATA_INSUFFICIENT'], nullable: true);
        strings(v, ['baseDate', 'previousBaseDate'], nullable: true);
        entries(v['points'], point);
        require(v.containsKey('currentPoint'));
        if (v['currentPoint'] != null) {
          final p = object(v['currentPoint']);
          point(p);
          strings(p, ['priceBaseDate'], nullable: true);
        }
      case UserOperation.histories:
        entries(value, history);
      case UserOperation.news:
      case UserOperation.todayNews:
        page(object(value), item: newsItem, hasNext: true);
      case UserOperation.newsDetail:
        final v = object(value);
        checkedId(v['id']);
        strings(v, ['title', 'publishedAt']);
        oneOf(v['category'], categories);
        require(
          v['content'] is String ||
              v['content'] is List &&
                  (v['content'] as List).every((e) => e is String),
        );
        entries(v['sources'], (s) => strings(s, ['name', 'url']));
        if (v['imageSource'] != null) {
          final s = object(v['imageSource']);
          strings(s, ['name', 'url', 'author', 'license', 'licenseUrl']);
          oneOf(s['type'], ['NONE', 'AI_GENERATED', 'WIKIMEDIA', 'MANUAL']);
        }
      case UserOperation.newsKeywords:
        entries(object(value)['keywords'], (k) {
          strings(k, ['keyword', 'definition', 'context', 'watchPoint']);
          oneOf(k['category'], ['PERSON', 'POLICY', 'EVENT', 'TERM', 'TREND']);
        });
      case UserOperation.newsMarketAnalysis:
        strings(object(value), ['risk', 'watchPoint']);
      case UserOperation.searchNews:
        page(object(value), key: 'content', item: newsItem);
      case UserOperation.contents:
      case UserOperation.searchContents:
        page(object(value), item: contentItem);
      case UserOperation.assetContents:
        final v = object(value);
        checkedId(v['assetId']);
        strings(v, ['assetCode', 'assetName']);
        entries(v['contents'], (c) {
          checkedId(c['id']);
          checkedId(c['assetId']);
          oneOf(c['sourceType'], [
            'YOUTUBE',
            'THREADS',
            'X',
            'INTERNAL_NEWS',
            'OTHER',
          ]);
          strings(c, ['title', 'url']);
          require(safeUrl(c['url']) != null);
          strings(c, ['imageUrl', 'createdAt'], nullable: true);
        });
      case UserOperation.people:
        entries(object(value)['people'], (p) {
          checkedId(p['id']);
          strings(p, ['name']);
          strings(p, [
            'xProfileUrl',
            'threadsProfileUrl',
            'createdAt',
          ], nullable: true);
          entries(p['posts'], (p) {
            checkedId(p['id']);
            strings(p, ['title', 'url']);
            oneOf(p['sourceType'], ['X', 'THREADS', 'YOUTUBE']);
            strings(p, ['createdAt'], nullable: true);
          });
        });
      case UserOperation.guestCalendar:
      case UserOperation.memberCalendar:
        calendar(object(value));
      case UserOperation.profile:
      case UserOperation.updateProfile:
        final v = object(value);
        checkedId(v['id']);
        strings(v, ['email', 'nickname']);
        if (v.containsKey('name')) strings(v, ['name'], nullable: true);
        oneOf(v['role'], ['USER', 'ADMIN']);
      case UserOperation.withdraw:
      case UserOperation.logout:
      case UserOperation.feedback:
      case UserOperation.deleteHolding:
        break;
    }
    return value;
  }
}

void validDate(String text) {
  final value = DateTime.tryParse(text);
  require(
    RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text) &&
        value != null &&
        '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}' ==
            text,
  );
}
