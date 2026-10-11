# Timesheet API and Configuration

Stage 5 supplies the backend engine. Stage 6 adds browser recording, the
Edit day dialog and the read endpoints below (acceptance verification in progress).
Product rules remain in [requirements](../requirements.md#timesheets);
Actual verification is recorded in the [tracker](../implementation_plan.md#stage-6-timesheet-interface).

All endpoints use the existing session authentication and CSRF protection.
`{user}` is the timesheet owner's UUID, including for your own sheet. Own access
is implicit; other sheets require the independent global read/write flags.
Administrator status grants no data access. Task read is sufficient for a new
task selection. Retaining the same row's task reference requires only sheet write.

## Configuration

Set `WORKING_TIME_ZONE` to an IANA zone such as `Europe/Berlin` in `.env` (Compose)
or the backend environment. UTC is the default. Recreate the backend after changes:

```sh
docker compose up -d web
```

All users share this setting. Absolute timestamps remain unchanged when the zone
changes; known spans are split for day reads and accepted writes at the new zone's
midnights. Read-only normalization uses deterministic fragment IDs, so repeated
reads and drafts remain stable. No GET writes to the database. Unknown ends stay
unknown and contribute zero. DST-transition acceptance is outside scope.

## Directory and Recording Context

`GET /api/v1/timesheets/` returns a paginated `results`/`next` directory containing
only `id` and `display_name`. Without either global others-timesheet flag it lists
only the caller; with read or write it lists all accounts, including inactive
accounts whose historical timesheets remain accessible. Administrator status alone
never widens the directory. It does not return email or account/permission fields.

`GET /api/v1/timesheets/{user}/context/` requires whole-sheet read access. It returns
`today` in the configured shared zone, `time_zone`, `revision`, and `open_sessions`.
Each open session includes `id`, `state`, the tail's shared-zone `date`, and `tail`
with the same permitted label/timestamp fields as a day row. This supports finding
unfinished days and choosing explicit overnight continuation without a session-ID
text field. It exposes no task descriptions, creates no rows and changes no revisions.
Write-only access does not authorize reading this context.

## Read a Day

`GET /api/v1/timesheets/{user}/days/YYYY-MM-DD/` returns `date`, `revision`,
`time_zone`, `work_seconds`, `unfinished`, and `sessions`.

Each session has `id`, `state` (`active`, `unfinished`, `closed`), `rows`,
`ended_at` (the selected day's closing marker, otherwise null), and
`continues_before` / `continues_after` flags for fixed midnight connections.
Each row has `id`, `session`, `kind`, `task`, `task_label`, `task_readable`,
`started_at`, `ended_at`, and `duration_seconds`. Durations count closed task
work only; breaks and unknown tails count zero. Whole-sheet totals include every
project. Task labels are permitted, while descriptions and other task details
are never embedded; `task_readable` controls access to the separate task endpoint.

Closed work is split across calendar days. An unknown tail appears on its start
date only; it never reserves the following days. A closing marker exactly at
midnight belongs to the day that just ended.

## Commands

`POST /api/v1/timesheets/{user}/commands/` accepts `command`, `date`, and
`expected_revision`, plus the command-specific fields below. Supply offset-bearing
ISO timestamps (for example `2026-10-09T09:00:00+02:00`). Naive timestamps are
interpreted in the configured shared zone. Every successful command returns only
`user` and the new `revision`, including for callers with write without read.
Every failed command leaves rows, sheet/domain revisions, and totals unchanged.

| Command | Additional fields | Behavior |
| --- | --- | --- |
| `start` | `at`, `task` (UUID or null for a break) | Begin an independent selected-day session. Today becomes active and the prior active session becomes unfinished without a fabricated end. Historical starts are unfinished. If the day already has work, target its session instead. |
| `switch`, `append` | `session`, `at`, `task` | Close the targeted tail and begin another task/break. Historical appends use the selected date and preserve today's session. |
| `break` | `session`, `at` | Close the targeted tail and start an explicit break. |
| `end_day` | `session`, `at` | Close the tail and session together; midnight at the end of the selected date is permitted. An active overnight session may also be explicitly closed today. |
| `continue` | `session`, `at`, `task` | Explicitly continue earlier unfinished work into today, closing and splitting the previous tail. Reject overlap or another active session instead of merging sessions. |
| `resume` | `session`, `at`, `task`, confirmation fields | Convert a closed session's closing marker to a break ending at `at`, then start work. Requires preview/confirmation. |
| `boundary` | `entry`, `edge` (`start`/`end`), `at`, confirmation fields | Move the boundary and adjoining row together. Independent edges may move; midnight connections remain fixed. |
| `delete_last` | `entry`, confirmation fields | Delete only a session's last row, extending its predecessor or reopening its tail. An independent sole-row session is cleared. Connected overnight coverage cannot be removed. |
| `replace_day` | `sessions` | Atomically validate and replace the selected day using the complete draft described below. |

Each session/row identifier must belong to the targeted sheet and date. Unknown
fields and inappropriate command-specific fields are rejected. There is no
individual middle-insert/delete endpoint. Selecting a final task for active current
recording returns `task_reopen_required`; reopen through the separate authorized
task action. Historical selections and Edit day do not change task statuses.

## Preview and Confirmation

Post a `boundary`, `delete_last`, or `resume` command to
`/api/v1/timesheets/{user}/commands/preview/` first. It returns `revision`,
`domain_revision`, `user`, and `advice`. Readers also receive `before` and `after`
day data. Write-only callers receive no stored timeline content; validation errors use a generic `timeline` key instead
of stored row identifiers. Preview performs
all validation but no writes or revision increments.

Apply that command through `/commands/` with `confirm: true` and
`expected_domain_revision` from the preview. Both sheet and domain revisions and
current grants are checked under locks. Changed access/data requires a new preview.
`resume_confirmation_required` advises conversion when adding after a closing marker.

## Replace a Day

Submit every session fragment on the selected day, including rows and any closing
marker. For example, this replaces Friday with two task spans and an explicit break:

```json
{
  "command": "replace_day",
  "date": "2026-10-09",
  "expected_revision": 7,
  "sessions": [{
    "id": "00000000-0000-0000-0000-000000000001",
    "state": "closed",
    "ended_at": "2026-10-09T17:00:00Z",
    "rows": [
      {"id": "00000000-0000-0000-0000-000000000002", "kind": "task", "task": "00000000-0000-0000-0000-000000000003", "started_at": "2026-10-09T09:00:00Z", "ended_at": "2026-10-09T12:00:00Z"},
      {"client_key": "break-added", "kind": "break", "task": null, "started_at": "2026-10-09T12:00:00Z", "ended_at": "2026-10-09T12:43:00Z"},
      {"client_key": "work-added", "kind": "task", "task": "00000000-0000-0000-0000-000000000003", "started_at": "2026-10-09T12:43:00Z", "ended_at": "2026-10-09T17:00:00Z"}
    ]
  }]
}
```

Use real retained session/row IDs from GET; omit `id` for new sessions/rows and
provide a stable `client_key` for associating errors. Submit only editable fields:
session `id`/`client_key`, `state`, `ended_at`, `rows`; row `id`/`client_key`, `kind`,
`task`, `started_at`, `ended_at`. Derived GET labels/flags are not accepted inputs.
Rows may arrive unsorted; validation checks the complete chronological timeline.

Omit an independent session to remove it; an empty `sessions` clears an independent
day. Known durations must be positive, adjoining boundaries must match, and internal
gaps need explicit breaks. The command never infers sessions or repairs neighbors.
An active/unfinished session must have exactly one unknown-end last row. A closed
session needs a matching closing marker. Incoming/outgoing midnight connections
and neighboring fragments are fixed; their task attribution may change. Historical
drafts cannot take over the active recording session. Retained row IDs survive saves.

`invalid_timeline` returns `fields` keyed by a retained row ID, supplied client key,
session ID, or `timeline`. Structural input errors use field/index paths. A stale
revision returns `409 stale_revision`. Clients must keep the draft and require reload
and review; do not automatically replay it. Cancel is local and makes no request.
