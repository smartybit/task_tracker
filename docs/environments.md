# Environment Deployment and Operations

The user requested three or more independent environments on 2026-10-19:

| Role | Purpose | Data policy |
| --- | --- | --- |
| Production | Real work, after production acceptance | Persistent; separate activation |
| Evaluation | User testing and evaluation of a selected release | Persistent; agent checks must not reset or upgrade it; release updates require separate user authorization |
| Agent | Development, exploration and verification | Separate data; additional named environments may be created |

This Stage 11 milestone prepares evaluation and agent deployments. Production
activation and full Stage 11 operational acceptance remain separate work.

## Selected Implementation Defaults

- One Compose project per named environment, with its own PostgreSQL database,
  uploads, network, Django secret and image namespace.
- Gunicorn runs Django with debug disabled. A separate Nginx container serves the
  built frontend and forwards only the matching prefixed API paths. Node/Vite
  development servers remain available through the existing development setup.
- Evaluation uses `/time-tracker-eval/` on loopback port 8181; the first persistent
  agent environment uses `/time-tracker-agent/` on loopback port 8182. Production
  reserves `/time-tracker-prod/`; it is not activated by this milestone.
- Evaluation uses the public origin `https://evaluation.example.com`, Secure cookies and the
  existing application login (agreed 2026-10-20). Host Nginx must preserve the full
  mount when forwarding to loopback. Its replacement is prepared in `/tmp` for
  administrator installation; `/etc/nginx` is not changed by this preparation.
  Agent retains loopback HTTP and SSH-tunnel access.
- Named, versioned builds isolate releases: rebuilding an agent environment does
  not change evaluation images or its next restart. Updates target an explicit
  environment name. Existing disposable test projects stay separate.

Evaluation public HTTPS is active and verified after the administrator's
installation. Full backup/restoration and production acceptance remain separate
Stage 11 work.

Discuss a persistent deployment before applying it and obtain explicit user
authorization for the release and target. Implementation/testing alone does not
authorize deployment (confirmed 2026-10-21).

## Deployed State: 2026-10-21

| Environment | State | Access URL | Release |
| --- | --- | --- | --- |
| `evaluation` | UI adjustments deployed; all services healthy; public HTTPS verified | `https://evaluation.example.com/time-tracker-eval/` | `ui-1ca13e4-20261021` |
| `agent` | All three services healthy | `http://127.0.0.1:8182/time-tracker-agent/` | `7850df8-20261020` |
| Production | Not initialized or activated | Reserved for later setup | None |

At initial deployment both environments had fresh migrated databases and empty
account, task and image tables; this is historical evidence, not an assumption
for future checks. Initial statuses are installed by migrations. Run the bootstrap
command below if you have not yet created your evaluation administrator.
Evaluation's working time zone is `Asia/Tbilisi` (UTC+4), selected for Tbilisi/Yerevan
on 2026-10-20; agent remains UTC. `init --zone` selects an IANA zone for a new
environment, defaulting to UTC. Existing configurations store `WORKING_TIME_ZONE`
explicitly. Refresh open browser pages after a working-zone change.

The six intended services use restart policies and separate persistent volumes.
Final read-only checks confirmed loopback-only frontend bindings, no published
database/backend ports, built assets and metadata, rejected unknown hosts/missing
assets, non-root read-only application containers, and debug disabled. Safe
deployment evidence is retained in ignored
`.artifacts/verification/stage11-persistent-deployment-20261020.json`.
The two existing downloader containers and original volumes were preserved.

The HTTPS follow-up built evaluation-only release `https-health-20261020` from
health-check fix `b6f8dca` and recreated only evaluation's backend/frontend.
Four deployment regression tests passed without database setup. A temporary local
HTTPS proxy using the staged routing passed the deployment checks, redirects,
obsolete-route rejection, Secure CSRF cookies, anonymous protection and CSRF
enforcement; Chromium rendered the sign-in form and connected-database status.
No evaluation account was created and authenticated sign-in/sign-out is left to
the operator. All other container IDs and host Nginx file hashes were preserved;
`verify agent` passed. Safe results and the inspected screenshot are under
`.artifacts/verification/evaluation-https-20261020/`.

The first public verification reached the old host's 404 before installation.
After the user installed the host configuration and loaded the interface, the
standard public `verify evaluation` passed, including trusted HTTPS and real
frontend/API/PostgreSQL checks. The user created an administrator and initial
organization/project; list/detail API handlers confirmed their relationship in a
read-only transaction. Password login was not automated by the agent.

The 2026-10-20 time-zone update changed only evaluation's `WORKING_TIME_ZONE` from
UTC to `Asia/Tbilisi`. Its backend was recreated using the same release and its
existing frontend Nginx was gracefully reloaded to refresh upstream DNS. Runtime
`TIME_ZONE` and the +14,400-second offset were confirmed; both standard environment
verifiers passed. No build, migration or application-record write was performed.
Only evaluation's backend container ID changed. Private rollback configuration
and safe results are under `.artifacts/verification/evaluation-tbilisi-20261020/`.

After an intermediate readiness discussion and explicit user authorization on
2026-10-21, evaluation was upgraded to UI source `1ca13e4`, release
`ui-1ca13e4-20261021`. Its backend/frontend were rebuilt and recreated using the
standard environment manager. The migration check reported no migrations to apply.
Read-only before/after fingerprints confirmed unchanged domain records, migration
history, database identity and upload bytes. Evaluation's database container,
agent and unrelated container identities were preserved. All configuration except
the release selection is unchanged, including public HTTPS, Secure cookies and
`Asia/Tbilisi`.

Standard evaluation verification passed through loopback and actual public HTTPS;
agent verification passed. Chromium displayed the new compact public sign-in UI
without JavaScript errors or automatic connection diagnostics. No account login,
seed, reset or application-record write was performed. Prior full regression and
three synthetic prefixed-deployment results are in the
[UI subplan](ui_adjustment_plan.md). User review of the authenticated UI is next;
remaining Stage 11 production and backup/restoration work stays deferred.

Safe deployment results, fingerprints and the public sign-in screenshot are under
`.artifacts/verification/evaluation-ui-20261021/`. The private rollback config is
`evaluation.before-ui.env` in that directory (mode 600); it retains the previous
`https-health-20261020` release, HTTPS settings and Tbilisi zone. Both previous
application images remain available. If rollback is needed, restore only this
configuration and restart evaluation with the standard commands:

```sh
cp .artifacts/verification/evaluation-ui-20261021/evaluation.before-ui.env environments/evaluation.env
python3 scripts/environments.py up evaluation
python3 scripts/environments.py verify evaluation
```

This UI rollback does not restore the database or uploads; the release introduced
no backend/schema changes. Do not use the older pre-HTTPS rollback configuration
for a UI-only rollback.

## Targeted Commands

The host needs Python 3, Docker Engine and Compose. Commands work from any current
directory when the script is addressed by its absolute path. The following is the
initial setup sequence; `evaluation` and `agent` are already initialized and
running on this server, so use `status` or `bootstrap` for them:

```sh
python3 scripts/environments.py init evaluation --role evaluation --port 8181 --path /time-tracker-eval/ --origin https://evaluation.example.com
python3 scripts/environments.py build evaluation
python3 scripts/environments.py up evaluation
python3 scripts/environments.py status evaluation
python3 scripts/environments.py verify evaluation

python3 scripts/environments.py init agent --role agent --port 8182 --path /time-tracker-agent/
python3 scripts/environments.py build agent
python3 scripts/environments.py up agent
```

`init` creates unique secrets in `environments/NAME.env` (mode 600, directory
mode 700). This entire directory is excluded from Git and Docker build contexts.
It refuses existing files, shared ports/secrets/identities and overlapping mounts.
It also refuses to register an identity already used by Docker containers,
networks or volumes, and refuses operations on a project owned by another workspace.
`list` and `check NAME` show safe metadata without printing secrets. Shell variables
cannot override the selected environment configuration.

`build NAME --release NEW_TAG` builds only that environment's image namespace.
An already completed release cannot be overwritten. Building selects a release
but does not restart services; `up NAME` applies it. `up` starts the database,
stops only the selected application's services, runs migrations using its selected
image, then starts the backend/frontend and waits for health. It never seeds data.
If migration fails, that environment's application stays stopped for operator
recovery; automatic schema rollback is not attempted. Back up important data
before schema-changing updates. `down NAME` retains its database and upload
volumes and offers no volume-deletion option.

To add another independent agent environment:

```sh
python3 scripts/environments.py init agent-2 --role agent --port 8183 --path /time-tracker-agent-2/
python3 scripts/environments.py build agent-2
python3 scripts/environments.py up agent-2
```

Names are explicit on every operation. An agent build/reset/restart must target an
agent environment, never evaluation or production. The original `scripts/test.sh`
and prefix fixtures remain disposable synthetic projects, separate from these
persistent environments. `logs NAME` returns bounded recent service logs.

## Verify a Running Deployment

After startup, an update or a restart, run:

```sh
python3 scripts/environments.py verify evaluation
python3 scripts/environments.py verify agent
```

`check NAME` validates configuration, `status NAME` lists services, and `verify NAME`
checks the existing deployment. Verification returns 0 after all checks pass;
a failed check prints the reason and returns nonzero. It never starts, restarts,
migrates or seeds services, and makes no application data changes. Existing
accounts/records, additional environments and any configured working time zone
are supported. Service access logs can record its GET requests.

Checks cover all three services' health/restart policies, the selected application
release, loopback-only frontend bindings, unpublished backend/database ports,
environment-owned persistent volumes, and non-root/read-only restricted application
containers. A whitelist of Django settings is compared with the configuration,
including identity, role, zone, debug, cookie paths/security and trusted origin;
the probe prints only those settings, with no account/task/image queries or
secret output.
The command then checks built HTML/assets and caching, instance metadata,
API/backend identity and PostgreSQL health, missing-asset rejection and local
unknown-host rejection.

HTTP probes reach the loopback frontend directly. When the configured public
origin differs, it must also be reachable and pass the frontend/API checks;
HTTPS uses certificate validation. Redirects and assets outside the configured
mount are rejected. HTTP requests use a 10-second socket timeout and an 8 MiB response
limit; Docker inspection/settings commands have 30-second timeouts. A release
selected by `build` but not applied by `up` is reported as a mismatch.

This is a deployment health/configuration check. Authentication, permission
matrices, concurrent edits, image/CSV behavior, cross-instance isolation and
restart persistence remain covered by the existing regression/lifecycle suites.
Backup/restoration acceptance remains separate. The old one-off `/tmp` checks are
not needed to operate or verify deployments.

Host tooling tests, including local HTTP fixtures, run with:

```sh
python3 -m unittest discover -s scripts -p test_environment_tools.py -v
```

These tests need permission to bind ephemeral loopback sockets and do not need
Docker or change deployed services.

## Activate Evaluation HTTPS (Administrator Handoff)

The evaluation runtime is configured for HTTPS at
`https://evaluation.example.com/time-tracker-eval/`, with persistent storage and corrected
release `https-health-20261020`. The fix makes the internal HTTP health-check
exemption account for the URL prefix under HTTPS; the original release remains
available for rollback. Host Nginx has now been activated by the user and public
verification passes; the installation steps below are retained for redeployment.
The old HTTP SSH-tunnel URL no longer supports normal sign-in with these settings.

The reviewed replacement is `/tmp/sites-available/evaluation.example.com`; the maintained
copy is [docker/host-nginx/evaluation.example.com.conf](../docker/host-nginx/evaluation.example.com.conf).
It removes both obsolete project locations, preserves Certbot/TLS and the HTTP
redirect, and proxies only `/time-tracker-eval/` to `127.0.0.1:8181` without stripping
the prefix. The no-slash path redirects to the canonical trailing slash. Existing
application authentication controls access; there is no extra proxy password.

On the server, run with administrator permissions:

```sh
sudo cp -a /etc/nginx/sites-available/evaluation.example.com /etc/nginx/sites-available/evaluation.example.com.before-time-tracker
sudo cp /tmp/sites-available/evaluation.example.com /etc/nginx/sites-available/evaluation.example.com
sudo nginx -t
```

Keep the backup from the first installation; do not overwrite it on retries.
Only if the validation succeeds:

```sh
sudo systemctl reload nginx
cd /home/vasiliy/Projects/task_tracker
python3 scripts/environments.py verify evaluation
```

Open **https://evaluation.example.com/time-tracker-eval/** in your browser. If needed, run
`python3 scripts/environments.py bootstrap evaluation` in your server terminal
first: enter your email and use the generated password printed there. If you
already have an administrator, use its existing credentials. No account is created
automatically by the HTTPS preparation. No SSH tunnel is needed for evaluation.
After activation, check sign-in/sign-out, the slash redirect and rejection of
the removed project paths. The live verifier checks trusted HTTPS and built
frontend/API health without changing application records.

If `nginx -t` fails, do not reload. Restore the saved file and validate again.
To undo a successfully applied host route, restore and reload:

```sh
sudo cp /etc/nginx/sites-available/evaluation.example.com.before-time-tracker /etc/nginx/sites-available/evaluation.example.com
sudo nginx -t
```

Only after successful validation, run `sudo systemctl reload nginx`.
To also restore evaluation's previous SSH-access settings, from the project root:

```sh
cp .artifacts/verification/evaluation-https-20261020/evaluation.before-https.env environments/evaluation.env
python3 scripts/environments.py check evaluation
python3 scripts/environments.py up evaluation
python3 scripts/environments.py verify evaluation
```

The private backup retains the original secrets and release; it is ignored by
Git. Do not publish it. Runtime rollback retains database/upload volumes and runs
the normal migration check for the unchanged release. After rollback the original
SSH tunnel URL can be used again.

## Agent SSH Access

From your computer, replace `YOUR_SERVER` with your usual SSH host:

```sh
ssh -N -L 8182:127.0.0.1:8182 vasiliy@YOUR_SERVER
```

Open `http://127.0.0.1:8182/time-tracker-agent/`. Keep the local port and the
configured origin consistent.
Only the frontend is published, bound to server loopback. PostgreSQL and Gunicorn
have no host ports. SSH provides transport encryption; loopback HTTP intentionally
has non-Secure scoped cookies in the private agent environment. Public HTTP
origins are rejected. Evaluation uses the HTTPS handoff above.

## First Administrator

After starting an environment, run this from the server terminal:

```sh
python3 scripts/environments.py bootstrap evaluation
```

By user decision, this asks for the email interactively, generates a strong
password and prints the URL, email and password only after successful account
creation. It refuses once an administrator exists. No account is created during
deployment preparation. The existing backend bootstrap command remains available
for operators who want to supply a password interactively instead.

Recovery remains explicitly targeted:

```sh
python3 scripts/environments.py reset-password evaluation --reactivate --grant-admin
```

This asks for the email and delegates hidden password entry to the backend.
`--generate-password` instead prints a generated replacement after success.

## Verification and Remaining Work

`python3 scripts/check-environments.py LABEL` reserves only the synthetic
`deployment-check-eval`, `deployment-check-agent` and `deployment-check-extra`
configurations. It refuses pre-existing configurations, generates temporary
secrets/accounts and uses separate Docker projects/volumes. It exercises real
built assets, routing, host/CSRF enforcement, private images, same-browser sessions,
independent data/report totals and CSV downloads across three installations.
It then rebuilds/restarts only an agent while monitoring evaluation and comparing
database/domain/image snapshots. Automatic cleanup removes only those reserved
synthetic projects/storage. Logs/status and screenshots stay in ignored artifacts.
The browser uses host networking solely to reach the loopback-only test ports.

On application/tooling source `7850df8`,
`stage11-environments-20261020-2` exited 0. All three deployments passed startup,
interactive bootstrap and duplicate refusal, the browser checks above, and
session/data/image/report preservation after agent replacement and restart.
Evaluation stayed healthy across 95 observations; its containers and the third
environment's containers were unchanged. Synthetic resources were fully removed.
Screenshots of the independent 1.00/2.00/3.00-hour totals were inspected.

Six host-tool tests passed. `stage11-root-focused-20261020` also exited 0:
fresh PostgreSQL migrations, system/drift checks and 28 authentication,
administration/concurrency, deployment-setting and prefix/WSGI tests passed
(79.493 seconds for the tests). Its disposable services were removed.

Production is not activated. Backup schedule/retention/destination, verified
full-system restore and final production operational acceptance remain Stage 11
work. Named volumes provide persistence, not a backup.

## References

- [Multiple-instance routing and trust contract](multiple_instances.md).
- [Agreed backup policy](../architecture.md#agreed-backup-and-restoration-policy).
- [Django deployment guidance](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Gunicorn proxy settings](https://gunicorn.org/reference/settings/).
- [Nginx proxy URI handling](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
