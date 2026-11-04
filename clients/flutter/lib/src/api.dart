import 'dart:async';

import 'exact_json.dart';

class CancellationToken {
  bool _cancelled = false;
  final _listeners = <void Function()>[];
  bool get isCancelled => _cancelled;
  void cancel() {
    if (_cancelled) return;
    _cancelled = true;
    for (final callback in _listeners) {
      callback();
    }
    _listeners.clear();
  }

  void onCancel(void Function() callback) {
    if (_cancelled) {
      callback();
    } else {
      _listeners.add(callback);
    }
  }
}

class ApiRequest {
  ApiRequest(
    this.path, {
    this.method = 'GET',
    this.headers = const {},
    this.body,
    this.cancel,
    this.credentials = true,
  });
  final String path, method;
  final Map<String, String> headers;
  final String? body;
  final CancellationToken? cancel;
  final bool credentials;
}

class ApiResponse {
  ApiResponse(
    this.status,
    this.body, {
    this.headers = const {'content-type': 'application/json'},
  });
  final int status;
  final String body;
  final Map<String, String> headers;
}

abstract class ApiTransport {
  Future<ApiResponse> send(ApiRequest request);
}

class ApiException implements Exception {
  ApiException(this.status, this.code, this.message);
  final int status;
  final String code, message;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({required this.transport});
  final ApiTransport transport;
  Future<void>? _refreshing;
  void Function()? onAuthenticationLost;
  void Function()? onRequestsInvalidated;
  int _sessionGeneration = 0;
  void clearSession() {
    _sessionGeneration++;
    _refreshing = null;
    onRequestsInvalidated?.call();
  }

  Future<Map<String, String>> _csrf(CancellationToken? cancel) async {
    final r = await transport.send(
      ApiRequest('/api/auth/csrf', cancel: cancel),
    );
    _check(r);
    final data = decodeJsonExact(r.body);
    if (data is! Map ||
        data['headerName'] is! String ||
        data['token'] is! String)
      throw const FormatException('CSRF 응답 형식 오류');
    final header = data['headerName'] as String,
        token = data['token'] as String;
    if (!RegExp(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$").hasMatch(header) ||
        token.isEmpty ||
        token.contains(RegExp(r'[\r\n]')) ||
        [
          'cookie',
          'authorization',
          'host',
          'content-length',
          'content-type',
        ].contains(header.toLowerCase()))
      throw const FormatException('CSRF 응답 형식 오류');
    return {header: token};
  }

  void _check(ApiResponse response) {
    if (response.status >= 200 && response.status < 300) return;
    String code = 'HTTP_${response.status}',
        message = '요청에 실패했습니다. (${response.status})';
    try {
      final data = decodeJsonExact(response.body);
      if (data is Map) {
        if (data['code'] is String) code = data['code'];
        if (data['message'] is String) message = data['message'];
      }
    } on FormatException {
      /* Keep status even for an HTML gateway error. */
    }
    throw ApiException(response.status, code, message);
  }

  Future<void> _refresh() async {
    final csrf = await _csrf(null);
    final response = await transport.send(
      ApiRequest('/api/auth/refresh', method: 'POST', headers: csrf),
    );
    _check(response);
  }

  Future<String?> request(
    String path, {
    String method = 'GET',
    Object? body,
    bool csrf = false,
    CancellationToken? cancel,
  }) async {
    if (!path.startsWith('/api/') || path.startsWith('//'))
      throw ArgumentError('API 경로가 필요합니다.');
    final session = _sessionGeneration;
    final headers = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
    };
    if (csrf) headers.addAll(await _csrf(cancel));
    if (cancel?.isCancelled == true || session != _sessionGeneration)
      throw const RequestCancelled();
    final request = ApiRequest(
      path,
      method: method,
      headers: headers,
      body: body == null ? null : encodeJsonExact(body),
      cancel: cancel,
    );
    var response = await transport.send(request);
    if (session != _sessionGeneration) throw const RequestCancelled();
    if (response.status == 401 &&
        method == 'GET' &&
        !path.startsWith('/api/auth/')) {
      final refresh = _refreshing ??= _refresh();
      try {
        await refresh;
      } catch (e) {
        if (e is ApiException &&
            e.status == 401 &&
            session == _sessionGeneration)
          onAuthenticationLost?.call();
        rethrow;
      } finally {
        if (identical(_refreshing, refresh)) _refreshing = null;
      }
      if (cancel?.isCancelled == true || session != _sessionGeneration)
        throw const RequestCancelled();
      response = await transport.send(request);
    }
    if (session != _sessionGeneration) throw const RequestCancelled();
    if (response.status == 401 && path != '/api/auth/mobile/exchange')
      onAuthenticationLost?.call();
    _check(response);
    if (response.status == 204) return null;
    if (!response.headers.entries.any(
      (e) =>
          e.key.toLowerCase() == 'content-type' &&
          e.value.toLowerCase().contains('application/json'),
    ))
      throw const FormatException('JSON 응답이 필요합니다.');
    return response.body;
  }
}

class RequestCancelled implements Exception {
  const RequestCancelled();
  @override
  String toString() => '요청을 취소했습니다.';
}
