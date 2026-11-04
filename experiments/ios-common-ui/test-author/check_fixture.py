#!/usr/bin/env python3
"""Independent ephemeral-loopback fixture contract smoke; no Simulator/build."""
import importlib.util
import json
from pathlib import Path
from threading import Thread
from urllib.request import urlopen, Request
from urllib.error import HTTPError
spec = importlib.util.spec_from_file_location("common_fixture", Path(__file__).with_name("ui_fixture.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
assert issubclass(fixture.Handler, fixture.sdk.Handler)
server = fixture.sdk.original.ThreadingHTTPServer(("127.0.0.1", 0), fixture.Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}"
def get(path):
    with urlopen(base + path) as response:
        return json.load(response)
try:
    today = get('/api/news/today')['items']
    assert len(today) == 11 and today[0]['id'] == 171 and today[-1]['id'] == 181
    assert today[0]['imageUrl'] == '/fixture/photo.jpg' and today[1]['imageUrl'] is None
    assert today[2]['imageUrl'] == '/fixture/missing.png'
    with urlopen(base + today[0]['imageUrl']) as response:
        assert response.headers['Content-Type'] == 'image/jpeg' and response.read() == fixture.JPEG_PHOTO
    with urlopen(base + '/fixture/photo.png') as response:
        assert response.headers['Content-Type'] == 'image/png' and response.read().startswith(b'\x89PNG')
    assert get('/api/search/news?q=%EC%8B%9C%EC%9E%A5')['content'][0]['id'] == 72
    assert get('/api/news/72')['title'] == '검색 전용 결과'
    assert get('/api/news/172')['id'] == 172
    try:
        get('/api/users/me')
        raise AssertionError('unauthenticated profile was accepted')
    except HTTPError as error:
        assert error.code == 401
    try:
        urlopen(Request(base + '/api/feedback', data=b'{}', headers={'Content-Type': 'application/json'}))
        raise AssertionError('missing CSRF was accepted')
    except HTTPError as error:
        assert error.code == 403
    print('PASS inherited SDK Handler; 11 today fixtures; relative/photo/none/error URLs; original content[] search/detail; unauthenticated401; missingCSRF403')
finally:
    server.shutdown(); server.server_close(); thread.join()
