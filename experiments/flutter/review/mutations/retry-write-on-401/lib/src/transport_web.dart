import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

import 'api.dart';
import 'native_auth.dart';

class PlatformTransport implements ApiTransport {
  PlatformTransport(Uri configured)
    : baseUri = Uri.parse(web.window.location.origin) {
    validateOrigin(baseUri);
    if (configured.origin != baseUri.origin)
      throw ArgumentError('Web은 API와 동일 origin에서 실행해야 합니다.');
  }
  final Uri baseUri;
  int _session = 0;
  final _active = <void Function()>{};
  void invalidateRequests() {
    _session++;
    for (final abort in _active.toList()) {
      abort();
    }
    _active.clear();
  }

  void clearSession() => invalidateRequests();
  Future<void> login(ApiClient client) async {
    web.window.location.assign(baseUri.resolve('/api/auth/google').toString());
  }

  Future<void> openLink(Uri uri) async {
    web.window.open(uri.toString(), '_blank', 'noopener,noreferrer');
  }

  @override
  Future<ApiResponse> send(ApiRequest request) {
    final target = baseUri.resolve(request.path);
    if (target.origin != baseUri.origin)
      throw ArgumentError('다른 origin 요청을 거절했습니다.');
    final session = _session;
    final result = Completer<ApiResponse>();
    final xhr = web.XMLHttpRequest();
    xhr.open(request.method, target.toString());
    xhr.withCredentials = true;
    xhr.timeout = 25000;
    request.headers.forEach((name, value) => xhr.setRequestHeader(name, value));
    void fail(Object error) {
      if (!result.isCompleted) result.completeError(error);
    }

    void abort() {
      fail(const RequestCancelled());
      xhr.abort();
    }

    _active.add(abort);
    xhr.onload = ((web.Event event) {
      if (session != _session) {
        abort();
        return;
      }
      if (result.isCompleted) return;
      final text = xhr.responseText;
      if (text.length > 4 * 1024 * 1024) {
        fail(const FormatException('응답 크기를 초과했습니다.'));
        return;
      }
      final headers = <String, String>{};
      for (final line in xhr.getAllResponseHeaders().split('\r\n')) {
        final separator = line.indexOf(':');
        if (separator > 0)
          headers[line.substring(0, separator).toLowerCase()] = line
              .substring(separator + 1)
              .trim();
      }
      result.complete(ApiResponse(xhr.status, text, headers: headers));
    }).toJS;
    xhr.onerror = ((web.Event event) => fail(
      StateError('네트워크 연결을 확인해주세요.'),
    )).toJS;
    xhr.ontimeout = ((web.Event event) {
      fail(TimeoutException('요청 시간이 초과되었습니다.'));
      xhr.abort();
    }).toJS;
    xhr.onabort = ((web.Event event) => fail(const RequestCancelled())).toJS;
    xhr.onprogress = ((web.ProgressEvent event) {
      if (event.loaded > 4 * 1024 * 1024) {
        fail(const FormatException('응답 크기를 초과했습니다.'));
        xhr.abort();
      }
    }).toJS;
    request.cancel?.onCancel(() {
      xhr.abort();
      fail(const RequestCancelled());
    });
    if (request.cancel?.isCancelled != true) xhr.send(request.body?.toJS);
    return result.future.whenComplete(() => _active.remove(abort));
  }
}
