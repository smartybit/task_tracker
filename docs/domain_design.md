# Domain Model and API Design

Stage 1 design for the [implementation plan](../implementation_plan.md).
[Requirements](../requirements.md) remain authoritative. This document selects
initial implementation approaches for delegated behavior, not additional
user-confirmed product requirements. Stage 2 implemented the initial User and
MutationLock models and a versioned health API. Stage 3 adds session/account,
organization/project, and grant APIs, shared access policies, and the minimal
Timesheet record; verification status is tracked in the implementation plan.
Stage 4 implements tasks/statuses, preview/confirmation operations, and the minimal
time-record relationships used for deletion protection. Stage 5 implements the
recording/correction engine and revised lifecycle. Remaining feature operations
are a design contract; verification status belongs in the implementation tracker.

The timesheet sections were revised on 2026-10-09 for the agreed
[Edit day](../requirements.md#timesheet-editing) and
[unfinished-day](../requirements.md#unfinished-days-and-overnight-work) behavior.
They supersede Stage 1's automatic middle-edit and globally single-open-entry
proposals. Stage 5 adds lifecycle migrations and backend commands; the Stage 6
interface remains Not started.

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
| timesheets / WorkSession | timesheet, started_at, ended_at (nullable), lifecycle state (active/unfinished/closed) | Continuity is required inside a session, not between sessions. One active recording session per user; multiple unfinished historical sessions are permitted. A closed session's end represents its End of Working Day marker. Stage 5 adds the lifecycle field and revised constraints. |
| timesheets / TimeEntry | timesheet, session, kind (task/break), task (nullable), started_at, ended_at (nullable) | Timesheet agrees with session; task required exactly for task entries; closed end greater than start; known intervals cannot overlap. One open tail per session, with unknown end/zero duration until closure; its session determines whether it is active recording or historical unfinished work. Task foreign key protects deletion, including hidden records. |
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
  in the configured shared working zone. `WORKING_TIME_ZONE` is configurable
  in `.env`/backend settings, with UTC as the default; DST acceptance is out of scope.
- Paginate lists and search with stable ordering. Reject unknown mutation fields;
  clients cannot set creator, calculated duration, inherited grants, or first-use
  markers directly.
- Use `400` for malformed input, `403` for an authenticated but forbidden action,
  `404` for missing or unreadable read targets, and `409` for stale revisions or
  business-rule conflicts. Session-authentication failures may use DRF's `403`;
  include a stable `authentication_required` code rather than depending on status
  alone. Error shape: `{code, message, fields?}` with non-sensitive details.
- Compound operations requiring preview return permitted affected rows and required
  confirmations without writing. Apply repeats validation inside the transaction;
  a preview is never authorization for a later write. Edit day's visible draft is
  its review step: Save changes submits one validated atomic replacement, without
  persisting an invalid draft or requiring a second preview window.
- Timesheet commands require `expected_revision`. Task mutations use task revisions;
  tree-changing previews also carry the domain revision. Successful commands return
  new revisions. Stale commands fail without changes; the UI refreshes and asks for
  review again instead of silently replaying historical edits. Preserve any Edit
  day draft when refreshing; never overwrite it with refreshed server rows.

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
| `timesheets/{user}/days/{date}` | Whole day rows, session identifiers/lifecycle, daily work total, revision, task labels and open/end markers, midnight connections | Timesheet read gate, never project-filtered. Expose unfinished-day warnings without embedding protected task content. |
| `timesheets/{user}/commands` | Typed start/switch/break/end-day/append/boundary/delete_last/resume/continue/replace_day command, explicit target date/session, expected revision and preview where required | Timesheet write gate. New task selection requires task read; retained references require no additional task read. `replace_day` carries the complete selected-day rows/markers with stable row identifiers; there is no individual middle-insert/delete command. Write-only responses are acknowledgements. |
| `tasks/{id}/remarks`, `remarks/{id}`, `remarks/{id}/star` | Ordered remarks, create/edit body, delete, toggle shared star | Task read plus corresponding remark flag. Preserve original author/time; return body only if remark read is also granted. |
| Description/remark `images`, `images/{id}/download` | Multipart upload; protected download/delete | Containing-object read/write gates; verified PNG/JPEG/WebP, maximum 2 MiB. Reject invalid, oversized, or foreign-source image identifiers. |
| `references/resolve` | Stable target identifiers; visible target or generic unavailable result | Resolve each target independently with task/remark read rules; never leak restricted titles, authors, snippets, or image previews. Source edits check source write access. |
| `search` | Query, pagination; task/description/remark matches and safe snippets | PostgreSQL full-text queries over separately authorized task and remark sources; permission-filter counts/ranking inputs, not just returned rows. No separate search service. |
| `reports/options` | Working zone/today and readable project/task/permitted-person labels | No administration fields or emails; other people require authorized task records in readable projects plus Read Others' Timesheets. |
| `reports/projects`, `reports/people-days`, `reports/tasks` | Date range, optional permitted person/project/task selection; direct/descendant/total hours as applicable | Shared authorized base query before grouping; task selection includes descendants. No other-person totals without Read Others' Timesheets. |
| `reports/records.csv` | Date range only; individual authorized task records with agreed columns | Same base access restrictions; excludes breaks/end markers. Interactive report filters are not accepted as export filters. Open task records have blank end and zero duration. |

## Timeline Semantics

Commands accept timestamps, not caller-calculated durations. Successful commands
validate the complete resulting timeline, normalize explicitly closed overnight
spans at local midnight, and commit together. The daily UI may show a synthetic
`end_of_day` row keyed to its WorkSession; it is not a work-duration entry.

- **Lifecycle:** active recording is distinct from unfinished historical sessions
  and closed sessions. An unfinished session has one tail with an unknown end;
  it does not reserve all future time. Closed sessions have no open tails. Permit
  one active recording session per timesheet and one open tail per session.
- **Start new day:** a new selected day's recording starts an independent active
  session by default. Mark any earlier active session unfinished without supplying
  its end. Do not block new recording or invent an interval between days.
- **Switch/break:** within the explicitly targeted session, close its tail and
  start a task or break at the same boundary. Reject duplicate/reversed boundaries.
  A task with an unset end contributes zero; breaks never contribute work hours.
- **Historical append:** ask for a start on the selected historical date. Close
  that session's unfinished tail at the supplied boundary and create its next tail.
  The historical session remains unfinished and today's active session is unchanged.
  Ordinary append cannot insert inside an existing interval.
- **End day:** close the targeted session's tail and session together at an explicit
  instant; the marker is the session's closing boundary. Closing historical work
  does not change today's active session or its entries.
- **Continue previous session:** explicitly opt into genuine overnight recording
  rather than the default independent new day. Validate against other sessions and
  active-recording uniqueness; do not silently merge conflicting sessions.
- **Resume:** when continuing a closed session, require explicit conversion of its
  end marker to a break. Reopen the session, fill from the former closing boundary
  to the new work start with a break, then start the selected task. Starting a new
  day's separate session does not fill the overnight interval. Do not silently
  bypass the conversion advice when resuming the same closed day.
- **Boundary edit:** ordinary edits change adjoining end/start together. First/last
  boundary edits also adjust an independent session edge. Preview affected changes;
  reject reordering, overlaps, or non-positive closed spans.
- **Delete last:** ordinary deletion is limited to the last task/break row of the
  selected session. Extend its predecessor to the removed row's end, or leave it
  open when deleting an open tail; preserve historical/active lifecycle. Delete an
  independent session if its sole row is removed. Do not remove connected overnight
  coverage. Use Edit day for a different attribution or any middle deletion.
- **Replace day:** submit the date, expected revision, and complete rows/session
  markers, associating retained IDs only with the targeted timesheet/day. New rows
  have stable client keys for validation errors. Revalidate task selections and the
  resulting timeline, including other sessions and neighboring-day connections.
  Preserve retained record identities; apply accepted changes together and bump
  the timesheet revision. Invalid/stale submissions change nothing. Retaining a
  valid unfinished tail is allowed; gaps do not implicitly create new sessions.
- **Final task:** historical additions/corrections remain allowed without status
  changes, including an unfinished historical tail. Selecting a final task
  for new current work returns `task_reopen_required`; reopening is a separate
  task-write action, not something a timesheet-only user can authorize implicitly.
  If the actor cannot reopen it, they can choose another task or a break.

### Edit Day Draft and Daily Boundaries

Edit day opens a modal copy of the selected day's Task / Start Time / End Time
table, with breaks and closing markers. Allow arbitrary row insertion/deletion and
time edits in frontend memory without automatic neighbor adjustments. Highlight
gaps, overlaps, missing fields, and invalid durations without blocking draft edits.
Sort by start after a field edit completes; keep incomplete rows at the bottom,
preserve focus, and use stable row keys. The task picker searches readable tasks
and filters by project/status, including final tasks.

Save changes submits one complete draft. Require positive closed durations,
continuity inside each session, valid markers, and no known overlaps. Independent
session edges may change or their day may become empty. Fixed midnight connections
to adjacent days must remain covered; reassign their work or replace it with breaks
rather than removing it. Correct neighboring days separately. An overnight carry-in
keeps its actual start, with the outside-day portion protected from a one-day edit.

Cancel never writes. Confirm dismissal of a changed draft. Validation, permission,
network, and revision errors retain the draft. A conflict requires refreshing and
reviewing stored work alongside the draft; never silently merge or replay it.

Open entries retain their actual start even across midnight and contribute zero.
Only explicit closure creates the midnight-split closed rows. Preview identifies
all affected days. The UI must not fabricate a midnight stop or daily recorded hours.
An explicitly continued overnight entry may appear as a carry-in row with its real
start and zero duration; this is not a new stored entry. An unfinished historical
tail instead stays on its historical day with an Unfinished warning. It is not
automatically shown as today's active work.

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
Use PostgreSQL exclusion protection on known half-open intervals per timesheet as
a backstop against overlaps. An unfinished historical tail has an unknown interval;
do not interpret every null end as an unbounded range. Check its actual span against
all other sessions when closing it. Store the timesheet foreign key on entries and
validate that it agrees with their session. Enforce one active session per timesheet
and one open tail per session, with lifecycle-consistent end timestamps. Continuity,
tree cycles, common-project rules, and final ancestors require service validation.

Stage 5 replaces Stage 4’s global null-end uniqueness through additive migrations.
Existing closed sessions become closed and existing open sessions remain active,
without inventing ends. Known-range exclusion allows multiple unknown tails;
entry/session agreement is also protected in PostgreSQL. The concrete command
payload is documented in [the timesheet API](timesheet_api.md); execution evidence
belongs in the implementation tracker.
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
coverage; timeline examples have Stage 5 coverage and report examples now have
Stage 7 backend and browser coverage. Executed verification is recorded in the
implementation tracker. Times use a controlled fixed zone;
all durations are independently calculated.

The historical middle-edit examples below now describe explicit day drafts, not
automatic neighbor adjustment. Git history preserves the superseded Stage 1
proposals. The Friday/Monday scenario is also specified in
[requirements](../requirements.md#friday-to-monday-example).

| Scenario | Input / action | Expected committed result |
| --- | --- | --- |
| Insert forgotten work in Edit day | A 09:00–10:00, B 10:00–11:00; add C 09:30–10:00 to the draft | Overlap is highlighted; saving fails unchanged until the user also shortens A to 09:30. Saving that complete valid draft gives A 09:00–09:30, C 09:30–10:00, B unchanged; 2 work hours. |
| Delete middle entry in Edit day | A 09:00–10:00, B 10:00–10:30, C 10:30–11:00; remove B from the draft | A and C do not move automatically. Gap blocks save. Explicitly extend A to 10:30 for 2 work hours, or add a break 10:00–10:30 for 1.5 work hours, then save atomically. |
| Delete first entry in Edit day | A 09:00–10:00, B 10:00–11:00 in an independent session; remove A | User may move the independent session start to 10:00, or explicitly replace A with a break. Either valid draft records 1 work hour; no neighbor changes occur automatically. |
| Delete last ordinary record | A 09:00–10:00, B from 10:00 with unset end; delete B after preview | A becomes the session's open tail from 09:00, duration zero. Its session retains active/unfinished lifecycle. Deleting an independent session's sole row clears the session. |
| Cancel or reject a draft | Change rows into a gap/overlap, then cancel or attempt save | Cancel discards the draft; invalid save retains it with errors. Stored rows, revision, and totals remain unchanged. |
| Invalid boundary | Same A/B; move their boundary to 11:30 | Conflict; entries, revisions, and total remain unchanged. |
| Open and overnight | Start A at 23:30, inspect at 00:15, then close at 00:30 | Before closure: end unset, 0 hours. After: 23:30–00:00 and 00:00–00:30, 0.5 hours each day, 1 hour total. |
| Resume closed session | A 09:00–17:00, closing marker at 17:00; explicitly resume B at 18:00 | A unchanged, break 17:00–18:00, B open/zero; 8 work hours until B closes. |
| Friday unfinished, Monday recording | Friday meeting 09:00–12:00, break 12:00–12:43, email from 12:43 with unset end; start Monday work at 09:00 | Monday becomes the active session; Friday is unfinished with 3 recorded work hours and a zero-duration email tail. No weekend interval or end is invented. |
| Complete Friday on Monday | Previous example; select Friday, append task at Friday 14:00, End of Working Day at Friday 17:00 | Email closes 12:43–14:00; task records 14:00–17:00. Friday records 7h 17m of work. Monday's rows and active session remain unchanged. |
| Historical final task | Append a Completed task to an unfinished Friday session, then close it | Task and ancestor statuses remain unchanged; current task read and timesheet write are checked. A still-unfinished tail contributes zero and never takes over Monday recording. |
| Fixed midnight connection | A closed overnight span is split at midnight; edit one day | A valid draft retains the fixed connected midnight edge; removing its required coverage blocks save. Other-day intervals are not silently rewritten. |
| Close unfinished work into later work | Friday has an unknown tail; Monday has recorded work; supply an end extending into Monday's work | Reject the overlapping closure without changing either session or revision. Missing end alone did not reserve the weekend. |
| Final ancestor reopening | Root and child Completed; grandchild Completed -> In Progress | All three become In Progress with individual history rows; unrelated branches unchanged. Denied change leaves all unchanged. |
| Finalization blocked | Root -> Completed while grandchild is Waiting for Customer Response | Conflict even if its immediate child is final; no history or status changes. |
| Owner loses access | Owner U has write at assignment, then all their task grants are removed | Owner remains U; U cannot read/edit; another authorized writer can edit description. Reassignment to U or move requiring U's eligibility fails until eligible. |
| Project move | Parent direct 1h, child 2h, grandchild 0.5h in P; explicit root move to Q | P loses 3.5h, Q gains 3.5h. Parent direct 1h, descendants 2.5h, total 3.5h; validate every owner's destination write grant first. |
| Status permanence | Completed used once, then no tasks currently use it | Rename/final-flag change/delete still rejected; assigning Completed to another eligible task remains allowed. |
| Whole sheet vs report | Viewer has Read Others' Timesheets and read access to P only; colleague records P 1h and Q 2h | Whole sheet shows both task labels and 3h; Q details unavailable; reports/CSV include P 1h only. |
| Own-only report | Same records, but viewer lacks Read Others' Timesheets | Reports/CSV contain only viewer's own work in readable projects, even if Write Others' Timesheets is granted. |
| CSV special/open rows | Closed A 09:00–10:30, break 10:30–11:00, open B from 11:00; another session has a closing marker | Closed A exports 1.5h; open B exports blank end/0h. No break or end marker row. Person/project/task UI filters do not narrow the authorized dump. |
| Concurrent commands | Two current starts use timesheet revision 7 | One commits revision 8; the other gets stale-revision conflict. Exactly one active recording session remains; historical unfinished tails may coexist. |
| Day save races current recording | Friday draft uses revision 7; Monday switch commits revision 8 before Save changes | Reject stale Friday save without applying rows. Retain the draft for reload/review; Monday's new recording is preserved. |
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
  English and Russian, including mixed-language content, are agreed for initial
  search. Select the concrete indexing/query configuration in Stage 8; it does
  not require a separate search service.

## Remaining Decisions and Implementation Boundary

The shared working zone is configurable in settings, defaulting to UTC. Backup
responsibility and full-system restoration requirements are agreed in the
[architecture](../architecture.md#agreed-backup-and-restoration-policy); tooling,
schedule, retention, and destination remain deployment decisions. They do not
block schema/API design. Initial search languages are English and Russian;
the concrete multilingual configuration, supplementary UI libraries, and
server/proxy are chosen when their stages need them. The initial test runners are Django and
Playwright/Chromium, introduced in Stage 2 and extended through Stage 4. Worked
examples are design contracts; actual PostgreSQL, browser, and concurrency
evidence is recorded in the implementation tracker. Task/status acceptance
passed in Stage 4; timeline acceptance passed in Stage 5. Stage 7 reporting and
CSV acceptance passed two full lifecycle runs, each with 97 PostgreSQL tests and
30 Chromium scenarios. Content acceptance remains planned. Concrete reporting
contracts are in [the reporting API](reporting_api.md).
