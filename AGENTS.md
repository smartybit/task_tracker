# Project Guidance

This project is a task and time tracker for personal use and small teams.

## Project Documents

- [requirements.md](requirements.md) is the authoritative source for purpose,
  scope, features, permissions, and business rules.
- [architecture.md](architecture.md) records the selected stack, implementation
  proposals, deployment considerations, and future frontend options.
- [testing_charter.md](testing_charter.md) defines testing priorities, meaningful
  scenarios, and completion criteria.
- [implementation_plan.md](implementation_plan.md) tracks implementation stages,
  completion checks, current progress, and remaining decisions.
- [docs/infrastructure_notes.md](docs/infrastructure_notes.md) preserves observed
  setup failures, verified fixes, and session-specific execution limitations.
  Read it before infrastructure troubleshooting or starting verification services.

Read the relevant documents before changing behavior or design. Keep agreed
requirements distinct from proposed defaults and open questions. Incorporate new
user decisions in the appropriate document and preserve existing knowledge when
reorganizing documentation. Explicit user instructions take precedence; update
the documents when those instructions change recorded decisions.

## Implementation Guidance

- Follow the selected Django/REST Framework and React/TypeScript/Vite stack in
  the architecture. PostgreSQL is the database for development, testing, and
  deployment.
- Enforce permissions, business rules, and report calculations in the backend
  so all frontends use consistent behavior.
- Preserve the distinction between whole-timesheet access and project-restricted
  reporting. Apply reporting access restrictions before calculating totals.
- Protect multi-record timesheet and hierarchy operations from partial changes
  and concurrent inconsistencies, following the architecture proposals.
- Keep changes scoped to the user's request and preserve unrelated local edits.
- Update product behavior in the requirements and technical decisions in the
  architecture; keep the testing charter aligned with both.
- Keep the implementation tracker current as work starts and verified milestones
  are reached. Record actual results, checks, blockers, and the next action; mark
  stages complete only when their completion checks are satisfied.

## Git Workflow

- Use Git to track project changes and preserve the history of decisions.
- Commit when a coherent intermediate result has been reached and can be clearly
  described, such as a completed feature, fix, or documentation update. Make these
  milestone commits without waiting for a separate commit request.
- Prefer smaller, meaningful commits throughout each implementation stage rather
  than accumulating the entire stage into one large commit. Keep each commit
  focused on a coherent result; do not split tightly coupled changes merely to
  reduce commit size.
- Use clear, descriptive commit messages that explain the concrete change and
  its purpose.
- Review the diff, check whitespace, and run verification appropriate to the
  change before committing. Stage only changes belonging to that result and
  preserve unrelated local edits.
- Keep commits local unless the user requests publishing or pushing them.

## Verification and Handoff

- Use the testing charter to select checks proportional to the change, with
  particular attention to permissions, time accounting, and data integrity.
- Use PostgreSQL for database integration and concurrency checks.
- Use verified setup and test commands from the repository once available. Add
  those instructions as application scaffolding and test tooling are introduced.
- For documentation changes, check consistency, local links, and whitespace.
- Report what changed, what was verified, and any remaining limitations. Clearly
  distinguish checks actually run from tests planned for future implementation.
