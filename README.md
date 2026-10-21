# Task Tracker

Personal and small-team task/time tracking, built with Django/REST Framework,
React/TypeScript/Vite, and PostgreSQL.

The application supports task hierarchies and statuses, project permissions,
personal and colleague timesheets, historical corrections, reports/CSV, remarks,
shared stars, references, private images, and English/Russian search. Accounts are
administrator-managed; there is no public registration or automatic default account.

## Start Here

- [Documentation map](docs/README.md): find current guidance by task and learn how
  to maintain it without duplication.
- [Current status and next work](implementation_plan.md): implementation progress,
  latest verification, and outstanding acceptance.
- [User guide](docs/user_guide.md): everyday task, timesheet, and reporting workflows.
- [Requirements](requirements.md): authoritative scope and business rules.
- [Agent guidance](AGENTS.md): repository workflow and documentation obligations.
- [Project details archive](docs/archive/README.md): historical decisions and evidence.

## Local Development Quick Start

Requires Docker Engine and Compose. Commands run from the repository root.
Optionally copy `.env.example` to `.env` for local settings; defaults are for
local development only. See [development commands](docs/development.md) for
prerequisites, independent instances, account recovery, and troubleshooting.

```sh
docker compose config --quiet
docker compose build web frontend
docker compose up -d --wait
docker compose exec web python manage.py bootstrap_admin --email you@example.com
```

Open `http://127.0.0.1:5173` (use an SSH tunnel when running on the VDS).
Bootstrap prompts for a password and refuses if an administrator already exists.
`docker compose down` stops development while retaining database/upload volumes;
adding `--volumes` would remove that data.

## Verification

Run the isolated PostgreSQL/build/Chromium workflow sequentially:

```sh
sh scripts/test-runner.sh verification-1 full
```

Use a new label for each run. The wrapper captures results in ignored
`.artifacts/verification/` and uses scoped test cleanup. See
[test commands and helpers](docs/development.md#isolated-test-setup) and the
[testing charter](testing_charter.md) to select checks for a change.

Documentation checks (host Python 3 required):

```sh
python3 scripts/check-links.py
git diff --check
```

## Persistent Environments

The [operations guide](docs/environments.md) owns deployed releases, access URLs,
time zones, bootstrap, updates, live verification, and rollback instructions.
Persistent deployments require discussion and explicit authorization for the
release and target. Development/test completion does not authorize an upgrade.
