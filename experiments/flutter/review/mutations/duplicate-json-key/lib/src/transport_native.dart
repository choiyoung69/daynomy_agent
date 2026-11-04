import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'native_auth.dart';

class PlatformTransport implements ApiTransport {
  PlatformTransport(this.baseUri) {
    validateOrigin(baseUri);
  }
  final Uri baseUri;
  final MemoryCookieJar jar = MemoryCookieJar();
  final HttpClient _http = HttpClient()
    ..connectionTimeout = const Duration(seconds: 8);
  static const maxBytes = 4 * 1024 * 1024;
  int _session = 0;
  final _active = <void Function()>{};
  void invalidateRequests() {
    _session++;
    for (final abort in _active.toList()) {
      abort();
    }
    _active.clear();
  }

  void clearSession() {
    invalidateRequests();
    jar.clear();
  }

  Future<void> login(ApiClient client) => NativeAuthCoordinator(
    client: client,
    broker: _Broker(),
    baseUri: baseUri,
  ).login();
  Future<void> openLink(Uri uri) async {
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication))
      throw StateError('링크를 열 수 없습니다.');
  }

  @override
  Future<ApiResponse> send(ApiRequest request) async {
    final target = baseUri.resolve(request.path);
    if (target.origin != baseUri.origin)
      throw ArgumentError('다른 origin의 API 요청을 거절했습니다.');
    final session = _session;
    HttpClientRequest? outgoing;
    StreamSubscription<List<int>>? incoming;
    Completer<List<int>>? reading;
    bool stopped = false;
    final cancelled = Completer<ApiResponse>();
    void abort(Object error) {
      stopped = true;
      outgoing?.abort(error);
      incoming?.cancel();
      if (reading != null && !reading!.isCompleted)
        reading!.completeError(error);
      if (!cancelled.isCompleted) cancelled.completeError(error);
    }

    void stop() => abort(const RequestCancelled());
    _active.add(stop);
    request.cancel?.onCancel(stop);
    final timer = Timer(
      const Duration(seconds: 25),
      () => abort(TimeoutException('요청 시간이 초과되었습니다.')),
    );
    Future<ApiResponse> execute() async {
      try {
        if (stopped) throw const RequestCancelled();
        final connection = await _http.openUrl(request.method, target);
        outgoing = connection;
        if (stopped) {
          connection.abort();
          throw const RequestCancelled();
        }
        connection.followRedirects = false;
        request.headers.forEach(connection.headers.set);
        final cookie = jar.headerFor(target);
        if (cookie.isNotEmpty)
          connection.headers.set(HttpHeaders.cookieHeader, cookie);
        if (request.body != null) connection.add(utf8.encode(request.body!));
        final response = await connection.close();
        if (session != _session) {
          response.listen((_) {}).cancel();
          throw const RequestCancelled();
        }
        jar.accept(target, response.headers[HttpHeaders.setCookieHeader] ?? []);
        final bytes = <int>[];
        reading = Completer<List<int>>();
        incoming = response.listen(
          (chunk) {
            if (stopped) return;
            if (bytes.length + chunk.length > maxBytes) {
              abort(const FormatException('응답 크기를 초과했습니다.'));
              return;
            }
            bytes.addAll(chunk);
          },
          onError: (Object error) {
            if (!reading!.isCompleted) reading!.completeError(error);
          },
          onDone: () {
            if (!reading!.isCompleted) reading!.complete(bytes);
          },
          cancelOnError: true,
        );
        await reading!.future;
        if (session != _session) throw const RequestCancelled();
        final headers = <String, String>{};
        response.headers.forEach((k, v) => headers[k] = v.join(','));
        return ApiResponse(
          response.statusCode,
          utf8.decode(bytes),
          headers: headers,
        );
      } finally {
        timer.cancel();
      }
    }

    try {
      return await Future.any([execute(), cancelled.future]);
    } finally {
      _active.remove(stop);
      timer.cancel();
    }
  }
}

class _Broker implements NativeAuthBroker {
  @override
  Future<String?> authenticate(
    Uri authorizationUri, {
    required String callbackScheme,
  }) async {
    try {
      return await FlutterWebAuth2.authenticate(
        url: authorizationUri.toString(),
        callbackUrlScheme: callbackScheme,
        options: const FlutterWebAuth2Options(preferEphemeral: true),
      );
    } on PlatformException catch (e) {
      if (e.code == 'CANCELED' || e.code == 'CANCELLED') return null;
      throw NativeAuthException('provider_unavailable');
    }
  }
}
