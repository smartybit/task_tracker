# UI Adjustment Subplan

Agreed 2026-10-20 after read-only review of evaluation tasks and six remarks.
The starred remark governs this objective: structure everyday task work and move
auxiliary functions into separate windows. This objective takes priority over
remaining Stage 11 production and backup/restoration work.

## Milestones

1. **In progress — Application shell:** Tasks landing screen, compact header,
   Tasks/Reports navigation, administrator management and System status grouped
   under Administration, separate My access for colleagues.
2. **Pending — Task windows:** list and right-hand timesheet on the main screen;
   native task detail, search and command dialogs; New task and Add subtask;
   status/history/ownership/move/delete commands; Close details is dismissal,
   Change status is completion. Preserve list context and protect changed drafts.
3. **Pending — Recording:** drag/drop is primary; Record work dialog is the
   keyboard/touch alternative. Historical drops require a time. Keep Break,
   End of Working Day and Edit day commands; move session/overnight controls into
   dialogs. Show HH:MM without rounding stored/editable timestamps.
4. **Pending — Remarks:** composer above stream; newest first by default with
   oldest-first option remembered per user for the browser session. Shared stars
   remain chronological and links focus originals in either stream order.
5. **Pending — Acceptance:** browser workflows, precision/permission/stale/failure
   regressions, responsive screenshots, production build, prefixed hosting and
   complete isolated regression lifecycle. Record actual evidence below.

## Implementation constraints

Use existing backend APIs and permission/revision/transaction rules, with no
schema or dependency changes expected. Use one active native modal, preserve
failed drafts, confirm changed-draft dismissal, restore focus, and distinguish
confirmed writes from subsequent reload failures. Preserve existing UTC and
configured working-zone behavior. Stack the workspace on narrow screens.

Evaluation records and its release must not be changed by development or tests.
Use agent/synthetic environments. Prepare a verified release for review; updating
evaluation is a separate deployment action.

## Verification record

- Planning: three tasks and six remarks reviewed in a PostgreSQL read-only
  transaction. No evaluation records changed.
- Implementation started; runtime acceptance has not yet run.
