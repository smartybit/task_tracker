# Environment Deployment and Operations

Current operating procedures and dated deployment inventory. Use
[the tracker](../implementation_plan.md) for outstanding acceptance and next work,
[instance design](multiple_instances.md) for routing/isolation contracts, and the
[documentation map](README.md) for related references. Earlier releases, handoffs,
and verification attempts are in the [deployment archive](archive/README.md).

| Role | Purpose | Data policy |
| --- | --- | --- |
| Production | Real work after production acceptance | Persistent; separate activation |
| Evaluation | User review of a selected release | Persistent; verification must not reset or upgrade it |
| Agent | Development/exploration with additional named environments as needed | Separate releases, secrets, and data |

Discuss persistent deployment changes and obtain explicit user authorization for
release and target. Implementation/testing completion alone does not authorize an
upgrade. Use synthetic deployment-check environments for destructive verification.

## Runtime Defaults

- Each named environment has its own Compose project, PostgreSQL database, uploads,
  network, Django secret, instance identity, and versioned image namespace.
- Gunicorn serves Django with debug disabled; non-root read-only Nginx serves built
  frontend assets and forwards matching prefixed API paths. Backend/database ports
  are not published; frontend bindings are loopback-only. Services use restart policies.
- Host Nginx handles evaluation public HTTPS; the agent stays private through SSH.
  The full application mount is preserved to the private frontend. Node/Vite
  remains confined to builds/development.
- Rebuilding an agent does not change evaluation's selected images or next restart.
  Database/upload volumes survive application container replacement; they are not backups.

## Deployed State: 2026-10-21

Last recorded verification: 2026-10-21, before this documentation reorganization.
Use `verify NAME` below to check current runtime state; this table is not a live probe.

| Environment | Recorded state | Access URL | Release | Working zone |
| --- | --- | --- | --- | --- |
| `evaluation` | UI deployed; public HTTPS verified; authenticated user review pending | `https://evaluation.example.com/time-tracker-eval/` | `ui-1ca13e4-20261021` (source `1ca13e4`) | `Asia/Tbilisi` |
| `agent` | All three services healthy; private access | `http://127.0.0.1:8182/time-tracker-agent/` | `7850df8-20261020` | UTC |
| Production | Not initialized/activated | Prefix `/time-tracker-prod/` reserved | None | Not configured |

Evaluation's private frontend listens on loopback port 8181; agent uses 8182.
Evaluation already has an administrator and user data. Do not assume fresh/empty
storage or bootstrap again. `init --zone` selects the shared IANA working zone for
a new environment (UTC default); existing configs store `WORKING_TIME_ZONE` explicitly.
Refresh browser pages after a zone change. Backend-only recreation may require a
frontend Nginx reload to refresh upstream DNS; verify afterward.

[UI deployment evidence](archive/2026-10-21/verification_history.md#authorized-evaluation-ui-deployment-2026-10-21)
records unchanged domain data, migration history, database identity, and uploads;
[HTTPS/zone history](archive/2026-10-21/verification_history.md#evaluation-public-activation-and-working-zone-2026-10-20)
records earlier activation. Production/backup/restoration acceptance remains deferred
as described in the tracker.

## Evaluation UI Rollback

The 2026-10-21 deployment retained previous application images and the private
`evaluation.before-ui.env` under ignored `.artifacts/verification/evaluation-ui-20261021/`
(mode 600). It selects `https-health-20261020` with the current HTTPS/Tbilisi settings.
Confirm the saved configuration/images still exist before an authorized rollback:

```sh
cp .artifacts/verification/evaluation-ui-20261021/evaluation.before-ui.env environments/evaluation.env
python3 scripts/environments.py up evaluation
python3 scripts/environments.py verify evaluation
```

This release introduced no backend/schema changes. The commands retain database
and uploads; they are not database restoration. Do not substitute the older
pre-HTTPS rollback configuration for a UI-only rollback. Artifact availability is
local to this server; do not publish private configuration or secrets.

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

## Host HTTPS Configuration

The maintained template is [evaluation.example.com.conf](../docker/host-nginx/evaluation.example.com.conf).
It preserves TLS/HTTP redirect handling, proxies only `/time-tracker-eval/` to
`127.0.0.1:8181` without stripping the mount, and redirects the bare mount to its
trailing slash. Application sign-in controls access; there is no extra proxy password.
The template removes obsolete project routes and allows the same 16 MiB request
body envelope as the private frontend. Per-image application limits are unchanged.

For an authorized installation/redeployment, review the template against current
host configuration and retain a backup that will not overwrite an earlier backup.
Use the maintained repository file, not a possibly expired `/tmp` copy. Installation
and reload require host administrator permissions; the original activation was
performed by the user. Validate with `sudo nginx -t` before `sudo systemctl reload nginx`.
If validation fails, restore the saved host file and validate again before reload.

After installation, run `python3 scripts/environments.py verify evaluation`, then
check browser sign-in/sign-out, slash redirect, and obsolete-route rejection. Local
fixture TLS does not establish public HTTPS acceptance. The agent URL remains
private; evaluation's HTTPS settings do not support normal sign-in over its former
HTTP SSH-tunnel URL. Historical migration and pre-HTTPS rollback commands are in
[the original handoff](archive/2026-10-21/verification_history.md#original-evaluation-https-installation-and-rollback).

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
origins are rejected. Evaluation uses public HTTPS as described above.

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

## Deployment Lifecycle Verification

`python3 scripts/check-environments.py LABEL` uses only reserved synthetic
`deployment-check-eval`, `deployment-check-agent`, and `deployment-check-extra`
configurations. It refuses pre-existing configurations, generates temporary
secrets/accounts, and uses separate Docker projects/volumes. It exercises built
assets, routing, host/CSRF enforcement, private images, same-browser sessions,
independent data/report totals, and CSV across three installations. It then
rebuilds/restarts an agent while monitoring its evaluation sibling and comparing
record/database/image snapshots. Host networking reaches only loopback test ports.

Automatic scoped cleanup removes synthetic projects/storage/configs. Logs, status,
and screenshots remain in ignored artifacts. Select checks using the
[testing charter](../testing_charter.md); results and outstanding production/restore
acceptance belong in [the tracker](../implementation_plan.md), not this runbook.

## References

- [Multiple-instance routing and trust contract](multiple_instances.md).
- [Agreed backup policy](../architecture.md#agreed-backup-and-restoration-policy).
- [Troubleshooting](infrastructure_notes.md).
- [Django deployment guidance](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Gunicorn proxy settings](https://gunicorn.org/reference/settings/).
- [Nginx proxy URI handling](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
