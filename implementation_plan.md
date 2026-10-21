# Implementation Plan and Progress

This file owns current implementation status, next actions, and remaining
completion checks. [Requirements](requirements.md) own product behavior;
[architecture](architecture.md) owns technical decisions. Use the
[documentation map](docs/README.md) to find details, and the
[archive](docs/archive/README.md) for completed-stage evidence and decision history.

## Current Position

Last updated: 2026-10-21. This is recorded project status, not a live service probe.

- Stages 1–10 are complete. UI adjustments are implemented and technically verified.
- The user authorized the evaluation UI deployment, which is complete. **Next:
  user review of the authenticated UI.** Record feedback and acceptance before
  resuming deferred production and backup/restoration work.
- Stage 11 is **Deferred** after evaluation/agent preparation. Production is not
  activated; backup tooling and full-system restoration acceptance are outstanding.
- [Operations](docs/environments.md#deployed-state-2026-10-21) owns the dated
  evaluation/agent release inventory, access details, and rollback. Subsequent
  persistent deployments require separate discussion and explicit authorization.
- Documentation reorganization is complete: the [documentation map](docs/README.md)
  guides readers and writers; dated history is separate with two-way links.
  [Preservation and verification](docs/archive/README.md#documentation-reorganization-2026-10-21)
  are recorded once in the archive.

## Latest Application Verification

These checks were performed before this documentation reorganization; they have
not been rerun for documentation-only edits.

| Scope | Recorded result | Detailed evidence |
| --- | --- | --- |
| Full clean application lifecycle | `cfb6c23`, `ui-adjustments-final-20261021`, exit 0: 146 PostgreSQL tests, fresh migrations/system/drift, frontend configuration/build, 47 Chromium scenarios; scoped cleanup | [UI verification](docs/archive/2026-10-21/ui_adjustments.md#verification-record) |
| Built prefixed deployments | `ui-adjustments-release-20261021-retry`, exit 0: three isolated Gunicorn/static-Nginx deployments, session/data/image/CSV isolation, replacement/restart persistence and sibling availability; harness correction `6bb5543` | [Built-deployment evidence](docs/archive/2026-10-21/verification_history.md#ui-adjustment-verification-2026-10-2021) |
| Authorized evaluation UI deployment | Source `1ca13e4`, exit 0: local/public HTTPS checks, Chromium sign-in rendering, unchanged domain records/migrations/database identity/uploads, agent verification | [Deployment evidence](docs/archive/2026-10-21/verification_history.md#authorized-evaluation-ui-deployment-2026-10-21) |

Authenticated user UI acceptance and production/full-system restoration acceptance
remain separate. Earlier failed/interrupted attempts are preserved in the linked
history; success of a later run does not convert them into successful checks.

## Completed Milestones

| Stage | Delivered result | Evidence |
| --- | --- | --- |
| 1 | Domain and API design | [Stage 1](docs/archive/2026-10-21/implementation_history.md#stage-1-data-model-and-api-operations) |
| 2 | Application foundation and isolated test tooling | [Stage 2](docs/archive/2026-10-21/implementation_history.md#stage-2-application-foundation) |
| 3 | Accounts, catalogs, and permissions | [Stage 3](docs/archive/2026-10-21/implementation_history.md#stage-3-accounts-and-permissions) |
| 4 | Tasks, hierarchy, statuses, and interface | [Stage 4](docs/archive/2026-10-21/implementation_history.md#stage-4-tasks-and-their-interface) |
| 5 | Timesheet engine and corrections | [Stage 5](docs/archive/2026-10-21/implementation_history.md#stage-5-timesheet-engine) |
| 6 | Timesheet interface | [Stage 6](docs/archive/2026-10-21/implementation_history.md#stage-6-timesheet-interface) |
| 7 | Reports and CSV | [Stage 7](docs/archive/2026-10-21/implementation_history.md#stage-7-reporting-and-csv-export) |
| 8 | Remarks, references, images, and search | [Stage 8](docs/archive/2026-10-21/implementation_history.md#stage-8-remarks-references-images-and-search) |
| 9 | Administrator safeguards/recovery and development acceptance | [Stage 9](docs/archive/2026-10-21/implementation_history.md#stage-9-development-completion-and-application-verification) |
| 10 | Multiple-instance prefix support | [Stage 10](docs/archive/2026-10-21/implementation_history.md#stage-10-multiple-instance-prefix-support) |
| UI follow-up | Workspace/dialog/remark-order adjustments; technical acceptance complete | [UI subplan](docs/archive/2026-10-21/ui_adjustments.md) |

## Stage 11: Production Deployment and Operational Verification

**Deferred by user decision:** resume after UI acceptance. Completed preparation
is preserved in [Stage 11 history](docs/archive/2026-10-21/implementation_history.md#stage-11-production-deployment-and-operational-verification).

- [x] Select/configure Gunicorn, static Nginx assets, and isolated evaluation/agent
  deployments, including independent release/storage configuration.
- [x] Verify startup, migrations, prefixed routing, session isolation, and database/
  image persistence through targeted replacement/restart in built deployments.
- [x] Document setup, bootstrap/recovery, startup/updates, and read-only live checks.
- [x] Activate and verify evaluation public HTTPS; retain private agent access.
- [ ] Configure and accept the public production host/proxy and activate production,
  subject to explicit target/release authorization.
- [ ] Select backup tooling, schedule, retention, and destination under the
  [agreed backup policy](architecture.md#agreed-backup-and-restoration-policy).
- [ ] Write and exercise full-system restoration on another machine from backups
  of PostgreSQL, attachments, and required configuration. Verify record/file
  consistency in isolation; named-volume persistence alone is not backup acceptance.
- [ ] Complete final critical API/database/browser and exploratory acceptance for
  production readiness, including permissions and competing edits, under the
  [testing charter](testing_charter.md#completion-criteria-and-boundaries).

Use isolated deployment-like services and synthetic data for destructive lifecycle,
upgrade, and restore checks. Never restore into live databases or attachment storage.
Completion requires passing the outstanding checks, maintained operating procedures,
and no unresolved defect that exposes unauthorized data, loses work, corrupts
records/timelines, or produces incorrect totals.

## Maintaining This Tracker

Update current status in place when work starts or reaches a verified milestone.
Use Not started, In progress, Deferred, Blocked, or Done; name any dependency and
next action. Deferred reflects an explicit user decision. Mark Done only after
completion checks pass. Keep planned tests distinct from actual results.

Keep one concise latest-evidence summary here and archive completed investigations
or detailed milestone reports. Link to the owning document for rules and runtime
state. Follow the [documentation maintenance policy](docs/README.md#write-in-the-right-place)
and commit coherent milestones under [AGENTS.md](AGENTS.md).
