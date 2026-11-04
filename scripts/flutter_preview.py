#!/usr/bin/env python3
"""Serve a Flutter web build and proxy the local API on one loopback origin."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
       'te', 'trailer', 'transfer-encoding', 'upgrade', 'host'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18300)
    parser.add_argument('--api', default='http://127.0.0.1:18086')
    parser.add_argument('--build', type=Path, default=ROOT / 'clients/flutter/build/web')
    args = parser.parse_args()
    api = urlsplit(args.api)
    if api.scheme != 'http' or api.hostname not in ('127.0.0.1', 'localhost') or api.path not in ('', '/') or api.username or api.password or api.query or api.fragment:
        parser.error('api must be a loopback HTTP origin')
    build = args.build.resolve()
    if not (build / 'index.html').is_file():
        parser.error('build/index.html missing; run flutter build web first')
    mimetypes.add_type('application/wasm', '.wasm')
    mimetypes.add_type('text/javascript', '.mjs')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Paths can contain authorization codes; do not log requests.

        def handle_request(self):
            path = urlsplit(self.path).path
            if path.startswith(('/api/', '/oauth2/', '/login/oauth2/')):
                connection = http.client.HTTPConnection(api.hostname, api.port or 80, timeout=45)
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if size < 0 or size > 2 * 1024 * 1024:
                        return self.send_error(413)
                    body = self.rfile.read(size) if size else None
                    headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP}
                    connection.request(self.command, self.path, body, headers)
                    response = connection.getresponse()
                    data = response.read(8 * 1024 * 1024 + 1)
                    if len(data) > 8 * 1024 * 1024:
                        return self.send_error(502)
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() not in HOP | {'content-length'}:
                            self.send_header(key, value)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    if self.command != 'HEAD':
                        self.wfile.write(data)
                except (OSError, ValueError, http.client.HTTPException):
                    self.send_error(502, 'Local API unavailable')
                finally:
                    connection.close()
                return
            if self.command not in ('GET', 'HEAD'):
                return self.send_error(405)
            target = (build / unquote(path).lstrip('/')).resolve()
            if not target.is_relative_to(build):
                return self.send_error(403)
            if target.is_dir():
                target /= 'index.html'
            if not target.is_file():
                if target.suffix:
                    return self.send_error(404)
                target = build / 'index.html'
            data = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        do_GET = do_HEAD = do_POST = do_PATCH = do_DELETE = do_OPTIONS = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Flutter preview: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
