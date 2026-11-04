import 'dart:async';

import 'package:flutter/material.dart' hide SearchController;

import 'api.dart';
import 'exact_json.dart';
import 'repository.dart';
import 'search.dart';

typedef JsonMap = Map<String, Object?>;
String valueText(Object? value) => value == null ? '확인되지 않음' : value.toString();
String today() =>
    dateText(DateTime.now().toUtc().add(const Duration(hours: 9)));
String dateText(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
String errorText(Object? error) => error is ApiException
    ? error.message
    : error is FormatException
    ? '서버 응답 형식을 확인하지 못했습니다.'
    : error is TimeoutException
    ? '응답 시간이 초과되었습니다.'
    : '불러오지 못했습니다. 연결을 확인해주세요.';
Widget heading(String title, {String? subtitle}) => Padding(
  padding: const EdgeInsets.only(top: 8, bottom: 24),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
      ),
      if (subtitle != null)
        Padding(padding: const EdgeInsets.only(top: 8), child: Text(subtitle)),
    ],
  ),
);
Widget notice(String text, {Key? key, bool error = false}) => Builder(
  builder: (context) => Semantics(
    liveRegion: true,
    child: Padding(
      key: key,
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 16,
          color: error ? Theme.of(context).colorScheme.error : null,
        ),
      ),
    ),
  ),
);
Widget action(
  String text,
  VoidCallback? onPressed, {
  String? key,
  IconData? icon,
}) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 4),
  child: FilledButton.tonalIcon(
    key: key == null ? null : ValueKey(key),
    onPressed: onPressed,
    icon: Icon(icon ?? Icons.arrow_forward, size: 20),
    label: Text(text),
  ),
);
Widget input(
  String label,
  TextEditingController controller, {
  String? key,
  ValueChanged<String>? onChanged,
  bool decimal = false,
  int lines = 1,
}) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 8),
  child: TextFormField(
    key: key == null ? null : ValueKey(key),
    controller: controller,
    onChanged: onChanged,
    keyboardType: decimal
        ? const TextInputType.numberWithOptions(decimal: true)
        : null,
    minLines: lines,
    maxLines: lines,
    decoration: InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
      alignLabelWithHint: lines > 1,
    ),
  ),
);
Widget section(String title, List<Widget> children) => Padding(
  padding: const EdgeInsets.only(bottom: 24),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        title,
        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 12),
      ...children,
    ],
  ),
);
ExactNumber money(String raw, {int scale = 4, bool positive = false}) {
  final text = raw.trim();
  require(RegExp('^[0-9]+(?:\\.[0-9]{1,$scale})?\$').hasMatch(text));
  require(text.split('.').first.replaceFirst(RegExp(r'^0+'), '').length <= 15);
  final n = ExactNumber(text);
  if (positive) require(double.parse(text) > 0);
  return n;
}

class DaynomyApp extends StatelessWidget {
  const DaynomyApp({
    super.key,
    required this.repository,
    this.onLogin,
    this.onOpenLink,
    this.onSessionCleared,
  });
  final AppRepository repository;
  final Future<void> Function()? onLogin;
  final Future<void> Function(Uri)? onOpenLink;
  final VoidCallback? onSessionCleared;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'DAYNOMY',
    debugShowCheckedModeBanner: false,
    themeMode: ThemeMode.system,
    theme: _theme(Brightness.light),
    darkTheme: _theme(Brightness.dark),
    home: _Home(
      repository: repository,
      onLogin: onLogin,
      onOpenLink: onOpenLink,
      onSessionCleared: onSessionCleared,
    ),
  );
  ThemeData _theme(Brightness brightness) {
    final colors = ColorScheme.fromSeed(
      seedColor: const Color(0xff2458c8),
      brightness: brightness,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: colors,
      scaffoldBackgroundColor: brightness == Brightness.light
          ? const Color(0xfff7f8fa)
          : const Color(0xff10151e),
      textTheme: Typography.material2021(platform: TargetPlatform.android).black
          .apply(bodyColor: colors.onSurface, displayColor: colors.onSurface),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        contentPadding: EdgeInsets.all(16),
      ),
    );
  }
}

class _Home extends StatefulWidget {
  const _Home({
    required this.repository,
    this.onLogin,
    this.onOpenLink,
    this.onSessionCleared,
  });
  final AppRepository repository;
  final Future<void> Function()? onLogin;
  final Future<void> Function(Uri)? onOpenLink;
  final VoidCallback? onSessionCleared;
  @override
  State<_Home> createState() => _HomeState();
}

class _HomeState extends State<_Home> {
  int tab = 0, epoch = 0;
  JsonMap? profile;
  Object? profileError;
  bool booting = true;
  Stock? selected;
  final guest = <JsonMap>[];
  late final SearchController search = SearchController(widget.repository);
  static const names = ['search', 'portfolio', 'news', 'calendar', 'profile'];
  static const labels = ['검색', '포트폴리오', '뉴스', '캘린더', '내 정보'];
  static const icons = [
    Icons.search_outlined,
    Icons.account_balance_wallet_outlined,
    Icons.article_outlined,
    Icons.calendar_month_outlined,
    Icons.person_outline,
  ];
  @override
  void initState() {
    super.initState();
    widget.repository.client.onAuthenticationLost = () {
      if (mounted && profile != null) cleared();
    };
    bootstrap();
  }

  Future<void> bootstrap() async {
    try {
      final data = object(
        await widget.repository.invoke(UserOperation.profile),
      );
      if (!mounted) return;
      setState(() {
        profile = data;
        profileError = null;
        booting = false;
        epoch++;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        profile = null;
        profileError = e is ApiException && e.status == 401 ? null : e;
        booting = false;
        epoch++;
      });
    }
  }

  void cleared() {
    if (!mounted) return;
    widget.repository.client.clearSession();
    widget.onSessionCleared?.call();
    search.suspend();
    search.query('');
    search.setManualPrice('');
    search.draftQuantity = '1';
    search.guestAverageKrw.clear();
    setState(() {
      profile = null;
      profileError = null;
      selected = null;
      guest.clear();
      epoch++;
    });
  }

  @override
  void dispose() {
    widget.repository.client.onAuthenticationLost = null;
    search.dispose();
    super.dispose();
  }

  Future<void> link(Object? raw) async {
    final uri = safeUrl(raw);
    if (uri == null) return;
    try {
      await widget.onOpenLink?.call(uri);
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('링크를 열지 못했습니다.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      _SearchPage(
        key: const ValueKey('search-root'),
        search: search,
        selected: selected,
        onSelect: (s) => setState(() => selected = s),
        onAdd: (h) => setState(() {
          guest.removeWhere((v) => v['assetId'] == h['assetId']);
          guest.add(h);
        }),
        isMember: profile != null,
        repository: widget.repository,
        onLink: link,
      ),
      _PortfolioPage(
        key: ValueKey('portfolio-$epoch'),
        repository: widget.repository,
        member: profile != null,
        guest: guest,
        selected: selected,
        selectedPrice: search.priceText,
        onGuestChanged: () => setState(() {}),
        onLink: link,
      ),
      _NewsPage(
        key: const ValueKey('news-root'),
        repository: widget.repository,
        onLink: link,
      ),
      _CalendarPage(
        key: ValueKey('calendar-$epoch'),
        repository: widget.repository,
        member: profile != null,
        guest: guest,
        onLink: link,
      ),
      _ProfilePage(
        key: ValueKey('profile-$epoch'),
        repository: widget.repository,
        profile: profile,
        profileError: profileError,
        onProfile: (p) => setState(() => profile = p),
        onClear: cleared,
        onRetry: bootstrap,
        onLogin: () async {
          await widget.onLogin?.call();
          await bootstrap();
        },
      ),
    ];
    final content = booting
        ? const Center(child: CircularProgressIndicator())
        : pages[tab];
    void select(int i) {
      if (i != tab) {
        if (tab == 0) search.suspend();
        setState(() => tab = i);
      }
    }

    return LayoutBuilder(
      builder: (context, size) {
        final wide = size.maxWidth >= 900;
        return Scaffold(
          appBar: AppBar(
            title: const Text(
              'DAYNOMY',
              style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 1.2),
            ),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Center(
                  child: Text(
                    profile == null ? '게스트' : '${profile!['nickname']}',
                  ),
                ),
              ),
            ],
          ),
          body: SafeArea(
            child: Row(
              children: [
                if (wide)
                  NavigationRail(
                    selectedIndex: tab,
                    onDestinationSelected: select,
                    labelType: NavigationRailLabelType.all,
                    destinations: List.generate(
                      5,
                      (i) => NavigationRailDestination(
                        icon: Icon(icons[i], key: ValueKey('nav-${names[i]}')),
                        label: Text(labels[i]),
                      ),
                    ),
                  ),
                Expanded(child: content),
              ],
            ),
          ),
          bottomNavigationBar: wide
              ? null
              : NavigationBar(
                  selectedIndex: tab,
                  onDestinationSelected: select,
                  destinations: List.generate(
                    5,
                    (i) => NavigationDestination(
                      key: ValueKey('nav-${names[i]}'),
                      icon: Icon(icons[i]),
                      label: labels[i],
                    ),
                  ),
                ),
        );
      },
    );
  }
}

Widget pageBody(String key, List<Widget> children) => SingleChildScrollView(
  key: ValueKey('page-$key'),
  padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
  child: Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 960),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  ),
);

class _SearchPage extends StatefulWidget {
  const _SearchPage({
    super.key,
    required this.search,
    required this.selected,
    required this.onSelect,
    required this.onAdd,
    required this.isMember,
    required this.repository,
    required this.onLink,
  });
  final SearchController search;
  final Stock? selected;
  final ValueChanged<Stock> onSelect;
  final ValueChanged<JsonMap> onAdd;
  final bool isMember;
  final AppRepository repository;
  final Future<void> Function(Object?) onLink;
  @override
  State<_SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<_SearchPage> {
  final query = TextEditingController(),
      price = TextEditingController(),
      quantity = TextEditingController(text: '1'),
      averageKrw = TextEditingController();
  Object? formError;
  bool added = false;
  @override
  void initState() {
    super.initState();
    widget.search.addListener(changed);
    price.text = widget.search.priceText;
    query.text = widget.search.queryText;
    quantity.text = widget.search.draftQuantity;
    averageKrw.text =
        widget.search.guestAverageKrw[widget.selected?.assetId] ?? '';
  }

  void changed() {
    if (!mounted) return;
    if (price.text != widget.search.priceText)
      price.text = widget.search.priceText;
    setState(() {});
  }

  @override
  void dispose() {
    widget.search.removeListener(changed);
    query.dispose();
    price.dispose();
    quantity.dispose();
    averageKrw.dispose();
    super.dispose();
  }

  void add() {
    try {
      final s = widget.selected!;
      final h = <String, Object?>{
        ...s.toJson(),
        'quantity': checkedId(ExactNumber(quantity.text.trim())),
        'averagePurchasePrice': money(
          s.currency == 'USD' ? averageKrw.text : price.text,
          scale: 2,
          positive: true,
        ),
      };
      widget.onAdd(h);
      setState(() {
        added = true;
        formError = null;
      });
    } catch (e) {
      setState(() => formError = '수량은 양의 정수, 평균 매입가는 소수점 2자리 이내의 양수로 입력해주세요.');
    }
  }

  Future<void> openRelatedContent(JsonMap content) async {
    final raw = (content['url'] as String).trim();
    if (content['sourceType'] == 'INTERNAL_NEWS') {
      final match = RegExp(r'^/news/([1-9][0-9]*)$').firstMatch(raw);
      if (match != null) {
        int? id;
        try {
          id = checkedId(ExactNumber(match[1]!));
        } on FormatException {
          // Keep a valid URL visible without sending an invalid API ID.
        }
        if (id != null) {
          await Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (context) => _NewsDetail(
                repository: widget.repository,
                id: id!,
                onLink: widget.onLink,
              ),
            ),
          );
          return;
        }
      }
    }
    if (safeUrl(raw) != null) {
      await widget.onLink(raw);
      return;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('이 관련 자료의 앱 경로는 아직 지원하지 않습니다.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.search;
    return pageBody('search', [
      heading(
        '종목을 찾고, 흐름을 읽어요',
        subtitle: '국내·미국 주식과 ETF를 검색하세요. 가격은 최근 저장 종가입니다.',
      ),
      input(
        '종목명 또는 코드',
        query,
        key: 'stock-query',
        onChanged: (q) {
          added = false;
          s.query(q);
        },
      ),
      Wrap(
        spacing: 12,
        runSpacing: 8,
        children: [
          DropdownButton<String>(
            value: s.country,
            items: const [
              DropdownMenuItem(value: 'KR', child: Text('한국')),
              DropdownMenuItem(value: 'US', child: Text('미국')),
            ],
            onChanged: (v) => s.updateFilters(country: v),
          ),
          DropdownButton<String>(
            value: s.category,
            items: const [
              DropdownMenuItem(value: 'ALL', child: Text('전체 유형')),
              DropdownMenuItem(value: 'STOCK', child: Text('주식')),
              DropdownMenuItem(value: 'ETF', child: Text('ETF')),
            ],
            onChanged: (v) => s.updateFilters(category: v),
          ),
        ],
      ),
      if (s.loading)
        const LinearProgressIndicator(key: ValueKey('search-loading')),
      if (s.error != null) ...[
        notice(
          errorText(s.error),
          key: const ValueKey('search-error'),
          error: true,
        ),
        action('다시 검색', () => s.query(query.text), key: 'search-retry'),
      ],
      if (!s.loading && s.error == null && s.stocks.isEmpty)
        notice(
          query.text.trim().isEmpty ? '검색어를 입력해주세요.' : '검색 결과가 없습니다.',
          key: const ValueKey('search-empty'),
        ),
      ...s.stocks.map(
        (stock) => ListTile(
          key: ValueKey('stock-${stock.assetId}'),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 4,
            vertical: 8,
          ),
          title: Text(stock.name),
          subtitle: Text(
            '${stock.assetCode} · ${stock.market} · ${stock.category}',
          ),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            widget.onSelect(stock);
            averageKrw.text = s.guestAverageKrw[stock.assetId] ?? '';
            added = false;
            s.selectStock(stock);
          },
        ),
      ),
      if (widget.selected != null) ...[
        const Divider(height: 32),
        heading(
          widget.selected!.name,
          subtitle: '${widget.selected!.market} · ${widget.selected!.currency}',
        ),
        if (s.quote != null)
          notice('최근 저장 종가 · ${s.quote!.baseDate} · ${s.quote!.currency}'),
        input(
          widget.isMember || widget.selected!.currency == 'USD'
              ? '참고 종가 (${widget.selected!.currency})'
              : '평균 매입가 (KRW, 최대 소수 2자리)',
          price,
          key: 'price-input',
          decimal: true,
          onChanged: s.setManualPrice,
        ),
        if (widget.isMember)
          notice('포트폴리오에서 선택한 종목의 매수·매도를 기록할 수 있습니다.')
        else ...[
          if (widget.selected!.currency == 'USD') ...[
            notice('USD 참고 종가는 원화 원가로 사용하지 않습니다. 실제 KRW 평균 매입가를 입력해주세요.'),
            input(
              '평균 매입가 (KRW, 최대 소수 2자리)',
              averageKrw,
              key: 'holding-average-krw',
              decimal: true,
              onChanged: (value) =>
                  s.guestAverageKrw[widget.selected!.assetId] = value,
            ),
          ],
          input(
            '보유 수량',
            quantity,
            key: 'holding-quantity',
            decimal: true,
            onChanged: (v) => s.draftQuantity = v,
          ),
          if (formError != null) notice('$formError', error: true),
          action('게스트 보유에 추가', add, key: 'holding-add', icon: Icons.add),
          if (added) notice('이 기기의 게스트 초안에 추가했습니다. 포트폴리오에서 확인하세요.'),
        ],
        DataPanel(
          repository: widget.repository,
          operation: UserOperation.assetContents,
          params: {'assetId': '${widget.selected!.assetId}'},
          identity: 'asset-${widget.selected!.assetId}',
          builder: (v) => section('종목 관련 자료', [
            if (array(object(v)['contents']).isEmpty) notice('등록된 자료가 없습니다.'),
            ...array(object(v)['contents']).map((c) {
              final m = object(c);
              return ListTile(
                title: Text('${m['title']}'),
                subtitle: Text('${m['sourceType']}'),
                onTap: () => openRelatedContent(m),
              );
            }),
          ]),
        ),
      ],
    ]);
  }
}

class DataPanel extends StatefulWidget {
  const DataPanel({
    super.key,
    required this.repository,
    required this.operation,
    this.params = const {},
    this.body,
    required this.identity,
    required this.builder,
  });
  final AppRepository repository;
  final UserOperation operation;
  final Map<String, String> params;
  final Object? body;
  final String identity;
  final Widget Function(Object?) builder;
  @override
  State<DataPanel> createState() => _DataPanelState();
}

class _DataPanelState extends State<DataPanel> {
  Object? data, error;
  bool loading = true;
  CancellationToken? cancel;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void didUpdateWidget(DataPanel old) {
    super.didUpdateWidget(old);
    if (old.identity != widget.identity) load();
  }

  Future<void> load() async {
    cancel?.cancel();
    cancel = CancellationToken();
    final g = ++generation;
    setState(() {
      loading = true;
      error = null;
      data = null;
    });
    try {
      final v = await widget.repository.invoke(
        widget.operation,
        params: widget.params,
        body: widget.body,
        cancel: cancel,
      );
      if (mounted && g == generation) setState(() => data = v);
    } catch (e) {
      if (mounted && g == generation) setState(() => error = e);
    } finally {
      if (mounted && g == generation) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    generation++;
    cancel?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (loading)
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: CircularProgressIndicator()),
      );
    if (error != null)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          notice(errorText(error), error: true),
          action('다시 불러오기', load),
        ],
      );
    return widget.builder(data);
  }
}

class _PortfolioPage extends StatefulWidget {
  const _PortfolioPage({
    super.key,
    required this.repository,
    required this.member,
    required this.guest,
    required this.selected,
    required this.selectedPrice,
    required this.onGuestChanged,
    required this.onLink,
  });
  final AppRepository repository;
  final bool member;
  final List<JsonMap> guest;
  final Stock? selected;
  final String selectedPrice;
  final VoidCallback onGuestChanged;
  final Future<void> Function(Object?) onLink;
  @override
  State<_PortfolioPage> createState() => _PortfolioPageState();
}

class _PortfolioPageState extends State<_PortfolioPage> {
  JsonMap? saved, calculated, ai;
  List<Object?> histories = [];
  Object? loadError, writeError;
  bool loading = false, busy = false;
  int version = 0;
  CancellationToken? cancel;
  int assessmentGeneration = 0;
  CancellationToken? assessmentCancel;
  final from = TextEditingController(
        text: dateText(DateTime.now().subtract(const Duration(days: 30))),
      ),
      to = TextEditingController(text: today());
  @override
  void initState() {
    super.initState();
    if (widget.member) load();
  }

  @override
  void dispose() {
    assessmentGeneration++;
    assessmentCancel?.cancel();
    cancel?.cancel();
    from.dispose();
    to.dispose();
    super.dispose();
  }

  Future<void> load() async {
    cancel?.cancel();
    final token = cancel = CancellationToken();
    final gen = ++version;
    setState(() {
      loading = true;
      loadError = null;
      saved = null;
      histories = [];
    });
    try {
      final portfolio = object(
        await widget.repository.invoke(UserOperation.portfolio, cancel: token),
      );
      if (mounted && gen == version) setState(() => saved = portfolio);
      final history = array(
        await widget.repository.invoke(
          UserOperation.histories,
          params: {'from': from.text, 'to': to.text},
          cancel: token,
        ),
      );
      if (mounted && gen == version)
        setState(() {
          saved = portfolio;
          histories = history;
        });
    } catch (e) {
      if (mounted && gen == version) setState(() => loadError = e);
    } finally {
      if (mounted && gen == version) setState(() => loading = false);
    }
  }

  List<JsonMap> get holdings => widget.member
      ? array(saved?['holdings'] ?? []).map(object).toList()
      : widget.guest;
  List<JsonMap> get requestHoldings => holdings
      .map(
        (h) => <String, Object?>{
          'assetId': h['assetId'],
          'quantity': h['quantity'],
          'averagePurchasePrice': h['averagePurchasePrice'],
        },
      )
      .toList();
  bool currentAssessment(
    int generation,
    CancellationToken token,
    String snapshot,
  ) =>
      mounted &&
      generation == assessmentGeneration &&
      !token.isCancelled &&
      encodeJsonExact(requestHoldings) == snapshot;

  Future<void> calculate() async {
    if (busy) return;
    assessmentCancel?.cancel();
    final token = assessmentCancel = CancellationToken();
    final generation = ++assessmentGeneration;
    final inputs = requestHoldings;
    final snapshot = encodeJsonExact(inputs);
    setState(() {
      busy = true;
      writeError = null;
    });
    try {
      final result = await calculateForAnalysis(inputs, token);
      if (!currentAssessment(generation, token, snapshot)) return;
      setState(() => calculated = result);
    } catch (error) {
      if (currentAssessment(generation, token, snapshot)) {
        setState(() => writeError = error);
      }
    } finally {
      if (mounted && generation == assessmentGeneration) {
        setState(() => busy = false);
      }
    }
  }

  Future<void> analyze({bool refresh = false}) async {
    if (busy) return;
    assessmentCancel?.cancel();
    final token = assessmentCancel = CancellationToken();
    final generation = ++assessmentGeneration;
    final inputs = requestHoldings;
    final snapshot = encodeJsonExact(inputs);
    setState(() {
      busy = true;
      writeError = null;
    });
    try {
      if (widget.member) {
        final result = object(
          await widget.repository.invoke(
            refresh
                ? UserOperation.refreshAnalysis
                : UserOperation.generateAnalysis,
            cancel: token,
          ),
        );
        if (!currentAssessment(generation, token, snapshot)) return;
        setState(() => ai = result);
      } else {
        final calculation = await calculateForAnalysis(inputs, token);
        if (!currentAssessment(generation, token, snapshot)) return;
        setState(() => calculated = calculation);
        final priced = array(calculation['holdings'])
            .map(object)
            .where((holding) => holding['weight'] != null);
        final assets = priced
            .map(
              (holding) => <String, Object?>{
                'assetName': holding['name'],
                'weight': holding['weight'],
              },
            )
            .toList();
        // A late calculation must never start a new trial-consuming POST after
        // leaving this screen or changing the holdings used by the calculation.
        if (!currentAssessment(generation, token, snapshot)) return;
        final result = object(
          await widget.repository.invoke(
            UserOperation.guestAnalysis,
            body: {'assets': assets},
            cancel: token,
          ),
        );
        if (!currentAssessment(generation, token, snapshot)) return;
        setState(() => ai = result);
      }
    } catch (error) {
      if (currentAssessment(generation, token, snapshot)) {
        setState(() => writeError = error);
      }
    } finally {
      if (mounted && generation == assessmentGeneration) {
        setState(() => busy = false);
      }
    }
  }

  Future<JsonMap> calculateForAnalysis(
    List<JsonMap> inputs,
    CancellationToken token,
  ) async => object(
    await widget.repository.invoke(
      UserOperation.calculate,
      body: {'holdings': inputs},
      cancel: token,
    ),
  );

  Future<void> transaction({JsonMap? history}) async {
    if (history == null && widget.selected == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('검색에서 종목을 먼저 선택해주세요.')));
      return;
    }
    final result = await showDialog<bool>(
      context: context,
      builder: (c) => _TransactionDialog(
        repository: widget.repository,
        stock: widget.selected,
        initialPrice: widget.selectedPrice,
        history: history,
      ),
    );
    if (result == true && mounted) {
      ai = null;
      calculated = null;
      await load();
    }
  }

  Future<void> deleteTransaction(JsonMap h) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('거래를 삭제할까요?'),
        content: const Text('삭제 후 서버에서 보유와 거래 내역을 다시 계산합니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('취소'),
          ),
          FilledButton(
            key: const ValueKey('transaction-delete-confirm'),
            onPressed: () => Navigator.pop(c, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    setState(() => busy = true);
    try {
      await widget.repository.invoke(
        UserOperation.deleteTransaction,
        params: {'transactionId': '${h['historyId']}'},
      );
      if (mounted) await load();
    } catch (e) {
      if (mounted) setState(() => writeError = e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> editHolding(JsonMap h) async {
    final result = await showDialog<JsonMap>(
      context: context,
      builder: (c) => _HoldingDialog(holding: h),
    );
    if (result == null) return;
    if (widget.member) {
      setState(() => busy = true);
      try {
        await widget.repository.invoke(
          UserOperation.updateHolding,
          params: {'assetId': '${h['assetId']}'},
          body: result,
        );
        if (mounted) await load();
      } catch (e) {
        if (mounted) setState(() => writeError = e);
      } finally {
        if (mounted) setState(() => busy = false);
      }
    } else {
      h.addAll(result);
      widget.onGuestChanged();
      setState(() {
        calculated = null;
        ai = null;
      });
    }
  }

  Future<void> removeHolding(JsonMap h) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text('${h['name']} 보유 삭제'),
        content: const Text('보유 항목을 삭제할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (yes != true) return;
    if (widget.member) {
      setState(() => busy = true);
      try {
        await widget.repository.invoke(
          UserOperation.deleteHolding,
          params: {'assetId': '${h['assetId']}'},
        );
        if (mounted) await load();
      } catch (e) {
        if (mounted) setState(() => writeError = e);
      } finally {
        if (mounted) setState(() => busy = false);
      }
    } else {
      widget.guest.remove(h);
      widget.onGuestChanged();
      setState(() {
        calculated = null;
        ai = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) => pageBody('portfolio', [
    heading(
      '나의 포트폴리오',
      subtitle: widget.member
          ? '회원 원장 · 기록한 거래와 보유 현황'
          : '게스트 초안 · 앱을 닫으면 사라지며 회원 원장에 저장되지 않습니다.',
    ),
    if (!widget.member) const SizedBox(key: ValueKey('guest-portfolio')),
    if (loading) const LinearProgressIndicator(),
    if (loadError != null) ...[
      notice(errorText(loadError), error: true),
      action('보유·거래 다시 조회', load),
    ],
    if (!loading && loadError == null && holdings.isEmpty)
      notice('보유 자산이 없습니다. 검색에서 종목을 선택해주세요.'),
    ...holdings.map(
      (h) => Padding(
        key: ValueKey('holding-${h['assetId']}'),
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${h['name']}',
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 19),
            ),
            Text('${h['quantity']}주 · 평균 ${h['averagePurchasePrice']} KRW'),
            Wrap(
              spacing: 8,
              children: [
                action(
                  '보유 수정',
                  busy ? null : () => editHolding(h),
                  icon: Icons.edit_outlined,
                ),
                action(
                  '보유 삭제',
                  busy ? null : () => removeHolding(h),
                  icon: Icons.delete_outline,
                ),
              ],
            ),
          ],
        ),
      ),
    ),
    if (widget.member)
      action(
        '매수·매도 기록',
        busy ? null : () => transaction(),
        key: 'transaction-add',
        icon: Icons.add,
      ),
    if (busy) const LinearProgressIndicator(),
    if (writeError != null) ...[
      notice(
        '${errorText(writeError)} 변경 요청의 처리 여부가 불확실하면 재전송 전에 목록을 다시 조회해주세요.',
        error: true,
      ),
      if (widget.member) action('목록 재조회', load),
    ],
    Wrap(
      spacing: 12,
      runSpacing: 8,
      children: [
        action(
          '서버 평가 계산',
          busy ? null : calculate,
          key: widget.member ? 'member-calculate' : 'guest-calculate',
          icon: Icons.calculate_outlined,
        ),
        action(
          'AI 영향 분석',
          busy ? null : () => analyze(),
          key: widget.member ? 'member-analysis' : 'guest-analysis',
          icon: Icons.auto_awesome_outlined,
        ),
      ],
    ),
    if (calculated != null) _calculation(calculated!),
    if (ai != null) analysisView(ai!, widget.onLink),
    if (widget.member) ...[
      section('거래·성과 조회 기간', [
        input('시작일 (YYYY-MM-DD)', from),
        input('종료일 (YYYY-MM-DD)', to),
        action(
          '기간 적용',
          () => setState(() {
            load();
          }),
        ),
      ]),
      section('거래 이력', [
        if (histories.isEmpty && !loading && loadError == null)
          notice('조회 기간의 거래 이력이 없습니다.'),
        ...histories.map((raw) {
          final h = object(raw), id = checkedId(h['historyId']);
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${h['effectiveDate']} · ${h['name']} · ${h['changeType']}',
                ),
                Text(
                  '수량 ${valueText(h['transactionQuantity'] ?? h['quantity'])} · 가격 ${valueText(h['unitPrice'] ?? h['averagePurchasePrice'])}',
                ),
                if (['BUY', 'SELL'].contains(h['changeType']))
                  Wrap(
                    spacing: 8,
                    children: [
                      action(
                        '거래 수정',
                        busy ? null : () => transaction(history: h),
                        key: 'transaction-edit-$id',
                        icon: Icons.edit_outlined,
                      ),
                      action(
                        '거래 삭제',
                        busy ? null : () => deleteTransaction(h),
                        key: 'transaction-delete-$id',
                        icon: Icons.delete_outline,
                      ),
                    ],
                  ),
              ],
            ),
          );
        }),
      ]),
      DataPanel(
        repository: widget.repository,
        operation: UserOperation.performance,
        params: {'from': from.text, 'to': to.text},
        identity: 'performance-$version-${from.text}-${to.text}',
        builder: (v) {
          final data = object(v);
          return section('자산 추이', [
            notice(
              data['status'] == 'READY'
                  ? '서버 스냅샷 기준'
                  : '추이를 계산할 스냅샷 데이터가 부족합니다.',
            ),
            ...array(data['points']).map((p) {
              final m = object(p);
              return ListTile(
                title: Text('${m['baseDate']}'),
                subtitle: Text(
                  '평가 ${m['totalEvaluationAmount']}원 · 손익 ${m['totalProfitLoss']}원 · 수익률 ${m['totalReturnRate']}%',
                ),
              );
            }),
          ]);
        },
      ),
      DataPanel(
        repository: widget.repository,
        operation: UserOperation.savedAnalysis,
        identity: 'saved-analysis-$version',
        builder: (v) => section('저장된 AI 분석', [
          analysisView(object(v), widget.onLink),
          action('새 근거로 다시 확인', busy ? null : () => analyze(refresh: true)),
        ]),
      ),
      DataPanel(
        repository: widget.repository,
        operation: UserOperation.analysisHistory,
        identity: 'analysis-history-$version',
        builder: (v) => section('분석 이력', [
          if (array(v).isEmpty) notice('저장된 분석 이력이 없습니다.'),
          ...array(v).map((a) {
            final m = object(a);
            return ExpansionTile(
              title: Text('${m['analyzedAt']}'),
              subtitle: Text(valueText(m['changeReason'])),
              children: [
                if (m['analysis'] != null)
                  analysisView(object(m['analysis']), widget.onLink),
              ],
            );
          }),
        ]),
      ),
    ],
  ]);
}

Widget _calculation(JsonMap v) => section('서버 평가 결과', [
  if (v['pricingStatus'] == 'PARTIAL')
    notice(
      '일부 종가가 없어 전체 수익률을 계산하지 못했습니다.',
      key: const ValueKey('pricing-partial'),
    ),
  if (v['pricingStatus'] == 'MIXED_DATES') notice('종목별 종가 기준일이 다릅니다.'),
  Text('매입 ${v['totalPurchaseAmount']}원'),
  Text('평가 ${v['totalEvaluationAmount']}원'),
  Text(
    '손익 ${valueText(v['totalProfitLoss'])} · 수익률 ${valueText(v['totalReturnRate'])}',
  ),
  Text('기준일 ${valueText(v['baseDate'])}'),
  ...array(v['holdings']).map((h) {
    final m = object(h);
    return ListTile(
      title: Text('${m['name']}'),
      subtitle: Text(
        m['priceAvailable'] == true
            ? '${m['closePrice']} ${stockCurrency(m)} · ${m['baseDate']} · 손익 ${m['profitLoss']}'
            : '저장 종가 없음',
      ),
    );
  }),
]);
Widget analysisView(JsonMap data, Future<void> Function(Object?) onLink) {
  final v = data.containsKey('status') ? data['analysis'] : data;
  return Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (data.containsKey('status'))
        notice(
          '분석 상태: ${data['status']} · 현재 보유 일치: ${data['matchesCurrentPortfolio']}',
        ),
      if (data['failureCode'] != null) notice('분석 실패: ${data['failureCode']}'),
      if (v is JsonMap) ...[
        notice('${v['overallImpact']}'),
        Text(
          '분석 ${v['analyzedAssetCount']}/${v['totalAssetCount']} · 근거 범위 ${v['coverage'] ?? '확인되지 않음'}',
        ),
        ...array(v['impacts']).map((a) {
          final m = object(a);
          return ExpansionTile(
            title: Text('${m['assetName']} · ${valueText(m['direction'])}'),
            subtitle: Text('${m['issueSummary']}'),
            children: [
              Text(
                '${m['expectedReaction']}\n${m['outlook']}\n${m['reason']}\n${m['evidenceSentence']}',
              ),
              ...array(m['sources']).map((s) {
                final item = object(s);
                return ListTile(
                  title: Text('${item['title']}'),
                  onTap: () => onLink(item['url']),
                );
              }),
            ],
          );
        }),
        ...array(v['sources']).map((s) {
          final m = object(s);
          return ListTile(
            title: Text('${m['title']}'),
            subtitle: Text('${m['url']}'),
            onTap: () => onLink(m['url']),
          );
        }),
      ] else
        notice('저장된 분석 본문이 없습니다.'),
    ],
  );
}

class _TransactionDialog extends StatefulWidget {
  const _TransactionDialog({
    required this.repository,
    this.stock,
    this.history,
    this.initialPrice = '',
  });
  final String initialPrice;
  final AppRepository repository;
  final Stock? stock;
  final JsonMap? history;
  @override
  State<_TransactionDialog> createState() => _TransactionDialogState();
}

class _TransactionDialogState extends State<_TransactionDialog> {
  late final q = TextEditingController(
        text: valueText(widget.history?['transactionQuantity'] ?? 1),
      ),
      price = TextEditingController(
        text: widget.history?['unitPrice']?.toString() ?? widget.initialPrice,
      ),
      fee = TextEditingController(
        text: widget.history?['fee']?.toString() ?? '0',
      ),
      tax = TextEditingController(
        text: widget.history?['tax']?.toString() ?? '0',
      ),
      date = TextEditingController(
        text: widget.history?['effectiveDate']?.toString() ?? today(),
      ),
      rate = TextEditingController(
        text: widget.history?['exchangeRate']?.toString() ?? '',
      );
  String type = 'BUY';
  Object? error;
  bool busy = false, uncertain = false;
  bool get us => widget.history != null
      ? '${widget.history!['assetCode']}'.endsWith('.US')
      : widget.stock!.currency == 'USD';
  @override
  void dispose() {
    for (final c in [q, price, fee, tax, date, rate]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    JsonMap body;
    try {
      validDate(date.text.trim());
      require(date.text.trim().compareTo(today()) <= 0);
      body = {
        'quantity': checkedId(ExactNumber(q.text.trim())),
        'unitPrice': money(price.text, positive: true),
        'fee': money(fee.text, scale: 2),
        'tax': money(tax.text, scale: 2),
        'tradeDate': date.text.trim(),
        if (us) 'exchangeRate': money(rate.text, scale: 6, positive: true),
        if (widget.history == null) 'assetId': widget.stock!.assetId,
        if (widget.history == null) 'type': type,
      };
    } catch (_) {
      setState(
        () => error = '수량·양수 가격(최대 소수 4자리)·수수료·세금·날짜를 확인해주세요. 미국 거래는 당시 USD/KRW 환율도 필요합니다.',
      );
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.repository.invoke(
        widget.history == null
            ? UserOperation.createTransaction
            : UserOperation.updateTransaction,
        params: widget.history == null
            ? {}
            : {'transactionId': '${widget.history!['historyId']}'},
        body: body,
      );
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted)
        setState(() {
          error = e;
          uncertain = e is! ApiException || e.status >= 500;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.history == null ? '${widget.stock!.name} 거래 기록' : '거래 수정',
    ),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (widget.history == null)
            DropdownButtonFormField<String>(
              initialValue: type,
              decoration: const InputDecoration(labelText: '거래 종류'),
              items: const [
                DropdownMenuItem(value: 'BUY', child: Text('매수')),
                DropdownMenuItem(value: 'SELL', child: Text('매도')),
              ],
              onChanged: busy ? null : (v) => setState(() => type = v!),
            ),
          input('거래 수량', q, key: 'transaction-quantity', decimal: true),
          input(
            '단가 (${us ? 'USD' : 'KRW'}, 최대 소수 4자리)',
            price,
            key: 'transaction-unit-price',
            decimal: true,
          ),
          input('수수료', fee, key: 'transaction-fee', decimal: true),
          input('세금', tax, key: 'transaction-tax', decimal: true),
          input('거래일 (YYYY-MM-DD)', date, key: 'transaction-date'),
          if (us) ...[
            input('거래일 USD/KRW 환율', rate, decimal: true),
            action(
              '거래일 환율 조회',
              busy
                  ? null
                  : () async {
                      try {
                        final v = object(
                          await widget.repository.invoke(
                            UserOperation.exchangeRate,
                            params: {'date': date.text},
                          ),
                        );
                        if (mounted) setState(() => rate.text = '${v['rate']}');
                      } catch (e) {
                        if (mounted) setState(() => error = e);
                      }
                    },
            ),
          ],
          if (busy) const LinearProgressIndicator(),
          if (error != null)
            notice(error is String ? '$error' : errorText(error), error: true),
          if (uncertain)
            notice('처리 여부가 불확실합니다. 닫고 목록을 재조회한 뒤 확인해주세요. 자동 재전송하지 않습니다.'),
          const SizedBox(height: 24),
          FilledButton(
            key: const ValueKey('transaction-submit'),
            onPressed: busy || uncertain ? null : submit,
            child: const Text('거래 저장'),
          ),
          TextButton(
            onPressed: busy ? null : () => Navigator.pop(context, uncertain),
            child: Text(uncertain ? '닫고 재조회' : '취소'),
          ),
        ],
      ),
    ),
  );
}

class _HoldingDialog extends StatefulWidget {
  const _HoldingDialog({required this.holding});
  final JsonMap holding;
  @override
  State<_HoldingDialog> createState() => _HoldingDialogState();
}

class _HoldingDialogState extends State<_HoldingDialog> {
  late final q = TextEditingController(text: '${widget.holding['quantity']}'),
      price = TextEditingController(
        text: '${widget.holding['averagePurchasePrice']}',
      );
  String? error;
  @override
  void dispose() {
    q.dispose();
    price.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('${widget.holding['name']} 보유 수정'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          input('보유 수량', q, decimal: true),
          input('평균 매입가 (KRW, 최대 소수 2자리)', price, decimal: true),
          if (error != null) notice(error!, error: true),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('취소'),
      ),
      FilledButton(
        onPressed: () {
          try {
            Navigator.pop(context, <String, Object?>{
              'quantity': checkedId(ExactNumber(q.text.trim())),
              'averagePurchasePrice': money(
                price.text,
                scale: 2,
                positive: true,
              ),
            });
          } catch (_) {
            setState(() => error = '수량과 평균 매입가를 확인해주세요.');
          }
        },
        child: const Text('보유 수정'),
      ),
    ],
  );
}

class _NewsPage extends StatefulWidget {
  const _NewsPage({super.key, required this.repository, required this.onLink});
  final AppRepository repository;
  final Future<void> Function(Object?) onLink;
  @override
  State<_NewsPage> createState() => _NewsPageState();
}

class _NewsPageState extends State<_NewsPage> {
  int page = 1, revision = 0;
  String category = 'ALL', sourceFilter = 'ALL', mode = 'news';
  final query = TextEditingController();
  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  Future<void> detail(JsonMap news) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (c) => _NewsDetail(
          repository: widget.repository,
          id: checkedId(news['id']),
          onLink: widget.onLink,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final op = switch (mode) {
      'today' => UserOperation.todayNews,
      'contents' =>
        query.text.trim().isEmpty
            ? UserOperation.contents
            : UserOperation.searchContents,
      'people' => UserOperation.people,
      _ =>
        query.text.trim().isEmpty
            ? UserOperation.news
            : UserOperation.searchNews,
    };
    final params = <String, String>{
      if (mode != 'people' && mode != 'today') 'page': '$page',
      if (mode != 'people' && mode != 'today')
        'size': mode == 'contents' ? '12' : '6',
      if (query.text.trim().isNotEmpty) 'q': query.text.trim(),
      if (mode == 'news' && query.text.trim().isEmpty) 'category': category,
      if (mode == 'news' && query.text.trim().isNotEmpty) 'sort': 'RELEVANCE',
      if (mode == 'contents') 'source': sourceFilter,
    };
    return pageBody('news', [
      heading('이슈와 근거를 함께', subtitle: '뉴스, 종목 자료와 주요 인물의 발언을 확인하세요.'),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final item in {
            'news': '뉴스',
            'today': '오늘 뉴스',
            'contents': '통합 콘텐츠',
            'people': '주요 인물',
          }.entries)
            ChoiceChip(
              label: Text(item.value),
              selected: mode == item.key,
              onSelected: (_) => setState(() {
                mode = item.key;
                page = 1;
              }),
            ),
        ],
      ),
      if (mode == 'news' || mode == 'contents') ...[
        input('뉴스·콘텐츠 검색어', query),
        action(
          '검색 적용',
          () => setState(() {
            page = 1;
            revision++;
          }),
          icon: Icons.search,
        ),
      ],
      if (mode == 'news')
        DropdownButtonFormField<String>(
          initialValue: category,
          decoration: const InputDecoration(labelText: '뉴스 분류'),
          items: ['ALL', ...categories]
              .map(
                (v) =>
                    DropdownMenuItem(value: v, child: Text(categoryLabel(v))),
              )
              .toList(),
          onChanged: (v) => setState(() {
            category = v!;
            page = 1;
          }),
        ),
      if (mode == 'contents')
        DropdownButtonFormField<String>(
          initialValue: sourceFilter,
          decoration: const InputDecoration(labelText: '출처'),
          items: ['ALL', 'DAYNOMY', 'X', 'THREADS', 'YOUTUBE']
              .map(
                (v) => DropdownMenuItem(
                  value: v,
                  child: Text(v == 'ALL' ? '전체 출처' : v),
                ),
              )
              .toList(),
          onChanged: (v) => setState(() {
            sourceFilter = v!;
            page = 1;
          }),
        ),
      DataPanel(
        repository: widget.repository,
        operation: op,
        params: params,
        identity: '$mode-$params-$revision',
        builder: (raw) {
          final data = object(raw);
          if (mode == 'people') {
            final people = array(data['people']);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (people.isEmpty) notice('등록된 인물이 없습니다.'),
                ...people.map((p) {
                  final m = object(p);
                  return ExpansionTile(
                    title: Text('${m['name']}'),
                    children: [
                      for (final key in [
                        'xProfileUrl',
                        'threadsProfileUrl',
                        'youtubeProfileUrl',
                      ])
                        if (m[key] != null)
                          ListTile(
                            title: Text('$key'),
                            subtitle: Text('${m[key]}'),
                            onTap: () => widget.onLink(m[key]),
                          ),
                      ...array(m['posts']).map((p) {
                        final post = object(p);
                        return ListTile(
                          title: Text('${post['title']}'),
                          subtitle: Text(
                            '${post['sourceType']} · ${valueText(post['publishedAt'] ?? post['createdAt'])}',
                          ),
                          onTap: () => widget.onLink(post['url']),
                        );
                      }),
                    ],
                  );
                }),
              ],
            );
          }
          final list = array(
            data[op == UserOperation.searchNews ? 'content' : 'items'],
          );
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (list.isEmpty) notice('결과가 없습니다.'),
              ...list.map((n) {
                final m = object(n), id = checkedId(m['id']);
                return ListTile(
                  key: ValueKey('news-$id'),
                  contentPadding: const EdgeInsets.symmetric(
                    vertical: 12,
                    horizontal: 4,
                  ),
                  title: Text(
                    '${m['title']}',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '${m['category'] != null ? categoryLabel('${m['category']}') : m['source']} · ${valueText(m['publishedAt'] ?? m['date'])}',
                    ),
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => mode == 'contents' && m['kind'] != 'NEWS'
                      ? widget.onLink(m['url'])
                      : detail(m),
                );
              }),
              if (mode != 'today')
                Wrap(
                  spacing: 16,
                  children: [
                    action(
                      '이전 페이지',
                      page > 1 ? () => setState(() => page--) : null,
                      icon: Icons.chevron_left,
                    ),
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text('$page / ${data['totalPages']}'),
                    ),
                    action(
                      '다음 페이지',
                      integerValue(data['totalPages']) > BigInt.from(page)
                          ? () => setState(() => page++)
                          : null,
                      icon: Icons.chevron_right,
                    ),
                  ],
                ),
            ],
          );
        },
      ),
    ]);
  }
}

String categoryLabel(String value) =>
    const {
      'ALL': '전체',
      'REAL_ESTATE': '부동산',
      'DEPOSIT_SAVINGS': '예금·적금',
      'STOCK': '주식',
      'ECONOMY': '경제지표',
      'ETF': 'ETF',
      'BOND': '채권',
      'PENSION': '연금',
      'FOREIGN_EXCHANGE': '외화·환율',
      'VIRTUAL_ASSET': '가상자산',
      'GOLD': '금',
    }[value] ??
    value;

class _NewsDetail extends StatelessWidget {
  const _NewsDetail({
    required this.repository,
    required this.id,
    required this.onLink,
  });
  final AppRepository repository;
  final int id;
  final Future<void> Function(Object?) onLink;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('뉴스 상세')),
    body: SafeArea(
      child: SingleChildScrollView(
        key: const ValueKey('news-detail'),
        padding: const EdgeInsets.all(24),
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                DataPanel(
                  repository: repository,
                  operation: UserOperation.newsDetail,
                  params: {'newsId': '$id'},
                  identity: 'detail-$id',
                  builder: (raw) {
                    final v = object(raw);
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        heading(
                          '${v['title']}',
                          subtitle:
                              '${categoryLabel('${v['category']}')} · ${v['publishedAt']}',
                        ),
                        ...((v['content'] is String)
                                ? [v['content']]
                                : (v['content'] as List))
                            .map(
                              (p) => Padding(
                                padding: const EdgeInsets.only(bottom: 20),
                                child: Text(
                                  '$p',
                                  style: const TextStyle(
                                    fontSize: 18,
                                    height: 1.65,
                                  ),
                                ),
                              ),
                            ),
                        section(
                          '출처',
                          array(v['sources']).map((s) {
                            final m = object(s);
                            return ListTile(
                              title: Text('${m['name']}'),
                              subtitle: Text('${m['url']}'),
                              onTap: () => onLink(m['url']),
                            );
                          }).toList(),
                        ),
                      ],
                    );
                  },
                ),
                _NewsAux(repository: repository, id: id, keywords: true),
                _NewsAux(repository: repository, id: id, keywords: false),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _NewsAux extends StatefulWidget {
  const _NewsAux({
    required this.repository,
    required this.id,
    required this.keywords,
  });
  final AppRepository repository;
  final int id;
  final bool keywords;
  @override
  State<_NewsAux> createState() => _NewsAuxState();
}

class _NewsAuxState extends State<_NewsAux> {
  Object? data, error;
  bool loading = true;
  final cancel = CancellationToken();
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final v = await widget.repository.invoke(
        widget.keywords
            ? UserOperation.newsKeywords
            : UserOperation.newsMarketAnalysis,
        params: {'newsId': '${widget.id}'},
        cancel: cancel,
      );
      if (mounted) setState(() => data = v);
    } catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    cancel.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.keywords ? '핵심 키워드' : '시장 분석';
    if (loading) return notice('$title 불러오는 중');
    if (error != null) {
      if (error is ApiException && (error as ApiException).status == 404)
        return section(title, [notice('아직 등록된 분석이 없습니다.')]);
      return section(title, [
        notice(errorText(error), error: true),
        action('분석 다시 조회', load),
      ]);
    }
    final v = object(data);
    return section(
      title,
      widget.keywords
          ? [
              if (array(v['keywords']).isEmpty) notice('등록된 키워드가 없습니다.'),
              ...array(v['keywords']).map((k) {
                final m = object(k);
                return ExpansionTile(
                  title: Text('${m['keyword']}'),
                  children: [
                    Text(
                      '${m['definition']}\n${m['context']}\n확인할 점: ${m['watchPoint']}',
                    ),
                  ],
                );
              }),
            ]
          : [
              Text('위험 요인: ${v['risk']}'),
              const SizedBox(height: 8),
              Text('확인할 점: ${v['watchPoint']}'),
            ],
    );
  }
}

class _CalendarPage extends StatefulWidget {
  const _CalendarPage({
    super.key,
    required this.repository,
    required this.member,
    required this.guest,
    required this.onLink,
  });
  final AppRepository repository;
  final bool member;
  final List<JsonMap> guest;
  final Future<void> Function(Object?) onLink;
  @override
  State<_CalendarPage> createState() => _CalendarPageState();
}

class _CalendarPageState extends State<_CalendarPage> {
  DateTime month = DateTime(DateTime.now().year, DateTime.now().month);
  String scope = 'ALL';
  String? rangeFrom, rangeTo;
  String? rangeError;
  Future<void> range() async {
    final value = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100, 12, 31),
    );
    if (value != null && mounted)
      setState(() {
        if ((value.end.year - value.start.year) * 12 +
                value.end.month -
                value.start.month >
            11) {
          rangeError = '한 번에 최대 12개월 범위를 선택해주세요.';
          return;
        }
        rangeError = null;
        rangeFrom = dateText(value.start);
        rangeTo = dateText(value.end);
        month = DateTime(value.start.year, value.start.month);
      });
  }

  @override
  Widget build(BuildContext context) => pageBody('calendar', [
    heading('투자 캘린더', subtitle: '발표 일정과 보유 자산의 과거 반응을 함께 확인하세요.'),
    Wrap(
      spacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        IconButton(
          tooltip: '이전 달',
          onPressed: month.year == 2000 && month.month == 1
              ? null
              : () => setState(
                  () => month = DateTime(month.year, month.month - 1),
                ),
          icon: const Icon(Icons.chevron_left),
        ),
        Text(
          '${month.year}년 ${month.month}월',
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
        ),
        IconButton(
          tooltip: '다음 달',
          onPressed: month.year == 2100 && month.month == 12
              ? null
              : () => setState(
                  () => month = DateTime(month.year, month.month + 1),
                ),
          icon: const Icon(Icons.chevron_right),
        ),
        DropdownButton<String>(
          value: scope,
          items: const [
            DropdownMenuItem(value: 'ALL', child: Text('전체 일정')),
            DropdownMenuItem(value: 'PORTFOLIO', child: Text('내 보유 관련')),
          ],
          onChanged: (v) => setState(() => scope = v!),
        ),
        action('날짜 범위 선택', range, icon: Icons.date_range),
      ],
    ),
    if (rangeError != null) notice(rangeError!, error: true),
    if (rangeFrom != null) ...[
      notice('$rangeFrom ~ $rangeTo · 기간의 모든 월을 조회합니다.'),
      action(
        '범위 해제',
        () => setState(() {
          rangeFrom = null;
          rangeTo = null;
        }),
      ),
    ],
    _CalendarData(
      repository: widget.repository,
      member: widget.member,
      guest: widget.guest,
      month: month,
      scope: scope,
      rangeFrom: rangeFrom,
      rangeTo: rangeTo,
      builder: (v) {
        final list = array(object(v)['events']).map(object).where((e) {
          final date = '${e['announcedAt']}'.split('T').first;
          return rangeFrom == null ||
              date.compareTo(rangeFrom!) >= 0 && date.compareTo(rangeTo!) <= 0;
        }).toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (list.isEmpty)
              notice(
                '선택한 기간에 일정이 없습니다.',
                key: const ValueKey('calendar-empty'),
              ),
            ...list.map((e) {
              final value = object(e['value']),
                  source = object(e['source']),
                  a = object(e['portfolioAnalysis']);
              return ExpansionTile(
                title: Text('${e['title']}'),
                subtitle: Text(
                  '${e['announcedAt']} · ${e['upcoming'] == true ? '예정' : '발표됨'}',
                ),
                children: [
                  Text(
                    '이전 ${valueText(value['previousValue'])} → 실제 ${valueText(value['actualValue'])} ${value['unit']}',
                  ),
                  Text(
                    '영향 ${a['impactLevel']} · 상태 ${a['status']} · 관련 자산 ${a['relatedAssetCount']}',
                  ),
                  Text(
                    '평가 ${a['totalEvaluationAmount']}원 · 기준일 ${valueText(a['priceBaseDate'])}',
                  ),
                  ...array(a['historicalReactions']).map((r) {
                    final m = object(r);
                    return ListTile(
                      title: Text('${m['direction']} · 표본 ${m['sampleCount']}'),
                      subtitle: Text(
                        '중앙 수익률 ${valueText(m['medianReturnRate'])}% · 범위 ${valueText(m['lowerReturnRate'])} ~ ${valueText(m['upperReturnRate'])}%\n예상금액 ${valueText(m['lowerEstimatedAmount'])} ~ ${valueText(m['upperEstimatedAmount'])}원',
                      ),
                    );
                  }),
                  ListTile(
                    title: Text('${source['name']}'),
                    subtitle: Text('${source['url']}'),
                    onTap: () => widget.onLink(source['url']),
                  ),
                ],
              );
            }),
          ],
        );
      },
    ),
  ]);
}

class _ProfilePage extends StatefulWidget {
  const _ProfilePage({
    super.key,
    required this.repository,
    required this.profile,
    required this.profileError,
    required this.onProfile,
    required this.onClear,
    required this.onRetry,
    required this.onLogin,
  });
  final AppRepository repository;
  final JsonMap? profile;
  final Object? profileError;
  final ValueChanged<JsonMap> onProfile;
  final VoidCallback onClear;
  final Future<void> Function() onRetry, onLogin;
  @override
  State<_ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<_ProfilePage> {
  late final nickname = TextEditingController(
    text: widget.profile?['nickname'] as String? ?? '',
  );
  final feedback = TextEditingController();
  String? nicknameError, feedbackError, sessionError;
  bool feedbackSuccess = false, busy = false;
  @override
  void dispose() {
    nickname.dispose();
    feedback.dispose();
    super.dispose();
  }

  Future<void> saveNickname() async {
    final text = nickname.text.trim();
    if (text.isEmpty || text.length > 20) {
      setState(() => nicknameError = '닉네임은 공백 없이 1~20자로 입력해주세요.');
      return;
    }
    setState(() {
      busy = true;
      nicknameError = null;
    });
    try {
      final p = object(
        await widget.repository.invoke(
          UserOperation.updateProfile,
          body: {'nickname': text},
        ),
      );
      if (mounted) widget.onProfile(p);
    } catch (e) {
      if (mounted) setState(() => nicknameError = errorText(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submitFeedback() async {
    if (feedback.text.trim().isEmpty || feedback.text.length > 1000) {
      setState(() => feedbackError = '피드백을 1~1000자로 입력해주세요.');
      return;
    }
    setState(() {
      busy = true;
      feedbackError = null;
      feedbackSuccess = false;
    });
    try {
      await widget.repository.invoke(
        UserOperation.feedback,
        body: {'content': feedback.text, 'pagePath': '/profile'},
      );
      if (mounted)
        setState(() {
          feedbackSuccess = true;
          feedback.clear();
        });
    } catch (e) {
      if (mounted)
        setState(
          () => feedbackError = '${errorText(e)} 처리 여부가 불확실하면 바로 재전송하지 말아주세요.',
        );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> leave(bool withdraw) async {
    if (withdraw) {
      final yes = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('회원 탈퇴'),
          content: const Text('탈퇴하면 이 계정으로 회원 기능을 사용할 수 없습니다. 계속할까요?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('탈퇴'),
            ),
          ],
        ),
      );
      if (yes != true) return;
    }
    if (!mounted) return;
    final repository = widget.repository;
    final clearParentSession = widget.onClear;
    repository.client.clearSession();
    setState(() => busy = true);
    try {
      await repository.invoke(
        withdraw ? UserOperation.withdraw : UserOperation.logout,
      );
      // Session termination belongs to the app, even when this tab was disposed.
      clearParentSession();
    } catch (e) {
      if (mounted) setState(() => sessionError = errorText(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => pageBody('profile', [
    heading('내 정보', subtitle: '계정과 의견을 관리하세요.'),
    if (widget.profileError != null) ...[
      notice(errorText(widget.profileError), error: true),
      action('계정 다시 확인', widget.onRetry),
    ] else if (widget.profile == null) ...[
      notice('로그인하면 거래 원장과 보유 자산을 계정에 저장할 수 있어요.'),
      action(
        'Google로 로그인',
        busy
            ? null
            : () async {
                setState(() => busy = true);
                try {
                  await widget.onLogin();
                } catch (e) {
                  if (mounted) setState(() => sessionError = errorText(e));
                } finally {
                  if (mounted) setState(() => busy = false);
                }
              },
        key: 'login-button',
        icon: Icons.login,
      ),
    ] else ...[
      Text(
        '${widget.profile!['nickname']}',
        style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w600),
      ),
      Text('${widget.profile!['email']}'),
      if (widget.profile!['name'] != null)
        Text('이름: ${widget.profile!['name']}'),
      input('닉네임 (최대 20자)', nickname, key: 'nickname-input'),
      if (nicknameError != null)
        notice(
          nicknameError!,
          key: const ValueKey('nickname-error'),
          error: true,
        ),
      action(
        '닉네임 저장',
        busy ? null : saveNickname,
        key: 'nickname-save',
        icon: Icons.check,
      ),
      Wrap(
        spacing: 12,
        children: [
          action('로그아웃', busy ? null : () => leave(false), icon: Icons.logout),
          action(
            '회원 탈퇴',
            busy ? null : () => leave(true),
            icon: Icons.person_remove_outlined,
          ),
        ],
      ),
    ],
    if (sessionError != null) notice(sessionError!, error: true),
    const Divider(height: 48),
    section('의견 보내기', [
      input(
        '어떤 점을 개선하면 좋을까요? (최대 1000자)',
        feedback,
        key: 'feedback-input',
        lines: 3,
      ),
      if (feedbackError != null)
        notice(
          feedbackError!,
          key: const ValueKey('feedback-error'),
          error: true,
        ),
      if (feedbackSuccess)
        notice('의견을 전달했습니다. 감사합니다.', key: const ValueKey('feedback-success')),
      action(
        '피드백 보내기',
        busy ? null : submitFeedback,
        key: 'feedback-submit',
        icon: Icons.send_outlined,
      ),
    ]),
    if (busy) const LinearProgressIndicator(),
  ]);
}

class _CalendarData extends StatefulWidget {
  const _CalendarData({
    required this.repository,
    required this.member,
    required this.guest,
    required this.month,
    required this.scope,
    required this.rangeFrom,
    required this.rangeTo,
    required this.builder,
  });
  final AppRepository repository;
  final bool member;
  final List<JsonMap> guest;
  final DateTime month;
  final String scope;
  final String? rangeFrom, rangeTo;
  final Widget Function(Object?) builder;
  String get identity =>
      '${month.year}-${month.month}-$scope-$rangeFrom-$rangeTo-${encodeJsonExact(guest)}';
  @override
  State<_CalendarData> createState() => _CalendarDataState();
}

class _CalendarDataState extends State<_CalendarData> {
  Object? data, error;
  bool loading = true;
  CancellationToken? cancel;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void didUpdateWidget(_CalendarData old) {
    super.didUpdateWidget(old);
    if (old.identity != widget.identity) load();
  }

  @override
  void dispose() {
    generation++;
    cancel?.cancel();
    super.dispose();
  }

  Future<void> load() async {
    cancel?.cancel();
    final token = cancel = CancellationToken();
    final g = ++generation;
    setState(() {
      loading = true;
      error = null;
      data = null;
    });
    try {
      final start = widget.rangeFrom == null
          ? widget.month
          : DateTime.parse(widget.rangeFrom!);
      final end = widget.rangeTo == null
          ? widget.month
          : DateTime.parse(widget.rangeTo!);
      var current = DateTime(start.year, start.month);
      final last = DateTime(end.year, end.month);
      final events = <Object?>[];
      while (!current.isAfter(last)) {
        final result = object(
          await widget.repository.invoke(
            widget.member
                ? UserOperation.memberCalendar
                : UserOperation.guestCalendar,
            params: {
              'year': '${current.year}',
              'month': '${current.month}',
              'scope': widget.scope,
            },
            body: widget.member
                ? null
                : {
                    'holdings': widget.guest
                        .map(
                          (h) => <String, Object?>{
                            'assetId': h['assetId'],
                            'quantity': h['quantity'],
                          },
                        )
                        .toList(),
                  },
            cancel: token,
          ),
        );
        if (token.isCancelled) throw const RequestCancelled();
        events.addAll(array(result['events']));
        current = DateTime(current.year, current.month + 1);
      }
      events.sort(
        (a, b) => '${object(a)['announcedAt']}'.compareTo(
          '${object(b)['announcedAt']}',
        ),
      );
      if (mounted && g == generation)
        setState(() => data = <String, Object?>{'events': events});
    } catch (e) {
      if (mounted && g == generation) setState(() => error = e);
    } finally {
      if (mounted && g == generation) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading)
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: CircularProgressIndicator()),
      );
    if (error != null)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          notice(errorText(error), error: true),
          action('일정 다시 조회', load),
        ],
      );
    return widget.builder(data);
  }
}
