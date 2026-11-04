import http from 'node:http';
import https from 'node:https';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, sep } from 'node:path';

const args = process.argv.slice(2);
function option(name, fallback) {
  const at = args.indexOf(name);
  if (at < 0) return fallback;
  if (!args[at + 1] || args[at + 1].startsWith('--')) throw new Error(`Missing ${name} value`);
  return args[at + 1];
}
const port = Number(option('--port', '18082'));
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid local port');
const api = new URL(option('--api-origin', 'http://127.0.0.1:18081'));
if (!['http:', 'https:'].includes(api.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(api.hostname) || api.username || api.password || api.pathname !== '/' || api.search || api.hash) throw new Error('API origin must be an explicit loopback HTTP(S) origin');
const webRoot = resolve(fileURLToPath(new URL('../web/', import.meta.url)));
const hopHeaders = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade', 'host']);
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };
function fail(response, code) {
  if (response.headersSent) { response.destroy(); return; }
  response.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  response.end(JSON.stringify({ message: code === 502 ? 'API 서버에 연결할 수 없습니다.' : '요청한 경로를 제공하지 않습니다.' }));
}
const server = http.createServer(async (request, response) => {
  const raw = request.url ?? '/';
  if (!raw.startsWith('/') || raw.startsWith('//') || /%2f|%5c|\\|\0/i.test(raw)) { fail(response, 400); return; }
  let url;
  try { url = new URL(raw, 'http://localhost'); } catch { fail(response, 400); return; }
  if (url.pathname.startsWith('/api/')) {
    if (request.method !== 'GET' && request.method !== 'HEAD') { fail(response, 405); return; }
    const headers = {};
    for (const [key, value] of Object.entries(request.headers)) if (!hopHeaders.has(key.toLowerCase()) && value !== undefined) headers[key] = value;
    headers.host = api.host;
    const transport = api.protocol === 'https:' ? https : http;
    const upstream = transport.request(api, { method: request.method, path: url.pathname + url.search, headers }, result => {
      const resultHeaders = {};
      for (const [key, value] of Object.entries(result.headers)) if (!hopHeaders.has(key.toLowerCase()) && value !== undefined) resultHeaders[key] = value;
      resultHeaders['cache-control'] = 'no-store';
      response.writeHead(result.statusCode ?? 502, resultHeaders);
      result.pipe(response);
      result.on('error', () => response.destroy());
    });
    upstream.setTimeout(15000, () => upstream.destroy(new Error('API timeout')));
    upstream.on('error', () => fail(response, 502));
    request.on('aborted', () => upstream.destroy());
    response.on('close', () => { if (!response.writableEnded) upstream.destroy(); });
    upstream.end();
    return;
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') { fail(response, 405); return; }
  const pathname = url.pathname;
  let relative;
  if (pathname === '/') relative = 'index.html';
  else if (pathname === '/styles.css') relative = 'styles.css';
  else if (/^\/dist\/[A-Za-z0-9_-]+\.js$/.test(pathname)) relative = pathname.slice(1);
  else { fail(response, 404); return; }
  const file = resolve(webRoot, relative);
  if (!file.startsWith(webRoot + sep)) { fail(response, 404); return; }
  try {
    const body = await readFile(file);
    const extension = '.' + relative.split('.').at(-1);
    response.writeHead(200, {
      'Content-Type': mime[extension] ?? 'application/octet-stream',
      'Content-Length': body.length,
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
      'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch { fail(response, 404); }
});
server.listen(port, '127.0.0.1', () => console.log(`DAYNOMY local WebView server ready on port ${port}; loopback API proxy configured`));
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => server.close(() => process.exit(0)));
