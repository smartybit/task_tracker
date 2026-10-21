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
current verification results. Stage 7 acceptance passed two complete test runs,
each with 97 PostgreSQL backend tests, the production build, and 30 Chromium scenarios.

Stage 4 adds task creation/editing, ownership transfer, flat/tree lists, project
and multiple-status filters, hierarchy/project moves, status history, and protected
status catalogs. Its acceptance verification is complete; see the tracker.

Stage 5 adds the backend timesheet engine: recording, breaks, closing markers,
independent unfinished days, overnight continuation, previews, and atomic day
corrections. Stage 6 adds browser timesheets and the Edit day dialog; acceptance
verification is complete. Stage 7 adds reporting APIs, report screens, and CSV
downloads; full acceptance verification is complete. Stage 8 remarks, shared stars,
stable references, private images and multilingual search are complete. Final
acceptance passed 126 PostgreSQL tests, the production build, 41 Chromium scenarios
and synthetic image-container replacement. Stage 9 contains development completion
and application verification, including administrator safeguards/recovery. Stage 10
covers multiple-instance URL-prefix support and is complete: sibling/nested mounts
and reusable development instances passed acceptance. Full root regression passed
142 PostgreSQL tests, frontend configuration checks, the production build and all
43 Chromium scenarios. Stage 11 contains production server/proxy configuration,
deployment, backups and restoration.
Stage 9 is complete: administrator safeguards/recovery and development acceptance
passed 139 PostgreSQL tests, the production build and all 43 Chromium scenarios.
The [UI adjustment subplan](docs/ui_adjustment_plan.md) is implemented and technically
verified: 146 PostgreSQL tests, 47 Chromium scenarios, build/configuration checks,
and three built prefixed deployments passed. User UI review is next; remaining
Stage 11 work is deferred until UI acceptance. After separate user authorization,
evaluation now runs UI release `ui-1ca13e4-20261021` with verified public HTTPS;
existing records/uploads and its Tbilisi working zone are preserved. Agent access
remains private.
Production activation and backup/restoration acceptance remain pending.
Detailed evidence is recorded in the implementation tracker.
No personal account is created automatically, and public registration is unavailable.

## Task Management

After sign-in, everyone opens **Tasks**. Administrators find account/catalog/grant
and status management under **Administration**, including **System status** for
connection checks. Colleagues can review project grants under **My access**. Task
access follows current project/organization grants. Administrators
need explicit grants to view or modify tasks. **Refresh tasks** reloads current
access and data; **Refresh access** also refreshes account/catalog management.

Use **New task** to create work in a writable project and review its preview
before confirming. Each task has an **Actions** menu for **Add subtask**, editing,
status changes, recording, ownership, moves and deletion. Add subtask preselects
the parent and project. Clicking a title opens a separate details/remarks window;
**History** opens status history. **Close details** dismisses the window; finish a
task through **Change status**. Each command has its own dialog. Use the
project/status filters and Flat/Tree view
button to find work. With status filters active, matching tasks whose parents are
excluded appear at the top level.

Status changes, moves, and deletion require a preview and confirmation. Choose a
non-final status for any final ancestors that must reopen. A move's destination
project is explicit and applies to the subtree; every owner's eligibility is
checked. Tasks with children or any recorded time cannot be deleted. A stale task
or preview retains input and requires explicit **Refresh tasks** and another
review. Changed drafts require confirmation before dismissal; acknowledged saves
with failed reloads are reported as saved and must not be submitted again.

Administrators configure statuses under **Administration → Statuses**. Once used, a status remains
protected even after its tasks change status or are deleted. Write-only project
access permits task creation with a safe acknowledgement; browsing descriptions
and lists requires task read access. Advanced write-only changes remain available
through the revision-aware API described in the domain design.

## Task Remarks

Open a task to read its remarks and shared stars. The composer sits above the
stream. **Remark order** switches between newest first (default) and oldest first;
the choice is remembered per user for the browser session. Post text above
the conversation; authorized users can edit, delete, or star any remark. Stars
link to the original remark and are visible to other readers. Edits retain the
original author and creation time and show an edit timestamp.

Remark reading requires task read plus remark read. Posting and other changes
require task read plus remark write; task write is unnecessary. Write-only remark
access offers a composer without displaying the conversation. Task deletion also
requires remark write when remarks exist and previews the number removed.

Failed writes retain text. Stale or denied writes require **Reload remarks** and
review; changed edits require confirmation before disposal. A confirmed save with
a failed reload is reported as saved. Drafts belong to the open task window;
closing or switching tasks asks before discarding changed drafts. See [the remarks API](docs/remarks_api.md).

Descriptions and remarks offer **Insert reference** for readable tasks or remarks.
Links use stable IDs, display current labels, and open the target task or focus
the original remark. **Refresh references** checks labels and access again.
Restricted and deleted targets both display **Unavailable reference**. See
[the content API](docs/content_api.md).

Select **Add images** or paste screenshots into a description or remark. Images
upload with the text when saved; failed writes retain pending images. Accepted
formats are static PNG/JPEG/WebP, at most 2 MiB each and five new images per save.
Remove image tokens to delete them on save. Downloads require current access to
their description or remark. Development uploads persist in a separate named
volume; include it with the database in backups.

In Tasks, **Search tasks and remarks** searches readable titles, descriptions and
remarks using English/Russian word forms, including mixed text. All query words
must match one task or remark. Results show excerpts and open the task or original
remark. Search again to refresh access/content; **Next search page** loads further
matches. Search failures retain the query and clear previous excerpts.

`sh scripts/check-image-persistence.sh` verifies synthetic image bytes, metadata
and private access across test-web container replacement using a temporary test
volume, then removes that isolated stack and volume. Run it separately from other
test commands; it never uses development data.

## Timesheet Workspace

After sign-in, the timesheet sits to the right of Tasks on wide screens and below
Tasks on narrow screens. Choose **Day** and, when permitted, **Timesheet person**.
Table start/end cells show **HH:MM**. All displayed and entered times use the
shared working zone shown in the panel; precise values remain available in editors
and are preserved when unchanged.
Daily totals cover the whole timesheet across projects; breaks and unknown ends
count zero. Task labels remain visible after task access is lost; opening their
descriptions still requires task read permission.

Drag a task into today's sheet to record at the current time, or use a task's
**Actions → Record time** command or **Record work…** to open the searchable
picker. The picker includes final tasks
and filters by project and selected statuses. Current recording against a final
task requires reopening it separately in Tasks. For historical additions, enter
**Selected-day time** explicitly; dropping a task on a past day selects it and
asks for that time. Use **Break** and **End of Working Day** to close intervals.
The recording window includes a target-session selector; days with multiple
sessions require an explicit selection. Adding after a closing
marker previews its conversion to a break before confirmation.

Starting a new day leaves older tails unfinished. Their dates appear as links;
correcting them preserves today's recording. Open **Overnight work…** and choose
**Continue previous session** for explicit overnight work; this closes the
earlier interval at the supplied
time. **Close overnight recording** closes an earlier active session today.

Click a start/end boundary to preview changing it and its neighbor together.
**Delete last record** previews deletion and extension of the predecessor; middle
corrections use **Edit day…**. The modal copies the selected day, supports arbitrary
row/session additions and removals, and highlights gaps, overlaps and incomplete
values. Time edits sort rows on blur, retaining input keys and keyboard focus.
Enter closing markers explicitly; internal gaps need Break rows. Connected
midnight edges are fixed and neighboring days are edited separately.

**Save changes** validates and writes the whole draft atomically. **Cancel** and
Escape discard locally, with confirmation for changed drafts. Failed saves keep
the draft. Stale or denied saves require explicit **Reload day and discard draft**
and review before another save; no automatic replay occurs. Reloading or leaving
the page warns about unsaved changes. Normal stale commands require **Reload
timesheet** and another review. Use **Refresh access** when access changes.
If changes were saved but reloading fails, the interface says they were saved
and requires reload/review before another attempt. Read-only colleague sheets omit editing controls;
write-without-read access remains supported through the API, because the browser
day editor needs readable rows.

## Timesheet API and Configuration

The engine and browser controls use the authenticated, CSRF-protected API.
See [command contracts and examples](docs/timesheet_api.md).
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
dependency changes require rebuilding. Database data uses `development-db`;
private image files use `development-uploads`. Source create/edit endpoints accept
images as documented in [the content API](docs/content_api.md).

Stop development containers with `docker compose down`, which retains that
database and image volumes. Do not use `down --volumes` on the development project if you
want to retain its data. This Compose setup is not a production deployment.

## Independent Development Instances

Stage 10 adds `compose.instances.dev.yaml` for independent development installations
with different URL prefixes. This configuration uses development servers; production
hosting remains Stage 11 work. Sibling-prefix, nested-prefix and reusable
development-instance lifecycles passed, including scoped cleanup and independent
sessions, data, images and replacement. Root-path regression also passed.

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

The [multiple-instance design](docs/multiple_instances.md) records the shared-host
routing contract and common-origin limitation. The disposable verification commands
are `sh scripts/test-prefixes.sh LABEL` (sibling mounts),
`sh scripts/test-prefixes.sh LABEL nested` (nested second mount), and
`sh scripts/check-instances-dev.sh LABEL` (the reusable development configuration).
Use a fresh label per run; logs/status are retained in `.artifacts/verification/`.
These helpers require host Python 3, OpenSSL, `flock`, GNU `timeout` and Docker
lifecycle access, and remove only their reserved synthetic projects/volumes.
Run them serially with other browser suites. The paired fixture exposes HTTPS
only inside its isolated Docker network and uses a temporary self-signed certificate;
it does not publish or configure the proposed production host.

## Persistent Evaluation and Agent Environments

Persistent evaluation and agent deployments use the separate
[environment commands and access guide](docs/environments.md), with Gunicorn
and built frontend assets. More agent environments can be added by name. Those
environments have independent releases, secrets and storage; existing development
and disposable test commands retain their original scope. Evaluation account
bootstrap asks for an email and prints a generated password on the terminal.

On this server, evaluation is available at
`https://evaluation.example.com/time-tracker-eval/`, with working time zone `Asia/Tbilisi`
(UTC+4). Its frontend stays on loopback port 8181 behind host Nginx; see the
[installation and rollback instructions](docs/environments.md#activate-evaluation-https-administrator-handoff).
Agent remains at
`http://127.0.0.1:8182/time-tracker-agent/`, accessible through an SSH tunnel.
From the server repository, run `python3 scripts/environments.py bootstrap evaluation`
to create your administrator. No account was created automatically. Production
has not been initialized or activated.

Use `python3 scripts/environments.py verify evaluation` (or `verify agent`) after
startup or updates to check the running deployment without modifying application
data. The [operations guide](docs/environments.md#verify-a-running-deployment)
describes its checks and limits.

## Reports and CSV Export

Select **Reports** to view project summaries, people by day, or task hierarchies.
Dates default to the current month through today in the server's configured
working time zone. Filter by inclusive dates, person, project, or a task and its
descendants. Hierarchy rows show direct, descendant, and combined hours; the
overall total counts source work once. Hours are rounded to two decimal places
after summing exact durations, and unfinished entries contribute zero.

Reports require task read access to each project. Without Read Others' Timesheets,
they include only your own work. Whole-timesheet daily totals can include work
outside readable projects, so they can differ from report totals. Administrators
have no report access bypass. Historical corrections and current task projects
and parent relationships determine later report results; use **Refresh reports**
after edits in another session.

**Download CSV** exports all authorized individual task records for the selected
dates. Person, project, and task report filters do not narrow the download. Columns
are Person, Project, Task, Date, Start Time, End Time, and Duration in decimal hours.
Breaks and closing markers are omitted; unfinished records have a blank end and
zero duration. Closed work crossing local midnight produces daily fragments.
Empty exports contain only column headings. See the
[reporting API](docs/reporting_api.md) for routes, filter validation, and consistency.

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
[agreed policy](requirements.md#users-and-authentication) and
[implementation details](architecture.md#agreed-administrator-lifecycle-follow-up).

The server administrator is responsible for backups of the PostgreSQL cluster,
attachment directory, and necessary configuration. Written instructions for
restoring the entire system on another machine and verification of that procedure
remain Stage 11 work; tooling, schedule, retention, and destination await deployment
planning. See the [backup policy](architecture.md#agreed-backup-and-restoration-policy).

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
Stage 3 adds account/CSRF, permission-matrix, migration-upgrade, rollback, and
concurrency checks, plus separate-session browser administration workflows.
Stage 4 adds deep task trees, permanent status protection, task endpoint permissions,
owner/project moves, real time-reference deletion checks, hierarchy races, and
Stage 3 schema upgrades. Stage 5 adds controlled multi-day timelines, atomic
correction and permission checks, UTC/Berlin midnight allocation, lifecycle upgrades,
and independent-connection recording/day-save races. Stage 6 adds timesheet browser
acceptance. Stage 7 adds report fixtures with independently known totals, a report
access matrix, snapshot consistency, and actual CSV downloads. Stage 8 adds
reference lifecycle, private-image validation/rollback, screenshot fixtures,
English/Russian search, index upgrades and a search/revocation race.
Stage 9 adds administrator self-protection, server recovery/status preservation,
session invalidation, account rollback and waiting-update checks, plus browser
workflows for own-account editing and denied stale administrator forms.
See the tracker for component versus full-run results.
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

- [Multiple-instance design](docs/multiple_instances.md) for Stage 10 configuration,
  session/data isolation and development verification. Acceptance is in progress;
  actual deployment remains Stage 11 work.
- [Architecture](architecture.md), including test isolation and search direction.
- [Domain/API design](docs/domain_design.md), including delegated initial defaults.
- [Testing charter](testing_charter.md) for risk-based scenarios and release criteria.
- [Implementation tracker](implementation_plan.md) for checks actually run,
  limitations, milestone commits, and next actions.
- [Infrastructure notes](docs/infrastructure_notes.md) for previously encountered
  setup problems, fixes, and session-specific Docker access/cleanup limitations.
