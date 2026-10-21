# Documentation Map and Maintenance

Current documents describe supported behavior, selected design, operating
procedures, and outstanding work. The [project details archive](archive/README.md)
preserves how those decisions evolved and what was verified at earlier milestones.
History is not a prerequisite for ordinary work.

## Find Information for Your Task

Start with [project guidance](../AGENTS.md) and the short
[current position](../implementation_plan.md#current-position), then read only the
relevant documents and sections below. Check source code when implementation
details matter; a recorded verification result does not prove the current checkout.

| Task or question | Current authority or reference |
| --- | --- |
| What is the product supposed to do? | [Requirements](../requirements.md): scope, permissions, accounting, and agreed behavior |
| What is done, pending, blocked, or next? | [Implementation tracker](../implementation_plan.md) |
| How do I use the interface? | [User guide](user_guide.md) |
| How do I run development, bootstrap/recover accounts, or execute tests? | [Development commands](development.md) |
| How is the application structured, and why? | [Architecture](../architecture.md) |
| Which models, access gates, transactions, and shared API conventions apply? | [Domain design](domain_design.md) |
| What are the concrete API payloads? | [Timesheets](timesheet_api.md), [reports/CSV](reporting_api.md), [remarks](remarks_api.md), [references/images/search](content_api.md); accounts/tasks are in the [operation catalogue](domain_design.md#operation-catalogue) |
| What checks matter for my change? | [Testing charter](../testing_charter.md); commands live in [development](development.md#isolated-test-setup) |
| How do prefixes, routing, cookies, and isolation work? | [Multiple instances](multiple_instances.md) |
| What is deployed, and how is it operated? | [Environment operations](environments.md), including dated deployment state and rollback |
| Why did setup fail, and what is the known fix? | [Infrastructure troubleshooting](infrastructure_notes.md) |
| Why was an earlier approach changed, or what exactly passed then? | [Archive index](archive/README.md), then the linked topic/milestone |

## Write in the Right Place

- Update the document that owns the fact. Link to it from related documents;
  include a short contextual summary only when readers need it. Do not copy
  acceptance reports, release tables, or whole rules into several files.
- Current pages use topic headings and present tense. Preserve useful rationale,
  worked examples, limitations, and failure behavior. Explain surprising design
  choices where they are used; detailed chronology belongs in the archive.
- Distinguish user-agreed requirements, defaults adopted under delegated judgment,
  unselected proposals, and observed implementation. Reorganization alone must
  not promote a proposal into an agreed requirement.
- Update current status in place. Keep the next action, blocker/dependency, and
  a concise latest verification summary with a link to evidence. Do not prepend
  another session report or maintain a second progress log.
- Operating instructions contain maintained commands and prerequisites. Deployment
  state has an observation date and its own verification command; historical
  container identities and test counts do not establish live state.
- Prefer an existing page/section. Create a separate page only for a distinct
  recurring task or reference, and add it to this map. Temporary subplans have
  one status owner and are retired when their remaining work is incorporated.

## Move Details to the Archive

Archive when a milestone completes, a decision is superseded, a substantial
investigation is resolved, or a temporary plan closes. Retain useful evidence
and rationale; routine retries and command transcripts stay in ignored artifacts
or Git history. Unresolved work and currently needed instructions stay current.

1. Extract any lasting rule, rationale, fix, or command into its current owner.
   Keep the distinction between planned and executed checks.
2. Add a focused record under `docs/archive/YYYY-MM-DD/` with its date, topic,
   superseded approach/reason when relevant, source revision, checks actually run,
   results, limitations, and artifact locations. Distinguish an application defect
   from a harness failure or an unexplained interruption. Never archive secrets.
3. Link the current topic/status to the relevant archive section. Give the archive
   record a historical notice and links back to its current replacement and the
   archive index. Add one discoverable entry in that index.
4. Replace the old current narrative with the current conclusion and the link.
   Relocate incoming links to removed headings; do not leave duplicated narratives
   merely to preserve anchors. Relative links must work from the new location.
5. Check the diff for lost unique decisions, examples, evidence, and open work.
   Run `python3 scripts/check-links.py` and `git diff --check` before committing.

Archive records are historical evidence, not current instructions or authority.
Correct factual errors explicitly; do not silently rewrite old outcomes as though
they were known at the time. The initial 2026-10-21 import retains large legacy
records to preserve context; future entries should be focused milestone records,
not repeated snapshots of whole current documents.

## Keep Documentation Useful

For every documentation change, ask: does this help a future reader decide, act,
or verify? Update existing wording before adding paragraphs. Remove stale status
claims and repeated explanations in the touched area. Keep substantive examples
and boundaries even when they take space; no arbitrary word limit overrides
correctness. Review links in both directions when moving content.

Commands, policy, scope, and known limitations must remain understandable without
reading the archive. Historical logs/screenshots under ignored `.artifacts/` may
be local-only or unavailable; the committed evidence summary must stand on its own.
