import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:daynomy_flutter/daynomy.dart';
import 'support/fakes.dart';

void main() {
  test('요청은 cookie credentials와 취소 토큰을 전송에 전달한다', () async {
    final token = CancellationToken();
    var cancelled = false;
    final transport = FakeTransport((request) {
      request.cancel?.onCancel(() => cancelled = true);
      return ApiResponse(200, '{}');
    });
    final client = ApiClient(transport: transport);
    await client.request('/api/stocks?q=AAPL', cancel: token);
    expect(transport.requests.single.credentials, isTrue);
    expect(transport.requests.single.cancel, same(token));
    token.cancel();
    expect(token.isCancelled, isTrue);
    expect(cancelled, isTrue);
  });

  test('204는 빈 body를 JSON 파싱하지 않고 null을 반환한다', () async {
    final client = ApiClient(transport: FakeTransport((_) => ApiResponse(204, '')));
    expect(await client.request('/api/feedback', method: 'POST'), isNull);
  });

  test('쓰기 전 CSRF 조회하고 지정 headerName·정확한 금액 JSON을 보낸다', () async {
    final transport = FakeTransport((request) => request.path == '/api/auth/csrf'
        ? ApiResponse(200, '{"headerName":"X-CUSTOM-CSRF","token":"fixture-token"}')
        : ApiResponse(204, ''));
    await ApiClient(transport: transport).request('/api/portfolio/transactions', method: 'POST', csrf: true,
      body: {'assetId': 1, 'unitPrice': ExactNumber('9007199254740993.0100')});
    expect(transport.requests.map((r) => r.path), ['/api/auth/csrf', '/api/portfolio/transactions']);
    final write = transport.requests.last;
    expect(write.headers['X-CUSTOM-CSRF'], 'fixture-token');
    expect(write.headers.entries.any((e) => e.key.toLowerCase() == 'content-type' && e.value.contains('application/json')), isTrue);
    expect(write.body, '{"assetId":1,"unitPrice":9007199254740993.0100}');
  });

  for (final body in ['{}', '{"headerName":"X-CSRF","token":""}', '{"headerName":"","token":"x"}', '{"headerName":2,"token":"x"}', '[]']) {
    test('malformed CSRF 이후 쓰기를 보내지 않는다: $body', () async {
      final transport = FakeTransport((_) => ApiResponse(200, body));
      final call = ApiClient(transport: transport).request('/api/feedback', method: 'POST', csrf: true, body: {'content':'a'});
      await expectLater(call, throwsFormatException);
      expect(transport.requests.map((r) => r.path), ['/api/auth/csrf']);
    });
  }

  test('동시 GET 401은 refresh 1개를 공유하고 각각 1회만 재전송한다', () async {
    final refresh = Completer<ApiResponse>();
    final counts = <String,int>{};
    final transport = FakeTransport((request) {
      counts.update(request.path, (n) => n+1, ifAbsent: () => 1);
      if (request.path == '/api/auth/csrf') return ApiResponse(200, csrfBody);
      if (request.path == '/api/auth/refresh') return refresh.future;
      return counts[request.path] == 1 ? ApiResponse(401, '{"code":"ACCESS_EXPIRED"}') : ApiResponse(200, '{}');
    });
    final client = ApiClient(transport: transport);
    final first = client.request('/api/users/me');
    final second = client.request('/api/users/me/portfolio');
    await Future<void>.delayed(Duration.zero);
    expect(counts['/api/auth/refresh'], 1);
    expect(transport.requests.singleWhere((r) => r.path == '/api/auth/refresh').headers['X-XSRF-TOKEN'], 'test-only-token');
    refresh.complete(ApiResponse(204, ''));
    await Future.wait([first,second]);
    expect(counts['/api/users/me'], 2);
    expect(counts['/api/users/me/portfolio'], 2);
    expect(counts['/api/auth/refresh'], 1);
  });

  test('refresh 실패는 원래 GET을 다시 보내지 않으며 루프를 만들지 않는다', () async {
    final transport = FakeTransport((request) => request.path == '/api/auth/csrf'
        ? ApiResponse(200, csrfBody) : ApiResponse(401, '{"code":"UNAUTHORIZED","message":"로그인이 필요합니다."}'));
    await expectLater(ApiClient(transport: transport).request('/api/users/me'), throwsA(isA<ApiException>().having((e) => e.status,'status',401)));
    expect(transport.requests.where((r) => r.path == '/api/users/me').length, 1);
    expect(transport.requests.where((r) => r.path == '/api/auth/refresh').length, 1);
  });

  test('refresh 성공 뒤 GET이 다시 401이면 두 번째 refresh를 보내지 않는다', () async {
    final transport = FakeTransport((request) {
      if (request.path == '/api/auth/csrf') return ApiResponse(200, csrfBody);
      if (request.path == '/api/auth/refresh') return ApiResponse(204, '');
      return ApiResponse(401, '{}');
    });
    await expectLater(ApiClient(transport: transport).request('/api/users/me'), throwsA(isA<ApiException>()));
    expect(transport.requests.where((r) => r.path == '/api/users/me').length, 2);
    expect(transport.requests.where((r) => r.path == '/api/auth/refresh').length, 1);
  });

  for (final method in ['POST','PATCH','DELETE']) {
    for (final status in [401,403,409,429,503]) {
      test('$method $status를 자동 재전송하지 않는다', () async {
        final transport = FakeTransport((request) => request.path == '/api/auth/csrf' ? ApiResponse(200, csrfBody) : ApiResponse(status, '{"code":"CONFLICT","message":"다시 확인해주세요."}'));
        await expectLater(ApiClient(transport: transport).request('/api/portfolio/transactions', method:method, csrf:true), throwsA(isA<ApiException>().having((e)=>e.status,'status',status)));
        expect(transport.requests.where((r)=>r.path == '/api/portfolio/transactions').length, 1);
        expect(transport.requests.where((r)=>r.path == '/api/auth/refresh'), isEmpty);
      });
    }
  }
  test('쓰기 timeout은 처리 여부 불명 상태를 유지하며 반복하지 않는다', () async {
    final transport = FakeTransport((request) {
      if (request.path == '/api/auth/csrf') return ApiResponse(200, csrfBody);
      throw TimeoutException('fixture timeout');
    });
    await expectLater(ApiClient(transport: transport).request('/api/feedback', method:'POST',csrf:true), throwsA(isA<TimeoutException>()));
    expect(transport.requests.where((r)=>r.path == '/api/feedback').length, 1);
  });
  test('JSON 에러 code/message를 보존한다', () async {
    final transport = FakeTransport((_) => ApiResponse(403,'{"code":"GUEST_ANALYSIS_LIMIT_EXCEEDED","message":"체험을 모두 사용했습니다."}'));
    await expectLater(ApiClient(transport:transport).request('/api/portfolio/analysis',method:'POST'),throwsA(isA<ApiException>()
      .having((e)=>e.code,'code','GUEST_ANALYSIS_LIMIT_EXCEEDED').having((e)=>e.message,'message','체험을 모두 사용했습니다.')));
  });
  test('HTML 오류 body에도 HTTP status를 잃지 않는다', () async {
    final transport = FakeTransport((_) => ApiResponse(502,'<html>gateway</html>', headers: {'content-type':'text/html'}));
    await expectLater(ApiClient(transport:transport).request('/api/news'),throwsA(isA<ApiException>().having((e)=>e.status,'status',502)));
  });
}
