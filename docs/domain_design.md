# Domain Model and API Design

Stage 1 design for the [implementation plan](../implementation_plan.md).
[Requirements](../requirements.md) remain authoritative. This document selects
initial implementation approaches for delegated behavior, not additional
user-confirmed product requirements. Stage 2 implemented the initial User and
MutationLock models and a versioned health API. Stage 3 adds session/account,
organization/project, and grant APIs, shared access policies, and the minimal
Timesheet record; verification status is tracked in the implementation plan.
Stage 4 implements tasks/statuses, preview/confirmation operations, and the minimal
time-record relationships used for deletion protection. Recording commands and
remaining feature operations below remain a design contract. Refine it
with verified migrations and tests as each feature stage starts.

## Modules and Records

Use UUID public identifiers, database foreign keys, and creation/update timestamps
where relevant. Do not duplicate a task's organization or recorded work's project:
derive them through current relationships so historical attribution stays correct.

| Module / record | Essential fields and relationships | Integrity and lifecycle |
| --- | --- | --- |
| accounts / User | email, display name, password hash, active flag, application-administrator flag, read/write others' timesheets | Custom Django user before the first migration; normalize email consistently and enforce case-insensitive uniqueness. Application administration never implies data access. Deactivate referenced users rather than cascade-delete their work. |
| access / OrganizationGrant | user, organization, task read/write, remark read/write | Unique user/organization; independent Boolean grants, all initially false. |
| access / ProjectGrant | user, project, the same four flags | Unique user/project; effective flag is organization OR project, never a project denial. |
| projects / Organization | name | Protect deletion while projects exist. |
| projects / Project | organization, name | Protect deletion while tasks exist; do not change its organization through a generic field edit. An explicit future move would need grant/owner validation. |
| tasks / TaskStatus | name, final, first_used_at | Seed the five initial statuses; first use is permanent, even after tasks are deleted or change status. Used status fields and deletion are locked. |
| tasks / Task | title, description, project, parent (nullable), owner, creator, status, revision | Protect project, owner, creator, parent, and status references. Same-project acyclic tree; only creation, ownership transfer, and project changes check owner eligibility. |
| tasks / TaskStatusChange | task, previous/new status, actor, changed_at | Record initial status and subsequent changes, including propagated ancestor changes; delete history only with an eligible task. |
| timesheets / Timesheet | user (unique), revision | Persistent per-user lock target, created with the account; ownership grants unconditional self-access. |
| timesheets / WorkSession | timesheet, started_at, ended_at (nullable) | Defines the recorded interval; continuity is required inside it, not between sessions. A closed session's end represents its End of Working Day marker. |
| timesheets / TimeEntry | timesheet, session, kind (task/break), task (nullable), started_at, ended_at (nullable) | Timesheet agrees with session; task required exactly for task entries; closed end greater than start; no overlapping entries and at most one running entry per timesheet. Task foreign key protects deletion, including hidden records. |
| remarks / Remark | task, author, body, starred, created_at, edited_at, revision | Shared stars; original author/time survive edits. Task deletion may remove remarks only after its eligibility and content-write checks. |
| content / Image | containing task OR remark, private storage key, verified format, byte size, uploader | Exactly one containing object; no standalone task attachment collection or public media URL. Deletion cleanup follows its containing object. |
| content / Reference | source task OR remark, target kind and stable UUID | Validate source ownership; resolve target permissions on every access. Target identifiers survive deletion for an unavailable placeholder; no target cascade. |
| core / MutationLock | singleton key | Persistent transaction coordination row, created by a migration; see locking below. Not an audit log. |

Descriptions and remark bodies initially use plain text with structured image and
reference identifiers, not executable HTML. Rich editing can be added without
changing access rules. Users and catalogs have no public signup/delete shortcut.

## Authorization Contract

Evaluate current grants on every request; do not store effective grants in a login
session. Keep view queries distinct from write eligibility so write without read
remains technically possible. No Django superuser shortcut in domain services,
serializers, downloads, search, or reports; do not expose domain models through an
unrestricted Django admin interface.

| Operation | Required access |
| --- | --- |
| Read task/list/history/description image | Effective task read for its project. |
| Create/change/delete task | Effective task write; creation owner is the actor. Owner/project selection also validates the selected owner's task write grant. |
| Read remarks or their images | Task read AND effective remark read. |
| Add/change/delete/star remarks or their images | Task read AND effective remark write; task write is not necessary. |
| Read a timesheet | Self OR Read Others' Timesheets; no project filtering. |
| Change a timesheet, including its past | Self OR Write Others' Timesheets; no project write or read required for retained task references. Selecting a new task additionally requires task read. |
| Read report/CSV records | Readable task project AND (self records OR Read Others' Timesheets). |
| Configure accounts, grants, organizations/projects, statuses | Application administrator; this does not grant access to their task content. |

Write-only operations return an identifier/revision acknowledgement, not a full
object representation. Reading that object still requires read access. Error and
preview responses must not disclose protected descriptions, remarks, related-user
records, or child details. An authorized whole-timesheet response may expose task
labels and timestamps, but links/details and project report access remain separate.

## API Conventions

- Prefix application routes with `/api/v1/`. Browser authentication uses Django
  sessions and CSRF protection, including login. No token/mobile authentication or
  email delivery is introduced now.
- Use ISO dates and offset-aware timestamps. Store instants in UTC and derive days
  in the configured shared working zone. UTC is a temporary test/development
  default, not a decision about the deployment zone; DST acceptance is out of scope.
- Paginate lists and search with stable ordering. Reject unknown mutation fields;
  clients cannot set creator, calculated duration, inherited grants, or first-use
  markers directly.
- Use `400` for malformed input, `403` for an authenticated but forbidden action,
  `404` for missing or unreadable read targets, and `409` for stale revisions or
  business-rule conflicts. Session-authentication failures may use DRF's `403`;
  include a stable `authentication_required` code rather than depending on status
  alone. Error shape: `{code, message, fields?}` with non-sensitive details.
- Compound operations have a preview mode, returning permitted affected rows and
  required confirmations without writing. Apply repeats validation inside the
  transaction; a preview is never authorization for a later write.
- Timesheet commands require `expected_revision`. Task mutations use task revisions;
  tree-changing previews also carry the domain revision. Successful commands return
  new revisions. Stale commands fail without changes; the UI refreshes and asks for
  confirmation again instead of silently replaying historical edits.

## Operation Catalogue

These are operation families, not generic model CRUD permission bypasses. Read and
write gates refer to the authorization table above. All mutations validate fields,
references, and applicable business invariants before committing.

| Route / operation | Input and result | Access and failure behavior |
| --- | --- | --- |
| `GET auth/csrf`, `POST auth/login`, `POST auth/logout`, `GET auth/me` | CSRF token; email/password; session; current identity and capabilities | Login validates active account/password without exposing which failed. No public registration. Logout requires CSRF. |
| `users` and `users/{id}` administration | Create/update account, active state and global timesheet flags; password-reset action accepts a new password | Administrator only, password validation/hashing, no password in responses or logs. Account changes do not reassign tasks. |
| `organizations`, `projects`, scoped `grants` | Read permitted catalog choices; administrator create/update/delete or replace a user's local flags | Non-admin selectors expose only choices needed for authorized operations; grant management is admin-only. Referenced organizations/projects cannot cascade-delete tasks. |
| `statuses` | Read catalog; administrator create/update/delete unused status | Used status returns `status_already_used` on any change or deletion. Seeded status names and final flags match requirements. |
| `tasks`, `tasks/{id}`, `tasks/{id}/history` | Filtered list/tree or details; create title/description/project/parent/status with creator as owner; edit descriptive fields | Separate read/write gates. Missing project, ineligible owner, cross-project parent, or cycle rejects the whole change. Status/project/parent/owner changes use dedicated operations below. |
| `POST tasks/preview`, `POST tasks/{id}/{status,move,delete}/preview` | Proposed command values (plus task revision for an existing task); domain revision, permitted affected rows, safe target acknowledgement | No writes or revision bumps; current task write required. Confirmation uses `confirm: true` and `expected_domain_revision`. Deletion applies via `DELETE tasks/{id}`; creation/status/move apply via their normal routes. |
| `projects/{id}/eligible-owners` | Eligible active user IDs and display names | Project task write; no account-management fields or emails. |
| `tasks/{id}/owner` | Proposed owner and expected revision; acknowledgement | Task write and new owner's effective task write. Later access loss does not invalidate unrelated task edits. |
| `tasks/{id}/status` | Selected status, optional non-final ancestor status and preview/confirmation | Task write for every changed task. Finalization requires all descendants final; reopening propagates to final ancestors. Reject invalid/used-status edits separately from valid assignments of used statuses. |
| `tasks/{id}/move` | New parent or root, explicit destination project if changed, revisions, preview/confirmation | Write in source/destination projects and owner eligibility for every project-changed task. Move subtree atomically; same project unless explicitly changed. Preserve final-ancestor invariant or reject. |
| `DELETE tasks/{id}` with deletion preview | Expected revision and confirmation of eligible remark/image removal | Task write plus task read and remark write if remarks will be removed. Any child or any user's time entry blocks deletion, including hidden references; generic conflict without protected record details. |
| `timesheets/{user}/days/{date}` | Whole day rows, daily work total, revisions, permitted task labels and open/end markers | Timesheet read gate, never project-filtered. Protected task content is not embedded. |
| `timesheets/{user}/commands` | Typed start/switch/break/end-day/insert/boundary/delete/resume command, expected revision and optional preview | Timesheet write gate. New task selection requires task read. No read gate on editing retained references; write-only responses are acknowledgements. See timeline semantics below. |
| `tasks/{id}/remarks`, `remarks/{id}`, `remarks/{id}/star` | Ordered remarks, create/edit body, delete, toggle shared star | Task read plus corresponding remark flag. Preserve original author/time; return body only if remark read is also granted. |
| Description/remark `images`, `images/{id}/download` | Multipart upload; protected download/delete | Containing-object read/write gates; verified PNG/JPEG/WebP, maximum 2 MiB. Reject invalid, oversized, or foreign-source image identifiers. |
| `references/resolve` | Stable target identifiers; visible target or generic unavailable result | Resolve each target independently with task/remark read rules; never leak restricted titles, authors, snippets, or image previews. Source edits check source write access. |
| `search` | Query, pagination; task/description/remark matches and safe snippets | PostgreSQL full-text queries over separately authorized task and remark sources; permission-filter counts/ranking inputs, not just returned rows. No separate search service. |
| `reports/projects`, `reports/people-days`, `reports/tasks` | Date range, optional permitted person/project/task selection; direct/descendant/total hours as applicable | Shared authorized base query before grouping; task selection includes descendants. No other-person totals without Read Others' Timesheets. |
| `reports/records.csv` | Date range only; individual authorized task records with agreed columns | Same base access restrictions; excludes breaks/end markers. Interactive report filters are not accepted as export filters. Open task records have blank end and zero duration. |

## Timeline Semantics

Commands accept timestamps, not caller-calculated durations. Successful commands
normalize the complete affected session, split closed spans at local midnight,
validate continuity, and commit together. The daily UI may show a synthetic
`end_of_day` row keyed to its WorkSession; it is not a work-duration entry.

- **Start/switch:** choose a readable task and start instant. In a running session,
  close the current entry and start the new one at the same boundary. With no
  session, create one. Reject duplicate/reversed boundaries instead of producing
  zero-length closed entries. A new task entry reports zero until closed.
- **Break:** identical boundary handling with kind `break` and no task. Breaks can
  remain open but never contribute work hours.
- **End day:** close the running entry and session together at the chosen instant.
  No open entry remains; the marker is the session's closing boundary.
- **Resume:** when continuing a closed session, require explicit conversion of its
  end marker to a break. Reopen the session, fill from the former closing boundary
  to the new work start with a break, then start the selected task. Starting a new
  day's separate session does not fill the overnight interval. Do not silently
  bypass the conversion advice when resuming the same closed day.
- **Insert:** within an existing entry, shorten it at the insertion instant and
  assign the remainder up to the next boundary to the selected task or break.
  In an open entry, the newly inserted remainder becomes the running entry.
  At an existing boundary, require explicit replacement rather than guessing.
  Outside a session, request explicit session creation or boundary extension;
  reject spans that overlap another session.
- **Boundary edit:** change the adjoining end/start together, including across day
  fragments. First/last-boundary edits also adjust the session boundary. Reject
  reordering entries, overlap with another session, or non-positive closed spans.
- **Delete:** default to extending the immediately preceding entry to the removed
  entry's end (or make it open if deleting the running entry). With no predecessor,
  replace the removed interval with a break. An explicit replace-with-break option
  avoids incorrectly attributing removed work to its predecessor. Normalize across
  midnight again; the operation never leaves a hole inside the session.
- **Final task:** historical corrections remain allowed. Selecting a final task
  for new current work returns `task_reopen_required`; reopening is a separate
  task-write action, not something a timesheet-only user can authorize implicitly.
  If the actor cannot reopen it, they can choose another task or a break.

Open entries retain their actual start even across midnight and contribute zero.
Only explicit closure creates the midnight-split closed rows. Preview identifies
all affected days. The UI must not fabricate a midnight stop or daily recorded hours.
The current day can show an ongoing entry from a previous day as a carry-in row
with its real start and zero duration; that display is not a new stored entry.

## Transactions, Concurrency, and Constraints

For the initial small-team implementation, favor a simple correct coordination
strategy over premature concurrency optimizations:

1. Every domain mutation enters `transaction.atomic()` and locks the persistent
   singleton MutationLock row before reading mutable permissions and references.
   Accounts/grants/catalog changes participate too; login/session storage does not.
2. Timesheet mutations additionally lock that user's persistent Timesheet row.
   Use this order everywhere, including management commands and fixture operations
   that exercise business services. No writable generic admin routes or bulk
   updates may bypass the services.
3. Re-read current state and revisions after locking. Validate all affected owners,
   descendants, statuses, content grants, sessions, and neighbors before writing.
   Update revisions and history, then commit; errors roll back the entire command.

This deliberately serializes business writes initially. It handles deletion racing
with time recording/child creation and finalization racing with reopening without
an incomplete per-tree lock scheme. Reads remain concurrent. Replace the global
coordination with finer-grained ordered locks only when measured load warrants it
and PostgreSQL concurrency regressions demonstrate equivalent integrity.

Add database checks for entry kind/task consistency, positive closed durations,
and uniqueness; use protected foreign keys for task time records and child tasks.
Use a PostgreSQL exclusion constraint on half-open time ranges per timesheet as a
backstop against overlaps, treating a running range as unbounded. Store the
timesheet foreign key on entries for this constraint and validate that it agrees
with their session. Enforce one running entry/session per timesheet. Continuity,
tree cycles, common-project rules, and final ancestors require service validation.
Protect permanent status first-use/immutability against accidental direct changes
with a database trigger when statuses are implemented.

For multi-query reports and streamed CSV, capture an authorized consistent database
snapshot (read-only repeatable-read transaction) and complete queries under it.
Do not calculate rollups from a different tree revision or lazy-query CSV rows
after leaving the snapshot. Avoid holding the snapshot open on a slow client:
materialize/export to temporary storage before serving it if needed.

File writes cannot be rolled back with PostgreSQL. Validate/stage uploads first,
then attach metadata atomically; clean staged files on failure. Remove obsolete
files only after commit, retaining an orphan-cleanup procedure for failed physical
deletion. Keep file bytes out of transaction error responses and logs.

## Worked Acceptance Examples

These examples define expected outcomes. Task/status scenarios now have Stage 4
coverage; timeline/report examples remain future fixtures. Executed verification
is recorded in the implementation tracker. Times use a controlled fixed zone;
all durations are independently calculated.

| Scenario | Input / action | Expected committed result |
| --- | --- | --- |
| Insert forgotten work | A 09:00–10:00, B 10:00–11:00; insert C at 09:30 | A 09:00–09:30, C 09:30–10:00, B unchanged; total remains 2 hours. |
| Delete middle entry | A 09:00–10:00, B 10:00–10:30, C 10:30–11:00; delete B | A extends to 10:30, C unchanged; total 2 hours. Replace-with-break instead gives 1.5 work hours. |
| Delete first entry | A 09:00–10:00, B 10:00–11:00; delete A | Break 09:00–10:00, B unchanged; 1 work hour. |
| Invalid boundary | Same A/B; move their boundary to 11:30 | Conflict; entries, revisions, and total remain unchanged. |
| Open and overnight | Start A at 23:30, inspect at 00:15, then close at 00:30 | Before closure: end unset, 0 hours. After: 23:30–00:00 and 00:00–00:30, 0.5 hours each day, 1 hour total. |
| Resume closed session | A 09:00–17:00, closing marker at 17:00; explicitly resume B at 18:00 | A unchanged, break 17:00–18:00, B open/zero; 8 work hours until B closes. |
| Final ancestor reopening | Root and child Completed; grandchild Completed -> In Progress | All three become In Progress with individual history rows; unrelated branches unchanged. Denied change leaves all unchanged. |
| Finalization blocked | Root -> Completed while grandchild is Waiting for Customer Response | Conflict even if its immediate child is final; no history or status changes. |
| Owner loses access | Owner U has write at assignment, then all their task grants are removed | Owner remains U; U cannot read/edit; another authorized writer can edit description. Reassignment to U or move requiring U's eligibility fails until eligible. |
| Project move | Parent direct 1h, child 2h, grandchild 0.5h in P; explicit root move to Q | P loses 3.5h, Q gains 3.5h. Parent direct 1h, descendants 2.5h, total 3.5h; validate every owner's destination write grant first. |
| Status permanence | Completed used once, then no tasks currently use it | Rename/final-flag change/delete still rejected; assigning Completed to another eligible task remains allowed. |
| Whole sheet vs report | Viewer has Read Others' Timesheets and read access to P only; colleague records P 1h and Q 2h | Whole sheet shows both task labels and 3h; Q details unavailable; reports/CSV include P 1h only. |
| Own-only report | Same records, but viewer lacks Read Others' Timesheets | Reports/CSV contain only viewer's own work in readable projects, even if Write Others' Timesheets is granted. |
| CSV special/open rows | Closed A 09:00–10:30, break 10:30–11:00, open B from 11:00; another session has a closing marker | Closed A exports 1.5h; open B exports blank end/0h. No break or end marker row. Person/project/task UI filters do not narrow the authorized dump. |
| Concurrent commands | Two starts use timesheet revision 7 | One commits revision 8; the other gets stale-revision conflict. Exactly one running entry and no overlap remain. |
| Delete race | Task deletion races child creation or first time record | Serialized result: either deletion succeeds and creation fails, or creation succeeds and deletion is blocked. No orphan child or time record. |

## Reporting and Search Details to Carry Forward

- Use one authorized-record selector for all report views and CSV. Whole-timesheet
  totals intentionally use a different selector without project restrictions.
  Calculated hours embedded in task lists/details must use the report selector too;
  task read alone must not reveal other users' recorded totals.
- Keep durations exact until output; initially render decimal hours rounded to
  two decimal places with trailing zeros optional. Summaries sum original durations,
  not rounded CSV cells, so a sum of displayed rows may differ by rounding.
- Accept report/CSV date ranges as inclusive calendar dates, translated to the
  shared-zone interval `[from midnight, day-after-to midnight)`. Closed entries
  split at midnight make day attribution unambiguous; open rows belong to their
  start date and always report zero.
- Group by the timesheet user, not owner; use current task project/ancestors.
  Avoid joining remarks into the time-record query and multiplying durations.
- Search tasks/descriptions and remarks separately under their own read gates,
  then merge/paginate ranked results. Add PostgreSQL indexes with migrations.
  English/Russian/mixed-language configuration remains to be selected before
  Stage 8; it does not require a separate search service.

## Remaining Decisions and Implementation Boundary

The deployment working zone and backup responsibility/recovery expectations remain
open as recorded in the requirements and architecture. They do not block schema/API
design. Search language configuration, supplementary UI libraries, and server/proxy
are chosen when their stages need them. The initial test runners are Django and
Playwright/Chromium, introduced in Stage 2 and extended through Stage 4. Worked
examples are design contracts; actual PostgreSQL, browser, and concurrency
evidence is recorded in the implementation tracker. Task/status acceptance
passed in Stage 4; timeline, report, and content acceptance remain planned.
