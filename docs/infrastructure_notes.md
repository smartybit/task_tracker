# Infrastructure Notes for Future Agents

Recorded on 2026-10-08 during the foundation work in `c54e5ad`. These are observed
setup problems, fixes, and verification limits, not new product requirements.
Use [README.md](../README.md) for setup commands and the
[implementation tracker](../implementation_plan.md) for current progress. Update
this note when a discovery changes; do not treat old session restrictions as
permanent properties of the VDS.

## Stage 2 Verification: 2026-10-08

The Stage 2 access blocker was resolved through explicit sandbox escalation
during verification in `e9a6ccf`. Git commit, Docker inspection, scoped Compose
lifecycle commands, and the test script ran with approval; no socket/group/daemon
permissions were changed. The sandboxed Git commit and test script failed before
escalation, and host loopback access also needed escalation. Continue requesting access when required;
past approvals do not establish access in a future session.

Earlier diagnostic documentation was reviewed and committed as `df58d99`.
Its expired session instructions have been removed; the verified findings and
access failures are retained below. Git history preserves the original text.

Two sequential approved `sh scripts/test.sh` runs exited successfully: each built
images, started ready services, migrated fresh PostgreSQL 17.11 databases, passed
system/migration-drift checks and all 13 backend tests, seeded synthetic accounts,
built TypeScript/Vite production assets, and passed all 3 Chromium checks using
Playwright 1.64.0. After each run, Docker label-filtered container/network/volume
listings showed no `task-tracker-tests` resources. The npm esbuild install-script
warning remained non-failing. No application changes were needed.

Development started with the following command, creating a fresh development
volume and applying all 18 migrations:

```sh
docker compose -f compose.yaml -p task-tracker-dev up -d --build --wait --wait-timeout 120
```

Django checks passed with no migration drift. All 3 Chromium checks passed
against its actual `frontend:5173` Compose service;
frontend-internal and host-loopback `/api/v1/health/` checks returned PostgreSQL
health through Vite's proxy. Only frontend port 5173 was published, on loopback.

The second test run took place while development remained running. Development
retained the same database system identifier, 18 migrations, zero users, and its
`domain` coordination row at revision zero; the tests did not seed development.

Development `down` retained `task-tracker-dev_development-db`. A second
`up -d --wait --wait-timeout 120` reused the same database system identifier and
counts; startup reported no migrations to apply, and the host-loopback proxied
health route passed again. Final `down` removed development containers/network
while retaining the volume. The two downloader containers remained running with
their original IDs; their volume and three pre-existing stopped containers were
preserved. No pruning, broad cleanup, or development-volume removal was used.

Stage 2 completion checks passed. Results apply to foundation source `c54e5ad`
and documentation baseline `df58d99`, with no application changes during the
checks. Current implementation status is maintained in the tracker.

## Stage 3 Verification Findings: 2026-10-08

Stage 3 extends the same Compose entry point without new runtime dependencies.
The test API explicitly trusts `http://frontend:5173` for CSRF; the development
loopback origins remain separate. Login is explicitly CSRF-protected, and
session-authenticated unsafe requests return a stable `csrf_failed` JSON error.
Public health connectivity alone did not establish these mutation behaviors.

The accounts app must precede Django auth in `INSTALLED_APPS` so its guarded
`createsuperuser`/`changepassword` command replacements take precedence. The first
backend check caught the incorrect order; corrected checks passed. Use the
interactive `bootstrap_admin` command documented in README and application
account management for subsequent account/password changes.

PostgreSQL activity sampling in a transaction can retain a statistics snapshot.
The deterministic blocked-writer regression calls `pg_stat_clear_snapshot()`
before checking `pg_stat_activity`; it then observes an actual lock wait before
committing administrator revocation. Independent connections, bounded lock waits,
and committed-state assertions are required for these concurrency checks.

The initial Chromium catalog scenario used an exact label query that did not
match the select element. Its accessible combobox name was correct; the test
now selects by that role/name. The other eight browser checks passed on that
attempt; full lifecycle results are recorded in the tracker.

One approved full-script attempt exited with status 143 during the initial test
reset, before application checks. Its cleanup completed, and Docker inspection
confirmed no test containers/network remained. The cause was not established;
the next invocation started successfully from clean test state. Keep this
interrupted attempt distinct from successful verification runs. The later
running-stack reset succeeded and did not reproduce the interruption.

Two sequential complete `sh scripts/test.sh` invocations subsequently exited 0
against Stage 3 source `5653aa5`: each passed all 35 PostgreSQL backend tests,
TypeScript/Vite build, and all 9 Chromium checks, followed by cleanup. The second
invocation reset a healthy running test stack before recreating services and
fresh databases. No test containers, networks, or volumes remained after either
run. Final Docker inspection retained both development/downloader volumes and
all five unrelated container IDs; no development migrations or fixture resets
were run. Stage 3 is complete; Stage 4 remains unstarted.

## Stage 4 Verification Findings: 2026-10-09

Stage 4 source `c2d5ca3` passed two sequential complete test-script runs, each
with exit 0, 54 PostgreSQL tests, TypeScript/production build, and 16 Chromium
checks. The first successful run reset healthy running services. After each run,
label-filtered inspection found no test containers, networks, or volumes; both
original volumes and all five unrelated container IDs were preserved. No
Docker-daemon, socket, group, or host-permission changes were made.

The verified foreground-terminal wrapper uses this noninteractive command and
captures its log plus a separate exit-status file:

```sh
timeout --foreground 1200 sh scripts/test.sh < /dev/null
```

The temporary helpers are now maintained as
[`scripts/test-runner.sh`](../scripts/test-runner.sh),
[`scripts/check-links.py`](../scripts/check-links.py), and
[`scripts/docker-diagnostics.sh`](../scripts/docker-diagnostics.sh).
The runner resolves the checkout from its location and defaults new log/status
files to ignored `.artifacts/verification/`; see
[Verification Helpers](../README.md#verification-helpers) for usage and the
focused account mode's prepared-stack requirement. Historical results below
remain at their original paths and were produced by the original temporary runner.

Successful logs/status files remain under `/tmp/task-tracker-stage4-verified1`
and `verified2` with `.log`/`.status` extensions. Keep foreground supervision,
command completion, and scoped cleanup distinct from service health. The first
terminal attempt used plain `timeout`, which created another process group; its
shell stopped with job-control state `T` when a Compose exec client tried to read
the foreground terminal. Unsandboxed inspection of the exact runner PIDs
established that state. After terminating only the stuck check clients, continuing
that test process group let its pending termination and cleanup finish (exit 143).
No application-check result was obtained from that interrupted wrapper. A
standalone check with closed input passed; `--foreground` plus closed input then
passed both complete runs.

Earlier Compose command clients exited 130 or 143 while one-off browsers continued.
A two-scenario rerun's retained `.last-run.json` reported passed with no failed
tests; another full attempt's retained browser result identified only the account
scenario as failed. These are component results, not successful lifecycle
commands. Restricted-session process probes did not reliably establish host runner
state. A `nohup` wrapper failed to produce its completion-status file even though
the account browser finished; a small `setsid` background probe also produced no
completion file. Do not rely on detached host processes in this session.

Use role/name selectors for wrapped selects and prefilled textareas. Exact
`getByLabel` queries can include option text or initial textarea content while the
accessible combobox/textbox name remains correct. The first browser attempt passed
the nine existing checks, then timed out on these selectors. Its obsolete test
stack was torn down; subsequent connection failures in that attempt were caused
by teardown. Corrected selectors passed the task workflows. Complete status/tree
workflows measured over 30 seconds, so the shared scenario deadline is 90 seconds;
normal short assertion deadlines are unchanged.

The initial full attempt passed all 54 backend tests and 15 browser checks but
exceeded the existing account scenario's 30-second deadline after deactivation.
A longer run revealed the underlying wait: an in-flight task request had already
returned the revoked colleague session to sign-in, so Refresh access no longer
existed. Reload after deactivation/password reset and assert sign-in; this verifies
invalidation regardless of which request detects it first. Use a separate synthetic
account when rerunning that scenario. The corrected focused scenario passed in
27 seconds and passed again in both complete runs. Raising the deadline alone
did not resolve the obsolete UI-state assumption.

Compose `down --volumes` does not stop a still-running one-off browser container.
An early teardown retained its network until that browser exited through `--rm`.
Inspect label-filtered containers/networks/volumes after completion and repeat
scoped cleanup if necessary; a `down` exit code alone is insufficient evidence.

The initial restricted build also failed writing Docker buildx activity under the
user's Docker configuration directory; approved escalation resolved it. Docker
inspection and Git writes continued to require session-specific approval when
restricted. Backend component checks passed fresh migrations, 52 regressions,
and two additional write-only regressions before full acceptance. Development
volumes were never migrated, reset, or seeded. Stage 4 is complete; Stage 5 remains
Not started.

## Stage 5 Verification Findings: 2026-10-09

Focused engine checks reuse the test Compose project and source-mounted backend;
no development volume is migrated. Fresh lifecycle migrations, system/drift checks,
and 19 task regressions passed. An initial 24-check engine attempt passed timeline
scenarios but failed four concurrency fixtures and the upgrade fixture: transaction
flush removes the seeded coordination row, and historical model state must include
`accounts.0002_user_session_version` to match the database. Restore the lock in
transaction fixtures and retain other apps’ latest migration targets when testing
Stage 4-to-Stage 5 upgrades. Corrected 24- and expanded 25-check runs passed;
three subsequent checks passed storage-failure rollback, subsecond totals, and
competing complete-day saves. These are component results; full lifecycle
acceptance is recorded separately in the tracker.

The shared working zone is configured through `WORKING_TIME_ZONE`; UTC is the
default and Europe/Berlin is also verified outside DST transitions. Normalization
on reads uses deterministic fragment IDs for older unsplit spans or zone changes;
reads do not change timestamps, revisions or stored rows. Accepted commands persist
normalization atomically. Do not rewrite old migration history or infer unknown
end times when configuring the zone.

Stage 5 completion: final source `2c12aa6` passed two sequential complete
`sh scripts/test.sh` lifecycles through the repository runner, labels
`stage5-verified2` and `stage5-verified3`, each exit 0. Each passed 82 PostgreSQL
tests, system/drift checks, fresh migrations, TypeScript/Vite build, and 16 Chromium
checks. An earlier baseline run (`stage5-verified1`, source `601ed20`) also exited 0;
the final-source repetitions additionally include safe write-only validation errors.
Logs and status files remain under ignored `.artifacts/verification/`.

Before `stage5-verified2`, db/web/frontend were explicitly started and all three
reported healthy; the full run then successfully reset them. The repeat started
from the inspected clean state. After each final-source run, project-label filters
showed no test containers, networks or volumes. Original container IDs
`5362f5db3c1c`, `4be32c2c4bf7`, `fd646cd028b8`, `bcd4c9629eee`, and `6cf3f68761fc`
remained, along with `task-tracker-dev_development-db` and
`youtube-downloader_downloads`. No development migration/reset/seed or host
permission changes ran. The known non-failing npm esbuild script warning remains.
Stage 5 is complete; timesheet UI/browser acceptance belongs to Stage 6.

## Stage 6 Verification Findings: 2026-10-11

The initial component run exposed `crypto.randomUUID()` being unavailable at the
plain HTTP Compose hostname. Draft keys now use local counters with timestamps;
they are stable client error keys, not persisted UUIDs. Focus checks must leave all
segments of a native datetime-local input before expecting blur/sorting. Chromium
normalizes zero seconds out of its field value; assert the actual value format.
These test corrections preserve real keyboard/focus coverage.

Sign-in initially mounted the workspace before account catalogs finished, and
resolving the first server-zone date triggered a second day load after briefly
showing recording controls. Publish the authenticated workspace once catalogs are
ready, and recognize the already-loaded owner/date/version to avoid that second
load. Readiness assertions allow 15 seconds for the multi-request initial screen;
normal assertions remain 5 seconds. A competing-tab check now explicitly waits for
the current-time checkbox before editing its timestamp.

One component command client exited 143 while its one-off browser remained running.
Container logs and retained browser artifacts supplied component evidence only;
this is not a successful lifecycle invocation. Continue to use the documented
foreground terminal runner with closed stdin for full acceptance. Do not reset the
test stack while its browser is still running. Session-specific restricted Docker
log/process inspection required approved escalation; no host configuration changed.

`stage6-verified1`, interface source `820028b`, exited 0 through the repository
foreground terminal runner: 85 PostgreSQL tests, fresh migrations/system/drift,
TypeScript/Vite build and 25 Chromium checks passed. The first run reset healthy
services. Label-filtered inspection found no remaining test containers, networks or
volumes; both original volumes and all five unrelated container IDs were preserved.

Final review adds safe handling when read revocation removes timelines from a
write-only preview, and accurate acknowledgement when storage succeeds but its
subsequent reload fails. Both focused Chromium regressions passed. The follow-up
was committed as `daf9299` and passed `stage6-verified2` in full, exit 0: 85
PostgreSQL tests, migrations/system/drift, build and 25 Chromium scenarios. The
repeat also reset a healthy running stack. Both logs/status files are retained in
ignored `.artifacts/verification/`.

After the repeat, project-label inspection again found no test containers,
networks or volumes. Original container IDs `5362f5db3c1c`, `4be32c2c4bf7`,
`fd646cd028b8`, `bcd4c9629eee`, and `6cf3f68761fc` and both original volumes were
preserved. No development migration/reset/seed or host permission changes ran.
Desktop, narrow and modal screenshots were inspected; the existing non-failing
npm warning remains. Stage 6 is complete; reporting/CSV belongs to Stage 7.

## Docker Access Is Session-Specific

Before approved lifecycle verification, an earlier agent session produced these
different outcomes:

| Action | Observed outcome |
| --- | --- |
| `docker info --format '{{json .Driver}} {{json .ServerVersion}}'` | Succeeded; daemon reported 29.8.0. |
| `docker run ...` and `docker compose build web frontend` | Succeeded; containers ran and images built. |
| `docker compose config --quiet` and test-config validation | Succeeded; validates configuration, not service startup. |
| `docker version`, Compose startup, and `docker stop` | Docker socket permission denied. |
| Forwarding Ctrl-C to running verification sessions | Rejected by the tool's approval policy. |

Read-only diagnostics supplied from the user's normal SSH terminal confirmed
that `vasiliy` (UID 1000) belonged to `docker` (GID 989), and the socket was
`root:docker`, mode `660`. Docker used the default context and
`unix:///var/run/docker.sock`, without environment overrides; Docker 29.8.0 and
the system service/socket were healthy. An inactive user-level Docker service
was expected for this system daemon. The agent saw restricted groups and
mapped socket ownership (`nobody:nogroup`). This identified an agent execution
restriction, not a daemon failure. No host permission/configuration changes were
needed; approved sandbox escalation subsequently enabled lifecycle verification.

Earlier Git staging also succeeded while commit failed creating `.git/index.lock`
on a read-only filesystem. Approved Git write access resolved that failure.

This is evidence of command/session access differences, not proof of a broken
Docker installation or an incorrect host group. Check the current session's
execution permissions before repeating host-level troubleshooting. A successful
build/run does not establish permission to start Compose services or stop them.

Do not change socket permissions, add privileged containers, mount the Docker
socket into a helper container, or otherwise route around an execution restriction.
If required startup/shutdown access is unavailable, report that limitation and
ask for an authorized session or user-run verification.

## Establish Cleanup Before Starting Services

- `docker run --rm` removes a container after it exits; it does not make an
  indefinitely running server exit. Do not assume a terminal interrupt will work.
- Prefer bounded, disposable checks when possible. The verified browser fallback
  runs `timeout 120 sh /checks/browser-checks.sh` inside its container. That script
  starts its own temporary Vite server and waits for readiness. It still needs a
  separately running test API and database; it is not a complete environment.
- Confirm an authorized cleanup path before starting long-running API/database
  services. If stopping is denied, hand off exact names and ports; do not launch
  more unbounded copies or use broad prune/volume-removal commands.
- The previous fallback used only `task-tracker-foundation-db` (loopback 55439),
  `task-tracker-foundation-api` (loopback 8009), and
  `task-tracker-foundation-frontend` (loopback 5179). The bounded browser check used
  loopback 5180. These names/ports are not evidence that services are running now.

The user initially reported those three containers stopped. Stage 2 verification
subsequently inspected all containers and independently confirmed no foundation
containers remained. Neither observation establishes future-session access.
Recheck ownership/availability before reusing names or ports; never stop an unrelated service to free a port.

After that cleanup, a Stage 2 completion attempt on the same date confirmed the
restriction remained: standalone `docker compose ps` succeeded and showed no
development-project containers; Docker info also succeeded. Test Compose startup
was denied. `sh scripts/test.sh` failed at the initial test-project reset and again
in its cleanup trap before any application checks or startup. No new verification
containers were started by that failed attempt. Later approved lifecycle
verification resolved this blocker and confirmed test and development cleanup.

## Non-Root Frontend Files Must Be Writable

The initial frontend build failed with `EACCES` while Vite wrote a temporary
configuration module beside `vite.config.ts`. Running as UID 1000 was insufficient
because `/app` and copied files were owned by root.

The fix in [docker/frontend.Dockerfile](../docker/frontend.Dockerfile) is to give
`/app` to the `node` user, install dependencies as that user, and use
`COPY --chown=node:node` for package manifests and sources. The non-root production
build and live Vite server subsequently worked. Preserve writable generated-file
locations when changing mounts; do not solve this by running everything as root or
making the entire source tree world-writable.

## Vite Must Recognize the Internal Compose Hostname

Loopback browser checks alone missed the hostname used by Compose. The
[Vite configuration](../frontend/vite.config.ts) explicitly permits `frontend` in
`server.allowedHosts`, while `/api` proxies to `web:8000` by default.

Keep this hostname aligned with Compose service names. Do not disable host
checking globally. The [foundation regression](../frontend/tests/foundation.spec.ts)
sends the internal hostname in the request and verifies acceptance. It passed,
but is not a substitute for verifying the complete Compose network/startup flow.

## Dependency Tool Cache and Runtime Differences

Backend lock generation initially failed when pip-tools tried to create the
unwritable default cache `/.cache`. It succeeded with an explicit
`--cache-dir /tmp/pip-cache`. The disposable container installed pip-tools 7.6.2
using `PYTHONUSERBASE=/tmp/pip-tools`, without changing a home-directory variable.
The resulting [backend lockfile](../backend/requirements.txt) includes hashes.
Keep lock generation under the selected Python 3.13 runtime and use a writable
tool-specific cache rather than modifying host permissions.

Host Node/npm were absent; no host installation was needed. Frontend builds use
the Node 22 image, while the Playwright image has its own Node/npm runtime. Keep
the Playwright package and image version aligned (currently 1.64.0). Its npm
printed an esbuild install-script warning, but the source build and browser checks
passed; that warning was not a failing check or a reason to enable all package
scripts indiscriminately.

## Django Migration Ordering and Test Guards

Create the schema migration before adding a data migration that depends on it.
Adding `core.0002_seed_mutation_lock` before `core.0001_initial` existed caused
`NodeNotFoundError` during `makemigrations`. The current ordering is correct:
the initial migration creates the table, then the data migration creates the
persistent `domain` coordination row. Do not rewrite already-applied migrations
to repeat this initial scaffolding workaround.

Use the dedicated test configuration, not development credentials:

- `APP_ENV=test`, database/user `task_tracker_test`, and temporary uploads.
- The backend test command rejects development settings; settings also reject
  mismatched test database/user configuration.
- The seed command accepts only the designated test databases/user and is
  repeatable. The test runner creates `test_task_tracker_test`; browser fixtures
  use `task_tracker_test` separately.
- `scripts/test.sh` resets only the fixed `task-tracker-tests` Compose project.
  Run it sequentially; do not point cleanup at the development project/volume.

## What Was and Was Not Verified

At the foundation milestone: images built, PostgreSQL 17.11 migrations and drift
checks passed, 13 backend tests passed, TypeScript/production builds passed, and
3 Playwright Chromium checks passed using the documented component arrangement.
Source-mounted backend checks and the rebuilt backend image were both exercised.

At that foundation milestone, full development Compose startup and the combined
Compose reset/test/cleanup script had not been exercised successfully. Those
checks were subsequently run with authorized access; see the verification update
above for repeatability, cleanup, and development results.

## Stage 7 Verification Findings: 2026-10-11

The backend component suite passed all 12 reporting checks twice using the
source-mounted backend in the isolated PostgreSQL test project. Initial Docker
socket denial required approved escalation; no daemon or host permissions changed.

`stage7-attempt1` passed all 97 PostgreSQL tests and the production build. Three new
browser scenarios timed out on exact `getByLabel` selects (`Report view`,
`Report project`, and `Timesheet person`); traces showed correct report totals and
the same wrapped-select behavior already documented for Stage 4. Corrected tests
use accessible combobox role/name selectors. The failure/retry/stale-response
scenario passed during that attempt, but the run was interrupted and is not a
successful full lifecycle. Ctrl-C ended the runner without a status file; its
cleanup removed services but left the one-off browser/network. Label-filtered
inspection identified that exact test-owned remainder, and project-scoped
`down --volumes --remove-orphans` removed it before restarting test services.

Original failed traces/screenshots were preserved under ignored
`.artifacts/verification/stage7-attempt1-browser/`. The corrected focused command
used foreground supervision, closed input, and a 360-second limit against the
prepared test stack. All five scenarios passed (`stage7-reports1`, exit 0), with
desktop/narrow screenshots inspected. Final full-run evidence remains in the
implementation tracker; component success alone does not complete Stage 7.

`stage7-verified1` on interface source `f4dfd00` exited 1: all 97 PostgreSQL tests,
the production build, and 29 of 30 Chromium scenarios passed. The existing account
password-reset scenario exceeded its five-second completion-message assertion
while the focused backend CSV follow-up ran concurrently. The trace confirms the
reset returned HTTP 200 after 4.6 seconds; catalog refresh then completed outside
that assertion window. This does not establish why the request was slower. The
failed trace is preserved under `.artifacts/verification/stage7-verified1-browser/`.
Cleanup was inspected: no test resources remained; all five original unrelated
container IDs and both original volumes were unchanged.

Keep remaining runtime suites sequential. The account regression now awaits and
asserts the password-reset HTTP response before its unchanged completion-message
deadline. That workflow passed in 26.6 seconds during serial `stage7-verified2`.
CSV review source `9ba2742` also passed all 12 focused PostgreSQL checks with
explicit `Accept: text/csv` and JSON errors. Full-run acceptance was pending at
this milestone.

Serial full acceptance completed on 2026-10-12: `stage7-verified2` and
`stage7-verified3` each exited 0 with 97 PostgreSQL tests, fresh migrations,
system/drift checks, TypeScript/Vite production build, and 30 Chromium scenarios.
Application source `9ba2742` and browser follow-up `7f7e583` were exercised in
both runs. The repeat's account reset workflow passed in 27.2 seconds with the
same assertion deadline; its full browser suite passed in 8.2 minutes. No runtime
suites overlapped these final runs. Both started with healthy prepared test
services, verified their reset, and completed scoped cleanup. Final inspection
found no test containers, networks, or volumes; the five original unrelated
container IDs and both original persistent volumes remained unchanged. Development
data was not migrated/reset/seeded. Logs/status are retained under ignored
`.artifacts/verification/`; final browser screenshots are preserved in
`.artifacts/verification/stage7-verified3-browser/`. Stage 7 is complete.

## Stage 8 Remarks Verification Findings: 2026-10-12

Focused source-mounted PostgreSQL verification passed 29 remarks/task checks
after correcting non-object JSON validation in the shared strict serializer.
Raising a string-shaped serializer error had caused DRF's error dictionary
construction to fail; a `non_field_errors` dictionary now returns 400 and the
regression includes arrays, strings, and numbers. No schema or dependency change
was needed for that fix. The new remarks migration passed fresh and upgrade checks.

All four focused Chromium workflows passed. The first full run
(`stage8-remarks-verified1`) passed 107 PostgreSQL tests, the production build,
and the four final-layout remarks scenarios. Its new fixtures granted the shared
administrator access to their projects, contaminating the later administrator
no-data-access assertion in the existing task workflow. The trace shows three
readable discussion tasks, confirming fixture contamination. Fixtures now use a
dedicated scenario user's authenticated API context for content; management uses
the shared administrator without changing that administrator's data permissions.

The first full run was interrupted before completion and has no successful
lifecycle status. Subsequent connection failures followed teardown. The retained
one-off browser was inspected by project label; scoped cleanup removed the test
network, and separate label-filtered listings confirmed no test containers,
networks, or volumes remained. Artifacts are retained in ignored
`.artifacts/verification/stage8-remarks-attempt1-browser/`. Docker and Git writes
required session-specific approved access; no host permissions or development
data were changed.

Corrected serial run `stage8-remarks-verified2` passed 107 PostgreSQL tests,
fresh migrations/system/drift, the production build, and all 34 Chromium scenarios
(10.7-minute browser suite). Application `7d331c6` and fixture correction `f4329c8`
were exercised. The 20-minute foreground wrapper budget expired during final
cleanup, returning 124 despite all application checks passing. Keep this distinct
from a successful lifecycle invocation. Separate inspection found no test
containers/networks/volumes, and all five original unrelated container IDs and
both persistent volumes were preserved. Final screenshots were inspected and
retained under ignored `.artifacts/verification/stage8-remarks-verified2-browser/`.

The growing suite now has a 30-minute full-run budget in `scripts/test-runner.sh`;
the focused account budget remains three minutes. Shell syntax/documentation
checks passed; another full lifecycle under the expanded budget has not run.
The older 1200-second command above records the Stage 4 arrangement. Use the
repository wrapper and README for current commands. Final-stage acceptance still
requires successful full lifecycle evidence; remarks component checks alone do
not complete Stage 8.

## Stage 8 References and Images: 2026-10-12

Reference source/migration/API checks passed five PostgreSQL tests; both new
Chromium scenarios and all four existing remarks scenarios passed (2.7 minutes).
The shared editor now uses explicit textarea labels; browser locators use control
roles because label text can include select options or textarea children.

Image streaming tests now use `TransactionTestCase`. Closing a `FileResponse`
sends request-finished and closes the database connection; doing that inside a
wrapping `TestCase` transaction made subsequent queries unusable. Real transactions
also verify after-commit file deletion. The corrected run passed all eleven
content tests (52.233 seconds). Boundary-validation assertions now verify actual
API 400 responses rather than expecting domain exceptions from serializer errors.

The HTTP Compose hostname does not provide `crypto.randomUUID`; its exception in
FileReader.onload left uploads pending. UUID v4 generation now uses
`crypto.getRandomValues`, and read failures/aborts settle their promises. A browser
narrow-screen check found intrinsic grid sizing overflowing with file inputs;
single-column task grids now use `minmax(0, 1fr)`. All three image and four remark
Chromium scenarios passed (2.8 minutes); inspected screenshots are retained under
ignored `.artifacts/verification/stage8-images-focused-browser/`.

`sh scripts/check-image-persistence.sh` exited 0. It attached a scoped synthetic
image volume, verified bytes/metadata/authorized download and admin denial, forcibly
recreated the test web container, and verified the same data and permissions again.
Cleanup removed the test stack/network/image volume. All five original unrelated
containers and both original volumes were preserved. The development image volume
is configured but no development services or data were changed. The expanded
twelve-check content suite passed (42.084 seconds), adding stale/nested rollback
and cleanup-failure recovery. Full-stage acceptance follows search implementation.

## Stage 8 Final Acceptance: 2026-10-12

English/Russian search passed eighteen focused content checks (59.425 seconds),
a separate waiting-search/revocation race (8.162 seconds) and both browser workflows
(37.9 seconds). Search narrow screenshots were inspected. Final image-draft review
moved pending remark bytes into the parent draft so a denied composer can unmount
without losing the upload; all seven image/remark browser scenarios passed.

`stage8-final-verified1` passed 126 PostgreSQL tests and the build, but one older
task browser expectation assumed automatic stale-edit refresh. The delivered image
editor intentionally retains the draft until explicit refresh. Forty other Chromium
scenarios passed; cleanup completed and the wrapper exited 1. Its artifacts are
retained. The corrected scenario now checks pending text/image retention, disabled
saving, and latest content after explicit refresh; its focused run passed in
36.8 seconds. No application change was needed for this failure.

Final source `142611f` passed `stage8-final-verified2`, exit 0: fresh migrations,
system/drift checks, 126 PostgreSQL tests (571.625 seconds), production build and
all 41 Chromium scenarios (14.2 minutes). Healthy-stack reset and final cleanup
completed. Log creation to status write measured 25 minutes 31 seconds; the
30-minute wrapper budget was sufficient. This is the successful full-stage
lifecycle evidence, superseding the earlier pending status without erasing failed
or timed-out attempts.

Independent Docker inspection found no test containers/networks/volumes. All five
original unrelated container IDs and both original volumes were preserved. Logs,
status and screenshots are retained under ignored
`.artifacts/verification/stage8-final-verified2*`; final narrow image layout was
inspected on the same application source. Development data/services were untouched.
Production deployment and full backup/restoration remain unimplemented. The
2026-10-13 stage split schedules this operational work in Stage 10; Stage 9 now
contains development activities only.

## Stage 9 Development Verification: 2026-10-13

Application source `1f79ff6` passed
`sh scripts/test-runner.sh stage9-verified1 full`, exit 0: healthy-stack reset,
fresh migrations, system/drift checks, all 139 PostgreSQL tests (594.845 seconds),
TypeScript/Vite build and all 43 Chromium scenarios (13.6 minutes). Log creation
to status write measured 25 minutes 9 seconds, within the existing 30-minute bound.
The repository foreground runner and closed input worked without modification.
Logs/status remain under ignored `.artifacts/verification/stage9-verified1.*`.

The first focused browser attempt created accounts through an API context that
shared the page's cookies, then attempted UI sign-in while still authenticated as
the fixture administrator. The form disappeared during filling. Clearing that
fixture session before UI sign-in corrected the setup; both Stage 9 scenarios
passed focused and full runs. The failed focused artifacts remain under
`.artifacts/verification/stage9-focused1-browser`.

A script-driven exploratory session exercised keyboard saves and concurrent
opposing administrator-demotion requests. One update saved and the other was
denied after privilege rechecking. Its initial assertion incorrectly expected
administrators to see no project catalogs; catalog administration is separate
from data access. Checking effective data flags instead passed and strengthened
the focused recovery fixtures. Outcomes and desktop/narrow inspection are retained
in `.artifacts/verification/stage9-exploration.md` and `stage9-focused2-browser/`.

Focused Docker commands required session-specific escalation after socket denials;
approved retries succeeded. No host/socket/group/daemon configuration changed.
Final project-label inspection found no test containers, networks or volumes.
All five original unrelated container IDs and both original volumes were
preserved. Development data/services were not migrated, reset or seeded.
Stage 9 is complete; production server/proxy configuration, deployment and
full-system backup/restoration remain Stage 10 work.
