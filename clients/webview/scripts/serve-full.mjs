import http from 'node:http';
import https from 'node:https';
import { open, realpath } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, isAbsolute, sep, extname } from 'node:path';

// No application secrets or request values are logged by this local server.
const args = process.argv.slice(2);
const options = new Map();
for (let i = 0; i < args.length; i += 2) {
  if (!['--port', '--api-origin', '--dist'].includes(args[i]) || !args[i + 1] || options.has(args[i])) throw new Error('Invalid CLI options');
  options.set(args[i], args[i + 1]);
}
const port = Number(options.get('--port') ?? '18082');
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid local port');
const origin = options.get('--api-origin') ?? 'http://127.0.0.1:18081';
const api = new URL(origin);
if (!['http:', 'https:'].includes(api.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(api.hostname) || api.username || api.password || api.pathname !== '/' || api.search || api.hash || !/^https?:\/\/(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?\/?$/.test(origin)) throw new Error('API origin must be an explicit loopback origin');
const dist = options.get('--dist') ?? fileURLToPath(new URL('../fullweb/dist', import.meta.url));
if (!isAbsolute(dist)) throw new Error('Dist must be absolute');
const root = await realpath(dist);
const hop = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade', 'host']);
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.webmanifest': 'application/manifest+json', '.mp4': 'video/mp4', '.avif': 'image/avif' };
const security = {
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'no-referrer',
  'x-frame-options': 'DENY',
  'content-security-policy': "default-src 'self'; script-src 'self' https://platform.x.com https://www.threads.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; media-src 'self' https:; frame-src https:; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
};
function fail(res, code) {
  if (res.destroyed) return;
  if (res.headersSent) { res.destroy(); return; }
  res.writeHead(code, { ...security, 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ message: code === 502 ? 'API 서버에 연결할 수 없습니다.' : '요청한 경로를 제공하지 않습니다.' }));
}
function filtered(headers) {
  const omit = new Set([...hop, ...(headers.connection ?? '').split(',').map(v => v.trim().toLowerCase())]);
  return Object.fromEntries(Object.entries(headers).filter(([key, value]) => !omit.has(key) && value !== undefined));
}
function validatedPath(raw) {
  if (!raw.startsWith('/') || raw.startsWith('//') || /[\\\x00-\x20\x7f#]|%(?![\da-f]{2})/i.test(raw)) return null;
  const path = raw.split('?')[0];
  // Encoded separators are dangerous only in the routing/filesystem path.
  // Query values (returnTo, search text, OAuth scopes) remain opaque bytes.
  if (/%2f|%5c/i.test(path)) return null;
  let decoded;
  try { decoded = decodeURIComponent(path); } catch { return null; }
  // Validate before URL normalization, including encoded dot segments.
  if (/[\\\x00-\x1f\x7f]/.test(decoded) || decoded.split('/').some(s => s === '.' || s === '..' || s.startsWith('.') || /%[\da-f]{2}/i.test(s))) return null;
  if (decoded.split('/').some(s => ['src', 'node_modules'].includes(s)) || /\.(?:map|tsx?|jsx|mjs|cjs|pem|key|lock)$/i.test(decoded)) return null;
  return decoded;
}
function spa(path) {
  if (extname(path)) return false;
  return /^(?:\/(?:welcome|portfolio(?:\/records)?|investment-calendar|mypage|search|stocks|people|login|signup|about|terms|privacy|standard)?|\/news(?:\/[^/]+)?|\/stocks\/[^/]+(?:\/card-preview)?|\/finance(?:\/[^/]+)*|\/admin(?:\/(?:news(?:\/(?:new|[^/]+\/edit))?|feedbacks|stocks|stock-contents|people))?)\/?$/.test(path);
}
async function staticFile(path, req, res) {
  let handle;
  try {
    const canonical = await realpath(resolve(root, '.' + path));
    if (!canonical.startsWith(root + sep)) return false;
    if (validatedPath('/' + canonical.slice(root.length + 1).split(sep).join('/')) === null) return false;
    handle = await open(canonical, 'r');
    const stat = await handle.stat();
    if (!stat.isFile()) { await handle.close(); return false; }
    res.writeHead(200, { ...security, 'content-type': mime[extname(canonical).toLowerCase()] ?? 'application/octet-stream', 'content-length': stat.size });
    if (req.method === 'HEAD') { await handle.close(); res.end(); return true; }
    const stream = handle.createReadStream();
    stream.on('error', () => res.destroy());
    res.on('close', () => stream.destroy());
    stream.pipe(res);
    return true;
  } catch { if (handle) await handle.close().catch(() => {}); return false; }
}
const server = http.createServer(async (req, res) => {
  const raw = req.url ?? '/';
  const path = validatedPath(raw);
  if (path === null) { fail(res, 400); return; }
  if (/^\/(?:api|oauth2|login\/oauth2)(?:\/|$)/.test(path)) {
    if (!['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'].includes(req.method)) { fail(res, 405); return; }
    const headers = filtered(req.headers);
    headers.host = api.host;
    // Origin is deliberately untouched: backend CORS/CSRF sees the actual client.
    const transport = api.protocol === 'https:' ? https : http;
    const upstream = transport.request(api, { method: req.method, path: raw, headers }, result => {
      const resultHeaders = { ...filtered(result.headers), ...security };
      res.writeHead(result.statusCode ?? 502, resultHeaders);
      result.on('error', () => res.destroy());
      result.pipe(res);
    });
    upstream.setTimeout(30000, () => upstream.destroy());
    upstream.on('error', () => fail(res, 502));
    req.on('aborted', () => upstream.destroy());
    req.on('error', () => upstream.destroy());
    res.on('close', () => { if (!res.writableEnded) upstream.destroy(); });
    req.pipe(upstream);
    return;
  }
  if (!['GET', 'HEAD'].includes(req.method)) { fail(res, 404); return; }
  if (await staticFile(path === '/' ? '/index.html' : path, req, res)) return;
  if (spa(path) && /(?:^|,)\s*text\/html(?:\s*;[^,]*)?(?:,|$)/i.test(req.headers.accept ?? '')) {
    if (await staticFile('/index.html', req, res)) return;
  }
  fail(res, 404);
});
server.on('clientError', (_error, socket) => { socket.end('HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n'); });
server.listen(port, '127.0.0.1', () => console.log(`DAYNOMY full WebView ready on port ${port}`));
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => { server.close(() => process.exit(0)); server.closeAllConnections(); });
