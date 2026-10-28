#!/usr/bin/env python3
"""Synthetic iOS UI-test fixture. This is NOT Rust/DB integration evidence.
Run before Xcode UI tests: python3 experiments/ios-native/verification/ui_fixture.py
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from urllib.parse import parse_qs, urlsplit
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  parsed=urlsplit(self.path);query=parse_qs(parsed.query)
  if parsed.path=='/api/stocks':
   body='{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI","currency":"KRW"}]}' if query.get('q')==['삼성'] else '{"stocks":[]}'
   status=200
  elif parsed.path=='/api/stocks/1/price':
   time.sleep(2.5)
   body='{"assetId":1,"assetCode":"005930","name":"삼성전자","closePrice":123.4500,"baseDate":"2026-10-24","currency":"KRW"}';status=200
  else:body='{"code":"STOCK_PRICE_NOT_FOUND"}';status=404
  data=body.encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=18082);args=parser.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 print(f'Synthetic UI fixture http://127.0.0.1:{args.port}; not Rust/DB evidence',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
