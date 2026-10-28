import http.server,threading,subprocess,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
ready=threading.Event();logout=threading.Event();events=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def result(self,status,body=b'',cookie=None):
  self.send_response(status)
  if cookie:self.send_header('Set-Cookie',cookie)
  self.send_header('Content-Length',str(len(body)));self.end_headers()
  try:self.wfile.write(body)
  except (BrokenPipeError,ConnectionResetError):events.append('client-disconnected')
 def do_GET(self):
  if self.path=='/probe':self.result(200,b'ready' if ready.is_set() else b'waiting')
  elif self.path=='/api/auth/csrf':self.result(200,b'{"headerName":"X-XSRF-TOKEN","token":"fixture"}')
  else:self.result(401,b'{}')
 def do_POST(self):
  if self.path=='/api/auth/refresh':
   events.append('refresh-pending');ready.set();logout.wait(5);time.sleep(.3)
   self.result(204,cookie='access_token=synthetic; Path=/; HttpOnly');events.append('late-refresh-response-attempted')
  else:
   events.append('logout-response');self.result(204);logout.set()
server=http.server.ThreadingHTTPServer(('127.0.0.1',18097),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with (OUT/'cookie-race.log').open('w') as log:r=subprocess.run([str(OUT/'cookie-race')],stdout=log,stderr=log,timeout=15)
 (OUT/'cookie-race-result.json').write_text(json.dumps({'exit_code':r.returncode,'server_events':events,'claim':'Actual URLSession private cookie jar; loopback late refresh versus logout. Synthetic HTTP server, not Rust/provider.'},indent=2)+'\n')
finally:server.shutdown();server.server_close()
raise SystemExit(r.returncode)
