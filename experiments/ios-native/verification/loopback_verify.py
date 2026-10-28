#!/usr/bin/env python3
"""Independent real socket/URLSession checks, without DB or original-server access."""
import argparse, hashlib, http.server, json, select, socket, subprocess, threading, time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
requested=threading.Event(); disconnected=threading.Event(); calls=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  parsed=urlsplit(self.path);query=parse_qs(parsed.query);calls.append({'path':parsed.path,'query':query,'method':'GET'})
  if parsed.path=='/__status': return self.send(200,'requested' if requested.is_set() else 'waiting')
  if parsed.path=='/api/stocks' and query.get('q')==['cancel']:
   requested.set()
   deadline=time.monotonic()+6
   while time.monotonic()<deadline:
    readable,_,_=select.select([self.connection],[],[],.05)
    if readable and self.connection.recv(1,socket.MSG_PEEK)==b'':disconnected.set();return
   return self.send(500,'{}')
  if parsed.path=='/api/stocks':
   valid=query=={'q':['삼성 & ETF%_!+?#'],'country':['US']}
   return self.send(200 if valid else 400,'{"stocks":[{"assetId":1,"assetCode":"005930","name":"삼성전자","category":"STOCK","market":"KOSPI"}]}')
  if parsed.path.endswith('/404/price'):return self.send(404,'{"code":"STOCK_PRICE_NOT_FOUND"}')
  if parsed.path.endswith('/405/price'):return self.send(404,'{"code":"OTHER"}')
  price='01' if parsed.path.endswith('/2/price') else '123456789012345678901234567890123456789.0000000001'
  return self.send(200,'{"assetId":1,"assetCode":"005930","name":"삼성전자","baseDate":"2026-10-23","closePrice":'+price+'}')
 def send(self,status,body):
  data=body.encode();self.send_response(status);self.send_header('Content-Length',str(len(data)));self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True,type=Path);args=parser.parse_args()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 started=time.monotonic()
 try:
  run=subprocess.run([str(args.binary.resolve()),'loopback',f'http://127.0.0.1:{server.server_port}'],capture_output=True,text=True,timeout=30)
  disconnected.wait(2)
  (OUT/'loopback.log').write_text(run.stdout+run.stderr)
  result={'exit_code':run.returncode,'elapsed_seconds':time.monotonic()-started,'slow_request_observed':requested.is_set(),'socket_disconnect_observed':disconnected.is_set(),'requests':calls,'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),'scope':'macOS URLSession real loopback HTTP; not iOS'}
  (OUT/'loopback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(run.stdout,run.stderr);print(json.dumps(result,ensure_ascii=False))
  return 0 if run.returncode==0 and requested.is_set() and disconnected.is_set() else 1
 finally:server.shutdown();server.server_close()
if __name__=='__main__':raise SystemExit(main())
