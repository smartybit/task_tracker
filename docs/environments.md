# Environment Deployment and Operations

The user requested three or more independent environments on 2026-10-19:

| Role | Purpose | Data policy |
| --- | --- | --- |
| Production | Real work, after production acceptance | Persistent; separate activation |
| Evaluation | User testing and evaluation of a selected release | Persistent; agent checks must not reset or upgrade it |
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
- Loopback HTTP is for SSH-tunnel access. Public HTTPS requires an explicit origin
  and host-proxy configuration that preserves the application mount. Existing
  public host configuration is inspected but not changed during preparation.
- Named, versioned builds isolate releases: rebuilding an agent environment does
  not change evaluation images or its next restart. Updates target an explicit
  environment name. Existing disposable test projects stay separate.

These are implementation defaults, not a claim that public hosting or full
backup/restoration acceptance is complete. Verified commands, actual deployment
state and outstanding work will be recorded here as implementation progresses.

## Targeted Commands

The host needs Python 3, Docker Engine and Compose. Commands work from any current
directory when the script is addressed by its absolute path. From the repository:

```sh
python3 scripts/environments.py init evaluation --role evaluation --port 8181 --path /time-tracker-eval/
python3 scripts/environments.py build evaluation
python3 scripts/environments.py up evaluation
python3 scripts/environments.py status evaluation

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

## SSH Access

From your computer, replace `YOUR_SERVER` with your usual SSH host:

```sh
ssh -N -L 8181:127.0.0.1:8181 vasiliy@YOUR_SERVER
```

Open `http://127.0.0.1:8181/time-tracker-eval/`. Keep the local port and the
configured origin consistent. Agent access, when needed, uses another tunnel
forwarding port 8182 and `http://127.0.0.1:8182/time-tracker-agent/`.
Only the frontend is published, bound to server loopback. PostgreSQL and Gunicorn
have no host ports. SSH provides transport encryption; loopback HTTP intentionally
has non-Secure scoped cookies. Public HTTP origins are rejected. Public HTTPS
needs separate host-proxy configuration, HTTPS cookies and operational acceptance;
no public host configuration is changed by these commands.

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

Prototype startup and six host-tool tests plus three deployment-setting tests
passed. Three-environment browser/lifecycle acceptance is pending. Production is
not activated. Backup schedule/retention/destination, verified full-system restore
and final production operational acceptance remain Stage 11 work. Named volumes
provide persistence, not a backup.

## References

- [Multiple-instance routing and trust contract](multiple_instances.md).
- [Agreed backup policy](../architecture.md#agreed-backup-and-restoration-policy).
- [Django deployment guidance](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Gunicorn proxy settings](https://gunicorn.org/reference/settings/).
- [Nginx proxy URI handling](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
