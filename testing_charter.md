# Testing Charter

## Purpose and Authority

Establish confidence that the task tracker protects access boundaries, preserves
recorded work, and produces correct totals while supporting everyday team use.
Prioritize permission errors, lost data, and incorrect time accounting.

Product behavior is defined in [requirements.md](requirements.md). Selected
technologies and implementation proposals are in [architecture.md](architecture.md).
This charter guides testing; it does not add product features. Treat proposed
defaults as revisable choices and keep their tests aligned with the behavior
selected during implementation.

## Test Missions

### 1. Exercise Access Boundaries

- Cover regular users and administrators with direct project grants, inherited
  organization grants, and all read/write flag combinations. Organization grants
  remain effective when project flags are unset. Administrators have no implicit
  access to application data.
- Verify unconditional read/write access to one's own timesheet. Separately test
  Read Others' Timesheets and Write Others' Timesheets across all other users.
- Verify that whole-timesheet access includes every project while task details,
  remarks, and images still require their corresponding access. Preserve the
  permitted task labels and timestamps in the timesheet.
- Require task read plus the relevant remark permission for remark operations.
  Check that task read alone permits recording time without task write or ownership.
- Verify historical task selection includes final tasks without reopening them;
  new selections require current task read. Existing timesheet references remain
  editable after task access loss without exposing protected details. Recheck
  permissions when an Edit day draft is saved, including write-without-read APIs.
- Check permissions through direct API requests as well as the interface, including
  search snippets, reference previews, downloads, reports, and CSV exports.
- Transfer ownership to an eligible user, then revoke that user's access. Ownership
  remains intact and confers no visibility or editing rights.
- Change permissions during an active session; subsequent requests must use the
  current grants. Include deliberately configured write-without-read combinations.

### Stage 3 Authentication and Administration Checks

Use the shared Compose harness for API and Chromium checks for
CSRF bootstrap, login/logout, account creation, administrator password reset,
catalog/grant management, and current identity. Exercise valid mutations through
the actual Vite proxy as well as missing/invalid CSRF and untrusted origins;
API tests must explicitly enforce CSRF. Verify that old passwords no longer
work after reset, existing sessions lose authentication after reset/deactivation, and grant
or administrator-role changes affect subsequent requests without another login.
Use separate browser contexts and reset mutable synthetic fixtures between cases.

Check first-administrator bootstrap races, account/timesheet atomic creation,
unique grants, rejected updates, and rollback against PostgreSQL. Exercise new
migrations on both fresh databases and an isolated Stage 2 schema with synthetic
existing users. At Stage 3, task/remark and self/others timesheet access are shared
service contracts; repeat those checks through actual feature endpoints when
Stages 4–8 introduce them. The Stage 3 completion boundary does not imply that
task, time-entry, remark, or reporting workflows already work.

Follow-up, pending the administrator lifecycle decision: cover last-active-admin
deactivation/demotion, two competing removals, and the agreed recovery procedure.
These cases were not part of the successful Stage 3 suite.

### 2. Preserve Timesheet Integrity

- Start tasks, switch tasks, append breaks, and close the targeted session. Active
  and historical unfinished tails have unset ends and contribute zero until closed.
- Verify ordinary shared-boundary edits and last-record deletion with preview;
  earlier rows cannot be individually inserted/deleted through ordinary controls
  or a bypass API. A last deletion extends the predecessor or clears an independent
  sole-row session, without changing today's active session during historical edits.
- In Edit day, freely add, change, and delete rows at the beginning/middle/end.
  Draft gaps/overlaps and invalid durations are highlighted without preventing edits
  or automatically moving neighbors. Invalid saves leave rows/revisions/totals
  unchanged; valid saves apply the complete day atomically. Cancel never writes.
- Check continuity, positive closed durations, session markers, fixed midnight
  connections, changes to independent session edges, and clearing independent days.
  Breaks fill internal gaps; outside-session time needs no filler. Do not infer new
  sessions from draft gaps. A valid unfinished tail may remain after saving.
- Exercise Friday-to-Monday correction: start Monday without completing Friday,
  then append Friday's forgotten task at 14:00 and close Friday at 17:00. Verify
  Friday's 7h 17m of work, no weekend filler/work, and unchanged Monday records and
  active-session identity. Cover multiple unfinished historical days and reject
  a supplied historical end that overlaps later known work.
- Verify new-day recording defaults to an independent session, explicit Continue
  previous session supports overnight work, and closed-session resumption retains
  the advice to convert its End of Working Day marker to a break.
- Verify the configurable UTC default, Europe/Berlin, and reallocation of stored
  spans after a zone change, including stable draft identifiers and read-only GET.
- Close work that crosses midnight and verify each day's allocation without losing
  a minute. Merely crossing midnight, logging out, or restarting the application
  must not invent an end time or recorded hours.
- Exercise simultaneous current starts, historical appends, boundary changes, and
  whole-day saves using independent PostgreSQL connections. Accepted results
  preserve the timeline; stale/failed operations leave no partial changes. Check
  one active session per user and one unfinished tail per session, including
  migration from the existing Stage 4 global null-end uniqueness constraints.

### Stage 6 Browser Acceptance

- Open Edit day for historical and running days; test add/remove/time edits,
  sorting after field completion, incomplete rows, focus, keyboard navigation,
  validation highlighting, and changed-draft dismissal confirmation.
- Select readable tasks with search and project/status filters, including final
  tasks. Retain existing inaccessible references without opening protected details.
- Verify a failed save preserves input, invalid drafts never change persisted
  work, successful saves refresh the day, and Cancel leaves the original intact.
- Record Monday in another tab while editing Friday; a stale save must preserve
  the draft and require reload/review without overwriting Monday's recording.
- Exercise ordinary historical additions with explicit selected-day timestamps,
  last-record deletion, unfinished warnings/partial totals, explicit overnight
  continuation, and fixed midnight boundaries in the day editor.

Stage 6 implements these browser scenarios; execution results and outstanding
checks are recorded in the tracker. They were not exercised during Stage 4 or the
documentation revision of 2026-10-09.

### 3. Enforce Task and Status Rules

- Require a project, enforce one project throughout a hierarchy, and reject cycles.
  Different owners are allowed; ownership and project changes enforce the agreed
  owner eligibility checks without automatically resolving later access loss.
- Block finalizing a task while any descendant is non-final. Reopening propagates
  through final ancestors while leaving unrelated branches unchanged.
- Verify status history and immutability of used statuses. Under the proposed
  default, first use permanently prevents editing or deleting that status.
- Block deletion whenever a child or any user's timesheet record exists, including
  records the caller cannot view. Check administrators and indirect deletion paths.
- Race deletion against creation of a child or time record, and finalization
  against a descendant reopening. The committed result must satisfy the rules.
- Repeat the Stage 3 grant matrix through actual task endpoints, including
  administrators without grants, write-only acknowledgements, protected list/tree
  counts and history, and grants revoked while a mutation waits for the domain
  lock. Stale revisions and previews must reject without partial history changes
  or disclosure of unreadable tasks.
- Test the five initial statuses on fresh migrations and an isolated Stage 3
  upgrade preserving existing users, grants, and timesheet rows. Check permanent
  first-use protection after the last referencing task changes status or is deleted.

### Stage 4 Browser Acceptance

Exercise task creation/editing and ownership transfer through the real frontend,
including persistence after reload. Use a three-level tree, collapse/expand it,
and combine project and multiple-status filters; matching children remain visible
when their parents are filtered out. Check status history, blocked finalization,
ancestor-reopening previews, cancellation, cycle rejection, subtree project moves,
and protected/eligible deletion.

Use independent browser contexts for stale task revisions and revoke grants from
another session. Cover read-only controls, write-only creation without content
responses, denied actions from stale screens, and administrators without data
grants. Invalidate a preview with another domain mutation and require a new review.
Configure unused statuses through the management UI and verify used-status controls
are protected. Exercise keyboard input/focus, repeated confirmation clicks, and
recovery from a failed request without losing the draft. Capture desktop and narrow
viewport screenshots for inspection; Chromium remains the acceptance browser.

### 4. Reconcile Reports and CSV with Recorded Work

- Require project task read access for every reported project. Without Read Others'
  Timesheets, include only the requesting user's work; with it, include permitted
  project work from all users. Apply these restrictions before calculating totals.
- Verify project summaries, person-by-day summaries, and task hierarchies with
  person/date filters and descendant selection. Person means the timesheet user.
- Check direct and descendant hours separately, with every entry counted once.
  For example, direct work of 1 hour on a parent, 2 on its child, and 0.5 on its
  grandchild gives the parent 1 direct hour, 2.5 descendant hours, and 3.5 total hours.
- Exclude breaks from work totals and count open entries as zero. Display decimal
  hours: six hours and thirty minutes is `6.5`. Sum original durations before rounding.
- Edit historical entries, move tasks between parents, and change a hierarchy's
  project. Reports must reflect current relationships and project attribution.
- Distinguish unrestricted whole-timesheet daily totals from project-restricted
  reports; differences must follow permissions rather than inconsistent arithmetic.
- Export all authorized task records in the requested period, independently of
  interactive report filters. Check Person, Project, Task, Date, Start Time,
  End Time, and decimal Duration. Exclude breaks and closing markers; retain open
  task records with a blank end and zero duration. Check CSV quoting and Unicode.

### 5. Complete Everyday Workflows and Preserve Data

- Exercise email/password sign-in, administrator-created accounts, catalog and
  permission management, and denial of unauthorized operations.
- Create tasks, filter multiple statuses, switch flat/hierarchical lists, drag a
  task into the timesheet, correct past work, and inspect resulting reports.
- Post remarks, verify author/timestamp and chronology, share stars between users,
  and jump from a starred remark to its original position.
- Follow references after renames, moves, access loss, and deletion. Verify image
  upload/download permissions, invalid files, and the selected size limit. Test
  screenshot pasting if implemented.
- Restart the application and verify persisted records and attachments. Exercise
  failed multi-record operations and confirm rollback without data loss.

## Verification Approach

The [reusable test setup](architecture.md#reusable-test-setup) describes
shared services, isolation, fixture/reset handling, and result capture. The
[implementation plan](implementation_plan.md#shared-test-environment) maps that
environment to each stage. Initial executable foundation checks exist; see
[README.md](README.md) for verified setup commands and the tracker for actual
results. Stage 2–4 checks passed, including two complete Stage 4 lifecycle runs
with 54 PostgreSQL tests and 16 Chromium checks each. Stage 5 also passed two full
runs with 82 PostgreSQL tests and 16 browser checks, including recording/correction engine acceptance. Stage 6 browser checks
are in progress; report and content workflow checks remain planned.

- Use focused automated tests for business rules and meaningful boundary cases.
- Run API and database integration tests against PostgreSQL, including real
  transactions and independent connections for concurrency scenarios.
- Maintain a small set of browser tests for complete critical workflows. Use
  exploratory sessions for two-tab interactions, repeated actions, stale screens,
  keyboard navigation, and recovery after failed requests.
- Use isolated synthetic data: multiple users, two organizations with several
  projects, different permission combinations, and a hierarchy at least three
  levels deep. Include several days, midnight work, open entries, and special entries.
- Control the clock and working time zone for reproducible checks. Derive expected
  results independently from small examples rather than duplicating implementation.
- For each defect, retain reproduction steps and add an appropriate regression
  check. Record the tested revision, environment, results, and known limitations.

## Completion Criteria and Boundaries

Before a version is considered ready, its critical automated checks pass against
PostgreSQL, required end-to-end workflows have been exercised, and there are no
unresolved defects that expose unauthorized data, lose records, corrupt timelines,
or produce incorrect totals. Document remaining limitations and reproduce failures
clearly. Verify startup and persistence in the deployment configuration.

Native Android/desktop clients, offline synchronization, general file attachments,
email delivery, approvals, immutable auditing, and daylight-saving behavior are
outside the first-version charter. Backup/restore acceptance checks depend on the
still-open backup responsibility and recovery requirements; the shared working
time zone is configurable through settings (UTC default).
