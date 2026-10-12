# Implementation Plan and Progress

This is the working implementation tracker. Product behavior is defined in
[requirements.md](requirements.md), technical decisions in
[architecture.md](architecture.md), and verification priorities in
[testing_charter.md](testing_charter.md). This plan defines sequencing and records
actual progress; it does not turn proposals into confirmed requirements.

## Current Position

- Last updated: 2026-10-12.
- Stages 1–7 are complete: 7 of 9 implementation stages complete.
- Stage 8 remarks/shared stars are implemented through the API and task window.
  The corrected focused PostgreSQL run passed 29 checks (10 new remarks checks
  plus 19 task regressions), including all 256 grant combinations, three new
  independent-connection races, rollback, and the Stage 7 upgrade. The four new
  Chromium workflows passed. Application `7d331c6` and fixture follow-up `f4329c8`
  passed all 107 PostgreSQL checks, the production build, and all 34 Chromium
  scenarios in `stage8-remarks-verified2`. The wrapper reached its 20-minute limit
  during final cleanup (exit 124), so successful full-lifecycle acceptance remains
  pending. Cleanup and preservation of original resources were independently
  verified. The wrapper now allows 30 minutes for the growing suite.
  Stable references are delivered in `3de23bf`; five focused PostgreSQL and two
  reference browser scenarios passed, alongside four remark regressions. Private
  images now have validated atomic saves, screenshot paste and persistent storage;
  eleven content checks, seven browser workflows and test-container replacement
  passed. The expanded twelve-check content suite passed, including cleanup
  failures and nested rollback. English/Russian search is
  underway; full-stage lifecycle acceptance remains pending.
- Stage 7 started from `0fd2774`. Backend milestone `020cd88` passed 12 focused
  PostgreSQL tests, including a 64-combination access matrix and a concurrent
  report snapshot check. Report screens and five browser scenarios are implemented;
  `stage7-verified2` and `stage7-verified3` passed sequential full lifecycles, each
  with 97 PostgreSQL tests, production build, and 30 Chromium scenarios, exit 0.
  Healthy-stack resets, cleanup, and original-resource preservation were inspected.
  Stage 7 is Done; Stage 8 is In progress.
- Stage 6 passed two sequential full lifecycle runs: `stage6-verified1` on interface
  source `820028b` and `stage6-verified2` on final application source `daf9299`.
  Each exited 0 with 85 PostgreSQL tests, fresh migrations/system/drift checks,
  TypeScript/Vite production build, and 25 Chromium scenarios. Both reset healthy
  running test services and completed inspected scoped cleanup.
- The browser now provides the right-hand timesheet, day/person selection,
  task actions/drop/picker, task/break recording, correction previews, historical
  additions, overnight continuation and atomic Edit day drafts. Invalid, stale,
  denied and failed requests preserve drafts; acknowledged saves with failed
  reloads require reload/review and are not reported as rolled back.
- Stage 6 adds three discovery endpoint checks and nine browser workflows.
  Permissions, final tasks, retained restricted references, keyboard focus,
  precision, fixed midnight connections and competing tabs passed. Desktop,
  narrow and modal screenshots were inspected. Final source also covers read
  revocation with write retained and confirmed-save/reload-failure recovery.
- Stage 6 local milestones: discovery `363bb93`, interface `820028b`, review
  follow-up `daf9299`. Both runs preserved the five original unrelated container
  IDs and both original volumes; no test containers, networks or volumes remain.
  Development data was not migrated/reset/seeded. Stage 7 reporting and CSV export
  are also complete; Stage 8 is In progress and Stage 9 remains Not started.
- Stage 5 source `2c12aa6` passed two sequential complete test-script runs,
  `stage5-verified2` and `stage5-verified3`: each exited 0 with 82 PostgreSQL
  tests, the TypeScript/production build, and 16 Chromium checks. The first
  final-source run reset healthy running test services; the repeat started clean.
- The engine now supports task/break recording, active/unfinished/closed sessions,
  independent new days, explicit overnight continuation, historical append/close,
  correction previews, last-record deletion and atomic complete-day replacement.
  Friday corrections preserve Monday recording. Invalid/stale/competing writes
  preserve continuity, references, revisions and totals.
- Shared time zone configuration in `.env`/backend settings is sufficient by
  agreement on 2026-10-09. `WORKING_TIME_ZONE` defaults to UTC; UTC, Europe/Berlin
  and reallocation after a zone change passed. DST transitions remain outside scope.
- Stage 5 adds 28 checks, including six independent-connection races, rollback
  after a storage failure, safe write-only errors, precise durations, and a Stage 4
  upgrade preserving records/IDs/revisions without fabricating missing ends.
- Stage 5 cleanup was inspected after both final-source runs: no test-owned containers,
  networks or volumes remain. All five original unrelated container IDs and both
  original volumes were preserved. Development data was not migrated/reset/seeded.
- Stage 5 local milestones: engine `601ed20`, write-only error fix `2c12aa6`.
  Detailed contracts are in [the timesheet API](docs/timesheet_api.md).
  Stage 6 completed its timesheet workspace, Edit day, and browser acceptance on
  2026-10-11. Stage 7 reporting is complete; Stage 8 remarks are implemented with
  regression checks passed. References and images are delivered; search and
  full-stage acceptance remain pending.
- Timesheet design revised by agreement on 2026-10-09: ordinary shared-boundary
  edits and last-row deletion, an atomic Edit day draft for middle corrections,
  and independent new-day recording with historical unfinished sessions. Friday
  can be completed on Monday without changing Monday's recording. Documentation
  consistency, 57 local Markdown links/anchors, and whitespace checks passed;
  no application tests or migrations ran at that documentation milestone.
  Those rules are implemented in the Stage 5 engine and Stage 6 interface.
- Stage 4 follow-up: preserved the temporary verification runner, local Markdown
  link checker, and read-only Docker diagnostics under `scripts/`, with portable
  paths and documented usage. Shell syntax, 50 local links/anchors, and isolated
  helper checks passed (both modes, success/failure status capture, closed input,
  external working directories, invalid arguments, overwrite protection, and
  diagnostic continuation). Application suites were not rerun for this tooling-only
  change; Stage 5 had not started at that tooling milestone.
- Accounts/session authentication, organization/project catalogs, grants, and task
  management are implemented. Tasks include owners, descriptions, flat/tree lists,
  project/multiple-status filters, hierarchy/project moves, configured statuses,
  status history, ancestor reopening, and protected deletion.
- Stage 4 source `c2d5ca3` passed two sequential complete `sh scripts/test.sh`
  runs, each with 54 PostgreSQL tests, TypeScript/production build, and 16 Chromium
  checks. The first successful run reset healthy running test services. The bounded
  foreground runner uses `timeout --foreground` and closed standard input.
- Actual task endpoints cover all 256 local/inherited grant combinations, no
  administrator bypass, safe write-only responses/previews, stale revisions,
  revocation, and independent-connection hierarchy/deletion/finalization races.
  Fresh migrations and isolated Stage 2 and Stage 3 upgrades passed. Real time
  references protect task deletion; PostgreSQL triggers protect statuses permanently.
- Stage 4 browser acceptance covered the seven task workflows plus nine existing checks.
  Desktop/narrow screenshots were inspected; Chromium is the accepted browser.
- Stage 4 cleanup was inspected after both successful runs. No test containers,
  networks or volumes remained. All five original unrelated container IDs and both original
  volumes, including development data, were preserved. Earlier failed/interrupted
  attempts and their verified fixes are recorded in the Stage 4 milestones and
  [infrastructure notes](docs/infrastructure_notes.md#stage-4-verification-findings-2026-10-09).
- Stage 4 local milestones: backend `bcd6b87`, interface `72bf07a`, session regression
  `c2d5ca3`. Completion evidence is recorded below and in
  `docs: record Stage 4 completion and verification`.
- Stage 5 was implemented on 2026-10-09. Stage 6 started on 2026-10-11 after
  reviewing the clean working tree, completed engine, API contracts and UI gaps.
- Administrator self-protection and server recovery policy are agreed: reject
  self-deactivation/demotion, permit changes to other administrators, and provide
  server-side password reset for any existing user with explicit reactivation and
  administrator-grant options. Self-protection and the reset/recovery command are
  not implemented yet; they remain a focused account-lifecycle follow-up outside
  Stage 3's existing completion evidence.
- Backup ownership and scope are agreed: the server administrator backs up the
  PostgreSQL cluster, attachment directory, and necessary configuration, with
  written instructions to restore the entire system on another machine. Procedure
  implementation and verification remain Stage 9 work; tooling, schedule,
  retention, and destination await deployment planning.

## Progress Overview

| Stage | Result | Status | Completion evidence |
| --- | --- | --- | --- |
| 1 | Data model and API operation design | Done | [Design and worked examples](docs/domain_design.md); documentation checks recorded below |
| 2 | Runnable application foundation | Done | Two full Compose test runs; fresh development startup, API/browser checks, restart persistence, and scoped cleanup verified |
| 3 | Accounts, organization/project setup, and permissions | Done | Two full lifecycle runs: 35 PostgreSQL tests, build, 9 Chromium checks each; running-stack reset and cleanup verified |
| 4 | Task management and task interface | Done | Two full lifecycle runs: 54 PostgreSQL tests, build, 16 Chromium checks each; running-stack reset and cleanup verified |
| 5 | Timesheet engine | Done | Two full lifecycle runs: 82 PostgreSQL tests, build, 16 Chromium checks each; lifecycle upgrade, six new races, running-stack reset and cleanup verified |
| 6 | Timesheet interface | Done | Two full lifecycle runs: 85 PostgreSQL tests, build, 25 Chromium scenarios each; discovery permissions, drafts, revocation/reload recovery, running-stack reset and cleanup verified |
| 7 | Reporting and CSV export | Done | Two sequential full lifecycles: 97 PostgreSQL tests, build, 30 Chromium scenarios each; reporting access, CSV, running-stack reset and cleanup verified |
| 8 | Remarks, references, images, and search | In progress | Remarks milestone: 107 PostgreSQL checks, build and 34 Chromium scenarios passed; wrapper timed out during cleanup (124), cleanup inspected; full-stage acceptance pending |
| 9 | Deployment preparation and release verification | Not started | — |

Statuses are Not started, In progress, Blocked, or Done. Mark a stage Done only
when its work and completion checks are satisfied. Record any blocker and the
specific action needed to resolve it; do not infer completion from elapsed effort.

## Shared Test Environment

Reuse the [shared test setup](architecture.md#reusable-test-setup) rather
than creating unrelated environments for each stage. Its core is an isolated
application and PostgreSQL setup, disposable scenario data, temporary image
storage, and a real browser when needed. Stage 2 introduces the tooling and
verified commands; later stages extend the fixtures and checks. Stage 2 evidence
below records executed checks; environments for unstarted stages remain planned.

## Stage 1: Data Model and API Operations

- [x] Define entities and relationships for users, organizations, projects, access
  grants, tasks, statuses/history, remarks, images, and timesheet entries.
- [x] Design email-based accounts before creating the initial user migrations.
- [x] Define API operations for account/catalog management, task/tree changes,
  time recording/corrections, remarks, references, images, reports, and CSV.
- [x] Define authorization checks, validation failures, and transaction boundaries
  for operations that affect multiple records.
- [x] Work through historical insertion/deletion examples, reopening ancestors,
  project moves, and used-status immutability. Record selected implementation
  approaches in the architecture and retain the distinction from product rules.

Test environment: documentation and worked examples only; no running application
is required yet. Define example inputs, expected timelines, access outcomes, and
report totals that can later become automated fixtures.

Completion check: the design covers the agreed requirements and gives each
critical operation a clear input, result, access rule, and failure behavior.
Technical details can evolve as implementation provides evidence.

The timesheet portion of this initial design was superseded by the agreed
[editing](requirements.md#timesheet-editing) and
[unfinished-day](requirements.md#unfinished-days-and-overnight-work) decisions on
2026-10-09. Domain examples and the Stage 5/6 plan now reflect them; the original
Stage 1 milestone and historical verification records remain valid design history.

Design result: [domain model and API operations](docs/domain_design.md), linked
from the architecture, covers the schema, command semantics, authorization matrix,
failure responses, locking approach, and worked examples. Stage 1 completion is a
design milestone only, not evidence of functioning features or executed tests.

## Stage 2: Application Foundation

- [x] Scaffold Django/REST Framework and React/TypeScript/Vite with PostgreSQL.
- [x] Add reproducible development startup using Docker Compose, dependency
  lockfiles, configuration templates, and appropriate ignored/generated paths.
- [x] Establish initial backend modules (`accounts`, `core`, `config`) and the
  versioned API structure from Stage 1; feature modules grow in their stages.
- [x] Introduce the initial account/database migrations and a minimal frontend
  shell that can communicate with the backend.
- [x] Set up the test harness and isolated PostgreSQL test data. Document verified
  setup, migration, build, and test commands.
- [x] Implement shared test configuration, database/upload isolation, seed/reset
  and readiness handling, selected test tooling, and result capture. Add an initial
  real-browser smoke check and document its browser target.

Test environment: containerized application services with dedicated PostgreSQL
test databases and temporary uploads. Exercise clean startup, migrations, API
connectivity, the frontend build, and the initial browser smoke check. Verify the
documented test/reset workflow without touching development data.

Completion check: a fresh development setup starts successfully, migrations run,
the frontend reaches the API, the frontend builds, and the initial automated
checks run against PostgreSQL. No unimplemented feature is presented as complete.

Completion evidence (2026-10-08, application source `c54e5ad`, verification
baseline `df58d99`; documentation-only changes during verification):

- Two sequential approved `sh scripts/test.sh` runs exited 0. Each built images,
  migrated fresh PostgreSQL 17.11 databases, passed Django system/migration-drift
  checks and all 13 backend tests, seeded synthetic accounts, built TypeScript/Vite
  production assets, and passed all 3 Playwright 1.64.0 Chromium checks.
- After each run, label-filtered Docker listings showed no test-owned containers,
  networks, or volumes. No concurrent invocations or development-data resets ran.
- Fresh development Compose startup with `up -d --build --wait --wait-timeout 120`
  succeeded, applying all 18 migrations. Development system/drift checks passed;
  3 Chromium checks passed against the actual development frontend. Requests from
  inside Vite and from host loopback reached PostgreSQL through `/api/v1/health/`.
- The second test run ran alongside development. Database system identifier,
  migration count (18), user count (0), and coordination row (`domain`, revision 0)
  stayed unchanged. Development shutdown without `--volumes` retained its volume;
  restart reused the same database identity/counts and served the proxied API.
- Final cleanup removed development containers/network and retained
  `task-tracker-dev_development-db`. The unrelated downloader services and volume,
  plus three pre-existing stopped containers, remained untouched.
- Both Compose configurations, shell syntax, Markdown links/anchors, diff, and
  whitespace were checked. No application failures or code changes were needed.
  The npm esbuild install-script warning remained non-failing.

At the Stage 2 milestone, only account/core modules were introduced; Stage 3
extends that foundation with projects, access, and the minimal timesheet model. Temporary uploads, guarded test seed/reset,
readiness checks, browser failure artifacts, and the versioned health API provide
the shared foundation. Later-stage fixtures and workflows remain unimplemented.
Stage 3 implementation progress is recorded below.

## Stage 3: Accounts and Permissions

Plan reviewed against Stage 2 verification in `e9a6ccf`. Reuse the existing UUID
email user model, migrations, session middleware, versioned API, MutationLock,
and sequential Compose test lifecycle. Stage 2 verified public health requests;
Stage 3 backend checks now verify authenticated requests, CSRF, account
administration, and grants. All 9 Chromium checks and two complete lifecycle
runs passed. The sequence below records the completed Stage 3 work.

- [x] Add `projects` and `access` modules with organizations, projects, and unique
  user/organization and user/project grants. Use new migrations without rewriting
  applied account/core migrations. Introduce the minimal per-user `Timesheet`
  record/revision from Stage 1, backfill existing users, and create it atomically
  with new accounts. Work sessions and time entries remain Stage 5 work.
- [x] Implement shared account/catalog/grant mutation services using the existing
  domain coordination lock and transaction. Check current administrator access
  inside the transaction; reject unknown fields and protected deletion/reparenting.
  Account creation and its timesheet must commit or roll back together. Management
  commands and fixture setup must preserve the same invariants.
- [x] Implement the proposed guarded first-administrator command, email/password
  sign-in and sign-out, CSRF bootstrap, and current-identity API. Use the Stage 1
  `auth/csrf`, `auth/login`, `auth/logout`, and `auth/me` contracts. Enforce CSRF on
  login and every unsafe authenticated request, return consistent safe errors,
  and keep public registration and unrestricted Django admin routes absent.
- [x] Implement administrator-created accounts, account updates/deactivation,
  global timesheet flags, and administrator-driven password reset without email.
  Apply password validation and hashing; passwords must not appear in responses
  or logs. Verify rejection of inactive accounts and invalidation of existing
  sessions after password reset/deactivation. The exact bootstrap/reset approach
  follows the implementation decisions in the architecture.
- [x] Implement independent effective task/remark read and write checks with
  organization OR project inheritance, and self/others timesheet checks. Evaluate
  current database grants on each request. Keep whole-timesheet authorization
  distinct from project reporting; administrative status grants no data bypass.
- [x] Implement administrator-only organization/project and grant APIs plus scoped
  catalog selectors for regular users. Include choices needed for authorized
  write-only operations without exposing task/remark content. Reject attempts
  to set inherited grants or unrelated account fields through these endpoints.
- [x] Add login, account/reset, catalog, and grant-management screens. Extend the
  shared frontend API client for session requests, CSRF headers/token refresh,
  and authentication/permission failures. Verify cookies and trusted origins
  through Vite's real Compose proxy; explicitly configure the internal browser
  origin in test settings while retaining bounded host/origin allowlists.
  Selecting write in the UI enables read; the API still accepts write-only grants.
- [x] Extend guarded synthetic seed/reset fixtures with two organizations,
  several projects, administrators without data grants, and representative grant
  combinations. Isolate browser scenarios that change passwords or permissions;
  do not rely on suite order or credentials left by a previous scenario.
- [x] Add PostgreSQL API/service checks for allowed/denied administration, duplicate
  grants/accounts, rollback, direct and inherited grants, write without read,
  remark task-read prerequisites, self-access, and all others-timesheet flag
  combinations. Exercise active-session grant/admin revocation and deactivation;
  verify competing grant/account operations with independent transactions.
- [x] Add separate-session Chromium workflows for login/logout, account creation
  and password reset, catalog/grant management, and access changes without a new
  login. Exercise missing/invalid CSRF and unsafe untrusted-origin requests as
  well as successful mutations through the real frontend/API/PostgreSQL stack.

Test environment: extend Stage 2's verified `sh scripts/test.sh`; retain its
PostgreSQL isolation, readiness, builds, browser artifacts, and scoped cleanup.
Keep the health/proxy regression checks. Use explicit CSRF enforcement in API
checks and real browser contexts so test-client shortcuts cannot mask failures.
Verify new migrations both on a fresh test database and against an isolated
Stage 2 schema containing synthetic existing users, including timesheet backfill.
Development data must not be used for migration or fixture-reset checks.

Completion check: the complete test script passes sequentially on two clean runs
with cleanup verified. A first administrator can be bootstrapped by the documented
command, users can sign in/out, and administrators can manage accounts, reset
passwords, configure organization/project catalogs and grants through the browser.
PostgreSQL and browser checks demonstrate CSRF/session behavior, allowed and denied management,
current permissions after changes, and independent read/write grants. Shared
service checks cover the own-timesheet exception and task/remark permission matrix;
actual task, time-entry, remark, and reporting endpoints are verified when added
in Stages 4–8. Do not present those later workflows as completed in Stage 3.

Backend milestone evidence (2026-10-08): new migrations applied, Django system
and migration-drift checks passed, and 35 PostgreSQL tests passed through the
source-mounted test Compose backend. This includes all 256 local/inherited flag
combinations, CSRF/session checks, password reset/deactivation with reactivation,
account/timesheet rollback, bootstrap command/races, concurrent grant replacement,
a blocked writer after administrator revocation, and an isolated Stage 2 schema
upgrade. Generic Django command precedence and PostgreSQL activity-snapshot
sampling were corrected after the initial checks. Frontend TypeScript/production
build passed. Browser and complete lifecycle acceptance were pending at that
backend milestone; subsequent results are recorded below.
Commit: `feat: implement Stage 3 account and permission backend`.

Interface milestone evidence (2026-10-08): the login, account/create/edit/reset,
organization/project, and grant-management screens are implemented. The first
complete clean `sh scripts/test.sh` run exited 0: 35 PostgreSQL tests, TypeScript/
production build, all 9 Chromium checks, and automatic cleanup passed. Label-filtered
Docker inspection confirmed no test containers, networks, or volumes remained.
The browser suite exercises separate sessions, CSRF/origins through the Compose
proxy, account deactivation/reset, catalog protection/rename/delete, inherited
and write-only grants, and live grant/admin revocation. A TypeScript header typing
issue and an exact-label catalog test locator were corrected. At that interface
milestone the repeatability run was in progress; completion is recorded below.
Commit: `feat: add Stage 3 account and grant management screens`.

Stage 3 completion evidence (2026-10-08, application source `5653aa5`): two
sequential full `sh scripts/test.sh` runs exited 0 without application changes
between them. Each passed readiness/migrations, Django system/drift checks,
35 PostgreSQL tests, TypeScript/Vite build, synthetic seed/reset, and all 9
Playwright 1.64.0 Chromium checks. The second invocation began with a healthy
running test stack and successfully reset it before creating fresh databases.
After each run, scoped Docker listings showed no test containers/networks/volumes.
Final inspection matched all five unrelated container IDs and preserved both
`task-tracker-dev_development-db` and `youtube-downloader_downloads`.

The 35 backend checks include the initial 13 foundation checks plus Stage 3
API/service, migration-upgrade, command, rollback, and independent-connection
concurrency scenarios. Browser checks cover six account/administration scenarios
plus the three foundation regressions. Missing/invalid CSRF and untrusted origins
are rejected through the actual Compose proxy; separate sessions demonstrate
password/deactivation invalidation and live grant/administrator revocation.

One earlier full-script attempt exited 143 during reset before application checks;
its cleanup was inspected, and the successful running-stack reset did not reproduce
it. The npm esbuild install-script warning remained non-failing. Both Compose
configurations, shell syntax, 45 local Markdown links/anchors, whitespace, and
scoped diffs were checked. No Stage 3 blocker remains. Stage 4 is Not started.
Commit: `docs: record Stage 3 completion and verification`.

## Stage 4: Tasks and Their Interface

- [x] Reuse the Stage 3 session/client, current-grant selectors, and domain mutation
  services. Check mutable permissions and expected task/domain revisions under
  the existing lock; return safe acknowledgements for write-only operations.
- [x] Implement task creation/editing, owners, project membership, hierarchy,
  configured statuses, and status-change history.
- [x] Seed the five agreed initial statuses through additive migrations. Preserve
  permanent first-use protection, including after all referencing tasks change
  status or are deleted, following the Stage 1 database-trigger design.
- [x] Enforce one project per hierarchy, cycle prevention, owner eligibility,
  final-state rules, ancestor reopening, and immutability of used statuses.
- [x] Implement deletion eligibility checks. Introduce supporting time-record
  models as needed to verify the restriction even before time recording is usable;
  reuse the existing Timesheet row and defer recording commands to Stage 5.
  Protect projects referenced by tasks against catalog deletion.
- [x] Build flat/tree task lists, project and multiple-status filters, and the
  task description window.
- [x] Verify hierarchy/project changes and ownership after access loss. Exercise
  concurrent task operations where they can invalidate the business rules.
- [x] Extend permission checks through actual task list/tree/detail/history and
  mutation endpoints, including no admin bypass, write-only responses, stale
  previews/revisions, and revocation while a writer waits for the lock.

Test environment: extend the shared fixtures with deep task trees, used/unused
statuses, differing owners, and referenced time records. Use API and browser checks
for task workflows and independent PostgreSQL connections for hierarchy races.
Retain Stage 3 regressions and add an isolated upgrade from its schema with existing
users, grants, and timesheet rows. Reuse `sh scripts/test.sh`; require two sequential
successful full runs, including reset of running services and inspected scoped
cleanup. Preserve development volumes and unrelated containers throughout.

Completion check: permitted users manage tasks through the interface, forbidden
operations are rejected by the API, and task/history invariants remain valid.
Fresh and upgrade migrations and the expanded repeatable suite pass; task deletion
protection uses real database references rather than mocked time-record checks.

Backend milestone (2026-10-09): task/status APIs, atomic hierarchy changes,
permanent status triggers, and real time-reference deletion protection implemented.
Fresh migrations, system/drift checks, and the full 52-test PostgreSQL suite passed,
including both schema upgrades and five task concurrency scenarios. Two subsequent
focused regressions passed for source-content protection in write-only move previews
and write-only/revoked command responses (54 tests now defined). Interface source
and TypeScript/production build are complete; browser and repeatable full lifecycle
acceptance remain pending. Stage 4 stays In progress; Stage 5 is Not started.
Commit: `feat: implement Stage 4 task and status backend`.

Interface milestone (2026-10-09): task workspace and status administration
implemented. The first full script attempt passed all 54 PostgreSQL tests,
TypeScript/production build, and all seven new task browser scenarios; eight of
nine existing browser checks also passed. The existing account lifecycle scenario
reached deactivation but exceeded its 30-second deadline, so the attempt exited 1.
Scoped cleanup was inspected and no test containers/networks/volumes remained.
The shared browser scenario deadline is now 90 seconds, with short assertion
deadlines unchanged. Desktop/narrow screenshots were inspected. Two sequential
successful full runs with this configuration are still required. Stage 4 In
progress; Stage 5 Not started.
Commit: `feat: add Stage 4 task workspace and status management`.

Session-regression follow-up (2026-10-09): a longer run established that the
account scenario waited for Refresh access after an in-flight task request had
already invalidated the colleague's session and returned to sign-in. The test now
reloads after deactivation/password reset and verifies sign-in independently of
which request detects revocation first. The focused account workflow passed.
The preceding full attempt again passed all 54 backend checks; its command client
later exited 143 while the browser container continued. Its retained browser
result identified only the account scenario as failed. Do not count that attempt
as successful lifecycle acceptance. The attempted background wrapper did not
survive to write its status file; final runs use a bounded foreground terminal
with separate log/exit-status files.
Stage 4 remains In progress; two successful full runs are pending.
Commit: `test: handle prompt session revocation during task loading`.

Completion verified (2026-10-09): source `c2d5ca3` passed two sequential full
repository test-script runs, each with exit 0, 54 PostgreSQL tests,
TypeScript/production build, and all 16 Chromium checks. The first successful run
reset healthy running test services. Both fresh migrations and isolated Stage 2/
Stage 3 upgrades passed. Task endpoint permissions, permanent status protection,
real time-reference deletion checks, and five task concurrency scenarios passed.
UI acceptance includes keyboard/focus, repeated confirmations, failed-request
recovery, stale tabs/previews, and live grant/session changes. Desktop and narrow
screenshots were inspected; cross-browser acceptance is not claimed.

After each successful run, label-filtered Docker inspection found no test
containers, networks, or volumes. All five original unrelated container IDs and
both original volumes were preserved; no development migrations or fixture resets
were performed. Full logs/status files remain at
`/tmp/task-tracker-stage4-verified1.log`, `.status`, and the corresponding
`verified2` paths. The verified agent wrapper keeps a foreground terminal attached
and runs `timeout --foreground 1200 sh scripts/test.sh < /dev/null`.
Both Compose configurations, shell syntax, local Markdown links/anchors, scoped
diffs, and whitespace were checked. Earlier failed/interrupted attempts are
retained above and in the infrastructure notes. No Stage 4 blocker remains.
Stage 4 Done; stop here. Stage 5 and later remain Not started.
Commit: `docs: record Stage 4 completion and verification`.

## Stage 5: Timesheet Engine

- [x] Implement task starts/switches, breaks, end-of-day markers, and personal or
  permitted other-user timesheet operations.
- [x] Add active/unfinished/closed session lifecycle and additive migrations replacing
  Stage 4's global `one_running_session` / `one_running_entry` null-end constraints.
  Preserve existing records without inventing end times; permit one active session
  per user and one unfinished tail per session.
- [x] Implement independent new-day starts by default, explicit overnight
  continuation, and session-targeted historical append/close using supplied times.
  Historical corrections must not replace today's active recording.
- [x] Implement ordinary shared-boundary edits and last-record deletion with preview,
  plus atomic `replace_day` commands carrying complete rows/markers and revision.
  Do not expose individual middle-insert/delete commands or automatic draft repair.
- [x] Validate complete day replacements, known intervals, session markers, and
  fixed neighboring-day connections; allow independent edge changes/empty days
  and valid unfinished tails. Return row-associated errors with no partial writes.
- [x] Preserve zero reported duration for active and historical unfinished tails
  until explicit closure; unknown ends must not reserve all subsequent time.
- [x] Implement closed-entry midnight splitting in the configured shared zone.
- [x] Apply multi-record changes in transactions with protection against competing
  edits, including operations across days and different task projects.
- [x] Verify continuity, overlap rejection, end-of-day resumption, invalid changes,
  rollback, Friday-to-Monday corrections, lifecycle/schema upgrades, and concurrent
  day saves/recording using independent PostgreSQL connections.

Test environment: real PostgreSQL transactions with controlled clocks and an
explicit test zone, known multi-day timelines, and independently calculated
durations. Include multiple unfinished historical days alongside active recording.
Coordinate competing requests through independent connections and verify committed
state and rollback, not just individual response codes.

Completion check: reproducible timeline examples produce correct stored intervals
and durations; successful, failed, and competing operations preserve integrity.
Invalid day drafts never reach storage, accepted drafts commit atomically, and
Friday corrections preserve Monday's rows and active-session identity. New lifecycle
constraints replace the Stage 4 schema without data loss or fabricated closures.
Shared-zone configuration is sufficient by agreement on 2026-10-09; verify the
UTC default and an explicit Europe/Berlin configuration for time-behavior acceptance.

Implementation milestone (2026-10-09): backend lifecycle migrations, strict
recording/correction commands, previews, coherent day reads, known-interval
exclusion and entry/session agreement triggers are implemented. Shared working
zone configuration in `.env` is sufficient by user decision; UTC default and
Europe/Berlin are covered, including existing spans after a configuration change.
The 25 focused PostgreSQL checks passed, followed by three added rollback,
subsecond-duration and simultaneous-day-save checks. Initial fresh migrations,
system/drift checks and 19 task regressions passed. Two initial fixture failures
were corrected: transaction flush requires restoring the domain lock, and upgrade
historical models need the matching account migration state. Six independent-
connection races and a Stage 4 lifecycle upgrade are now defined. At this milestone,
two full expanded suite runs, running-stack reset and cleanup inspection remained pending. Stage 5
was In progress; Stage 6 was Not started.

Review follow-up: validation against stored neighboring rows now removes row IDs
from errors for write-only callers. Readers retain row-associated draft errors.
The actual endpoint permission-matrix regression includes that failure path.
Source `601ed20` subsequently passed an initial full invocation with 82 PostgreSQL
tests, the production build and 16 Chromium checks (exit 0, inspected cleanup).
The error-response follow-up passed its focused endpoint regression and the two
final-source full runs below.

Completion evidence (2026-10-09, application source `2c12aa6`):

- Two sequential full lifecycle invocations exited 0:
  `sh scripts/test-runner.sh stage5-verified2 full` and
  `sh scripts/test-runner.sh stage5-verified3 full`. Each runs the unchanged
  `sh scripts/test.sh` under foreground supervision with closed input and a
  bounded timeout. Logs/status files are in ignored `.artifacts/verification/`.
- Each run passed fresh PostgreSQL migrations, Django system/migration-drift
  checks, all 82 backend tests (54 existing plus 28 Stage 5), synthetic seeding,
  TypeScript/Vite production build, and all 16 existing Chromium checks.
  The timesheet interface/browser acceptance is Stage 6 and remains unimplemented.
- Independent expected totals passed: Friday 7h 17m while Monday remains active;
  unknown tails zero; breaks excluded; UTC and Berlin midnight allocations;
  existing-span reallocation after a zone change; no subsecond truncation.
- Complete drafts reject gaps, overlaps, invalid durations, markers and foreign
  identifiers with no writes. Independent edges/empty days and unfinished tails
  are accepted. Fixed neighboring midnight coverage survives reattribution.
  Shared-boundary/last-deletion/resumption previews do not write; stale revisions,
  stale previews, revoked grants and injected storage failures roll back entirely.
- Actual authenticated/CSRF endpoints passed self/others flag combinations,
  no administrator bypass, task-read selection/retained restricted references,
  historical final tasks without reopening, and safe write-only success/errors.
- Six independent-connection races passed: competing starts, competing whole-day
  saves, Friday save versus Monday switch, append versus boundary edit, waiting
  writer after timesheet-write revocation, and recording versus task deletion.
- The isolated Stage 4 upgrade preserved open/closed record IDs, timestamps and
  sheet revisions, backfilled lifecycle without invented ends, removed old global
  null-end uniqueness, and permitted multiple unfinished tails. Fresh schemas and
  earlier Stage 2/3 upgrades also passed in both complete runs. PostgreSQL excludes
  overlapping known ranges and protects active/tail uniqueness and sheet agreement.
- The first final-source run reset healthy db/web/frontend services. After both
  runs, label-filtered inspection found no test containers, networks or volumes.
  All five unrelated container IDs and both original volumes were unchanged;
  development data was not migrated/reset/seeded. No daemon permissions changed.
- Both Compose configurations, 64 local Markdown links/anchors, and whitespace
  checks passed. Remaining limitations: Stage 6 UI and later feature stages,
  DST-transition acceptance, and the administrator lifecycle follow-up (policy
  subsequently agreed; self-protection and server recovery remain unimplemented).
  Stage 5 is Done; next action is implementing Stage 6 from its plan below.

## Stage 6: Timesheet Interface

Started and completed 2026-10-11. Review confirmed the Stage 5 engine and its
documented acceptance history; browser recording and day editing were absent at
the start. Added the right-hand panel, recording/correction controls, in-memory
day drafts, discovery endpoints and browser checks.

Discovery milestone (2026-10-11): added a paginated label-only colleague directory
and read-gated shared-zone context with unfinished session tails. Three focused
PostgreSQL checks passed: global flag combinations including administrators,
revocation, no task-description/account-field disclosure, unchanged stored rows
and revisions on GET, and Berlin date allocation. Initial fixture assertions were
corrected for the existing anonymous 403 response and shared-zone command dates.
TypeScript/Vite build passed for the first UI pass. Initial browser acceptance
exposed insecure-context UUID generation and excessive initial loads,
which were corrected. Follow-up workflows passed recording, Friday corrections,
invalid/transient draft saves, ordinary preview corrections, colleague permissions,
and overnight boundaries. A competing-tab check exposed a transient second initial
day load; owner/date/version load tracking avoids it. That component artifact
recorded eight passes and one failure before the final load fix. Build and 64
local links/anchors passed; desktop, narrow and modal screenshots were inspected.
Stage 6 was In progress at that milestone; both full runs below pass the fixed
competing-tab workflow.

- [x] Build the right-hand Task / Start Time / End Time table and Day selector.
- [x] Add task drag-and-drop, task switching, break and end-of-day actions.
- [x] Add ordinary shared-boundary editing and last-record deletion with previews;
  historical append/close asks for selected-day timestamps. New days start
  independently; offer explicit Continue previous session for overnight work.
- [x] Add Edit day as a modal copy of the selected day, available on historical
  and running days. Support arbitrary draft insertion/deletion/time edits, visible
  gap/overlap errors, stable focus, and sorting after field editing completes.
- [x] Add a searchable task picker with project/status filters, including final
  tasks for historical work without reopening them. Retain restricted references
  while protecting task details and checking new-selection permissions.
- [x] Implement Save changes/Cancel, changed-draft dismissal confirmation, atomic
  whole-day submission, and draft preservation after errors/stale revisions.
  Require reload/review rather than automatic replay or overwriting newer work.
- [x] Display active/unfinished/closed sessions and partial totals/unfinished
  warnings; preserve fixed midnight connections in the one-day editor.
- [x] Support viewing/editing other users' timesheets according to the global flags,
  while keeping restricted task details protected.
- [x] Add browser workflow checks for recording work and correcting past work.
  Cover Friday corrections while Monday records, draft validation/cancel, final
  task selection, sorting/focus, competing tabs, and failed-request recovery.

Test environment: real automated browsers against the shared frontend/API and
reset test database. Use independent sessions or tabs, controlled timestamps, and
seeded cross-project timesheets to exercise edits, permission boundaries, and
failed-request recovery. Include a historical unfinished session alongside today's
active session; no test should treat the unknown historical end as weekend work.

Completion check: users can complete the task-to-timesheet workflow through the
browser, including ordinary historical additions and advanced Edit day corrections.
Invalid drafts are editable but cannot be saved, Cancel leaves stored work intact,
and completing Friday preserves Monday recording. This is the first useful
work-tracking milestone; the remaining first-version features are still outstanding.

Lifecycle milestone (2026-10-11): `stage6-verified1` exited 0 against interface
source `820028b`, passing 85 PostgreSQL tests, fresh migrations, system/drift checks,
TypeScript/Vite build, and 25 Chromium scenarios. It reset healthy running services;
label-filtered cleanup found no test containers, networks or volumes. All five
original unrelated container IDs and both original volumes were preserved.

Final review follow-up: handle previews without timelines after colleague read
revocation while write remains; distinguish acknowledged saves from subsequent
reload failures, requiring reload/review without duplicate writes. Row validation
messages now show plain text and empty draft rows sort stably. Both focused
Chromium regressions passed (40.4 seconds), and TypeScript/Vite build passed.
The follow-up was committed as `daf9299`; repeat lifecycle acceptance follows.

Completion evidence (2026-10-11):

- `sh scripts/test-runner.sh stage6-verified1 full` and
  `sh scripts/test-runner.sh stage6-verified2 full` both exited 0, sequentially.
  The first tested interface `820028b`; the repeat tested final source `daf9299`
  with the review follow-up and expanded permission/reload assertions.
  Logs/status files are retained under ignored `.artifacts/verification/`.
- Each passed fresh PostgreSQL migrations, system and migration-drift checks,
  all 85 backend tests (82 existing plus three discovery checks), the TypeScript/
  production build, and all 25 Chromium scenarios (16 existing plus nine new).
  Earlier migration upgrades and independent-connection races remained green.
- Browser recording passed task actions/drop, switching, breaks, closing and reload
  persistence. Historical additions use explicit selected-day times and final
  tasks without reopening them. Friday totals are 7h 17m while today's independent
  active session stays unchanged; the backend retains the controlled Friday-to-
  Monday example. Unknown tails remain zero and no weekend interval is fabricated.
- Day drafts passed insertion/removal, local gap/overlap highlighting, sorting
  after native field completion, stable keyboard focus, Cancel/Escape confirmation,
  atomic saves, invalid/transient failure recovery and explicit stale reload/review.
  Running-day drafts retain unknown ends and subsecond timestamps. Independent
  historical days can be cleared without changing active work.
- Ordinary boundary, last-record deletion and resumption previews passed stale
  domain rejection and conversion advice. Overnight continuation splits known
  work; one-day editors retain fixed midnight connections and neighboring totals.
  Client zone conversion and backend context dates passed Berlin checks alongside
  the UTC test stack; DST-transition acceptance remains outside scope.
- Whole colleague sheets show every project while restricting task descriptions.
  Read-only controls, retained inaccessible references, revoked write on save,
  and safe previews after read revocation with write retained passed. A confirmed
  save followed by a failed reload is acknowledged, preserves the local copy,
  increments revision only once and disables another save until reload/review.
- Both full runs reset healthy services. After each, project-label inspection
  found no test containers, networks or volumes. The five original unrelated
  container IDs and `task-tracker-dev_development-db` / `youtube-downloader_downloads`
  were unchanged. No development migrations/resets/seeds or host permission changes
  ran. The known non-failing npm warning remains.
- Both Compose configurations, 64 local Markdown links/anchors and whitespace
  checks passed. Stage 6 is Done. Next action is Stage 7 reporting/CSV; remarks,
  references, images, search and deployment remain later-stage work. Chromium is
  the verified browser; agreed administrator self-protection and server recovery
  remain unimplemented follow-up work.

## Stage 7: Reporting and CSV Export

Started 2026-10-11 from clean source `0fd2774`. Reviewed reporting/access rules,
snapshot and shared-zone contracts, existing account/task/timesheet services, and
infrastructure notes. Use the existing Django/REST Framework and React/TypeScript
stack plus Python's standard CSV module; no new runtime dependencies were added.
Backend milestone `020cd88` and interface milestone `f4dfd00` are implemented.
Full lifecycle verification passed twice; Stage 7 completed on 2026-10-12.

- [x] Implement a shared query restricted to readable projects and permitted
  timesheet users before aggregating or exporting records.
- [x] Implement project summaries, person/day summaries, and task hierarchy reports,
  with person/date filters and separate direct/descendant hours.
- [x] Calculate decimal hours from original durations, count open entries as zero,
  and reflect current task projects and parent relationships.
- [x] Build report screens and export individual authorized task records for a
  selected period with the agreed CSV columns. Exclude special entries and do not
  apply interactive report filters to the dump.
- [x] Reconcile results against independently calculated examples, including
  historical edits, project moves, rounding, midnight work, and access changes.

Test environment: seed small datasets with independently known project/person/day
and direct/descendant totals. Compare API and browser results with those values;
parse actual CSV downloads and check individual records, permissions, quoting, and
rounding before and after edits or moves.

Completion check: browser reports and CSV satisfy their respective access rules
and agree with source records. The task-to-timesheet-to-report workflow is usable.

Backend milestone (2026-10-11): shared authorized selector, read-only repeatable-read
snapshots, project/person-day/hierarchy APIs, label-only report options, exact
microsecond accounting, and spooled CSV downloads implemented without schema or
dependency changes. All 12 focused PostgreSQL checks passed, including 64 grant/role/
timesheet-flag combinations across reports/options/CSV, real-session deactivation,
historical day correction, hierarchy/project moves, subsecond rounding, Berlin
midnight reallocation, materialized downloads, and an independent-connection
move/revocation during a report snapshot. Interface and full acceptance were
pending at this milestone. Contract: [reporting API](docs/reporting_api.md).

Interface milestone (2026-10-11): all three report views, inclusive date/person/
project/subtree filters, and CSV downloads are implemented. Failed or stale loads
do not display older results; revoked selections require a new choice. All five
focused Chromium scenarios passed (`stage7-reports1`, exit 0), covering independent
totals, actual quoted Unicode CSV bytes, open/special records, report-filter
independence, whole-sheet/report separation, live access changes, administrator
restrictions, keyboard navigation, failure/retry/stale responses, Edit day
corrections, and current project moves. Desktop and narrow screenshots inspected.
The first full attempt passed all 97 PostgreSQL tests and the production build;
three browser selectors timed out before correction, and that attempt was
interrupted, with scoped cleanup inspected. At this component milestone, two
sequential full lifecycles on the final source remained required for completion.

Review follow-up (2026-10-11): CSV downloads now accept explicit `Accept: text/csv`
requests while validation/authentication errors retain JSON responses. All 12
focused PostgreSQL checks passed with the explicit CSV header, including the
64-combination matrix and JSON validation-error regression. This suite overlapped
the `stage7-verified1` browser phase; an existing password-reset assertion exceeded
its five-second wait while the operation was still pending. Cause is not established;
remaining runtime suites were scheduled sequentially. Full final-source acceptance
was still pending, and the failed run is not counted toward completion.

Browser timing follow-up (2026-10-11): the failed `stage7-verified1` trace shows
password reset returned HTTP 200 after 4.6 seconds, followed by the normal catalog
refresh. The account browser regression now explicitly awaits and checks that
response before the existing five-second completion-message assertion, rather
than including the password operation in that assertion window. No application
behavior or assertion deadline changed. The corrected account lifecycle passed
in 26.6 seconds during serial `stage7-verified2`; that run's 97 PostgreSQL tests
and production build also passed. Full browser completion and repeat were pending
at this milestone.

First successful full lifecycle (2026-10-11): `stage7-verified2` exited 0 with all
97 PostgreSQL tests, fresh migrations/system/drift checks, TypeScript/production
build, and all 30 Chromium scenarios. Application source `9ba2742` and browser
timing follow-up `7f7e583` were exercised. The run reset healthy prepared test
services, and cleanup inspection found no test containers/networks/volumes. All
five original unrelated container IDs and both original persistent volumes were
unchanged. Logs/status and browser artifacts are retained under ignored
`.artifacts/verification/`. One sequential complete repeat remained at this milestone.

Completion verification (2026-10-12): `stage7-verified3` exited 0 on `7f7e583`,
including application follow-up `9ba2742`, after the successful `stage7-verified2`.
Both serial full lifecycles passed 97 PostgreSQL tests, fresh migrations, system
and migration-drift checks, TypeScript/Vite production build, and 30 Chromium
scenarios each. The repeat's browser suite passed in 8.2 minutes, including the
account reset workflow in 27.2 seconds. Both runs reset healthy prepared test
services and completed scoped cleanup. Final inspection found no test containers,
network, or volumes; all five original unrelated container IDs and both original
persistent volumes were preserved. No development data was migrated/reset/seeded.
Final log/status are `.artifacts/verification/stage7-verified3.log` and `.status`;
browser screenshots are preserved under ignored
`.artifacts/verification/stage7-verified3-browser/`.
Stage 7 is Done. Stage 8 is underway; administrator self-protection/recovery
and deployment backup procedures remain the separately recorded follow-ups.

## Stage 8: Remarks, References, Images, and Search

Initial search languages agreed on 2026-10-12: English and Russian, including
mixed-language content. Concrete multilingual indexing/query configuration is
Stage 8 work; centralize language handling to allow later additions. Stage 8
is In progress as of 2026-10-12. The first milestone implements remarks and
shared stars through the API and task window, including permission-aware task
deletion. References, images, and multilingual search follow this milestone.

Stable inline references now synchronize transactionally and resolve current
permissions through a batched API; the browser provides insertion/navigation.
Images, search, and final lifecycle acceptance follow.

- [x] Implement chronological remarks with authors/timestamps, shared stars at
  the top of the task window, and navigation to original remarks.
- [x] Implement task/remark cross-references with stable targets and appropriate
  handling of restricted or deleted objects.
- [x] Implement images in descriptions and remarks, validated formats/size limits,
  persistent storage, and permission-checked downloads. Include screenshot pasting
  if practical, recording its delivered or deferred status explicitly.
- [ ] Implement search over tasks, descriptions, and remarks with authorized
  results and snippets, using PostgreSQL full-text search and indexes through
  Django as described in the [search approach](architecture.md#planned-search-approach).
- [ ] Verify content workflows, reference lifecycle, image validation, and direct
  access attempts using the API and browser.

Test environment: use temporary image storage, valid/invalid/size-boundary files,
and seeded remarks, references, and searchable text with different access grants.
API and browser checks cover direct downloads, snippets, shared stars, and target
lifecycle changes; exercise screenshot pasting if delivered.

Completion check: collaboration, attachments, and search work through the interface
without revealing protected content. Remaining optional work is documented.

### Remarks Milestone: 2026-10-12

The first milestone adds the UUID Remark model/migration, chronological and
shared-star endpoints, revision-aware edit/delete/star commands, and the task
window conversation/composer. Author/creation time survive edits by other writers;
stars leave the edit timestamp unchanged. Write without remark read returns safe
acknowledgements. Task moves change remark access through current containment.
Eligible task deletion requires content write, previews remark counts, and rejects
intervening content changes. Backend reads/writes use the domain lock for coherent
permission checks; no new runtime dependency was added.

The first component run passed 28 of 29 checks and exposed a shared serializer
failure for non-object JSON; corrected validation returns 400. The repeat passed
all 29 PostgreSQL checks, fresh migrations, system and drift checks. Four focused
Chromium scenarios passed collaboration, literal text, star navigation/focus,
access loss, write-only posting, stale/failed saves, saved/reload-failed recovery,
keyboard/repeated submissions, and deletion previews. Desktop/narrow screenshots
were inspected. Final review moved the shared stars above the description;
the complete regression suite exercised this final layout.

Application milestone: `7d331c6`. The first full run
(`stage8-remarks-verified1`) passed all 107 PostgreSQL tests, the final
TypeScript/Vite build, and all four final-layout remark browser scenarios. The
new browser fixtures granted the shared administrator application access, causing
the later task-access baseline to fail (three discussion tasks remained readable).
The run was interrupted before completion; later browser connection failures
followed test-service teardown. It is not a successful lifecycle run. Its browser
artifacts are preserved under ignored
`.artifacts/verification/stage8-remarks-attempt1-browser/`.

Fixture follow-up `f4329c8` creates content through a dedicated scenario user
context and never grants the shared administrator data access. The corrected
serial run (`stage8-remarks-verified2`) passed 107 PostgreSQL checks, fresh
migrations/system/drift, the production build, and all 34 Chromium scenarios
(browser suite 10.7 minutes). The administrator-access regression passed. Final
desktop/narrow screenshots were inspected and retained under ignored
`.artifacts/verification/stage8-remarks-verified2-browser/`.

The wrapper's 20-minute total budget expired during final cleanup and returned
124 despite all application checks passing. This is component regression evidence,
not a successful full lifecycle invocation. Independent inspection found no test
containers, networks, or volumes; all five original unrelated container IDs and
both original persistent volumes remained unchanged. Development data was not
migrated/reset/seeded. Log/status are retained under ignored
`.artifacts/verification/stage8-remarks-verified2.log` and `.status`.

The full runner now allows 30 minutes; its shell syntax and documentation checks
passed. The expanded deadline has not been exercised with another full application
run. At that point references, images and search were unimplemented. Stage 8
remains In progress; the remarks milestone's
application checks are complete.
The next milestone was stable references, followed by private images and search;
their subsequent progress is recorded below.

### References Milestone: 2026-10-12

Added source-owned stable references, strict batched resolution under the domain
lock, and migration backfill. Target deletion preserves unavailable tokens;
renames/moves resolve current labels/containment. Restricted and missing responses
have identical shapes. Editors provide task/remark pickers with selection insertion
and focus restoration. Reference links navigate to the original task or remark;
star previews use a generic token label.

Five focused PostgreSQL checks passed (24.620 seconds), including source rollback,
constraints, permissions/lifecycle, strict inputs, and migration backfill. Fresh
migrations, system/drift checks and TypeScript/Vite build passed. Both new Chromium
reference scenarios passed after correcting locators to use accessible roles;
the four existing remark scenarios also passed (six scenarios, 2.7 minutes).
Checked 81 local documentation links/anchors and whitespace. Full-stage acceptance
remains pending; next work is private image insertion and multilingual search.

### Images Milestone: 2026-10-12

Delivered source-owned private files/metadata, inclusive
2 MiB validation, atomic source saves with rollback cleanup, after-commit removal,
file selection/paste, and a persistent development volume. Eleven focused content
PostgreSQL checks passed (52.233 seconds), including six image scenarios and the
reference regressions. The frontend build passed. Initial browser runs exposed
`crypto.randomUUID` being unavailable on the HTTP test service hostname; UUID v4
generation now uses `crypto.getRandomValues`, and file-read failures settle their
promises. Image/browser and container-recreation acceptance are still running or
pending at that point. All three image and four remark Chromium workflows
subsequently passed (2.8 minutes), including the corrected narrow layout.
Inspected screenshots are retained under ignored
`.artifacts/verification/stage8-images-focused-browser/`.

`sh scripts/check-image-persistence.sh` exited 0: original image bytes, PostgreSQL
metadata and private download access survived forced test-web container replacement
with a temporary named volume. Its cleanup removed the scoped test stack/network/
volume, preserving all original unrelated containers and volumes. Development
services/data were untouched. The expanded suite passed all twelve content checks
(42.084 seconds), including stale/nested rollback and cleanup-failure recovery.
Fresh migrations, system/drift, both Compose configurations, production build,
82 local documentation links/anchors and whitespace passed. Search and final
lifecycle acceptance remain outstanding.

## Stage 9: Deployment and Release Verification

- [ ] Select and configure the application server, reverse proxy, production
  frontend assets, and deployment settings for the VDS.
- [ ] Persist PostgreSQL data and images across application restarts/replacements.
- [ ] Document initial setup, account bootstrap, migrations, startup, and updates.
- [ ] Select backup tooling, schedule, retention, and destination for backups
  managed by the server administrator. Document and exercise full-system
  restoration on another machine from backups of the PostgreSQL cluster,
  attachment directory, and necessary configuration; verify database/attachment
  consistency in isolation.
- [ ] Run the critical API/database and browser checks from the testing charter
  and complete exploratory sessions for permissions and competing edits.
- [ ] Verify startup, migrations, and persistence in the deployment configuration.
  Record actual deployment state and remaining limitations.

Test environment: an isolated deployment-like Compose setup with production
frontend assets, the selected server/proxy, and persistent test volumes. Exercise
migrations, restart/replacement, and agreed backup/restore checks using synthetic
data only. Run critical API/browser checks and exploratory sessions without using
live VDS databases or attachments.

Completion check: the first-version completion criteria in the testing charter
are met, operations are documented, and no unresolved issue exposes unauthorized
data, loses records, corrupts timelines, or produces incorrect totals.

## Decisions and Dependencies to Track

- Implement the [agreed administrator policy](requirements.md#users-and-authentication)
  before production use: reject self-deactivation/demotion, allow changes to
  other administrators, and provide server-side password reset with explicit
  reactivation and administrator-grant options. Include serialized competing-update
  and recovery checks from the testing charter. Self-protection and the recovery
  command are planned work, not part of Stage 3's existing completion evidence.
- Shared zone is configurable in `.env`/backend settings by agreement on
  2026-10-09; verify UTC and Europe/Berlin with controlled clocks in Stage 5.
- Implement and verify the [agreed backup policy](architecture.md#agreed-backup-and-restoration-policy)
  in Stage 9 before production use, including written full-system restoration
  instructions. Deployment planning selects tooling, schedule, retention, and
  destination. This does not block earlier implementation stages.
- Select supplementary frontend libraries, the application server, and reverse
  proxy when their stages need them; record choices in the architecture.
- Refine proposed defaults as their stages begin. Update the authoritative
  documents when a decision changes rather than keeping conflicting rules here.
- Follow the default stage order, introducing supporting models or fixtures earlier
  when required to enforce rules. Tests and browser integration grow with features.

## Maintaining This Tracker

- Update the current position, stage status, and checkboxes when work starts or
  reaches a verified intermediate result. Partial work remains visible.
- Record significant progress below with the date, delivered result, verification
  actually performed, relevant commits, and any blocker or next action.
- Commit coherent milestones following [AGENTS.md](AGENTS.md), including the
  corresponding tracker update. Completion evidence may reference a commit that
  contains the entry by its descriptive subject; later updates can add its hash.
- Keep planned checks distinct from executed checks. Do not mark a stage Done
  merely because its files exist or its implementation has been drafted.

## Progress Log

These entries record results at each milestone. Current status and next work are
defined in Current Position and the stage sections above.

| Date | Milestone | Evidence |
| --- | --- | --- |
| 2026-10-08 | Planning baseline prepared | Requirements, architecture, testing charter, and agent/Git guidance are recorded through `cba1d65`. |
| 2026-10-08 | Implementation tracker created | Reviewed against project documents; local links and whitespace checked. No application tests existed or were run at this milestone. Included in the commit titled `docs: add implementation plan and progress tracker`. |
| 2026-10-08 | Reusable test setup documented | Architecture defines shared services, isolation, fixtures, execution lifecycle, and evidence; all nine stages identify their test environment. Documentation consistency, local links, and whitespace checked in the commit titled `docs: describe reusable test setup across implementation stages`. No runtime or application tests were implemented or run at this milestone. |
| 2026-10-08 | Search infrastructure direction recorded | Architecture and Stage 8 specify PostgreSQL-backed search through Django, without a separate search service for v1. Diff, local link/heading, and whitespace checked; no application tests run. Commit: `docs: record PostgreSQL search approach`. |
| 2026-10-08 | Stage 1 design completed | Domain records, API/access/error contracts, timeline commands, locking, and worked acceptance examples reviewed against requirements and charter; 26 Markdown links/anchors and whitespace checked. No application/database/browser tests run. Environment probe: Python 3.13.5 and Compose v5.5.1 available; initial Docker version denied, approved Docker info succeeded (29.8.0); host Node/npm absent. Commit: `docs: complete initial domain and API design`. |
| 2026-10-08 | Stage 2 foundation implemented and component-verified | Built Django/React images; PostgreSQL 17.11 migrations and migration-drift/system checks passed; 13 backend tests passed; TypeScript and Vite production build passed; 3 Playwright 1.64.0 checks passed against real API/database services, including the internal Compose hostname. Backend checks/seed entry point exercised, Compose files validated, shell syntax/local links/whitespace checked. Commands/environment documented in README. Compose startup was denied by session Docker socket permissions, so full orchestration/reset/cleanup script is not claimed verified and Stage 2 was In progress at this milestone. Commit: `feat: scaffold Dockerized Django and React foundation`. |
| 2026-10-08 | Infrastructure discoveries preserved | Added troubleshooting notes linked from AGENTS and README; recorded user-confirmed cleanup without claiming independent inspection or restored permissions. Documentation checked against existing code and prior results; local links/anchors and whitespace checked. No runtime tests rerun. Commit: `docs: preserve infrastructure discoveries for future agents`. |
| 2026-10-08 | Stage 2 completion attempt blocked | Docker info succeeded (29.8.0); standalone development `docker compose ps` showed no containers. Test Compose startup was denied. `sh scripts/test.sh` failed at its initial test-project reset and its cleanup trap with Docker socket permission denied; no application checks ran or new containers started. Recorded the evidence and blocker; documentation consistency/links/whitespace checked. Commit: `docs: record Stage 2 verification access blocker`. Stage 2 was incomplete at this milestone; the later lifecycle verification resolved the blocker. |
| 2026-10-08 | Stage 2 lifecycle verification completed | Diagnostic documentation reviewed/committed as `df58d99`. Two full test-script runs passed (13 PostgreSQL tests, build, 3 Chromium checks each), with no test resources left. Fresh development startup/migrations, 3 development Chromium checks, proxy connectivity, isolation, and restart persistence passed; final cleanup retains development data and unrelated resources. Docker/Git/host-loopback access used explicit sandbox approvals. Documentation links/anchors, configuration, shell syntax, diff, and whitespace checked. Commit: `docs: complete Stage 2 lifecycle verification`. Stage 2 completed; Stage 3 implementation remained unstarted. |
| 2026-10-08 | Stage 3 plan reviewed against verified foundation | Clarified existing scaffolding, session/CSRF proxy checks, transactional account/grant services, minimal timesheet backfill, administrator bootstrap/reset proposals, fixture isolation, and completion boundaries for later endpoints. Removed obsolete session instructions while retaining infrastructure findings and milestone evidence. Documentation consistency, local links/anchors, and whitespace checked; no runtime tests run for this documentation review. Stage 3 implementation was Not started at this planning milestone. Commit: `docs: refine Stage 3 plan and remove stale handovers`. |
| 2026-10-08 | Stage 3 backend implemented and verified | Session/CSRF, account/bootstrap/reset, project/organization/grant APIs and shared policies implemented; additive migrations/backfill and transactional domain services verified. System/drift checks and 35 PostgreSQL tests pass, including permission matrix, upgrade, rollback, and independent-connection races. Browser/full lifecycle verification was pending at this milestone; Stage 3 was In progress. Commit: `feat: implement Stage 3 account and permission backend`. |
| 2026-10-08 | Stage 3 management interface verified | Added session-aware frontend client and login/account/catalog/grant screens. First full clean test script exited 0 with 35 PostgreSQL tests, build, 9 Chromium checks, and inspected cleanup. Corrected browser test header typing and catalog select locator; repeatability was pending at this milestone. Stage 3 was In progress. Commit: `feat: add Stage 3 account and grant management screens`. |
| 2026-10-08 | Stage 3 completed | Source `5653aa5` passed two sequential full test-script runs, each with 35 PostgreSQL tests, TypeScript/Vite build, 9 Chromium checks, and inspected cleanup. The second run reset running services successfully; initial reset interruption (143) did not reproduce. Upgrade/backfill, CSRF/session behavior, permission matrix, rollback, and concurrency verified. Both development/downloader volumes and all unrelated container IDs preserved. Configuration, shell syntax, 45 local Markdown links/anchors, diff, and whitespace checked. Stage 3 Done; Stage 4 remains Not started. Commit: `docs: record Stage 3 completion and verification`. |
| 2026-10-08 | Post-Stage 3 lessons incorporated | Updated shared test setup to reflect implemented coverage and strengthened Stage 4 plans for service reuse, real endpoint permissions, status protection, Stage 3 schema upgrades, and repeatable scoped cleanup. Account-service review identified last-active-admin lockout; recorded a proposed safeguard and recovery decision without changing agreed behavior. Checked documentation consistency, 47 local Markdown links/anchors, and whitespace; no runtime tests run for this documentation-only change. Stage 4 remains Not started. Commit: `docs: incorporate Stage 3 lessons into remaining plan`. |
| 2026-10-09 | Stage 4 backend implemented | Additive task/status and time-reference migrations, strict revision-aware command/preview endpoints, scoped owner selection, permanent status triggers, and atomic hierarchy/history/deletion rules. Fresh migrations and system/drift checks passed; full 52-test PostgreSQL regression suite passed, including five task races and Stage 3 upgrade. Two added focused write-only regressions passed; 54 tests now defined. Browser/full lifecycle acceptance pending; Stage 4 In progress, Stage 5 Not started. Commit: `feat: implement Stage 4 task and status backend`. |
| 2026-10-09 | Stage 4 interface implemented and component-verified | Added flat/tree task workspace, project/multiple-status filters, description/history panel, owner/status/move/deletion flows, safe creation in write-only projects, and status catalogs. First full script attempt passed 54 PostgreSQL tests, build, all seven new Chromium scenarios, and eight existing checks; one existing account lifecycle scenario exceeded 30 seconds after reaching deactivation. Attempt exited 1 and scoped cleanup was inspected. Shared scenario deadline adjusted to 90 seconds; assertions remain bounded. Desktop/narrow screenshots inspected. Two successful full runs pending; Stage 4 In progress, Stage 5 Not started. Commit: `feat: add Stage 4 task workspace and status management`. |
| 2026-10-09 | Stage 4 session regression corrected | A trace showed that background task requests can detect deactivation before the colleague clicks Refresh access. Updated the existing account browser scenario to reload and assert sign-in after deactivation/password reset; focused workflow passed. The prior full attempt passed 54 backend tests but its command client exited 143 while Chromium continued; its retained browser result identified only the account scenario as failed. Full acceptance remains pending. Commit: `test: handle prompt session revocation during task loading`. |
| 2026-10-09 | Stage 4 completed | Source `c2d5ca3` passed two sequential full test-script runs, each exiting 0 with 54 PostgreSQL tests, TypeScript/Vite build, 16 Chromium checks, and inspected cleanup. The first successful run reset healthy running services. Fresh/Stage 2/Stage 3 migrations, actual endpoint grant matrix, permanent status triggers, real time-reference deletion protection, five task races, and complete task UI workflows passed. Desktop/narrow screenshots inspected. Both original volumes and all five unrelated container IDs preserved; no test resources remain. Foreground timeout/closed-input execution verified; earlier failures retained in infrastructure notes. Configuration, shell syntax, local links/anchors, diff, and whitespace checked. Stage 4 Done; Stage 5 remains Not started. Commit: `docs: record Stage 4 completion and verification`. |
| 2026-10-09 | Timesheet editing and unfinished-day decisions agreed | Updated authoritative requirements, architecture, domain/API contracts and examples, testing charter, and Stage 5/6 plans for ordinary shared-boundary edits/last deletion, Edit day drafts with atomic validation/save, final-task historical selection, and independent new-day recording alongside unfinished historical sessions. Added the Friday-to-Monday example and planned migration away from Stage 4 global null-end uniqueness; superseded middle-edit proposals are identified and preserved in Git history. Documentation consistency, 57 local Markdown links/anchors, worked duration arithmetic, and whitespace checked. No code/schema/services changed; no application tests or migrations run. Stages 5 and 6 remain Not started. Commit: `docs: revise timesheet editing and unfinished-day rules`. |
| 2026-10-09 | Stage 5 completed | Engine `601ed20` and safe write-only error follow-up `2c12aa6`. Final source passed two sequential complete lifecycle runs (`stage5-verified2`, `stage5-verified3`): 82 PostgreSQL tests, TypeScript/Vite build and 16 Chromium checks each, exit 0. Six new races, lifecycle migration, rollback, Friday-to-Monday accounting and configurable UTC/Berlin allocation passed. Healthy-stack reset and scoped cleanup verified; all five unrelated container IDs and both original volumes preserved. Stage 5 Done; Stage 6 UI remains Not started. Commit: `docs: record Stage 5 completion and verification`. |

| 2026-10-11 | Stage 6 started; discovery endpoints verified | Reviewed clean source at `2ebd739` and Stage 5 contracts/history. Added label-only sheet directory and read-gated recording context; three focused PostgreSQL checks passed. UI and browser workflows in progress; full lifecycle acceptance pending. |
| 2026-10-11 | Stage 6 interface implemented | Added right-hand timesheet, task actions/drop/picker, ordinary previews, historical and overnight controls, native Edit day drafts with stable focus, atomic saves and explicit stale reload. Three API discovery checks and build pass. Component artifact records eight of nine new browser workflows passed; a competing-tab initialization race was fixed for final acceptance. Desktop/narrow/modal screenshots inspected; two full lifecycle runs pending. |
| 2026-10-11 | Stage 6 first lifecycle passed; review follow-up verified | `stage6-verified1` exited 0 on `820028b`: 85 PostgreSQL tests, build and 25 Chromium scenarios; healthy-stack reset and scoped cleanup passed. Follow-up safely handles missing write-only preview timelines and acknowledged saves with failed reloads; both focused Chromium regressions and production build passed. Repeat full lifecycle pending. |
| 2026-10-11 | Stage 6 completed | Interface `820028b` and final review source `daf9299` passed sequential full lifecycles (`stage6-verified1`, `stage6-verified2`), each exit 0 with 85 PostgreSQL tests, production build and 25 Chromium scenarios. Nine new workflows cover recording, Friday/current independence, drafts, previews, permissions, overnight boundaries, precision and reload recovery. Both healthy-stack resets and inspected cleanup passed; all original unrelated container IDs and volumes preserved. Stage 6 Done; Stage 7 reporting/CSV is next. |
| 2026-10-11 | Backup and administrator policies recorded | Agreed self-deactivation/demotion prohibition, permitted changes to other administrators, server-side password reset with explicit reactivation/admin-grant options, and replacement passwords without expiry or mandatory change. Recorded server-administrator backup responsibility for the PostgreSQL cluster, attachments, and necessary configuration, plus written full-system restoration instructions for another machine. Added future lifecycle/recovery/restoration checks; self-protection and server recovery remain unimplemented, and backup procedure work remains Stage 9. Documentation consistency, local links/anchors, and whitespace checked. No application code changed or application tests run; stage completion statuses and prior verification evidence preserved. Commit: `docs: record backup and administrator recovery policies`. |
| 2026-10-11 | Stage 7 backend implemented | `020cd88` adds shared report authorization, project/person-day/hierarchy APIs, label-only options, exact duration accounting, read-only repeatable-read snapshots, and spooled CSV downloads. Twelve focused PostgreSQL tests passed twice, including 64 access combinations and a concurrent move/revocation snapshot. No schema or dependency changes; full lifecycle acceptance pending. |
| 2026-10-11 | Stage 7 interface component-verified | Added report navigation/screens, filters, hierarchy totals, CSV downloads, and failure/stale/access-change handling. All five focused Chromium scenarios passed (`stage7-reports1`, exit 0); desktop/narrow screenshots inspected. First full attempt passed 97 PostgreSQL tests and build but had three wrapped-select test locator timeouts and was interrupted; corrected selectors use accessible combobox roles. Full final-source repetition remains pending; Stage 7 In progress. |
| 2026-10-12 | Stage 7 completed | Backend `020cd88`, interface `f4dfd00`, CSV negotiation `9ba2742`, and browser timing follow-up `7f7e583`. Two serial full lifecycles (`stage7-verified2`, `stage7-verified3`) each exited 0 with 97 PostgreSQL tests, production build, and 30 Chromium scenarios. Report authorization, exact totals, historical corrections, hierarchy/project moves, snapshot consistency, actual CSV downloads, and error/access recovery passed. Healthy-stack resets and scoped cleanup inspected; original unrelated containers and persistent volumes preserved. Documentation consistency, local links/anchors, and whitespace checked. Stage 7 Done; Stage 8 is next. |
| 2026-10-12 | Initial search languages agreed | Recorded English and Russian, including mixed-language content, in requirements, architecture, design, and testing charter. Concrete multilingual indexing/query configuration remains Stage 8 work, with centralized language handling for later additions. Documentation consistency, local links/anchors, and whitespace checked; no application code changed or application tests run. Stage 8 remains Not started. |
| 2026-10-12 | Stage 8 remarks milestone implemented | Chronological remarks, shared stars/navigation, edit/delete commands, independent permissions, safe write-only acknowledgements, and content-aware task-deletion previews. Corrected focused suite passed 29 PostgreSQL checks; all four new Chromium workflows passed and desktop/narrow screenshots were inspected. Full run passed 107 PostgreSQL checks and the final production build; full browser/lifecycle result and cleanup are pending. Fixed non-object JSON validation exposed by the new regression. Requirements, architecture, API/design, README, and testing charter aligned; 79 local links/anchors and whitespace checked. References, images, and English/Russian search remain next; Stage 8 In progress. Commit: `feat: add task remarks and shared stars`. |
| 2026-10-12 | Remarks browser fixtures isolated | Removed shared-administrator application grants from remarks fixtures; content operations use a separate scenario user's authenticated context. The first full attempt passed 107 PostgreSQL checks, build, and all four remarks workflows, but later task access failed due to fixture contamination; the attempt was interrupted and is not lifecycle acceptance. Artifacts retained and scoped cleanup inspected. Corrected repeat again passed 107 PostgreSQL checks, build, and all four remarks workflows; remaining browser/lifecycle verification pending. Final desktop/narrow screenshots inspected; local links/whitespace checked. Commit: `test: isolate remarks browser fixtures from administrator access`. |
| 2026-10-12 | Remarks regression verification recorded | Application `7d331c6` and fixtures `f4329c8` passed all 107 PostgreSQL checks, production build, and all 34 Chromium scenarios in serial `stage8-remarks-verified2`. The wrapper's 20-minute limit expired during final cleanup (124); this is not successful lifecycle acceptance. Independent inspection confirmed no test resources and preservation of all five original container IDs and both persistent volumes. Final desktop/narrow screenshots and log/status retained. Extended the full runner to 30 minutes and updated README; shell syntax, local links, consistency, and whitespace checked. No application rerun under the new deadline. Remarks milestone checks complete; references, images, English/Russian search, and full-stage lifecycle acceptance remain pending. Stage 8 In progress. |
