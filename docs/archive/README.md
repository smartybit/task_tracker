# Project Details Archive

Historical rationale, implementation milestones, and verification evidence.
Start with the [current documentation map](../README.md) for behavior and commands,
or the [current tracker](../../implementation_plan.md) for status and next work.
Earlier stage numbers and status statements describe their recorded dates.
Archived commands and temporary paths are evidence, not maintained instructions.

## History Through 2026-10-21

Imported from repository revision `961b44a`. These frozen records preserve the
original detailed records, including failed
attempts and superseded proposals. Later dated entries can supersede earlier
ones within the same record. Their size is a one-time preservation measure;
new history follows the [archiving policy](../README.md#move-details-to-the-archive).

| Topic | Historical record | Current replacement |
| --- | --- | --- |
| Foundation, accounts, and permissions | [Stages 1–3](2026-10-21/implementation_history.md#stage-1-data-model-and-api-operations) | [Domain design](../domain_design.md), [architecture](../../architecture.md) |
| Task hierarchy and status protection | [Stage 4](2026-10-21/implementation_history.md#stage-4-tasks-and-their-interface) | [Task design](../../architecture.md#tasks-and-statuses) |
| Timesheet editing and unfinished-day decisions | [Stage 5](2026-10-21/implementation_history.md#stage-5-timesheet-engine), [Stage 6](2026-10-21/implementation_history.md#stage-6-timesheet-interface), [decision chronology](2026-10-21/implementation_history.md#progress-log) | [Requirements](../../requirements.md#timesheet-editing), [timeline semantics](../domain_design.md#timeline-semantics) |
| Reports and CSV | [Stage 7](2026-10-21/implementation_history.md#stage-7-reporting-and-csv-export) | [Reporting API](../reporting_api.md) |
| Remarks, references, images, and search | [Stage 8](2026-10-21/implementation_history.md#stage-8-remarks-references-images-and-search) | [Content architecture](../../architecture.md#remarks-and-references), [content API](../content_api.md) |
| Administrator lifecycle and recovery | [Stage 9](2026-10-21/implementation_history.md#stage-9-development-completion-and-application-verification) | [Account design](../../architecture.md#accounts-and-authentication) |
| URL prefixes and independent instances | [Stage 10](2026-10-21/implementation_history.md#stage-10-multiple-instance-prefix-support) | [Multiple instances](../multiple_instances.md) |
| Deployment preparation and live verification | [Stage 11 preparation](2026-10-21/implementation_history.md#stage-11-production-deployment-and-operational-verification) | [Operations](../environments.md), [remaining Stage 11 work](../../implementation_plan.md#stage-11-production-deployment-and-operational-verification) |
| UI feedback, implementation, and acceptance | [UI adjustment subplan](2026-10-21/ui_adjustments.md) | [User guide](../user_guide.md), [UI design](../../architecture.md#web-interface), [pending review](../../implementation_plan.md#current-position) |
| Setup investigations and verification failures | [Verification history](2026-10-21/verification_history.md) (dated headings by stage) | [Troubleshooting](../infrastructure_notes.md) |
| Evaluation HTTPS, time zone, and UI deployment | [HTTPS handoff](2026-10-21/verification_history.md#evaluation-https-handoff-2026-10-20), [zone](2026-10-21/verification_history.md#evaluation-public-activation-and-working-zone-2026-10-20), [UI deployment](2026-10-21/verification_history.md#authorized-evaluation-ui-deployment-2026-10-21) | [Current deployment and rollback](../environments.md#deployed-state-2026-10-21) |
| Retired standalone foundation commands | [Historical component verification](2026-10-21/verification_history.md#historical-component-verification) | [Development commands](../development.md) |

The complete [implementation history](2026-10-21/implementation_history.md) includes
the original stage evidence and decision log. Git retains previous document
versions and implementation diffs; it complements these readable summaries.

## Documentation Reorganization: 2026-10-21

The user requested current documents that a fresh agent can navigate efficiently,
with historical implementation details preserved separately and clear maintenance
rules against duplication. Current pages now own rules, design, procedures, and
status; this archive owns dated evidence. The old UI subplan is retained here,
with its remaining user-review step in the current tracker. No application behavior
or deployment change is part of this reorganization.

Verification for the documentation milestone (`docs: separate current guidance
from project history`):

- Compared all prose in the original implementation tracker, infrastructure notes,
  and UI subplan with their archived copies, ignoring relocated link targets and
  historical notices: preserved in full. Retired foundation commands and the
  original HTTPS handoff/rollback procedure are retained in verification history.
- Reviewed current requirements, remaining acceptance checks, design, and operating
  instructions for consistency; preserved product-rule/default distinctions and
  the pending user review/production/restoration boundaries.
- All 295 local links/anchors passed; all 21 Markdown documents are reachable
  from the documentation map. The checker now includes nested archive pages. Temporary fixture checks passed for valid two-way links, a missing nested
  target, and a missing heading. Whitespace checks passed.
- Application tests and live deployment checks were not rerun for this documentation
  change. Generated logs/screenshots referenced by older entries remain local-only
  artifacts; their availability is not guaranteed by this archive.
