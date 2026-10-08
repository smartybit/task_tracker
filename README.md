# Task Tracker

Personal work and small-team task/time tracking. Product rules are in
[requirements.md](requirements.md); see [implementation progress](implementation_plan.md)
before assuming a feature is available.

## Current Foundation

The repository now contains Django/REST Framework, an email-based user model and
migrations, a PostgreSQL-backed health endpoint, and a React/TypeScript/Vite shell.
Task workflows, login screens, grants, time recording, reports, and content/search
are **not implemented yet**. The user model is preparation for Stage 3, not a
completed authentication or permissions feature. No personal account is created
automatically.

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
checks migrations, runs backend tests, seeds three synthetic accounts, builds the
frontend, and runs browser checks. Cleanup removes that test project and temporary
data even on failure. Run sequentially, not concurrently with another invocation.
Failure screenshots/traces remain in ignored `frontend/test-results/`.
Later stages add permission, hierarchy, timesheet, image, and report fixtures.

The Django test command refuses development settings. The seed command also
requires the dedicated test database/user and never seeds development accounts.
The test runner creates and destroys its own `test_task_tracker_test` database;
browser fixtures use the separately migrated `task_tracker_test` database.

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
not production configuration. The configured working zone is UTC only as a
temporary development/test default; the deployment zone still needs selection.

## Design and Verification References

- [Architecture](architecture.md), including test isolation and search direction.
- [Domain/API design](docs/domain_design.md), including delegated initial defaults.
- [Testing charter](testing_charter.md) for risk-based scenarios and release criteria.
- [Implementation tracker](implementation_plan.md) for checks actually run,
  limitations, milestone commits, and next actions.
- [Infrastructure notes](docs/infrastructure_notes.md) for previously encountered
  setup problems, fixes, and session-specific Docker access/cleanup limitations.
