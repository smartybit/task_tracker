# Implementation Plan and Progress

This is the working implementation tracker. Product behavior is defined in
[requirements.md](requirements.md), technical decisions in
[architecture.md](architecture.md), and verification priorities in
[testing_charter.md](testing_charter.md). This plan defines sequencing and records
actual progress; it does not turn proposals into confirmed requirements.

## Current Position

- Last updated: 2026-10-08.
- Planning documents and the implementation roadmap are prepared.
- Stages 1 and 2 are complete: 2 of 9 implementation stages complete.
- Stage 2 now has Django/REST Framework, account/core migrations, a health API,
  a React/TypeScript/Vite shell, locked dependencies, and isolated test configuration.
  Task, permission, timesheet, reporting, and content workflows are not implemented.
- Full Stage 2 verification passed with explicit sandbox approvals: two sequential
  complete test runs, fresh development startup, real frontend/API/database checks,
  and development shutdown/restart with database identity and contents retained.
- Each test run passed 13 PostgreSQL backend tests, TypeScript/production build,
  and 3 Chromium checks. A further 3 Chromium checks passed against development.
  Scoped test cleanup was independently verified after each run.
- The test rerun left the running development database unchanged. Development
  containers/networks are stopped and removed; its database volume is retained.
  Unrelated containers and volumes are preserved.
- Pending handoff documentation was committed as `df58d99`; verification results
  are in the milestone titled `docs: complete Stage 2 lifecycle verification`.
- Stage 3 remains Not started. Stop here as requested; the next implementation
  session can begin Stage 3. See [README.md](README.md) for verified commands and
  [infrastructure notes](docs/infrastructure_notes.md#stage-2-verification-resumed-2026-10-08)
  for current results and historical access restrictions.

## Progress Overview

| Stage | Result | Status | Completion evidence |
| --- | --- | --- | --- |
| 1 | Data model and API operation design | Done | [Design and worked examples](docs/domain_design.md); documentation checks recorded below |
| 2 | Runnable application foundation | Done | Two full Compose test runs; fresh development startup, API/browser checks, restart persistence, and scoped cleanup verified |
| 3 | Accounts, organization/project setup, and permissions | Not started | — |
| 4 | Task management and task interface | Not started | — |
| 5 | Timesheet engine | Not started | — |
| 6 | Timesheet interface | Not started | — |
| 7 | Reporting and CSV export | Not started | — |
| 8 | Remarks, references, images, and search | Not started | — |
| 9 | Deployment preparation and release verification | Not started | — |

Statuses are Not started, In progress, Blocked, or Done. Mark a stage Done only
when its work and completion checks are satisfied. Record any blocker and the
specific action needed to resolve it; do not infer completion from elapsed effort.

## Shared Test Environment

Reuse the [planned test setup](architecture.md#reusable-test-setup-planned) rather
than creating unrelated environments for each stage. Its core is an isolated
application and PostgreSQL setup, disposable scenario data, temporary image
storage, and a real browser when needed. Stage 2 introduces the tooling and
verified commands; later stages extend the fixtures and checks. The descriptions
below are planned environments, not evidence of tests already executed.

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

Only account/core backend modules are introduced so far; remaining feature modules
will grow in their respective stages. Temporary uploads, guarded test seed/reset,
readiness checks, browser failure artifacts, and the versioned health API provide
the shared foundation. Later-stage fixtures and workflows remain unimplemented.
Stage 3 has not started.

## Stage 3: Accounts and Permissions

- [ ] Implement email/password sign-in and sign-out, first-administrator setup,
  administrator-created accounts, and the selected password reset workflow.
- [ ] Implement organization/project setup and grant configuration, with the
  management interface required to exercise them.
- [ ] Implement shared access checks and authorized queries for task/remark grants
  and organization inheritance, keeping read and write independently meaningful.
- [ ] Implement unconditional access to one's own timesheet and global Read Others'
  Timesheets / Write Others' Timesheets flags.
- [ ] Add login and management screens. Ensure administrator privileges do not
  implicitly bypass application-data permissions.
- [ ] Add API checks for grant combinations, inheritance, direct unauthorized
  requests, and permission changes during an active session.

Test environment: reuse Stage 2 with seeded users, administrators, organizations,
projects, and grant combinations. API checks exercise the authorization matrix;
separate browser sessions exercise login and permission management without sharing
authentication state.

Completion check: users can sign in and administrators can configure accounts and
grants. Access tests demonstrate both allowed operations and denied operations,
including write-without-read cases and the own-timesheet exception.

## Stage 4: Tasks and Their Interface

- [ ] Implement task creation/editing, owners, project membership, hierarchy,
  configured statuses, and status-change history.
- [ ] Enforce one project per hierarchy, cycle prevention, owner eligibility,
  final-state rules, ancestor reopening, and immutability of used statuses.
- [ ] Implement deletion eligibility checks. Introduce supporting time-record
  models as needed to verify the restriction even before time recording is usable.
- [ ] Build flat/tree task lists, project and multiple-status filters, and the
  task description window.
- [ ] Verify hierarchy/project changes and ownership after access loss. Exercise
  concurrent task operations where they can invalidate the business rules.

Test environment: extend the shared fixtures with deep task trees, used/unused
statuses, differing owners, and referenced time records. Use API and browser checks
for task workflows and independent PostgreSQL connections for hierarchy races.

Completion check: permitted users manage tasks through the interface, forbidden
operations are rejected by the API, and task/history invariants remain valid.

## Stage 5: Timesheet Engine

- [ ] Implement task starts/switches, breaks, end-of-day markers, and personal or
  permitted other-user timesheet operations.
- [ ] Implement historical insertion, shared-boundary edits, deletion, and the
  selected neighboring-entry adjustment rules behind isolated backend operations.
- [ ] Preserve zero reported duration for running entries until explicit closure.
- [ ] Implement closed-entry midnight splitting in the configured shared zone.
- [ ] Apply multi-record changes in transactions with protection against competing
  edits, including operations across days and different task projects.
- [ ] Verify continuity, overlap rejection, end-of-day resumption, invalid changes,
  rollback, and concurrent requests using independent PostgreSQL connections.

Test environment: real PostgreSQL transactions with controlled clocks and an
explicit test zone, known multi-day timelines, and independently calculated
durations. Coordinate competing requests through independent connections and
verify committed state and rollback, not just individual response codes.

Completion check: reproducible timeline examples produce correct stored intervals
and durations; successful, failed, and competing operations preserve integrity.
The deployment working time zone must be selected for final time-behavior acceptance.

## Stage 6: Timesheet Interface

- [ ] Build the right-hand Task / Start Time / End Time table and Day selector.
- [ ] Add task drag-and-drop, task switching, break and end-of-day actions.
- [ ] Add historical insertion, manual boundary editing, deletion, and previews
  of affected entries with clear validation feedback.
- [ ] Support viewing/editing other users' timesheets according to the global flags,
  while keeping restricted task details protected.
- [ ] Add browser workflow checks for recording work and correcting past work.
  Explore competing tabs and recovery after a failed request.

Test environment: real automated browsers against the shared frontend/API and
reset test database. Use independent sessions or tabs, controlled timestamps, and
seeded cross-project timesheets to exercise edits, permission boundaries, and
failed-request recovery.

Completion check: users can complete the task-to-timesheet workflow through the
browser, including historical corrections. This is the first useful work-tracking
milestone; the remaining first-version features are still outstanding.

## Stage 7: Reporting and CSV Export

- [ ] Implement a shared query restricted to readable projects and permitted
  timesheet users before aggregating or exporting records.
- [ ] Implement project summaries, person/day summaries, and task hierarchy reports,
  with person/date filters and separate direct/descendant hours.
- [ ] Calculate decimal hours from original durations, count open entries as zero,
  and reflect current task projects and parent relationships.
- [ ] Build report screens and export individual authorized task records for a
  selected period with the agreed CSV columns. Exclude special entries and do not
  apply interactive report filters to the dump.
- [ ] Reconcile results against independently calculated examples, including
  historical edits, project moves, rounding, midnight work, and access changes.

Test environment: seed small datasets with independently known project/person/day
and direct/descendant totals. Compare API and browser results with those values;
parse actual CSV downloads and check individual records, permissions, quoting, and
rounding before and after edits or moves.

Completion check: browser reports and CSV satisfy their respective access rules
and agree with source records. The task-to-timesheet-to-report workflow is usable.

## Stage 8: Remarks, References, Images, and Search

- [ ] Implement chronological remarks with authors/timestamps, shared stars at
  the top of the task window, and navigation to original remarks.
- [ ] Implement task/remark cross-references with stable targets and appropriate
  handling of restricted or deleted objects.
- [ ] Implement images in descriptions and remarks, validated formats/size limits,
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

## Stage 9: Deployment and Release Verification

- [ ] Select and configure the application server, reverse proxy, production
  frontend assets, and deployment settings for the VDS.
- [ ] Persist PostgreSQL data and images across application restarts/replacements.
- [ ] Document initial setup, account bootstrap, migrations, startup, and updates.
- [ ] Resolve backup ownership and recovery expectations; document and exercise
  the agreed backup/restore procedure for both database data and image files.
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

- Select the shared working time zone or fixed offset before finalizing Stage 5
  behavior; use an explicitly controlled test zone while that decision is pending.
- Resolve backup responsibility and recovery expectations before production use
  in Stage 9. This does not block earlier implementation stages.
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

| Date | Milestone | Evidence and next action |
| --- | --- | --- |
| 2026-10-08 | Planning baseline prepared | Requirements, architecture, testing charter, and agent/Git guidance are recorded through `cba1d65`. |
| 2026-10-08 | Implementation tracker created | Reviewed against project documents; local links and whitespace checked. No application tests exist or were run. Included in the commit titled `docs: add implementation plan and progress tracker`. Next: Stage 1; all implementation stages remain unstarted. |
| 2026-10-08 | Reusable test setup documented | Architecture defines shared services, isolation, fixtures, execution lifecycle, and evidence; all nine stages identify their test environment. Documentation consistency, local links, and whitespace checked in the commit titled `docs: describe reusable test setup across implementation stages`. No runtime or application tests implemented or run; next action remains Stage 1. |
| 2026-10-08 | Search infrastructure direction recorded | Architecture and Stage 8 specify PostgreSQL-backed search through Django, without a separate search service for v1. Diff, local link/heading, and whitespace checked; no application tests run. Commit: `docs: record PostgreSQL search approach`. Next: Stage 1. |
| 2026-10-08 | Stage 1 design completed | Domain records, API/access/error contracts, timeline commands, locking, and worked acceptance examples reviewed against requirements and charter; 26 Markdown links/anchors and whitespace checked. No application/database/browser tests run. Environment probe: Python 3.13.5 and Compose v5.5.1 available; initial Docker version denied, approved Docker info succeeded (29.8.0); host Node/npm absent. Commit: `docs: complete initial domain and API design`. Next: Stage 2 and container execution checks. |
| 2026-10-08 | Stage 2 foundation implemented and component-verified | Built Django/React images; PostgreSQL 17.11 migrations and migration-drift/system checks passed; 13 backend tests passed; TypeScript and Vite production build passed; 3 Playwright 1.64.0 checks passed against real API/database services, including the internal Compose hostname. Backend checks/seed entry point exercised, Compose files validated, shell syntax/local links/whitespace checked. Commands/environment documented in README. Compose startup was denied by session Docker socket permissions, so full orchestration/reset/cleanup script is not claimed verified and Stage 2 remains In progress. Commit: `feat: scaffold Dockerized Django and React foundation`. Next: verify Compose workflows and finish Stage 2 before accounts/permissions implementation. |
| 2026-10-08 | Infrastructure discoveries preserved | Added troubleshooting notes linked from AGENTS and README; recorded user-confirmed cleanup without claiming independent inspection or restored permissions. Documentation checked against existing code and prior results; local links/anchors and whitespace checked. No runtime tests rerun. Commit: `docs: preserve infrastructure discoveries for future agents`. Next: complete Stage 2 Compose verification. |
| 2026-10-08 | Stage 2 completion attempt blocked | Docker info succeeded (29.8.0); standalone development `docker compose ps` showed no containers. Test Compose startup was denied. `sh scripts/test.sh` failed at its initial test-project reset and its cleanup trap with Docker socket permission denied; no application checks ran or new containers started. Recorded the evidence and blocker; documentation consistency/links/whitespace checked. Commit: `docs: record Stage 2 verification access blocker`. Next: authorized Compose lifecycle access or user-run verification; Stage 2 is not complete. |
| 2026-10-08 | Stage 2 lifecycle verification completed | Pending handoff reviewed/committed as `df58d99`. Two full test-script runs passed (13 PostgreSQL tests, build, 3 Chromium checks each), with no test resources left. Fresh development startup/migrations, 3 development Chromium checks, proxy connectivity, isolation, and restart persistence passed; final cleanup retains development data and unrelated resources. Docker/Git/host-loopback access used explicit sandbox approvals. Documentation links/anchors, configuration, shell syntax, diff, and whitespace checked. Commit: `docs: complete Stage 2 lifecycle verification`. Stage 2 Done; stop before Stage 3 as requested. |
