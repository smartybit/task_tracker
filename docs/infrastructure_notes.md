# Infrastructure Troubleshooting

Read before infrastructure troubleshooting or starting verification services.
Use [development commands](development.md) and [environment operations](environments.md)
for maintained procedures. This page preserves actionable lessons; detailed
attempts, outcomes, and former session restrictions are in the
[verification archive](archive/2026-10-21/verification_history.md).
Current execution permissions and service state must be checked in the current session.

## Docker Access and Process Supervision

**Symptom:** Docker/socket, Git index, buildx cache, or loopback-listener access fails
inside an agent session despite working in the user's terminal.

**Cause/fix:** Earlier failures were execution restrictions, not broken host Docker
or group configuration. Use the session's authorized escalation path when needed;
prior success of `docker info` or a build does not establish lifecycle/cleanup
access. Do not change socket permissions, add privileged helper containers, or
mount the daemon socket to route around restrictions. The read-only
`bash scripts/docker-diagnostics.sh` helper bounds individual probes; its final
exit status alone does not prove daemon access.

**Verify:** Confirm the needed command and scoped cleanup are permitted before
starting services. See [access findings](archive/2026-10-21/verification_history.md#docker-access-is-session-specific).

**Symptom:** A test client exits 130/143, a shell stops in job-control state `T`,
or no runner status file appears while a browser still runs.

**Fix:** Use the [foreground test wrapper](development.md#verification-helpers)
with closed stdin and GNU `timeout --foreground`. Detached `nohup`/`setsid` probes
were unreliable in earlier sessions. Keep build inputs stable during checks; editing
a running shell script previously caused exit 127. Do not run competing browser
suites, rebuild frontend sources, or tear down a stack while its browser is active.

**Verify:** Require the wrapper's recorded completion/exit status plus inspected
cleanup. Passing component output or service health is not successful lifecycle
acceptance. Codes 124/143 or a missing status file need inspection; do not infer
an application defect or a successful run. See
[runner findings](archive/2026-10-21/verification_history.md#stage-4-verification-findings-2026-10-09)
and [stable-input findings](archive/2026-10-21/verification_history.md#stage-10-verification-findings-2026-10-13).

## Cleanup and Fixture Isolation

- `docker run --rm` removes an exited container; it does not stop an indefinite
  server. Compose cleanup may leave a running one-off browser and its network.
  Inspect exact project-labelled containers/networks/volumes after interruptions.
  Stop/remove only owned test resources; never use broad prune or live-volume removal.
- Use the reserved synthetic test/prefix/deployment project names from the maintained
  helpers. Record the relevant current baseline before lifecycle checks; historical
  container IDs, counts, and free ports are not future-state guarantees.
- Test settings require `APP_ENV=test`, database/user `task_tracker_test`, and
  temporary uploads. Django tests create `test_task_tracker_test`; browser fixtures
  use the separately migrated `task_tracker_test`. Guarded commands refuse development
  settings. Run shared-stack suites sequentially.
- Give scenarios independent synthetic users. Do not grant application-data access
  to the shared fixture administrator or alter another scenario's credentials.
  Reusing fixed accounts without reset can produce 409 fixture conflicts.
- Inspect preserved database identity/records and image bytes for lifecycle checks;
  a retained volume name alone does not establish data preservation.

[Cleanup history](archive/2026-10-21/verification_history.md#establish-cleanup-before-starting-services)
and [fixture contamination](archive/2026-10-21/verification_history.md#stage-8-remarks-verification-findings-2026-10-12)
explain the corresponding failures.

## Build, Dependencies, and Proxy Readiness

| Symptom | Known cause/fix | Verification |
| --- | --- | --- |
| Vite temporary-config `EACCES` | Own writable build locations as the non-root node user; preserve `COPY --chown` and `/app` ownership | Non-root build/start succeeds; do not make the tree world-writable |
| pip-tools cache failure at `/.cache` | Use a tool-specific writable cache such as `/tmp/pip-cache` and `PYTHONUSERBASE=/tmp/pip-tools` under Python 3.13 | Regenerate hashed locks with the selected runtime |
| Host Node/npm unavailable | Use existing Node/build and Playwright containers | Align Playwright package/image versions; a non-failing esbuild warning is not permission to enable every install script |
| Internal Compose hostname rejected | Align Vite `allowedHosts` and Django/CSRF trusted origins with actual service/browser origins | Check actual proxy mutations, not just loopback health; retain host/CSRF protection |
| Missing JavaScript returns HTML/200 | Disable SPA fallback for the fragment-navigation application (`appType: mpa`) | Missing assets/unknown paths remain 404 under root and prefixed mounts |
| Gunicorn settings rejected | Validate `forwarder_headers` as the installed version expects; its empty value is a string | Deployment build validates Gunicorn configuration |
| Read-only Nginx fails startup | Put client/proxy/fastcgi/uwsgi/scgi temp paths under `/tmp`; quote comma-containing Compose tmpfs flow-list values | Actual built frontend health/startup passes |
| Private frontend readiness gets host rejection | Send the configured public Host to Django, not internal `web` | Readiness succeeds without widening allowed hosts |
| HTTPS backend health redirects | Match the exact configured script prefix in the security redirect exemption | Root/prefixed/nested health works while other HTTP paths still redirect |
| Backend-only recreation leaves stale Nginx upstream | Reload the existing frontend to refresh upstream DNS | Verify the selected environment afterward |

See [build findings](archive/2026-10-21/verification_history.md#non-root-frontend-files-must-be-writable),
[deployment setup](archive/2026-10-21/verification_history.md#stage-11-environment-preparation-2026-10-1920),
[HTTPS fix](archive/2026-10-21/verification_history.md#evaluation-https-handoff-2026-10-20),
and [zone update](archive/2026-10-21/verification_history.md#evaluation-public-activation-and-working-zone-2026-10-20).
Staged TLS with a fixture certificate does not prove public HTTPS activation;
use the maintained live verifier after host installation.

## PostgreSQL, Migrations, and Streaming Tests

- Create schema migrations before dependent data migrations; never rewrite applied
  migrations to repeat an initial scaffolding fix. Account command guards depend
  on app ordering before Django auth.
- Transaction-test flush can remove the seeded domain lock. Restore it in fixtures.
  Historical upgrade models must include compatible latest migrations for other
  apps, such as the account session-version field.
- PostgreSQL activity checks can retain a statistics snapshot. Call
  `pg_stat_clear_snapshot()` before sampling lock waits; use independent connections,
  explicit synchronization, bounded waits, and committed-state assertions.
- Use real transactions for streaming `FileResponse` lifecycle and after-commit
  file cleanup. Closing a response can close the database connection, breaking
  queries inside a wrapping `TestCase` transaction.
- Strict serializer non-object errors must use the expected error-dictionary shape;
  verify actual 400 responses for arrays/scalars, not only raised domain exceptions.

See [migration guards](archive/2026-10-21/verification_history.md#django-migration-ordering-and-test-guards),
[timeline fixtures](archive/2026-10-21/verification_history.md#stage-5-verification-findings-2026-10-09),
[lock sampling](archive/2026-10-21/verification_history.md#stage-3-verification-findings-2026-10-08),
and [streaming checks](archive/2026-10-21/verification_history.md#stage-8-references-and-images-2026-10-12).

## Browser Fixtures and Drafts

- Prefer accessible role/name locators for wrapped selects and prefilled textareas;
  exact label queries can include options/initial content.
- Await meaningful readiness before editing: loaded task count for empty lists,
  initial report table/options before dates, and current-recording controls before
  timestamps. Increasing arbitrary timeouts does not fix an obsolete state assumption.
- After password reset/deactivation, reload and assert sign-in; an in-flight request
  may already have removed Refresh access. Await the mutation response separately
  from its UI completion message.
- Native datetime-local fields must lose all segment focus before blur/sort assertions;
  Chromium can omit zero seconds. Verify retained timestamp precision separately.
- Plain HTTP Compose hosts may lack `crypto.randomUUID()`. Draft keys use local
  counters/timestamps; image UUIDs use `crypto.getRandomValues`. Settle FileReader
  failure/abort paths so uploads cannot remain pending indefinitely.
- Scroll lazy images into view and await decoded width. Use the visible drag/drop
  target and assert the resulting row. Close details before a reload when the fresh
  page opens the task list. Test keyboard/focus behavior at desktop and narrow sizes.
- Keep pending image bytes in the parent draft across permission-driven unmounts.
  Stale edits retain drafts until explicit refresh; saved-but-reload-failed needs a
  different assertion from failed save. Neither case should silently resubmit.

See [timesheet browser findings](archive/2026-10-21/verification_history.md#stage-6-verification-findings-2026-10-11),
[image findings](archive/2026-10-21/verification_history.md#stage-8-references-and-images-2026-10-12),
and [UI verification](archive/2026-10-21/verification_history.md#ui-adjustment-verification-2026-10-2021).
Add future actionable fixes here; archive the completed investigation using the
[maintenance policy](README.md#move-details-to-the-archive).
