// Disposable development verification fixture; no production hosting configuration.
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import { readFileSync } from 'node:fs';
import { canonicalBasePath } from '../frontend/instance-config.ts';

export function validateRoutes(values) {
  if (!Array.isArray(values) || values.length < 2) throw new Error('At least two isolated routes are required.');
  const routes = values.map(value => {
    const prefix = canonicalBasePath(value.prefix);
    const target = new URL(value.target);
    if (prefix === '/' || target.protocol !== 'http:' || target.pathname !== '/' || target.username || target.password || target.search || target.hash) {
      throw new Error('Routes need a non-root mount and an internal HTTP origin.');
    }
    if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(value.instanceId)) throw new Error('Invalid instance ID.');
    return { prefix, target, instanceId: value.instanceId };
  });
  for (let i = 0; i < routes.length; i++) for (let j = i + 1; j < routes.length; j++) {
    if (routes[i].instanceId === routes[j].instanceId || routes[i].target.origin === routes[j].target.origin
        || routes[i].prefix.startsWith(routes[j].prefix) || routes[j].prefix.startsWith(routes[i].prefix)) {
      throw new Error('Instance mounts, IDs and targets must be distinct and mounts must not overlap.');
    }
  }
  return routes;
}

const routes = validateRoutes(JSON.parse(process.env.PREFIX_ROUTES));
// Fail startup if any route points at an instance with a different mount/identity.
for (const route of routes) {
  const deadline = Date.now() + 30000;
  while (true) {
    let response;
    try {
      response = await fetch(new URL(`${route.prefix}api/v1/health/`, route.target), { signal: AbortSignal.timeout(5000) });
    } catch (error) {
      if (Date.now() >= deadline) throw error;
    }
    if (response?.ok) {
      if (response.headers.get('X-Task-Tracker-Base-Path') !== route.prefix
          || response.headers.get('X-Task-Tracker-Instance') !== route.instanceId) throw new Error('Gateway route/instance configuration mismatch.');
      break;
    }
    if (Date.now() >= deadline) throw new Error('Gateway backend readiness deadline exceeded.');
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}

function match(rawUrl) {
  const path = rawUrl.split('?', 1)[0];
  return routes.find(route => path === route.prefix.slice(0, -1) || path.startsWith(route.prefix));
}
function forward(req, res) {
  const route = match(req.url);
  if (!route) { res.writeHead(404); res.end('Unknown instance path.'); return; }
  const [path] = req.url.split('?', 1);
  if (path === route.prefix.slice(0, -1)) {
    res.writeHead(308, { Location: route.prefix + req.url.slice(path.length) }); res.end(); return;
  }
  const upstream = http.request(new URL(req.url, route.target), {
    method: req.method, headers: { ...req.headers, host: route.target.host },
  }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
  upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Instance unavailable.'); });
  req.on('aborted', () => upstream.destroy());
  req.pipe(upstream);
}

function upgrade(req, socket, head) {
  const route = match(req.url);
  if (!route) { socket.destroy(); return; }
  const upstream = net.connect(Number(route.target.port || 80), route.target.hostname, () => {
    const headers = { ...req.headers, host: route.target.host };
    upstream.write(`${req.method} ${req.url} HTTP/1.1\r\n${Object.entries(headers).map(([key, value]) => `${key}: ${value}`).join('\r\n')}\r\n\r\n`);
    if (head.length) upstream.write(head);
    socket.pipe(upstream); upstream.pipe(socket);
  });
  upstream.on('error', () => socket.destroy());
  socket.on('error', () => upstream.destroy());
}
const tlsDirectory = process.env.PREFIX_TLS_DIRECTORY ?? '/tls';
for (const server of [http.createServer(forward), https.createServer({
  key: readFileSync(`${tlsDirectory}/key.pem`), cert: readFileSync(`${tlsDirectory}/cert.pem`),
}, forward)]) {
  server.on('upgrade', upgrade);
  server.listen(server instanceof https.Server ? 8443 : 8080, '0.0.0.0');
}
console.log('Isolated development prefix gateway ready.');
