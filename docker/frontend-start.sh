#!/bin/sh
set -eu
. /etc/task-tracker/instance.env
[ "${APP_BASE_PATH:-}" = "$BUILT_BASE_PATH" ] && [ "${INSTANCE_ID:-}" = "$BUILT_INSTANCE_ID" ] || {
    printf 'Frontend image/runtime instance mismatch; rebuild for the configured path and ID.\n' >&2
    exit 1
}
case "${PUBLIC_SCHEME:-}" in http|https) ;; *) printf 'Invalid PUBLIC_SCHEME.\n' >&2; exit 1 ;; esac
printf '%s' "${PUBLIC_HOST:-}" | grep -Eq '^[a-zA-Z0-9.-]+$' || { printf 'Invalid PUBLIC_HOST.\n' >&2; exit 1; }
# The backend is private and Compose waits for health before this service starts.
if ! wget -q -S --header "Host: $PUBLIC_HOST" -O /tmp/backend-health http://web:8000/api/v1/health/ 2>/tmp/backend-headers; then
    cat /tmp/backend-headers >&2
    printf 'Backend readiness request failed.\n' >&2
    exit 1
fi
backend_path=$(awk 'tolower($1) == "x-task-tracker-base-path:" {gsub("\r", "", $2); print $2}' /tmp/backend-headers)
backend_id=$(awk 'tolower($1) == "x-task-tracker-instance:" {gsub("\r", "", $2); print $2}' /tmp/backend-headers)
[ "$backend_path" = "$BUILT_BASE_PATH" ] && [ "$backend_id" = "$BUILT_INSTANCE_ID" ] || {
    printf 'Frontend/backend instance mismatch.\n' >&2
    exit 1
}
envsubst '${PUBLIC_SCHEME} ${PUBLIC_HOST}' < /etc/task-tracker/nginx.conf.template > /tmp/nginx.conf
exec nginx -c /tmp/nginx.conf -g 'daemon off;'
