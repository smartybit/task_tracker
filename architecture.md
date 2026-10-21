# Task Tracker Architecture

Current technical design and rationale. [Requirements](requirements.md) own product
behavior; [domain design](docs/domain_design.md) owns model relationships, access
contracts, timeline semantics, and transaction details. Use the
[documentation map](docs/README.md) to find commands and API references.
[Historical milestones](docs/archive/README.md) preserve implementation evolution;
[the tracker](implementation_plan.md) owns status and verification evidence.

## Accepted Decisions

- Backend: Python 3.13, Django 5.2 LTS, and Django REST Framework.
- Frontend: React, TypeScript, and Vite; Node 22 for builds/development.
- PostgreSQL 17 is the database for development, tests, and deployment.
- The backend owns permissions, business rules, and report calculations so future
  clients can use the same behavior. Cross-database portability is outside scope.
- Docker Compose runs development and VDS deployments. Deployment uses Gunicorn
  and Nginx serving built static frontend assets; Vite is a development server.
- Dependencies are locked in backend hashed requirements and the frontend lockfile;
  [development](docs/development.md#runtime-and-dependencies) owns tool versions.

## Application Structure

Backend modules cover accounts, projects, access, tasks, timesheets, reports,
remarks, and content. Views validate inputs and call shared services/policies.
Persistence helpers and model managers are not authorized mutation entry points.
The versioned `/api/v1/` API uses session authentication and CSRF protection for
browser requests. Native-client authentication is unselected future work.

Business writes use a persistent domain coordination row, followed by a per-user
timesheet lock when needed. This conservative small-team strategy serializes
mutations across hierarchy, grants, catalogs, content, and time records. Recheck
permissions and revisions after locking. Optimize only with measured need and
independent-connection PostgreSQL tests demonstrating equivalent integrity.
Read consistency depends on the operation: many content/timesheet reads also
coordinate with writers; reports use a database snapshot. Exact ordering and
constraints are in [transaction design](docs/domain_design.md#transactions-concurrency-and-constraints).

## Accounts and Authentication

Accounts have case-insensitive unique email identities and a persistent timesheet
created atomically. Bootstrap uses the domain lock and refuses if any administrator
exists, including an inactive one. Startup creates no accounts or default passwords.
The accounts app precedes Django auth so guarded management commands take precedence.

Django validates/hashes passwords. Password resets invalidate sessions through the
password hash; deactivation increments a private session version so reactivation
does not revive old sessions. Current grants are checked on requests, not cached
as effective session permissions. Login itself is CSRF-protected; frontend clients
refresh the token after login and distinguish authentication, permission, CSRF,
and validation errors. Host and trusted-origin checks stay enabled through proxies.

Administrator self-deactivation/demotion returns `400 self_protection` before any
fields change. Current actor privileges are rechecked after lock waits. Server
recovery uses the same atomic service boundaries, with independent explicit
reactivation/admin-grant options and no implicit data grants. Bootstrap and recovery
commands are in [development](docs/development.md#first-administrator-and-account-management)
and [operations](docs/environments.md#first-administrator).
[Stage 9 history](docs/archive/2026-10-21/implementation_history.md#stage-9-development-completion-and-application-verification)
records the safeguards follow-up to the original account implementation.

## Tasks and Statuses

Parent pointers represent the task tree; project and ancestor attribution derive
from current relationships. Services validate cycles, common projects, all affected
owners, and final ancestors before committing. Protected foreign keys prevent
indirect deletion of referenced catalogs, children, and time records. PostgreSQL
triggers make status first use permanent and prevent later status modification.

Descriptive edits/ownership transfers require task revisions. Creation, status,
move, and delete commands use previews and explicit confirmation with the domain
revision; existing tasks also supply their revision. Previews take the coordination
lock without writes or revision bumps. Confirmation repeats validation. Visible
preview rows require read access in both old and proposed projects; write-only
callers receive safe acknowledgements. Status changes and history commit together.

Lists use stable 50-item pages. The workspace fetches authorized pages, filters
project/status, and builds flat/tree views from parent IDs. A matching child whose
parent is filtered out appears as a displayed root. Owner selection exposes only
eligible active user IDs/names. See the [operation catalogue](docs/domain_design.md#operation-catalogue)
and [task history](docs/archive/2026-10-21/implementation_history.md#stage-4-tasks-and-their-interface).

## Timesheet Engine

WorkSession distinguishes active, unfinished, and closed work. One active session
per timesheet and one open tail per session permit historical unfinished days
alongside current recording. Unknown ends contribute zero and do not reserve an
infinite interval. PostgreSQL `btree_gist` exclusion constraints protect known
intervals; triggers enforce session/timesheet agreement. Services enforce continuity.

Ordinary edits change shared boundaries or delete the last row with preview.
`replace_day` validates a complete day draft and neighboring midnight connections
atomically, preserving retained IDs and other days' independent work. See
[timeline semantics](docs/domain_design.md#timeline-semantics) and
[timesheet API](docs/timesheet_api.md) for exact commands and error behavior.

Store absolute instants. `WORKING_TIME_ZONE` defaults to UTC; changing it requires
backend recreation and reallocates known spans without rewriting source timestamps
on GET. Read normalization handles old unsplit spans/zone changes with deterministic
fragment IDs; accepted commands persist normalized spans atomically. Split only
explicitly closed intervals at local midnight. DST acceptance remains outside scope.
The configured deployment zones belong in [operations](docs/environments.md).

The [editing decision history](docs/archive/2026-10-21/implementation_history.md#stage-5-timesheet-engine)
explains the replacement of automatic middle edits and globally single-open-entry
constraints. Additive migrations preserve IDs, timestamps, and revisions without
inventing missing ends.

## Web Interface

Tasks is the signed-in workspace, with the timesheet to its right or below on
narrow screens. Native dialogs hold details, commands, search, recording, and day
editing. Administration groups management screens; System status loads diagnostics
only when opened. Catalog directories load only when needed, with guards against
slow responses replacing newer results after navigation/refresh.

A single active task dialog switches between forms and previews, retaining the
mounted hidden form so cancel preserves text/images. Keep drafts in React memory,
confirm changed-draft dismissal/navigation, warn on browser unload, and restore
focus to the opener. In-flight refs plus disabled buttons prevent duplicate submits.
Stale results preserve input and require explicit reload/review. Acknowledged writes
followed by failed reads are reported as saved; block resubmission until review.

Day editing sorts on blur with stable local keys and restores keyboard focus after
row movement. `datetime-local` represents the backend working zone via Intl parts,
independent of browser zone; unchanged timestamps preserve precision. Tables show
HH:MM. Read-gated context supplies today and unfinished tails; label-only colleague
selection does not expose account-management fields. The browser editor requires
read plus write; safe write-only mutations remain available through the API.

React sorts the fully fetched remark stream by creation time/ID; sessionStorage
remembers newest/oldest-first per user. The API and shared-star list keep chronological
ordering. [Usage](docs/user_guide.md) describes interactions; the
[UI subplan archive](docs/archive/2026-10-21/ui_adjustments.md) records feedback,
implementation constraints, and acceptance.

## Reporting

A shared authorized-record selector filters projects/users before totals or CSV.
Whole-timesheet views deliberately use different access rules. Current task project
and ancestors determine attribution. Sum integer microseconds, allocate date-clipped
closed spans at working-zone midnight, and round decimal hours only at output.
Batch hierarchy rollups avoid queries per node and double counting.

Each report/options/CSV response uses a read-only repeatable-read PostgreSQL snapshot
covering current account/grants, relationships, and records. Materialize JSON inside
the snapshot. CSV uses a batched iterator and spool (disk after 1 MiB); close the
transaction before streaming so slow downloads do not hold snapshots or query lazily.

Selected records and readable task trees initially fit in memory for the small-team
scope. Add caching/precomputed summaries only with measured need and defined
invalidation. [Reporting API](docs/reporting_api.md) owns filters, rounding, and CSV
format; [Stage 7 history](docs/archive/2026-10-21/implementation_history.md#stage-7-reporting-and-csv-export)
records the implementation and snapshot verification.

## Remarks and References

Remarks have independent revisions and a `(task, created_at, id)` pagination index.
Writes and page reads use the domain lock for coherent access/content checks.
Task deletion checks remark-write access and content-aware previews; intervening
content changes invalidate the preview. Details are in [remarks API](docs/remarks_api.md).

Source-owned Reference rows synchronize with task/remark text in the same
transaction. Plain-text `[task:UUID]` and `[remark:UUID]` tokens reference stable IDs
without target foreign keys, preserving unavailable placeholders after deletion.
Constraints enforce one source and unique targets per source. A batched resolver
checks current access under the domain lock; restricted/missing targets share the
same response. Migration indexing preserves existing text/revisions. See
[content API](docs/content_api.md) and [content history](docs/archive/2026-10-21/implementation_history.md#stage-8-remarks-references-images-and-search).

## Search Approach

PostgreSQL full-text search with functional GIN indexes avoids a separate search
service. Task title/description is one document; each remark is another. Permission
filters apply before counts, ranking, and excerpts. Search holds the domain lock
through serialization and orders by rank/kind/UUID.

`content/search_config.py` centralizes vector expressions, token stripping, and
language selection. Documents concatenate English/Russian vectors. Cyrillic query
words use Russian normalization, other words English; `plainto_tsquery` removes stop
words. Nonempty groups combine with AND through the simple configuration to avoid
stemming twice. Inline reference/image tokens are excluded from indexing/excerpts,
preventing referenced labels or attachment content from leaking into source search.
Escaped plain-text headlines mark matches; the UI clears stale excerpts on failure.

Functional indexes freeze the shared expression in migrations and cover existing
content. Adding a language requires dictionary availability, central classifier/list
changes, an index-rebuilding migration, and mixed-language/query-plan regressions.
See [search API](docs/content_api.md#search).

## Images and Content Handling

Images use private persistent file storage with PostgreSQL metadata and exactly
one task/remark source. Pillow fully decodes static PNG/JPEG/WebP, checking inclusive
2 MiB and 20-million-pixel limits. Up to five new base64 images accompany the source
mutation with inline UUID tokens, avoiding separate orphan draft uploads.

Domain mutations register rollback cleanup; robust after-commit callbacks delete
obsolete files. Crashes/cleanup failures can leave orphans; `prune_content_images`
reconciles under the domain lock with an hour's grace and reports missing referenced
files. Downloads open files only after current source access checks and use
private/no-store and nosniff headers. [Content API](docs/content_api.md#images)
owns payloads and cleanup commands. Test storage stays separate from persistent uploads.

## Agreed Backup and Restoration Policy

The server administrator backs up the PostgreSQL cluster, attachment directory,
and configuration needed to restore the whole system on another machine. Backups
must support consistent restoration of database records and attachments, with
written startup/restoration instructions. Tooling, schedule, retention, destination,
and a verified isolated full-system restore remain outstanding in
[Stage 11](implementation_plan.md#stage-11-production-deployment-and-operational-verification).

## Deployment and Instance Isolation

Each named environment has its own Compose project, database/uploads, secrets,
network, instance/cookie identity, and release image namespace. `APP_BASE_PATH` and
`INSTANCE_ID` drive matching frontend/build/backend configuration. Internal routes
remain `/api/v1/`; Django's script prefix restores external paths. Document-fragment
navigation requires no SPA fallback; missing assets/unknown paths retain 404s.
[Multiple-instance design](docs/multiple_instances.md) owns the full configuration,
proxy, cookie, and same-origin trust contract.

Host Nginx terminates public HTTPS and preserves the full mount and Host to a
loopback static frontend; the private frontend strips the API prefix and sets the
forwarded scheme from the configured origin. Secure cookies and exact prefix-aware
health-check exemptions preserve HTTPS behavior. A 16 MiB proxy envelope accommodates
batched images without changing their per-image limit. Node is a build dependency,
not a deployed application service.

`environments.py verify NAME` inspects the selected deployment, whitelisted settings,
release/storage/ports, frontend/API identity, database health, and built assets via
GET. It verifies a different public origin with trusted HTTPS and no redirect
following. It makes no empty-data, fixed-zone, or host-wide inventory assumption.
[Operations](docs/environments.md) owns commands, current inventory, and authorization;
[deployment history](docs/archive/2026-10-21/implementation_history.md#stage-11-production-deployment-and-operational-verification)
records preparation and earlier routing decisions.

## Reusable Test Setup

Use the existing isolated PostgreSQL/Django/build/Chromium harness and synthetic
prefix/deployment fixtures. Separate test databases and upload volumes from all
persistent environments. [Testing charter](testing_charter.md) owns scenarios,
concurrency/fixture principles, and completion criteria;
[development](docs/development.md#isolated-test-setup) owns execution commands.
Actual results belong in the tracker and linked archive, not in architecture.

## Future Frontends and Open Decisions

No native Android implementation or offline synchronization is selected. Responsive
web/touch support is current. Capacitor could package the web UI; React Native
could share API/TypeScript contracts with separate native screens. Choose only
when native workflows are scoped; offline changes need explicit conflict rules.
Backup choices and production activation remain in the tracker. Supplementary UI
libraries and finer-grained locking should be selected only when needs justify them.
