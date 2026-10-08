#!/bin/sh
set -eu

task_tracker_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_test() {
    docker compose --project-directory "$task_tracker_root" \
        -f "$task_tracker_root/compose.test.yaml" -p task-tracker-tests "$@"
}

# This fixed project/config owns only synthetic test services and ephemeral data.
# Do not run simultaneous instances: each run recreates that same test project.
trap 'compose_test down --volumes' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
compose_test down --volumes
compose_test build web frontend
compose_test up -d --wait --wait-timeout 120 db web frontend
compose_test exec -T web python manage.py check
compose_test exec -T web python manage.py makemigrations --check --dry-run
compose_test exec -T web python manage.py test --noinput -v 2
compose_test exec -T web python manage.py seed_test_data
compose_test exec -T frontend npm run build
compose_test run --rm browser
