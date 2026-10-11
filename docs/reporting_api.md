# Reporting API and CSV

Stage 7 implements the reporting rules in [requirements](../requirements.md#search-and-reporting).
Execution evidence and completion status are in the [tracker](../implementation_plan.md#stage-7-reporting-and-csv-export).

## Access and Consistency

All routes require an active authenticated user. A shared record selector requires
task read permission on the record's current project (direct or inherited from
its organization). Without Read Others' Timesheets, only the viewer's own records
are included. Task write, Write Others' Timesheets, ownership, and administrator
status do not grant report access. Apply restrictions before grouping or totals.
Whole-timesheet daily totals intentionally follow separate, broader access rules.

Each response reads current account flags, grants, task relationships, and records
under one read-only repeatable-read PostgreSQL snapshot. A change committed after
that snapshot is reflected in subsequent requests. Reads never change stored
timesheets, sessions, entries, or revisions. CSV is generated completely before
serving the file, without lazy database reads during download. Responses use
`Cache-Control: no-store`.

## Routes and Filters

Routes are relative to `/api/v1/`:

| GET route | Parameters | Response |
| --- | --- | --- |
| `reports/options/` | None | Shared `time_zone`, local `today`, `read_others_timesheets`, readable `projects` (`id`, `name`), readable `tasks` (`id`, `title`, `project`, `parent`), and permitted `people` (`id`, `name`). Includes the viewer; other people need authorized task records in a readable project, across any dates. No emails or administration fields. |
| `reports/projects/` | Required `from`, `to`; optional `project`, `person`, `task` UUIDs | `results` with project ID, `name`, and `hours`; readable projects with no matching work have zero hours. |
| `reports/people-days/` | Same | `results` with person ID, `name`, `date`, and `hours`, ordered by date/name/ID. Includes dates with zero-duration unfinished task records; does not invent empty days. |
| `reports/tasks/` | Same | A preorder hierarchy with `task`, `title`, `project`, `parent`, `depth`, `direct_hours`, `descendant_hours`, and `total_hours`. Includes readable tasks with no work as zero. Selecting a task returns its subtree with depth starting at zero. |
| `reports/records.csv` | Required `from`, `to` only | UTF-8 CSV download of individual authorized task records, including unfinished records. Person/project/task report filters are not accepted on this endpoint. |

Dates use inclusive ISO calendar dates in the configured working time zone.
UUID filters combine with AND; a selected task includes all descendants. The
person is the timesheet user, regardless of task owner. Every JSON report includes
`from`, `to`, `time_zone`, `total_hours`, and `results`. Its total sums source work
once; do not sum ancestor and descendant rollups together.

Missing/invalid/reversed ranges, malformed UUIDs, unknown parameters, and repeated
parameters return `400 invalid_input`. The maximum date `9999-12-31` is rejected
because the range needs an exclusive next-day boundary. Unavailable person,
project, or task selections return a generic `404 not_found`, including restricted
and nonexistent identifiers. Individually permitted but incompatible filters
(such as a task and a different project) produce no matching work.

## Time Accounting and CSV Format

- Sum original integer microseconds and convert to decimal hours at output,
  rounded half up to two places. Numbers are returned as decimal strings.
  The total can differ from the sum of rounded display cells or CSV durations.
- Attribute work to the task's current project and hierarchy. Historical edits,
  project moves, and parent changes affect later reports and exports.
- Closed spans are clipped to the requested period and split at local midnight,
  including older unsplit spans or spans stored before a zone change. CSV emits
  one row per resulting daily fragment, consistent with the timesheet day view.
- Unfinished task records belong to their start day, retain their start time,
  and have a blank end with zero duration. Breaks and closing markers are excluded.
- CSV columns are `Person`, `Project`, `Task`, `Date`, `Start Time`, `End Time`,
  and `Duration`. Times are local `HH:MM:SS` with fractional seconds retained when
  present. A midnight end is `00:00:00` on the next day. Names and titles use normal
  CSV quoting for commas, quotes, and newlines. No descriptions or email addresses
  are exported. Rows are ordered by stored start time, timesheet ID, and entry ID,
  with fragments of each record in chronological order.
- Downloads are named `task-records-FROM-to-TO.csv`; an empty authorized dataset
  produces a header-only file.
