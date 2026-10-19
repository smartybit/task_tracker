#!/bin/sh
set -eu

if [ "${1:-}" = '--run' ]; then
    task_tracker_root=$4
else
    task_tracker_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
fi
if [ "${1:-}" != '--run' ]; then
    if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
        printf 'Usage: sh scripts/test-prefixes.sh LABEL [sibling|nested]\n' >&2; exit 2
    fi
    prefix_label=$1
    case "$prefix_label" in ''|*[!a-zA-Z0-9_-]*) printf 'Invalid label.\n' >&2; exit 2 ;; esac
    prefix_mode=${2:-sibling}
    case "$prefix_mode" in sibling|nested) ;; *) printf 'Invalid mode.\n' >&2; exit 2 ;; esac
    result_directory="$task_tracker_root/.artifacts/verification"
    mkdir -p "$result_directory"
    prefix_log="$result_directory/$prefix_label.log"
    prefix_status="$result_directory/$prefix_label.status"
    if [ -e "$prefix_log" ] || [ -e "$prefix_status" ]; then printf 'Choose a new label.\n' >&2; exit 2; fi
    # This fixed disposable project must never have overlapping runner invocations.
    exec 9>"$result_directory/prefix-tests.lock"
    flock -n 9 || { printf 'Another prefix verification is running.\n' >&2; exit 2; }
    printf 'Log: %s\nStatus: %s\n' "$prefix_log" "$prefix_status"
    prefix_runner=$(mktemp /tmp/task-tracker-prefix-runner-XXXXXX)
    cp "$0" "$prefix_runner"
    set +e
    timeout --foreground 1800 sh "$prefix_runner" --run "$prefix_label" "$prefix_mode" "$task_tracker_root" > "$prefix_log" 2>&1 < /dev/null
    prefix_result=$?
    set -e
    printf '%s\n' "$prefix_result" > "$prefix_status"
    rm -f -- "$prefix_runner"
    exit "$prefix_result"
fi

cd "$task_tracker_root"
PREFIX_LABEL=$2
export PREFIX_LABEL
PREFIX_VERSION_A=local
export PREFIX_VERSION_A
if [ "$3" = nested ]; then PREFIX_PATH_B=/team/time-tracker-prod/; else PREFIX_PATH_B=/time-tracker-prod/; fi
export PREFIX_PATH_B
PREFIX_TLS_DIRECTORY=$(mktemp -d /tmp/task-tracker-prefix-tls-XXXXXX)
export PREFIX_TLS_DIRECTORY
compose_prefix() {
    docker compose --project-directory "$task_tracker_root" -f "$task_tracker_root/compose.prefix-test.yaml" -p task-tracker-prefix-tests "$@"
}
cleanup() {
    prefix_run_result=$?
    prefix_cleanup_result=0
    if [ "$prefix_run_result" -ne 0 ]; then
        compose_prefix logs --no-color --tail 80 gateway frontend-a frontend-b observer || true
    fi
    compose_prefix down --volumes --remove-orphans < /dev/null || prefix_cleanup_result=$?
    rm -f -- "$PREFIX_TLS_DIRECTORY/key.pem" "$PREFIX_TLS_DIRECTORY/cert.pem"
    rmdir -- "$PREFIX_TLS_DIRECTORY"
    if [ "$prefix_cleanup_result" -ne 0 ]; then exit "$prefix_cleanup_result"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=gateway -addext subjectAltName=DNS:gateway \
    -keyout "$PREFIX_TLS_DIRECTORY/key.pem" -out "$PREFIX_TLS_DIRECTORY/cert.pem" > /dev/null 2>&1
compose_prefix down --volumes --remove-orphans
compose_prefix build web-a web-b frontend-a frontend-b
compose_prefix up -d --wait --wait-timeout 150 db-a db-b web-a web-b frontend-a frontend-b gateway
for prefix_web in web-a web-b; do
    compose_prefix exec -T "$prefix_web" python manage.py check
    compose_prefix exec -T "$prefix_web" python manage.py makemigrations --check --dry-run
    compose_prefix exec -T "$prefix_web" python manage.py seed_test_data
done
for prefix_frontend in frontend-a frontend-b; do
    compose_prefix exec -T "$prefix_frontend" npm run test:config
    compose_prefix exec -T "$prefix_frontend" npm run build
done
# Expected failures must contain the validation error, not a daemon/network failure.
expect_failure() {
    prefix_expected=$1
    shift
    prefix_negative_log="$task_tracker_root/.artifacts/verification/$PREFIX_LABEL-negative.log"
    if "$@" > "$prefix_negative_log" 2>&1; then printf 'Invalid configuration unexpectedly started.\n' >&2; exit 1; fi
    grep -F "$prefix_expected" "$prefix_negative_log"
}
expect_failure 'differs from the frontend image' compose_prefix run --rm --no-deps -e APP_BASE_PATH=/wrong/ frontend-a npm run dev
expect_failure 'Frontend/backend instance configuration mismatch' compose_prefix run --rm --no-deps -e API_PROXY_TARGET=http://web-b:8000 frontend-a npm run dev
expect_failure 'must be distinct' compose_prefix run --rm --no-deps \
    -e 'PREFIX_ROUTES=[{"prefix":"/one/","instanceId":"same","target":"http://frontend-a:5173"},{"prefix":"/two/","instanceId":"same","target":"http://frontend-b:5173"}]' gateway
expect_failure 'must be distinct' compose_prefix run --rm --no-deps \
    -e 'PREFIX_ROUTES=[{"prefix":"/one/","instanceId":"first","target":"http://frontend-a:5173"},{"prefix":"/one/nested/","instanceId":"second","target":"http://frontend-b:5173"}]' gateway
if [ "$3" = nested ]; then
    compose_prefix run --rm --no-deps browser npm run test:e2e -- tests/instances.spec.ts --max-failures=1
else
    compose_prefix run --rm --no-deps browser npm run test:e2e -- tests/instances.spec.ts tests/images.spec.ts tests/references.spec.ts \
        tests/reports.spec.ts tests/search.spec.ts tests/timesheets.spec.ts \
        --grep 'instances:|description images|clipboard screenshots|description references|remark picker|actual CSV|English and Russian|current work supports' --max-failures=1
fi
prefix_browser_artifacts="$task_tracker_root/.artifacts/verification/$PREFIX_LABEL-browser"
cp -R "$task_tracker_root/frontend/test-results" "$prefix_browser_artifacts"
prefix_b_ids=$(compose_prefix ps -q db-b web-b frontend-b)
compose_prefix exec -T -e PREFIX_CHECK_PHASE=reset web-a python manage.py shell < scripts/prefix-persistence.py
for prefix_web in web-a web-b; do
    compose_prefix exec -T -e PREFIX_CHECK_PHASE=before "$prefix_web" python manage.py shell < scripts/prefix-persistence.py
done
compose_prefix up -d --wait --wait-timeout 30 observer
PREFIX_VERSION_A=updated
export PREFIX_VERSION_A
compose_prefix build web-a
compose_prefix up -d --no-deps --force-recreate --wait --wait-timeout 120 web-a
test "$prefix_b_ids" = "$(compose_prefix ps -q db-b web-b frontend-b)"
compose_prefix exec -T observer node -e "const n = Number(require('node:fs').readFileSync('/tmp/observer-count', 'utf8')); if (n < 2) process.exit(1); console.log('Sibling remained healthy during ' + n + ' observations.');"
compose_prefix stop observer
compose_prefix logs observer
for prefix_web in web-a web-b; do
    compose_prefix exec -T -e PREFIX_CHECK_PHASE=after "$prefix_web" python manage.py shell < scripts/prefix-persistence.py
done
compose_prefix run --rm --no-deps -e PREFIX_PHASE=after browser npm run test:e2e -- tests/instances.spec.ts --max-failures=1
cp -R "$task_tracker_root/frontend/test-results" "$task_tracker_root/.artifacts/verification/$PREFIX_LABEL-after-browser"
printf 'Paired instance lifecycle and sibling resource preservation passed.\n'
