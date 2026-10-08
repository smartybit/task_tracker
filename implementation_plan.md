# Implementation Plan and Progress

This is the working implementation tracker. Product behavior is defined in
[requirements.md](requirements.md), technical decisions in
[architecture.md](architecture.md), and verification priorities in
[testing_charter.md](testing_charter.md). This plan defines sequencing and records
actual progress; it does not turn proposals into confirmed requirements.

## Current Position

- Last updated: 2026-10-08.
- Planning documents and the implementation roadmap are prepared.
- Application implementation has not started: 0 of 9 implementation stages complete.
- The repository currently contains documentation only. No application, database
  migrations, or executable test suite has been created or run.
- Next action: Stage 1, define the data model and API operations.

## Progress Overview

| Stage | Result | Status | Completion evidence |
| --- | --- | --- | --- |
| 1 | Data model and API operation design | Not started | — |
| 2 | Runnable application foundation | Not started | — |
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

## Stage 1: Data Model and API Operations

- [ ] Define entities and relationships for users, organizations, projects, access
  grants, tasks, statuses/history, remarks, images, and timesheet entries.
- [ ] Design email-based accounts before creating the initial user migrations.
- [ ] Define API operations for account/catalog management, task/tree changes,
  time recording/corrections, remarks, references, images, reports, and CSV.
- [ ] Define authorization checks, validation failures, and transaction boundaries
  for operations that affect multiple records.
- [ ] Work through historical insertion/deletion examples, reopening ancestors,
  project moves, and used-status immutability. Record selected implementation
  approaches in the architecture and retain the distinction from product rules.

Completion check: the design covers the agreed requirements and gives each
critical operation a clear input, result, access rule, and failure behavior.
Technical details can evolve as implementation provides evidence.

## Stage 2: Application Foundation

- [ ] Scaffold Django/REST Framework and React/TypeScript/Vite with PostgreSQL.
- [ ] Add reproducible development startup using Docker Compose, dependency
  lockfiles, configuration templates, and appropriate ignored/generated paths.
- [ ] Establish the backend modules and versioned API structure from Stage 1.
- [ ] Introduce the initial account/database migrations and a minimal frontend
  shell that can communicate with the backend.
- [ ] Set up the test harness and isolated PostgreSQL test data. Document verified
  setup, migration, build, and test commands.

Completion check: a fresh development setup starts successfully, migrations run,
the frontend reaches the API, the frontend builds, and the initial automated
checks run against PostgreSQL. No unimplemented feature is presented as complete.

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
  results and snippets.
- [ ] Verify content workflows, reference lifecycle, image validation, and direct
  access attempts using the API and browser.

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
