# Task Tracking Tool: Clarified Requirements

This document supplements `initial_project_description.md` and takes precedence
where later answers change the original requirements. Confirmed requirements below
reflect the user's answers. Proposed defaults are implementation choices for the
first version and remain open to revision.

## Confirmed Requirements

### Purpose and Scope

- A personal or small-team tool for recording work, progress, difficulties, and
  decisions. Billing and approval workflows are outside the first version.
- A modular application with a web frontend initially; other frontends may follow.
- Daily totals, project totals, and search are required. CSV export is desirable.
- Deploy on the current VDS. Backup ownership and restore procedures remain open.
- SQLite and PostgreSQL are intended database options. Equivalent workflows and a
  documented migration procedure are desirable; their implementation cost should
  be assessed before committing to the first-version scope.
- No immutable audit trail, archiving, deletion recovery, or preservation of
  deleted tasks and their history is required in the first version. Task status
  change history remains required while the task exists.

### Users and Authentication

- Users sign in using an email address and password.
- Administrators create accounts. No email delivery in the first version.
- Administrators manage permissions and catalogs such as task statuses.
- Administrative privileges do not bypass access permissions for application data.

### Tasks, Ownership, and Hierarchy

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
- Users choose project and owner independently of the parent task. The hierarchy
  may therefore span projects and owners.
- Parent time totals include time recorded directly against the parent and all
  descendants, without double counting.
- Task statuses are administrator-configured and have a `final` property, meaning
  that no further activity is planned.
- Initial statuses include In Progress, Postponed, Waiting for Customer Response,
  Canceled, and Completed. Canceled and Completed are final.
- A task may enter a final status only if every descendant is already in a final
  status, not merely its immediate children.
- Users may select multiple statuses to include in their task list, in addition
  to filtering by project and switching between flat and hierarchical views.
- A task cannot be deleted if it has any child tasks or any records in any user's
  timesheet. This restriction applies to everyone, including administrators,
  regardless of whether they can view those children or records.

### Timesheets

- Each user has a personal timesheet and can always read and modify it, including
  historical entries, even when no timesheet permissions are configured.
- Configured timesheet permissions mean Read Others' Timesheets and Write Others'
  Timesheets. They govern access to other users' timesheets only.
- Timesheet permissions cover the person's entire timesheet, including entries
  from every project, breaks, and closing markers. They are not filtered by the
  viewer's project permissions.
- Timesheet access does not grant access to referenced task descriptions or
  details. Opening a task requires separate task read permission.
- Timesheet entries must not overlap or leave unrecorded gaps within a recorded
  working session. Breaks explicitly represent time without a task.
- Users can insert, edit, and delete historical entries. Detailed adjustment
  behavior is delegated to the implementation and may change in a later version.
- Starting another entry closes the preceding entry at the new start time.
- Break is a filler entry with no associated task.
- End of Working Day closes the last entry. It does not record task work.
- When adding work after an End of Working Day marker, the application should
  advise converting that marker to a break.
- All users share a single time zone. Daylight-saving behavior is outside scope.
- Work crossing midnight is split into entries for the two calendar days.

### Permissions

- Separate permissions apply to tasks, timesheets, and task remarks.
- Each area has independent read and write flags. Read permits viewing; write
  permits supported modifications, including adding, editing, deleting, and
  modifying historical data.
- Task and remark grants are additive. An organization-level grant applies to
  every project in that organization and cannot be denied at the project level.
- Users have implicit read and write access to their own timesheet. Unset
  timesheet flags do not restrict this access.
- Read Others' Timesheets and Write Others' Timesheets apply to other users'
  whole timesheets, independently of project-level task and remark access.
  Timesheet write access permits changes to entries without granting permission
  to modify their referenced tasks.
- An unset flag means no local grant; an inherited grant can still apply.
- The underlying permission model permits write without read. The configuration
  UI should enable read when write is selected to discourage accidental use of
  that combination.
- A restricted cross-reference indicates that the referenced object exists but
  is unavailable; content access remains restricted.

### Remarks, References, and Images

- Remarks contain arbitrary text and record their author and timestamp.
- Remarks appear chronologically. Starred remarks are shared, not personal,
  and appear in a separate chronological list linking to their original position.
- Task descriptions and remarks can reference tasks and remarks.
- Tasks, descriptions, and remarks support images and screenshots, with a 2 MB
  limit per screenshot. Pasting screenshots directly is desirable.
- General file attachments may be required later.
- Reference behavior, attachment formats, and remark editing details are delegated
  to implementation judgment.

## Proposed First-Version Defaults

These defaults make the delegated behavior concrete. They are proposals rather
than additional user-confirmed requirements.

### Time Adjustment Rules

- Represent intervals as start-inclusive and end-exclusive. A boundary at 10:00
  can end one entry and start the next without overlap or a gap.
- Permit one running entry per user. Starting task work or a break closes it.
- Store chronological segments bounded by their neighboring start times and an
  optional end-of-day boundary.
- Inserting a task at 09:30 within an entry from 09:00 to 10:00 shortens that
  entry to 09:00–09:30 and assigns 09:30–10:00 to the inserted task. Later entries
  keep their start times. Historical insertion asks for a start time.
- Editing a shared boundary adjusts the end of the earlier entry and the start
  of the next together. Reject changes that create zero or negative durations
  or reorder unrelated entries. Preview affected rows before applying the edit.
- Deleting a middle entry extends its predecessor to the next boundary. If it
  has no predecessor, replace the removed interval with a break. Offer replacing
  any removed interval with a break when the preceding work did not continue.
- Adding work beyond a closed day requires an explicit conversion of the closing
  marker into a break; the break fills the interval before the new work starts.
- Times before the first entry and after a closing marker are outside the recorded
  session and do not require filler entries.
- Split overnight work at exactly midnight. The preceding day's entry ends at
  the next day's 00:00, displayed as an end-of-day boundary, and the following
  day's entry starts at that same instant. Literally ending at 23:59 would lose
  one minute and contradict the no-gap requirement.
- Exclude breaks and end-of-day markers from working-time totals.
- Apply all changes to affected entries atomically. Permit edits when the editor
  is the timesheet's user or has Write Others' Timesheets permission. Neighboring
  entries in other projects do not need separate timesheet permissions or
  permission to modify the tasks themselves.

### Hierarchy and Reporting

- Reject cycles in task hierarchies.
- Preserve the final-state invariant when adding or moving children or reopening
  descendants: affected final ancestors must also be reopened, with permission
  checks and an explicit preview of the changes.
- Allow historical time corrections on final tasks. Starting new work should
  prompt the user to reopen the task and any affected ancestors.
- Attribute project totals to the project of each recorded task. A cross-project
  parent total can differ from its own project's total.
- Restrict task and remark searches and hierarchy views to accessible data.
  Task rollups exclude inaccessible descendants and are labeled as partial.
- Whole-timesheet views, daily totals, and timesheet exports include all work
  entries when the viewer is the timesheet's user or has Read Others' Timesheets
  permission, even if some referenced tasks are inaccessible. They must not
  expose protected task descriptions, remarks, or other task details.
- A user's daily total sums work entries once; it must not sum both ancestor
  rollups and their descendant entries.

### Content and Lifecycle

- Use stable identifiers for references so renaming or moving a task does not
  break links. Show a generic unavailable label for restricted targets, without
  exposing titles, authors, snippets, or attachment previews.
- Deleted references show a generic unavailable/deleted-target placeholder.
- In an accessible timesheet, show the task label and recorded times for each
  entry. If the task is restricted, disable access to its details and show the
  access restriction when the user attempts to open it.
- Attachment access follows its containing task or remark. Downloads enforce the
  same permissions as views. Accept verified PNG, JPEG, and WebP images initially;
  use a 2 MiB (2,097,152-byte) upload limit as the interpretation of 2 MB.
- Users with remark write permission may edit, delete, or star remarks. Preserve
  the original author and creation timestamp when editing; show an edit timestamp.
  No version history is required.
- Check task deletion eligibility atomically: reject deletion if any child task
  or timesheet record references the task. Do not cascade deletion into children
  or timesheet records, including through project or organization deletion.
- For an eligible task, preview deletion of its remarks and attachments and
  require the relevant write permissions. References to the deleted task become
  unavailable. No task deletion recovery is required.
- Provide an administrator-driven password reset without email, and a local
  setup procedure to create the first administrator.

## Questions Still Open

1. The phrase "Let the system advise to change the task" in the hierarchy answer
   is incomplete. What advice or automatic suggestion was intended?
2. Which shared time zone or fixed UTC offset should be configured for deployment?
3. Who handles VDS backups, and what recovery procedure is expected?
