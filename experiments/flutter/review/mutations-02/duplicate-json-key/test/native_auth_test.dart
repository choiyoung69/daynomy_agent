import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';
import 'support/fakes.dart';

class FakeBroker implements NativeAuthBroker {
  FakeBroker(this.reply);
  final Future<String?> Function(Uri) reply;
  final starts=<Uri>[];
  @override
  Future<String?> authenticate(Uri authorizationUri,{required String callbackScheme}) {
    expect(callbackScheme,'org.daynomy.app');
    starts.add(authorizationUri);
    return reply(authorizationUri);
  }
}

String callback(Uri uri,{String? state,String? scheme,String? host,String? path,String? code}) => Uri(
  scheme:scheme ?? 'org.daynomy.app',host:host ?? 'auth',path:path ?? '/callback',
  queryParameters:{'state':state ?? uri.queryParameters['state']!,'code':code ?? 'opaque-test-only-code'},
).toString();

void main() {
  test('S256 challenge/state는 외부 UA에, verifier는 HTTPS exchange body에만 전송',() async {
    final transport=FakeTransport((_)=>ApiResponse(204,''));
    final broker=FakeBroker((uri) async=>callback(uri));
    final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:broker,
      baseUri:Uri.parse('https://api.daynomy.test'),randomBytes:(count)=>List<int>.generate(count,(i)=>i));
    await coordinator.login();
    final start=broker.starts.single;
    expect(start.scheme,'https');
    expect(start.host,'api.daynomy.test');
    expect(start.path,'/api/auth/mobile/start');
    final verifier=base64Url.encode(List<int>.generate(32,(i)=>i)).replaceAll('=','');
    final challenge=base64Url.encode(sha256.convert(utf8.encode(verifier)).bytes).replaceAll('=','');
    expect(start.queryParameters['code_challenge'],challenge);
    expect(start.queryParameters['state'],matches(RegExp(r'^[A-Za-z0-9_-]{32,128}$')));
    expect(start.toString(),isNot(contains(verifier)));
    final exchange=transport.requests.single;
    expect(Uri.parse(exchange.path).path,'/api/auth/mobile/exchange');
    expect(exchange.method,'POST');
    expect(exchange.headers.keys.any((k)=>k.toLowerCase().contains('csrf')),isFalse);
    expect(decodeJsonExact(exchange.body!),{'code':'opaque-test-only-code','codeVerifier':verifier});
    expect(transport.requests.any((r)=>r.path=='/api/auth/csrf'),isFalse);
  });
  for (final invalid in <String Function(Uri)>[
    (uri)=>callback(uri,state:'wrong-state'),
    (uri)=>callback(uri,scheme:'https'),
    (uri)=>callback(uri,host:'evil'),
    (uri)=>callback(uri,path:'/different'),
    (uri)=>'org.daynomy.app://auth/callback?code=only-code',
    (uri)=>'org.daynomy.app://auth/callback?state=${uri.queryParameters['state']}',
    (uri)=>'org.daynomy.app://auth/callback?code=a&code=b&state=${uri.queryParameters['state']}',
    (uri)=>'org.daynomy.app://auth/callback?code=a&state=${uri.queryParameters['state']}&state=other',
    (uri)=>'org.daynomy.app://user@auth/callback?code=a&state=${uri.queryParameters['state']}',
    (uri)=>'org.daynomy.app://auth:444/callback?code=a&state=${uri.queryParameters['state']}',
  ]) {
    test('콜백 origin/path/state/필드가 불일치하면 exchange하지 않는다 #${invalid.hashCode}',() async {
      final transport=FakeTransport((_)=>ApiResponse(204,''));
      final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:FakeBroker((uri) async=>invalid(uri)),baseUri:Uri.parse('https://api.daynomy.test'));
      await expectLater(coordinator.login(),throwsA(isA<NativeAuthException>()));
      expect(transport.requests,isEmpty);
    });
  }
  test('인증 세션 취소는 cancelled, exchange 요청 없음',() async {
    final transport=FakeTransport((_)=>ApiResponse(204,''));
    final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:FakeBroker((_) async=>null),baseUri:Uri.parse('https://api.daynomy.test'));
    await expectLater(coordinator.login(),throwsA(isA<NativeAuthException>().having((e)=>e.code,'code','cancelled')));
    expect(transport.requests,isEmpty);
  });
  test('검증된 provider 오류 콜백도 exchange하지 않는다',() async {
    final transport=FakeTransport((_)=>ApiResponse(204,''));
    final broker=FakeBroker((uri) async=>'org.daynomy.app://auth/callback?state=${uri.queryParameters['state']}&error=access_denied');
    final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:broker,baseUri:Uri.parse('https://api.daynomy.test'));
    await expectLater(coordinator.login(),throwsA(isA<NativeAuthException>()));
    expect(transport.requests,isEmpty);
  });
  test('exchange 401은 로그인 실패이며 refresh 또는 exchange 반복 없음',() async {
    final transport=FakeTransport((_)=>ApiResponse(401,'{"code":"INVALID_MOBILE_AUTH_CODE"}'));
    final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:FakeBroker((uri) async=>callback(uri)),baseUri:Uri.parse('https://api.daynomy.test'));
    await expectLater(coordinator.login(),throwsA(anyOf(isA<ApiException>(),isA<NativeAuthException>())));
    expect(transport.requests.length,1);
  });
  test('임의 HTTP origin으로 로그인 정보를 보내지 않는다',() async {
    final transport=FakeTransport((_)=>ApiResponse(204,''));
    final broker=FakeBroker((uri) async=>callback(uri));
    await expectLater(() async {
      final coordinator=NativeAuthCoordinator(client:ApiClient(transport:transport),broker:broker,baseUri:Uri.parse('http://untrusted.example'));
      await coordinator.login();
    },throwsA(anyOf(isA<ArgumentError>(),isA<NativeAuthException>())));
    expect(transport.requests,isEmpty);
    expect(broker.starts,isEmpty);
  });

  group('native 메모리 cookie jar',() {
    final origin=Uri.parse('https://api.daynomy.test/api/users/me');
    test('HttpOnly 쿠키를 동일 origin API에 보내고 다른 host로 누출하지 않는다',() {
      final jar=MemoryCookieJar();
      jar.accept(origin,['access_token=fixture-access; Path=/; Secure; HttpOnly; SameSite=Lax','refresh_token=fixture-refresh; Path=/api/auth; Secure; HttpOnly']);
      expect(jar.headerFor(origin),contains('access_token=fixture-access'));
      expect(jar.headerFor(origin),isNot(contains('refresh_token')));
      expect(jar.headerFor(Uri.parse('https://api.daynomy.test/api/auth/refresh')),contains('refresh_token=fixture-refresh'));
      expect(jar.headerFor(Uri.parse('https://evil.test/api/users/me')),isEmpty);
      expect(jar.headerFor(Uri.parse('https://api.daynomy.test:444/api/users/me')),isEmpty);
      expect(jar.headerFor(Uri.parse('http://api.daynomy.test/api/users/me')),isEmpty);
    });
    test('cross-site Domain 쿠키 거절과 path 경계 검사',() {
      final jar=MemoryCookieJar();
      jar.accept(origin,['a=fixture-a; Domain=evil.test; Path=/','b=fixture-b; Path=/api/auth; Secure']);
      expect(jar.headerFor(origin),isEmpty);
      expect(jar.headerFor(Uri.parse('https://api.daynomy.test/api/authentication')),isEmpty);
      expect(jar.headerFor(Uri.parse('https://api.daynomy.test/api/auth/logout')),contains('b=fixture-b'));
    });
    test('Max-Age/삭제/앱 종료 clear, 새 jar에 지속되지 않음',() {
      var now=DateTime.utc(2026,10,28);
      final jar=MemoryCookieJar(now:()=>now);
      jar.accept(origin,['a=fixture-a; Max-Age=10; Path=/','b=fixture-b; Path=/']);
      expect(jar.headerFor(origin),contains('a=fixture-a'));
      now=now.add(const Duration(seconds:11));
      expect(jar.headerFor(origin),isNot(contains('a=')));
      jar.accept(origin,['b=; Max-Age=0; Path=/']);
      expect(jar.headerFor(origin),isEmpty);
      jar.accept(origin,['c=fixture-c; Path=/']);
      jar.clear();
      expect(jar.headerFor(origin),isEmpty);
      expect(MemoryCookieJar().headerFor(origin),isEmpty);
    });
  });
}
