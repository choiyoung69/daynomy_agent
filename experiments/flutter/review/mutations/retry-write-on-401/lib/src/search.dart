import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'exact_json.dart';
import 'repository.dart';

class SearchController extends ChangeNotifier {
  SearchController(this.repository);
  final AppRepository repository;
  Timer? _timer;
  CancellationToken? _searchToken, _priceToken;
  int _generation = 0, _priceGeneration = 0, _edit = 0;
  bool _disposed = false;
  String get queryText => _query;
  String draftQuantity = '1';
  final guestAverageKrw = <int, String>{};
  String _query = '', country = 'KR', category = 'ALL', priceText = '';
  List<Stock> _all = [];
  List<Stock> get stocks =>
      _all.where((s) => category == 'ALL' || s.category == category).toList();
  bool loading = false;
  Object? error;
  PriceQuote? quote;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void query(String value) {
    _query = value.trim();
    _timer?.cancel();
    _searchToken?.cancel();
    final generation = ++_generation;
    error = null;
    _all = [];
    loading = false;
    if (_query.isEmpty) {
      _notify();
      return;
    }
    _timer = Timer(const Duration(milliseconds: 250), () async {
      final token = _searchToken = CancellationToken();
      loading = true;
      _notify();
      try {
        final v = await repository.invoke(
          UserOperation.stocks,
          params: {'q': _query, 'country': country},
          cancel: token,
        );
        if (!_disposed && generation == _generation)
          _all = decodeStocks(encodeJsonExact(v));
      } catch (e) {
        if (!_disposed && generation == _generation) error = e;
      } finally {
        if (!_disposed && generation == _generation) {
          loading = false;
          _notify();
        }
      }
    });
    _notify();
  }

  void updateFilters({String? country, String? category}) {
    final changed = country != null && country != this.country;
    if (country != null) this.country = country;
    if (category != null) this.category = category;
    if (changed)
      query(_query);
    else
      _notify();
  }

  Future<void> selectStock(Stock value) async {
    _priceToken?.cancel();
    final token = _priceToken = CancellationToken();
    final generation = ++_priceGeneration, edit = _edit;
    priceText = '';
    quote = null;
    _notify();
    try {
      final data = await repository.invoke(
        UserOperation.price,
        params: {'assetId': '${value.assetId}'},
        cancel: token,
      );
      if (!_disposed && generation == _priceGeneration) {
        quote = decodePrice(encodeJsonExact(data));
        if (edit == _edit) priceText = quote!.closePrice.lexeme;
        _notify();
      }
    } catch (e) {
      if (!_disposed && generation == _priceGeneration) {
        error = e;
        _notify();
      }
    }
  }

  void setManualPrice(String value) {
    _edit++;
    priceText = value;
    _notify();
  }

  void suspend() {
    _timer?.cancel();
    _searchToken?.cancel();
    _priceToken?.cancel();
    _generation++;
    _priceGeneration++;
    loading = false;
  }

  @override
  void dispose() {
    _disposed = true;
    suspend();
    super.dispose();
  }
}
