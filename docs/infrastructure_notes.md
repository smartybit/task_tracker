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
subsequent reload fails. Focused regressions and repeat lifecycle verification
are recorded in the tracker as they finish.

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
