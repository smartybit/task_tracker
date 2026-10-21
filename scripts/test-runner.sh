#!/bin/sh
set -u

# Keep this wrapper in the foreground; scripts/test.sh owns full-suite cleanup.
if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    printf 'Usage: sh scripts/test-runner.sh LABEL [full|account] [OUTPUT_DIRECTORY]\n' >&2
    exit 2
fi
run_label=$1
run_mode=${2:-full}
case "$run_label" in
    ''|*[!a-zA-Z0-9_-]*)
        printf 'LABEL must contain only letters, digits, underscores, or hyphens.\n' >&2
        exit 2 ;;
esac
case "$run_mode" in
    full|account) ;;
    *) printf 'Mode must be full or account.\n' >&2; exit 2 ;;
esac

task_tracker_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd) || exit 1
# Resolve a supplied relative output directory from the caller's directory.
output_directory=${3:-"$task_tracker_root/.artifacts/verification"}
mkdir -p -- "$output_directory" || exit 1
output_directory=$(CDPATH= cd -- "$output_directory" && pwd) || exit 1
run_log="$output_directory/$run_label.log"
run_status="$output_directory/$run_label.status"
if [ -e "$run_log" ] || [ -e "$run_status" ]; then
    printf 'Results already exist for this label; choose a new LABEL.\n' >&2
    exit 2
fi
cd -- "$task_tracker_root" || exit 1
printf 'Log: %s\nStatus: %s\n' "$run_log" "$run_status"
if [ "$run_mode" = account ]; then
    timeout --foreground 180 docker compose -f compose.test.yaml -p task-tracker-tests run --rm browser npm run test:e2e -- tests/accounts.spec.ts --grep 'administrator creates' --max-failures=1 < /dev/null > "$run_log" 2>&1
else
    timeout --foreground 2700 sh scripts/test.sh < /dev/null > "$run_log" 2>&1
fi
run_result=$?
printf '%s\n' "$run_result" > "$run_status" || exit 1
exit "$run_result"
