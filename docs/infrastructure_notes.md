# Infrastructure Notes for Future Agents

Recorded on 2026-10-08 during the foundation work in `c54e5ad`. These are observed
setup problems, fixes, and verification limits, not new product requirements.
Use [README.md](../README.md) for setup commands and the
[implementation tracker](../implementation_plan.md) for current progress. Update
this note when a discovery changes; do not treat old session restrictions as
permanent properties of the VDS.

## Docker Access Is Session-Specific

The same agent session produced these different outcomes:

| Action | Observed outcome |
| --- | --- |
| `docker info --format '{{json .Driver}} {{json .ServerVersion}}'` | Succeeded; daemon reported 29.8.0. |
| `docker run ...` and `docker compose build web frontend` | Succeeded; containers ran and images built. |
| `docker compose config --quiet` and test-config validation | Succeeded; validates configuration, not service startup. |
| `docker version`, Compose startup, and `docker stop` | Docker socket permission denied. |
| Forwarding Ctrl-C to running verification sessions | Rejected by the tool's approval policy. |

This is evidence of command/session access differences, not proof of a broken
Docker installation or an incorrect host group. Check the current session's
execution permissions before repeating host-level troubleshooting. A successful
build/run does not establish permission to start Compose services or stop them.

Do not change socket permissions, add privileged containers, mount the Docker
socket into a helper container, or otherwise route around an execution restriction.
If required startup/shutdown access is unavailable, report that limitation and
ask for an authorized session or user-run verification.

## Establish Cleanup Before Starting Services

- `docker run --rm` removes a container after it exits; it does not make an
  indefinitely running server exit. Do not assume a terminal interrupt will work.
- Prefer bounded, disposable checks when possible. The verified browser fallback
  runs `timeout 120 sh /checks/browser-checks.sh` inside its container. That script
  starts its own temporary Vite server and waits for readiness. It still needs a
  separately running test API and database; it is not a complete environment.
- Confirm an authorized cleanup path before starting long-running API/database
  services. If stopping is denied, hand off exact names and ports; do not launch
  more unbounded copies or use broad prune/volume-removal commands.
- The previous fallback used only `task-tracker-foundation-db` (loopback 55439),
  `task-tracker-foundation-api` (loopback 8009), and
  `task-tracker-foundation-frontend` (loopback 5179). The bounded browser check used
  loopback 5180. These names/ports are not evidence that services are running now.

The user confirmed on 2026-10-08 that the three requested containers were stopped.
That confirmation was not independently inspected and does not demonstrate a
change to agent execution permissions. Recheck ownership/availability before
reusing names or ports; never stop an unrelated service to free a port.

## Non-Root Frontend Files Must Be Writable

The initial frontend build failed with `EACCES` while Vite wrote a temporary
configuration module beside `vite.config.ts`. Running as UID 1000 was insufficient
because `/app` and copied files were owned by root.

The fix in [docker/frontend.Dockerfile](../docker/frontend.Dockerfile) is to give
`/app` to the `node` user, install dependencies as that user, and use
`COPY --chown=node:node` for package manifests and sources. The non-root production
build and live Vite server subsequently worked. Preserve writable generated-file
locations when changing mounts; do not solve this by running everything as root or
making the entire source tree world-writable.

## Vite Must Recognize the Internal Compose Hostname

Loopback browser checks alone missed the hostname used by Compose. The
[Vite configuration](../frontend/vite.config.ts) explicitly permits `frontend` in
`server.allowedHosts`, while `/api` proxies to `web:8000` by default.

Keep this hostname aligned with Compose service names. Do not disable host
checking globally. The [foundation regression](../frontend/tests/foundation.spec.ts)
sends the internal hostname in the request and verifies acceptance. It passed,
but is not a substitute for verifying the complete Compose network/startup flow.

## Dependency Tool Cache and Runtime Differences

Backend lock generation initially failed when pip-tools tried to create the
unwritable default cache `/.cache`. It succeeded with an explicit
`--cache-dir /tmp/pip-cache`. The disposable container installed pip-tools 7.6.2
using `PYTHONUSERBASE=/tmp/pip-tools`, without changing a home-directory variable.
The resulting [backend lockfile](../backend/requirements.txt) includes hashes.
Keep lock generation under the selected Python 3.13 runtime and use a writable
tool-specific cache rather than modifying host permissions.

Host Node/npm were absent; no host installation was needed. Frontend builds use
the Node 22 image, while the Playwright image has its own Node/npm runtime. Keep
the Playwright package and image version aligned (currently 1.64.0). Its npm
printed an esbuild install-script warning, but the source build and browser checks
passed; that warning was not a failing check or a reason to enable all package
scripts indiscriminately.

## Django Migration Ordering and Test Guards

Create the schema migration before adding a data migration that depends on it.
Adding `core.0002_seed_mutation_lock` before `core.0001_initial` existed caused
`NodeNotFoundError` during `makemigrations`. The current ordering is correct:
the initial migration creates the table, then the data migration creates the
persistent `domain` coordination row. Do not rewrite already-applied migrations
to repeat this initial scaffolding workaround.

Use the dedicated test configuration, not development credentials:

- `APP_ENV=test`, database/user `task_tracker_test`, and temporary uploads.
- The backend test command rejects development settings; settings also reject
  mismatched test database/user configuration.
- The seed command accepts only the designated test databases/user and is
  repeatable. The test runner creates `test_task_tracker_test`; browser fixtures
  use `task_tracker_test` separately.
- `scripts/test.sh` resets only the fixed `task-tracker-tests` Compose project.
  Run it sequentially; do not point cleanup at the development project/volume.

## What Was and Was Not Verified

At the foundation milestone: images built, PostgreSQL 17.11 migrations and drift
checks passed, 13 backend tests passed, TypeScript/production builds passed, and
3 Playwright Chromium checks passed using the documented component arrangement.
Source-mounted backend checks and the rebuilt backend image were both exercised.

Full development Compose startup and the combined Compose reset/test/cleanup
script have not been exercised successfully. Next verification is that complete
workflow, including repeatability and cleanup, before Stage 2 is marked Done.
No application tests were rerun just to write this note.
