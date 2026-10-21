# UI Adjustment Subplan

Agreed 2026-10-20 after read-only review of evaluation tasks and six remarks.
The starred remark governs this objective: structure everyday task work and move
auxiliary functions into separate windows. This objective takes priority over
remaining Stage 11 production and backup/restoration work.

## Milestones

1. **Implemented; acceptance pending — Application shell:** Tasks landing screen, compact header,
   Tasks/Reports navigation, administrator management and System status grouped
   under Administration, separate My access for colleagues.
2. **Implemented; acceptance pending — Task windows:** list and right-hand timesheet on the main screen;
   native task detail, search and command dialogs; New task and Add subtask;
   status/history/ownership/move/delete commands; Close details is dismissal,
   Change status is completion. Preserve list context and protect changed drafts.
3. **Implemented; acceptance pending — Recording:** drag/drop is primary; Record work dialog is the
   keyboard/touch alternative. Historical drops require a time. Keep Break,
   End of Working Day and Edit day commands; move session/overnight controls into
   dialogs. Show HH:MM without rounding stored/editable timestamps.
4. **Implemented; acceptance pending — Remarks:** composer above stream; newest first by default with
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
- Application shell and dialog implementation compile with TypeScript/Vite.
- First focused browser pass: 8/10 passed, including complete task edit/tree,
  status/hierarchy, move/delete, stale-save, catalog and keyboard/recovery flows.
  Diagnostics retry exceeded five seconds while the frontend was refreshed;
  a revocation scenario used an immediate count during reload and skipped opening
  details. Results retained under `.artifacts/verification/ui-adjustments/`.
  The selector race is corrected and stable-source regression is in progress;
  these results are not full acceptance.

- 2026-10-21: latest source builds successfully. Nine focused browser cases pass,
  including native current-work drag/drop, multiple-session choice, unchanged
  microsecond boundary preservation, focus/draft dismissal, remark ordering and
  saved-write/reload-failure recovery. Two focused failures were a reused fixed
  account fixture (409) and task-list loading exceeding a five-second assertion;
  the latter now waits explicitly for list readiness. Full fresh-database and
  built/prefixed deployment acceptance remain pending.
- Desktop and narrow workspace/remarks screenshots were inspected. No page-width
  overflow was found. A further permission-test rerun exposed that an empty list
  has zero visible height; readiness now waits for the loaded matching-task count.
  The rerun failed and its command client reported 143; it is not acceptance.
- The permission workflow passed its corrected standalone rerun (1/1, 56.2s,
  command exit 0). The implementation milestone is ready for full clean lifecycle
  acceptance; evaluation has not been updated.
