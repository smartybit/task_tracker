# Using Task Tracker

Everyday workflows for the current web interface. For product rules, see
[requirements](../requirements.md); for setup and account recovery, see
[development](development.md) or [deployed environments](environments.md).
Return to the [documentation index](README.md).

## Task Management

After sign-in, everyone opens **Tasks**. Administrators find account/catalog/grant
and status management under **Administration**, including **System status** for
connection checks. Colleagues can review project grants under **My access**. Task
access follows current project/organization grants. Administrators
need explicit grants to view or modify tasks. **Refresh tasks** reloads current
access and data; **Refresh access** also refreshes account/catalog management.

Use **New task** to create work in a writable project and review its preview
before confirming. Each task has an **Actions** menu for **Add subtask**, editing,
status changes, recording, ownership, moves and deletion. Add subtask preselects
the parent and project. Clicking a title opens a separate details/remarks window;
**History** opens status history. **Close details** dismisses the window; finish a
task through **Change status**. Each command has its own dialog. Use the
project/status filters and Flat/Tree view
button to find work. With status filters active, matching tasks whose parents are
excluded appear at the top level.

Status changes, moves, and deletion require a preview and confirmation. Choose a
non-final status for any final ancestors that must reopen. A move's destination
project is explicit and applies to the subtree; every owner's eligibility is
checked. Tasks with children or any recorded time cannot be deleted. A stale task
or preview retains input and requires explicit **Refresh tasks** and another
review. Changed drafts require confirmation before dismissal; acknowledged saves
with failed reloads are reported as saved and must not be submitted again.

Administrators configure statuses under **Administration → Statuses**. Once used, a status remains
protected even after its tasks change status or are deleted. Write-only project
access permits task creation with a safe acknowledgement; browsing descriptions
and lists requires task read access. Advanced write-only changes remain available
through the revision-aware API described in the domain design.

## Task Remarks

Open a task to read its remarks and shared stars. The composer sits above the
stream. **Remark order** switches between newest first (default) and oldest first;
the choice is remembered per user for the browser session. Post text above
the conversation; authorized users can edit, delete, or star any remark. Stars
link to the original remark and are visible to other readers. Edits retain the
original author and creation time and show an edit timestamp.

Remark reading requires task read plus remark read. Posting and other changes
require task read plus remark write; task write is unnecessary. Write-only remark
access offers a composer without displaying the conversation. Task deletion also
requires remark write when remarks exist and previews the number removed.

Failed writes retain text. Stale or denied writes require **Reload remarks** and
review; changed edits require confirmation before disposal. A confirmed save with
a failed reload is reported as saved. Drafts belong to the open task window;
closing or switching tasks asks before discarding changed drafts. See [the remarks API](remarks_api.md).

Descriptions and remarks offer **Insert reference** for readable tasks or remarks.
Links use stable IDs, display current labels, and open the target task or focus
the original remark. **Refresh references** checks labels and access again.
Restricted and deleted targets both display **Unavailable reference**. See
[the content API](content_api.md).

Select **Add images** or paste screenshots into a description or remark. Images
upload with the text when saved; failed writes retain pending images. Accepted
formats are static PNG/JPEG/WebP, at most 2 MiB each and five new images per save.
Remove image tokens to delete them on save. Downloads require current access to
their description or remark. Development uploads persist in a separate named
volume; include it with the database in backups.

In Tasks, **Search tasks and remarks** searches readable titles, descriptions and
remarks using English/Russian word forms, including mixed text. All query words
must match one task or remark. Results show excerpts and open the task or original
remark. Search again to refresh access/content; **Next search page** loads further
matches. Search failures retain the query and clear previous excerpts.

## Timesheet Workspace

After sign-in, the timesheet sits to the right of Tasks on wide screens and below
Tasks on narrow screens. Choose **Day** and, when permitted, **Timesheet person**.
Table start/end cells show **HH:MM**. All displayed and entered times use the
shared working zone shown in the panel; precise values remain available in editors
and are preserved when unchanged.
Daily totals cover the whole timesheet across projects; breaks and unknown ends
count zero. Task labels remain visible after task access is lost; opening their
descriptions still requires task read permission.

Drag a task into today's sheet to record at the current time, or use a task's
**Actions → Record time** command or **Record work…** to open the searchable
picker. The picker includes final tasks
and filters by project and selected statuses. Current recording against a final
task requires reopening it separately in Tasks. For historical additions, enter
**Selected-day time** explicitly; dropping a task on a past day selects it and
asks for that time. Use **Break** and **End of Working Day** to close intervals.
The recording window includes a target-session selector; days with multiple
sessions require an explicit selection. Adding after a closing
marker previews its conversion to a break before confirmation.

Starting a new day leaves older tails unfinished. Their dates appear as links;
correcting them preserves today's recording. Open **Overnight work…** and choose
**Continue previous session** for explicit overnight work; this closes the
earlier interval at the supplied
time. **Close overnight recording** closes an earlier active session today.

Click a start/end boundary to preview changing it and its neighbor together.
**Delete last record** previews deletion and extension of the predecessor; middle
corrections use **Edit day…**. The modal copies the selected day, supports arbitrary
row/session additions and removals, and highlights gaps, overlaps and incomplete
values. Time edits sort rows on blur, retaining input keys and keyboard focus.
Enter closing markers explicitly; internal gaps need Break rows. Connected
midnight edges are fixed and neighboring days are edited separately.

**Save changes** validates and writes the whole draft atomically. **Cancel** and
Escape discard locally, with confirmation for changed drafts. Failed saves keep
the draft. Stale or denied saves require explicit **Reload day and discard draft**
and review before another save; no automatic replay occurs. Reloading or leaving
the page warns about unsaved changes. Normal stale commands require **Reload
timesheet** and another review. Use **Refresh access** when access changes.
If changes were saved but reloading fails, the interface says they were saved
and requires reload/review before another attempt. Read-only colleague sheets omit editing controls;
write-without-read access remains supported through the API, because the browser
day editor needs readable rows.

## Reports and CSV Export

Select **Reports** to view project summaries, people by day, or task hierarchies.
Dates default to the current month through today in the server's configured
working time zone. Filter by inclusive dates, person, project, or a task and its
descendants. Hierarchy rows show direct, descendant, and combined hours; the
overall total counts source work once. Hours are rounded to two decimal places
after summing exact durations, and unfinished entries contribute zero.

Reports require task read access to each project. Without Read Others' Timesheets,
they include only your own work. Whole-timesheet daily totals can include work
outside readable projects, so they can differ from report totals. Administrators
have no report access bypass. Historical corrections and current task projects
and parent relationships determine later report results; use **Refresh reports**
after edits in another session.

**Download CSV** exports all authorized individual task records for the selected
dates. Person, project, and task report filters do not narrow the download. Columns
are Person, Project, Task, Date, Start Time, End Time, and Duration in decimal hours.
Breaks and closing markers are omitted; unfinished records have a blank end and
zero duration. Closed work crossing local midnight produces daily fragments.
Empty exports contain only column headings. See the
[reporting API](reporting_api.md) for routes, filter validation, and consistency.
