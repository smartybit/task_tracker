#!/bin/sh
set -eu
if [ "${1:-}" = '--run' ]; then
    task_tracker_root=$2
else
    task_tracker_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
fi
if [ "${1:-}" != '--run' ]; then
    if [ "$#" -ne 1 ]; then printf 'Usage: sh scripts/check-instances-dev.sh LABEL\n' >&2; exit 2; fi
    instance_label=$1
    case "$instance_label" in ''|*[!a-zA-Z0-9_-]*) printf 'Invalid label.\n' >&2; exit 2 ;; esac
    instance_results="$task_tracker_root/.artifacts/verification"
    mkdir -p "$instance_results"
    if [ -e "$instance_results/$instance_label.log" ] || [ -e "$instance_results/$instance_label.status" ]; then printf 'Choose a new label.\n' >&2; exit 2; fi
    exec 9>"$instance_results/development-instance-tests.lock"
    flock -n 9 || { printf 'Another development-instance check is running.\n' >&2; exit 2; }
    printf 'Log: %s\n' "$instance_results/$instance_label.log"
    instance_runner=$(mktemp /tmp/task-tracker-instance-runner-XXXXXX)
    cp "$0" "$instance_runner"
    set +e
    timeout --foreground 1200 sh "$instance_runner" --run "$task_tracker_root" > "$instance_results/$instance_label.log" 2>&1 < /dev/null
    instance_result=$?
    set -e
    printf '%s\n' "$instance_result" > "$instance_results/$instance_label.status"
    rm -f -- "$instance_runner"
    exit "$instance_result"
fi
cd "$task_tracker_root"
instance_directory=$(mktemp -d /tmp/task-tracker-instance-check-XXXXXX)
python3 - "$instance_directory" <<'PY'
import secrets
import socket
import sys
from pathlib import Path
used_ports = set()
for side, path in [('a', '/instance-a/'), ('b', '/team/instance-b/')]:
    while True:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        if port not in used_ports:
            used_ports.add(port)
            break
    values = dict(INSTANCE_ID=f'task-tracker-instance-check-{side}', APP_BASE_PATH=path, FRONTEND_PORT=str(port),
                  POSTGRES_PASSWORD=secrets.token_hex(24), DJANGO_SECRET_KEY=secrets.token_hex(32))
    target = Path(sys.argv[1]) / f'{side}.env'
    target.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    target.chmod(0o600)
PY
compose_instance_check() {
    instance_side=$1
    shift
    case "$instance_side" in a|b) ;; *) exit 2 ;; esac
    env -u INSTANCE_ID -u APP_BASE_PATH -u FRONTEND_PORT -u INSTANCE_VERSION -u POSTGRES_DB -u POSTGRES_USER \
        -u POSTGRES_PASSWORD -u DJANGO_SECRET_KEY -u WORKING_TIME_ZONE \
        docker compose --project-directory "$task_tracker_root" --env-file "$instance_directory/$instance_side.env" \
        -f "$task_tracker_root/compose.instances.dev.yaml" -p "task-tracker-instance-check-$instance_side" "$@"
}
cleanup() {
    instance_cleanup_result=0
    for instance_side in a b; do compose_instance_check "$instance_side" down --volumes --remove-orphans || instance_cleanup_result=$?; done
    rm -f -- "$instance_directory/a.env" "$instance_directory/b.env"
    rmdir -- "$instance_directory"
    if [ "$instance_cleanup_result" -ne 0 ]; then exit "$instance_cleanup_result"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for instance_side in a b; do
    compose_instance_check "$instance_side" down --volumes --remove-orphans
    compose_instance_check "$instance_side" up -d --build --wait --wait-timeout 150
    compose_instance_check "$instance_side" exec -T -e INSTANCE_CHECK_PHASE=before web python manage.py shell < scripts/development-instance-check.py
    compose_instance_check "$instance_side" exec -T -e INSTANCE_CHECK_PHASE=before frontend node --input-type=module < scripts/development-frontend-check.mjs
done
instance_b_ids=$(compose_instance_check b ps -q)
compose_instance_check a exec -T -e INSTANCE_CHECK_PHASE=reset web python manage.py shell < scripts/development-instance-check.py
compose_instance_check a up -d --no-deps --force-recreate --wait --wait-timeout 120 web frontend
test "$instance_b_ids" = "$(compose_instance_check b ps -q)"
for instance_side in a b; do
    compose_instance_check "$instance_side" exec -T -e INSTANCE_CHECK_PHASE=after web python manage.py shell < scripts/development-instance-check.py
    compose_instance_check "$instance_side" exec -T -e INSTANCE_CHECK_PHASE=after frontend node --input-type=module < scripts/development-frontend-check.mjs
done
printf 'Development instance configuration, targeted management and sibling resource preservation passed.\n'
