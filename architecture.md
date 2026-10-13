# Task Tracking Tool: Architecture

This document records selected technologies and implementation proposals.
[requirements.md](requirements.md) defines product behavior and business rules;
[testing_charter.md](testing_charter.md) defines verification priorities.
Proposals below preserve the approaches discussed so far and remain revisable.

## Stage 1 Implementation Design

[Domain model and API design](docs/domain_design.md) specifies records, access
gates, operation contracts, transaction boundaries, and worked acceptance examples.
It selects initial approaches for delegated behavior without changing the agreed
product rules. The timesheet design was revised on 2026-10-09 to reflect the agreed
Edit day and unfinished-day workflows. Stage 5 implements their backend engine;
Stage 6 implements the interface and has passed full lifecycle acceptance.
Later sections retain the broader architecture context.

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

### Agreed Administrator Lifecycle Follow-up

The [administrator policy](requirements.md#users-and-authentication) is agreed but
requires a focused implementation follow-up in Stage 9. Reject self-deactivation
and self-demotion in the account service; permit changes to another administrator's
active status or administrator privileges. Reuse MutationLock and recheck the
actor's current privileges after acquiring it for competing account updates.

Provide a server-side password-reset command for any existing user, with explicit
options to reactivate the user and grant administrator privileges for recovery.
Without those options, preserve both statuses. Reuse Django password validation,
hashing, and existing session invalidation, and apply requested account changes
atomically through the account services. Replacement passwords have no expiry or
mandatory-change workflow. The command must work when no active administrator can
sign in; first-administrator bootstrap remains a separate setup operation.

Current account updates allow self-deactivation/demotion and can remove the last
active administrator. Bootstrap rejects any existing administrator, including an
inactive one. Self-protection and the server-side reset/recovery command are not
implemented or covered by Stage 3's completion evidence; browser password reset
and session invalidation are already implemented.

## Stage 4 Implementation Decisions

- Task/status services reuse the domain coordination row, current-grant policies,
  strict input validation, and session/CSRF client. Descriptive edits and ownership
  transfers require the task revision. Creation, status changes, moves, and deletion
  use separate preview endpoints and require explicit confirmation with the preview's
  domain revision; existing tasks additionally require their task revision.
- Previews hold the same coordination lock but perform no writes or revision bumps.
  Confirmation rechecks permissions, owners, hierarchy, and revisions under that
  lock. Preview rows require read access in both the existing and proposed project;
  write-only callers receive acknowledgements without protected content. Successful
  writes serialize according to the destination's current read permission.
- Store parent pointers and derive subtree/ancestor changes in the service. Explicit
  project moves change the whole moved subtree and validate every affected owner's
  destination write access. Adding/moving a non-final task or reopening a descendant
  requires a selected non-final status for every affected final ancestor. All status
  changes, including creation and propagated reopening, create history rows atomically.
- Seed the five initial statuses with additive migrations. PostgreSQL triggers mark
  first use on task insertion/status assignment and reject subsequent status changes
  or deletion, including attempts to clear the permanent marker. Protected foreign
  keys block catalog, child-task, and time-record deletion paths.
- Introduce WorkSession/TimeEntry persistence relationships and basic kind/duration/
  running-row constraints solely to exercise deletion protection with real records.
  There are no recording services or endpoints in Stage 4. Session agreement,
  overlap/continuity enforcement, and recording/correction commands remain Stage 5.
- Expose an assignment directory only to project task writers, containing eligible
  active users' IDs and display names. It exposes no account-management fields or
  email addresses. Status catalogs are readable by signed-in users; configuration
  remains administrator-only.
- The task workspace loads all authorized pages, applies project/multiple-status
  filters, and builds flat/tree views from parent IDs. A filtered-out parent makes
  its matching descendant a displayed root, so the filter never hides matching work.
  The API also supports project/repeated-status filters and stable 50-item pages;
  both flat and tree results carry parent IDs. No report totals are introduced.
- The description panel includes status history and separate edit/owner/status/move/
  deletion controls. Compound changes display a cancellable confirmation panel.
  Stale revisions/previews refresh current state and require a new review; failed
  transient requests preserve input for retry. Administrators use the Tasks and
  Statuses tabs alongside the existing management screens.

## Stage 5 Engine and Stage 6 Interface

The [agreed editing rules](requirements.md#timesheet-editing) and
[unfinished-day behavior](requirements.md#unfinished-days-and-overnight-work)
replace automatic middle insertion/deletion and the original single-open-entry
design. Stage 5 owns backend implementation; Stage 6 owns the interface.

- Represent session lifecycle explicitly as active, unfinished, or closed. An
  unfinished historical tail has no known end and zero duration, while a separate
  current session can record work. Permit one active session per timesheet and
  one open tail per session; do not infer an end to satisfy uniqueness.
- Additive migrations replace Stage 4’s global null-end constraints with one
  active session per timesheet, one open tail per session, and a lifecycle/end
  check. Existing closed sessions are backfilled as closed, open sessions remain
  active, and entry IDs/timestamps and sheet revisions are preserved. PostgreSQL
  `btree_gist` supports a known-interval exclusion constraint; null ends are
  excluded from its range expression. Triggers enforce entry/session sheet agreement.
- New-day starts leave an earlier session unfinished by default. Explicit
  continuation supports genuine overnight work. Session-targeted append/close
  commands use historical timestamps without changing today's active session.
- Ordinary corrections retain shared-boundary edits and last-row deletion with
  preview/confirmation. Middle corrections use one `replace_day` command carrying
  the date, complete draft rows/session markers, and expected timesheet revision.
- Stage 6 keeps drafts in React memory. Native modal dialogs provide keyboard
  containment and Escape handling; changed drafts require dismissal confirmation
  and register a before-unload warning. A shared table and searchable task picker
  serve the panel, previews and editor. Draft gaps/overlaps are highlighted locally;
  backend validation remains authoritative. Sort on blur with stable local keys and
  restore the next keyboard target after DOM movement. Local draft keys work over
  plain HTTP without relying on secure-context browser APIs.
- datetime-local fields represent the backend's shared zone, using Intl zone parts
  to convert wall time to absolute timestamps independently of the browser zone.
  Unchanged draft timestamps retain their original precision. The backend supplies
  today's shared-zone date and unfinished tails through a read-gated context
  endpoint. A paginated label-only timesheet directory includes colleagues only
  with either global others-timesheet flag; it does not expose account email,
  administration or permission fields.
- The task workspace and timesheet share record/open-task actions. Drag/drop starts
  current work immediately and asks for a selected-day time on historical days.
  Recording commands, boundary/deletion/resumption previews and complete drafts use
  the existing Stage 5 engine. Sheet/domain revisions reject stale commands; draft
  saves retain input and disable retries until explicit reload/discard and review.
  Mutation buttons use an immediate in-flight ref as well as disabled controls.
  A preview may omit timelines after read revocation while write remains; detect
  that safe response before rendering and require refreshed access. A confirmed
  save followed by a failed GET is reported as saved with reload failure, disables
  resubmission, and preserves the local copy until reload/review. Do not imply that
  an acknowledged write was rolled back because its subsequent read failed.
- Read-only colleague sheets omit edits. The browser day editor requires read plus
  write for colleagues; unusual write-only access remains available through the
  existing safe revision-aware API. Task labels in readable sheets are permitted;
  task descriptions open through the separately authorized task endpoint.
- Saving locks the domain coordination row followed by the target Timesheet row,
  rechecks current grants and revisions, validates the resulting timeline and
  adjacent-day boundaries, then applies all changes and increments the revision.
  Preserve retained entry identifiers; never replace another day's independent work.
- A one-day replacement preserves fixed midnight connections and may retain a
  valid unfinished tail. Closing real overnight work still normalizes its closed
  spans across midnight; no synthetic stop is created merely by changing dates.
- Database overlap protection must apply to known intervals without treating an
  unfinished historical tail as an infinite reservation. Validate its actual span
  against later sessions when it is closed. Keep PostgreSQL overlap backstops and
  service continuity checks consistent with this distinction.
- Rejected saves leave records/revisions unchanged and return row-associated
  validation errors. Stale saves retain the client draft and require reload/review;
  do not merge or replay it automatically. Cancel has no backend mutation.

- The shared zone is configured through `WORKING_TIME_ZONE` in `.env`/the
  backend environment; UTC is the default. Restart the backend after changing it.
  Known spans are normalized for reads as well as writes, so a configuration
  change or an older unsplit span still produces correct daily allocation.
  Virtual split IDs are deterministic for stable drafts; GET never writes them.
  Accepted commands persist normalized spans in the same transaction. UTC and
  Europe/Berlin acceptance uses controlled clocks outside DST transitions.
- Command inputs, preview confirmation, editable day payloads, and safe read/write
  responses are documented in [the timesheet API](docs/timesheet_api.md).
  Only changed/new entries are rewritten; retained IDs survive accepted corrections.
  Reads and previews coordinate with domain writers to give coherent responses.

## Proposed Data and Transaction Approach

- Model organizations, projects, tasks, statuses, users, access grants, remarks,
  images, and timesheet entries as related records with stable identifiers.
- Represent the task hierarchy with parent relationships. Enforce common-project
  and acyclic-hierarchy rules through the business operations that change the tree.
- Keep a status's first-use marker so immutability does not depend on whether
  any task still references it. Record task status changes while the task exists.
- Persist an active or historical unfinished entry's start with an unset end.
  Its duration is zero until explicit closure establishes the actual interval;
  session lifecycle distinguishes it from today's recording.
- Represent time intervals as start-inclusive and end-exclusive. Chronological
  segments are bounded by neighboring start times and an optional closing boundary.
  Split closed overnight work at exactly midnight in the configured working zone.
- Use database transactions for timesheet boundary edits and whole-day saves,
  ancestor reopening, hierarchy/project changes, and deletion checks. Complete
  each operation together or roll it back completely.
- Serialize competing edits to a user's timesheet by locking a persistent
  per-user timesheet record for the transaction. Protect hierarchy and deletion
  operations against concurrent changes with suitable locking and constraints.
- Treat source timestamps and current task relationships as authoritative. Derive
  totals from them rather than maintaining independent totals that can become stale.

## Stage 7 Reporting Implementation

- Build a shared authorized-record query that restricts projects and timesheet
  users according to the reporting rules in the requirements. Apply access
  restrictions before aggregation and consistently reuse them for CSV export.
- Calculate durations from closed entries, treating open entries as zero and
  excluding taskless entries from work reports and CSV.
- Filter task records in PostgreSQL, then split closed spans at configured-zone
  midnight boundaries and sum integer microseconds in the backend. This replaces
  the initial database-aggregation proposal so legacy unsplit spans and zone
  changes use the same allocation rules as timesheets. Round decimal hours to
  two places with half-up rounding only at output. Compute descendant rollups
  from the task tree and direct totals in a batch without queries per node.
- Resolve project attribution through each task's current project and rollups
  through its current ancestors. Historical edits and moves affect later queries.
- Calculate reports on request initially. Add caching or precomputed summaries
  only if measured performance requires them and invalidation rules are defined.
- Sum original durations before converting to decimal hours and rounding output.
- Use a read-only PostgreSQL repeatable-read transaction for each report, options
  response, or CSV generation, including fresh account/grant checks, current task
  relationships, and records. Materialize JSON inside the snapshot. Generate CSV
  with a batched iterator into a temporary spool (disk after 1 MiB), close the
  transaction, then stream the file; a slow download never holds a snapshot open.
- Return structured report data to the frontend and individual authorized records
  to CSV for the selected period, independently of interactive filters. Report
  queries initially materialize selected records and the readable task tree in
  memory, appropriate to the personal/small-team scope; optimize if measured load
  warrants it. Report options expose labels only, including other people only if
  their task records are within the viewer's readable projects and the viewer has
  Read Others' Timesheets. Do not expose account-administration fields or emails.
- The concrete routes, filters, rounding, zone allocation, and CSV contract are
  documented in [the reporting API](docs/reporting_api.md). No schema changes or
  additional runtime libraries are required. Backend and browser acceptance passed
  two full lifecycle runs; execution evidence is recorded in the tracker.
- Verify report results against independently calculated examples and exercise
  permission boundaries and concurrent mutations using PostgreSQL.

## Stage 8 Remarks Milestone

Remarks use the `remarks` app and a UUID model with a containing task, protected
author, plain-text body, shared star, original creation time, optional edit time,
and independent revision. A `(task, created_at, id)` index supports stable
chronological pagination. The React task window loads the conversation and shows
its shared stars separately, with links that focus the original remarks.

All remark writes use the existing domain mutation lock, recheck current project
permissions after acquiring it, and require expected revisions for existing
remarks. Read endpoints hold the lock through permission checks and serialization
of one page. Task deletion now checks remark-write permission when remarks exist,
previews their count, and uses the domain revision to reject intervening content
changes. Task moves automatically change remark access through current containment.
Write-only remark responses contain identifiers/revisions only.

The browser preserves text on failed writes and requires explicit reload/review
after stale or denied writes. Acknowledged writes with failed reloads are reported
as saved. Drafts belong to the open task window; closing/switching tasks does not
persist them. No supplementary frontend or backend dependency is introduced.
See [the remarks API](docs/remarks_api.md) for the delivered contract.
Multilingual search is described below; full-stage verification is tracked separately.

### Stable References

The `content` app stores source-owned `Reference` rows synchronized in the same
transaction as task-description or remark-body changes. Plain text contains
`[task:UUID]` / `[remark:UUID]` tokens; constraints enforce one source and unique
targets per source. Targets are identifiers without foreign keys, preserving
placeholders after deletion. A data migration indexes existing tokens without
editing their source content or revision.

A batched resolver holds the domain lock and applies current task/remark read
permissions before returning current labels and destination task IDs. Restricted
and missing targets share an unavailable response. The React editor provides a
picker, selection insertion and focus restoration; rendered links resolve current
labels and navigate through the permission-checked task view. Star previews avoid
embedding a second navigation link. See [the content API](docs/content_api.md).

## Search Approach

Search uses PostgreSQL full-text vectors, queries and functional GIN indexes
through Django, following the [Django search API](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/)
and [PostgreSQL text-search functions](https://www.postgresql.org/docs/17/textsearch-controls.html).
The backend filters task and remark sources separately by current read permissions
before counts, ranking and excerpts. Search holds the domain lock through page
serialization, uses deterministic rank/kind/UUID ordering, and provides no admin
or whole-timesheet-access bypass. No separate search service is used.

English and Russian, including mixed-language content, are the agreed initial
scope (2026-10-12). `content/search_config.py` centralizes vector expressions,
token removal and query language selection. Each document concatenates English
and Russian vectors. Cyrillic query words are normalized with Russian, other
words with English; PostgreSQL's `plainto_tsquery` removes each group's stop words.
Nonempty normalized groups combine with AND, preserving their lexemes through
the simple configuration rather than stemming twice. This supports mixed
inflections within one document without requiring a single document language.

Task title/description form one document; each remark body forms another. Inline
reference/image tokens are stripped before indexing and excerpts, so inaccessible
target labels and attachment data never become source search text. Per-language
headlines supply escaped plain text excerpts with bracketed matches. The UI retains
the query after failures, clears stale excerpts, and navigates through authorized
task views. See [the content API](docs/content_api.md).

Functional GIN indexes freeze the shared expression in task/remark migrations and
cover historical content automatically. Query-plan checks verify both indexes
are usable. Adding a language requires updating the central language list and
classifier, ensuring suitable PostgreSQL dictionaries, rebuilding affected indexes
with a migration, and mixed-language regressions. UI and permissions remain shared;
languages without suitable built-in processing may need additional tooling.

## Images and Content Handling

- Image files use a persistent local volume, with metadata and ownership
  relationships in PostgreSQL. Images belong to descriptions or remarks, as
  specified in the requirements.
- Validate actual static PNG/JPEG/WebP content with hash-locked Pillow 12.3.0,
  including a full decode, an inclusive 2 MiB input limit and a 20-million-pixel
  limit. The implementation follows Pillow's [image validation API](https://pillow.readthedocs.io/en/stable/reference/Image.html).
- Serve downloads through permission-checked endpoints, applying the containing
  task/remark's current permissions rather than exposing a public upload directory.
- Use stable identifiers for cross-references and resolve visibility on access.
  Keep file cleanup consistent with deletion of an eligible containing object.
- New images travel as base64 in ordinary source commands, up to five per save,
  with inline UUID tokens. This keeps creation, edits, revisions and uploads in
  one permission-checked operation and avoids orphan draft uploads. The editor
  supports file selection and screenshot paste, retaining pending bytes on failure.
- `ContentImage` stores exactly one task/remark source, verified metadata and a
  generated private file path. Domain mutations register rollback file cleanup;
  deletion uses robust after-commit callbacks. Process crashes or failed cleanup
  can leave orphan files; `prune_content_images` reconciles files under the domain
  lock, with an hour's grace, and reports missing referenced files.
- Download endpoints open files only after current source permission checks;
  private/no-store and nosniff headers prevent public cache reuse or MIME guessing.
  Development uses `development-uploads`, initialized for UID 1000; test storage
  remains temporary. See [the content API](docs/content_api.md).

## Agreed Backup and Restoration Policy

The server administrator is responsible for backing up the PostgreSQL cluster,
the attachment directory, and the configuration necessary to restore the system.
Backups must support a consistent restoration of database records and their
attachments. Provide written instructions for restoring the entire system on
another machine, including the required configuration and startup steps.

Select backup tooling, schedule, retention, and destination during deployment
planning. The backup/restore procedure and isolated full-system restoration check
remain Stage 10 work; no completed backup or restoration is claimed here.

## Proposed Deployment and Operations

By agreement on 2026-10-13, production configuration and deployment belong to
Stage 10. Stage 9 contains development activities only: the agreed administrator
lifecycle follow-up and application verification in the existing test setup.

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
  work progresses, following the agreed backup and restoration policy above.

## Reusable Test Setup

The shared environment was introduced in Stage 2 of the
[implementation plan](implementation_plan.md#stage-2-application-foundation) and
extended in Stage 3 with authenticated API/browser workflows, migration upgrades,
and independent-connection concurrency checks. Development Compose startup,
frontend-to-API connectivity, repeatable tests, and scoped cleanup were verified
on 2026-10-08. See [README.md](README.md) for commands and the tracker for exact
results. Stages 4–5 extend it with task and timesheet-engine acceptance; Stage 6
adds timesheet browser workflows, and Stage 7 adds reporting and CSV acceptance.
Extend the same harness as content features arrive. The [testing charter](testing_charter.md)
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
- Extend the environment in Stage 10 with production assets, the selected server
  and reverse proxy, and persistent test volumes for restart, migration, and
  agreed backup/restore checks. Never restore test backups into live storage.

### Shared Data and Deterministic Results

- Provide reusable builders and a documented seed/reset workflow for synthetic
  users and administrators, two organizations, several projects, grant combinations,
  and task trees at least three levels deep. Extend fixtures only as their models
  and features become available.
- Add multi-day timelines with active/unfinished/closed sessions, breaks, closing
  markers, midnight work, and the Friday-to-Monday correction example. Include
  invalid drafts and competing day saves/recording. Keep independently calculated
  totals and expected CSV records, including rounding cases, rather than deriving
  expectations from the report implementation itself.
- Control the backend clock and use explicit shared test zones. Verify the
  configurable UTC default and Europe/Berlin midnight allocation. Use controlled
  browser time or explicit historical timestamps where a workflow depends on the clock.
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

1. Select backup tooling, schedule, retention, and destination during deployment
   planning, following the agreed backup and restoration policy.
2. Select the application server, reverse proxy, and any supplementary frontend
   libraries during implementation; these were not fixed by the stack decision.
