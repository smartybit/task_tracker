import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import { instanceConfig } from '../instance-config.ts';

const { basePath, instanceId } = instanceConfig(process.env);
const mount = basePath.slice(0, -1);
const schemeVariable = '${PUBLIC_SCHEME}';
const hostVariable = '${PUBLIC_HOST}';
mkdirSync(`deployment-root${basePath}`, { recursive: true });
cpSync('dist', `deployment-root${basePath}`, { recursive: true });
writeFileSync('instance.env', `BUILT_BASE_PATH='${basePath}'\nBUILT_INSTANCE_ID='${instanceId}'\n`);
writeFileSync('nginx.conf.template', `
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  access_log /dev/stdout;
  client_body_temp_path /tmp/client_temp;
  proxy_temp_path /tmp/proxy_temp;
  fastcgi_temp_path /tmp/fastcgi_temp;
  uwsgi_temp_path /tmp/uwsgi_temp;
  scgi_temp_path /tmp/scgi_temp;
  map $uri $asset_cache {
    default "no-store";
    "~^${basePath}assets/" "public, max-age=31536000, immutable";
  }
  server { listen 8080 default_server; server_name _; return 400; }
  server {
    listen 8080;
    server_name ${hostVariable};
    root /usr/share/nginx/html;
    absolute_redirect off;
    client_max_body_size 16m;
    add_header Cache-Control $asset_cache always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy same-origin always;
    add_header Cross-Origin-Opener-Policy same-origin always;
    ${mount ? `location = ${mount} { return 308 ${basePath}$is_args$args; }` : ''}
    location = ${basePath}api { return 308 ${basePath}api/$is_args$args; }
    location ^~ ${basePath}api/ {
      proxy_pass http://web:8000/api/;
      proxy_http_version 1.1;
      proxy_set_header Host $http_host;
      proxy_set_header Connection "";
      proxy_set_header X-Forwarded-Proto ${schemeVariable};
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_set_header X-Forwarded-Host "";
      proxy_set_header SCRIPT_NAME "";
      proxy_set_header PATH_INFO "";
      proxy_read_timeout 65s;
      proxy_redirect off;
    }
    location = ${basePath} { try_files ${basePath}index.html =404; }
    location = ${basePath}index.html { try_files $uri =404; }
    location = ${basePath}instance.json { try_files $uri =404; }
    location ^~ ${basePath}assets/ { try_files $uri =404; }
    location / { return 404; }
  }
}
`);
