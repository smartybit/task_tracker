# Task Tracker

Personal work and small-team task/time tracking. Product rules are in
[requirements.md](requirements.md); see [implementation progress](implementation_plan.md)
before assuming a feature is available.

## Available Features

Django/REST Framework and React now provide email/password sessions, account and
password administration, organization/project catalogs, and organization/project
grant management. Shared backend policies cover independent task/remark grants,
organization inheritance, own-timesheet access, and global others-timesheet flags.
Administrators have no automatic application-data grants. See the tracker for
current verification results. Stage 5 acceptance passed two complete test runs,
each with 82 PostgreSQL backend tests, the production build, and 16 Chromium checks.

Stage 4 adds task creation/editing, ownership transfer, flat/tree lists, project
and multiple-status filters, hierarchy/project moves, status history, and protected
status catalogs. Its acceptance verification is complete; see the tracker.

Stage 5 adds the backend timesheet engine: recording, breaks, closing markers,
independent unfinished days, overnight continuation, previews, and atomic day
corrections. The browser timesheet interface is Stage 6. Reports, remarks, images,
and search remain unimplemented. No personal account is
created automatically, and public registration is unavailable.

## Task Management

After sign-in, regular users see their task workspace; administrators select
**Tasks**. Task access follows current project/organization grants. Administrators
need explicit grants to view or modify tasks. **Refresh tasks** reloads current
access and data; **Refresh access** also refreshes account/catalog management.

Create a task in a writable project, optionally choose a parent, and review the
preview before confirming. Click a task to open its description, status history,
and permitted editing controls. Use the project/status filters and Flat/Tree view
button to find work. With status filters active, matching tasks whose parents are
excluded appear at the top level.

Status changes, moves, and deletion require a preview and confirmation. Choose a
non-final status for any final ancestors that must reopen. A move's destination
project is explicit and applies to the subtree; every owner's eligibility is
checked. Tasks with children or any recorded time cannot be deleted. A stale task
or preview refreshes the workspace and requires another review.

Administrators configure statuses under **Statuses**. Once used, a status remains
protected even after its tasks change status or are deleted. Write-only project
access permits task creation with a safe acknowledgement; browsing descriptions
and lists requires task read access. Advanced write-only changes remain available
through the revision-aware API described in the domain design.

## Timesheet API and Configuration

The backend engine is available through the authenticated, CSRF-protected API;
Stage 6 will add its browser controls. See [command contracts and examples](docs/timesheet_api.md).
Own-sheet access is implicit. Global Read/Write Others’ Timesheets flags govern
other sheets independently; administrators have no data bypass.

Set `WORKING_TIME_ZONE=Europe/Berlin` (or another IANA zone) in `.env` and recreate
the backend with `docker compose up -d web`. UTC is the default. All users share
this setting. Timestamps remain absolute instants; changing the zone reallocates
known spans to its calendar days, without fabricating ends for unfinished work.
Tests explicitly use UTC and verify Europe/Berlin outside DST transitions.
Daylight-saving acceptance remains outside scope.

## Runtime and Dependencies

- Docker Engine and Docker Compose; no host Python/Node installation is required.
- Python 3.13, Django 5.2 LTS, PostgreSQL 17, and Node 22 container images.
- Backend dependencies are pinned with hashes in `backend/requirements.txt`,
  generated from `backend/requirements.in` using pip-tools 7.6.2.
- Frontend/tooling dependencies are pinned in `frontend/package-lock.json`.
- Django's test runner handles backend checks; Playwright 1.64.0 runs Chromium
  workflows. Component-specific tooling will be selected when needed.

## Development Compose Workflow

The development startup, migrations, frontend-to-API connectivity, and Chromium
smoke checks were verified on 2026-10-08. Docker commands require authorized daemon
access; in a restricted agent session, request sandbox escalation for both startup
and cleanup before starting services. See the [infrastructure notes](docs/infrastructure_notes.md).

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
dependency changes require rebuilding. Database data uses the development volume.
Image persistence is not implemented yet; no upload endpoint exists.

Stop development containers with `docker compose down`, which retains that
database volume. Do not use `down --volumes` on the development project if you
want to retain its data. This Compose setup is not a production deployment.

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

Current limitation: account updates do not protect the last active administrator
from deactivation or demotion, and no supported recovery command exists. Keep an
active administrator available. The proposed safeguard and recovery policy remain
an [open product decision](requirements.md#open-product-questions).

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
documented loopback origins. Lists use 50-item pages (`page`, `count`, `next`, and
`results`). Grant writes replace local flags and default omitted flags to false.

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
Stage 3 adds account/CSRF, permission-matrix, migration-upgrade, rollback, and
concurrency checks, plus separate-session browser administration workflows.
Stage 4 adds deep task trees, permanent status protection, task endpoint permissions,
owner/project moves, real time-reference deletion checks, hierarchy races, and
Stage 3 schema upgrades. Stage 5 adds controlled multi-day timelines, atomic
correction and permission checks, UTC/Berlin midnight allocation, lifecycle upgrades,
and independent-connection recording/day-save races. Later stages add image and report fixtures.
Browser mutation scenarios create separate synthetic accounts so password/grant changes
do not alter another scenario’s credentials. The guarded `seed_test_data` command
restores the three baseline fixture accounts and grants when repeated.

The Django test command refuses development settings. The seed command also
requires the dedicated test database/user and never seeds development accounts.
The test runner creates and destroys its own `test_task_tracker_test` database;
browser fixtures use the separately migrated `task_tracker_test` database.

### Verification Helpers

Reusable helpers from Stage 4 are maintained in `scripts/`. They resolve the
repository from their own location and can also be invoked from another directory
using their absolute paths.

For a bounded full test run with a captured log and exit status:

```sh
sh scripts/test-runner.sh verification-1 full
```

This runs the same `scripts/test.sh` workflow with a 20-minute limit, foreground
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

Check inline local Markdown links and heading anchors in root/docs files with
`python3 scripts/check-links.py` (requires host Python 3). This is a small local
link checker, not a complete Markdown validator or external URL checker.

For Docker access troubleshooting, run `bash scripts/docker-diagnostics.sh` from
your normal terminal without sudo. It collects read-only host/socket/context and
daemon information, with a 20-second limit per command when `timeout` is available.
Unavailable or failed checks are reported and do not stop subsequent checks; its
final exit code does not establish that Docker access works. The bounded test
wrapper requires GNU `timeout` with `--foreground` support.

### Historical Component Verification

The following loopback-only temporary container arrangement was used for initial
foundation verification before the complete Compose workflow was verified. It is
retained for reproducing those component checks. Confirm authorized startup and
cleanup before using it. Commands run from the repository root; use separate
terminals for long-running database/API/frontend services. Stop them with Ctrl-C
when finished; `--rm` removes their containers and the temporary database data is not retained.
The explicit names and ports belong only to this verification arrangement. If
they are already in use, stop and choose another documented arrangement rather
than stopping an unrelated service.

Start the synthetic database:

```sh
docker run --rm --name task-tracker-foundation-db \
  -p 127.0.0.1:55439:5432 --env-file docker/test.env postgres:17-alpine
```

After PostgreSQL reports readiness, run the backend checks from current source:

```sh
docker run --rm --network host --user 1000:1000 \
  --env-file docker/test.env -e POSTGRES_HOST=127.0.0.1 -e POSTGRES_PORT=55439 \
  -v "$PWD/backend:/app" -v "$PWD/scripts:/checks:ro" \
  task-tracker-web:dev sh /checks/backend-checks.sh
```

Start the API and then the frontend in separate terminals:

```sh
docker run --rm --init --network host --name task-tracker-foundation-api \
  --env-file docker/test.env -e POSTGRES_HOST=127.0.0.1 -e POSTGRES_PORT=55439 \
  -v "$PWD/backend:/app" \
  task-tracker-web:dev python manage.py runserver --noreload 127.0.0.1:8009

docker run --rm --init --network host --name task-tracker-foundation-frontend \
  -e API_PROXY_TARGET=http://127.0.0.1:8009 \
  task-tracker-dev-frontend npm run dev -- --host 127.0.0.1 --port 5179
```

Build/type-check the frontend and run Chromium workflows:

```sh
docker run --rm --user 1000:1000 task-tracker-dev-frontend npm run build

docker run --rm --init --ipc=host --network host --user 1000:1000 \
  -e BASE_URL=http://127.0.0.1:5180 -e API_PROXY_TARGET=http://127.0.0.1:8009 \
  -v "$PWD/frontend:/work" -v "$PWD/scripts:/checks:ro" -w /work \
  mcr.microsoft.com/playwright:v1.64.0-noble \
  timeout 120 sh /checks/browser-checks.sh
```

This browser entry point builds from source, starts its own temporary Vite server
on port 5180, waits for readiness, and tests the internal Compose hostname plus
successful API/database connectivity and failed-request recovery. Its disposable
container is time-bounded; it does not need the separate port-5179 frontend.

The historical arrangement requires authorized cleanup of the exact containers
started. Verify names and ownership before stopping them; the infrastructure
notes record the original names and observed cleanup. The current Compose test
entry point performs its own scoped cleanup.

The temporary ports and host networking above are Linux verification conveniences,
not production configuration. The shared working zone is configurable as described
in [Timesheet API and Configuration](#timesheet-api-and-configuration).

## Design and Verification References

- [Architecture](architecture.md), including test isolation and search direction.
- [Domain/API design](docs/domain_design.md), including delegated initial defaults.
- [Testing charter](testing_charter.md) for risk-based scenarios and release criteria.
- [Implementation tracker](implementation_plan.md) for checks actually run,
  limitations, milestone commits, and next actions.
- [Infrastructure notes](docs/infrastructure_notes.md) for previously encountered
  setup problems, fixes, and session-specific Docker access/cleanup limitations.
