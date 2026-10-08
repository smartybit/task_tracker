# Task Tracking Tool: Architecture

This document records selected technologies and implementation proposals.
[requirements.md](requirements.md) defines product behavior and business rules;
[testing_charter.md](testing_charter.md) defines verification priorities.
Proposals below preserve the approaches discussed so far and remain revisable.

## Stage 1 Implementation Design

[Domain model and API design](docs/domain_design.md) specifies records, access
gates, operation contracts, transaction boundaries, and worked acceptance examples.
It selects initial approaches for delegated behavior without changing the agreed
product rules. Later sections retain the broader architecture context.

Initially, business mutations use a persistent database coordination lock, with
per-user timesheet locking inside that transaction. This conservative small-team
approach serializes writes to protect hierarchy, catalog, permission, and timesheet
changes together. Finer-grained concurrency is a later optimization requiring
measurements and equivalent PostgreSQL integrity tests.

## Accepted Decisions

- Backend: Python 3.13, Django 5.2 LTS, and Django REST Framework.
- Web frontend: React, TypeScript, and Vite.
- PostgreSQL is the only database engine, used for development, testing, and
  deployment. Cross-engine portability and migration are outside the scope.
- The first frontend is a web application. The architecture must allow additional
  frontends to use the same backend later.
- Permission checks, business rules, and report calculations are owned by the
  backend API so every client receives the same behavior.
- The deployment target is the current VDS where development is taking place.

## Proposed Application Structure

- Use one backend application with modules for accounts, access control,
  organizations/projects, tasks, remarks/images, timesheets, and reporting.
- Keep business operations in shared backend services so API endpoints, management
  screens, and future clients enforce consistent rules.
- Expose a versioned REST API with explicit request/response contracts. Keep API
  types and reusable client utilities separate from browser-specific components.
- Serve the React application as static assets and use the Django API for data.
- Use session authentication for the web application with the corresponding
  request protections. Select a native-client authentication mechanism when a
  mobile app is scoped; mobile requests must use the same authorization rules.
- Implement the application's administrator role with explicit data grants in
  every interface, including management screens. Catalog/account administration
  must not accidentally grant unrestricted access to tasks or time records.

## Stage 3 Implementation Decisions

Stage 2 already supplies the UUID email user model, session middleware, PostgreSQL
migrations, domain coordination row, versioned health API, and verified Compose
lifecycle. Extend these components with new migrations and feature modules.
The implementation retains the existing user model and adds new migrations.
The decisions below implement the reviewed Stage 3 proposals; the requirements
and Stage 1 authorization contracts remain authoritative. Runtime verification
results are recorded in the implementation tracker.

- Add `projects` and `access` modules and a minimal `timesheets.Timesheet` model
  containing the unique user relationship and revision. Backfill existing users
  and create the row in the same transaction as subsequent accounts. The time
  engine and commands remain Stage 5 work; Stage 4 may introduce the minimal
  time-record relationships needed to enforce task deletion protection. Keep
  account/catalog/grant mutations behind shared services using the existing
  MutationLock before checking mutable administrator permissions or references;
  login/session storage is excluded.
- Provide a local interactive first-administrator command that validates/hashes
  the password and atomically creates the account and timesheet only if no
  application administrator exists. Serialize competing bootstrap attempts through
  MutationLock. Do not create default accounts or passwords on service startup.
  Ordinary account creation goes through administrator-only services/API screens.
  The generic `createsuperuser` and `changepassword` commands direct operators to
  these paths; the accounts app precedes Django auth for command registration.
- Use administrator-entered new passwords for the Stage 1 password-reset action,
  with Django password validation/hashing and no email delivery. Verify that old
  passwords and existing sessions stop authenticating after reset, and inactive
  accounts cannot continue through existing sessions. No temporary-password or
  forced-change workflow is introduced. A private `session_version` is included
  in Django session hashes and incremented on deactivation, so reactivation does
  not revive old sessions. Password hashes continue to invalidate reset sessions.
- Implement CSRF bootstrap/login/logout/current-identity endpoints and a shared
  browser API client for cookies, CSRF headers, and refreshed tokens after login.
  Explicitly protect login itself. Keep JSON errors consistent with Stage 1 and
  distinguish authentication, permission, validation, and CSRF failures without
  exposing account existence or protected data.
- Configure exact trusted frontend origins for each environment and test unsafe
  requests through Vite's actual proxy. The current Chromium suite uses
  `http://frontend:5173`; test CSRF configuration must cover that origin, while
  development covers its documented loopback browser origins. Keep host checking
  and CSRF validation enabled. Stage 2's GET-only health checks did not verify this.
- Keep effective grants in shared checks/selectors rather than session state.
  Combine organization/project flags with OR independently for each operation;
  remarks also require task read. Catalog choices must support authorized
  write-only operations without returning protected content. Verify timesheet
  self/others checks at service level now, then enforce and repeat those checks
  against real endpoints as Stages 4–8 implement them.
- Extend the existing guarded seed command and sequential test entry point.
  Browser cases that reset passwords or change grants need independently reset
  fixtures and separate session contexts. Preserve foundation health/proxy checks,
  database/upload isolation, failure artifacts, and test-owned cleanup. Verify
  upgrades from the Stage 2 schema with synthetic users in an isolated database.
  Lists use stable ordering and 50-item pages; grant configuration returns local
  and effective flags for the selected account. Zero flags replace a local grant
  without denying inherited access. Browser mutation scenarios create independent
  accounts and never change the shared fixture administrator credentials.

Later domain mutations must reuse these services and coordination rules. Low-level
model managers are persistence helpers, not authorized administration entry points.
Recheck the current actor, grants, object state, and expected revisions after
acquiring the domain lock. Stage 3 policy-helper coverage does not demonstrate
authorization or safe serialization through task, time, or reporting endpoints.

## Proposed Data and Transaction Approach

- Model organizations, projects, tasks, statuses, users, access grants, remarks,
  images, and timesheet entries as related records with stable identifiers.
- Represent the task hierarchy with parent relationships. Enforce common-project
  and acyclic-hierarchy rules through the business operations that change the tree.
- Keep a status's first-use marker so immutability does not depend on whether
  any task still references it. Record task status changes while the task exists.
- Persist a running entry's start timestamp with an unset end timestamp. Compute
  its report duration as zero; closing the entry establishes its duration.
- Represent time intervals as start-inclusive and end-exclusive. Chronological
  segments are bounded by neighboring start times and an optional closing boundary.
  Split closed overnight work at exactly midnight in the configured working zone.
- Use database transactions for timesheet neighbor adjustments, ancestor reopening,
  hierarchy/project changes, and deletion checks. Complete each operation together
  or roll it back completely.
- Serialize competing edits to a user's timesheet by locking a persistent
  per-user timesheet record for the transaction. Protect hierarchy and deletion
  operations against concurrent changes with suitable locking and constraints.
- Treat source timestamps and current task relationships as authoritative. Derive
  totals from them rather than maintaining independent totals that can become stale.

## Proposed Reporting Implementation

- Build a shared authorized-record query that restricts projects and timesheet
  users according to the reporting rules in the requirements. Apply access
  restrictions before aggregation and consistently reuse them for CSV export.
- Calculate durations from closed entries, treating open entries as zero and
  excluding taskless entries from work reports and CSV.
- Use database aggregation for project and person/day summaries and direct hours
  per task. Compute descendant rollups from the task tree and direct totals in a
  batch, avoiding a separate database request for every node.
- Resolve project attribution through each task's current project and rollups
  through its current ancestors. Historical edits and moves affect later queries.
- Calculate reports on request initially. Add caching or precomputed summaries
  only if measured performance requires them and invalidation rules are defined.
- Sum original durations before converting to decimal hours and rounding output.
- Return structured report data to the frontend. Stream individual authorized
  records to CSV for the selected period, independently of interactive filters.
- Verify report results against independently calculated examples and exercise
  permission boundaries and concurrent mutations using PostgreSQL.

## Planned Search Approach

PostgreSQL is expected to do the heavy lifting for search, using its built-in
full-text search and database indexes through Django. No separate search service
is planned for the first version. The backend enforces task and remark permissions
for search results and snippets.

## Proposed Images and Content Handling

- Store image files in a persistent local volume, with metadata and ownership
  relationships in PostgreSQL. Images belong to descriptions or remarks, as
  specified in the requirements.
- Validate the actual image format and the selected upload size limit.
- Serve downloads through permission-checked endpoints, applying the containing
  task/remark's current permissions rather than exposing a public upload directory.
- Use stable identifiers for cross-references and resolve visibility on access.
  Keep file cleanup consistent with deletion of an eligible containing object.

## Proposed Deployment and Operations

- Use Docker Compose for reproducible development and VDS deployment.
- Keep runtime services to the backend, PostgreSQL, and a reverse proxy serving
  frontend assets and forwarding API requests. Select the application server and
  reverse proxy during deployment design.
- Build frontend assets in a build stage. Node.js is needed for frontend builds;
  the deployed browser application is served as static files.
- Persist database data and image files outside disposable application containers.
- Provide a local setup command to create the first administrator; account
  creation and password reset then follow the agreed administrator workflows.
- Define schema migration, startup, backup, and recovery procedures as deployment
  work progresses. Backup scope must account for both database data and image files.

## Reusable Test Setup

The shared environment was introduced in Stage 2 of the
[implementation plan](implementation_plan.md#stage-2-application-foundation) and
extended in Stage 3 with authenticated API/browser workflows, migration upgrades,
and independent-connection concurrency checks. Development Compose startup,
frontend-to-API connectivity, repeatable tests, and scoped cleanup were verified
on 2026-10-08. See [README.md](README.md) for commands and the tracker for exact
results. Extend the same harness and fixtures as features arrive; the later
feature scenarios below remain planned. The [testing charter](testing_charter.md)
defines the scenarios and acceptance priorities.

### Services and Isolation

- Use a separate Docker Compose test project or equivalent explicit test
  configuration for the backend, PostgreSQL, and frontend build/runtime when
  browser checks need it. Reuse application code and locked dependencies; match
  the PostgreSQL major version intended for deployment.
- Give tests dedicated configuration, credentials, database/storage names, and
  host ports when exposed. Test startup, reset, and cleanup must target only this
  environment, never development or production data on the shared VDS.
- Run backend checks against disposable PostgreSQL databases created through
  application migrations. Give browser scenarios a separately reset application
  database; independent suites must not share mutable state accidentally.
- Use temporary upload directories or dedicated test volumes with synthetic
  images. Remove only test-owned files during cleanup, not real attachments.
- Reuse built images where practical, but reset mutable data between runs. Keep
  release-verification databases, volumes, and credentials isolated too.

### Test Layers

- Combine focused business-rule tests with API/database integration tests using
  real PostgreSQL rather than substituting another database engine.
- Exercise concurrency with real commits and independent database connections,
  explicit synchronization, and bounded timeouts. Tests wrapped in one shared
  rollback transaction do not demonstrate locking or competing-request behavior.
- Run browser workflows against the real frontend, backend, and test database.
  Use separate authenticated browser contexts for different users or clients.
- Check TypeScript and the production frontend build; add focused component tests
  where useful. Mock-based UI checks do not replace end-to-end integration checks.
- Extend the environment in Stage 9 with production assets, the selected server
  and reverse proxy, and persistent test volumes for restart, migration, and
  agreed backup/restore checks. Never restore test backups into live storage.

### Shared Data and Deterministic Results

- Provide reusable builders and a documented seed/reset workflow for synthetic
  users and administrators, two organizations, several projects, grant combinations,
  and task trees at least three levels deep. Extend fixtures only as their models
  and features become available.
- Add multi-day timelines with closed/open entries, breaks, closing markers, and
  midnight work. Keep small independently calculated totals and expected CSV
  records, including rounding cases, rather than deriving expectations from the
  report implementation itself.
- Control the backend clock and use an explicit shared test zone. Until the
  deployment zone is selected, use a documented fixed test zone; then include the
  selected deployment configuration in acceptance checks. Use controlled browser
  time or explicit historical timestamps where a workflow depends on the clock.
- Reset scenario data independently so tests do not rely on execution order.
  Include valid, invalid, and size-boundary image samples when images are added.
- Retain the isolated Stage 2-to-Stage 3 upgrade regression and add upgrades from
  the latest completed schema as new models arrive. Use synthetic existing users,
  grants, and timesheet rows; never exercise upgrades against development volumes.

### Setup, Execution, and Evidence

- Initial tooling is Django's built-in test runner, TypeScript/build checks, and
  Playwright 1.64.0 with Chromium smoke tests. Component-specific tooling and broader
  browser coverage remain deferred until needed; Chromium is the current test
  target, not a claim of cross-browser acceptance.
- Add verified repository entry points for building/starting services, migrations,
  seeding/resetting test data, running each test layer, and cleaning up test-owned
  resources. Document exact commands once implemented and successfully exercised;
  do not present proposed commands as working instructions.
- Wait for database and application readiness before checks. Start with documented
  sequential execution; require separate databases and storage before enabling
  parallel suites.
- Record the tested revision, exact commands, relevant configuration, results, and
  known limitations. Retain useful failure logs and browser traces/screenshots as
  generated artifacts outside tracked source, and summarize actual checks in the
  implementation tracker. Do not include credentials in logs or reports.
- Make the same entry points reusable locally and by future CI. CI integration is
  not required by this documentation update. For later stage completion, run the
  expanded suite sequentially twice, including reset of running test services,
  and inspect cleanup while preserving development and unrelated resources.

## Future Android Frontend Options

No Android implementation has been selected or included in the first version.

- Make the initial web interface responsive and usable with touch input.
- Capacitor could package the web frontend as an Android application, reusing
  most browser UI code while adding native integrations where needed.
- React Native could provide a dedicated mobile interface using the same API,
  TypeScript data contracts, and suitable client utilities. Its native screen
  components would be built separately from the browser components.
- Choose between these options when Android workflows and native integrations
  are known. Offline editing would require additional synchronization and conflict
  rules; it is not an assumed capability of either approach.

## Open Technical and Operational Decisions

1. Who handles VDS backups, and what recovery procedure is expected?
2. Select the application server, reverse proxy, and any supplementary frontend
   libraries during implementation; these were not fixed by the stack decision.
3. Choose the deployment working time zone or fixed UTC offset, as identified
   in the requirements. Daylight-saving behavior remains outside product scope.
4. Define administrator recovery alongside the last-active-administrator product
   decision. Current account updates can remove the last active administrator;
   bootstrap rejects any existing administrator, including an inactive one.
   This code-review finding was not covered by Stage 3 verification. Neither a
   last-administrator guard nor a supported recovery command is implemented.
