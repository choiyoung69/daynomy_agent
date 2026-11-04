import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';

import 'api.dart';

abstract class NativeAuthBroker {
  Future<String?> authenticate(
    Uri authorizationUri, {
    required String callbackScheme,
  });
}

class NativeAuthException implements Exception {
  NativeAuthException(this.code);
  final String code;
  @override
  String toString() =>
      code == 'cancelled' ? '로그인을 취소했습니다.' : '로그인에 실패했습니다. 다시 시작해주세요.';
}

void validateOrigin(Uri uri) {
  if (uri.userInfo.isNotEmpty ||
      uri.host.isEmpty ||
      uri.hasFragment ||
      uri.hasQuery ||
      !(uri.scheme == 'https' ||
          uri.scheme == 'http' &&
              ['localhost', '127.0.0.1', '::1', '10.0.2.2'].contains(uri.host)))
    throw ArgumentError('HTTPS API origin 또는 명시적 개발용 loopback origin이 필요합니다.');
}

class NativeAuthCoordinator {
  NativeAuthCoordinator({
    required this.client,
    required this.broker,
    required this.baseUri,
    List<int> Function(int)? randomBytes,
  }) : _random = randomBytes ?? secureBytes {
    validateOrigin(baseUri);
  }
  final ApiClient client;
  final NativeAuthBroker broker;
  final Uri baseUri;
  final List<int> Function(int) _random;
  bool _active = false;
  static List<int> secureBytes(int count) {
    final r = Random.secure();
    return List.generate(count, (_) => r.nextInt(256));
  }

  Future<void> login() async {
    if (_active) throw NativeAuthException('in_progress');
    _active = true;
    try {
      final verifier = base64Url.encode(_random(32)).replaceAll('=', '');
      final state = base64Url.encode(_random(24)).replaceAll('=', '');
      final challenge = base64Url
          .encode(sha256.convert(utf8.encode(verifier)).bytes)
          .replaceAll('=', '');
      final start = baseUri
          .resolve('/api/auth/mobile/start')
          .replace(
            queryParameters: {'code_challenge': challenge, 'state': state},
          );
      final response = await broker.authenticate(
        start,
        callbackScheme: 'org.daynomy.app',
      );
      if (response == null) throw NativeAuthException('cancelled');
      final uri = Uri.tryParse(response);
      if (uri == null ||
          uri.scheme != 'org.daynomy.app' ||
          uri.host != 'auth' ||
          uri.path != '/callback' ||
          uri.hasPort ||
          uri.userInfo.isNotEmpty ||
          uri.hasFragment ||
          uri.queryParametersAll['state']?.length != 1 ||
          uri.queryParameters['state'] != state ||
          uri.queryParametersAll.containsKey('error') ||
          uri.queryParametersAll['code']?.length != 1 ||
          (uri.queryParameters['code'] ?? '').isEmpty)
        throw NativeAuthException('invalid_callback');
      await client.request(
        '/api/auth/mobile/exchange',
        method: 'POST',
        body: {'code': uri.queryParameters['code'], 'codeVerifier': verifier},
      );
    } finally {
      _active = false;
    }
  }
}

class _Cookie {
  _Cookie(
    this.origin,
    this.name,
    this.value,
    this.path,
    this.secure,
    this.expires,
  );
  final String origin, name, value, path;
  final bool secure;
  final DateTime? expires;
}

class MemoryCookieJar {
  MemoryCookieJar({DateTime Function()? now}) : _now = now ?? DateTime.now;
  final DateTime Function() _now;
  final _cookies = <_Cookie>[];
  void clear() => _cookies.clear();
  void accept(Uri origin, List<String> headers) {
    for (final raw in headers) {
      final parts = raw.split(';');
      final equals = parts.first.indexOf('=');
      if (equals <= 0) continue;
      final name = parts.first.substring(0, equals).trim(),
          value = parts.first.substring(equals + 1).trim();
      if (!RegExp(r'^[A-Za-z0-9_!#$%&\x27*+.^`|~-]+$').hasMatch(name) ||
          value.contains(RegExp(r'[\r\n;]')))
        continue;
      var path = origin.path.contains('/')
          ? origin.path.substring(0, origin.path.lastIndexOf('/') + 1)
          : '/';
      if (path.isEmpty) path = '/';
      bool secure = false, reject = false;
      DateTime? expires;
      int? age;
      for (final part in parts.skip(1)) {
        final pair = part.trim().split('=');
        final key = pair.first.toLowerCase(),
            val = pair.skip(1).join('=').trim();
        switch (key) {
          case 'domain':
            if (val.toLowerCase().replaceFirst(RegExp(r'^\.'), '') !=
                origin.host.toLowerCase())
              reject = true;
          case 'path':
            if (val.startsWith('/')) path = val;
          case 'secure':
            secure = true;
          case 'max-age':
            age = int.tryParse(val);
          case 'expires':
            expires = _cookieDate(val);
        }
      }
      if (reject || secure && origin.scheme != 'https') continue;
      if (age != null) expires = _now().add(Duration(seconds: age));
      _cookies.removeWhere(
        (c) => c.origin == origin.origin && c.name == name && c.path == path,
      );
      if (expires == null || expires.isAfter(_now()))
        _cookies.add(
          _Cookie(origin.origin, name, value, path, secure, expires),
        );
    }
  }

  String headerFor(Uri target) {
    _cookies.removeWhere(
      (c) => c.expires != null && !c.expires!.isAfter(_now()),
    );
    final matched =
        _cookies
            .where(
              (c) =>
                  c.origin == target.origin &&
                  (!c.secure || target.scheme == 'https') &&
                  (target.path == c.path ||
                      target.path.startsWith(c.path) &&
                          (c.path.endsWith('/') ||
                              target.path
                                  .substring(c.path.length)
                                  .startsWith('/'))),
            )
            .toList()
          ..sort((a, b) => b.path.length.compareTo(a.path.length));
    return matched.map((c) => '${c.name}=${c.value}').join('; ');
  }
}

DateTime? _cookieDate(String text) {
  const months = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12,
  };
  final m = RegExp(
    r'(\d{1,2})[ -]([A-Za-z]{3})[ -](\d{2,4}) (\d{2}):(\d{2}):(\d{2})',
  ).firstMatch(text);
  if (m == null || !months.containsKey(m[2])) return DateTime.tryParse(text);
  var year = int.parse(m[3]!);
  if (year < 100) year += year >= 70 ? 1900 : 2000;
  return DateTime.utc(
    year,
    months[m[2]]!,
    int.parse(m[1]!),
    int.parse(m[4]!),
    int.parse(m[5]!),
    int.parse(m[6]!),
  );
}
