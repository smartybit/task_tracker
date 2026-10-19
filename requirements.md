# Task Tracking Tool: Requirements

This is the authoritative product description and business specification. It
consolidates the original description and subsequent decisions, with later agreed
rules taking precedence over earlier versions. Agreed requirements and proposed
defaults are identified separately.

Technology choices and implementation proposals are in
[architecture.md](architecture.md). Verification priorities are in
[testing_charter.md](testing_charter.md).

## Purpose and Scope

- A personal or small-team tool for recording work, progress, difficulties, and
  decisions. Billing and approval workflows are outside the first version.
- A modular application with a web frontend initially; other frontends may follow.
- Daily totals, project totals, search, and CSV export are required in the first
  version.
- Deployment decisions and the agreed backup policy are documented in the architecture.
- No immutable audit trail, archiving, deletion recovery, or preservation of
  deleted tasks and their history is required in the first version. Task status
  change history remains required while the task exists.

## Main Features

- Organize work into tasks, projects, organizations, and task hierarchies.
- View tasks as a flat list or a tree, filtered by project and selected statuses.
- Record work in a personal timesheet and correct past entries.
- Discuss progress, difficulties, open questions, and decisions in task remarks;
  highlight important remarks with shared stars.
- Reference other tasks and remarks, and attach images in descriptions and remarks.
- Search task content and remarks, view time reports, and export individual records.
- Support multiple accounts with administrator-managed access permissions.

## Detailed Business Rules

The following requirements reflect agreed product behavior.

### Users and Authentication

- Users sign in using an email address and password.
- Administrators create accounts. No email delivery in the first version.
- Administrators manage permissions and catalogs such as task statuses.
- Administrative privileges do not bypass access permissions for application data.
- Administrators cannot deactivate themselves or remove their own administrator
  privileges. They may deactivate/reactivate another administrator or change that
  administrator's privileges. This replaces the earlier last-active-administrator
  proposal; the restriction is on self-deactivation and self-demotion.
- Provide administrator-driven password reset without email and a server-side
  command to reset the password of any existing user. Server recovery must offer
  explicit options to reactivate the selected user and grant administrator
  privileges; resetting a password alone does not change either status.
- Replacement passwords have no expiry and require no mandatory password change.
  Password resets invalidate old passwords and existing sessions. Deactivation
  invalidates existing sessions; reactivation does not restore them.
- First-administrator setup and server recovery are described in the architecture.

### Independent Instances

- Provide at least three environment roles (agreed 2026-10-19): production,
  persistent user evaluation/testing, and agent development/verification. Support
  additional agent environments when needed. Evaluation data and the selected
  evaluation release must survive work, test resets and updates in agent environments.
  Current deployment preparation targets evaluation and agent work; production
  remains a separate target.
- Support independent installations on the same hostname under different
  configurable URL prefixes, for example `/time-tracker-test/` and
  `/time-tracker-prod/` (agreed 2026-10-13). Preserve root-path hosting for existing
  development use.
- Each installation keeps its accounts, grants, application data, images and
  sign-in sessions separate. Signing out, resetting accounts or changing data
  in one instance must not change the other instance.
- All application assets, API requests, private images, downloads and generated
  links must work under the configured prefix. Prefixes do not create separate
  browser origins; separate hostnames are needed for different browser trust
  boundaries. Technical configuration and verification are described in the
  [multiple-instance design](docs/multiple_instances.md).

### Tasks, Ownership, and Hierarchy

- A task has a description, a status, and a history of status changes.
- Every task belongs to a project; every project belongs to an organization.
- The creator becomes the initial task owner.
- Ownership may be transferred. A proposed owner must have task write permission
  for the task's project. This check also applies when selecting a project.
- Ownership does not itself grant access permissions.
- An existing owner may subsequently lose access without preventing permission
  changes or causing technical problems. Keep the owner unchanged; no automatic
  reassignment, access restoration, or other resolution is required.
- An owner with neither read nor write permission cannot view or edit the task,
  even though they remain its owner. Evaluate access using current permissions,
  not ownership.
- All tasks in a hierarchy belong to the same project and therefore the same
  organization as its top-level task. Owners may differ between tasks.
- Project-based task permissions are consequently the same throughout a hierarchy.
- Parent time totals include time recorded directly against the parent and all
  descendants, without double counting.
- Task statuses are administrator-configured and have a `final` property, meaning
  that no further activity is planned.
- Initial statuses include In Progress, Postponed, Waiting for Customer Response,
  Canceled, and Completed. Canceled and Completed are final.
- Once a status has been used, it cannot be changed at all in the first version.
- A task may enter a final status only if every descendant is already in a final
  status, not merely its immediate children.
- Reopening a task also reopens any final ancestors up to the top-level task.
  Reopening does not require reopening its children or siblings.
- Users may select multiple statuses to include in their task list, in addition
  to filtering by project and switching between flat and hierarchical views.
- A task cannot be deleted if it has any child tasks or any records in any user's
  timesheet. This restriction applies to everyone, including administrators,
  regardless of whether they can view those children or records.
- Totals reflect current task properties. Moving a task hierarchy to another
  project moves its accumulated hours to that project, including historical hours.
  Changes to parent relationships also update the corresponding ancestor totals.

### Task List and Work Area

- Users can switch between hierarchical and flat task lists and filter by project.
  Multiple selected statuses determine which tasks are shown.
- A task window provides its description and a chronological remarks/chat section.
- The timesheet appears on the right-hand side of the work interface, with Task,
  Start Time, and End Time columns.
- A Day field selects the date whose timesheet entries are displayed.
- Dragging a task into the timesheet creates an entry starting at the current time
  when recording current work. Appending to a past day asks for a time on that
  selected date; middle insertion uses the Edit day dialog described below.
- Users can manually adjust entry start and end times through ordinary shared
  boundary edits or the Edit day dialog.

### Timesheets

- Each user has a personal timesheet and can always read and modify it, including
  historical entries, even when no timesheet permissions are configured.
- Configured timesheet permissions mean Read Others' Timesheets and Write Others'
  Timesheets. They govern access to other users' timesheets only.
- These flags are configured per user and grant access to any other user's
  timesheet. Individual colleague grants and employee reporting structures are
  outside the first version.
- Timesheet permissions cover the person's entire timesheet, including entries
  from every project, breaks, and closing markers. They are not filtered by the
  viewer's project permissions.
- Timesheet access does not grant access to referenced task descriptions or
  details. Opening a task requires separate task read permission.
- Task read permission is sufficient to select a task for time recording; task
  write permission and task ownership are not required. Editing existing timesheet
  records remains permitted through timesheet access if task access is later lost.
- Saved, known timesheet intervals must not overlap or leave unrecorded gaps within
  a recorded working session. Breaks explicitly represent time without a task.
  An unfinished last entry has an unknown end, not a known gap or an interval
  extending indefinitely; its interval is validated when explicitly closed.
- Users can correct historical entries through the agreed editing workflow below.
- Starting another entry in the targeted session closes that session's preceding
  entry at the new start time. Starting a separate day does not close an earlier
  unfinished day.
- A task entry with an unset end contributes zero duration to timesheets and
  reported totals until explicitly closed by a break, End of Working Day, or the
  start of another task in its session. Preserve its start time and leave its end
  unset while active or historically unfinished.
- Do not automatically infer an end time when the user logs out or leaves an
  entry running overnight. Duration is determined when the entry is closed.
- Break is a filler entry with no associated task.
- End of Working Day closes the last entry. It does not record task work.
- When adding work after an End of Working Day marker, the application should
  advise converting that marker to a break.
- All users share a single configurable time zone. Configuration in a settings
  file is sufficient; a settings UI is not required (agreed 2026-10-09).
  Daylight-saving behavior is outside scope.
- Work crossing midnight is split into entries for the two calendar days.

### Timesheet Editing

The following editing decisions were agreed on 2026-10-09. They replace the earlier
proposals for automatic middle insertion/deletion and one globally open entry.

- Ordinary timesheet controls allow appending tasks/breaks, End of Working Day,
  time-boundary edits, and deletion of the last task/break record. Middle insertion
  and deletion require **Edit day…**.
- Ordinary shared-boundary edits change the earlier end and adjoining start
  together. Reject non-positive closed durations, reordering, or overlaps; preview
  affected changes before confirmation.
- Ordinary Delete last record extends the predecessor through the removed interval.
  If the removed row has no end, its predecessor becomes the unfinished tail of
  that session; a historical correction does not replace today's active recording.
  Deleting the only row clears an independent session. Preserve connected overnight
  portions instead of removing coverage required by a neighboring day.
- Edit day opens a modal copy of the selected user's selected calendar day, using
  the usual Task / Start Time / End Time layout with breaks and closing markers.
  It is available on past days and on today while recording is active.
- In the modal, users may add, remove, and change rows and enter arbitrary start/end
  times without automatically modifying neighbors. Temporary gaps, overlaps,
  incomplete fields, and invalid durations are allowed in the draft only.
- Highlight invalid rows and gaps/overlaps. Sort rows by start time after a field
  edit completes, keeping incomplete rows at the bottom and preserving focus.
- Save changes validates the entire day draft and its connections to stored work.
  Reject invalid timelines without changing stored rows, revisions, or totals;
  otherwise save all changes together. A valid draft may retain an unfinished tail
  with an unset end and zero duration. No extra working sessions are inferred
  from gaps.
- Cancel discards the draft. Confirm dismissal when it contains changes. Preserve
  the draft after validation errors, failed requests, or concurrent-edit conflicts;
  require reload and review rather than silently overwriting newer work.
- Users may change independent session edges and clear independent days. Existing
  continuations across midnight keep their midnight boundary fixed in this one-day
  editor. Connected portions may be reassigned or replaced with breaks, but cannot
  be removed to leave a gap. Edit neighboring days separately.
- Gaps inside a session must be covered by explicit Break rows before saving.
  Time before a session's first row and after its closing marker needs no filler.
- Provide a task picker with text search and project/status filters, including
  Completed and Canceled tasks. Historical additions/corrections against final
  tasks leave their statuses unchanged. Starting new current recording against a
  final task requires a separate permitted task-reopening action.
- New task selections require current task read permission; retaining an existing
  task reference requires timesheet access, even after task access is lost.
  Timesheet access never permits opening otherwise restricted task details.
- Multi-record changes complete together or leave all affected records unchanged.
  Timesheet permissions apply across its projects; no task-write grant is needed
  to correct its retained records.

### Unfinished Days and Overnight Work

- Distinguish active recording, unfinished historical sessions, and closed sessions.
  Permit one active recording session per user and one unfinished tail per session;
  several historical days may remain unfinished.
- Starting work on a new selected day creates a separate session by default and
  marks the previous active session unfinished without supplying its missing end.
  It neither blocks new work nor fabricates work or breaks between days.
- Offer **Continue previous session…** explicitly for genuine overnight recording.
  Check the resulting timeline against other sessions before applying it. Merely
  crossing midnight does not close or otherwise change a running entry.
- An unfinished historical day remains available for ordinary end-of-session
  additions and End of Working Day, using user-supplied times on the selected date,
  or for advanced corrections through Edit day. These operations do not change
  another day's rows or the user's current recording session.
- Show an Unfinished warning for historical days with missing ends. Closed entries
  contribute their durations; the unfinished tail contributes zero until closed.
  A supplied end must not overlap later work.

### Friday-to-Monday Example

On Friday the user records a meeting 09:00–12:00, a break 12:00–12:43, and email for
Fred starting 12:43 with no end or End of Working Day. On Monday, starting new work
creates Monday's independent active session and leaves Friday unfinished.

On Monday the user selects Friday and appends a forgotten task at Friday 14:00.
The email entry becomes 12:43–14:00. Adding End of Working Day at Friday 17:00
closes the forgotten task at 17:00. Friday now has 7 hours 17 minutes of task work;
the break is excluded. Monday's rows and active recording are unchanged; no weekend
interval is invented. More involved Friday corrections use Edit day.

### Permissions

- Separate permissions apply to tasks, timesheets, and task remarks.
- Each area has independent read and write flags. Read permits viewing; write
  permits supported modifications, including adding, editing, deleting, and
  modifying historical data.
- Task and remark grants are additive. An organization-level grant applies to
  every project in that organization and cannot be denied at the project level.
- Access to task remarks requires task read permission plus the corresponding
  remark permission: remark read to view them and remark write to modify them.
  Task write permission is not needed merely to write remarks.
- Users have implicit read and write access to their own timesheet. Unset
  timesheet flags do not restrict this access.
- Read Others' Timesheets and Write Others' Timesheets apply to other users'
  whole timesheets, independently of project-level task and remark access.
  Timesheet write access permits changes to entries without granting permission
  to modify their referenced tasks.
- Each timesheet flag applies globally to all other users; it is not scoped to
  an organization, a project, or a selected colleague.
- An unset flag means no local grant; an inherited grant can still apply.
- The underlying permission model permits write without read. The configuration
  UI should enable read when write is selected to discourage accidental use of
  that combination.
- A restricted cross-reference indicates that the referenced object exists but
  is unavailable; content access remains restricted.

### Remarks, References, and Images

- Remarks contain arbitrary text and record their author and timestamp.
- Remarks appear chronologically. Starred remarks are shared, not personal,
  and appear in a separate chronological list at the top of the task window,
  linking to their original position in the main remarks stream.
- Task descriptions and remarks can reference tasks and remarks.
- Task descriptions and task remarks support inserted or attached images and
  screenshots, with a 2 MB limit per screenshot. Images are associated with those
  descriptions or remarks, without a separate standalone task attachment area.
  Pasting screenshots directly is desirable.
- General file attachments may be required later.
- Reference behavior, attachment formats, and remark editing details are delegated
  to implementation judgment.

### Search and Reporting

- Search covers tasks, their descriptions, and task remarks. Search results and
  snippets respect task and remark access permissions.
- Initial search supports English and Russian, including content that mixes the
  two languages. Additional languages may be added later.
- Implementation default in Stage 8: keyword AND semantics within one task
  (title/description) or one remark, with English/Russian word forms. Return
  readable task and remark matches separately, ranked with excerpts and navigation
  to the original. Inline target identifiers/labels and image bytes are not
  searched. Advanced query syntax and OCR remain optional.
- Report data requires task read access for its project, either granted directly
  or inherited from the organization. Read Others' Timesheets alone does not
  permit reporting on inaccessible projects.
- Without Read Others' Timesheets, reports include only the viewer's own recorded
  work. With that permission, reports may include all users' work, still limited
  to projects the viewer can read. Apply this rule to totals and person breakdowns.
- Initial report views are a project summary, a person-by-day summary, and a task
  hierarchy showing accumulated time. Views support person and date-range filters
  within the viewer's permitted data.
- Selecting a task includes its descendants. Show time recorded directly against
  the task and time recorded against descendants in separate columns. A combined
  task total includes both, without double counting.
- Display durations in decimal hours, for example `6.5` for six hours and thirty
  minutes.
- Historical project totals use the task's current project rather than its project
  at the time the work was recorded.
- First-version CSV export dumps individual authorized timesheet records for a
  selected time period, rather than exporting a filtered summary report. Do not
  apply interactive person, project, or task filters to this dump; users can
  filter the resulting file externally. Access restrictions always apply.
- CSV columns are Person, Project, Task, Date, Start Time, End Time, and Duration
  in decimal hours. Active and historically unfinished entries have a blank end
  time and zero duration.
- Task-linked CSV records require project read access and belong to the viewer
  unless the viewer has Read Others' Timesheets.
- CSV exports include task-linked records only. Breaks and End of Working Day
  markers are excluded.

## Proposed First-Version Defaults

These defaults make the delegated behavior concrete. They are proposals rather
than additional user-confirmed requirements. Remark editing defaults below have
been adopted in the Stage 8 implementation under that delegation; this does not
turn them into additional user-confirmed requirements.

### Time Representation and Closed-Day Resumption

- Represent intervals as start-inclusive and end-exclusive. A boundary at 10:00
  can end one entry and start the next without overlap or a gap.
- Adding work beyond a closed day requires an explicit conversion of the closing
  marker into a break; the break fills the interval before the new work starts.
- Times before the first entry and after a closing marker are outside the recorded
  session and do not require filler entries.
- Split overnight work at exactly midnight. The preceding day's entry ends at
  the next day's 00:00, displayed as an end-of-day boundary, and the following
  day's entry starts at that same instant. Literally ending at 23:59 would lose
  one minute and contradict the no-gap requirement.
- Apply overnight splitting when the entry is explicitly closed. Crossing midnight
  alone does not close the running entry or make it contribute recorded hours.
- Exclude breaks and end-of-day markers from working-time totals.

### Hierarchy and Reporting

- Reject cycles in task hierarchies.
- Enforce a common project throughout a hierarchy. A project change on a root
  updates the entire hierarchy together; an individual descendant cannot be moved
  to another project while it remains attached to its current parent.
- Reject reparenting across different projects unless the user explicitly chooses
  a consistent project for the moved subtree and satisfies the required task
  write permissions and owner checks. Never silently move tasks between projects.
- Preserve the final-state invariant when adding or moving children or reopening
  descendants: affected final ancestors must also be reopened, with permission
  checks and an explicit preview of the changes.
- Reopen final ancestors into a configured non-final status, leaving already
  non-final ancestors and other branches unchanged. Apply the requested change and
  ancestor changes together; leave them unchanged if a required change is denied.
- Treat status use as permanent: after first use, disallow renaming, changing the
  final flag, or deleting the status, even if no task currently uses it.
- Attribute project totals to the current project of each recorded task and
  recompute rollups after project or parent changes. Include each work entry once.
- Restrict task and remark searches and hierarchy views to accessible data.
- Task project permissions apply uniformly to every descendant in a hierarchy.
- Whole-timesheet views and their daily totals include all work entries when the
  viewer is the timesheet's user or has Read Others' Timesheets permission, even
  if some referenced tasks are inaccessible. They must not expose protected task
  descriptions, remarks, or other task details.
- Project reports and the CSV report dump additionally require project read
  access. They may therefore exclude entries visible in a whole-timesheet view.
  Clearly distinguish whole-timesheet daily totals from project-filtered report
  totals so differences are understandable.
- A user's daily total sums work entries once; it must not sum both ancestor
  rollups and their descendant entries.
- Calculate totals from original recorded durations and convert to decimal hours
  for display and export. Round only the final displayed value, rather than
  summing rounded entry values.
- Person filters refer to the user whose timesheet records the work, not the task
  owner. Changing task ownership does not reassign recorded work to another user.

### Content and Lifecycle

- Use stable identifiers for references so renaming or moving a task does not
  break links. Show a generic unavailable label for restricted targets, without
  exposing titles, authors, snippets, or attachment previews.
- Deleted references show a generic unavailable/deleted-target placeholder.
- Adopted in Stage 8 under delegated reference behavior: descriptions and remarks
  use stable inline task/remark tokens with a picker. Resolve current labels on
  access or explicit refresh; navigate to the task or original remark. Restricted
  and deleted targets share “Unavailable reference”, without revealing which case
  applies. Unknown target identifiers may be stored without an existence probe.
- In an accessible timesheet, show the task label and recorded times for each
  entry. If the task is restricted, disable access to its details and show the
  access restriction when the user attempts to open it.
- Attachment access follows its containing task or remark. Downloads enforce the
  same permissions as views. For descriptions, the containing object is the task.
  Accept verified PNG, JPEG, and WebP images initially; use a 2 MiB
  (2,097,152-byte) upload limit as the interpretation of 2 MB.
- Adopted in Stage 8 under delegated image-format details: initial images are
  static, limited to 20 million decoded pixels. Select files or paste screenshots
  into the description/remark editor; save them with the containing text. Up to
  five new images may be saved per operation, with further batches allowed.
  Failed saves retain pending images and text. Removing an image token deletes
  that source's image after a successful save.
- Adopted in Stage 8: users with task read and remark write permission may edit,
  delete, or star any remark. Task write and authorship are not required. Preserve
  the original author and creation timestamp when editing; show an edit timestamp.
  No version history is required. Shared-star changes leave the text-edit timestamp
  unchanged.
- Reject task deletion if any child task or timesheet record references the task.
  Prevent bypassing this rule through concurrent changes or indirect deletion;
  do not cascade into children or time records through project/organization deletion.
- For an eligible task, preview deletion of its remarks and attachments and
  require the relevant write permissions. References to the deleted task become
  unavailable. No task deletion recovery is required.
