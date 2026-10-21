# Multiple Instances Under URL Prefixes

Current routing, configuration, and isolation contract for independent installations
under configurable paths on one host, including root-path development. Product scope
is in [requirements](../requirements.md#independent-instances); commands and deployed
state are in [development](development.md#independent-development-instances) and
[operations](environments.md). [Stage 10 history](archive/2026-10-21/implementation_history.md#stage-10-multiple-instance-prefix-support)
records the design evolution and acceptance. Return to the [documentation map](README.md).

## Configuration Contract

The application uses one canonical path and one stable instance identifier:

| Setting | Test example | Production example | Purpose |
| --- | --- | --- | --- |
| `APP_BASE_PATH` | `/time-tracker-test/` | `/time-tracker-prod/` | External UI, assets, API and cookie path |
| `INSTANCE_ID` | `time-tracker-test` | `time-tracker-prod` | Cookie names and instance-specific resource/config labels |

- Preserve `/` as the default application path and the existing single-instance
  development workflow. Normalize an optional missing trailing slash once; require
  an absolute path with a leading slash. Initially accept plain alphanumeric,
  underscore and hyphen path segments, including nested prefixes. Reject URL
  origins, query strings, fragments, whitespace, percent escapes, backslashes,
  duplicate separators and `.`/`..` segments rather than guessing their meaning.
- Validate the instance identifier as a lowercase alphanumeric/hyphen slug starting
  with an alphanumeric, at most 63 characters. Use `task-tracker-dev` as the
  root-development default; require explicit unique identifiers for
  paired instances.
- Supply the same canonical path to the frontend build/dev server and backend
  runtime. Derive API paths, script prefix and cookie paths from it; do not maintain
  separately editable copies. Reject inconsistent build/runtime configuration in
  the startup/build workflow. Do not infer the mount from an arbitrary request
  header or the current browser pathname.
- Deployment configuration rejects duplicate instance identifiers and
  duplicate or overlapping application mounts. Routing must match complete path
  segments, not similarly named neighbors such as `/time-tracker-test-other/`.

## Frontend Integration

Configure Vite's `base` from the validated application path for development and
builds. Imported JavaScript/CSS and HTML asset references must stay within that
prefix. Use `import.meta.env.BASE_URL` as the frontend's single path source and
use the shared API URL builder that appends `api/v1/` and a relative endpoint.
Keep authentication, CSRF bootstrap and `credentials: same-origin` behavior.

All application API URL producers use the configured mount:

| File | Implementation |
| --- | --- |
| `frontend/vite.config.ts` | Read/validate base configuration; prefix dev proxy matching and strip only the application prefix before forwarding API requests |
| `frontend/src/api.ts` | Shared API URL builder used by health checks and JSON requests, preserving query strings and slash rules |
| `frontend/src/Content.tsx` | Private image `<img>` and download links use that builder |
| `frontend/src/Reports.tsx` | CSV fetch uses that builder while retaining download/error handling |
| `frontend/index.html` | Verify Vite processes its entry/assets correctly at root and under a prefix |

Validate relative endpoint inputs so callers cannot accidentally supply an origin
or a leading slash that discards the application path. Preserve existing task and
remark fragment links in the current mounted document. Audit future URL producers
through the shared builder. There is no client-side path router or service worker.
The remark-order preference uses sessionStorage keyed by user UUID; storage is
shared by origin, not separated
by URL path. Future storage/cache use must account for instance namespaces and the
same-origin trust limitation below.

Each prefix has a frontend bundle built from the same source/release.
The path is a build-time value: changing it requires rebuilding
the bundle, not only changing backend environment variables. Serving one identical
bundle at arbitrary mounts through runtime configuration is a future alternative.

## Backend, Cookies and Request Handling

In `backend/config/settings.py`, validate the application configuration and derive:

| Django setting | Implemented value/behavior |
| --- | --- |
| `FORCE_SCRIPT_NAME` | External prefix without trailing slash; unset for `/` |
| `SESSION_COOKIE_NAME` | `task_tracker_<instance_id>_session` |
| `CSRF_COOKIE_NAME` | `task_tracker_<instance_id>_csrf` |
| `SESSION_COOKIE_PATH`, `CSRF_COOKIE_PATH` | Canonical application path with trailing slash |
| Cookie domain | Host-only; do not widen it to the parent domain |
| Cookie flags | Retain HttpOnly sessions and SameSite behavior; enable Secure for HTTPS hosting |

`DJANGO_COOKIE_SECURE=true` enables Secure session and CSRF cookies; the default
is false for local HTTP development. The paired HTTPS fixture uses true without
changing production hosting. Startup rejects invalid Boolean values.

Frontend images contain `.instance-build.json`; Vite startup rejects a different
runtime path/ID, then checks matching `X-Task-Tracker-Base-Path` and
`X-Task-Tracker-Instance` headers on the backend health endpoint. This leaves the
existing public health JSON contract unchanged. Builds also emit `dist/instance.json`
for deployment verification. Change a mount by rebuilding/recreating both
application services, not by changing only the backend environment.

Distinct names prevent accidental collisions with sibling instances and other
applications on the host; paths scope normal browser delivery. Keep CSRF tokens
obtained through the existing endpoint, rather than adding cookie parsing.
Login rotation, logout deletion, password reset and deactivation must use the same
configured names/paths. Changing a previously deployed instance's identifier/path
requires a new sign-in; any old cookie cleanup must target only its old names/path.

Keep internal `backend/config/urls.py` routes rooted at `api/v1/`. The forwarding
layer removes the external application prefix exactly once; Django's script prefix
restores it when generating URLs or redirects. Verify the WSGI/script-prefix and
`PATH_INFO` contract, including management-command URL generation and trailing
slash redirects with query strings. Internal backend health checks continue to
request `/api/v1/health/`; they do not pass through the public mount.

For HTTPS hosting, configure the actual allowed host and trusted origin without
a path (for example `https://projects.example.com`). Mounts on that host share the
origin. The [operations guide](environments.md) describes the selected Nginx/Gunicorn
integration; never trust unfiltered client-supplied forwarding headers.

No model/schema migration or per-row tenant field is needed: each instance is a
separate installation. UUIDs, task/remark reference tokens, image metadata, time
accounting, permissions and stored content remain unchanged. Cross-instance
reference resolution and shared sign-in are not introduced.

## External Routing Contract

| External request | Expected handling |
| --- | --- |
| `/time-tracker-test/` and its frontend assets | Test frontend bundle |
| `/time-tracker-test/api/v1/...` | Test backend `/api/v1/...` |
| `/time-tracker-prod/` and its frontend assets | Production frontend bundle |
| `/time-tracker-prod/api/v1/...` | Production backend `/api/v1/...` |

Vite uses `appType: mpa`: this application navigates with fragments, so no SPA
fallback is needed. Missing assets and unknown frontend paths return 404;
[the original failure](archive/2026-10-21/verification_history.md#stage-10-verification-findings-2026-10-13)
explains this choice.

Canonicalize the bare mount URL to its trailing-slash UI URL with the query
preserved. Match API routes before any frontend fallback. Missing API routes and
private images must retain backend errors, never return the SPA HTML. Missing
assets must not become successful HTML responses. Private images stay behind
Django's current permission checks; do not expose the upload directory as public
static files. Mounts have separate asset roots and any cache namespace includes
the mount; authenticated/private responses retain their existing cache policy.

The Vite development proxy must match the prefixed API path and remove the mount
once, yielding the existing internal API path. Paired verification uses an
isolated development forwarding fixture that exposes both instances at one origin
and preserves their external mounts when sending requests to their Vite servers;
Vite then performs the API rewrite. It must preserve request bodies, cookies and
CSRF headers. This is test/development tooling, not selection or rollout of the
production reverse proxy. Built deployments use the same public routing contract with
static frontend assets, Nginx, and Gunicorn.

## Instance Resources and Tooling

- `compose.instances.dev.yaml` and `instances/*.env.example` provide the reusable
  development-instance setup. Instance path, identifier, per-instance loopback
  frontend port and configuration are explicit. `compose.yaml` and the fixed
  isolated `compose.test.yaml` retain their root-path defaults.
- Launch instances with distinct Compose project names and env files. Keep
  project-scoped networks and database/upload volumes; avoid fixed container names
  or shared external volume names. Give each installation independent database
  credentials, Django secret, accounts and grants. Development instances use
  separate PostgreSQL containers; sharing a server with separate database
  roles/databases is a later operational choice requiring equivalent isolation.
- The root development workflow retains its shared `task-tracker-web:dev` image
  name. Independent instances instead use distinct image namespaces and optional
  `INSTANCE_VERSION` tags, with separately built frontend artifacts. Rebuilding
  one does not change the other's next restart. Their Compose setup copies source
  into images and has no shared writable source mounts.
- Keep database and upload storage together under the same instance ownership.
  Stopping/recreating one instance must retain its storage and leave the other's
  service IDs, data and availability unchanged. Updates follow the [operations guide](environments.md); production backup
  destinations and restoration remain outstanding, scoped by instance.
- Use explicitly targeted bootstrap/reset/migrate commands, for example
  `docker compose --env-file <instance.env> -f <instance-compose.yaml> -p <instance-id> exec web ...`.
  Runnable examples are in [development commands](development.md#independent-development-instances).
  Administrator accounts are bootstrapped/recovered separately for each database.
- Keep `scripts/test.sh` and `scripts/check-image-persistence.sh` limited to their
  existing disposable test project. `scripts/test-prefixes.sh` owns the separate
  `task-tracker-prefix-tests` project with isolated PostgreSQL/uploads and scoped
  cleanup. It reuses the guarded test database/user names inside separate database
  containers; seed/test safety checks remain in effect. The reusable development
  check owns only `task-tracker-instance-check-a` and `-b`.
- Prefixed Vite frontend health checks probe the mounted UI path; internal Django
  health remains unprefixed. Instance env files, secrets and verification artifacts
  are excluded from Git and Docker build contexts.

## Verification and Trust Boundaries

[The testing charter](../testing_charter.md#multiple-instance-acceptance) owns
acceptance scenarios; [development commands](development.md#independent-development-instances)
own sibling/nested/development verification entry points. Browser helpers centralize
mounted UI/API URLs because `page.goto('/')` and root-absolute API calls discard a
base URL's path. Backend integration checks retain internal routes.

Paths on one origin do not create separate browser trust boundaries. Scoped cookie
names/paths and separate databases prevent accidental session/data mixing; they
do not protect against arbitrary same-origin script execution. Use distinct
hostnames if different trust boundaries are needed. Cross-instance references and
shared sign-in are not supported.

[Stage 10 evidence](archive/2026-10-21/implementation_history.md#stage-10-multiple-instance-prefix-support)
records sibling/nested, reusable-development, and root regression acceptance.
Production readiness also requires the outstanding operational and full-system
restoration checks in [the current tracker](../implementation_plan.md).

## Technical References

- [Vite public base path](https://vite.dev/guide/build#public-base-path) and
  [development proxy matching](https://vite.dev/config/server-options#server-proxy).
- [Django script prefix](https://docs.djangoproject.com/en/5.2/ref/settings/#force-script-name),
  [session cookie settings](https://docs.djangoproject.com/en/5.2/ref/settings/#session-cookie-path)
  and [CSRF cookie settings](https://docs.djangoproject.com/en/5.2/ref/settings/#csrf-cookie-path).
- [Browser same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy).
