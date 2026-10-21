# Development and Verification Commands

Commands run from the repository root unless stated otherwise. Read
[troubleshooting](infrastructure_notes.md) before starting verification services.
For persistent evaluation/agent deployments, use [operations](environments.md).
Return to the [documentation index](README.md).

## Runtime and Dependencies

- Docker Engine and Docker Compose run the application and core test suite without
  host Python/Node. Host Python 3 is needed for documentation/environment helpers;
  prefix verification has additional prerequisites listed below.
- Python 3.13, Django 5.2 LTS, PostgreSQL 17, and Node 22 container images.
- Backend dependencies are pinned with hashes in `backend/requirements.txt`,
  generated from `backend/requirements.in` using pip-tools 7.6.2.
- Frontend/tooling dependencies are pinned in `frontend/package-lock.json`.
- Django's test runner handles backend checks; Playwright 1.64.0 runs Chromium
  workflows. Component-specific tooling will be selected when needed.

## Development Compose Workflow

Docker commands require authorized daemon access; in a restricted agent session,
use the required sandbox escalation for both startup
and cleanup before starting services. See the [infrastructure notes](infrastructure_notes.md).

Optionally copy `.env.example` to `.env` and select local development values.
The built-in defaults are development-only, not production credentials.

```sh
docker compose config --quiet
docker compose build web frontend
docker compose up -d --wait
docker compose ps
```

The browser address is `http://127.0.0.1:5173`. On the VDS, use an SSH
tunnel to reach its loopback address from your computer. PostgreSQL and Django
are not published on host ports in this configuration. Vite proxies `/api` to
Django. Backend sources and frontend sources/config are mounted for development;
dependency changes require rebuilding. Database data uses `development-db`;
private image files use `development-uploads`. Source create/edit endpoints accept
images as documented in [the content API](content_api.md).

Stop development containers with `docker compose down`, which retains that
database and image volumes. Do not use `down --volumes` on the development project if you
want to retain its data. This Compose setup is not a production deployment.

## Independent Development Instances

`compose.instances.dev.yaml` provides independent development installations
with different URL prefixes. It uses development servers. Persistent built
deployments use the [environment operations guide](environments.md).

Copy `instances/test.env.example` to `instances/test.env` and
`instances/prod.env.example` to `instances/prod.env`. Set different database
passwords and Django secrets in the ignored copies. The second example is another
development instance using the intended production prefix, not production settings.

Start each instance from the repository root:

```sh
docker compose --env-file instances/test.env -f compose.instances.dev.yaml -p time-tracker-test up -d --build --wait
docker compose --env-file instances/prod.env -f compose.instances.dev.yaml -p time-tracker-prod up -d --build --wait
```

The examples use `http://127.0.0.1:5174/time-tracker-test/` and
`http://127.0.0.1:5175/time-tracker-prod/`. Each has separate database/uploads,
images, configuration, accounts and grants. Code is copied into independently named
images; rebuild/recreate an instance to apply source changes. `INSTANCE_VERSION`
can select a distinct release tag within its image namespace. Changing its
`APP_BASE_PATH` or `INSTANCE_ID` also requires rebuilding the frontend and signing
in again; startup rejects mismatched image/runtime/backend configuration.

Bootstrap and recover accounts against the intended instance explicitly:

```sh
docker compose --env-file instances/test.env -f compose.instances.dev.yaml -p time-tracker-test exec web python manage.py bootstrap_admin --email you@example.com
docker compose --env-file instances/prod.env -f compose.instances.dev.yaml -p time-tracker-prod exec web python manage.py reset_password --email you@example.com --reactivate --grant-admin
```

Stop an instance with the same env/file/project arguments followed by `down`;
its database and upload volumes are retained. The original `docker compose`
root-path workflow remains available. The new cookie names require a fresh sign-in
when upgrading an existing development installation.

The [multiple-instance design](multiple_instances.md) records the shared-host
routing contract and common-origin limitation. The disposable verification commands
are `sh scripts/test-prefixes.sh LABEL` (sibling mounts),
`sh scripts/test-prefixes.sh LABEL nested` (nested second mount), and
`sh scripts/check-instances-dev.sh LABEL` (the reusable development configuration).
Use a fresh label per run; logs/status are retained in `.artifacts/verification/`.
These helpers require host Python 3, OpenSSL, `flock`, GNU `timeout` and Docker
lifecycle access, and remove only their reserved synthetic projects/volumes.
Run them serially with other browser suites. The paired fixture exposes HTTPS
only inside its isolated Docker network and uses a temporary self-signed certificate;
it does not publish or configure the production host.

## First Administrator and Account Management

After development startup has applied migrations, create the first administrator
from an interactive terminal:

```sh
docker compose exec web python manage.py bootstrap_admin --email you@example.com
```

The command prompts twice for a password, validates it, and atomically creates the
account and its timesheet record. It refuses once any application administrator
exists. It never creates default credentials. The generic Django `createsuperuser`
and `changepassword` commands direct operators to the supported application paths.

Sign in at the frontend address. Administrators can use Accounts to create/edit
accounts, deactivate/reactivate them, set global timesheet flags, and reset a
password. Share a reset password directly; no email is sent. Password resets and
deactivation revoke existing sessions; reactivation requires a new sign-in.
Catalogs manages organizations/projects; an organization with projects cannot be
deleted, and existing projects cannot change organizations through a field edit.
Statuses manages task-status catalogs; projects referenced by tasks cannot be deleted.

Administrators cannot deactivate themselves or remove their own administrator
privileges. Those two controls are disabled when editing your own account; the
backend also rejects direct requests without changing any account fields or
sessions. Other fields remain editable. Administrators may change another
administrator's active status or privileges.

From an interactive server terminal, reset any existing account's password:

```sh
docker compose exec web python manage.py reset_password --email person@example.com
```

The command prompts twice for a hidden password and validates it. It preserves
active/admin statuses unless explicitly requested and never creates an account.
Old passwords and sessions stop working; replacements have no expiry or mandatory
change. To recover an existing account when no active administrator can sign in:

```sh
docker compose exec web python manage.py reset_password --email person@example.com --reactivate --grant-admin
```

Use either recovery option independently if appropriate. Password and requested
status changes commit together. Recovery grants no project access or global
timesheet flags. First-account setup still uses `bootstrap_admin`; `reset_password`
works even when an existing inactive administrator prevents bootstrap. See the
[agreed policy](../requirements.md#users-and-authentication) and
[implementation details](../architecture.md#accounts-and-authentication).

The server administrator is responsible for backups of the PostgreSQL cluster,
attachment directory, and necessary configuration. Written instructions for
restoring the entire system on another machine and verification of that procedure
remain Stage 11 work; tooling, schedule, retention, and destination await deployment
planning. See the [backup policy](../architecture.md#agreed-backup-and-restoration-policy).

Grants manages local task/remark read/write flags per organization or project and
shows effective project flags. Organization and project flags combine with OR;
clearing a project flag cannot deny an inherited grant. UI write selection also
enables read, while the API supports write without read. Administrator status
permits configuration, without bypassing these data policies. Regular accounts
see catalog choices for projects where they have task read or write access.
Refresh access reloads current grants; the backend checks permissions on every
request even when a management screen was opened before access was revoked.

Browser requests use session cookies and CSRF headers through Vite's `/api` proxy.
The CSRF endpoint is `/api/v1/auth/csrf/`; login returns a refreshed token. Unsafe
requests, including login/logout, require a valid token and allowed origin. Test
configuration explicitly trusts `http://frontend:5173`; development trusts the
documented loopback origins. Catalog and task lists use 50-item pages (`page`,
`count`, `next`, and `results`); reports return the complete selected dataset as
described in the reporting API. Grant writes replace local flags and default
omitted flags to false.

## Isolated Test Setup

`compose.test.yaml` uses a separate fixed project, credentials, ephemeral database
storage, and temporary uploads, without publishing host ports. It does not inherit
development database settings from `.env`. The browser suite uses a real frontend,
API, and PostgreSQL; the failure-recovery check deliberately mocks one failed
request, then retries against the real backend.

Single entry point (run from the repository root with Docker lifecycle access):

```sh
sh scripts/test.sh
```

This recreates **only** the `task-tracker-tests` project, waits for service health,
checks migrations, runs backend tests, seeds three synthetic accounts, two
organizations, three projects, and representative grants, builds the
frontend, and runs browser checks. Cleanup removes that test project and temporary
data through its cleanup trap. Run sequentially, not concurrently with another
invocation. Inspect cleanup after interruptions: a one-off browser container may
outlive its command client. See the infrastructure notes for the verified
noninteractive terminal fallback.
Failure screenshots/traces remain in ignored `frontend/test-results/`.
The [testing charter](../testing_charter.md) defines scenario priorities;
[current status](../implementation_plan.md) links to recorded verification evidence.
Browser mutation scenarios create separate synthetic accounts so password/grant changes
do not alter another scenario’s credentials. The guarded `seed_test_data` command
restores the three baseline fixture accounts and grants when repeated.

The Django test command refuses development settings. The seed command also
requires the dedicated test database/user and never seeds development accounts.
The test runner creates and destroys its own `test_task_tracker_test` database;
browser fixtures use the separately migrated `task_tracker_test` database.

### Verification Helpers

Reusable helpers are maintained in `scripts/`. They resolve the
repository from their own location and can also be invoked from another directory
using their absolute paths.

For a bounded full test run with a captured log and exit status:

```sh
sh scripts/test-runner.sh verification-1 full
```

This runs the same `scripts/test.sh` workflow with a 45-minute limit, foreground
supervision, and closed standard input. Results default to ignored
`.artifacts/verification/verification-1.log` and `.status`; the wrapper returns
the test command's exit status. Use a new label for each run. An optional third
argument selects an output directory, relative to the caller's working directory.
Keep the wrapper in the foreground and run sequentially. A missing status file
means completion was not recorded; inspect test-owned resources after interruptions
as described in the infrastructure notes.

For the focused account-revocation browser scenario on an already running,
prepared **test** stack, use `sh scripts/test-runner.sh account-1 account`.
This mode has a three-minute limit and leaves the existing stack running.

Check inline local Markdown links and heading anchors in root/docs files, including the archive, with
`python3 scripts/check-links.py` (requires host Python 3). This is a small local
link checker, not a complete Markdown validator or external URL checker.

For Docker access troubleshooting, run `bash scripts/docker-diagnostics.sh` from
your normal terminal without sudo. It collects read-only host/socket/context and
daemon information, with a 20-second limit per command when `timeout` is available.
Unavailable or failed checks are reported and do not stop subsequent checks; its
final exit code does not establish that Docker access works. The bounded test
wrapper requires GNU `timeout` with `--foreground` support.


## Image Persistence Check

`sh scripts/check-image-persistence.sh` verifies synthetic image bytes, metadata
and private access across test-web container replacement, then removes its
isolated stack and temporary volume. Run it separately from other test commands.
