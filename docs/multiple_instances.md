# Multiple Instances Under URL Prefixes

This is the Stage 10 development design, recorded on 2026-10-13. The user requested
independent installations under different paths on one host, for example
`https://projects.example.com/time-tracker-test/` and
`https://projects.example.com/time-tracker-prod/`. Product scope is recorded in
[requirements](../requirements.md#independent-instances); technical defaults below
describe the selected implementation. Core prefix configuration, URL construction,
cookies and development configuration are implemented; paired-instance and full
regression acceptance remain pending. Actual production server/proxy configuration, deployment and operational
backup/restoration are deferred to Stage 11.

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
- Validate the instance identifier as a bounded lowercase alphanumeric/hyphen
  slug usable in cookie and Compose resource names. Use `task-tracker-dev` as the
  proposed root-development default; require explicit unique identifiers for
  paired instances.
- Supply the same canonical path to the frontend build/dev server and backend
  runtime. Derive API paths, script prefix and cookie paths from it; do not maintain
  separately editable copies. Reject inconsistent build/runtime configuration in
  the startup/build workflow. Do not infer the mount from an arbitrary request
  header or the current browser pathname.
- Stage 11 hosting configuration must reject duplicate instance identifiers and
  duplicate or overlapping application mounts. Routing must match complete path
  segments, not similarly named neighbors such as `/time-tracker-test-other/`.

## Frontend Changes

Configure Vite's `base` from the validated application path for development and
builds. Imported JavaScript/CSS and HTML asset references must stay within that
prefix. Use `import.meta.env.BASE_URL` as the frontend's single path source and
introduce a shared API URL builder that appends `api/v1/` and a relative endpoint.
Keep authentication, CSRF bootstrap and `credentials: same-origin` behavior.

Replace every current root-absolute API URL:

| File | Required change |
| --- | --- |
| `frontend/vite.config.ts` | Read/validate base configuration; prefix dev proxy matching and strip only the application prefix before forwarding API requests |
| `frontend/src/api.ts` | Shared API URL builder used by health checks and JSON requests, preserving query strings and slash rules |
| `frontend/src/Content.tsx` | Private image `<img>` and download links use that builder |
| `frontend/src/Reports.tsx` | CSV fetch uses that builder while retaining download/error handling |
| `frontend/index.html` | Verify Vite processes its entry/assets correctly at root and under a prefix |

Validate relative endpoint inputs so callers cannot accidentally supply an origin
or a leading slash that discards the application path. Preserve existing task and
remark fragment links in the current mounted document. Audit future URL producers
through the shared builder. There is no client-side path router, localStorage,
sessionStorage or service worker in the current application; if introduced later,
its base path or storage/cache namespace must follow the instance configuration.

The initial proposal builds a frontend bundle for each prefix from the same
source/release. The path is a build-time value: changing it requires rebuilding
the bundle, not only changing backend environment variables. Serving one identical
bundle at arbitrary mounts through runtime configuration is a future alternative.

## Backend, Cookies and Request Handling

In `backend/config/settings.py`, validate the application configuration and derive:

| Django setting | Proposed value/behavior |
| --- | --- |
| `FORCE_SCRIPT_NAME` | External prefix without trailing slash; unset for `/` |
| `SESSION_COOKIE_NAME` | `task_tracker_<instance_id>_session` |
| `CSRF_COOKIE_NAME` | `task_tracker_<instance_id>_csrf` |
| `SESSION_COOKIE_PATH`, `CSRF_COOKIE_PATH` | Canonical application path with trailing slash |
| Cookie domain | Host-only; do not widen it to the parent domain |
| Cookie flags | Retain HttpOnly sessions and SameSite behavior; enable Secure for HTTPS hosting in Stage 11 |

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

For eventual HTTPS hosting, allow `projects.example.com` as a host and configure
the trusted origin as `https://projects.example.com`, without a path. Both mounts
use that origin. Trusted forwarded-host/scheme handling, Secure cookies, TLS and
production settings belong to Stage 11; document the integration contract now and
do not trust unfiltered client-supplied forwarding headers.

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

Canonicalize the bare mount URL to its trailing-slash UI URL with the query
preserved. Match API routes before any frontend fallback. Missing API routes and
private images must retain backend errors, never return the SPA HTML. Missing
assets must not become successful HTML responses. Private images stay behind
Django's current permission checks; do not expose the upload directory as public
static files. Mounts have separate asset roots and any cache namespace includes
the mount; authenticated/private responses retain their existing cache policy.

The Vite development proxy must match the prefixed API path and remove the mount
once, yielding the existing internal API path. For paired verification, add an
isolated development forwarding fixture that exposes both instances at one origin
and preserves their external mounts when sending requests to their Vite servers;
Vite then performs the API rewrite. It must preserve request bodies, cookies and
CSRF headers. This is test/development tooling, not selection or rollout of the
production reverse proxy. Stage 11 uses the same public routing contract with
static frontend assets and the selected production server/proxy.

## Instance Resources and Tooling

- Add a separate reusable development-instance Compose configuration and example
  environment files, or equivalent scoped overrides. Parameterize instance path,
  identifier, per-instance loopback frontend port and configuration explicitly.
  Preserve `compose.yaml` and the fixed isolated `compose.test.yaml` defaults.
- Launch instances with distinct Compose project names and env files. Keep
  project-scoped networks and database/upload volumes; avoid fixed container names
  or shared external volume names. Give each installation independent database
  credentials, Django secret, accounts and grants. Separate PostgreSQL containers
  are the initial development proposal; sharing a server with separate database
  roles/databases is a later operational choice requiring equivalent isolation.
- Current `task-tracker-web:dev` is a shared mutable image name. Paired instances
  need distinct or immutable versioned image references and separately built
  frontend artifacts so rebuilding one does not change the other's next restart.
  Avoid shared writable source mounts when testing independent application updates.
- Keep database and upload storage together under the same instance ownership.
  Stopping/recreating one instance must retain its storage and leave the other's
  service IDs, data and availability unchanged. Production backup destinations,
  restoration and update procedures remain Stage 11 work, scoped by instance.
- Document explicitly targeted bootstrap/reset/migrate commands, for example
  `docker compose --env-file <instance.env> -f <instance-compose.yaml> -p <instance-id> exec web ...`.
  These are command shapes, not runnable instructions until the planned files exist.
  Administrator accounts are bootstrapped/recovered separately for each database.
- Keep `scripts/test.sh` and `scripts/check-image-persistence.sh` limited to their
  existing disposable test project. Introduce a separate paired-instance runner
  with explicit test-owned project labels, isolated PostgreSQL/uploads and cleanup.
  Reuse the current guarded test database/user names inside separate isolated
  database containers rather than weakening the seed/test safety checks.
- Update relevant Compose health checks: a prefixed Vite frontend is probed at
  its mounted UI path; internal Django health remains unprefixed. Exclude new env
  files, secrets and verification artifacts from Git and Docker build contexts.

## Verification and Completion

Extend the browser helpers in `frontend/tests/` as well as Playwright configuration.
Changing only Playwright's `baseURL` is insufficient: existing `page.goto('/')`
and root-absolute API URLs discard its pathname. Centralize UI/API test URL
construction, while retaining backend integration tests against internal routes.

Stage 10 acceptance must cover:

1. Root-path compatibility plus two different sibling prefixes at the same origin;
   also verify nested valid prefixes and invalid/mismatched configuration failures.
2. Frontend loading/reloading, assets, health, CSRF/login/logout, task and remark
   references, image upload/download and actual CSV downloads at the correct mount.
   Inspect requested URLs and redirect locations for missing/doubled prefixes.
3. Both instances open in the same browser context, with separate accounts and
   cookie names/paths. Login, logout, password reset and deactivation in one must
   preserve the other's session and authorization state. Check actual Set-Cookie
   and deletion behavior, including Secure flags through an isolated HTTPS fixture.
4. Separate organizations/tasks/timesheets/remarks/search/report totals/uploads,
   even when account emails match. An object/image ID present only in one instance
   must be unavailable in the other; matching IDs, if any, resolve only local data
   under local permissions. Verify changes do not alter the other's counts,
   bytes or records.
5. Boundary routing, preserved query strings, bare-mount redirects, missing API
   and asset errors, and no public image path or global `/api` fallback into a
   different instance. No loosening of CSRF, host checks or current permissions.
6. Isolated migrate/bootstrap/recovery, independent restart/replacement/update,
   and scoped cleanup with original development/unrelated resources preserved.
   Run the normal PostgreSQL/build/Chromium regression lifecycle too.

Both paths share an origin: cookie paths and separate databases prevent accidental
session/data mixing but do not create a browser security boundary between the
applications. If their code requires different trust boundaries, use different
hostnames. This design supports the requested common-host layout without claiming
protection from arbitrary same-origin script execution.

Stage 10 completes only after the code/tooling and these checks are implemented
and pass. Current focused evidence is recorded in the tracker; production readiness still
requires Stage 11 deployment and full-system restoration verification.

## Technical References

- [Vite public base path](https://vite.dev/guide/build#public-base-path) and
  [development proxy matching](https://vite.dev/config/server-options#server-proxy).
- [Django script prefix](https://docs.djangoproject.com/en/5.2/ref/settings/#force-script-name),
  [session cookie settings](https://docs.djangoproject.com/en/5.2/ref/settings/#session-cookie-path)
  and [CSRF cookie settings](https://docs.djangoproject.com/en/5.2/ref/settings/#csrf-cookie-path).
- [Browser same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Same-origin_policy).
