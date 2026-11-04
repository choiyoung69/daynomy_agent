import 'dart:async';
import 'dart:io';

import 'package:daynomy_flutter/daynomy.dart';
import 'package:daynomy_flutter/src/transport_native.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late HttpServer server;
  late Uri origin;
  late PlatformTransport transport;
  late Future<void> Function(HttpRequest) handler;
  setUp(() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    origin = Uri.parse('http://127.0.0.1:${server.port}');
    transport = PlatformTransport(origin);
    handler = (request) async { request.response.write('{}'); await request.response.close(); };
    server.listen((request) async {
      try { await handler(request); } on Object { /* A cancelled client may disconnect. */ }
    });
  });
  tearDown(() async {
    transport.clearSession();
    await server.close(force: true);
  });

  test('real HTTP accepts HttpOnly cookies with path isolation and clears session', () async {
    final seen = <String, String>{};
    handler = (request) async {
      seen[request.uri.path] = request.headers.value('cookie') ?? '';
      if (request.uri.path == '/api/session') {
        request.response.headers.add('set-cookie', 'access=fixture; HttpOnly; Path=/');
        request.response.headers.add('set-cookie', 'refresh=fixture; HttpOnly; Path=/api/auth');
        request.response.headers.add('set-cookie', 'bad=fixture; Domain=elsewhere.invalid; Path=/');
        request.response.headers.add('set-cookie', 'secure=fixture; Secure; Path=/');
      }
      request.response.write('{}'); await request.response.close();
    };
    await transport.send(ApiRequest('/api/session'));
    await transport.send(ApiRequest('/api/portfolio'));
    await transport.send(ApiRequest('/api/auth/refresh'));
    await transport.send(ApiRequest('/api/authentic'));
    expect(seen['/api/portfolio'], 'access=fixture');
    expect(seen['/api/auth/refresh'], contains('refresh=fixture'));
    expect(seen['/api/authentic'], 'access=fixture');
    transport.clearSession();
    await transport.send(ApiRequest('/api/after-clear'));
    expect(seen['/api/after-clear'], '');
  });

  test('real HTTP caller cancellation resolves before delayed headers', () async {
    final entered = Completer<void>(), release = Completer<void>();
    handler = (request) async {
      entered.complete(); await release.future;
      request.response.write('{}'); await request.response.close();
    };
    final token = CancellationToken();
    final request = transport.send(ApiRequest('/api/slow', cancel: token));
    final assertion = expectLater(request, throwsA(isA<RequestCancelled>()));
    await entered.future; token.cancel();
    await assertion.timeout(const Duration(seconds: 2));
    release.complete();
  });

  test('real HTTP clearSession aborts and cannot restore late Set-Cookie', () async {
    final entered = Completer<void>(), release = Completer<void>();
    handler = (request) async {
      if (request.uri.path == '/api/slow') {
        entered.complete(); await release.future;
        request.response.headers.add('set-cookie', 'late=fixture; Path=/');
      }
      request.response.write('{}'); await request.response.close();
    };
    final pending = transport.send(ApiRequest('/api/slow'));
    final assertion = expectLater(pending, throwsA(isA<RequestCancelled>()));
    await entered.future; transport.clearSession();
    await assertion.timeout(const Duration(seconds: 2));
    release.complete();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await transport.send(ApiRequest('/api/after'));
    expect(transport.jar.headerFor(origin.resolve('/api/after')), isEmpty);
  });

  test('real HTTP streamed body cancellation finishes immediately', () async {
    final firstChunk = Completer<void>(), release = Completer<void>();
    handler = (request) async {
      request.response.write('{'); await request.response.flush();
      firstChunk.complete(); await release.future;
      request.response.write('}'); await request.response.close();
    };
    final token = CancellationToken();
    final pending = transport.send(ApiRequest('/api/stream', cancel: token));
    final assertion = expectLater(pending, throwsA(isA<RequestCancelled>()));
    await firstChunk.future; token.cancel();
    await assertion.timeout(const Duration(seconds: 2)); release.complete();
  });

  test('real HTTP refuses redirects, cross-origin and oversized response', () async {
    handler = (request) async {
      if (request.uri.path == '/api/redirect') {
        request.response.statusCode = 302;
        request.response.headers.set('location', '/api/destination');
      } else {
        request.response.write('x' * (PlatformTransport.maxBytes + 1));
      }
      await request.response.close();
    };
    expect((await transport.send(ApiRequest('/api/redirect'))).status, 302);
    await expectLater(transport.send(ApiRequest('https://elsewhere.invalid/api/')), throwsArgumentError);
    await expectLater(transport.send(ApiRequest('/api/large')), throwsFormatException);
  });

  test('real HTTP timeout aborts a stalled server response', () async {
    final release = Completer<void>();
    handler = (request) async { await release.future; await request.response.close(); };
    await expectLater(transport.send(ApiRequest('/api/timeout')), throwsA(isA<TimeoutException>()));
    release.complete();
  }, timeout: const Timeout(Duration(seconds: 35)));
}
