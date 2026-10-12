#!/bin/sh
set -eu

task_tracker_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
image_override=$(mktemp /tmp/task-tracker-images-XXXXXX.yaml)
cat > "$image_override" <<'YAML'
services:
  web:
    environment:
      UPLOAD_ROOT: /var/lib/task-tracker/uploads
    volumes:
      - image-restart:/var/lib/task-tracker/uploads
volumes:
  image-restart:
YAML
compose_images() {
    docker compose --project-directory "$task_tracker_root" -f "$task_tracker_root/compose.test.yaml" \
        -f "$image_override" -p task-tracker-tests "$@"
}
cleanup() {
    compose_images down --volumes --remove-orphans < /dev/null
    rm -f -- "$image_override"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
compose_images up -d --wait --wait-timeout 120 db web frontend < /dev/null
compose_images exec -T web python manage.py seed_test_data < /dev/null
compose_images exec -T -e IMAGE_CHECK_PHASE=before web python manage.py shell < "$task_tracker_root/scripts/image-persistence-check.py"
compose_images up -d --no-deps --force-recreate --wait --wait-timeout 120 web < /dev/null
compose_images exec -T -e IMAGE_CHECK_PHASE=after web python manage.py shell < "$task_tracker_root/scripts/image-persistence-check.py"
